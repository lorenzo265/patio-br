"""Rotas do cadastro com login de verdade: só dentro da empresa, só com o papel certo."""

from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nuvem.semente import SENHA_DAS_CAMERAS, Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]


def test_sem_login_a_rota_responde_401(app: FastAPI, cenario: Demonstracao) -> None:
    resposta = TestClient(app).get(f"/api/cadastro/sites/{cenario.site_a.id}")

    assert (resposta.status_code, resposta.json()) == (401, {"detail": "entre no sistema"})


def test_cookie_inventado_responde_401(app: FastAPI, cenario: Demonstracao) -> None:
    cliente = TestClient(app, cookies={"patio_sessao": "codigo-inventado"})

    assert cliente.get("/api/cadastro/sites").status_code == 401


def test_usuario_da_empresa_a_nao_ve_nada_da_empresa_b(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    # O teste obrigatório da separação (SDD 5.5), agora pela rota, com login de verdade.
    gestor_a = entrar(cenario.gestor_a.email)
    site_b = cenario.site_b.id

    assert [site["id"] for site in gestor_a.get("/api/cadastro/sites").json()] == [
        cenario.site_a.id
    ]
    for rota in (f"/api/cadastro/sites/{site_b}", f"/api/cadastro/sites/{site_b}/cameras"):
        resposta = gestor_a.get(rota)
        assert (resposta.status_code, resposta.json()) == (404, {"detail": "não encontrado"})


def test_usuario_da_empresa_b_nao_ve_nada_da_empresa_a(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    gestor_b = entrar(cenario.gestor_b.email)

    assert [site["id"] for site in gestor_b.get("/api/cadastro/sites").json()] == [
        cenario.site_b.id
    ]
    assert gestor_b.get(f"/api/cadastro/sites/{cenario.site_a.id}").status_code == 404


def test_site_da_empresa_sem_ligacao_com_o_usuario_responde_404(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    gestor_a = entrar(cenario.gestor_a.email)

    assert gestor_a.get(f"/api/cadastro/sites/{cenario.site_a2.id}").status_code == 404


def test_cameras_saem_sem_a_senha(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.gestor_a.email).get(
        f"/api/cadastro/sites/{cenario.site_a.id}/cameras"
    )

    assert resposta.status_code == 200
    assert "senha" not in resposta.text
    assert SENHA_DAS_CAMERAS not in resposta.text
    assert cenario.camera_a.senha_cifrada not in resposta.text


def test_porteiro_ve_os_sites_dele(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.porteiro_a.email).get("/api/cadastro/sites")

    assert [site["id"] for site in resposta.json()] == [cenario.site_a.id]


@pytest.mark.parametrize("quem", ["porteiro_a", "patio_a"])
def test_so_o_gestor_ve_as_cameras(entrar: Entrar, cenario: Demonstracao, quem: str) -> None:
    usuario = getattr(cenario, quem)

    resposta = entrar(usuario.email).get(f"/api/cadastro/sites/{cenario.site_a.id}/cameras")

    assert (resposta.status_code, resposta.json()) == (403, {"detail": "sem permissão"})


def test_administracao_nao_usa_as_rotas_do_cliente(entrar: Entrar, cenario: Demonstracao) -> None:
    # A administração tem rotas próprias (D-19); nas do cliente, ela não tem empresa nem site.
    resposta = entrar(cenario.administrador.email).get("/api/cadastro/sites")

    assert resposta.status_code == 403


def test_usuario_do_cliente_nao_entra_nas_rotas_da_administracao(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    resposta = entrar(cenario.gestor_a.email).get("/api/admin/empresas")

    assert (resposta.status_code, resposta.json()) == (403, {"detail": "sem permissão"})


def test_rotas_da_administracao_sem_login_respondem_401(
    app: FastAPI, cenario: Demonstracao
) -> None:
    assert TestClient(app).get("/api/admin/empresas").status_code == 401


def test_administracao_ve_todas_as_empresas(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.administrador.email).get("/api/admin/empresas")

    assert resposta.status_code == 200
    assert [empresa["cnpj"] for empresa in resposta.json()] == [
        cenario.empresa_a.cnpj,
        cenario.empresa_b.cnpj,
    ]

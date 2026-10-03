"""Rotas da frota: a administração gera o código; a caixa ativa e baixa a configuração."""

from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from nuvem.cadastro import servico as servico_do_cadastro
from nuvem.semente import SENHA_DAS_CAMERAS, Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]


def _gerar_codigo(administracao: TestClient, site_id: int) -> str:
    resposta = administracao.post(f"/api/admin/sites/{site_id}/codigos-de-ativacao")
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["codigo"])


def _ativar(app: FastAPI, codigo: str) -> dict[str, str]:
    resposta = TestClient(app).post("/api/borda/ativar", json={"codigo": codigo})
    assert resposta.status_code == 201, resposta.text
    return dict(resposta.json())


def _caixa(app: FastAPI, chave: str) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {chave}"})


@pytest.fixture
def administracao(entrar: Entrar, cenario: Demonstracao) -> TestClient:
    return entrar(cenario.administrador.email)


def test_administracao_gera_codigo_que_vence_em_24_horas(
    administracao: TestClient, cenario: Demonstracao
) -> None:
    resposta = administracao.post(f"/api/admin/sites/{cenario.site_a.id}/codigos-de-ativacao")

    assert resposta.status_code == 201
    assert set(resposta.json()) == {"codigo", "expira_em"}


def test_usuario_do_cliente_nao_gera_codigo(entrar: Entrar, cenario: Demonstracao) -> None:
    gestor = entrar(cenario.gestor_a.email)

    resposta = gestor.post(f"/api/admin/sites/{cenario.site_a.id}/codigos-de-ativacao")

    assert resposta.status_code == 403


def test_codigo_para_site_que_nao_existe_responde_404(administracao: TestClient) -> None:
    assert administracao.post("/api/admin/sites/999999/codigos-de-ativacao").status_code == 404


def test_caixa_ativa_e_recebe_a_chave(
    app: FastAPI, administracao: TestClient, cenario: Demonstracao
) -> None:
    ativada = _ativar(app, _gerar_codigo(administracao, cenario.site_a.id))

    assert set(ativada) == {"caixa_id", "site_id", "chave"}
    assert ativada["site_id"] == str(cenario.site_a.id)


def test_mesmo_codigo_na_segunda_vez_responde_401(
    app: FastAPI, administracao: TestClient, cenario: Demonstracao
) -> None:
    codigo = _gerar_codigo(administracao, cenario.site_a.id)
    _ativar(app, codigo)

    resposta = TestClient(app).post("/api/borda/ativar", json={"codigo": codigo})

    assert resposta.status_code == 401
    assert resposta.json() == {"detail": "código de ativação inválido, já usado ou vencido"}


def test_ativar_sem_o_codigo_responde_422_apontando_o_campo(app: FastAPI) -> None:
    resposta = TestClient(app).post("/api/borda/ativar", json={})

    assert resposta.status_code == 422
    assert [erro["loc"] for erro in resposta.json()["detail"]] == [["body", "codigo"]]


def test_caixa_baixa_a_configuracao_do_proprio_site(
    app: FastAPI, administracao: TestClient, cenario: Demonstracao
) -> None:
    ativada = _ativar(app, _gerar_codigo(administracao, cenario.site_a.id))

    resposta = _caixa(app, ativada["chave"]).get("/api/borda/configuracao")

    assert resposta.status_code == 200
    configuracao = resposta.json()
    assert configuracao["caixa_id"] == ativada["caixa_id"]
    assert configuracao["site_id"] == str(cenario.site_a.id)
    assert [(f["nome"], f["sentido"]) for f in configuracao["faixas"]] == [
        ("Entrada 1", "entrada"),
        ("Saída 1", "saida"),
    ]
    entrada = configuracao["faixas"][0]
    assert entrada["id"] == str(cenario.faixa_a.id)
    assert [c["posicao"] for c in entrada["cameras"]] == ["frente", "tras"]
    # A caixa precisa da senha para ler o vídeo da câmera: só ela a recebe, decifrada.
    assert entrada["cameras"][0]["senha"] == SENHA_DAS_CAMERAS


def test_caixa_da_empresa_b_so_ve_o_site_dela(
    app: FastAPI, administracao: TestClient, cenario: Demonstracao
) -> None:
    ativada = _ativar(app, _gerar_codigo(administracao, cenario.site_b.id))

    configuracao = _caixa(app, ativada["chave"]).get("/api/borda/configuracao").json()

    assert configuracao["site_id"] == str(cenario.site_b.id)
    cameras = [c["id"] for f in configuracao["faixas"] for c in f["cameras"]]
    assert cameras == [str(cenario.camera_b.id)]


def test_sem_chave_responde_401_pedindo_bearer(app: FastAPI) -> None:
    resposta = TestClient(app).get("/api/borda/configuracao")

    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


def test_chave_inventada_responde_401(app: FastAPI) -> None:
    assert _caixa(app, "chave-inventada").get("/api/borda/configuracao").status_code == 401


def test_chave_revogada_responde_401(
    app: FastAPI, administracao: TestClient, cenario: Demonstracao
) -> None:
    ativada = _ativar(app, _gerar_codigo(administracao, cenario.site_a.id))

    revogacao = administracao.post(f"/api/admin/caixas/{ativada['caixa_id']}/revogar")

    assert revogacao.status_code == 200
    assert _caixa(app, ativada["chave"]).get("/api/borda/configuracao").status_code == 401


def test_administracao_lista_as_caixas(
    app: FastAPI, administracao: TestClient, cenario: Demonstracao
) -> None:
    ativada = _ativar(app, _gerar_codigo(administracao, cenario.site_a.id))
    administracao.post(f"/api/admin/caixas/{ativada['caixa_id']}/revogar")

    caixas = administracao.get("/api/admin/caixas").json()

    assert [(c["id"], c["site_id"], c["revogada"]) for c in caixas] == [
        (int(ativada["caixa_id"]), cenario.site_a.id, True)
    ]


def test_usuario_do_cliente_nao_revoga_caixa(entrar: Entrar, cenario: Demonstracao) -> None:
    assert entrar(cenario.gestor_a.email).post("/api/admin/caixas/1/revogar").status_code == 403


def test_sessao_do_painel_nao_serve_de_chave_da_caixa(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    # O cookie do login é de pessoa; a caixa se identifica só pela chave.
    assert entrar(cenario.gestor_a.email).get("/api/borda/configuracao").status_code == 401


def test_caixa_nao_ve_as_faixas_de_outro_site_da_mesma_empresa(
    app: FastAPI, administracao: TestClient, cenario: Demonstracao, sessao: Session
) -> None:
    portaria = servico_do_cadastro.criar_portaria(sessao, cenario.site_a2, nome="Portaria 2")
    servico_do_cadastro.criar_faixa(sessao, portaria, nome="Entrada do site 2", sentido="entrada")
    ativada = _ativar(app, _gerar_codigo(administracao, cenario.site_a.id))

    configuracao = _caixa(app, ativada["chave"]).get("/api/borda/configuracao").json()

    assert "Entrada do site 2" not in [faixa["nome"] for faixa in configuracao["faixas"]]

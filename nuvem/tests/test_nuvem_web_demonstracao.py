"""A tela do dia de demonstração (T45, D-49): começar o dia e acompanhar."""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from nuvem.cifra import Cifra
from nuvem.demonstracao import empresa
from nuvem.demonstracao.empresa import EmpresaDeDemonstracao
from nuvem.relogio import agora
from nuvem.semente import Demonstracao
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
SENHA = "senha-da-demonstracao"


@pytest.fixture(autouse=True)
def _hora_fixa(app: FastAPI) -> None:
    app.dependency_overrides[agora] = lambda: AGORA


@pytest.fixture
def demo(
    sessao: Session, senhas: Senhas, cifra: Cifra, cenario: Demonstracao
) -> EmpresaDeDemonstracao:
    return empresa.criar(
        sessao, senhas, cifra, nome="Empresa de demonstração", cnpj="DEMO0000000W00",
        dominio="web.demonstracao.example", senha=SENHA, pin="246802",
        administrador_id=cenario.administrador.id, agora=AGORA, dias=1, semente=1,
    )  # fmt: skip


def _gestor(entrar: Entrar, demo: EmpresaDeDemonstracao) -> TestClient:
    return entrar(demo.gestor.email, SENHA)


def test_sem_login_vai_para_a_tela_de_entrar(app: FastAPI) -> None:
    resposta = TestClient(app).get("/demonstracao", follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


def test_so_o_gestor_comeca_o_dia(entrar: Entrar, demo: EmpresaDeDemonstracao) -> None:
    for pessoa in (demo.porteiro, demo.lider):
        cliente = entrar(pessoa.email, SENHA)
        assert cliente.get("/demonstracao").status_code == 403
        assert cliente.post("/demonstracao/comecar", data={"site": demo.site.id}).status_code == 403


def test_antes_de_comecar_a_tela_oferece_o_botao(
    entrar: Entrar, demo: EmpresaDeDemonstracao
) -> None:
    texto = _gestor(entrar, demo).get("/demonstracao").text

    assert 'action="/demonstracao/comecar"' in texto
    assert "Começar o dia" in texto


def test_comecar_o_dia_e_acompanhar(entrar: Entrar, demo: EmpresaDeDemonstracao) -> None:
    gestor = _gestor(entrar, demo)

    resposta = gestor.post(
        "/demonstracao/comecar", data={"site": demo.site.id}, follow_redirects=False
    )

    assert (resposta.status_code, resposta.headers["location"]) == (
        303, f"/demonstracao?site={demo.site.id}",
    )  # fmt: skip
    texto = gestor.get(f"/demonstracao?site={demo.site.id}").text
    assert "O dia está rodando" in texto
    assert "0 de 24 chegadas" in texto
    for caminho in ("/portaria", "/patio", "/mensagens", "/painel"):
        assert f'href="{caminho}?site={demo.site.id}"' in texto
    assert 'action="/demonstracao/comecar"' not in texto


def test_nao_comeca_dois_dias_ao_mesmo_tempo(entrar: Entrar, demo: EmpresaDeDemonstracao) -> None:
    gestor = _gestor(entrar, demo)
    gestor.post("/demonstracao/comecar", data={"site": demo.site.id})

    resposta = gestor.post("/demonstracao/comecar", data={"site": demo.site.id})

    assert resposta.status_code == 409
    assert "já está rodando" in resposta.text


def test_site_sem_caixa_avisa(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.gestor_a.email).post(
        "/demonstracao/comecar", data={"site": cenario.site_a.id}
    )

    assert resposta.status_code == 409
    assert "não tem caixa de borda" in resposta.text


def test_site_de_outra_empresa_responde_404(
    entrar: Entrar, cenario: Demonstracao, demo: EmpresaDeDemonstracao
) -> None:
    gestor = _gestor(entrar, demo)

    assert gestor.post("/demonstracao/comecar", data={"site": cenario.site_a.id}).status_code == 404
    assert gestor.get(f"/demonstracao?site={cenario.site_a.id}").status_code == 404


def test_fora_dos_ambientes_da_demonstracao_nada_disso_existe(
    app: FastAPI, entrar: Entrar, demo: EmpresaDeDemonstracao
) -> None:
    app.state.tem_demonstracao = False
    gestor = _gestor(entrar, demo)

    assert gestor.get("/demonstracao").status_code == 404
    assert gestor.post("/demonstracao/comecar", data={"site": demo.site.id}).status_code == 404
    assert 'href="/demonstracao"' not in gestor.get("/").text


def test_o_inicio_do_gestor_leva_a_demonstracao(
    entrar: Entrar, demo: EmpresaDeDemonstracao
) -> None:
    assert 'href="/demonstracao"' in _gestor(entrar, demo).get("/").text
    assert 'href="/demonstracao"' not in entrar(demo.porteiro.email, SENHA).get("/").text

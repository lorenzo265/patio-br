"""As telas do link de demonstração (T48, D-52 e D-54): a administração, a página do link e a
faixa que troca de papel."""

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nuvem.cadastro.acesso import COOKIE_DA_SESSAO, AcessoAdmin
from nuvem.cadastro.modelos import Empresa
from nuvem.config import Configuracao
from nuvem.demonstracao import empresa
from nuvem.demonstracao import link as demonstracao
from nuvem.principal import criar_app
from nuvem.relogio import agora
from nuvem.semente import Demonstracao
from nuvem.senhas import Senhas
from nuvem.web.agendar import EsconderCodigoDoLink

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
ADMINISTRACAO = "admin@patio-br.example"


@pytest.fixture(autouse=True)
def _hora_fixa_e_historico_curto(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[agora] = lambda: AGORA
    monkeypatch.setattr(empresa, "DIAS_DE_HISTORICO", 1)


@pytest.fixture
def codigo(sessao: Session, cenario: Demonstracao) -> str:
    gerado = demonstracao.gerar_link(
        sessao, AcessoAdmin(cenario.administrador.id), nome="Transportes Exemplo", agora=AGORA
    )
    sessao.commit()
    return gerado.codigo


def _empresas(sessao: Session) -> int:
    return sessao.scalar(select(func.count()).select_from(Empresa)) or 0


def _entrar_pelo_link(app: FastAPI, codigo: str) -> TestClient:
    cliente = TestClient(app)
    resposta = cliente.post(f"/demonstracao/link/{codigo}", follow_redirects=False)
    assert (resposta.status_code, resposta.headers["location"]) == (303, "/demonstracao")
    return cliente


# --- A página do link -------------------------------------------------------------------------


def test_a_pagina_do_link_mostra_para_quem_e_e_nao_cria_nada(
    app: FastAPI, sessao: Session, codigo: str
) -> None:
    empresas = _empresas(sessao)

    resposta = TestClient(app).get(f"/demonstracao/link/{codigo}")

    assert resposta.status_code == 200
    assert "Transportes Exemplo" in resposta.text
    assert f'action="/demonstracao/link/{codigo}"' in resposta.text
    assert COOKIE_DA_SESSAO not in resposta.cookies
    assert _empresas(sessao) == empresas
    assert resposta.headers["referrer-policy"] == "no-referrer"
    assert "no-store" in resposta.headers["cache-control"]


def test_entrar_pelo_link_leva_ao_dia_de_demonstracao_como_gestor(
    app: FastAPI, codigo: str
) -> None:
    cliente = _entrar_pelo_link(app, codigo)

    texto = cliente.get("/demonstracao").text
    assert "Começar o dia" in texto
    assert "Transportes Exemplo (demonstração)" in cliente.get("/").text


def test_entrar_vindo_de_outro_site_e_recusado(app: FastAPI, sessao: Session, codigo: str) -> None:
    empresas = _empresas(sessao)

    resposta = TestClient(app).post(
        f"/demonstracao/link/{codigo}", headers={"Sec-Fetch-Site": "cross-site"}
    )

    assert resposta.status_code == 403
    assert COOKIE_DA_SESSAO not in resposta.cookies
    assert _empresas(sessao) == empresas


@pytest.mark.parametrize("metodo", ["get", "post"])
def test_link_inventado_da_404(app: FastAPI, cenario: Demonstracao, metodo: str) -> None:
    resposta = getattr(TestClient(app), metodo)("/demonstracao/link/inventado")

    assert resposta.status_code == 404
    assert "Este link de demonstração não vale mais" in resposta.text


def test_o_codigo_do_link_nao_aparece_no_registro_de_acesso() -> None:
    registro = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "POST", "/demonstracao/link/segredo-do-link", "1.1", 303), None,
    )  # fmt: skip

    EsconderCodigoDoLink().filter(registro)

    assert registro.getMessage() == '127.0.0.1 - "POST /demonstracao/link/*** HTTP/1.1" 303'


# --- A faixa que troca de papel ---------------------------------------------------------------


def test_a_faixa_de_papel_aparece_para_quem_entrou(app: FastAPI, codigo: str) -> None:
    texto = _entrar_pelo_link(app, codigo).get("/").text

    assert 'action="/demonstracao/papel"' in texto
    assert re.search(r'value="gestor"[^>]*aria-pressed="true"', texto)


def test_trocar_de_papel_pela_faixa(app: FastAPI, codigo: str) -> None:
    cliente = _entrar_pelo_link(app, codigo)

    resposta = cliente.post(
        "/demonstracao/papel", data={"papel": "porteiro"}, follow_redirects=False
    )

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/portaria")
    assert cliente.get("/portaria").status_code == 200
    destinos = {"patio": "/patio", "gestor": "/demonstracao"}
    for papel, destino in destinos.items():
        resposta = cliente.post(
            "/demonstracao/papel", data={"papel": papel}, follow_redirects=False
        )
        assert resposta.headers["location"] == destino


def test_trocar_de_papel_pede_login(app: FastAPI, cenario: Demonstracao) -> None:
    resposta = TestClient(app).post(
        "/demonstracao/papel", data={"papel": "porteiro"}, follow_redirects=False
    )

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


def test_papel_que_nao_existe_e_recusado(app: FastAPI, codigo: str) -> None:
    cliente = _entrar_pelo_link(app, codigo)

    resposta = cliente.post("/demonstracao/papel", data={"papel": "administracao"})

    assert resposta.status_code == 422


# --- A administração --------------------------------------------------------------------------


def test_a_administracao_gera_o_link_e_ve_o_endereco_uma_vez(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    administracao = entrar(ADMINISTRACAO)

    resposta = administracao.post("/administracao/demonstracao", data={"nome": "Atacado Exemplo"})

    assert resposta.status_code == 200
    assert resposta.headers["referrer-policy"] == "no-referrer"
    assert "no-store" in resposta.headers["cache-control"]
    endereco = re.search(r"http://testserver/demonstracao/link/[\w-]+", resposta.text)
    assert endereco is not None
    lista = administracao.get("/administracao/demonstracao").text
    assert "Atacado Exemplo" in lista
    assert endereco.group(0) not in lista


def test_a_administracao_revoga_o_link(
    entrar: Entrar, app: FastAPI, sessao: Session, cenario: Demonstracao, codigo: str
) -> None:
    administracao = entrar(ADMINISTRACAO)
    (link,) = demonstracao.listar_links(sessao, AcessoAdmin(cenario.administrador.id))

    resposta = administracao.post(
        f"/administracao/demonstracao/{link.id}/revogar", follow_redirects=False
    )

    assert (resposta.status_code, resposta.headers["location"]) == (
        303, "/administracao/demonstracao",
    )  # fmt: skip
    assert "revogado" in administracao.get("/administracao/demonstracao").text
    assert TestClient(app).get(f"/demonstracao/link/{codigo}").status_code == 404


def test_o_inicio_da_administracao_leva_aos_links(entrar: Entrar, cenario: Demonstracao) -> None:
    texto = entrar(ADMINISTRACAO).get("/").text

    assert 'href="/administracao/demonstracao"' in texto


def test_quem_e_do_cliente_nao_ve_a_administracao(entrar: Entrar, cenario: Demonstracao) -> None:
    gestor = entrar(cenario.gestor_a.email)

    assert gestor.get("/administracao/demonstracao").status_code == 403
    resposta = gestor.post("/administracao/demonstracao", data={"nome": "x"})
    assert resposta.status_code == 403


def test_sem_login_a_administracao_leva_a_tela_de_entrar(
    app: FastAPI, cenario: Demonstracao
) -> None:
    resposta = TestClient(app).get("/administracao/demonstracao", follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


# --- Fora dos ambientes da demonstração -------------------------------------------------------


@pytest.fixture
def app_de_producao(app: FastAPI, url_banco_teste: str, senhas: Senhas, tmp_path: Path) -> FastAPI:
    configuracao = Configuracao(
        url_banco=url_banco_teste,
        chave_cifra="e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw=",
        ambiente="producao",
        pasta_fotos=tmp_path / "fotos",
        _env_file=None,
    )
    producao = criar_app(configuracao, senhas=senhas)
    producao.dependency_overrides = app.dependency_overrides
    return producao


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("get", "/demonstracao/link/qualquer"),
        ("post", "/demonstracao/link/qualquer"),
        ("post", "/demonstracao/papel"),
        ("get", "/administracao/demonstracao"),
        ("post", "/administracao/demonstracao"),
    ],
)
def test_fora_da_demonstracao_nada_disso_existe(
    app_de_producao: FastAPI, cenario: Demonstracao, metodo: str, caminho: str
) -> None:
    resposta = getattr(TestClient(app_de_producao), metodo)(caminho)

    assert resposta.status_code == 404


def test_fora_da_demonstracao_a_faixa_de_papel_nao_aparece(
    app_de_producao: FastAPI, cenario: Demonstracao
) -> None:
    cliente = TestClient(app_de_producao, base_url="https://testserver")
    resposta = cliente.post(
        "/entrar",
        data={"email": cenario.gestor_a.email, "senha": "demonstracao-local"},
        follow_redirects=False,
    )
    assert resposta.status_code == 303

    assert "/demonstracao/papel" not in cliente.get("/").text

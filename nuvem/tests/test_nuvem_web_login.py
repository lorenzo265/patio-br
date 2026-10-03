"""Telas de entrar, sair e trocar de porteiro: cookie seguro e respostas certas."""

from collections.abc import Callable

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.config import Configuracao
from nuvem.principal import criar_app
from nuvem.semente import PIN_DA_DEMONSTRACAO, SENHA_DA_DEMONSTRACAO, Demonstracao
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]
CHAVE_QUALQUER = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="


def _postar_login(
    cliente: TestClient, email: str, senha: str = SENHA_DA_DEMONSTRACAO
) -> httpx2.Response:
    return cliente.post("/entrar", data={"email": email, "senha": senha}, follow_redirects=False)


def test_tela_de_entrar_tem_o_formulario(app: FastAPI) -> None:
    resposta = TestClient(app).get("/entrar")

    assert resposta.status_code == 200
    assert 'name="email"' in resposta.text
    assert 'name="senha"' in resposta.text


def test_entrar_leva_ao_inicio_com_o_cookie_da_sessao(app: FastAPI, cenario: Demonstracao) -> None:
    resposta = _postar_login(TestClient(app), cenario.gestor_a.email)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/")
    cookie = resposta.headers["set-cookie"].lower()
    assert cookie.startswith("patio_sessao=")
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "secure" not in cookie  # ambiente local: http://localhost


def test_fora_do_ambiente_local_o_cookie_e_secure(
    url_banco_teste: str, sessao: Session, senhas: Senhas, cenario: Demonstracao
) -> None:
    app = criar_app(
        Configuracao(
            url_banco=url_banco_teste,
            chave_cifra=CHAVE_QUALQUER,
            ambiente="producao",
            _env_file=None,
        ),
        senhas=senhas,
    )
    app.dependency_overrides[obter_sessao] = lambda: sessao

    resposta = _postar_login(TestClient(app), cenario.gestor_a.email)

    assert "secure" in resposta.headers["set-cookie"].lower()


def test_o_padrao_do_ambiente_e_producao() -> None:
    # Esquecer a variável em produção não pode tirar o Secure do cookie.
    configuracao = Configuracao(
        url_banco="postgresql+pg8000://x@y/z", chave_cifra=CHAVE_QUALQUER, _env_file=None
    )

    assert configuracao.ambiente == "producao"


def test_senha_errada_responde_401_sem_cookie(app: FastAPI, cenario: Demonstracao) -> None:
    resposta = _postar_login(TestClient(app), cenario.gestor_a.email, "nao-e-esta-a-senha")

    assert resposta.status_code == 401
    assert "set-cookie" not in resposta.headers
    assert "E-mail ou senha incorretos" in resposta.text


def test_sexta_tentativa_responde_429(app: FastAPI, cenario: Demonstracao) -> None:
    cliente = TestClient(app)
    for _ in range(5):
        _postar_login(cliente, cenario.gestor_a.email, "nao-e-esta-a-senha")

    resposta = _postar_login(cliente, cenario.gestor_a.email)

    assert resposta.status_code == 429
    assert "15 minutos" in resposta.text


def test_sem_o_email_responde_422_apontando_o_campo(app: FastAPI) -> None:
    resposta = TestClient(app).post("/entrar", data={"senha": "qualquer-coisa"})

    assert resposta.status_code == 422
    assert [erro["loc"] for erro in resposta.json()["detail"]] == [["body", "email"]]


def test_inicio_sem_login_leva_a_tela_de_entrar(app: FastAPI) -> None:
    resposta = TestClient(app).get("/", follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


def test_inicio_mostra_quem_entrou(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.gestor_a.email).get("/")

    assert resposta.status_code == 200
    assert "Gestor A" in resposta.text


def test_inicio_da_administracao(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.administrador.email).get("/")

    assert resposta.status_code == 200
    assert "Administração" in resposta.text


def test_sair_apaga_a_sessao_no_servidor(
    app: FastAPI, entrar: Entrar, cenario: Demonstracao
) -> None:
    cliente = entrar(cenario.gestor_a.email)
    codigo = cliente.cookies["patio_sessao"]

    resposta = cliente.post("/sair", follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")
    # Mesmo quem guardou o código não entra mais com ele.
    copia = TestClient(app, cookies={"patio_sessao": codigo})
    assert copia.get("/api/cadastro/sites").status_code == 401


def test_troca_de_porteiro_pela_tela(entrar: Entrar, cenario: Demonstracao) -> None:
    cliente = entrar(cenario.porteiro_a.email)

    tela = cliente.get("/trocar-porteiro")
    resposta = cliente.post(
        "/trocar-porteiro",
        data={"porteiro_id": cenario.porteiro_a_noite.id, "pin": PIN_DA_DEMONSTRACAO},
        follow_redirects=False,
    )

    assert "Porteiro A (noite)" in tela.text
    assert (resposta.status_code, resposta.headers["location"]) == (303, "/")
    assert "Porteiro A (noite)" in cliente.get("/").text


def test_pin_errado_na_tela_responde_401(entrar: Entrar, cenario: Demonstracao) -> None:
    cliente = entrar(cenario.porteiro_a.email)

    resposta = cliente.post(
        "/trocar-porteiro", data={"porteiro_id": cenario.porteiro_a_noite.id, "pin": "000000"}
    )

    assert resposta.status_code == 401
    assert "PIN incorreto" in resposta.text


def test_lider_de_patio_nao_troca_de_porteiro(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.patio_a.email).get("/trocar-porteiro")

    assert resposta.status_code == 403

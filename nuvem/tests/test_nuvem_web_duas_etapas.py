"""As telas da verificação em duas etapas (SDD 8.2, D-60) e o zerar da administração."""

import re
from collections.abc import Callable
from datetime import UTC, datetime

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nuvem.cadastro import duas_etapas
from nuvem.semente import SENHA_DA_DEMONSTRACAO, Demonstracao

pytestmark = pytest.mark.integracao

SEGREDO_NA_TELA = re.compile(r'id="segredo">([A-Z2-7 ]+)<')
CODIGO_DE_RECUPERACAO = re.compile(r"\b[a-hjkmnp-z2-9]{4}-[a-hjkmnp-z2-9]{4}\b")


@pytest.fixture
def app_que_exige(app: FastAPI) -> FastAPI:
    """A aplicação como na homologação e na produção: o gestor e a administração passam pela
    verificação (o resto do ambiente continua o local dos testes)."""
    app.state.exige_duas_etapas = True
    return app


Navegador = Callable[[], TestClient]


@pytest.fixture
def navegador(app: FastAPI, com_csrf: Callable[[TestClient], TestClient]) -> Navegador:
    """Abre um navegador novo, que põe o código anti-CSRF da sessão em cada pedido."""
    return lambda: com_csrf(TestClient(app))


def _postar_login(cliente: TestClient, email: str) -> httpx2.Response:
    return cliente.post(
        "/entrar",
        data={"email": email, "senha": SENHA_DA_DEMONSTRACAO},
        follow_redirects=False,
    )


def _codigo_do_app(segredo: str, adiante: int = 0) -> str:
    agora = datetime.now(UTC)
    return duas_etapas.codigo_do_passo(segredo, duas_etapas.passo_de(agora) + adiante)


def _ligar(cliente: TestClient, email: str) -> tuple[str, httpx2.Response]:
    """Entra pela primeira vez e liga a verificação pela tela; devolve o segredo e a resposta."""
    assert _postar_login(cliente, email).headers["location"] == "/entrar/ligar"
    tela = cliente.get("/entrar/ligar")
    achado = SEGREDO_NA_TELA.search(tela.text)
    assert achado, tela.text
    segredo = achado.group(1).replace(" ", "")
    resposta = cliente.post(
        "/entrar/ligar", data={"codigo": _codigo_do_app(segredo)}, follow_redirects=False
    )
    return segredo, resposta


def test_gestor_vai_para_a_tela_de_ligar_e_ainda_nao_entrou(
    app_que_exige: FastAPI, cenario: Demonstracao, navegador: Navegador
) -> None:
    cliente = navegador()

    resposta = _postar_login(cliente, cenario.gestor_a.email)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar/ligar")
    assert "max-age=600" in resposta.headers["set-cookie"].lower()
    inicio = cliente.get("/", follow_redirects=False)
    assert (inicio.status_code, inicio.headers["location"]) == (303, "/entrar")


def test_a_tela_de_ligar_mostra_o_qr_e_o_segredo(
    app_que_exige: FastAPI, cenario: Demonstracao, navegador: Navegador
) -> None:
    cliente = navegador()
    _postar_login(cliente, cenario.gestor_a.email)

    tela = cliente.get("/entrar/ligar")

    assert tela.status_code == 200
    assert "<svg" in tela.text
    assert SEGREDO_NA_TELA.search(tela.text)
    assert 'name="_csrf"' in tela.text
    assert 'autocomplete="one-time-code"' in tela.text


def test_ligar_mostra_os_codigos_de_recuperacao_uma_vez_e_entra(
    app_que_exige: FastAPI, cenario: Demonstracao, navegador: Navegador
) -> None:
    cliente = navegador()

    _, resposta = _ligar(cliente, cenario.gestor_a.email)

    assert resposta.status_code == 200
    assert len(set(CODIGO_DE_RECUPERACAO.findall(resposta.text))) == 10
    assert resposta.headers["cache-control"] == "no-store"
    assert "patio_sessao=" in resposta.headers["set-cookie"]
    assert cliente.get("/", follow_redirects=False).status_code == 200


def test_depois_de_ligar_o_login_pede_o_codigo_e_entra_com_ele(
    app_que_exige: FastAPI, cenario: Demonstracao, navegador: Navegador
) -> None:
    segredo, _ = _ligar(navegador(), cenario.gestor_a.email)
    cliente = navegador()

    login = _postar_login(cliente, cenario.gestor_a.email)
    tela = cliente.get("/entrar/codigo")
    # O código do intervalo seguinte: o de agora pode ter sido o usado para ligar.
    resposta = cliente.post(
        "/entrar/codigo", data={"codigo": _codigo_do_app(segredo, 1)}, follow_redirects=False
    )

    assert login.headers["location"] == "/entrar/codigo"
    assert 'inputmode="numeric"' in tela.text
    assert (resposta.status_code, resposta.headers["location"]) == (303, "/")
    assert cliente.get("/", follow_redirects=False).status_code == 200


def test_codigo_errado_responde_401_e_depois_de_5_responde_429(
    app_que_exige: FastAPI, cenario: Demonstracao, navegador: Navegador
) -> None:
    segredo, _ = _ligar(navegador(), cenario.gestor_a.email)
    cliente = navegador()
    _postar_login(cliente, cenario.gestor_a.email)
    errado = _codigo_do_app(segredo, 9)

    respostas = [
        cliente.post("/entrar/codigo", data={"codigo": errado}).status_code for _ in range(6)
    ]

    assert respostas == [401] * 5 + [429]


def test_o_codigo_de_recuperacao_entra_pela_mesma_tela(
    app_que_exige: FastAPI, cenario: Demonstracao, navegador: Navegador
) -> None:
    _, ligada = _ligar(navegador(), cenario.gestor_a.email)
    recuperacao = CODIGO_DE_RECUPERACAO.findall(ligada.text)[0]
    cliente = navegador()
    _postar_login(cliente, cenario.gestor_a.email)

    resposta = cliente.post("/entrar/codigo", data={"codigo": recuperacao}, follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/")


def test_porteiro_entra_direto(
    app_que_exige: FastAPI, cenario: Demonstracao, navegador: Navegador
) -> None:
    resposta = _postar_login(navegador(), cenario.porteiro_a.email)

    assert resposta.headers["location"] == "/"


def test_sem_sessao_pela_metade_as_telas_do_codigo_levam_ao_login(
    app_que_exige: FastAPI, navegador: Navegador
) -> None:
    cliente = navegador()

    for caminho in ("/entrar/codigo", "/entrar/ligar"):
        resposta = cliente.get(caminho, follow_redirects=False)
        assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


def test_a_sessao_pela_metade_de_ligar_nao_abre_a_tela_do_codigo(
    app_que_exige: FastAPI, cenario: Demonstracao, navegador: Navegador
) -> None:
    cliente = navegador()
    _postar_login(cliente, cenario.gestor_a.email)

    resposta = cliente.get("/entrar/codigo", follow_redirects=False)

    assert resposta.headers["location"] == "/entrar/ligar"


def test_a_administracao_zera_a_verificacao_do_gestor(
    app_que_exige: FastAPI, cenario: Demonstracao, navegador: Navegador
) -> None:
    _ligar(navegador(), cenario.gestor_a.email)
    _, admin_ligada = _ligar(admin := navegador(), cenario.administrador.email)
    assert admin_ligada.status_code == 200

    resposta = admin.post(f"/api/admin/usuarios/{cenario.gestor_a.id}/duas-etapas/zerar")

    assert resposta.status_code == 204
    login = _postar_login(navegador(), cenario.gestor_a.email)
    assert login.headers["location"] == "/entrar/ligar"


def test_o_gestor_nao_zera_a_verificacao_de_ninguem(
    app: FastAPI, cenario: Demonstracao, navegador: Navegador
) -> None:
    gestor = navegador()
    _postar_login(gestor, cenario.gestor_a.email)

    resposta = gestor.post(f"/api/admin/usuarios/{cenario.porteiro_a.id}/duas-etapas/zerar")

    assert resposta.status_code == 403


def test_zerar_usuario_que_nao_existe_responde_404(
    app: FastAPI, cenario: Demonstracao, navegador: Navegador
) -> None:
    admin = navegador()
    _postar_login(admin, cenario.administrador.email)

    resposta = admin.post("/api/admin/usuarios/999999/duas-etapas/zerar")

    assert resposta.status_code == 404

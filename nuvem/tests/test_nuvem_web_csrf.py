"""O código anti-CSRF (SDD 8.2, D-55): todo pedido que muda alguma coisa, de quem tem a sessão
aberta, leva o código tirado da sessão."""

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from nuvem.cadastro.acesso import COOKIE_DA_SESSAO
from nuvem.semente import SENHA_DA_DEMONSTRACAO, Demonstracao
from nuvem.web import csrf
from nuvem.web.rotas import telas

pytestmark = pytest.mark.integracao

PASTA_DAS_TELAS = Path(telas.env.loader.searchpath[0])  # type: ignore[attr-defined]
FICOU_VELHA = "Esta página ficou velha"


def _logado(app: FastAPI, email: str) -> TestClient:
    """Entra sem pôr o código sozinho em cada pedido (o ``entrar`` dos outros testes põe)."""
    cliente = TestClient(app)
    resposta = cliente.post(
        "/entrar", data={"email": email, "senha": SENHA_DA_DEMONSTRACAO}, follow_redirects=False
    )
    assert resposta.status_code == 303
    return cliente


def _rotas(app: FastAPI) -> list[APIRoute]:
    """Todas as rotas, também as dos roteadores incluídos (o FastAPI 0.142 os guarda à parte)."""
    rotas = []
    for rota in app.routes:
        if isinstance(rota, APIRoute):
            rotas.append(rota)
        roteador = getattr(rota, "original_router", None)
        if roteador is not None:
            rotas += [incluida for incluida in roteador.routes if isinstance(incluida, APIRoute)]
    return rotas


def _codigo(app: FastAPI, cliente: TestClient) -> str:
    return csrf.codigo(app.state.segredo_csrf, cliente.cookies[COOKIE_DA_SESSAO])


def test_pedido_sem_o_codigo_e_recusado(app: FastAPI, cenario: Demonstracao) -> None:
    cliente = _logado(app, cenario.gestor_a.email)

    resposta = cliente.post("/sair", follow_redirects=False)

    assert resposta.status_code == 403
    assert FICOU_VELHA in resposta.text
    assert cliente.get("/", follow_redirects=False).status_code == 200


def test_codigo_no_formulario_passa(app: FastAPI, cenario: Demonstracao) -> None:
    cliente = _logado(app, cenario.gestor_a.email)

    resposta = cliente.post("/sair", data={"_csrf": _codigo(app, cliente)}, follow_redirects=False)

    assert resposta.status_code == 303


def test_codigo_no_cabecalho_passa(app: FastAPI, cenario: Demonstracao) -> None:
    cliente = _logado(app, cenario.gestor_a.email)

    resposta = cliente.post(
        "/sair", headers={"X-CSRF-Token": _codigo(app, cliente)}, follow_redirects=False
    )

    assert resposta.status_code == 303


def test_codigo_de_outra_sessao_e_recusado(app: FastAPI, cenario: Demonstracao) -> None:
    um = _logado(app, cenario.gestor_a.email)
    outro = _logado(app, cenario.gestor_a.email)

    resposta = outro.post("/sair", data={"_csrf": _codigo(app, um)}, follow_redirects=False)

    assert resposta.status_code == 403


def test_a_api_sem_o_codigo_responde_em_json(app: FastAPI, cenario: Demonstracao) -> None:
    cliente = _logado(app, cenario.gestor_a.email)

    resposta = cliente.post(
        f"/api/agendamentos/planilha?site_id={cenario.site_a.id}",
        files={"arquivo": ("agenda.csv", b"x", "text/csv")},
    )

    assert resposta.status_code == 403
    assert resposta.json() == {"detail": "código anti-CSRF ausente ou errado"}


def test_sem_sessao_nao_pede_codigo(app: FastAPI, cenario: Demonstracao) -> None:
    # Sem o cookie, o pedido não tem poder nenhum: segue para a rota, que pede o login.
    resposta = TestClient(app).post("/demonstracao/papel", data={"papel": "porteiro"})

    assert resposta.url.path == "/entrar"


def test_toda_rota_que_muda_confere_o_codigo(app: FastAPI, cenario: Demonstracao) -> None:
    cliente = _logado(app, cenario.gestor_a.email)
    conferidas = []
    for rota in _rotas(app):
        if csrf.isenta(rota.path):
            continue
        for metodo in rota.methods - {"GET", "HEAD", "OPTIONS"}:
            caminho = re.sub(r"\{[^}]+\}", "1", rota.path)
            resposta = cliente.request(metodo, caminho, follow_redirects=False)
            assert resposta.status_code == 403, f"{metodo} {rota.path}: {resposta.status_code}"
            conferidas.append(rota.path)
    assert len(conferidas) > 20  # se o FastAPI mudar onde guarda as rotas, isto avisa
    assert "/demonstracao/papel" in conferidas
    assert "/api/admin/caixas/{caixa_id}/revogar" in conferidas


def test_so_ficam_de_fora_as_rotas_em_que_o_cookie_nao_decide() -> None:
    assert csrf.ISENTAS == ("/entrar", "/agendar/", "/demonstracao/link/", "/api/borda/")


def test_todo_formulario_do_painel_leva_o_codigo() -> None:
    sem_codigo = []
    for arquivo in sorted(PASTA_DAS_TELAS.glob("*.html")):
        texto = arquivo.read_text(encoding="utf-8")
        for formulario in re.finditer(r"<form\b[^>]*>.*?</form>", texto, re.DOTALL):
            abertura = formulario.group(0).split(">", 1)[0]
            if 'method="post"' not in abertura:
                continue
            acao = re.search(r'action="([^"]*)"', abertura)
            if acao and csrf.isenta(acao.group(1)):
                continue
            if 'name="_csrf"' not in formulario.group(0):
                sem_codigo.append(f"{arquivo.name}: {abertura}")
    assert not sem_codigo, "\n".join(sem_codigo)


def test_a_tela_leva_o_codigo_da_sessao_no_formulario_e_no_htmx(
    app: FastAPI, cenario: Demonstracao
) -> None:
    cliente = _logado(app, cenario.gestor_a.email)
    codigo = _codigo(app, cliente)

    texto = cliente.get("/").text

    assert f'name="_csrf" value="{codigo}"' in texto
    assert f'hx-headers=\'{{"X-CSRF-Token": "{codigo}"}}\'' in texto


def test_tela_de_quem_nao_entrou_nao_tem_codigo(app: FastAPI) -> None:
    texto = TestClient(app).get("/entrar").text

    assert "_csrf" not in texto
    assert "X-CSRF-Token" not in texto


def test_rota_isenta_nao_pede_codigo_nem_com_a_sessao(app: FastAPI, cenario: Demonstracao) -> None:
    cliente = _logado(app, cenario.gestor_a.email)

    login = cliente.post(
        "/entrar",
        data={"email": cenario.porteiro_a.email, "senha": SENHA_DA_DEMONSTRACAO},
        follow_redirects=False,
    )
    link = cliente.post("/agendar/inventado", data={})

    assert (login.status_code, link.status_code) == (303, 404)

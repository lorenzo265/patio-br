"""O webhook do WhatsApp e o QR da portaria (SDD 7.5, D-58 e D-63)."""

import hashlib
import hmac
import json
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem import tarefas_de_fundo as fila
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

SEGREDO_DO_APP = "segredo-do-app-inventado"
CODIGO_DO_WEBHOOK = "codigo-de-verificacao-inventado"
NUMERO = "5511900000000"
CORPO = json.dumps(
    {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {"statuses": []}}]}],
    }
).encode()


def _assinar(corpo: bytes) -> str:
    return "sha256=" + hmac.new(SEGREDO_DO_APP.encode(), corpo, hashlib.sha256).hexdigest()


@pytest.fixture
def app_com_whatsapp(app: FastAPI) -> FastAPI:
    """A aplicação com o WhatsApp configurado (só o que a API usa: o webhook e o número)."""
    app.state.whatsapp_numero = NUMERO
    app.state.whatsapp_segredo_do_app = SEGREDO_DO_APP
    app.state.whatsapp_codigo_do_webhook = CODIGO_DO_WEBHOOK
    return app


def _verificar(cliente: TestClient, codigo: str) -> object:
    return cliente.get(
        "/api/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": codigo, "hub.challenge": "4242"},
    )


def test_a_meta_confere_o_webhook_com_o_codigo_certo(app_com_whatsapp: FastAPI) -> None:
    resposta = _verificar(TestClient(app_com_whatsapp), CODIGO_DO_WEBHOOK)

    assert (resposta.status_code, resposta.text) == (200, "4242")  # type: ignore[attr-defined]
    assert resposta.headers["content-type"].startswith("text/plain")  # type: ignore[attr-defined]


def test_codigo_errado_nao_confere_o_webhook(app_com_whatsapp: FastAPI) -> None:
    resposta = _verificar(TestClient(app_com_whatsapp), "outro")

    assert resposta.status_code == 403  # type: ignore[attr-defined]


def test_aviso_assinado_vira_uma_tarefa_so_mesmo_repetido(
    app_com_whatsapp: FastAPI, sessao: Session
) -> None:
    cliente = TestClient(app_com_whatsapp)
    cabecalhos = {"X-Hub-Signature-256": _assinar(CORPO), "Content-Type": "application/json"}

    respostas = [
        cliente.post("/api/whatsapp", content=CORPO, headers=cabecalhos).status_code
        for _ in range(2)
    ]

    assert respostas == [200, 200]
    tarefas = sessao.scalars(
        select(fila.TarefaDeFundo).where(fila.TarefaDeFundo.tipo == "aviso_do_whatsapp")
    ).all()
    assert len(tarefas) == 1
    assert tarefas[0].dados == {"aviso": json.loads(CORPO)}


@pytest.mark.parametrize("assinatura", [None, "sha256=errada"])
def test_aviso_sem_a_assinatura_certa_e_recusado(
    app_com_whatsapp: FastAPI, sessao: Session, assinatura: str | None
) -> None:
    cabecalhos = {"Content-Type": "application/json"}
    if assinatura:
        cabecalhos["X-Hub-Signature-256"] = assinatura

    resposta = TestClient(app_com_whatsapp).post("/api/whatsapp", content=CORPO, headers=cabecalhos)

    assert resposta.status_code == 403
    assert sessao.scalars(select(fila.TarefaDeFundo)).all() == []


@pytest.mark.parametrize("corpo", [b"isto nao e json", b"[1, 2]", b'"texto"'])
def test_aviso_assinado_que_nao_e_um_objeto_json_e_recusado(
    app_com_whatsapp: FastAPI, sessao: Session, corpo: bytes
) -> None:
    resposta = TestClient(app_com_whatsapp).post(
        "/api/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)}
    )

    assert resposta.status_code == 400
    assert sessao.scalars(select(fila.TarefaDeFundo)).all() == []


def test_sem_whatsapp_configurado_o_webhook_nao_existe(app: FastAPI) -> None:
    cliente = TestClient(app)

    assert _verificar(cliente, CODIGO_DO_WEBHOOK).status_code == 404  # type: ignore[attr-defined]
    resposta = cliente.post(
        "/api/whatsapp", content=CORPO, headers={"X-Hub-Signature-256": _assinar(CORPO)}
    )
    assert resposta.status_code == 404


# --- O QR da portaria ----------------------------------------------------------------------


def test_o_gestor_imprime_o_qr_da_portaria(
    app_com_whatsapp: FastAPI, cenario: Demonstracao, entrar: Callable[..., TestClient]
) -> None:
    cliente = entrar(cenario.gestor_a.email)

    resposta = cliente.get(f"/mensagens/qr?site={cenario.site_a.id}")

    assert resposta.status_code == 200
    assert "<svg" in resposta.text
    assert f"AVISOS S{cenario.site_a.id}" in resposta.text
    assert cenario.site_a.nome in resposta.text


def test_o_qr_de_site_de_outra_empresa_responde_nao_encontrado(
    app_com_whatsapp: FastAPI, cenario: Demonstracao, entrar: Callable[..., TestClient]
) -> None:
    cliente = entrar(cenario.gestor_a.email)

    resposta = cliente.get(f"/mensagens/qr?site={cenario.site_b.id}")

    assert resposta.status_code == 404


def test_so_o_gestor_imprime_o_qr(
    app_com_whatsapp: FastAPI, cenario: Demonstracao, entrar: Callable[..., TestClient]
) -> None:
    cliente = entrar(cenario.porteiro_a.email)

    resposta = cliente.get(f"/mensagens/qr?site={cenario.site_a.id}")

    assert resposta.status_code == 403


def test_sem_whatsapp_o_qr_diz_que_nao_esta_configurado(
    app: FastAPI, cenario: Demonstracao, entrar: Callable[..., TestClient]
) -> None:
    cliente = entrar(cenario.gestor_a.email)

    resposta = cliente.get(f"/mensagens/qr?site={cenario.site_a.id}")

    assert resposta.status_code == 200
    assert "<svg" not in resposta.text
    assert "não está configurado" in resposta.text

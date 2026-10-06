"""O retorno do SMS (SDD 7.5, D-64): ``/api/sms/<segredo>``, e o segredo fora do registro."""

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem import tarefas_de_fundo as fila
from nuvem.web.agendar import EsconderCodigoDoLink

pytestmark = pytest.mark.integracao

SEGREDO = "segredo-do-retorno-inventado-0123456789"
CORPO = json.dumps(
    {"type": "MESSAGE_STATUS", "messageId": "z1", "messageStatus": {"code": "DELIVERED"}}
).encode()


@pytest.fixture
def app_com_sms(app: FastAPI) -> FastAPI:
    app.state.sms_segredo_do_webhook = SEGREDO
    return app


def _tarefas(sessao: Session) -> list[fila.TarefaDeFundo]:
    return list(sessao.scalars(select(fila.TarefaDeFundo)))


def test_o_retorno_com_o_segredo_vira_uma_tarefa_so(app_com_sms: FastAPI, sessao: Session) -> None:
    cliente = TestClient(app_com_sms)

    respostas = [cliente.post(f"/api/sms/{SEGREDO}", content=CORPO).status_code for _ in range(2)]

    assert respostas == [200, 200]
    (tarefa,) = _tarefas(sessao)
    assert (tarefa.tipo, tarefa.dados) == ("aviso_do_sms", {"aviso": json.loads(CORPO)})


def test_o_segredo_errado_responde_como_se_a_rota_nao_existisse(
    app_com_sms: FastAPI, sessao: Session
) -> None:
    resposta = TestClient(app_com_sms).post("/api/sms/outro-segredo", content=CORPO)

    assert resposta.status_code == 404
    assert _tarefas(sessao) == []


@pytest.mark.parametrize("corpo", [b"isto nao e json", b"[1]"])
def test_retorno_que_nao_e_um_objeto_json_e_recusado(
    app_com_sms: FastAPI, sessao: Session, corpo: bytes
) -> None:
    resposta = TestClient(app_com_sms).post(f"/api/sms/{SEGREDO}", content=corpo)

    assert resposta.status_code == 400
    assert _tarefas(sessao) == []


def test_sem_sms_configurado_o_retorno_nao_existe(app: FastAPI) -> None:
    resposta = TestClient(app).post(f"/api/sms/{SEGREDO}", content=CORPO)

    assert resposta.status_code == 404


def test_o_segredo_some_do_registro_de_acesso() -> None:
    registro = logging.LogRecord(
        "uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
        ("10.0.0.1:5000", "POST", f"/api/sms/{SEGREDO}", "1.1", 200), None,
    )  # fmt: skip

    assert EsconderCodigoDoLink().filter(registro)
    assert registro.getMessage() == '10.0.0.1:5000 - "POST /api/sms/*** HTTP/1.1" 200'

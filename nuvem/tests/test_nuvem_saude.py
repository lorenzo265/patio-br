"""GET /saude: a API está no ar e alcança o banco."""

import logging

import pytest
from fastapi.testclient import TestClient

from nuvem.config import Configuracao
from nuvem.principal import criar_app

# Porta 1 da própria máquina: nada escuta ali, a conexão é recusada na hora.
URL_SEM_BANCO = "postgresql+pg8000://patio:x@127.0.0.1:1/patio"


@pytest.mark.integracao
def test_saude_responde_ok_com_o_banco_no_ar(url_banco_teste: str) -> None:
    app = criar_app(Configuracao(url_banco=url_banco_teste, _env_file=None))

    with TestClient(app) as cliente:
        resposta = cliente.get("/saude")

    assert (resposta.status_code, resposta.json()) == (200, {"ok": True})


@pytest.mark.integracao
def test_saude_responde_503_com_o_banco_fora_do_ar() -> None:
    app = criar_app(Configuracao(url_banco=URL_SEM_BANCO, _env_file=None))

    with TestClient(app) as cliente:
        resposta = cliente.get("/saude")

    assert (resposta.status_code, resposta.json()) == (503, {"ok": False})


@pytest.mark.integracao
def test_saude_registra_o_erro_quando_o_banco_falha(caplog: pytest.LogCaptureFixture) -> None:
    # Erro nunca é ignorado (SDD 8.1): a resposta diz "fora", o registro diz por quê.
    app = criar_app(Configuracao(url_banco=URL_SEM_BANCO, _env_file=None))

    with caplog.at_level(logging.ERROR, logger="nuvem"), TestClient(app) as cliente:
        cliente.get("/saude")

    assert any(registro.exc_info for registro in caplog.records)

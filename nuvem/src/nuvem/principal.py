"""A aplicação da nuvem (SDD 3.3).

Para rodar: ``uvicorn nuvem.principal:criar_app --factory``. Cada módulo do produto registra
aqui as suas rotas.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from nuvem.banco import criar_motor, obter_sessao
from nuvem.cadastro.rotas import roteador as rotas_do_cadastro
from nuvem.config import Configuracao, ler_configuracao
from nuvem.erros import NaoEncontradoError

_registro = logging.getLogger(__name__)


def criar_app(configuracao: Configuracao | None = None) -> FastAPI:
    """Monta a aplicação.

    Args:
        configuracao: os valores do ambiente; sem ela, lê do ambiente e do ``.env``.

    Raises:
        nuvem.config.ConfiguracaoInvalidaError: se faltar um valor obrigatório no ambiente.
    """
    configuracao = configuracao or ler_configuracao()
    motor = criar_motor(configuracao.url_banco.get_secret_value())

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
        yield
        motor.dispose()

    app = FastAPI(title="patio-br", lifespan=ciclo_de_vida)
    app.state.sessoes = sessionmaker(motor)
    app.add_api_route("/saude", saude, methods=["GET"])
    app.add_exception_handler(NaoEncontradoError, _nao_encontrado)
    app.include_router(rotas_do_cadastro)
    return app


def _nao_encontrado(_requisicao: Request, _erro: Exception) -> JSONResponse:
    # A mesma resposta para "não existe" e "é de outra empresa": não revela dado alheio.
    return JSONResponse({"detail": "não encontrado"}, status_code=status.HTTP_404_NOT_FOUND)


def saude(sessao: Annotated[Session, Depends(obter_sessao)]) -> JSONResponse:
    """Responde se a API está no ar e alcança o banco (503 quando não alcança)."""
    try:
        sessao.execute(text("select 1"))
    except SQLAlchemyError:
        _registro.exception("saúde: o banco não respondeu")
        return JSONResponse({"ok": False}, status_code=503)
    return JSONResponse({"ok": True})

"""A aplicação da nuvem (SDD 3.3).

Para rodar: ``uvicorn nuvem.principal:criar_app --factory``. Cada módulo do produto registra
aqui as suas rotas.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from nuvem.banco import criar_motor, obter_sessao
from nuvem.cadastro.rotas import roteador as rotas_do_cadastro
from nuvem.cadastro.rotas import roteador_admin as rotas_da_administracao
from nuvem.cifra import Cifra
from nuvem.config import Configuracao, ler_configuracao
from nuvem.erros import (
    CaixaNaoIdentificadaError,
    NaoEncontradoError,
    NaoIdentificadoError,
    SemPermissaoError,
)
from nuvem.frota import rotas as frota
from nuvem.senhas import Senhas
from nuvem.web import rotas as web

_registro = logging.getLogger(__name__)


def criar_app(configuracao: Configuracao | None = None, senhas: Senhas | None = None) -> FastAPI:
    """Monta a aplicação.

    Args:
        configuracao: os valores do ambiente; sem ela, lê do ambiente e do ``.env``.
        senhas: o resumidor de senhas; sem ele, o argon2 com o custo padrão.

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
    app.state.senhas = senhas or Senhas()
    app.state.cifra = Cifra(configuracao.chave_cifra)
    app.state.cookie_seguro = configuracao.cookie_seguro
    app.add_api_route("/saude", saude, methods=["GET"])
    app.add_exception_handler(NaoEncontradoError, _nao_encontrado)
    app.add_exception_handler(NaoIdentificadoError, _nao_identificado)
    app.add_exception_handler(SemPermissaoError, _sem_permissao)
    app.add_exception_handler(CaixaNaoIdentificadaError, _caixa_nao_identificada)
    app.include_router(rotas_do_cadastro)
    app.include_router(rotas_da_administracao)
    app.include_router(frota.roteador_borda)
    app.include_router(frota.roteador_admin)
    app.include_router(web.roteador)
    return app


def _e_da_api(requisicao: Request) -> bool:
    # A API responde em JSON; as telas, em HTML.
    return requisicao.url.path.startswith("/api/")


def _nao_encontrado(requisicao: Request, _erro: Exception) -> Response:
    # A mesma resposta para "não existe" e "é de outra empresa": não revela dado alheio.
    if _e_da_api(requisicao):
        return JSONResponse({"detail": "não encontrado"}, status_code=status.HTTP_404_NOT_FOUND)
    contexto = {"mensagem": "Não encontrado."}
    return web.tela(requisicao, "aviso.html", contexto, status.HTTP_404_NOT_FOUND)


def _nao_identificado(requisicao: Request, _erro: Exception) -> Response:
    if _e_da_api(requisicao):
        return JSONResponse(
            {"detail": "entre no sistema"}, status_code=status.HTTP_401_UNAUTHORIZED
        )
    return RedirectResponse("/entrar", status_code=status.HTTP_303_SEE_OTHER)


def _caixa_nao_identificada(_requisicao: Request, _erro: Exception) -> Response:
    return JSONResponse(
        {"detail": "chave da caixa ausente, inválida ou revogada"},
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _sem_permissao(requisicao: Request, _erro: Exception) -> Response:
    if _e_da_api(requisicao):
        return JSONResponse({"detail": "sem permissão"}, status_code=status.HTTP_403_FORBIDDEN)
    contexto = {"mensagem": "Seu papel não permite esta tela."}
    return web.tela(requisicao, "aviso.html", contexto, status.HTTP_403_FORBIDDEN)


def saude(sessao: Annotated[Session, Depends(obter_sessao)]) -> JSONResponse:
    """Responde se a API está no ar e alcança o banco (503 quando não alcança)."""
    try:
        sessao.execute(text("select 1"))
    except SQLAlchemyError:
        _registro.exception("saúde: o banco não respondeu")
        return JSONResponse({"ok": False}, status_code=503)
    return JSONResponse({"ok": True})

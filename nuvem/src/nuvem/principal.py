"""A aplicação da nuvem (SDD 3.3).

Para rodar: ``uvicorn nuvem.principal:criar_app --factory``. Cada módulo do produto registra
aqui as suas rotas.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from nuvem.agendamento import rotas as agendamento
from nuvem.armazenamento import ArmazenamentoLocal
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
from nuvem.portaria import rotas as portaria
from nuvem.senhas import Senhas
from nuvem.web import agendamentos as tela_de_agendamentos
from nuvem.web import agendar as tela_do_link
from nuvem.web import demonstracao as tela_da_demonstracao
from nuvem.web import em_breve as telas_em_breve
from nuvem.web import extrato as tela_do_extrato
from nuvem.web import mensagens as tela_das_mensagens
from nuvem.web import patio as tela_do_patio
from nuvem.web import portaria as tela_da_portaria
from nuvem.web import resolucao as tela_de_resolucao
from nuvem.web import rotas as web

_registro = logging.getLogger(__name__)

PASTA_ESTATICA = Path(web.__file__).parent / "estatico"
"""Arquivos de terceiros servidos como estão (o HTMX e o three.js), em ``/estatico``."""


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
    app.state.armazenamento = ArmazenamentoLocal(configuracao.pasta_fotos, app.state.cifra)
    app.state.cookie_seguro = configuracao.cookie_seguro
    app.state.tem_demonstracao = configuracao.tem_demonstracao
    app.state.url_publica = str(configuracao.url_publica) if configuracao.url_publica else None
    app.add_api_route("/saude", saude, methods=["GET"])
    app.add_exception_handler(NaoEncontradoError, _nao_encontrado)
    app.add_exception_handler(NaoIdentificadoError, _nao_identificado)
    app.add_exception_handler(SemPermissaoError, _sem_permissao)
    app.add_exception_handler(CaixaNaoIdentificadaError, _caixa_nao_identificada)
    app.include_router(rotas_do_cadastro)
    app.include_router(rotas_da_administracao)
    app.include_router(frota.roteador_borda)
    app.include_router(frota.roteador_admin)
    app.include_router(portaria.roteador_borda)
    app.include_router(agendamento.roteador)
    app.include_router(web.roteador)
    app.include_router(tela_da_portaria.roteador)
    app.include_router(tela_de_resolucao.roteador)
    app.include_router(tela_do_patio.roteador)
    app.include_router(tela_das_mensagens.roteador)
    app.include_router(tela_do_extrato.roteador)
    app.include_router(telas_em_breve.roteador)
    app.include_router(tela_da_demonstracao.roteador)
    app.include_router(tela_da_demonstracao.roteador_da_administracao)
    app.include_router(tela_do_link.roteador)
    app.include_router(tela_de_agendamentos.roteador)
    tela_do_link.esconder_codigo_no_registro_de_acesso()
    app.mount("/estatico", StaticFiles(directory=PASTA_ESTATICA), name="estatico")
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
    if requisicao.headers.get("HX-Request"):
        # Pedido do HTMX (ex.: a lista que se atualiza sozinha): ele mesmo leva à tela.
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED, headers={"HX-Redirect": "/entrar"}
        )
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

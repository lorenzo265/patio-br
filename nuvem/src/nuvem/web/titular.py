"""O pedido do titular na administração (SDD 6.2 e 8.3, D-70).

- ``GET /administracao/titular``: o formulário (a empresa, e a placa ou o celular).
- ``POST /administracao/titular``: o levantamento na tela; com ``formato=json``, o arquivo.

A placa e o celular vão no corpo do pedido, e não no endereço: o endereço fica no registro de
acesso. A resposta não fica guardada no navegador.
"""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import AcessoAdmin, obter_acesso_admin
from nuvem.erros import DadoInvalidoError
from nuvem.guarda import titular
from nuvem.prova.cadeia import json_canonico
from nuvem.relogio import agora
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/administracao/titular", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaAdministracao = Annotated[AcessoAdmin, Depends(obter_acesso_admin)]
Agora = Annotated[datetime, Depends(agora)]

SEM_CACHE = {"Cache-Control": "no-store"}


@roteador.get("")
def formulario(
    request: Request, sessao: SessaoDaRequisicao, _administracao: AcessoDaAdministracao
) -> HTMLResponse:
    """O formulário do pedido do titular."""
    return _tela(request, sessao, {})


@roteador.post("", response_model=None)
def levantar(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    empresa: Annotated[int, Form()],
    placa: Annotated[str, Form(max_length=20)] = "",
    celular: Annotated[str, Form(max_length=30)] = "",
    formato: Annotated[Literal["tela", "json"], Form()] = "tela",
) -> Response:
    """Tudo o que existe da placa ou do celular na empresa, na tela ou em arquivo."""
    try:
        achado = titular.levantar(
            sessao, administracao, empresa_id=empresa, placa=placa, celular=celular
        )
    except DadoInvalidoError as erro:
        contexto = {"empresa": empresa, "placa": placa, "celular": celular, "erro": str(erro)}
        resposta = _tela(request, sessao, contexto, codigo=status.HTTP_400_BAD_REQUEST)
        resposta.headers.update(SEM_CACHE)
        return resposta
    if formato == "json":
        # O nome do arquivo não leva a placa nem o celular.
        nome = f"titular-empresa-{empresa}-{momento:%Y-%m-%d}.json"
        return Response(
            json_canonico(achado.como_dicionario()).encode(),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{nome}"', **SEM_CACHE},
        )
    contexto = {"empresa": empresa, "placa": placa, "celular": celular, "achado": achado}
    resposta = _tela(request, sessao, contexto)
    resposta.headers.update(SEM_CACHE)
    return resposta


def _tela(
    request: Request,
    sessao: Session,
    contexto: dict[str, object],
    codigo: int = status.HTTP_200_OK,
) -> HTMLResponse:
    empresas = cadastro.listar_empresas(sessao)
    return tela(request, "administracao_titular.html", {"empresas": empresas, **contexto}, codigo)

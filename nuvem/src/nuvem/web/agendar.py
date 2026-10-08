"""Telas do link da transportadora (SDD 6.2, 8.2 e D-34): agendar pelo celular, sem conta.

- ``GET /agendar/<código>``: o formulário.
- ``POST /agendar/<código>``: cria o agendamento e leva à confirmação (assim, recarregar a página
  não agenda de novo); com erro, volta o formulário com os motivos e o que já estava preenchido.
- ``GET /agendar/<código>/feito/<número>``: a confirmação.

Link vencido, revogado ou inventado: 404, sem dizer qual. No limite: 429. As páginas não vão para
o cache, não mandam o endereço a outros sites e pedem para não ser indexadas. O registro de
acesso troca o código por ``***`` (``EsconderCodigoDoLink``).
"""

import logging
import re
from dataclasses import asdict, fields
from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from nuvem.agendamento import link as links
from nuvem.agendamento.link import FormularioDoLink, LinkEsgotadoError
from nuvem.agendamento.modelos import Agendamento
from nuvem.banco import obter_sessao
from nuvem.cadastro.servico import HorarioDoSite
from nuvem.erros import NaoEncontradoError
from nuvem.relogio import agora
from nuvem.web.rotas import tela

roteador = APIRouter(include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
Agora = Annotated[datetime, Depends(agora)]

CABECALHOS = {
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex",
}
"""O endereço tem o código: ele não vai para outro site, para o cache nem para buscadores."""

FORA = "Este link não vale mais. Peça um novo ao site."
ESGOTADO = "Este link chegou ao limite de agendamentos. Peça um novo ao site."

_CAMPOS = tuple(campo.name for campo in fields(FormularioDoLink))
TAMANHO_DO_CAMPO = 200
"""O que passar disto em um campo é cortado (nenhum campo de verdade chega perto)."""


@roteador.get("/agendar/{codigo}")
def formulario(
    request: Request, sessao: SessaoDaRequisicao, momento: Agora, codigo: str
) -> Response:
    """O formulário do link, vazio."""
    try:
        aberto = links.abrir_link(sessao, codigo, agora=momento)
    except NaoEncontradoError:
        return _aviso(request, FORA, status.HTTP_404_NOT_FOUND)
    except LinkEsgotadoError:
        return _aviso(request, ESGOTADO, status.HTTP_429_TOO_MANY_REQUESTS)
    return _formulario(request, codigo, aberto, FormularioDoLink(), [], status.HTTP_200_OK)


@roteador.post("/agendar/{codigo}")
async def agendar(
    request: Request, sessao: SessaoDaRequisicao, momento: Agora, codigo: str
) -> Response:
    """Cria o agendamento e leva à confirmação; com erro, volta o formulário com os motivos."""
    recebido = await request.form()
    preenchido = FormularioDoLink(
        **{campo: str(recebido.get(campo) or "")[:TAMANHO_DO_CAMPO] for campo in _CAMPOS}
    )
    # O banco é síncrono: fora da linha do servidor, como nas rotas comuns.
    return await run_in_threadpool(_agendar, request, sessao, momento, codigo, preenchido)


def _agendar(
    request: Request,
    sessao: Session,
    momento: datetime,
    codigo: str,
    preenchido: FormularioDoLink,
) -> Response:
    try:
        aberto = links.abrir_link(sessao, codigo, agora=momento)
        resultado = links.agendar_pelo_link(sessao, codigo, preenchido, agora=momento)
    except NaoEncontradoError:
        return _aviso(request, FORA, status.HTTP_404_NOT_FOUND)
    except LinkEsgotadoError:
        return _aviso(request, ESGOTADO, status.HTTP_429_TOO_MANY_REQUESTS)
    if isinstance(resultado, list):
        return _formulario(
            request, codigo, aberto, preenchido, resultado, status.HTTP_422_UNPROCESSABLE_CONTENT
        )
    sessao.commit()
    destino = f"/agendar/{codigo}/feito/{resultado.codigo_externo}"
    return RedirectResponse(destino, status_code=status.HTTP_303_SEE_OTHER, headers=CABECALHOS)


@roteador.get("/agendar/{codigo}/feito/{numero}")
def feito(
    request: Request, sessao: SessaoDaRequisicao, momento: Agora, codigo: str, numero: str
) -> Response:
    """A confirmação de um agendamento feito por este link."""
    try:
        agendamento = links.agendamento_do_link(sessao, codigo, numero, agora=momento)
        site = links.horario_do_link(sessao, codigo, agora=momento)
    except NaoEncontradoError:
        return _aviso(request, FORA, status.HTTP_404_NOT_FOUND)
    contexto = {"agendamento": agendamento, "site": site} | _janela(agendamento, site)
    return _com_cabecalhos(tela(request, "agendar_feito.html", contexto))


def _formulario(
    request: Request,
    codigo: str,
    aberto: links.LinkAberto,
    preenchido: FormularioDoLink,
    erros: list[str],
    codigo_http: int,
) -> HTMLResponse:
    contexto: dict[str, Any] = {
        "codigo": codigo,
        "aberto": aberto,
        "valores": asdict(preenchido),
        "erros": erros,
    }
    return _com_cabecalhos(tela(request, "agendar.html", contexto, codigo_http))


def _aviso(request: Request, mensagem: str, codigo_http: int) -> HTMLResponse:
    return _com_cabecalhos(tela(request, "agendar_aviso.html", {"mensagem": mensagem}, codigo_http))


def _com_cabecalhos(resposta: HTMLResponse) -> HTMLResponse:
    resposta.headers.update(CABECALHOS)
    return resposta


def _janela(agendamento: Agendamento, site: HorarioDoSite) -> dict[str, str]:
    fuso = ZoneInfo(site.fuso)
    inicio = agendamento.janela_inicio.astimezone(fuso)
    fim = agendamento.janela_fim.astimezone(fuso)
    return {"dia": f"{inicio:%d/%m/%Y}", "de": f"{inicio:%H:%M}", "ate": f"{fim:%H:%M}"}


# --- O registro de acesso não guarda o código (D-34) ------------------------------------------

_CODIGO_NO_CAMINHO = re.compile(r"^/(agendar|senha|demonstracao/link|api/sms)/[^/?#]+")
"""O link da transportadora, o de senha (D-75), o de demonstração (D-54) e o retorno do SMS
(D-64) levam o código no endereço."""


class EsconderCodigoDoLink(logging.Filter):
    """Troca o código do link por ``***`` no registro de acesso do uvicorn."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Reescreve o caminho (o 3º argumento do registro de acesso) e deixa passar."""
        argumentos = record.args
        if isinstance(argumentos, tuple) and len(argumentos) >= 3:
            caminho = argumentos[2]
            if isinstance(caminho, str):
                escondido = _CODIGO_NO_CAMINHO.sub(r"/\1/***", caminho)
                record.args = (*argumentos[:2], escondido, *argumentos[3:])
        return True


def esconder_codigo_no_registro_de_acesso() -> None:
    """Liga o filtro no registro de acesso do uvicorn (uma vez só, mesmo se chamada de novo)."""
    registro = logging.getLogger("uvicorn.access")
    if not any(isinstance(filtro, EsconderCodigoDoLink) for filtro in registro.filters):
        registro.addFilter(EsconderCodigoDoLink())

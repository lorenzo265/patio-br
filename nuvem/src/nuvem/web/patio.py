"""A tela do pátio e das docas (T42, SDD 6.2): o líder vê a fila e as docas e move os caminhões.

A página traz o HTMX, que busca o quadro (``/patio/quadro``) ao abrir e a cada 3 segundos. Chamar
para a doca tem página própria (as docas livres como botões), e começar, terminar e cancelar a
chamada são botões no próprio quadro.
"""

from datetime import datetime, timedelta
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, exigir_papel
from nuvem.patio import servico as patio
from nuvem.patio.servico import CaminhaoNoPatio, DocaOcupadaError
from nuvem.portaria import visitas
from nuvem.portaria.visitas import TransicaoInvalidaError
from nuvem.relogio import agora
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/patio", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDoPatio = Annotated[Acesso, Depends(exigir_papel("patio", "gestor"))]
Agora = Annotated[datetime, Depends(agora)]

ESTADO_NA_TELA = {"NA_FILA": "na fila", "CHAMADA": "chamado", "NA_DOCA": "na doca",
                  "LIBERADA": "liberado"}  # fmt: skip
MUDOU = "O caminhão mudou de situação enquanto você olhava; veja o quadro de novo."


@roteador.get("")
def tela_do_patio(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoPatio, site: int | None = None
) -> HTMLResponse:
    """O pátio de um site do usuário (o primeiro, se nenhum for pedido)."""
    sites = cadastro.listar_sites(sessao, acesso)
    if not sites:
        return tela(request, "aviso.html", {"mensagem": "Você não está ligado a nenhum site."})
    escolhido = cadastro.obter_site(sessao, acesso, site) if site is not None else sites[0]
    outros = [outro for outro in sites if outro.id != escolhido.id]
    return tela(request, "patio.html", {"site": escolhido, "outros_sites": outros})


@roteador.get("/quadro")
def quadro(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoPatio, momento: Agora, site: int
) -> HTMLResponse:
    """A fila, as docas e os liberados (o pedaço da tela que o HTMX troca)."""
    atual = patio.quadro(sessao, acesso, site, agora=momento)
    fuso = ZoneInfo(cadastro.obter_site(sessao, acesso, site).fuso)
    contexto = {
        "fila": [_caminhao(c, fuso) for c in atual.fila],
        "docas": [
            {"nome": d.nome, "caminhao": _caminhao(d.caminhao, fuso) if d.caminhao else None}
            for d in atual.docas
        ],
        "liberados": [_caminhao(c, fuso) for c in atual.liberados],
    }
    return tela(request, "patio_quadro.html", contexto)


@roteador.get("/visitas/{visita_id}/chamar")
def tela_de_chamar(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoPatio,
    momento: Agora,
    visita_id: int,
) -> HTMLResponse:
    """As docas livres do site, para chamar o caminhão."""
    return _chamar(request, sessao, acesso, momento, visita_id)


@roteador.post("/visitas/{visita_id}/chamar", response_model=None)
def chamar(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoPatio,
    momento: Agora,
    visita_id: int,
    doca_id: Annotated[int, Form()],
) -> HTMLResponse | RedirectResponse:
    """Chama o caminhão para a doca escolhida."""
    try:
        visita = patio.chamar(sessao, acesso, visita_id, doca_id, agora=momento)
    except DocaOcupadaError as erro:
        aviso = f"A {erro.doca} está ocupada. Escolha outra doca."
        return _chamar(request, sessao, acesso, momento, visita_id, aviso, status.HTTP_409_CONFLICT)
    except TransicaoInvalidaError:
        return _mudou(request, sessao)
    return _de_volta_ao_patio(sessao, visita.site_id)


@roteador.post("/visitas/{visita_id}/comecar", response_model=None)
def comecar(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoPatio, momento: Agora,
    visita_id: int,
) -> HTMLResponse | RedirectResponse:  # fmt: skip
    """O caminhão chegou à doca."""
    try:
        visita = patio.iniciar(sessao, acesso, visita_id, agora=momento)
    except TransicaoInvalidaError:
        return _mudou(request, sessao)
    return _de_volta_ao_patio(sessao, visita.site_id)


@roteador.post("/visitas/{visita_id}/terminar", response_model=None)
def terminar(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoPatio, momento: Agora,
    visita_id: int,
) -> HTMLResponse | RedirectResponse:  # fmt: skip
    """Terminou a carga ou a descarga."""
    try:
        visita = patio.finalizar(sessao, acesso, visita_id, agora=momento)
    except TransicaoInvalidaError:
        return _mudou(request, sessao)
    return _de_volta_ao_patio(sessao, visita.site_id)


@roteador.post("/visitas/{visita_id}/cancelar-chamada", response_model=None)
def cancelar_chamada(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoPatio, momento: Agora,
    visita_id: int,
) -> HTMLResponse | RedirectResponse:  # fmt: skip
    """O caminhão chamado não veio: volta para a fila."""
    try:
        visita = patio.cancelar_chamada(sessao, acesso, visita_id, agora=momento)
    except TransicaoInvalidaError:
        return _mudou(request, sessao)
    return _de_volta_ao_patio(sessao, visita.site_id)


def _de_volta_ao_patio(sessao: Session, site_id: int) -> RedirectResponse:
    sessao.commit()
    return RedirectResponse(f"/patio?site={site_id}", status.HTTP_303_SEE_OTHER)


def _mudou(request: Request, sessao: Session) -> HTMLResponse:
    sessao.rollback()
    return tela(request, "aviso.html", {"mensagem": MUDOU}, status.HTTP_409_CONFLICT)


def _chamar(
    request: Request,
    sessao: Session,
    acesso: Acesso,
    momento: datetime,
    visita_id: int,
    aviso: str = "",
    codigo: int = status.HTTP_200_OK,
) -> HTMLResponse:
    sessao.rollback()
    visita = visitas.obter_visita(sessao, acesso, visita_id)
    caminhao = patio.obter_caminhao(sessao, acesso, visita.id, agora=momento)
    fuso = ZoneInfo(cadastro.obter_site(sessao, acesso, visita.site_id).fuso)
    contexto = {
        "caminhao": _caminhao(caminhao, fuso),
        "site_id": visita.site_id,
        "docas": patio.docas_livres(sessao, acesso, visita.site_id),
        "na_fila": visita.estado == "NA_FILA",
        "aviso": aviso,
    }
    return tela(request, "patio_chamar.html", contexto, codigo)


def _caminhao(caminhao: CaminhaoNoPatio, fuso: ZoneInfo) -> dict[str, Any]:
    return {
        "visita_id": caminhao.visita_id,
        "estado": caminhao.estado,
        "situacao": ESTADO_NA_TELA.get(caminhao.estado, caminhao.estado),
        "placas": ", ".join(caminhao.placas),
        "agendamento": caminhao.agendamento or "sem agendamento",
        "tipo": caminhao.tipo or "",
        "chegada": caminhao.chegou_em.astimezone(fuso).strftime("%H:%M"),
        "tempo": _duracao(caminhao.tempo),
        "alerta": _alerta(caminhao),
        "doca": caminhao.doca or "",
    }


def _alerta(caminhao: CaminhaoNoPatio) -> str:
    if not caminhao.alerta:
        return ""
    return "passou das 5 horas" if caminhao.tempo >= patio.ESTADIA_DA_LEI else "perto das 5 horas"


def _duracao(tempo: timedelta) -> str:
    """Ex.: 4h10, 0h35."""
    minutos = max(int(tempo.total_seconds() // 60), 0)
    return f"{minutos // 60}h{minutos % 60:02d}"

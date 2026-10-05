"""O porteiro resolve a exceção e registra a chegada à mão (T41, SDD 5.2 e D-46).

Cada exceção tem página própria (``/portaria/excecoes/<id>``), fora da lista que se atualiza a
cada 2 segundos: a foto, as placas, os agendamentos possíveis pelos pontos e as ações ("é este",
"sem agendamento", "recusar" e corrigir a placa). A chegada manual (``/portaria/chegada-manual``)
pede as placas, sugere os agendamentos e registra com o que o porteiro escolher.
"""

from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from contratos.placa import PlacaInvalidaError
from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, exigir_papel
from nuvem.portaria import conferencia, resolucao
from nuvem.portaria.modelos import Excecao, Visita
from nuvem.portaria.resolucao import (
    AgendamentoIndisponivelError,
    ExcecaoJaResolvidaError,
    Opcao,
)
from nuvem.relogio import agora
from nuvem.web.portaria import FORA_DO_FORMATO, MOTIVO_NA_TELA
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/portaria", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaPortaria = Annotated[Acesso, Depends(exigir_papel("porteiro", "gestor"))]
Agora = Annotated[datetime, Depends(agora)]

JA_RESOLVIDA = "Esta exceção já foi resolvida (por outra pessoa ou porque o caminhão saiu)."
INDISPONIVEL = (
    "Esse agendamento não está disponível: já tem visita, foi cancelado ou está longe da hora."
)


# --- A exceção --------------------------------------------------------------------------------


@roteador.get("/excecoes/{excecao_id}")
def tela_da_excecao(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDaPortaria, excecao_id: int
) -> HTMLResponse:
    """A exceção, com a foto, as placas, os agendamentos possíveis e as ações."""
    return _excecao(request, sessao, acesso, excecao_id)


@roteador.post("/excecoes/{excecao_id}/agendamento", response_model=None)
def e_este(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDaPortaria,
    momento: Agora,
    excecao_id: int,
    agendamento_id: Annotated[int, Form()],
) -> HTMLResponse | RedirectResponse:
    """ "É este": liga a chegada ao agendamento escolhido."""
    try:
        visita = resolucao.ligar_ao_agendamento(
            sessao, acesso, excecao_id, agendamento_id, agora=momento
        )
    except ExcecaoJaResolvidaError:
        return _excecao(request, sessao, acesso, excecao_id, JA_RESOLVIDA, status.HTTP_409_CONFLICT)
    except AgendamentoIndisponivelError:
        return _excecao(request, sessao, acesso, excecao_id, INDISPONIVEL, status.HTTP_409_CONFLICT)
    return _de_volta_a_portaria(sessao, visita)


@roteador.post("/excecoes/{excecao_id}/sem-agendamento", response_model=None)
def sem_agendamento(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDaPortaria,
    momento: Agora,
    excecao_id: int,
) -> HTMLResponse | RedirectResponse:
    """Aceita a chegada sem agendamento."""
    try:
        visita = resolucao.aceitar_sem_agendamento(sessao, acesso, excecao_id, agora=momento)
    except ExcecaoJaResolvidaError:
        return _excecao(request, sessao, acesso, excecao_id, JA_RESOLVIDA, status.HTTP_409_CONFLICT)
    return _de_volta_a_portaria(sessao, visita)


@roteador.post("/excecoes/{excecao_id}/recusar", response_model=None)
def recusar(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDaPortaria,
    momento: Agora,
    excecao_id: int,
) -> HTMLResponse | RedirectResponse:
    """Recusa a entrada."""
    try:
        visita = resolucao.recusar(sessao, acesso, excecao_id, agora=momento)
    except ExcecaoJaResolvidaError:
        return _excecao(request, sessao, acesso, excecao_id, JA_RESOLVIDA, status.HTTP_409_CONFLICT)
    return _de_volta_a_portaria(sessao, visita)


@roteador.post("/excecoes/{excecao_id}/conferir", response_model=None)
def corrigir_na_foto(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDaPortaria,
    momento: Agora,
    excecao_id: int,
    foto: Annotated[int, Form()],
    placa: Annotated[str, Form()],
) -> HTMLResponse | RedirectResponse:
    """Confere a placa de uma foto da exceção; se ela muda, o casamento roda de novo."""
    excecao, _ = resolucao.obter_excecao(sessao, acesso, excecao_id)
    try:
        resolucao.conferir_placa(sessao, acesso, excecao.passagem_id, foto, placa, agora=momento)
    except PlacaInvalidaError:
        erro = f"A placa “{placa.strip()}” {FORA_DO_FORMATO}."
        return _excecao(request, sessao, acesso, excecao_id, erro, _INVALIDA)
    sessao.commit()
    return RedirectResponse(f"/portaria/excecoes/{excecao_id}", status.HTTP_303_SEE_OTHER)


@roteador.post("/excecoes/{excecao_id}/cavalo", response_model=None)
def digitar_cavalo(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDaPortaria,
    momento: Agora,
    excecao_id: int,
    placa: Annotated[str, Form()],
) -> HTMLResponse | RedirectResponse:
    """A placa do cavalo digitada, quando não há foto; o casamento roda de novo."""
    try:
        resolucao.digitar_cavalo(sessao, acesso, excecao_id, placa, agora=momento)
    except PlacaInvalidaError:
        erro = f"A placa “{placa.strip()}” {FORA_DO_FORMATO}."
        return _excecao(request, sessao, acesso, excecao_id, erro, _INVALIDA)
    except ExcecaoJaResolvidaError:
        return _excecao(request, sessao, acesso, excecao_id, JA_RESOLVIDA, status.HTTP_409_CONFLICT)
    sessao.commit()
    return RedirectResponse(f"/portaria/excecoes/{excecao_id}", status.HTTP_303_SEE_OTHER)


_INVALIDA = status.HTTP_422_UNPROCESSABLE_CONTENT


def _de_volta_a_portaria(sessao: Session, visita: Visita) -> RedirectResponse:
    site_id = visita.site_id
    sessao.commit()
    return RedirectResponse(f"/portaria?site={site_id}", status.HTTP_303_SEE_OTHER)


def _excecao(
    request: Request,
    sessao: Session,
    acesso: Acesso,
    excecao_id: int,
    aviso: str = "",
    codigo: int = status.HTTP_200_OK,
) -> HTMLResponse:
    # Depois de um erro, o que a requisição tentou gravar fica de fora.
    sessao.rollback()
    excecao, visita = resolucao.obter_excecao(sessao, acesso, excecao_id)
    fuso = ZoneInfo(cadastro.obter_site(sessao, acesso, visita.site_id).fuso)
    chegada = (visita.chegou_em or visita.criada_em).astimezone(fuso)
    aberta = excecao.situacao == "aberta"
    contexto: dict[str, Any] = {
        "excecao": excecao,
        "site_id": visita.site_id,
        "data": chegada.strftime("%d/%m"),
        "hora": chegada.strftime("%H:%M:%S"),
        "motivo": MOTIVO_NA_TELA[excecao.motivo],
        "placas": visita.composicao,
        "recortes": conferencia.recortes(sessao, acesso, excecao.passagem_id),
        "opcoes": [_opcao(o, fuso) for o in resolucao.opcoes(sessao, acesso, excecao_id)]
        if aberta
        else [],
        "aberta": aberta,
        "resolvida": _resolvida(excecao, fuso),
        "aviso": aviso,
    }
    return tela(request, "portaria_excecao.html", contexto, codigo)


def _resolvida(excecao: Excecao, fuso: ZoneInfo) -> str:
    if excecao.resolvida_em is None:
        return ""
    return f"{excecao.resolvida_em.astimezone(fuso):%H:%M}: {excecao.resolucao}"


def _opcao(opcao: Opcao, fuso: ZoneInfo) -> dict[str, Any]:
    inicio, fim = opcao.janela_inicio.astimezone(fuso), opcao.janela_fim.astimezone(fuso)
    return {
        "id": opcao.agendamento_id,
        "codigo": opcao.codigo,
        "placas": ", ".join([opcao.placa_cavalo, *opcao.placas_reboques]),
        "janela": f"{inicio:%d/%m} {inicio:%H:%M} às {fim:%H:%M}",
        "motorista": opcao.motorista,
        "pontos": opcao.pontos,
    }


# --- A chegada manual -------------------------------------------------------------------------


@roteador.get("/chegada-manual")
def tela_da_chegada_manual(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDaPortaria,
    momento: Agora,
    site: int,
    cavalo: str = "",
    reboques: str = "",
) -> HTMLResponse:
    """As placas; com elas, os agendamentos sugeridos pelos pontos."""
    return _chegada_manual(request, sessao, acesso, momento, site, cavalo, reboques)


@roteador.post("/chegada-manual", response_model=None)
def registrar_chegada_manual(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDaPortaria,
    momento: Agora,
    site: int,
    cavalo: Annotated[str, Form()],
    reboques: Annotated[str, Form()] = "",
    agendamento_id: Annotated[str, Form()] = "",
) -> HTMLResponse | RedirectResponse:
    """Registra a chegada com o agendamento escolhido (ou nenhum)."""
    escolhido = int(agendamento_id) if agendamento_id.strip().isdigit() else None
    try:
        resolucao.registrar_chegada_manual(
            sessao, acesso, site, _placas(cavalo, reboques), escolhido, agora=momento
        )
    except PlacaInvalidaError as erro:
        aviso = f"A placa “{erro.texto}” {FORA_DO_FORMATO}." if erro.texto else _SEM_CAVALO
        return _chegada_manual(
            request, sessao, acesso, momento, site, cavalo, reboques, aviso, _INVALIDA
        )
    except AgendamentoIndisponivelError:
        return _chegada_manual(
            request, sessao, acesso, momento, site, cavalo, reboques, INDISPONIVEL,
            status.HTTP_409_CONFLICT,
        )  # fmt: skip
    sessao.commit()
    return RedirectResponse(f"/portaria?site={site}", status.HTTP_303_SEE_OTHER)


_SEM_CAVALO = "Digite a placa do cavalo."


def _placas(cavalo: str, reboques: str) -> list[str]:
    return [cavalo, *reboques.replace(",", " ").split()]


def _chegada_manual(
    request: Request,
    sessao: Session,
    acesso: Acesso,
    momento: datetime,
    site_id: int,
    cavalo: str,
    reboques: str,
    aviso: str = "",
    codigo: int = status.HTTP_200_OK,
) -> HTMLResponse:
    sessao.rollback()
    site = cadastro.obter_site(sessao, acesso, site_id)
    fuso = ZoneInfo(site.fuso)
    sugestoes: list[dict[str, Any]] = []
    if cavalo.strip() and not aviso:
        try:
            achadas = resolucao.sugestoes(
                sessao, acesso, site.id, _placas(cavalo, reboques), agora=momento
            )
        except PlacaInvalidaError as erro:
            aviso, codigo = f"A placa “{erro.texto}” {FORA_DO_FORMATO}.", _INVALIDA
        else:
            sugestoes = [_opcao(o, fuso) for o in achadas]
    contexto = {
        "site": site,
        "cavalo": cavalo,
        "reboques": reboques,
        "sugestoes": sugestoes,
        "buscou": bool(cavalo.strip()) and not aviso,
        "aviso": aviso,
    }
    return tela(request, "portaria_manual.html", contexto, codigo)

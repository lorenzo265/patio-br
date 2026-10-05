"""O celular do motorista (T43, SDD 6.2 e D-47): as mensagens que ele receberia.

A lista mostra as últimas conversas de um site; cada uma abre numa tela em forma de celular, que
busca a conversa (``/mensagens/agendamentos/{id}/conversa``) ao abrir e a cada 3 segundos. O
canal de demonstração não envia nada; a tela diz isso. O número aparece escondido, só com o DDD
e o fim.
"""

from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from nuvem.agendamento import servico as agendamentos
from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, obter_acesso
from nuvem.mensagens import servico as mensagens
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/mensagens", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDoCliente = Annotated[Acesso, Depends(obter_acesso)]


@roteador.get("")
def conversas(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoCliente, site: int | None = None
) -> HTMLResponse:
    """As últimas conversas de um site do usuário (o primeiro, se nenhum for pedido)."""
    sites = cadastro.listar_sites(sessao, acesso)
    if not sites:
        return tela(request, "aviso.html", {"mensagem": "Você não está ligado a nenhum site."})
    escolhido = cadastro.obter_site(sessao, acesso, site) if site is not None else sites[0]
    lista = mensagens.conversas(sessao, acesso, escolhido.id)
    resumos = agendamentos.resumos(sessao, acesso, [c.agendamento_id for c in lista])
    fuso = ZoneInfo(escolhido.fuso)
    linhas = [
        {
            "agendamento_id": c.agendamento_id,
            "codigo": resumos[c.agendamento_id].codigo,
            "tipo": resumos[c.agendamento_id].tipo,
            "ultima": c.ultima.texto,
            "quando": _quando(c.ultima.criada_em, fuso),
            "quantas": c.quantas,
        }
        for c in lista
    ]
    contexto = {
        "site": escolhido,
        "outros_sites": [outro for outro in sites if outro.id != escolhido.id],
        "conversas": linhas,
    }
    return tela(request, "mensagens.html", contexto)


@roteador.get("/agendamentos/{agendamento_id}")
def celular(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoCliente, agendamento_id: int
) -> HTMLResponse:
    """A tela em forma de celular, com a conversa de um agendamento."""
    agendamento = agendamentos.obter(sessao, acesso, agendamento_id)
    site = cadastro.obter_site(sessao, acesso, agendamento.site_id)
    contexto = {
        "agendamento_id": agendamento.id,
        "codigo": agendamento.codigo_externo,
        "site": site,
        "para": _escondido(agendamento.motorista_celular),
    }
    return tela(request, "mensagens_celular.html", contexto)


@roteador.get("/agendamentos/{agendamento_id}/conversa")
def conversa(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoCliente, agendamento_id: int
) -> HTMLResponse:
    """As mensagens de um agendamento (o pedaço da tela que o HTMX troca), com o dia de cada uma."""
    agendamento = agendamentos.obter(sessao, acesso, agendamento_id)
    lista = mensagens.conversa(sessao, acesso, agendamento.id)
    fuso = ZoneInfo(cadastro.obter_site(sessao, acesso, agendamento.site_id).fuso)
    baloes: list[dict[str, Any]] = []
    for mensagem in lista:
        momento = mensagem.criada_em.astimezone(fuso)
        dia = f"{momento:%d/%m}"
        novo_dia = not baloes or baloes[-1]["dia"] != dia
        baloes.append(
            {"texto": mensagem.texto, "hora": f"{momento:%H:%M}", "dia": dia, "novo_dia": novo_dia}
        )
    return tela(request, "mensagens_conversa.html", {"baloes": baloes})


def _quando(momento: datetime, fuso: ZoneInfo) -> str:
    return f"{momento.astimezone(fuso):%d/%m %H:%M}"


def _escondido(celular: str | None) -> str:
    """Ex.: ``+5511987654321`` vira ``(11) •••••-4321``; vazio sem celular."""
    if not celular:
        return ""
    numero = celular.removeprefix("+55")
    return f"({numero[:2]}) •••••-{numero[-4:]}"

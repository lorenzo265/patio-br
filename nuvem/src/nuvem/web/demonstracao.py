"""A tela do dia de demonstração (T45, D-49): começar o dia e acompanhar.

Só existe nos ambientes ``local`` e ``demonstracao`` (fora deles, 404) e só para o gestor. A tela
se atualiza sozinha (HTMX) e leva às telas onde o dia acontece: portaria, pátio, mensagens e
painel.
"""

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, exigir_papel
from nuvem.demonstracao import dia as demonstracao
from nuvem.demonstracao.dia import DiaJaComecouError, SiteSemCaixaError
from nuvem.relogio import agora
from nuvem.web.rotas import tela


def so_com_demonstracao(request: Request) -> None:
    """Fora dos ambientes da demonstração, as rotas não existem (404)."""
    if not request.app.state.tem_demonstracao:
        raise HTTPException(status.HTTP_404_NOT_FOUND)


roteador = APIRouter(
    prefix="/demonstracao", include_in_schema=False, dependencies=[Depends(so_com_demonstracao)]
)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDoGestor = Annotated[Acesso, Depends(exigir_papel("gestor"))]
Agora = Annotated[datetime, Depends(agora)]


@roteador.get("")
def andamento(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoGestor, site: int | None = None
) -> HTMLResponse:
    """O dia de demonstração de um site do gestor: o botão de começar ou o andamento."""
    sites = cadastro.listar_sites(sessao, acesso)
    if not sites:
        return tela(request, "aviso.html", {"mensagem": "Você não está ligado a nenhum site."})
    escolhido = cadastro.obter_site(sessao, acesso, site) if site is not None else sites[0]
    dia = demonstracao.andamento(sessao, acesso, escolhido.id)
    fuso = ZoneInfo(escolhido.fuso)
    contexto = {
        "site": escolhido,
        "dia": dia,
        "termina": f"{dia.termina_em.astimezone(fuso):%H:%M:%S}" if dia else "",
        "comecou": f"{dia.comecou_em.astimezone(fuso):%d/%m às %H:%M}" if dia else "",
    }
    return tela(request, "demonstracao.html", contexto)


@roteador.post("/comecar", response_model=None)
def comecar(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoGestor,
    momento: Agora,
    site: Annotated[int, Form()],
) -> HTMLResponse | RedirectResponse:
    """Começa o dia de demonstração do site."""
    try:
        demonstracao.comecar(sessao, acesso, site, agora=momento)
    except DiaJaComecouError:
        return _aviso(request, sessao, "O dia de demonstração já está rodando neste site.")
    except SiteSemCaixaError:
        mensagem = "Este site não tem caixa de borda; o dia de demonstração precisa de uma."
        return _aviso(request, sessao, mensagem)
    sessao.commit()
    return RedirectResponse(f"/demonstracao?site={site}", status.HTTP_303_SEE_OTHER)


def _aviso(request: Request, sessao: Session, mensagem: str) -> HTMLResponse:
    sessao.rollback()
    return tela(request, "aviso.html", {"mensagem": mensagem}, status.HTTP_409_CONFLICT)

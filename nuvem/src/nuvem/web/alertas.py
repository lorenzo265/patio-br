"""Os alertas nas telas (SDD 6.2 e 8.1, D-68).

- **O sino** (``/alertas/sino``): o número de alertas abertos dos sites de quem é do cliente. A
  ``base.html`` o põe em todas as telas de quem entrou, e o HTMX o busca ao abrir e a cada minuto.
  A administração tem o dela (``/administracao/alertas/sino``): a caixa, a câmera e as tarefas.
- ``/alertas``: os abertos e os fechados das últimas 24 horas, com a hora no fuso do site.
- ``/alertas/whatsapp``: o gestor pede o código de uso único e recebe o link (e o QR) que abre o
  WhatsApp com "ALERTAS <código>". O código vale 10 minutos e só aparece nesta resposta, que
  não fica guardada no navegador. A administração tem o mesmo, em ``/administracao/alertas``.
"""

from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from markupsafe import Markup
from sqlalchemy.orm import Session

from nuvem.alertas import servico as alertas
from nuvem.alertas.modelos import Alerta
from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import (
    Acesso,
    AcessoAdmin,
    exigir_papel,
    obter_acesso,
    obter_acesso_admin,
)
from nuvem.cadastro.duas_etapas import qr_em_svg
from nuvem.cadastro.modelos import FUSO_PADRAO
from nuvem.mensagens import whatsapp
from nuvem.relogio import agora
from nuvem.web.mensagens import celular_escondido
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/alertas", include_in_schema=False)
roteador_da_administracao = APIRouter(prefix="/administracao/alertas", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDoCliente = Annotated[Acesso, Depends(obter_acesso)]
AcessoDoGestor = Annotated[Acesso, Depends(exigir_papel("gestor"))]
AcessoDaAdministracao = Annotated[AcessoAdmin, Depends(obter_acesso_admin)]
Agora = Annotated[datetime, Depends(agora)]

SEM_CACHE = {"Cache-Control": "no-store"}
"""A resposta com o código não fica guardada no navegador (nem no "voltar")."""
MINUTOS_DO_CODIGO = int(alertas.VALIDADE_DO_CODIGO.total_seconds() // 60)


# --- Quem é do cliente ----------------------------------------------------------------------


@roteador.get("")
def tela_dos_alertas(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoCliente, momento: Agora
) -> HTMLResponse:
    """Os abertos e os das últimas 24 horas, dos sites que o usuário vê."""
    sites = {site.id: site for site in cadastro.listar_sites(sessao, acesso)}
    linhas = []
    for alerta in alertas.recentes(sessao, acesso, agora=momento):
        site = sites[alerta.site_id] if alerta.site_id is not None else None
        linhas.append(_linha(alerta, site.nome if site else "", site.fuso if site else FUSO_PADRAO))
    gestor = acesso.papel == "gestor"
    celular = alertas.celular_autorizado(sessao, acesso) if gestor else None
    contexto = {
        "abertos": [linha for linha in linhas if linha["aberto"]],
        "fechados": [linha for linha in linhas if not linha["aberto"]],
        "varios_sites": len(sites) > 1,
        "pede_o_whatsapp": "/alertas/whatsapp" if gestor else None,
        "celular": celular_escondido(celular),
    }
    return tela(request, "alertas.html", contexto)


@roteador.get("/sino")
def sino(request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoCliente) -> HTMLResponse:
    """O sino: quantos alertas abertos há nos sites do usuário."""
    contexto = {"abertos": len(alertas.abertos(sessao, acesso)), "tela": "/alertas"}
    return tela(request, "alertas_sino.html", contexto)


@roteador.post("/whatsapp")
def pedir_o_whatsapp(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoGestor, momento: Agora
) -> HTMLResponse:
    """O link do WhatsApp com o código de uso único (só o gestor)."""
    return _whatsapp(request, sessao, acesso, momento, voltar="/alertas")


# --- A administração ------------------------------------------------------------------------


@roteador_da_administracao.get("")
def tela_da_administracao(
    request: Request, sessao: SessaoDaRequisicao, administracao: AcessoDaAdministracao
) -> HTMLResponse:
    """Os alertas abertos da caixa, da câmera e das tarefas, de todas as empresas."""
    abertos = alertas.abertos_da_administracao(sessao, administracao)
    lugares = alertas.lugares_da_administracao(sessao, administracao, abertos)
    linhas = []
    for alerta in abertos:
        lugar = lugares.get(alerta.id)
        onde = f"{lugar.empresa} · {lugar.site}" if lugar else "plataforma"
        linhas.append(_linha(alerta, onde, lugar.fuso if lugar else FUSO_PADRAO))
    contexto = {
        "abertos": linhas,
        "administracao": True,
        "pede_o_whatsapp": "/administracao/alertas/whatsapp",
        "celular": celular_escondido(alertas.celular_autorizado(sessao, administracao)),
    }
    return tela(request, "administracao_alertas.html", contexto)


@roteador_da_administracao.get("/sino")
def sino_da_administracao(
    request: Request, sessao: SessaoDaRequisicao, administracao: AcessoDaAdministracao
) -> HTMLResponse:
    """O sino da administração."""
    abertos = alertas.abertos_da_administracao(sessao, administracao)
    contexto = {"abertos": len(abertos), "tela": "/administracao/alertas"}
    return tela(request, "alertas_sino.html", contexto)


@roteador_da_administracao.post("/whatsapp")
def pedir_o_whatsapp_da_administracao(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
) -> HTMLResponse:
    """O link do WhatsApp com o código de uso único, para a administração."""
    return _whatsapp(request, sessao, administracao, momento, voltar="/administracao/alertas")


# --- Comum ----------------------------------------------------------------------------------


def _whatsapp(
    request: Request,
    sessao: Session,
    quem: Acesso | AcessoAdmin,
    momento: datetime,
    *,
    voltar: str,
) -> HTMLResponse:
    numero: str | None = request.app.state.whatsapp_numero
    contexto: dict[str, Any] = {"link": None, "voltar": voltar, "minutos": MINUTOS_DO_CODIGO}
    if numero is not None:
        codigo = alertas.pedir_codigo(sessao, quem, agora=momento)
        sessao.commit()
        link = whatsapp.link_para_autorizar(numero, f"ALERTAS {codigo}")
        # O SVG sai do segno, a partir do link que montamos: pode ir direto na tela.
        contexto |= {"link": link, "codigo": codigo, "qr": Markup(qr_em_svg(link))}
    resposta = tela(request, "alertas_whatsapp.html", contexto)
    resposta.headers.update(SEM_CACHE)
    return resposta


def _linha(alerta: Alerta, onde: str, fuso: str) -> dict[str, Any]:
    local = ZoneInfo(fuso)
    fechado = alerta.fechado_em.astimezone(local) if alerta.fechado_em else None
    return {
        "texto": alerta.texto,
        "onde": onde,
        "grave": alerta.tipo in alertas.GRAVES,
        "aberto": alerta.fechado_em is None,
        "desde": f"{alerta.aberto_em.astimezone(local):%d/%m %H:%M}",
        "ate": f"{fechado:%d/%m %H:%M}" if fechado else "",
    }

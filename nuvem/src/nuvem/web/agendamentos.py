"""Tela de agendamentos (SDD 6.2): o gestor vê e alimenta os agendamentos dos sites dele.

- A lista do dia (ou da semana), no fuso do site, com o cancelamento.
- Importar a planilha, com o relatório por linha, e baixar os modelos.
- Gerar e revogar os links das transportadoras. O endereço de um link novo aparece uma vez só,
  na resposta do pedido que o gerou (a página não vai para o cache).

Só o gestor, e só nos sites dele: outro papel recebe 403; site ou agendamento de outra empresa,
404.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from nuvem.agendamento import link as links
from nuvem.agendamento import servico
from nuvem.agendamento.modelos import Agendamento, LinkTransportadora
from nuvem.agendamento.planilha import (
    MAXIMO_DE_BYTES,
    Planilha,
    PlanilhaInvalidaError,
    importar_planilha,
    modelo_csv,
    modelo_xlsx,
)
from nuvem.agendamento.servico import Relatorio
from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, exigir_papel
from nuvem.cadastro.modelos import Site
from nuvem.erros import DadoInvalidoError
from nuvem.relogio import agora
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/agendamentos", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDoGestor = Annotated[Acesso, Depends(exigir_papel("gestor"))]
Agora = Annotated[datetime, Depends(agora)]
DIAS_DA_LISTA = (1, 7)
"""A lista mostra um dia ou uma semana."""

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass(frozen=True)
class Avisos:
    """O que a tela mostra além da lista, depois de um pedido do gestor."""

    relatorio: Relatorio | None = None
    erro_da_planilha: str | None = None
    link_novo: str | None = None
    erro_do_link: str | None = None


@roteador.get("")
def tela_de_agendamentos(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoGestor,
    momento: Agora,
    site: int | None = None,
    dia: date | None = None,
    dias: int = 1,
) -> HTMLResponse:
    """A lista do dia (ou da semana) de um site do gestor, com a planilha e os links."""
    if dias not in DIAS_DA_LISTA:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "a lista é de 1 ou 7 dias")
    return _tela(request, sessao, acesso, momento, site, dia, dias, Avisos())


@roteador.post("/planilha")
async def subir_planilha(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoGestor,
    momento: Agora,
    site: int,
    arquivo: UploadFile,
) -> HTMLResponse:
    """Importa a planilha no site e mostra o relatório por linha."""
    conteudo = await arquivo.read(MAXIMO_DE_BYTES + 1)
    planilha = Planilha(nome=arquivo.filename or "", conteudo=conteudo)
    return await run_in_threadpool(_importar, request, sessao, acesso, momento, site, planilha)


def _importar(
    request: Request,
    sessao: Session,
    acesso: Acesso,
    momento: datetime,
    site: int,
    planilha: Planilha,
) -> HTMLResponse:
    try:
        relatorio = importar_planilha(sessao, acesso, site, planilha, agora=momento)
    except PlanilhaInvalidaError as erro:
        avisos = Avisos(erro_da_planilha=str(erro))
        resposta = _tela(request, sessao, acesso, momento, site, None, 1, avisos)
        resposta.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return resposta
    sessao.commit()
    return _tela(request, sessao, acesso, momento, site, None, 1, Avisos(relatorio=relatorio))


@roteador.get("/modelo.csv")
def baixar_modelo_csv(_acesso: AcessoDoGestor) -> Response:
    """O modelo da planilha em CSV (só o cabeçalho)."""
    return _arquivo(modelo_csv(), "text/csv; charset=utf-8", "modelo-agendamentos.csv")


@roteador.get("/modelo.xlsx")
def baixar_modelo_xlsx(_acesso: AcessoDoGestor) -> Response:
    """O modelo da planilha em XLSX (a agenda vazia e uma aba de exemplo)."""
    return _arquivo(modelo_xlsx(), TIPO_XLSX, "modelo-agendamentos.xlsx")


@roteador.post("/links")
def gerar_link(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoGestor,
    momento: Agora,
    site: int,
    nome: Annotated[str, Form()],
    dias: Annotated[str, Form()] = str(links.VALIDADE_PADRAO.days),
    limite: Annotated[str, Form()] = str(links.LIMITE_PADRAO),
) -> HTMLResponse:
    """Gera um link para uma transportadora e mostra o endereço, uma vez só."""
    try:
        gerado = links.gerar_link(
            sessao,
            acesso,
            site,
            nome=nome,
            agora=momento,
            validade=timedelta(days=_numero(dias, "a validade")),
            limite=_numero(limite, "o limite"),
        )
    except DadoInvalidoError as erro:
        avisos = Avisos(erro_do_link=str(erro))
        resposta = _tela(request, sessao, acesso, momento, site, None, 1, avisos)
        resposta.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return resposta
    sessao.commit()
    base = request.app.state.url_publica or str(request.base_url)
    endereco = f"{base.rstrip('/')}/agendar/{gerado.codigo}"
    resposta = _tela(request, sessao, acesso, momento, site, None, 1, Avisos(link_novo=endereco))
    # O código está nesta página: ela não fica guardada no navegador nem em proxy.
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


@roteador.post("/links/{link_id}/revogar")
def revogar_link(
    sessao: SessaoDaRequisicao, acesso: AcessoDoGestor, momento: Agora, link_id: int
) -> RedirectResponse:
    """Revoga um link: ele deixa de valer na hora."""
    link = links.revogar_link(sessao, acesso, link_id, agora=momento)
    sessao.commit()
    return RedirectResponse(
        f"/agendamentos?site={link.site_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@roteador.post("/{agendamento_id}/cancelar")
def cancelar(
    sessao: SessaoDaRequisicao, acesso: AcessoDoGestor, momento: Agora, agendamento_id: int
) -> RedirectResponse:
    """Cancela um agendamento e volta à lista do dia dele."""
    agendamento = servico.cancelar(sessao, acesso, agendamento_id, agora=momento)
    fuso = ZoneInfo(cadastro.obter_site(sessao, acesso, agendamento.site_id).fuso)
    dia = agendamento.janela_inicio.astimezone(fuso).date()
    sessao.commit()
    return RedirectResponse(
        f"/agendamentos?site={agendamento.site_id}&dia={dia.isoformat()}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _tela(
    request: Request,
    sessao: Session,
    acesso: Acesso,
    momento: datetime,
    site_id: int | None,
    dia: date | None,
    dias: int,
    avisos: Avisos,
) -> HTMLResponse:
    sites = cadastro.listar_sites(sessao, acesso)
    if not sites:
        return tela(request, "aviso.html", {"mensagem": "Você não está ligado a nenhum site."})
    site = cadastro.obter_site(sessao, acesso, site_id) if site_id is not None else sites[0]
    fuso = ZoneInfo(site.fuso)
    dia = dia or momento.astimezone(fuso).date()
    de = datetime.combine(dia, time(0), fuso)
    ate = datetime.combine(dia + timedelta(days=dias), time(0), fuso)
    agendamentos = servico.listar(sessao, acesso, site.id, de=de, ate=ate)
    contexto: dict[str, Any] = {
        "site": site,
        "outros_sites": [outro for outro in sites if outro.id != site.id],
        "periodo": _periodo(dia, dias),
        "dia": dia.isoformat(),
        "dias": dias,
        "anterior": (dia - timedelta(days=dias)).isoformat(),
        "proximo": (dia + timedelta(days=dias)).isoformat(),
        "agendamentos": [_linha(agendamento, fuso) for agendamento in agendamentos],
        "links": [
            _link(link, site, momento) for link in links.listar_links(sessao, acesso, site.id)
        ],
        "avisos": avisos,
        "validade_padrao": links.VALIDADE_PADRAO.days,
        "limite_padrao": links.LIMITE_PADRAO,
    }
    return tela(request, "agendamentos.html", contexto)


def _periodo(dia: date, dias: int) -> str:
    if dias == 1:
        return f"{dia:%d/%m/%Y}"
    return f"{dia:%d/%m/%Y} a {dia + timedelta(days=dias - 1):%d/%m/%Y}"


def _linha(agendamento: Agendamento, fuso: ZoneInfo) -> dict[str, Any]:
    inicio = agendamento.janela_inicio.astimezone(fuso)
    fim = agendamento.janela_fim.astimezone(fuso)
    return {
        "id": agendamento.id,
        "dia": f"{inicio:%d/%m}",
        "janela": f"{inicio:%H:%M} às {fim:%H:%M}",
        "codigo": agendamento.codigo_externo,
        "origem": agendamento.origem,
        "tipo": agendamento.tipo,
        "placas": ", ".join([agendamento.placa_cavalo, *agendamento.placas_reboques]),
        "motorista": agendamento.motorista_nome or "",
        "celular": _celular(agendamento.motorista_celular),
        "toneladas": _toneladas(agendamento),
        "situacao": agendamento.situacao,
    }


def _link(link: LinkTransportadora, site: Site, momento: datetime) -> dict[str, Any]:
    return {
        "id": link.id,
        "nome": link.nome,
        "vence": f"{link.vence_em.astimezone(ZoneInfo(site.fuso)):%d/%m/%Y %H:%M}",
        "envios": f"{link.envios} de {link.limite_de_envios}",
        "situacao": links.situacao_do_link(link, agora=momento),
    }


def _celular(guardado: str | None) -> str:
    # Guardado como +5511987654321; na tela, como as pessoas leem: (11) 98765-4321.
    if not guardado:
        return ""
    numero = guardado.removeprefix("+55")
    return f"({numero[:2]}) {numero[2:7]}-{numero[7:]}"


def _toneladas(agendamento: Agendamento) -> str:
    # Como se escreve no Brasil: 32,5 (e não 32.500).
    if agendamento.toneladas is None:
        return ""
    return format(agendamento.toneladas.normalize(), "f").replace(".", ",")


def _arquivo(conteudo: bytes, tipo: str, nome: str) -> Response:
    return Response(
        conteudo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'}
    )


def _numero(texto: str, o_que: str) -> int:
    try:
        return int(texto.strip())
    except ValueError:
        raise DadoInvalidoError(f"{o_que} precisa ser um número inteiro") from None

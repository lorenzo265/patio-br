"""Tela crua da portaria (T12): as últimas passagens do site, atualizadas a cada 2 segundos.

A página traz o HTMX, que busca a lista (``/portaria/passagens``) ao abrir e a cada 2
segundos. A atualização empurrada pelo servidor (SSE) vem com a tela definitiva, no mês 3.
"""

from typing import Annotated, Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from nuvem.armazenamento import Armazenamento, obter_armazenamento
from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, exigir_papel
from nuvem.portaria import servico as portaria
from nuvem.portaria.modelos import PassagemRecebida
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/portaria", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaPortaria = Annotated[Acesso, Depends(exigir_papel("porteiro", "gestor"))]

CACHE_DA_FOTO = "private, max-age=86400, immutable"
"""A foto de uma passagem nunca muda (SDD 5.5): o navegador pode guardá-la."""


@roteador.get("")
def tela_da_portaria(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDaPortaria, site: int | None = None
) -> HTMLResponse:
    """A tela da portaria de um site do usuário (o primeiro, se nenhum for pedido)."""
    sites = cadastro.listar_sites(sessao, acesso)
    if not sites:
        return tela(request, "aviso.html", {"mensagem": "Você não está ligado a nenhum site."})
    escolhido = cadastro.obter_site(sessao, acesso, site) if site is not None else sites[0]
    outros = [outro for outro in sites if outro.id != escolhido.id]
    return tela(request, "portaria.html", {"site": escolhido, "outros_sites": outros})


@roteador.get("/passagens")
def lista_de_passagens(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDaPortaria, site: int
) -> HTMLResponse:
    """A lista das últimas passagens (o pedaço da tela que o HTMX troca)."""
    passagens = portaria.ultimas_passagens(sessao, acesso, site)
    fuso = ZoneInfo(cadastro.obter_site(sessao, acesso, site).fuso)
    faixas = cadastro.nomes_das_faixas(sessao, acesso, site)
    linhas = [_linha(passagem, fuso, faixas) for passagem in passagens]
    return tela(request, "portaria_passagens.html", {"passagens": linhas})


@roteador.get("/fotos/{passagem_id}/{indice}")
def foto(
    sessao: SessaoDaRequisicao,
    acesso: AcessoDaPortaria,
    armazenamento: Annotated[Armazenamento, Depends(obter_armazenamento)],
    passagem_id: UUID,
    indice: int,
) -> Response:
    """Uma foto de uma passagem que o usuário vê (404 para qualquer outra)."""
    conteudo = portaria.foto_da_passagem(sessao, acesso, armazenamento, passagem_id, indice)
    return Response(conteudo, media_type="image/jpeg", headers={"Cache-Control": CACHE_DA_FOTO})


def _linha(passagem: PassagemRecebida, fuso: ZoneInfo, faixas: dict[int, str]) -> dict[str, Any]:
    # O horário vai no fuso do site: é o que o porteiro vê no relógio da parede.
    inicio = passagem.inicio.astimezone(fuso)
    fotos = passagem.como_veio["fotos"]
    foto_da_placa = next((i for i, f in enumerate(fotos) if f["tipo"] == "placa"), None)
    return {
        "id": str(passagem.id),
        "data": inicio.strftime("%d/%m"),
        "hora": inicio.strftime("%H:%M:%S"),
        "faixa": faixas.get(passagem.faixa_id, f"faixa {passagem.faixa_id}"),
        "sentido": passagem.sentido,
        "placas": [
            {
                "placa": placa["placa"],
                "papel": placa["papel"],
                "confianca": f"{round(placa['confianca'] * 100)}%",
            }
            for placa in passagem.como_veio["placas"]
        ],
        "foto": foto_da_placa,
    }

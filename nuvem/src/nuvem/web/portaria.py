"""Tela crua da portaria (T12, T34 e T38): as últimas passagens e as exceções abertas do site.

A página traz o HTMX, que busca as listas (``/portaria/passagens`` e ``/portaria/excecoes``) ao
abrir e a cada 2 segundos. A atualização empurrada pelo servidor (SSE) e a resolução das
exceções vêm com a tela definitiva, no mês 3.

A conferência da placa (D-42) tem página própria (``/portaria/conferir/<passagem>``), fora das
listas que se atualizam: a atualização não apaga o que o porteiro digita.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from contratos.placa import PlacaInvalidaError
from nuvem.agendamento import servico as agendamentos
from nuvem.armazenamento import Armazenamento, obter_armazenamento
from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, exigir_papel
from nuvem.erros import NaoEncontradoError
from nuvem.portaria import conferencia, visitas
from nuvem.portaria import servico as portaria
from nuvem.portaria.modelos import ConferenciaPlaca, Excecao, PassagemRecebida
from nuvem.relogio import agora
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/portaria", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaPortaria = Annotated[Acesso, Depends(exigir_papel("porteiro", "gestor"))]
Agora = Annotated[datetime, Depends(agora)]

SENTIDO_NA_TELA = {"entrada": "entrada", "saida": "saída"}

FORA_DO_FORMATO = "não está no formato antigo (ABC1234) nem no Mercosul (ABC1D23)"

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
    resultados = portaria.resultados(sessao, acesso, passagens)
    conferidas = conferencia.ultimas_por_passagem(sessao, acesso, [p.id for p in passagens])
    linhas = [
        _linha(passagem, fuso, faixas)
        | {
            "resultado": resultados[passagem.id],
            "conferencia": _resumo_da_conferencia(conferidas.get(passagem.id, [])),
        }
        for passagem in passagens
    ]
    return tela(request, "portaria_passagens.html", {"passagens": linhas})


@roteador.get("/conferir/{passagem_id}")
def tela_de_conferir(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDaPortaria, passagem_id: UUID
) -> HTMLResponse:
    """Os recortes de placa de uma passagem, para o porteiro confirmar ou corrigir (D-42)."""
    return _conferir(request, sessao, acesso, passagem_id)


@roteador.post("/conferir/{passagem_id}", response_model=None)
def conferir(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDaPortaria,
    momento: Agora,
    passagem_id: UUID,
    foto: Annotated[int, Form()],
    placa: Annotated[str, Form()],
) -> HTMLResponse | RedirectResponse:
    """Grava a placa certa de um recorte e volta para a página da conferência."""
    try:
        conferencia.conferir(sessao, acesso, passagem_id, foto, placa, agora=momento)
    except PlacaInvalidaError:
        erro = f"A placa “{placa.strip()}” {FORA_DO_FORMATO}."
        return _conferir(request, sessao, acesso, passagem_id, erro=erro)
    sessao.commit()
    return RedirectResponse(f"/portaria/conferir/{passagem_id}", status.HTTP_303_SEE_OTHER)


def _conferir(
    request: Request, sessao: Session, acesso: Acesso, passagem_id: UUID, *, erro: str = ""
) -> HTMLResponse:
    recortes = conferencia.recortes(sessao, acesso, passagem_id)
    passagem = portaria.obter_passagem(sessao, acesso, passagem_id)
    fuso = ZoneInfo(cadastro.obter_site(sessao, acesso, passagem.site_id).fuso)
    contexto = {
        "passagem": _linha(
            passagem, fuso, cadastro.nomes_das_faixas(sessao, acesso, passagem.site_id)
        ),
        "site_id": passagem.site_id,
        "recortes": [
            {
                "foto": recorte.foto,
                "placa_lida": recorte.placa_lida,
                "ultima": _ultima(recorte.ultima, fuso),
            }
            for recorte in recortes
        ],
        "erro": erro,
    }
    codigo = status.HTTP_422_UNPROCESSABLE_CONTENT if erro else status.HTTP_200_OK
    return tela(request, "portaria_conferir.html", contexto, codigo)


def _ultima(feita: ConferenciaPlaca | None, fuso: ZoneInfo) -> dict[str, str] | None:
    if feita is None:
        return None
    momento = feita.momento.astimezone(fuso)
    return {
        "dia": momento.strftime("%d/%m"),
        "hora": momento.strftime("%H:%M"),
        "placa": feita.placa,
        "como": "corrigida" if feita.corrigida else "certa",
    }


def _resumo_da_conferencia(feitas: list[ConferenciaPlaca]) -> str:
    """Ex.: "placa certa", "corrigida: ABC1D28" (uma parte por recorte conferido)."""
    return " · ".join(f"corrigida: {f.placa}" if f.corrigida else "placa certa" for f in feitas)


MOTIVO_NA_TELA = {
    "sem_placa": "nenhuma placa lida",
    "sem_candidato": "sem agendamento com estas placas",
    "pontos_baixos": "parecido com um agendamento, mas sem segurança",
    "candidatos_proximos": "mais de um agendamento possível",
}


@roteador.get("/excecoes")
def lista_de_excecoes(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDaPortaria, site: int
) -> HTMLResponse:
    """As exceções abertas do site, da chegada mais antiga para a mais nova (só ver)."""
    excecoes = visitas.excecoes_abertas(sessao, acesso, site)
    fuso = ZoneInfo(cadastro.obter_site(sessao, acesso, site).fuso)
    cartoes = [_cartao(sessao, acesso, excecao, fuso) for excecao in excecoes]
    return tela(request, "portaria_excecoes.html", {"excecoes": cartoes})


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


def _cartao(sessao: Session, acesso: Acesso, excecao: Excecao, fuso: ZoneInfo) -> dict[str, Any]:
    visita = visitas.obter_visita(sessao, acesso, excecao.visita_id)
    passagem = portaria.obter_passagem(sessao, acesso, excecao.passagem_id)
    chegada = (visita.chegou_em or visita.criada_em).astimezone(fuso)
    return {
        "id": excecao.id,
        "passagem_id": str(passagem.id),
        "data": chegada.strftime("%d/%m"),
        "hora": chegada.strftime("%H:%M:%S"),
        "motivo": MOTIVO_NA_TELA[excecao.motivo],
        "placas": visita.composicao,
        "foto": _foto_da_placa(passagem),
        "candidatos": [
            candidato
            for item in excecao.candidatos
            if (candidato := _candidato(sessao, acesso, item, fuso)) is not None
        ],
    }


def _candidato(
    sessao: Session, acesso: Acesso, item: dict[str, Any], fuso: ZoneInfo
) -> dict[str, Any] | None:
    try:
        agendamento = agendamentos.obter(sessao, acesso, item["agendamento_id"])
    except NaoEncontradoError:
        return None  # o porteiro não vê este site (não deveria acontecer)
    inicio = agendamento.janela_inicio.astimezone(fuso)
    fim = agendamento.janela_fim.astimezone(fuso)
    return {
        "codigo": agendamento.codigo_externo,
        "placas": ", ".join([agendamento.placa_cavalo, *agendamento.placas_reboques]),
        "janela": f"{inicio:%d/%m} {inicio:%H:%M} às {fim:%H:%M}",
        "motorista": agendamento.motorista_nome or "",
        "pontos": item["pontos"],
    }


def _foto_da_placa(passagem: PassagemRecebida) -> int | None:
    fotos = passagem.como_veio["fotos"]
    return next((i for i, f in enumerate(fotos) if f["tipo"] == "placa"), None)


def _linha(passagem: PassagemRecebida, fuso: ZoneInfo, faixas: dict[int, str]) -> dict[str, Any]:
    # O horário vai no fuso do site: é o que o porteiro vê no relógio da parede.
    inicio = passagem.inicio.astimezone(fuso)
    return {
        "id": str(passagem.id),
        "data": inicio.strftime("%d/%m"),
        "hora": inicio.strftime("%H:%M:%S"),
        "faixa": faixas.get(passagem.faixa_id, f"faixa {passagem.faixa_id}"),
        "sentido": SENTIDO_NA_TELA[passagem.sentido],
        "placas": [
            {
                "placa": placa["placa"],
                "papel": placa["papel"],
                "confianca": f"{round(placa['confianca'] * 100)}%",
            }
            for placa in passagem.como_veio["placas"]
        ],
        "foto": _foto_da_placa(passagem),
    }

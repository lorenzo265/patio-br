"""A prova da visita (SDD 6.2, D-69), só do gestor.

- ``/prova?placa=``: as últimas visitas dos sites dele, ou as de uma placa.
- ``/prova/visitas/<visita>``: a página para imprimir ou salvar em PDF. Ao abrir, sela o que
  falta e confere tudo: a cadeia, cada registro de origem, as fotos e as âncoras.
- ``/prova/visitas/<visita>.json``: o arquivo da prova, com os elos e a regra do resumo, para
  qualquer um conferir sem nós.

As horas aparecem no fuso do site; as do arquivo, em UTC.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from contratos.placa import PlacaInvalidaError, normalizar_placa
from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, exigir_papel
from nuvem.portaria.modelos import TipoDeEvento, Visita
from nuvem.prova import cadeia
from nuvem.prova import servico as prova
from nuvem.prova.modelos import EloDaProva
from nuvem.prova.servico import Conferencia
from nuvem.relogio import agora
from nuvem.web.mensagens import celular_escondido
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/prova", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDoGestor = Annotated[Acesso, Depends(exigir_papel("gestor"))]
Agora = Annotated[datetime, Depends(agora)]

ROTULOS_DOS_EVENTOS: dict[TipoDeEvento, str] = {
    "check_in": "check-in",
    "excecao": "exceção",
    "nao_veio": "não veio",
    "saiu_sem_atendimento": "saiu sem atendimento",
    "aceita_sem_agendamento": "aceita sem agendamento",
    "recusada": "recusada",
    "placa_corrigida": "placa corrigida",
    "chamada": "chamada",
    "chamada_cancelada": "chamada cancelada",
    "inicio_na_doca": "início na doca",
    "fim_na_doca": "fim na doca",
    "saiu": "saiu",
}
SITUACOES_NA_TELA = {
    "criada": "criada",
    "enviada": "enviada",
    "entregue": "entregue",
    "lida": "lida",
    "falhou": "falhou",
}


@roteador.get("")
def busca(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoGestor, placa: str = ""
) -> HTMLResponse:
    """As últimas visitas, ou as de uma placa."""
    erro = None
    procurada = None
    if placa.strip():
        try:
            procurada = normalizar_placa(placa)
        except PlacaInvalidaError:
            erro = "Placa inválida: use o formato ABC1234 ou ABC1D23."
    sites = {site.id: site for site in cadastro.listar_sites(sessao, acesso)}
    visitas = [] if erro else prova.visitas_para_a_prova(sessao, acesso, placa=procurada)
    linhas = [
        {
            "id": visita.id,
            "placa": _placa(visita),
            "site": sites[visita.site_id].nome,
            "chegou": _local(visita.chegou_em or visita.criada_em, sites[visita.site_id].fuso),
            "estado": visita.estado,
        }
        for visita in visitas
    ]
    return tela(request, "prova_busca.html", {"visitas": linhas, "placa": placa, "erro": erro})


@roteador.get("/visitas/{visita_id}.json", response_model=None)
def arquivo(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoGestor,
    momento: Agora,
    visita_id: int,
) -> Response:
    """O arquivo da prova: os elos, a regra do resumo e o resultado da conferência."""
    visita, elos, conferencia = _selar_e_conferir(request, sessao, acesso, visita_id, momento)
    site = cadastro.obter_site(sessao, acesso, visita.site_id)
    conteudo = {
        "visita": visita.id,
        "site": site.nome,
        "gerado_em": momento.isoformat(),
        "regra": cadeia.REGRA,
        "elos": [
            {
                "ordem": elo.ordem,
                "tipo": elo.tipo,
                "referencia": elo.referencia,
                "conteudo": elo.conteudo,
                "anterior": elo.anterior,
                "resumo": elo.resumo,
                "selado_em": elo.selado_em.isoformat(),
            }
            for elo in elos
        ],
        "conferencia": {
            "integra": conferencia.integra,
            "elos": conferencia.elos,
            "quebra": (
                {"ordem": conferencia.quebra.ordem, "motivo": conferencia.quebra.motivo}
                if conferencia.quebra
                else None
            ),
            "ancoras": [
                {
                    "dia": a.dia.isoformat(),
                    "situacao": a.situacao,
                    "motivo": a.motivo,
                    "travada": a.travada,
                }
                for a in conferencia.ancoras
            ],
        },
    }
    return Response(
        cadeia.json_canonico(conteudo).encode(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="prova-visita-{visita.id}.json"'},
    )


@roteador.get("/visitas/{visita_id}")
def pagina(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoGestor,
    momento: Agora,
    visita_id: int,
) -> HTMLResponse:
    """A página da prova de uma visita, para imprimir ou salvar em PDF."""
    visita, elos, conferencia = _selar_e_conferir(request, sessao, acesso, visita_id, momento)
    site = cadastro.obter_site(sessao, acesso, visita.site_id)
    fuso = site.fuso
    faixas = cadastro.nomes_das_faixas(sessao, acesso, site.id)
    cameras = {str(c.id): c.nome for c in cadastro.listar_cameras(sessao, acesso, site.id)}
    pessoas = prova.nomes_das_pessoas(
        sessao,
        acesso,
        [elo.conteudo["usuario_id"] for elo in elos if elo.conteudo.get("usuario_id")],
    )
    contexto = {
        "visita": {
            "id": visita.id,
            "placa": _placa(visita),
            "site": site.nome,
            "chegou": _local(visita.chegou_em, fuso),
            "saiu": _local(visita.saiu_em, fuso),
            "estado": visita.estado,
        },
        "conferencia": _conferencia(conferencia, elos),
        "passagens": _passagens(elos, faixas, cameras, fuso),
        "eventos": [
            {
                "quando": _local(_hora(elo.conteudo["momento"]), fuso),
                "o_que": ROTULOS_DOS_EVENTOS.get(elo.conteudo["tipo"], elo.conteudo["tipo"]),
                "quem": pessoas.get(elo.conteudo["usuario_id"], "o sistema"),
            }
            for elo in elos
            if elo.tipo == "evento"
        ],
        "conferencias": [
            {
                "quando": _local(_hora(elo.conteudo["momento"]), fuso),
                "lida": elo.conteudo["placa_lida"] or "nada",
                "placa": elo.conteudo["placa"],
                "quem": pessoas.get(elo.conteudo["usuario_id"], ""),
            }
            for elo in elos
            if elo.tipo == "conferencia"
        ],
        "mensagens": _mensagens(elos, fuso),
        "elos": [
            {
                "ordem": elo.ordem,
                "tipo": elo.tipo,
                "referencia": elo.referencia,
                "resumo": elo.resumo,
                "selado": _local(elo.selado_em, fuso),
            }
            for elo in elos
        ],
        "regra": cadeia.REGRA,
    }
    return tela(request, "prova.html", contexto)


def _selar_e_conferir(
    request: Request, sessao: Session, acesso: Acesso, visita_id: int, momento: datetime
) -> tuple[Visita, list[EloDaProva], Conferencia]:
    # Sela o que falta antes de mostrar: a página e o arquivo trazem a visita inteira.
    if prova.selar_a_visita(sessao, acesso, visita_id, agora=momento):
        sessao.commit()
    conferencia = prova.conferir(
        sessao, acesso, visita_id, request.app.state.armazenamento, request.app.state.ancoras
    )
    elos = prova.elos_da_visita(sessao, acesso, visita_id)
    visita = sessao.get(Visita, visita_id)
    assert visita is not None  # a conferência já achou a visita
    return visita, elos, conferencia


def _conferencia(conferencia: Conferencia, elos: Sequence[EloDaProva]) -> dict[str, Any]:
    quebrado = None
    if conferencia.quebra is not None:
        (elo,) = [e for e in elos if e.ordem == conferencia.quebra.ordem]
        quebrado = {
            "ordem": elo.ordem,
            "tipo": elo.tipo,
            "referencia": elo.referencia,
            "motivo": conferencia.quebra.motivo,
        }
    return {
        "integra": conferencia.integra,
        "elos": conferencia.elos,
        "quebrado": quebrado,
        "ancoras": [
            {
                "dia": f"{a.dia:%d/%m/%Y}",
                "situacao": a.situacao,
                "motivo": a.motivo,
                "travada": a.travada,
            }
            for a in conferencia.ancoras
        ],
    }


def _passagens(
    elos: Sequence[EloDaProva], faixas: dict[int, str], cameras: dict[str, str], fuso: str
) -> list[dict[str, Any]]:
    resumos = {
        (elo.conteudo["passagem"], elo.conteudo["indice"]): elo.conteudo["resumo"]
        for elo in elos
        if elo.tipo == "foto"
    }
    passagens = []
    for elo in elos:
        if elo.tipo != "passagem":
            continue
        passagem = elo.conteudo["passagem"]
        como_veio = passagem["como_veio"]
        saude = elo.conteudo.get("saude")
        passagens.append(
            {
                "id": passagem["id"],
                "inicio": _local(_hora(como_veio["inicio"]), fuso, segundos=True),
                "fim": _local(_hora(como_veio["fim"]), fuso, segundos=True),
                "recebida": _local(_hora(passagem["recebida_em"]), fuso, segundos=True),
                "faixa": faixas.get(passagem["faixa_id"], f"faixa {passagem['faixa_id']}"),
                "sentido": como_veio["sentido"],
                "leitor": como_veio["versao_leitor"],
                "placas": [
                    {
                        "placa": placa["placa"],
                        "papel": placa["papel"],
                        "confianca": f"{round(placa['confianca'] * 100)}%",
                        "camera": cameras.get(placa["camera_id"], f"câmera {placa['camera_id']}"),
                    }
                    for placa in como_veio["placas"]
                ],
                "fotos": [
                    {
                        "indice": indice,
                        "tipo": foto["tipo"],
                        "camera": cameras.get(foto["camera_id"], f"câmera {foto['camera_id']}"),
                        "resumo": resumos.get((passagem["id"], indice)),
                    }
                    for indice, foto in enumerate(como_veio["fotos"])
                ],
                "saude": _saude(saude, fuso),
            }
        )
    return passagens


def _saude(saude: dict[str, Any] | None, fuso: str) -> str:
    if saude is None:
        return "sem saúde da caixa até a passagem chegar"
    diferenca = f"{saude['diferenca_do_relogio']:+.1f}".replace(".", ",")
    quando = _local(_hora(saude["recebida_em"]), fuso)
    return (
        f"saúde das {quando}: relógio da caixa com {diferenca} s de diferença, "
        f"{saude['cameras_no_ar']} de {saude['cameras']} câmeras no ar"
    )


def _mensagens(elos: Sequence[EloDaProva], fuso: str) -> list[dict[str, Any]]:
    por_mensagem: dict[int, dict[str, Any]] = {}
    for elo in elos:
        if elo.tipo != "mensagem":
            continue
        conteudo = elo.conteudo
        linha = por_mensagem.setdefault(
            conteudo["mensagem"],
            {
                "modelo": conteudo["modelo"],
                "canal": conteudo["canal"],
                "para": celular_escondido(conteudo["para"]),
                "texto": "",
                "situacoes": [],
            },
        )
        if conteudo["situacao"] == "criada":
            linha["texto"] = conteudo.get("texto", "")
        linha["situacoes"].append(
            f"{SITUACOES_NA_TELA[conteudo['situacao']]} {_local(_hora(conteudo['momento']), fuso)}"
        )
    return list(por_mensagem.values())


def _placa(visita: Visita) -> str:
    composicao: list[dict[str, str]] = visita.composicao or []
    return " + ".join(item["placa"] for item in composicao) or "sem placa"


def _hora(texto: str) -> datetime:
    return datetime.fromisoformat(texto)


def _local(momento: datetime | None, fuso: str, *, segundos: bool = False) -> str:
    if momento is None:
        return ""
    local = momento.astimezone(ZoneInfo(fuso))
    return f"{local:%d/%m %H:%M:%S}" if segundos else f"{local:%d/%m %H:%M}"

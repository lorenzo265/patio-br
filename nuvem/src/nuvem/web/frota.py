"""A frota de borda da administração (SDD 6.2, D-65): cada caixa, como está, e o histórico.

- ``/administracao/frota``: cada caixa não revogada, com a empresa, o site, as versões, o último
  contato, as câmeras, a fila, a máquina e o relógio.
- ``/administracao/frota/<caixa>``: a última saúde, câmera a câmera, e os últimos 7 dias, hora a
  hora (quantas saúdes chegaram em cada hora mostra quando a caixa sumiu).

As horas aparecem no fuso do site da caixa.
"""

from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro.acesso import AcessoAdmin, obter_acesso_admin
from nuvem.frota import saude
from nuvem.frota.saude import CaixaNaFrota, HoraDaCaixa
from nuvem.relogio import agora
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/administracao/frota", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaAdministracao = Annotated[AcessoAdmin, Depends(obter_acesso_admin)]
Agora = Annotated[datetime, Depends(agora)]


@roteador.get("")
def tela_da_frota(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
) -> HTMLResponse:
    """Todas as caixas, das mais novas para as mais antigas."""
    caixas = [_caixa(caixa) for caixa in saude.frota(sessao, administracao, agora=momento)]
    return tela(request, "administracao_frota.html", {"caixas": caixas})


@roteador.get("/{caixa_id}")
def tela_da_caixa(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    caixa_id: int,
) -> HTMLResponse:
    """Uma caixa: a última saúde e os últimos 7 dias, hora a hora (404 se não existir)."""
    caixa = saude.caixa_da_frota(sessao, administracao, caixa_id, agora=momento)
    horas = saude.historico_por_hora(sessao, administracao, caixa_id, agora=momento)
    contexto = {"caixa": _caixa(caixa), "horas": [_hora(hora) for hora in horas]}
    return tela(request, "administracao_caixa.html", contexto)


def _caixa(caixa: CaixaNaFrota) -> dict[str, Any]:
    fuso = ZoneInfo(caixa.fuso)
    if caixa.ultimo_contato is None:
        situacao = "nunca deu sinal"
    elif caixa.sem_contato:
        situacao = f"sem contato desde {_dia_e_hora(caixa.ultimo_contato, fuso)}"
    else:
        situacao = "no ar"
    linha: dict[str, Any] = {
        "id": caixa.caixa_id,
        "empresa": caixa.empresa,
        "site": caixa.site,
        "situacao": situacao,
        "sem_contato": caixa.sem_contato,
        "ativada": _dia_e_hora(caixa.ativada_em, fuso),
        "ultimo_contato": _dia_e_hora(caixa.ultimo_contato, fuso) if caixa.ultimo_contato else "",
        "versoes": " · ".join(
            versao for versao in (caixa.versao_programa, caixa.versao_leitor) if versao
        ),
        "relogio": _segundos(caixa.diferenca_do_relogio),
        "cameras": [
            {
                "nome": camera.nome,
                "no_ar": camera.no_ar,
                "quadros_por_segundo": _numero(camera.quadros_por_segundo),
                "ultimo_quadro": (
                    camera.ultimo_quadro.astimezone(fuso).strftime("%d/%m %H:%M:%S")
                    if camera.ultimo_quadro
                    else "nunca"
                ),
            }
            for camera in caixa.cameras
        ],
        "fila": "",
        "maquina": "",
    }
    if caixa.saude is not None:
        fila = caixa.saude.fila
        linha["fila"] = ", ".join(
            [
                _quantas(fila.passagens, "passagem", "passagens"),
                _quantas(fila.fotos, "foto", "fotos"),
                _quantas(fila.recusadas, "recusada", "recusadas"),
            ]
        )
        partes = [f"CPU {_numero(caixa.saude.cpu)}%"]
        if caixa.saude.temperatura is not None:
            partes.append(f"{_numero(caixa.saude.temperatura)} °C")
        partes += [
            f"memória {_numero(caixa.saude.memoria)}%",
            f"disco {_numero(caixa.saude.disco)}%",
        ]
        linha["maquina"] = " · ".join(partes)
    return linha


def _hora(hora: HoraDaCaixa) -> dict[str, Any]:
    return {
        "hora": hora.hora.strftime("%d/%m %Hh"),
        "contatos": f"{hora.contatos} de {saude.SAUDES_POR_HORA}",
        "faltou": hora.contatos < saude.SAUDES_POR_HORA,
        "cpu": f"{_numero(hora.cpu)}%",
        "temperatura": f"{_numero(hora.temperatura)} °C" if hora.temperatura is not None else "",
        "disco": f"{_numero(hora.disco)}%",
        "cameras": f"{hora.cameras_no_ar} de {hora.cameras}",
        "fila": hora.passagens_na_fila,
        "relogio": _segundos(hora.diferenca_do_relogio),
    }


def _dia_e_hora(momento: datetime, fuso: ZoneInfo) -> str:
    return momento.astimezone(fuso).strftime("%d/%m %H:%M")


def _numero(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def _segundos(valor: float | None) -> str:
    if valor is None:
        return ""
    return f"{valor:+.1f} s".replace(".", ",")


def _quantas(quantidade: int, uma: str, varias: str) -> str:
    return f"{quantidade} {uma if quantidade == 1 else varias}"

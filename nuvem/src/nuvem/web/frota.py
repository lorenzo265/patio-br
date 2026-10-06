"""A frota de borda da administração (SDD 6.2, D-65): cada caixa, como está, e o histórico.

- ``/administracao/frota``: cada caixa não revogada, com a empresa, o site, as versões, o último
  contato, as câmeras, a fila, a máquina e o relógio.
- ``/administracao/frota/<caixa>``: a última saúde, câmera a câmera, os últimos 7 dias, hora a
  hora (quantas saúdes chegaram em cada hora mostra quando a caixa sumiu), e as atualizações.
- ``/administracao/frota/versoes``: as versões da caixa: cadastrar e escolher para uma caixa, um
  site ou todas (D-67).

As horas aparecem no fuso do site da caixa.
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro.acesso import AcessoAdmin, obter_acesso_admin
from nuvem.erros import DadoInvalidoError
from nuvem.frota import saude, versoes
from nuvem.frota.saude import CaixaNaFrota, HoraDaCaixa
from nuvem.relogio import agora
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/administracao/frota", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaAdministracao = Annotated[AcessoAdmin, Depends(obter_acesso_admin)]
Agora = Annotated[datetime, Depends(agora)]

DAS_VERSOES = "/administracao/frota/versoes"
RESULTADO_NA_TELA = {"ok": "deu certo", "voltou": "voltou", "falhou": "falhou"}


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


@roteador.get("/versoes")
def tela_das_versoes(
    request: Request, sessao: SessaoDaRequisicao, administracao: AcessoDaAdministracao
) -> HTMLResponse:
    """As versões da caixa, o formulário de cadastrar e o de escolher."""
    return _tela_das_versoes(request, sessao, administracao)


@roteador.post("/versoes", response_model=None)
def cadastrar_versao(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    nome: Annotated[str, Form(max_length=50)],
    imagem: Annotated[str, Form(max_length=200)],
    resumo: Annotated[str, Form(max_length=71)],
) -> HTMLResponse | RedirectResponse:
    """Cadastra uma versão pelo resumo da imagem."""
    try:
        versoes.cadastrar_versao(
            sessao, administracao, nome=nome, imagem=imagem, resumo=resumo, agora=momento
        )
    except DadoInvalidoError as erro:
        sessao.rollback()
        return _tela_das_versoes(
            request, sessao, administracao, erro=str(erro), codigo=status.HTTP_400_BAD_REQUEST
        )
    sessao.commit()
    return RedirectResponse(DAS_VERSOES, status.HTTP_303_SEE_OTHER)


@roteador.post("/versoes/{versao_id}/escolher", response_model=None)
def escolher_versao(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    versao_id: int,
    alcance: Annotated[Literal["todas", "site", "caixa"], Form()],
    site_id: Annotated[int | None, Form()] = None,
    caixa_id: Annotated[int | None, Form()] = None,
) -> HTMLResponse | RedirectResponse:
    """Escolhe a versão para uma caixa, um site ou todas as caixas."""
    try:
        versoes.escolher_versao(
            sessao,
            administracao,
            versao_id,
            site_id=site_id if alcance == "site" else None,
            caixa_id=caixa_id if alcance == "caixa" else None,
            agora=momento,
        )
    except versoes.VersaoNaoProvadaError:
        sessao.rollback()
        erro = "A versão vai primeiro numa caixa: escolha para uma caixa e espere dar certo."
        return _tela_das_versoes(
            request, sessao, administracao, erro=erro, codigo=status.HTTP_409_CONFLICT
        )
    sessao.commit()
    return RedirectResponse(DAS_VERSOES, status.HTTP_303_SEE_OTHER)


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
    fuso = ZoneInfo(caixa.fuso)
    atualizacoes = [
        {
            "quando": _dia_e_hora(atualizacao.terminou_em, fuso),
            "de": atualizacao.de,
            "para": versao.nome,
            "resultado": RESULTADO_NA_TELA[atualizacao.resultado],
            "motivo": atualizacao.motivo,
        }
        for atualizacao, versao in versoes.atualizacoes_da_caixa(sessao, administracao, caixa_id)
    ]
    contexto = {
        "caixa": _caixa(caixa),
        "horas": [_hora(hora) for hora in horas],
        "atualizacoes": atualizacoes,
    }
    return tela(request, "administracao_caixa.html", contexto)


def _tela_das_versoes(
    request: Request,
    sessao: Session,
    administracao: AcessoAdmin,
    *,
    erro: str | None = None,
    codigo: int = status.HTTP_200_OK,
) -> HTMLResponse:
    lista = [
        {
            "id": item.versao.id,
            "nome": item.versao.nome,
            "resumo": item.versao.resumo[: len("sha256:") + 12],
            "imagem": item.versao.imagem,
            "sucesso": (
                f"deu certo em {item.caixas_com_sucesso} "
                f"{'caixa' if item.caixas_com_sucesso == 1 else 'caixas'}"
                if item.caixas_com_sucesso
                else "ainda não deu certo em nenhuma caixa"
            ),
        }
        for item in versoes.listar_versoes(sessao, administracao)
    ]
    contexto = {
        "versoes": lista,
        "alcances": versoes.alcances(sessao, administracao),
        "erro": erro,
    }
    return tela(request, "administracao_versoes.html", contexto, codigo)


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

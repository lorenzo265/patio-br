"""Ativação da caixa e configuração baixada da nuvem (SDD 7.4).

A administração gera um código de uso único para o site; a caixa troca o código por uma chave
própria e, com ela, baixa as faixas e as câmeras do site. A chave é um segredo: fica num arquivo
que só o dono lê e não aparece ao imprimir a caixa. A configuração baixada também fica guardada
assim, porque traz as senhas das câmeras: com ela, a caixa começa sem a nuvem (D-66).
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

from borda.agente import ConfiguracaoDoAgente

_registro = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaixaAtivada:
    """A caixa depois da ativação: a nuvem dela, os ids da nuvem e a chave."""

    nuvem: str
    caixa_id: str
    site_id: str
    chave: str = field(repr=False)


class CodigoRecusadoError(Exception):
    """O código de ativação é inválido, já foi usado ou venceu."""


class ChaveRecusadaError(Exception):
    """A nuvem não reconhece mais a chave (a caixa foi revogada, ou o banco foi zerado)."""


def ativar(cliente: httpx.Client, nuvem: str, codigo: str) -> CaixaAtivada:
    """Troca o código de ativação pela chave da caixa.

    Raises:
        CodigoRecusadoError: se a nuvem recusar o código.
        httpx.HTTPError: se a nuvem não responder como esperado.
    """
    nuvem = nuvem.rstrip("/")
    resposta = cliente.post(f"{nuvem}/api/borda/ativar", json={"codigo": codigo})
    if resposta.status_code == httpx.codes.UNAUTHORIZED:
        raise CodigoRecusadoError("código de ativação inválido, já usado ou vencido")
    resposta.raise_for_status()
    dados = resposta.json()
    return CaixaAtivada(nuvem, str(dados["caixa_id"]), str(dados["site_id"]), str(dados["chave"]))


def baixar_configuracao(cliente: httpx.Client, caixa: CaixaAtivada) -> ConfiguracaoDoAgente:
    """Baixa as faixas e as câmeras do site da caixa (com as senhas das câmeras).

    Raises:
        ChaveRecusadaError: se a nuvem não reconhecer a chave.
        httpx.HTTPError: se a nuvem não responder como esperado (ex.: fora do ar).
    """
    resposta = cliente.get(
        f"{caixa.nuvem}/api/borda/configuracao",
        headers={"Authorization": f"Bearer {caixa.chave}"},
    )
    if resposta.status_code == httpx.codes.UNAUTHORIZED:
        raise ChaveRecusadaError("a nuvem recusou a chave da caixa: ative de novo com um código")
    resposta.raise_for_status()
    return ConfiguracaoDoAgente.de_json(resposta.json())


def guardar_caixa(caixa: CaixaAtivada, arquivo: Path) -> None:
    """Guarda a caixa ativada num arquivo que só o dono lê (a chave é um segredo)."""
    _guardar_so_para_o_dono(asdict(caixa), arquivo)


def guardar_configuracao(configuracao: ConfiguracaoDoAgente, arquivo: Path) -> None:
    """Guarda a configuração num arquivo que só o dono lê (traz as senhas das câmeras)."""
    _guardar_so_para_o_dono(configuracao.para_json(), arquivo)


def ler_configuracao(arquivo: Path) -> ConfiguracaoDoAgente | None:
    """A configuração guardada, ou ``None`` se não há (ou se o arquivo está estragado)."""
    if not arquivo.is_file():
        return None
    try:
        return ConfiguracaoDoAgente.de_json(json.loads(arquivo.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError):
        _registro.warning("a configuração guardada está estragada; fica de fora")
        return None


def apagar_configuracao(arquivo: Path) -> None:
    """Apaga a configuração guardada (a chave recusada, ou a caixa ativada de novo)."""
    arquivo.unlink(missing_ok=True)


def _guardar_so_para_o_dono(dados: object, arquivo: Path) -> None:
    # Grava ao lado e troca de uma vez: a energia que cai no meio não estraga o arquivo que já
    # estava lá.
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    provisorio = arquivo.with_name(f"{arquivo.name}.novo")
    descritor = os.open(provisorio, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descritor, "w", encoding="utf-8") as saida:
        json.dump(dados, saida, indent=2)
        saida.flush()
        os.fsync(saida.fileno())
    os.chmod(provisorio, 0o600)  # se o provisório já existia com outra permissão
    os.replace(provisorio, arquivo)


def ler_caixa(arquivo: Path) -> CaixaAtivada | None:
    """Lê a caixa guardada, ou ``None`` se ela ainda não foi ativada."""
    if not arquivo.is_file():
        return None
    return CaixaAtivada(**json.loads(arquivo.read_text(encoding="utf-8")))

"""Regras da frota: ativação da caixa de borda com código de uso único e chave própria.

1. A administração gera um código para um site (vale 24 horas e uma vez só).
2. A caixa troca o código por uma chave; a nuvem guarda só o resumo da chave.
3. Toda chamada da caixa leva a chave (``Authorization: Bearer``); revogada, não vale mais.

As funções gravam com ``flush``; o ``commit`` é de quem chama.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.servico import FaixaDaBorda
from nuvem.cifra import Cifra
from nuvem.erros import NaoEncontradoError
from nuvem.frota.modelos import CaixaBorda, CodigoAtivacao
from nuvem.senhas import resumo_rapido

VALIDADE_DO_CODIGO = timedelta(hours=24)

ALFABETO_DO_CODIGO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
"""Letras e números sem os que se confundem ao digitar (0 e O, 1, I e L)."""

TAMANHO_DO_CODIGO = 12
"""12 sorteios em 31 símbolos: perto de 59 bits, impossível de adivinhar em 24 horas."""


class CodigoRecusadoError(Exception):
    """O código de ativação não existe, já foi usado ou venceu (sem dizer qual)."""


@dataclass(frozen=True)
class CodigoGerado:
    """O código como a administração o entrega a quem instala a caixa (``XXXX-XXXX-XXXX``)."""

    codigo: str
    expira_em: datetime


@dataclass(frozen=True)
class CaixaAtivada:
    """O que a caixa recebe na ativação; a chave aparece só aqui, uma vez."""

    caixa_id: int
    site_id: int
    chave: str


@dataclass(frozen=True)
class AcessoDaCaixa:
    """Uma caixa identificada pela chave: o site e a empresa dela."""

    caixa_id: int
    empresa_id: int
    site_id: int


@dataclass(frozen=True)
class ConfiguracaoDaCaixa:
    """O que a caixa baixa da nuvem para trabalhar (SDD 7.4)."""

    caixa_id: int
    site_id: int
    faixas: list[FaixaDaBorda]


def gerar_codigo_de_ativacao(
    sessao: Session, site_id: int, *, administrador_id: int, agora: datetime
) -> CodigoGerado:
    """Gera um código de ativação de uso único para um site.

    Raises:
        NaoEncontradoError: se o site não existir.
    """
    site = cadastro.obter_site_para_administracao(sessao, site_id)
    sorteado = "".join(secrets.choice(ALFABETO_DO_CODIGO) for _ in range(TAMANHO_DO_CODIGO))
    expira_em = agora + VALIDADE_DO_CODIGO
    sessao.add(
        CodigoAtivacao(
            empresa_id=site.empresa_id,
            site_id=site.id,
            codigo_resumo=resumo_rapido(sorteado),
            criado_por=administrador_id,
            criado_em=agora,
            expira_em=expira_em,
        )
    )
    sessao.flush()
    grupos = [sorteado[inicio : inicio + 4] for inicio in range(0, TAMANHO_DO_CODIGO, 4)]
    return CodigoGerado(codigo="-".join(grupos), expira_em=expira_em)


def ativar(sessao: Session, codigo: str, *, agora: datetime) -> CaixaAtivada:
    """Troca um código de ativação por uma caixa nova no site do código, com chave própria.

    O código vale digitado em minúsculas, com ou sem hífens e espaços.

    Raises:
        CodigoRecusadoError: se o código não existir, já tiver sido usado ou estiver vencido.
    """
    digitado = "".join(codigo.split()).replace("-", "").upper()
    registro = sessao.scalar(
        select(CodigoAtivacao)
        .where(
            CodigoAtivacao.codigo_resumo == resumo_rapido(digitado),
            CodigoAtivacao.usado_em.is_(None),
            CodigoAtivacao.expira_em > agora,
        )
        # Duas caixas com o mesmo código ao mesmo tempo: a segunda espera e já o encontra usado.
        .with_for_update()
    )
    if registro is None:
        raise CodigoRecusadoError
    registro.usado_em = agora
    chave = secrets.token_urlsafe(32)
    caixa = CaixaBorda(
        empresa_id=registro.empresa_id,
        site_id=registro.site_id,
        chave_resumo=resumo_rapido(chave),
        ativada_em=agora,
    )
    sessao.add(caixa)
    sessao.flush()
    return CaixaAtivada(caixa_id=caixa.id, site_id=caixa.site_id, chave=chave)


def caixa_da_chave(sessao: Session, chave: str) -> AcessoDaCaixa | None:
    """Devolve a caixa dona da chave, ou ``None`` se a chave não existir ou foi revogada."""
    caixa = sessao.scalar(
        select(CaixaBorda).where(
            CaixaBorda.chave_resumo == resumo_rapido(chave), CaixaBorda.revogada_em.is_(None)
        )
    )
    if caixa is None:
        return None
    return AcessoDaCaixa(caixa_id=caixa.id, empresa_id=caixa.empresa_id, site_id=caixa.site_id)


def configuracao(sessao: Session, cifra: Cifra, caixa: AcessoDaCaixa) -> ConfiguracaoDaCaixa:
    """As faixas e câmeras do site da caixa (com a senha das câmeras decifrada)."""
    faixas = cadastro.faixas_para_a_borda(
        sessao, cifra, empresa_id=caixa.empresa_id, site_id=caixa.site_id
    )
    return ConfiguracaoDaCaixa(caixa_id=caixa.caixa_id, site_id=caixa.site_id, faixas=faixas)


def revogar(sessao: Session, caixa_id: int, *, agora: datetime) -> CaixaBorda:
    """Revoga a chave da caixa: as chamadas dela passam a receber 401. Revogar de novo não muda
    a data da primeira revogação.

    Raises:
        NaoEncontradoError: se a caixa não existir.
    """
    caixa = sessao.get(CaixaBorda, caixa_id)
    if caixa is None:
        raise NaoEncontradoError(f"caixa {caixa_id}")
    if caixa.revogada_em is None:
        caixa.revogada_em = agora
        sessao.flush()
    return caixa


def listar_caixas(sessao: Session) -> list[CaixaBorda]:
    """Todas as caixas, das mais novas para as mais antigas. Só para a administração."""
    return list(sessao.scalars(select(CaixaBorda).order_by(CaixaBorda.id.desc())))

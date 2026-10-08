"""As versões da caixa (SDD 7.4, D-14 e D-67).

- **Cadastrar:** a administração cadastra cada versão pelo nome e pela imagem com o resumo
  (``sha256:…``): a caixa só baixa a imagem pelo resumo, que o Docker confere.
- **Escolher:** para todas as caixas, para um site ou para uma caixa. Vence a escolha mais
  específica (a da caixa, depois a do site, depois a de todas); em cada alcance vale a última.
- **A ordem:** uma versão só vai para um site ou para todas depois de dar certo numa caixa.
- **As atualizações** são contadas pela caixa e aparecem na frota.

As funções gravam com ``flush``; o ``commit`` é de quem chama.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import AcessoAdmin
from nuvem.cadastro.modelos import Empresa, Site
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.frota.modelos import (
    AtualizacaoCaixa,
    CaixaBorda,
    EscolhaDeVersao,
    ResultadoDaAtualizacao,
    VersaoCaixa,
)
from nuvem.frota.servico import AcessoDaCaixa

FORMATO_DO_RESUMO = r"^sha256:[0-9a-f]{64}$"
FORMATO_DO_NOME = r"^[0-9A-Za-z][0-9A-Za-z._-]{0,49}$"
FORMATO_DA_IMAGEM = r"^[a-z0-9]([a-z0-9._/-]{0,198}[a-z0-9])?$"
"""O repositório, sem etiqueta nem resumo (ex.: ``ghcr.io/<conta>/patio-caixa``)."""

LIMITE_DAS_ATUALIZACOES = 20


class VersaoNaoProvadaError(Exception):
    """A versão ainda não deu certo numa caixa: só pode ir para uma caixa (409)."""


class RelatoDeAtualizacao(BaseModel):
    """O que a caixa conta de uma troca de versão (``POST /api/borda/atualizacoes``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    de: Annotated[str, Field(min_length=1, max_length=300)]
    """A imagem que rodava antes, como a caixa a tinha."""
    para: Annotated[str, Field(pattern=FORMATO_DO_RESUMO)]
    """O resumo da versão nova."""
    comecou_em: AwareDatetime
    terminou_em: AwareDatetime
    resultado: ResultadoDaAtualizacao
    motivo: Annotated[str, Field(max_length=500)]
    """Por que voltou ou falhou (vazio se deu certo)."""

    @model_validator(mode="after")
    def _termina_depois_de_comecar(self) -> "RelatoDeAtualizacao":
        if self.terminou_em < self.comecou_em:
            raise ValueError("terminou antes de começar")
        return self


@dataclass(frozen=True)
class VersaoNaListagem:
    """Uma versão, com em quantas caixas ela já deu certo."""

    versao: VersaoCaixa
    caixas_com_sucesso: int


def cadastrar_versao(
    sessao: Session,
    administracao: AcessoAdmin,
    *,
    nome: str,
    imagem: str,
    resumo: str,
    agora: datetime,
) -> VersaoCaixa:
    """Cadastra uma versão do agente.

    Raises:
        DadoInvalidoError: se o nome, a imagem ou o resumo estão fora do formato, ou se o nome ou
            o resumo já são de outra versão.
    """
    nome, imagem, resumo = nome.strip(), imagem.strip(), resumo.strip().lower()
    if not re.fullmatch(FORMATO_DO_NOME, nome):
        raise DadoInvalidoError("o nome tem só letras, números, ponto, hífen e sublinhado")
    if not re.fullmatch(FORMATO_DA_IMAGEM, imagem):
        raise DadoInvalidoError("a imagem é o repositório, sem etiqueta nem resumo")
    if not re.fullmatch(FORMATO_DO_RESUMO, resumo):
        raise DadoInvalidoError("o resumo é sha256: seguido de 64 letras e números")
    repetida = sessao.scalar(
        select(VersaoCaixa).where((VersaoCaixa.nome == nome) | (VersaoCaixa.resumo == resumo))
    )
    if repetida is not None:
        raise DadoInvalidoError(f"o nome ou o resumo já são da versão {repetida.nome}")
    versao = VersaoCaixa(
        nome=nome,
        imagem=imagem,
        resumo=resumo,
        cadastrada_em=agora,
        cadastrada_por=administracao.administrador_id,
    )
    sessao.add(versao)
    sessao.flush()
    return versao


def escolher_versao(
    sessao: Session,
    administracao: AcessoAdmin,
    versao_id: int,
    *,
    site_id: int | None = None,
    caixa_id: int | None = None,
    agora: datetime,
) -> EscolhaDeVersao:
    """Escolhe a versão para uma caixa, para um site ou (sem os dois) para todas as caixas.

    Raises:
        NaoEncontradoError: se a versão, o site ou a caixa não existirem.
        DadoInvalidoError: se vierem o site e a caixa juntos.
        VersaoNaoProvadaError: para um site ou para todas, se a versão ainda não deu certo numa
            caixa.
    """
    if site_id is not None and caixa_id is not None:
        raise DadoInvalidoError("escolha para um site ou para uma caixa, não os dois")
    versao = sessao.get(VersaoCaixa, versao_id)
    if versao is None:
        raise NaoEncontradoError(f"versão {versao_id}")
    empresa_id = None
    if caixa_id is not None:
        caixa = sessao.get(CaixaBorda, caixa_id)
        if caixa is None:
            raise NaoEncontradoError(f"caixa {caixa_id}")
        empresa_id = caixa.empresa_id
    else:
        if site_id is not None:
            empresa_id = cadastro.obter_site_para_administracao(sessao, site_id).empresa_id
        if not _deu_certo_numa_caixa(sessao, versao.id):
            raise VersaoNaoProvadaError
    escolha = EscolhaDeVersao(
        versao_id=versao.id,
        empresa_id=empresa_id,
        site_id=site_id,
        caixa_id=caixa_id,
        escolhida_em=agora,
        escolhida_por=administracao.administrador_id,
    )
    sessao.add(escolha)
    sessao.flush()
    return escolha


def versao_da_caixa(sessao: Session, caixa: AcessoDaCaixa) -> VersaoCaixa | None:
    """A versão que vale para a caixa (a da caixa, a do site ou a de todas), ou ``None``."""
    alcances = (
        (EscolhaDeVersao.empresa_id == caixa.empresa_id)
        & (EscolhaDeVersao.caixa_id == caixa.caixa_id),
        (EscolhaDeVersao.empresa_id == caixa.empresa_id)
        & (EscolhaDeVersao.site_id == caixa.site_id),
        EscolhaDeVersao.empresa_id.is_(None),
    )
    for alcance in alcances:
        escolha = sessao.scalars(
            select(EscolhaDeVersao)
            .where(alcance)
            .order_by(EscolhaDeVersao.escolhida_em.desc(), EscolhaDeVersao.id.desc())
            .limit(1)
        ).one_or_none()
        if escolha is not None:
            return sessao.get(VersaoCaixa, escolha.versao_id)
    return None


def registrar_atualizacao(
    sessao: Session, caixa: AcessoDaCaixa, relato: RelatoDeAtualizacao, *, agora: datetime
) -> AtualizacaoCaixa:
    """Grava a troca de versão que a caixa contou.

    Raises:
        DadoInvalidoError: se o resumo não é de uma versão cadastrada.
    """
    versao = sessao.scalar(select(VersaoCaixa).where(VersaoCaixa.resumo == relato.para))
    if versao is None:
        raise DadoInvalidoError(f"nenhuma versão com o resumo {relato.para}")
    atualizacao = AtualizacaoCaixa(
        empresa_id=caixa.empresa_id,
        caixa_id=caixa.caixa_id,
        de=relato.de,
        versao_id=versao.id,
        comecou_em=relato.comecou_em,
        terminou_em=relato.terminou_em,
        resultado=relato.resultado,
        motivo=relato.motivo,
        recebida_em=agora,
    )
    sessao.add(atualizacao)
    sessao.flush()
    return atualizacao


def listar_versoes(sessao: Session, _administracao: AcessoAdmin) -> list[VersaoNaListagem]:
    """As versões, das mais novas para as mais antigas, com as caixas em que deram certo."""
    com_sucesso = (
        select(
            AtualizacaoCaixa.versao_id,
            func.count(AtualizacaoCaixa.caixa_id.distinct()).label("caixas"),
        )
        .where(AtualizacaoCaixa.resultado == "ok")
        .group_by(AtualizacaoCaixa.versao_id)
        .subquery()
    )
    linhas = sessao.execute(
        select(VersaoCaixa, func.coalesce(com_sucesso.c.caixas, 0))
        .outerjoin(com_sucesso, com_sucesso.c.versao_id == VersaoCaixa.id)
        .order_by(VersaoCaixa.id.desc())
    ).all()
    return [VersaoNaListagem(versao, caixas) for versao, caixas in linhas]


def atualizacoes_da_caixa(
    sessao: Session, _administracao: AcessoAdmin, caixa_id: int
) -> list[tuple[AtualizacaoCaixa, VersaoCaixa]]:
    """As últimas atualizações da caixa, das mais novas para as mais antigas, com a versão."""
    return [
        (atualizacao, versao)
        for atualizacao, versao in sessao.execute(
            select(AtualizacaoCaixa, VersaoCaixa)
            .join(VersaoCaixa, VersaoCaixa.id == AtualizacaoCaixa.versao_id)
            .where(AtualizacaoCaixa.caixa_id == caixa_id)
            .order_by(AtualizacaoCaixa.recebida_em.desc(), AtualizacaoCaixa.id.desc())
            .limit(LIMITE_DAS_ATUALIZACOES)
        ).all()
    ]


@dataclass(frozen=True)
class Alcances:
    """Para quem a administração pode escolher uma versão: os sites e as caixas no ar."""

    sites: list[tuple[int, str]]
    """(id, "empresa · site"), dos sites com caixa."""
    caixas: list[tuple[int, str]]
    """(id, "caixa N · site")."""


def alcances(sessao: Session, _administracao: AcessoAdmin) -> Alcances:
    """Os sites com caixa não revogada e as caixas não revogadas, para o formulário da escolha."""
    linhas = sessao.execute(
        select(CaixaBorda.id, Site.id, Site.nome, Empresa.nome)
        .join(Site, (Site.id == CaixaBorda.site_id) & (Site.empresa_id == CaixaBorda.empresa_id))
        .join(Empresa, Empresa.id == CaixaBorda.empresa_id)
        .where(CaixaBorda.revogada_em.is_(None))
        .order_by(Empresa.nome, Site.nome, CaixaBorda.id)
    ).all()
    sites = list(
        dict.fromkeys((site_id, f"{empresa} · {site}") for _, site_id, site, empresa in linhas)
    )
    caixas = [(caixa_id, f"caixa {caixa_id} · {site}") for caixa_id, _, site, _ in linhas]
    return Alcances(sites=sites, caixas=caixas)


def _deu_certo_numa_caixa(sessao: Session, versao_id: int) -> bool:
    return (
        sessao.scalar(
            select(AtualizacaoCaixa.id)
            .where(AtualizacaoCaixa.versao_id == versao_id, AtualizacaoCaixa.resultado == "ok")
            .limit(1)
        )
        is not None
    )

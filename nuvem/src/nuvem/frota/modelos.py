"""Tabelas da frota: os códigos de ativação, as caixas de borda, a saúde e as versões delas (SDD
5.1 e 7.4).

As de dados do cliente têm ``empresa_id`` e apontam para o pai pela dupla (pai, empresa), como
toda tabela filha (SDD 5.5). As versões são da plataforma (D-67).
"""

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base, do_pai_na_mesma_empresa, pode_ser_pai, texto_de_lista


class CodigoAtivacao(Base):
    """Um código de uso único que a administração gera para ativar uma caixa num site."""

    __tablename__ = "codigo_ativacao"
    __table_args__ = (do_pai_na_mesma_empresa("site"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    codigo_resumo: Mapped[str] = mapped_column(String(64), unique=True)
    """SHA-256 do código, sem os hífens (o código em si só aparece uma vez, para quem gerou)."""
    criado_por: Mapped[int] = mapped_column(ForeignKey("administrador.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Quando uma caixa usou o código; usado não vale de novo."""


class CaixaBorda(Base):
    """Uma caixa de borda (mini PC na portaria) ativada num site."""

    __tablename__ = "caixa_borda"
    __table_args__ = (pode_ser_pai(), do_pai_na_mesma_empresa("site"))

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    chave_resumo: Mapped[str] = mapped_column(String(64), unique=True)
    """SHA-256 da chave da caixa (a chave só existe na própria caixa)."""
    ativada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Quando a chave deixou de valer (caixa perdida, trocada ou desligada)."""
    ultimo_contato: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Quando chegou a última saúde, no relógio da nuvem; vazio se nunca chegou (D-65)."""
    versao_programa: Mapped[str | None] = mapped_column(String(100))
    versao_leitor: Mapped[str | None] = mapped_column(String(100))
    ultima_saude: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    """A última saúde, como chegou (o formato ``contratos.saude.Saude``)."""
    diferenca_do_relogio: Mapped[float | None] = mapped_column(Float)
    """Segundos: a hora da caixa menos a da nuvem, na última saúde (positivo = adiantada)."""


class SaudeCaixa(Base):
    """Uma saúde recebida de uma caixa: o histórico curto, de 7 dias (D-65).

    Os números que a frota resume hora a hora ficam em colunas; a saúde inteira, em ``dados``.
    """

    __tablename__ = "saude_caixa"
    __table_args__ = (
        do_pai_na_mesma_empresa("caixa_borda", "caixa_id"),
        Index("ix_saude_caixa_caixa_id_recebida_em", "caixa_id", "recebida_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    caixa_id: Mapped[int]
    recebida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """A hora da caixa."""
    diferenca_do_relogio: Mapped[float] = mapped_column(Float)
    cpu: Mapped[float] = mapped_column(Float)
    temperatura: Mapped[float | None] = mapped_column(Float)
    memoria: Mapped[float] = mapped_column(Float)
    disco: Mapped[float] = mapped_column(Float)
    cameras_no_ar: Mapped[int]
    cameras: Mapped[int]
    """As câmeras de placa abertas pela caixa."""
    passagens_na_fila: Mapped[int]
    dados: Mapped[dict[str, Any]] = mapped_column(JSONB)


ResultadoDaAtualizacao = Literal["ok", "voltou", "falhou"]
"""Deu certo, voltou para a versão anterior (a saúde não veio) ou falhou antes de trocar."""


class VersaoCaixa(Base):
    """Uma versão do agente da caixa, pela imagem e pelo resumo dela (D-67).

    Da plataforma, como a administração: não é de nenhuma empresa.
    """

    __tablename__ = "versao_caixa"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(50), unique=True)
    """O nome que aparece na frota e que o agente conta na saúde (ex.: ``0.2.0``)."""
    imagem: Mapped[str] = mapped_column(String(200))
    """O repositório da imagem, sem etiqueta (ex.: ``ghcr.io/<conta>/patio-caixa``)."""
    resumo: Mapped[str] = mapped_column(String(71), unique=True)
    """O resumo da imagem (``sha256:<64 letras>``): o Docker confere ao baixar."""
    cadastrada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cadastrada_por: Mapped[int] = mapped_column(ForeignKey("administrador.id"))

    @property
    def referencia(self) -> str:
        """A imagem pelo resumo, como a caixa a baixa."""
        return f"{self.imagem}@{self.resumo}"


class EscolhaDeVersao(Base):
    """A versão escolhida para todas as caixas, para um site ou para uma caixa (D-67).

    Só se acrescenta (o gatilho ``so_acrescenta``): em cada alcance vale a última.
    """

    __tablename__ = "escolha_de_versao"
    __table_args__ = (
        do_pai_na_mesma_empresa("site"),
        do_pai_na_mesma_empresa("caixa_borda", "caixa_id"),
        CheckConstraint(
            "(site_id IS NULL OR caixa_id IS NULL)"
            " AND ((site_id IS NULL AND caixa_id IS NULL) = (empresa_id IS NULL))",
            name="um_alcance",
        ),
        Index("ix_escolha_de_versao_alcance", "caixa_id", "site_id", "escolhida_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    versao_id: Mapped[int] = mapped_column(ForeignKey("versao_caixa.id"))
    empresa_id: Mapped[int | None]
    """Vazia na escolha para todas as caixas."""
    site_id: Mapped[int | None]
    caixa_id: Mapped[int | None]
    escolhida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    escolhida_por: Mapped[int] = mapped_column(ForeignKey("administrador.id"))


class AtualizacaoCaixa(Base):
    """Uma troca de versão, como a caixa contou (D-67). Só se acrescenta."""

    __tablename__ = "atualizacao_caixa"
    __table_args__ = (
        do_pai_na_mesma_empresa("caixa_borda", "caixa_id"),
        CheckConstraint("terminou_em >= comecou_em", name="termina_depois"),
        Index("ix_atualizacao_caixa_caixa_id_recebida_em", "caixa_id", "recebida_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    caixa_id: Mapped[int]
    de: Mapped[str] = mapped_column(String(300))
    """A imagem que rodava antes (como a caixa a tinha)."""
    versao_id: Mapped[int] = mapped_column(ForeignKey("versao_caixa.id"))
    """Para qual versão."""
    comecou_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    terminou_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resultado: Mapped[ResultadoDaAtualizacao] = mapped_column(
        texto_de_lista(ResultadoDaAtualizacao, "resultado_da_atualizacao")
    )
    motivo: Mapped[str] = mapped_column(String(500))
    recebida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))

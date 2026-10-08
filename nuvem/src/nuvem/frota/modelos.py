"""Tabelas da frota: os códigos de ativação, as caixas de borda e a saúde delas (SDD 5.1 e 7.4).

As três são dados do cliente: têm ``empresa_id`` e apontam para o pai pela dupla (pai,
empresa), como toda tabela filha (SDD 5.5).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base, do_pai_na_mesma_empresa, pode_ser_pai


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

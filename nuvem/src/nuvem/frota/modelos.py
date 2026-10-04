"""Tabelas da frota: os códigos de ativação e as caixas de borda (SDD 5.1 e 7.4).

As duas são dados do cliente: têm ``empresa_id`` e apontam para o site pela dupla (site,
empresa), como toda tabela filha (SDD 5.5).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
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

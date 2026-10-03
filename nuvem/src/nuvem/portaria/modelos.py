"""Tabela das passagens recebidas da borda (SDD 3.2 e 5.1).

A passagem é prova da chegada (SDD 5.5): fica guardada exatamente como veio (``como_veio``),
e não se edita. As colunas ao lado repetem o que as consultas usam (site, faixa, horários).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base, do_pai_na_mesma_empresa, texto_de_lista
from nuvem.cadastro.modelos import Sentido


class PassagemRecebida(Base):
    """Uma passagem que uma caixa de borda mandou."""

    __tablename__ = "passagem"
    __table_args__ = (
        do_pai_na_mesma_empresa("site"),
        do_pai_na_mesma_empresa("faixa"),
        do_pai_na_mesma_empresa("caixa_borda", coluna="caixa_id"),
        # A tela da portaria lista as últimas passagens de um site.
        Index("ix_passagem_site_id_inicio", "site_id", "inicio"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    """O id que a caixa gerou: o mesmo id de novo é a mesma passagem (reenvio seguro)."""
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    caixa_id: Mapped[int]
    faixa_id: Mapped[int]
    sentido: Mapped[Sentido] = mapped_column(texto_de_lista(Sentido, "sentido"))
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """Quando o veículo começou a passar, no relógio da caixa."""
    fim: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recebida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """Quando a nuvem recebeu (pode ser bem depois do ``inicio``, se a internet caiu)."""
    como_veio: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """A passagem inteira, no formato do contrato (``contratos.Passagem``)."""

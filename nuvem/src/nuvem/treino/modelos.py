"""Tabelas da base de treino (SDD 5.1, D-71).

O rótulo não é prova: ele se apaga quando a empresa revoga a autorização do treino.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base, do_pai_na_mesma_empresa, texto_de_lista

SituacaoDoRotulo = Literal["a_revisar", "aceito", "corrigido", "descartado"]
OrigemDoRotulo = Literal["conferencia", "rotulagem"]
"""A conferência do porteiro ou a rotulagem no Label Studio (``[ABERTO-18]``)."""
ConjuntoDoRotulo = Literal["treino", "regua"]


class AutorizacaoDeTreino(Base):
    """A cláusula do contrato que autoriza o uso das conferências da empresa no treino."""

    __tablename__ = "autorizacao_de_treino"
    __table_args__ = (
        # Uma ativa por empresa.
        Index(
            "uq_autorizacao_de_treino_ativa",
            "empresa_id",
            unique=True,
            postgresql_where=text("revogada_em IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"))
    clausula_em: Mapped[date] = mapped_column(Date)
    """A data da cláusula: só as conferências desde ela viram rótulo."""
    registrada_por: Mapped[int] = mapped_column(ForeignKey("administrador.id"))
    registrada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Rotulo(Base):
    """Um recorte de placa com a placa certa, para o treino ou para a régua."""

    __tablename__ = "rotulo"
    __table_args__ = (
        do_pai_na_mesma_empresa("passagem"),
        CheckConstraint("foto >= 0", name="foto_positiva"),
        UniqueConstraint("passagem_id", "foto"),
        Index("ix_rotulo_situacao", "situacao"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    passagem_id: Mapped[UUID]
    foto: Mapped[int]
    """O recorte: a posição dele nas fotos da passagem."""
    placa: Mapped[str] = mapped_column(String(7))
    origem: Mapped[OrigemDoRotulo] = mapped_column(
        texto_de_lista(OrigemDoRotulo, "origem_do_rotulo")
    )
    situacao: Mapped[SituacaoDoRotulo] = mapped_column(
        texto_de_lista(SituacaoDoRotulo, "situacao_do_rotulo")
    )
    conjunto: Mapped[ConjuntoDoRotulo] = mapped_column(
        texto_de_lista(ConjuntoDoRotulo, "conjunto_do_rotulo")
    )
    """Treino ou régua: sorteado ao nascer, pelo resumo, e não muda."""
    recorte: Mapped[str | None] = mapped_column(String(200))
    """Onde a cópia do recorte está na base de treino (vazio: a foto já tinha saído)."""
    resumo: Mapped[str | None] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revisado_por: Mapped[int | None] = mapped_column(ForeignKey("administrador.id"))
    revisado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

"""Tabelas da guarda (SDD 5.1 e 8.3, D-70).

A foto apagada e a marca de disputa só se acrescentam: um gatilho no banco recusa alterar ou
apagar (migração 0025), como nos eventos da visita.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base, do_pai_na_mesma_empresa, texto_de_lista

MotivoDaFotoApagada = Literal["prazo_de_guarda"]
AcaoDaDisputa = Literal["marcar", "desmarcar"]


class FotoApagada(Base):
    """Uma foto da passagem que saiu do armazenamento pelo prazo de guarda.

    O resumo dela continua na ``FotoRecebida``; esta diz quando e por quê. ``existia`` diz se o
    arquivo estava lá (a foto que a caixa não conseguiu mandar nunca chegou).
    """

    __tablename__ = "foto_apagada"
    __table_args__ = (
        do_pai_na_mesma_empresa("passagem"),
        UniqueConstraint("passagem_id", "indice"),
        CheckConstraint("indice >= 0", name="indice_positivo"),
        Index("ix_foto_apagada_apagada_em", "apagada_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    passagem_id: Mapped[UUID]
    indice: Mapped[int]
    ref: Mapped[str] = mapped_column(String(200))
    existia: Mapped[bool]
    motivo: Mapped[MotivoDaFotoApagada] = mapped_column(
        texto_de_lista(MotivoDaFotoApagada, "motivo_da_foto_apagada")
    )
    apagada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarcaDeDisputa(Base):
    """O gestor marca ou desmarca a visita "em disputa"; vale a última marca."""

    __tablename__ = "marca_de_disputa"
    __table_args__ = (
        do_pai_na_mesma_empresa("visita"),
        do_pai_na_mesma_empresa("usuario"),
        Index("ix_marca_de_disputa_visita_id", "visita_id"),
        Index("ix_marca_de_disputa_momento", "momento"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    visita_id: Mapped[int]
    acao: Mapped[AcaoDaDisputa] = mapped_column(texto_de_lista(AcaoDaDisputa, "acao_da_disputa"))
    motivo: Mapped[str] = mapped_column(String(300))
    usuario_id: Mapped[int]
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True))

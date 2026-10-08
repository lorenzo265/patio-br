"""Tabelas da prova (SDD 5.1 e 5.5, D-69).

A foto resumida e o elo só se acrescentam: um gatilho no banco recusa alterar ou apagar
(migração 0024), como nos eventos da visita. A âncora do dia é da plataforma, uma por dia; o
arquivo dela é que fica travado, fora do banco.
"""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base, do_pai_na_mesma_empresa, texto_de_lista

TipoDeElo = Literal[
    "passagem", "foto", "evento", "conferencia", "mensagem", "disputa", "foto_apagada"
]


class FotoRecebida(Base):
    """O resumo de uma foto da passagem, feito pela nuvem logo que a passagem chegou."""

    __tablename__ = "foto_recebida"
    __table_args__ = (
        do_pai_na_mesma_empresa("passagem"),
        UniqueConstraint("passagem_id", "indice"),
        CheckConstraint("indice >= 0", name="indice_positivo"),
        Index("ix_foto_recebida_resumida_em", "resumida_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    passagem_id: Mapped[UUID]
    indice: Mapped[int]
    """A posição da foto nas fotos da passagem."""
    ref: Mapped[str] = mapped_column(String(200))
    resumo: Mapped[str] = mapped_column(String(64))
    """O SHA-256 da foto, em hexadecimal."""
    tamanho: Mapped[int]
    resumida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EloDaProva(Base):
    """Um elo da cadeia de uma visita: o retrato de um registro e o resumo (``prova.cadeia``)."""

    __tablename__ = "elo_da_prova"
    __table_args__ = (
        do_pai_na_mesma_empresa("visita"),
        UniqueConstraint("visita_id", "ordem"),
        UniqueConstraint("visita_id", "tipo", "referencia"),
        CheckConstraint("ordem >= 1", name="ordem_positiva"),
        Index("ix_elo_da_prova_selado_em", "selado_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    visita_id: Mapped[int]
    ordem: Mapped[int]
    tipo: Mapped[TipoDeElo] = mapped_column(texto_de_lista(TipoDeElo, "tipo_de_elo"))
    referencia: Mapped[str] = mapped_column(String(100))
    """Sobre o quê: o id do registro (na mensagem, ``<id>:<situação>``)."""
    conteudo: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """O retrato do registro quando foi selado."""
    anterior: Mapped[str] = mapped_column(String(64))
    resumo: Mapped[str] = mapped_column(String(64))
    selado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AncoraDoDia(Base):
    """A âncora de um dia (UTC): o último resumo de cada visita que mudou, num arquivo travado."""

    __tablename__ = "ancora_do_dia"

    id: Mapped[int] = mapped_column(primary_key=True)
    dia: Mapped[date] = mapped_column(Date, unique=True)
    arquivo: Mapped[str] = mapped_column(String(200))
    resumo: Mapped[str] = mapped_column(String(64))
    """O SHA-256 do arquivo, para conferir que ele é o mesmo."""
    visitas: Mapped[int]
    travada: Mapped[bool]
    gravada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))

"""As cópias do banco e as restaurações de teste (D-74): da plataforma, fora das empresas."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base


class CopiaDoBanco(Base):
    """Uma cópia do banco no balde das cópias, com o que ela precisa ter (o manifesto)."""

    __tablename__ = "copia_do_banco"
    __table_args__ = (Index("ix_copia_do_banco_feita_em", "feita_em"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), unique=True)
    """O nome do arquivo no balde (ex.: ``copia-20261006-060000.dump``)."""
    feita_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tamanho: Mapped[int] = mapped_column(BigInteger)
    resumo: Mapped[str] = mapped_column(String(64))
    """O SHA-256 do arquivo, em hexadecimal."""
    migracao: Mapped[str] = mapped_column(String(32))
    """A migração do banco quando a cópia começou."""
    contagens: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """Quantas linhas cada tabela só de acréscimo tinha antes de a cópia começar."""
    ultimo_evento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """O ``registrado_em`` do último evento antes de a cópia começar."""
    apagada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RestauracaoDeTeste(Base):
    """Uma volta de cópia num banco temporário, para conferir que ela serve."""

    __tablename__ = "restauracao_de_teste"
    __table_args__ = (Index("ix_restauracao_de_teste_feita_em", "feita_em"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    copia_id: Mapped[int] = mapped_column(ForeignKey("copia_do_banco.id"))
    feita_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ok: Mapped[bool]
    detalhe: Mapped[str | None] = mapped_column(Text)
    """O que não conferiu (uma linha por problema)."""

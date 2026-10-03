"""Conexão com o PostgreSQL (SQLAlchemy 2, driver pg8000) e a base dos modelos da nuvem."""

from collections.abc import Iterator
from typing import get_args

from fastapi import Request
from sqlalchemy import (
    Engine,
    Enum,
    ForeignKeyConstraint,
    MetaData,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

CONVENCAO_DE_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
"""Nomes previsíveis para índices e restrições: as migrações conseguem achá-los depois."""


class Base(DeclarativeBase):
    """Base de todas as tabelas da nuvem; as migrações (Alembic) partem deste metadata."""

    metadata = MetaData(naming_convention=CONVENCAO_DE_NOMES)


def texto_de_lista(valores: object, nome: str) -> Enum:
    """Coluna de texto que só aceita os valores de um ``Literal`` (ex.: ``Sentido``).

    Guardada como texto com um CHECK (e não como tipo ENUM do PostgreSQL): mais fácil de migrar.
    """
    return Enum(*get_args(valores), name=nome, native_enum=False, create_constraint=True)


def do_pai_na_mesma_empresa(pai: str, coluna: str | None = None) -> ForeignKeyConstraint:
    """Chave estrangeira composta (pai, empresa) de uma tabela filha de cliente (SDD 5.5).

    A tabela filha precisa das colunas ``<pai>_id`` (ou ``coluna``) e ``empresa_id``; o banco
    recusa um filho de uma empresa num pai de outra.
    """
    return ForeignKeyConstraint(
        [coluna or f"{pai}_id", "empresa_id"], [f"{pai}.id", f"{pai}.empresa_id"]
    )


def pode_ser_pai() -> UniqueConstraint:
    """A dupla (id, empresa) única, que a chave estrangeira composta dos filhos exige no pai."""
    return UniqueConstraint("id", "empresa_id")


SQLSTATE_CHAVE_ESTRANGEIRA = "23503"
SQLSTATE_CHECK = "23514"
SQLSTATE_UNICIDADE = "23505"


def sqlstate(erro: DBAPIError) -> str | None:
    """Devolve o código SQLSTATE do PostgreSQL que causou o erro (ex.: ``"23503"``).

    Com o pg8000, só a violação de unicidade chega como ``IntegrityError``; chave estrangeira e
    CHECK chegam como ``ProgrammingError``. Para saber o que o banco recusou, use o código.
    """
    argumentos = getattr(erro.orig, "args", ())
    detalhes = argumentos[0] if argumentos else None
    codigo = detalhes.get("C") if isinstance(detalhes, dict) else None
    return codigo if isinstance(codigo, str) else None


def criar_motor(url: str) -> Engine:
    """Cria o motor de conexões; ``pool_pre_ping`` descarta conexões que o banco já fechou."""
    return create_engine(url, pool_pre_ping=True)


def obter_sessao(request: Request) -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão por requisição, fechada ao final dela."""
    sessoes: sessionmaker[Session] = request.app.state.sessoes
    with sessoes() as sessao:
        yield sessao

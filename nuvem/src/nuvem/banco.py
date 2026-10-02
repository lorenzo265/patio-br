"""Conexão com o PostgreSQL (SQLAlchemy 2, driver pg8000) e a base dos modelos da nuvem."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

CONVENCAO_DE_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
"""Nomes previsíveis para índices e restrições: as migrações conseguem achá-los depois."""


class Base(DeclarativeBase):
    """Base de todas as tabelas da nuvem; as migrações (Alembic) partem deste metadata."""

    metadata = MetaData(naming_convention=CONVENCAO_DE_NOMES)


def criar_motor(url: str) -> Engine:
    """Cria o motor de conexões; ``pool_pre_ping`` descarta conexões que o banco já fechou."""
    return create_engine(url, pool_pre_ping=True)


def obter_sessao(request: Request) -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão por requisição, fechada ao final dela."""
    sessoes: sessionmaker[Session] = request.app.state.sessoes
    with sessoes() as sessao:
        yield sessao

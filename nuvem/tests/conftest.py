"""O banco de teste da nuvem: o `postgres-teste` do `uv run tarefas up` (porta 5433).

No início da rodada, o banco é zerado e migrado do zero (assim toda rodada testa também as
migrações). Cada teste roda dentro de uma transação que é desfeita no fim, mesmo que o código
testado faça commit: nada que um teste grava sobra para o próximo.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nuvem.cadastro.acesso import Acesso, acesso_do_usuario
from nuvem.cifra import Cifra
from nuvem.semente import Demonstracao, semear

ARQUIVO_ALEMBIC = Path(__file__).resolve().parents[1] / "alembic.ini"
SUFIXO_DO_BANCO_DE_TESTE = "_teste"


class ConfiguracaoDosTestes(BaseSettings):
    """Onde está o banco de teste; muda pela variável PATIO_URL_BANCO_TESTE ou pelo .env."""

    model_config = SettingsConfigDict(env_prefix="PATIO_", env_file=".env", extra="ignore")

    url_banco_teste: str = "postgresql+pg8000://patio:patio-local@localhost:5433/patio_teste"


@pytest.fixture(scope="session")
def url_banco_teste() -> Iterator[str]:
    """Zera e migra o banco de teste uma vez por rodada; devolve a URL dele."""
    url = ConfiguracaoDosTestes().url_banco_teste
    endereco = make_url(url)
    # Trava de segurança: zerar o banco de desenvolvimento por engano apagaria tudo.
    if not (endereco.database or "").endswith(SUFIXO_DO_BANCO_DE_TESTE):
        pytest.fail(f"o nome do banco de teste precisa terminar em _teste: {endereco}")
    motor = create_engine(url)
    try:
        with motor.begin() as conexao:
            conexao.execute(text("drop schema public cascade"))
            conexao.execute(text("create schema public"))
            alembic = Config(ARQUIVO_ALEMBIC)
            alembic.attributes["connection"] = conexao
            command.upgrade(alembic, "head")
    except DBAPIError as erro:
        pytest.fail(
            f"banco de teste fora do ar ({endereco}): rode `uv run tarefas up` ({erro.orig})"
        )
    finally:
        motor.dispose()
    yield url


@pytest.fixture
def sessao(url_banco_teste: str) -> Iterator[Session]:
    """Sessão ligada a uma transação que é desfeita no fim do teste."""
    motor = create_engine(url_banco_teste)
    with motor.connect() as conexao:
        transacao = conexao.begin()
        # create_savepoint: o commit do código testado só fecha um savepoint, não a transação.
        with Session(bind=conexao, join_transaction_mode="create_savepoint") as sessao:
            yield sessao
        transacao.rollback()
    motor.dispose()


@pytest.fixture
def cifra() -> Cifra:
    """Cifra com uma chave nova a cada teste (nunca a do ambiente)."""
    return Cifra(SecretStr(Fernet.generate_key().decode()))


@pytest.fixture
def cenario(sessao: Session, cifra: Cifra) -> Demonstracao:
    """Os dados de demonstração (duas empresas), gravados no banco de teste vazio."""
    demonstracao = semear(sessao, cifra)
    assert demonstracao is not None, "o banco de teste deveria começar vazio"
    return demonstracao


@pytest.fixture
def acesso_a(sessao: Session, cenario: Demonstracao) -> Acesso:
    """O gestor da empresa A, ligado só ao site_a."""
    return acesso_do_usuario(sessao, cenario.gestor_a.id)


@pytest.fixture
def acesso_b(sessao: Session, cenario: Demonstracao) -> Acesso:
    """O gestor da empresa B."""
    return acesso_do_usuario(sessao, cenario.gestor_b.id)

"""O banco de teste da nuvem: o `postgres-teste` do `uv run tarefas up` (porta 15433).

No início da rodada, o banco é zerado e migrado do zero (assim toda rodada testa também as
migrações). Cada teste roda dentro de uma transação que é desfeita no fim, mesmo que o código
testado faça commit: nada que um teste grava sobra para o próximo.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Connection, create_engine, make_url, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro.acesso import Acesso, acesso_do_usuario
from nuvem.cifra import Cifra, obter_cifra
from nuvem.config import Configuracao
from nuvem.principal import criar_app
from nuvem.semente import SENHA_DA_DEMONSTRACAO, Demonstracao, semear
from nuvem.senhas import Senhas

ARQUIVO_ALEMBIC = Path(__file__).resolve().parents[1] / "alembic.ini"
SUFIXO_DO_BANCO_DE_TESTE = "_teste"
CHAVE_QUALQUER = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="
"""Chave da cifra da aplicação nos testes de rota (os testes da cifra usam uma nova a cada vez)."""


class ConfiguracaoDosTestes(BaseSettings):
    """Onde está o banco de teste; muda pela variável PATIO_URL_BANCO_TESTE ou pelo .env."""

    model_config = SettingsConfigDict(env_prefix="PATIO_", env_file=".env", extra="ignore")

    url_banco_teste: str = "postgresql+pg8000://patio:patio-local@localhost:15433/patio_teste"


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
def conexao(url_banco_teste: str) -> Iterator[Connection]:
    """Conexão com uma transação aberta, desfeita no fim do teste."""
    motor = create_engine(url_banco_teste)
    with motor.connect() as conexao:
        transacao = conexao.begin()
        yield conexao
        transacao.rollback()
    motor.dispose()


def _sessao_na(conexao: Connection) -> Session:
    # create_savepoint: o commit do código testado só fecha um savepoint, não a transação.
    return Session(bind=conexao, join_transaction_mode="create_savepoint")


@pytest.fixture
def sessao(conexao: Connection) -> Iterator[Session]:
    """Sessão dentro da transação do teste: nada do que ela grava sobra para o próximo."""
    with _sessao_na(conexao) as sessao:
        yield sessao


@pytest.fixture
def cifra() -> Cifra:
    """Cifra com uma chave nova a cada teste (nunca a do ambiente)."""
    return Cifra(SecretStr(Fernet.generate_key().decode()))


@pytest.fixture(scope="session")
def senhas() -> Senhas:
    """Argon2 com o menor custo possível: nos testes, o resumo não precisa ser lento."""
    return Senhas(PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))


@pytest.fixture
def cenario(sessao: Session, cifra: Cifra, senhas: Senhas) -> Demonstracao:
    """Os dados de demonstração (duas empresas), gravados no banco de teste vazio."""
    demonstracao = semear(sessao, cifra, senhas)
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


@pytest.fixture
def app(url_banco_teste: str, conexao: Connection, senhas: Senhas, cifra: Cifra) -> FastAPI:
    """A aplicação no ambiente local, dentro da transação do teste (desfeita no fim).

    Cada requisição ganha a própria sessão, como em produção: o que a rota grava sem
    ``commit`` se perde no fim da requisição.
    """
    configuracao = Configuracao(
        url_banco=url_banco_teste, chave_cifra=CHAVE_QUALQUER, ambiente="local", _env_file=None
    )
    app = criar_app(configuracao, senhas=senhas)

    def sessao_da_requisicao() -> Iterator[Session]:
        with _sessao_na(conexao) as sessao:
            yield sessao

    app.dependency_overrides[obter_sessao] = sessao_da_requisicao
    # A mesma cifra da semente do teste: as senhas das câmeras abrem.
    app.dependency_overrides[obter_cifra] = lambda: cifra
    return app


@pytest.fixture
def entrar(app: FastAPI) -> Callable[..., TestClient]:
    """Entra pela tela de login, como alguém de verdade, e devolve o navegador com o cookie."""

    def _entrar(email: str, senha: str = SENHA_DA_DEMONSTRACAO) -> TestClient:
        cliente = TestClient(app)
        resposta = cliente.post(
            "/entrar", data={"email": email, "senha": senha}, follow_redirects=False
        )
        assert resposta.status_code == 303, resposta.text
        return cliente

    return _entrar

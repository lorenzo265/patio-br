"""Ambiente do Alembic: aplica as migrações da nuvem no banco configurado.

Pela linha de comando (``uv run tarefas migrar``), o banco é o de ``PATIO_URL_BANCO``. Os testes
passam a própria conexão em ``config.attributes["connection"]`` (ver ``nuvem/tests/conftest.py``).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

from nuvem.banco import Base, criar_motor
from nuvem.config import ConfiguracaoInvalidaError, ler_configuracao


def _aplicar(conexao: Connection) -> None:
    context.configure(connection=conexao, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("as migrações da nuvem rodam conectadas ao banco; a opção --sql não é usada")

conexao_dos_testes = context.config.attributes.get("connection")
if conexao_dos_testes is not None:
    _aplicar(conexao_dos_testes)
else:
    if context.config.config_file_name is not None:
        fileConfig(context.config.config_file_name, disable_existing_loggers=False)
    try:
        configuracao = ler_configuracao()
    except ConfiguracaoInvalidaError as erro:
        raise SystemExit(f"erro: {erro}") from None
    motor = criar_motor(configuracao.url_banco.get_secret_value())
    with motor.connect() as conexao:
        _aplicar(conexao)
    motor.dispose()

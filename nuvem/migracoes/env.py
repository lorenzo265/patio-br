"""Ambiente do Alembic: aplica as migrações da nuvem no banco configurado.

Pela linha de comando (``uv run tarefas migrar``), o banco é o de ``PATIO_URL_BANCO``. Os testes
passam a própria conexão em ``config.attributes["connection"]`` (ver ``nuvem/tests/conftest.py``).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

from nuvem import tarefas_de_fundo as _fila  # noqa: F401
from nuvem.agendamento import modelos as _modelos_do_agendamento  # noqa: F401
from nuvem.alertas import modelos as _modelos_dos_alertas  # noqa: F401
from nuvem.banco import Base, motor_da_configuracao
from nuvem.cadastro import modelos as _modelos_do_cadastro  # noqa: F401  (registra as tabelas)
from nuvem.config import ConfiguracaoInvalidaError, ler_configuracao
from nuvem.demonstracao import modelos as _modelos_da_demonstracao  # noqa: F401
from nuvem.extrato import modelos as _modelos_do_extrato  # noqa: F401
from nuvem.frota import modelos as _modelos_da_frota  # noqa: F401
from nuvem.mensagens import modelos as _modelos_das_mensagens  # noqa: F401
from nuvem.portaria import modelos as _modelos_da_portaria  # noqa: F401
from nuvem.prova import modelos as _modelos_da_prova  # noqa: F401


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
    motor = motor_da_configuracao(configuracao)
    with motor.connect() as conexao:
        _aplicar(conexao)
    motor.dispose()

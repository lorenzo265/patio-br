"""A exportação da base de treino pela linha de comando (``uv run tarefas treino``, D-71)."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.orm import Session

from nuvem.banco import motor_da_configuracao
from nuvem.config import Configuracao, ConfiguracaoInvalidaError, ler_configuracao
from nuvem.treino import servico as treino
from nuvem.treino.guarda import guarda_do_treino_da_configuracao
from nuvem.treino.servico import Exportacao

DESTINO_PADRAO = Path("dados/treino")
"""Dentro de ``dados/``, que o Git ignora: os recortes são de placas reais."""


def exportar_da_configuracao(configuracao: Configuracao, destino: Path) -> Exportacao:
    """Monta a pasta com o banco e o armazenamento da configuração."""
    motor = motor_da_configuracao(configuracao)
    try:
        with Session(motor) as sessao:
            return treino.exportar(sessao, guarda_do_treino_da_configuracao(configuracao), destino)
    finally:
        motor.dispose()


def principal(argv: Sequence[str] | None = None) -> None:
    """Lê os argumentos e a configuração, monta a pasta e diz quantos recortes foram."""
    interpretador = argparse.ArgumentParser(prog="python -m nuvem.treino", description=__doc__)
    interpretador.add_argument("--destino", type=Path, default=DESTINO_PADRAO)
    argumentos = interpretador.parse_args(argv)
    try:
        configuracao = ler_configuracao()
    except ConfiguracaoInvalidaError as erro:
        raise SystemExit(f"erro: {erro}") from None
    feita = exportar_da_configuracao(configuracao, argumentos.destino)
    print(
        f"base de treino em {argumentos.destino}: {feita.treino} no treino, {feita.regua} na régua"
    )

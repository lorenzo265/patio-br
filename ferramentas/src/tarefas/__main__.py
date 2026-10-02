"""Permite rodar também como ``python -m tarefas``."""

import sys

from tarefas.comandos import principal

sys.exit(principal())

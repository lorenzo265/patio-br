"""O pacote tarefas é instalado pelo workspace do projeto."""

import importlib


def test_pacote_tarefas_e_importavel() -> None:
    modulo = importlib.import_module("tarefas")

    assert modulo.__doc__

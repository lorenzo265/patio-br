"""O pacote contratos é instalado pelo workspace do projeto."""

import importlib


def test_pacote_contratos_e_importavel() -> None:
    modulo = importlib.import_module("contratos")

    assert modulo.__doc__

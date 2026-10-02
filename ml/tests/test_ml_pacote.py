"""O pacote ml é instalado pelo workspace do projeto."""

import importlib


def test_pacote_ml_e_importavel() -> None:
    modulo = importlib.import_module("ml")

    assert modulo.__doc__

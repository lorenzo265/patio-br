"""O pacote borda usa o mesmo contrato de passagem que o resto do sistema (SDD 3.2)."""

import importlib
from importlib.metadata import requires


def test_pacote_borda_e_importavel() -> None:
    modulo = importlib.import_module("borda")

    assert modulo.__doc__


def test_borda_depende_do_pacote_de_contratos() -> None:
    dependencias = requires("patio-borda") or []

    assert "patio-contratos" in dependencias

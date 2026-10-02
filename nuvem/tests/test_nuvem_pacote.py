"""O pacote nuvem usa o mesmo contrato de passagem que o resto do sistema (SDD 3.2)."""

import importlib
from importlib.metadata import requires


def test_pacote_nuvem_e_importavel() -> None:
    modulo = importlib.import_module("nuvem")

    assert modulo.__doc__


def test_nuvem_depende_do_pacote_de_contratos() -> None:
    dependencias = requires("patio-nuvem") or []

    assert "patio-contratos" in dependencias

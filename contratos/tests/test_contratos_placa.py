"""Formato de placa: antigo (ABC1234) e Mercosul (ABC1D23), sempre em maiúsculas e sem hífen."""

import pytest

from contratos.placa import PlacaInvalidaError, normalizar_placa


def test_aceita_o_formato_antigo() -> None:
    assert normalizar_placa("ABC1234") == "ABC1234"


def test_aceita_o_formato_mercosul() -> None:
    assert normalizar_placa("ABC1D23") == "ABC1D23"


@pytest.mark.parametrize(
    ("escrita", "canonica"),
    [
        ("abc1d23", "ABC1D23"),
        ("ABC-1234", "ABC1234"),
        ("abc-1d23", "ABC1D23"),
        ("ABC 1234", "ABC1234"),
        ("  ABC1234 ", "ABC1234"),
    ],
)
def test_devolve_maiusculas_sem_hifen_nem_espacos(escrita: str, canonica: str) -> None:
    assert normalizar_placa(escrita) == canonica


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "AB1234",  # letras de menos
        "ABCD123",  # letras de mais
        "ABC12345",  # números de mais
        "1BC1234",  # número onde só cabe letra
        "ABC1DD3",  # duas letras no meio
        "ABC12D3",  # letra na posição errada
        "AB-C1234",  # hífen fora do lugar
        "ABC--1234",
        "ÁBC1234",  # letra com acento
        "ABC\u0661234",  # algarismo arábico-índico: é dígito, mas não é 0-9
    ],
)
def test_recusa_o_que_nao_e_placa(texto: str) -> None:
    with pytest.raises(PlacaInvalidaError):
        normalizar_placa(texto)


def test_erro_diz_quais_formatos_sao_aceitos() -> None:
    with pytest.raises(PlacaInvalidaError, match=r"ABC1234.*ABC1D23"):
        normalizar_placa("XYZ")


def test_erro_de_placa_e_um_erro_de_valor() -> None:
    # Validadores do pydantic transformam ValueError em erro de validação do campo.
    assert issubclass(PlacaInvalidaError, ValueError)

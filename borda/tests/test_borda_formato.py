"""Formato da placa lida (SDD 4.2): corrige por posição, nunca inventa caractere."""

import re

import pytest

from borda.leitor.formato import PENALIDADE_POR_CORRECAO, formatar
from contratos.placa import FORMATO_CANONICO


def test_placa_antiga_certa_passa_sem_mudar() -> None:
    lida = formatar("ABC1234", 0.9)

    assert lida is not None
    assert (lida.placa, lida.confianca, lida.correcoes) == ("ABC1234", 0.9, 0)


def test_placa_mercosul_certa_passa_sem_mudar() -> None:
    lida = formatar("ABC1D23", 0.9)

    assert lida is not None
    assert (lida.placa, lida.correcoes) == ("ABC1D23", 0)


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("0BC1234", "OBC1234"),
        ("A1C1234", "AIC1234"),
        ("AB81234", "ABB1234"),
        ("5BC1234", "SBC1234"),
    ],
    ids=["0 vira O", "1 vira I", "8 vira B", "5 vira S"],
)
def test_onde_so_cabe_letra_o_numero_parecido_vira_letra(texto: str, esperada: str) -> None:
    lida = formatar(texto, 1.0)

    assert lida is not None
    assert (lida.placa, lida.correcoes) == (esperada, 1)


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("ABCO234", "ABC0234"),
        ("ABC1D2I", "ABC1D21"),
        ("ABC12B4", "ABC1284"),
        ("ABCS234", "ABC5234"),
    ],
    ids=["O vira 0", "I vira 1", "B vira 8", "S vira 5"],
)
def test_onde_so_cabe_numero_a_letra_parecida_vira_numero(texto: str, esperada: str) -> None:
    lida = formatar(texto, 1.0)

    assert lida is not None
    assert (lida.placa, lida.correcoes) == (esperada, 1)


def test_quinta_posicao_aceita_letra_e_numero_e_nunca_e_corrigida() -> None:
    # ABC1O23 é Mercosul válida com a letra O; virar ABC1023 seria inventar.
    lida = formatar("ABC1O23", 1.0)

    assert lida is not None
    assert (lida.placa, lida.correcoes) == ("ABC1O23", 0)


def test_cada_correcao_reduz_a_confianca() -> None:
    uma = formatar("0BC1234", 1.0)
    duas = formatar("0BC12B4", 1.0)

    assert uma is not None and duas is not None
    assert uma.confianca == pytest.approx(PENALIDADE_POR_CORRECAO)
    assert duas.confianca == pytest.approx(PENALIDADE_POR_CORRECAO**2)
    assert PENALIDADE_POR_CORRECAO < 1


def test_tira_so_os_separadores_e_poe_em_maiusculas() -> None:
    lida = formatar(" abc-1d23 ", 0.8)

    assert lida is not None
    assert lida.placa == "ABC1D23"


@pytest.mark.parametrize(
    "texto",
    ["ABC123", "ABC12345", "", "AB*1234", "7BC1234", "ABC1Z23Z", "ABCX234", "ÃBC1234"],
    ids=[
        "curta",
        "longa",
        "vazia",
        "símbolo",
        "número sem correção onde cabe letra",
        "longa com letra",
        "letra sem correção onde cabe número",
        "letra com acento",
    ],
)
def test_texto_que_nao_vira_placa_sem_inventar_e_descartado(texto: str) -> None:
    assert formatar(texto, 0.99) is None


def test_resultado_segue_o_formato_do_contrato() -> None:
    lida = formatar("0BC1O2I", 1.0)

    assert lida is not None
    assert lida.placa == "OBC1O21"
    assert re.fullmatch(FORMATO_CANONICO, lida.placa)

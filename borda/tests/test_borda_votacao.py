"""Votação entre os quadros de um mesmo veículo (SDD 4.2)."""

import pytest

from borda.leitor.votacao import LeituraDoQuadro, votar


def _quadros(*leituras: tuple[str, float]) -> list[LeituraDoQuadro]:
    return [LeituraDoQuadro(placa=placa, confianca=confianca) for placa, confianca in leituras]


def test_fica_a_placa_lida_em_mais_quadros() -> None:
    resultado = votar(
        _quadros(("ABC1234", 0.8), ("ABC1284", 0.99), ("ABC1234", 0.7), ("ABC1234", 0.75))
    )

    assert resultado is not None
    assert (resultado.placa, resultado.quadros) == ("ABC1234", 3)


def test_empate_fica_com_a_maior_confianca_media() -> None:
    resultado = votar(
        _quadros(("ABC1234", 0.6), ("ABC1284", 0.9), ("ABC1234", 0.7), ("ABC1284", 0.8))
    )

    assert resultado is not None
    assert resultado.placa == "ABC1284"


def test_confianca_e_a_media_vezes_a_concordancia() -> None:
    # 4 de 5 quadros a 0,95 → 0,95 x 0,8 = 0,76 (SDD 4.2).
    resultado = votar(_quadros(*[("ABC1234", 0.95)] * 4, ("XYZ9876", 0.99)))

    assert resultado is not None
    assert resultado.confianca == pytest.approx(0.76)


def test_um_quadro_so_vale_a_confianca_dele() -> None:
    resultado = votar(_quadros(("ABC1D23", 0.9)))

    assert resultado is not None
    assert (resultado.placa, resultado.confianca, resultado.quadros) == ("ABC1D23", 0.9, 1)


def test_sem_quadros_nao_ha_placa() -> None:
    assert votar([]) is None


def test_empate_total_e_decidido_sempre_do_mesmo_jeito() -> None:
    # Mesma contagem e mesma confiança: a ordem dos quadros não muda o resultado.
    ida = votar(_quadros(("ABC1234", 0.9), ("XYZ9876", 0.9)))
    volta = votar(_quadros(("XYZ9876", 0.9), ("ABC1234", 0.9)))

    assert ida is not None and volta is not None
    assert ida.placa == volta.placa

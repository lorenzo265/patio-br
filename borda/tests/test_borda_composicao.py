"""Composição na caixa (SDD 4.3, D-23): junta cavalo (frente) e reboque (trás) de cada faixa."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from borda.composicao import Composicao, Compositor, LeituraDeVeiculo, Posicao

T0 = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
JANELA = timedelta(seconds=30)


def _leitura(
    placa: str | None,
    posicao: Posicao,
    segundos: float,
    *,
    faixa: str = "1",
    confianca: float = 0.95,
    quadros: int = 5,
) -> LeituraDeVeiculo:
    inicio = T0 + timedelta(seconds=segundos)
    return LeituraDeVeiculo(
        faixa_id=faixa,
        camera_id="11" if posicao == "frente" else "12",
        posicao=posicao,
        placa=placa,
        confianca=confianca,
        quadros=quadros,
        inicio=inicio,
        fim=inicio + timedelta(seconds=4),
    )


def _papeis(composicao: Composicao) -> list[tuple[str, str]]:
    return [(placa.placa, placa.papel) for placa in composicao.placas]


@pytest.fixture
def compositor() -> Compositor:
    return Compositor(janela=JANELA)


def test_cavalo_e_reboque_na_janela_viram_uma_composicao(compositor: Compositor) -> None:
    assert compositor.receber(_leitura("ABC1D23", "frente", 0)) == []

    prontas = compositor.receber(_leitura("XYZ9876", "tras", 12))

    assert [_papeis(c) for c in prontas] == [[("ABC1D23", "cavalo"), ("XYZ9876", "reboque")]]
    assert (prontas[0].inicio, prontas[0].fim) == (T0, T0 + timedelta(seconds=16))
    assert prontas[0].faixa_id == "1"


def test_composicao_leva_camera_confianca_e_quadros_de_cada_placa(compositor: Compositor) -> None:
    compositor.receber(_leitura("ABC1D23", "frente", 0, confianca=0.97, quadros=6))

    pronta = compositor.receber(_leitura("XYZ9876", "tras", 10, confianca=0.88, quadros=3))[0]

    cavalo, reboque = pronta.placas
    assert (cavalo.camera_id, cavalo.confianca, cavalo.quadros) == ("11", 0.97, 6)
    assert (reboque.camera_id, reboque.confianca, reboque.quadros) == ("12", 0.88, 3)


def test_cavalo_sem_reboque_sai_sozinho_no_fim_da_janela(compositor: Compositor) -> None:
    compositor.receber(_leitura("ABC1D23", "frente", 0))

    antes = compositor.vencer(T0 + timedelta(seconds=4) + JANELA - timedelta(seconds=1))
    depois = compositor.vencer(T0 + timedelta(seconds=4) + JANELA)

    assert antes == []
    assert [_papeis(c) for c in depois] == [[("ABC1D23", "cavalo")]]


def test_traseira_igual_a_frente_e_o_mesmo_veiculo_sem_reboque(compositor: Compositor) -> None:
    compositor.receber(_leitura("ABC1D23", "frente", 0))

    prontas = compositor.receber(_leitura("ABC1D23", "tras", 8))

    assert [_papeis(c) for c in prontas] == [[("ABC1D23", "cavalo")]]
    assert prontas[0].fim == T0 + timedelta(seconds=12)


def test_reboque_sem_cavalo_sai_na_hora_com_papel_desconhecido(compositor: Compositor) -> None:
    # Sem a frente, a placa traseira pode ser de um reboque ou do próprio cavalo (D-23).
    prontas = compositor.receber(_leitura("XYZ9876", "tras", 0))

    assert [_papeis(c) for c in prontas] == [[("XYZ9876", "desconhecido")]]


def test_traseira_depois_da_janela_nao_entra_na_composicao(compositor: Compositor) -> None:
    compositor.receber(_leitura("ABC1D23", "frente", 0))

    prontas = compositor.receber(_leitura("XYZ9876", "tras", 4 + 31))

    assert [_papeis(c) for c in prontas] == [
        [("ABC1D23", "cavalo")],
        [("XYZ9876", "desconhecido")],
    ]


def test_reboque_vai_para_o_cavalo_mais_recente_e_os_antigos_saem_sozinhos(
    compositor: Compositor,
) -> None:
    # Dois cavalos passaram pela frente; a traseira lida é do último que passou.
    compositor.receber(_leitura("AAA1111", "frente", 0))
    compositor.receber(_leitura("BBB2222", "frente", 6))

    prontas = compositor.receber(_leitura("XYZ9876", "tras", 14))

    assert [_papeis(c) for c in prontas] == [
        [("AAA1111", "cavalo")],
        [("BBB2222", "cavalo"), ("XYZ9876", "reboque")],
    ]


def test_faixas_diferentes_nao_se_misturam(compositor: Compositor) -> None:
    compositor.receber(_leitura("ABC1D23", "frente", 0, faixa="1"))

    prontas = compositor.receber(_leitura("XYZ9876", "tras", 5, faixa="2"))

    assert [(c.faixa_id, _papeis(c)) for c in prontas] == [("2", [("XYZ9876", "desconhecido")])]


def test_janela_e_configuravel() -> None:
    curta = Compositor(janela=timedelta(seconds=5))
    curta.receber(_leitura("ABC1D23", "frente", 0))

    prontas = curta.receber(_leitura("XYZ9876", "tras", 4 + 6))

    assert [_papeis(c) for c in prontas] == [
        [("ABC1D23", "cavalo")],
        [("XYZ9876", "desconhecido")],
    ]


def test_janela_padrao_e_30_segundos() -> None:
    assert Compositor().janela == timedelta(seconds=30)


def test_vencer_devolve_cada_composicao_uma_vez_so(compositor: Compositor) -> None:
    compositor.receber(_leitura("ABC1D23", "frente", 0))
    fim = T0 + timedelta(minutes=5)

    assert len(compositor.vencer(fim)) == 1
    assert compositor.vencer(fim) == []


def test_esvaziar_devolve_o_que_ainda_esperava(compositor: Compositor) -> None:
    # Ao desligar a caixa, nada que foi lido se perde.
    compositor.receber(_leitura("ABC1D23", "frente", 0))

    assert [_papeis(c) for c in compositor.esvaziar()] == [[("ABC1D23", "cavalo")]]


# --- Leitura sem placa legível -------------------------------------------------------------


def test_frente_ilegivel_com_traseira_lida_deixa_a_traseira_desconhecida(
    compositor: Compositor,
) -> None:
    # Viu-se um veículo na frente, mas sem placa: a traseira pode ser reboque ou o cavalo.
    compositor.receber(_leitura(None, "frente", 0))

    prontas = compositor.receber(_leitura("XYZ9876", "tras", 10))

    assert [_papeis(c) for c in prontas] == [[("XYZ9876", "desconhecido")]]
    assert prontas[0].inicio == T0


def test_frente_lida_com_traseira_ilegivel_fecha_so_com_o_cavalo(compositor: Compositor) -> None:
    compositor.receber(_leitura("ABC1D23", "frente", 0))

    prontas = compositor.receber(_leitura(None, "tras", 10))

    assert [_papeis(c) for c in prontas] == [[("ABC1D23", "cavalo")]]


def test_frente_sem_placa_nenhuma_vira_passagem_vazia(compositor: Compositor) -> None:
    # A nuvem recebe a passagem sem placas e trata como exceção (SDD 3.2).
    compositor.receber(_leitura(None, "frente", 0))

    assert [c.placas for c in compositor.vencer(T0 + timedelta(minutes=1))] == [()]


def test_traseira_sem_placa_e_sem_frente_vira_passagem_vazia(compositor: Compositor) -> None:
    assert [c.placas for c in compositor.receber(_leitura(None, "tras", 0))] == [()]


def test_recortes_acompanham_as_placas(compositor: Compositor) -> None:
    recorte = np.full((12, 40, 3), 7, dtype=np.uint8)
    compositor.receber(replace(_leitura("ABC1D23", "frente", 0), recorte=recorte))

    pronta = compositor.receber(_leitura("XYZ9876", "tras", 10))[0]

    assert len(pronta.recortes) == len(pronta.placas) == 2
    assert pronta.recortes[0] is recorte
    assert pronta.recortes[1] is None

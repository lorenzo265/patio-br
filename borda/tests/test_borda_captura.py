"""Captura (SDD 4.2): os quadros chegam por uma fonte, à taxa configurada (padrão 5 por segundo)."""

from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from borda.captura import (
    QUADROS_POR_SEGUNDO,
    FonteDeMemoria,
    FonteDePasta,
    QuadroNoTempo,
    amostrar,
)

T0 = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)


def _quadros(quantos: int, por_segundo: float) -> list[QuadroNoTempo]:
    imagem = np.zeros((4, 4, 3), dtype=np.uint8)
    return [
        QuadroNoTempo(momento=T0 + timedelta(seconds=i / por_segundo), imagem=imagem)
        for i in range(quantos)
    ]


def test_padrao_e_5_quadros_por_segundo() -> None:
    assert QUADROS_POR_SEGUNDO == 5


def test_amostrar_um_video_de_30_quadros_por_segundo_deixa_5_por_segundo() -> None:
    saida = list(amostrar(_quadros(60, por_segundo=30)))  # 2 segundos

    momentos = [q.momento for q in saida]
    assert len(saida) == 10
    assert momentos[0] == T0
    assert all(b - a >= timedelta(seconds=0.2) for a, b in pairwise(momentos))


def test_fonte_mais_lenta_que_a_taxa_passa_inteira() -> None:
    assert len(list(amostrar(_quadros(6, por_segundo=2), por_segundo=5))) == 6


def test_taxa_precisa_ser_positiva() -> None:
    with pytest.raises(ValueError, match="quadros por segundo"):
        list(amostrar(_quadros(2, por_segundo=5), por_segundo=0))


def test_fonte_de_memoria_devolve_os_quadros_dados() -> None:
    quadros = _quadros(3, por_segundo=5)

    assert list(FonteDeMemoria(quadros).quadros()) == quadros


@pytest.mark.integracao
def test_fonte_de_pasta_le_as_imagens_em_ordem_de_nome(tmp_path: Path) -> None:
    # Os quadros de um vídeo, tirados fora da caixa, numa pasta (até o [ABERTO-13]).
    for indice, vermelho in [(2, 30), (0, 10), (1, 20)]:
        Image.new("RGB", (8, 6), (vermelho, 0, 0)).save(tmp_path / f"quadro-{indice:04d}.png")
    (tmp_path / "LEIA-ME.txt").write_text("não é imagem", encoding="utf-8")

    quadros = list(FonteDePasta(tmp_path, inicio=T0, por_segundo=10).quadros())

    assert [q.momento for q in quadros] == [T0 + timedelta(seconds=i / 10) for i in range(3)]
    assert [q.imagem.shape for q in quadros] == [(6, 8, 3)] * 3
    # Em BGR, como a câmera entrega: o vermelho fica no último canal.
    assert [int(q.imagem[0, 0, 2]) for q in quadros] == [10, 20, 30]
    assert quadros[0].imagem.dtype == np.uint8


@pytest.mark.integracao
def test_fonte_de_pasta_vazia_nao_devolve_nada(tmp_path: Path) -> None:
    assert list(FonteDePasta(tmp_path, inicio=T0).quadros()) == []

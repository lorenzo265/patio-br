"""Captura (SDD 4.2): os quadros de uma câmera chegam por uma fonte, à taxa configurada.

A fonte entrega quadros com a hora em que foram vistos. ``amostrar`` deixa passar no máximo
``QUADROS_POR_SEGUNDO`` por segundo: caminhão na portaria anda devagar, e 3 a 5 quadros por
segundo bastam (SDD 4.4).

Fontes de agora:

- ``FonteDeMemoria``: quadros já prontos (testes e simulador);
- ``FonteDePasta``: as imagens de uma pasta, em ordem de nome (os quadros de um vídeo, tirados
  fora da caixa), para a demonstração.

A câmera (RTSP) e o arquivo de vídeo precisam de um decodificador de vídeo, e os disponíveis
trazem partes GPL ou LGPL (SDD ``[ABERTO-13]``): entram depois da decisão, como outra fonte.
"""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image

from borda.leitor.interface import Quadro

QUADROS_POR_SEGUNDO = 5.0

EXTENSOES_DE_IMAGEM = frozenset({".jpg", ".jpeg", ".png", ".bmp"})


@dataclass(frozen=True)
class QuadroNoTempo:
    """Um quadro e a hora em que a câmera o viu (o relógio da caixa)."""

    momento: datetime
    imagem: Quadro = field(compare=False, repr=False)


class FonteDeQuadros(Protocol):
    """De onde vêm os quadros de uma câmera."""

    def quadros(self) -> Iterator[QuadroNoTempo]:
        """Os quadros, na ordem em que foram vistos."""
        ...


def amostrar(
    quadros: Iterable[QuadroNoTempo], por_segundo: float = QUADROS_POR_SEGUNDO
) -> Iterator[QuadroNoTempo]:
    """Deixa passar no máximo ``por_segundo`` quadros por segundo.

    Passa o primeiro quadro e, depois, cada quadro que chega pelo menos ``1 / por_segundo``
    depois do último que passou.

    Raises:
        ValueError: se ``por_segundo`` não for positivo.
    """
    if por_segundo <= 0:
        raise ValueError(f"os quadros por segundo precisam ser positivos: {por_segundo}")
    intervalo = timedelta(seconds=1 / por_segundo)
    # Uma folga de 1 ms: 30 quadros por segundo não dão 1/5 de segundo exato entre eles.
    folga = timedelta(milliseconds=1)
    ultimo: datetime | None = None
    for quadro in quadros:
        if ultimo is None or quadro.momento - ultimo >= intervalo - folga:
            ultimo = quadro.momento
            yield quadro


class FonteAmostrada:
    """Uma fonte com a taxa limitada por ``amostrar`` (ex.: uma pasta de 30 quadros/s a 5)."""

    def __init__(self, fonte: FonteDeQuadros, por_segundo: float = QUADROS_POR_SEGUNDO) -> None:
        """Guarda a fonte e a taxa."""
        self._fonte = fonte
        self._por_segundo = por_segundo

    def quadros(self) -> Iterator[QuadroNoTempo]:
        """Os quadros da fonte, no máximo ``por_segundo`` por segundo."""
        return amostrar(self._fonte.quadros(), self._por_segundo)


class FonteDeMemoria:
    """Quadros já prontos, em memória."""

    def __init__(self, quadros: Sequence[QuadroNoTempo]) -> None:
        """Guarda os quadros."""
        self._quadros = list(quadros)

    def quadros(self) -> Iterator[QuadroNoTempo]:
        """Os quadros, na ordem dada."""
        return iter(self._quadros)


class FonteDePasta:
    """As imagens de uma pasta, em ordem de nome, como quadros de um vídeo."""

    def __init__(
        self, pasta: Path, *, inicio: datetime, por_segundo: float = QUADROS_POR_SEGUNDO
    ) -> None:
        """Prepara a leitura.

        Args:
            pasta: onde estão as imagens (``.jpg``, ``.png``...); outros arquivos são ignorados.
            inicio: a hora do primeiro quadro.
            por_segundo: quantos quadros por segundo as imagens representam (o quadro ``n``
                fica em ``inicio + n / por_segundo``).
        """
        self._pasta = pasta
        self._inicio = inicio
        self._intervalo = timedelta(seconds=1 / por_segundo)

    def quadros(self) -> Iterator[QuadroNoTempo]:
        """Os quadros, em BGR (como a câmera entrega), na ordem dos nomes dos arquivos."""
        imagens = sorted(
            arquivo
            for arquivo in self._pasta.iterdir()
            if arquivo.suffix.lower() in EXTENSOES_DE_IMAGEM
        )
        for indice, arquivo in enumerate(imagens):
            with Image.open(arquivo) as imagem:
                rgb = np.asarray(imagem.convert("RGB"), dtype=np.uint8)
            bgr = np.ascontiguousarray(rgb[:, :, ::-1])
            yield QuadroNoTempo(momento=self._inicio + indice * self._intervalo, imagem=bgr)

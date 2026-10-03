"""A interface única do leitor de placas (SDD 4.5): entra uma imagem, saem os textos lidos.

Qualquer motor (o v0 com modelos pré-treinados, o v1 com pesos nossos, o comercial) fica atrás
desta interface: trocar de motor não muda nada fora da caixa (SDD D-07).
"""

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import numpy.typing as npt

Quadro = npt.NDArray[np.uint8]
"""Uma imagem colorida, em BGR, com forma (altura, largura, 3): o que a captura entrega."""


@dataclass(frozen=True)
class Regiao:
    """Um retângulo na imagem, em pixels: canto de cima à esquerda, largura e altura."""

    x: int
    y: int
    largura: int
    altura: int


@dataclass(frozen=True)
class LeituraBruta:
    """Um texto que o motor achou na imagem, ainda sem a regra de formato da placa."""

    texto: str
    confianca: float
    """De 0 a 1."""
    regiao: Regiao
    """Onde o texto (a placa) está na imagem; serve para recortar a foto da placa."""


class LeitorDePlacas(Protocol):
    """Um motor de leitura de placas."""

    def ler(self, quadro: Quadro) -> list[LeituraBruta]:
        """Lê as placas de um quadro (pode não achar nenhuma)."""
        ...

"""A fonte de traços das placas sintéticas, desenhada por nós (D-72).

Cada caractere são linhas numa grade de 4 de largura por 8 de altura, como as letras estreitas e
de cantos chanfrados das placas. A fonte oficial da placa Mercosul e a Mandatory, da placa cinza,
não têm licença que sirva; o leitor aprende o formato com as variações, e não com o desenho exato
de cada letra.
"""

from collections.abc import Sequence

from PIL import Image, ImageDraw

LARGURA = 4
ALTURA = 8
Ponto = tuple[float, float]

_ZERO: list[Ponto] = [(1, 0), (3, 0), (4, 1), (4, 7), (3, 8), (1, 8), (0, 7), (0, 1), (1, 0)]
_P: list[Ponto] = [(0, 8), (0, 0), (3, 0), (4, 1), (4, 3), (3, 4), (0, 4)]

TRACOS: dict[str, list[list[Ponto]]] = {
    "0": [_ZERO],
    "1": [[(1, 2), (3, 0), (3, 8)]],
    "2": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (0, 8), (4, 8)]],
    "3": [
        [(0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (3, 4), (1, 4)],
        [(3, 4), (4, 5), (4, 7), (3, 8), (1, 8), (0, 7)],
    ],
    "4": [[(3, 8), (3, 0), (0, 6), (4, 6)]],
    "5": [[(4, 0), (0, 0), (0, 4), (3, 4), (4, 5), (4, 7), (3, 8), (1, 8), (0, 7)]],
    "6": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 7), (1, 8), (3, 8), (4, 7), (4, 5), (3, 4), (0, 4)]],
    "7": [[(0, 0), (4, 0), (1, 8)]],
    "8": [
        [(1, 4), (0, 3), (0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (3, 4), (1, 4)],
        [(1, 4), (0, 5), (0, 7), (1, 8), (3, 8), (4, 7), (4, 5), (3, 4)],
    ],
    "9": [[(4, 4), (1, 4), (0, 3), (0, 1), (1, 0), (3, 0), (4, 1), (4, 7), (3, 8), (1, 8), (0, 7)]],
    "A": [[(0, 8), (0, 2), (2, 0), (4, 2), (4, 8)], [(0, 5), (4, 5)]],
    "B": [
        [(0, 0), (3, 0), (4, 1), (4, 3), (3, 4), (0, 4)],
        [(3, 4), (4, 5), (4, 7), (3, 8), (0, 8), (0, 0)],
    ],
    "C": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 7), (1, 8), (3, 8), (4, 7)]],
    "D": [[(0, 0), (3, 0), (4, 1), (4, 7), (3, 8), (0, 8), (0, 0)]],
    "E": [[(4, 0), (0, 0), (0, 8), (4, 8)], [(0, 4), (3, 4)]],
    "F": [[(4, 0), (0, 0), (0, 8)], [(0, 4), (3, 4)]],
    "G": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 7), (1, 8), (3, 8), (4, 7), (4, 4), (2, 4)]],
    "H": [[(0, 0), (0, 8)], [(4, 0), (4, 8)], [(0, 4), (4, 4)]],
    "I": [[(1, 0), (3, 0)], [(2, 0), (2, 8)], [(1, 8), (3, 8)]],
    "J": [[(4, 0), (4, 7), (3, 8), (1, 8), (0, 7), (0, 6)]],
    "K": [[(0, 0), (0, 8)], [(4, 0), (0, 5)], [(1, 4), (4, 8)]],
    "L": [[(0, 0), (0, 8), (4, 8)]],
    "M": [[(0, 8), (0, 0), (2, 4), (4, 0), (4, 8)]],
    "N": [[(0, 8), (0, 0), (4, 8), (4, 0)]],
    "O": [
        [(0.5, 0), (3.5, 0), (4, 0.5), (4, 7.5), (3.5, 8), (0.5, 8), (0, 7.5), (0, 0.5), (0.5, 0)]
    ],
    "P": [_P],
    "Q": [_ZERO, [(2, 6), (4, 8)]],
    "R": [_P, [(2, 4), (4, 8)]],
    "S": [
        [
            (4, 1),
            (3, 0),
            (1, 0),
            (0, 1),
            (0, 3),
            (1, 4),
            (3, 4),
            (4, 5),
            (4, 7),
            (3, 8),
            (1, 8),
            (0, 7),
        ]
    ],
    "T": [[(0, 0), (4, 0)], [(2, 0), (2, 8)]],
    "U": [[(0, 0), (0, 7), (1, 8), (3, 8), (4, 7), (4, 0)]],
    "V": [[(0, 0), (2, 8), (4, 0)]],
    "W": [[(0, 0), (1, 8), (2, 4), (3, 8), (4, 0)]],
    "X": [[(0, 0), (4, 8)], [(4, 0), (0, 8)]],
    "Y": [[(0, 0), (2, 4), (4, 0)], [(2, 4), (2, 8)]],
    "Z": [[(0, 0), (4, 0), (0, 8), (4, 8)]],
    "-": [[(0.5, 4), (3.5, 4)]],
}
"""Os traços de cada caractere, na grade de ``LARGURA`` por ``ALTURA``."""

ESPESSURA = 0.11
"""A grossura do traço, em partes da altura da letra."""


def largura_de(altura: float) -> float:
    """A largura de uma letra desta altura (com a meia grossura de cada lado)."""
    return altura * LARGURA / ALTURA + altura * ESPESSURA


def desenhar(
    imagem: Image.Image,
    caractere: str,
    canto: tuple[float, float],
    *,
    altura: float,
    cor: int | tuple[int, int, int],
) -> None:
    """Desenha um caractere com o canto de cima à esquerda em ``canto``."""
    grossura = max(1, round(altura * ESPESSURA))
    meia = grossura / 2
    escala = (altura - grossura) / ALTURA
    desenho = ImageDraw.Draw(imagem)
    for linha in TRACOS[caractere]:
        pontos = [(canto[0] + meia + x * escala, canto[1] + meia + y * escala) for x, y in linha]
        _linha(desenho, pontos, grossura, cor)


def _linha(
    desenho: ImageDraw.ImageDraw,
    pontos: Sequence[tuple[float, float]],
    grossura: int,
    cor: int | tuple[int, int, int],
) -> None:
    desenho.line(list(pontos), fill=cor, width=grossura, joint="curve")
    raio = grossura / 2
    for x, y in (pontos[0], pontos[-1]):
        # A ponta redonda: o traço do Pillow termina reto.
        desenho.ellipse((x - raio, y - raio, x + raio, y + raio), fill=cor)

"""O formato da placa lida (SDD 4.2): valida e corrige pela posição de cada caractere.

Placa antiga ``LLLNNNN`` e Mercosul ``LLLNLNN``: as três primeiras posições são letras, a 4ª,
a 6ª e a 7ª são números, e a 5ª aceita os dois. Onde só cabe letra, um número parecido vira
letra (``0→O``, ``1→I``, ``8→B``, ``5→S``); onde só cabe número, o contrário. A 5ª posição
nunca é corrigida, porque os dois formatos são válidos.

O leitor nunca inventa nem apaga caractere: só os separadores saem, e o que não fica com 7
caracteres, ou tem um caractere sem correção possível na posição, é descartado.
"""

import re
from dataclasses import dataclass

PENALIDADE_POR_CORRECAO = 0.9
"""Cada caractere corrigido multiplica a confiança por este valor."""

_SEPARADORES = re.compile(r"[\s\-.·]")
_PARA_LETRA = {"0": "O", "1": "I", "8": "B", "5": "S"}
_PARA_NUMERO = {letra: numero for numero, letra in _PARA_LETRA.items()}
_LETRAS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_NUMEROS = frozenset("0123456789")
_SO_LETRA = (0, 1, 2)
_SO_NUMERO = (3, 5, 6)
_TAMANHO = 7


@dataclass(frozen=True)
class PlacaFormatada:
    """Uma placa no formato canônico, com a confiança já reduzida pelas correções."""

    placa: str
    confianca: float
    correcoes: int


def formatar(texto: str, confianca: float) -> PlacaFormatada | None:
    """Põe o texto lido no formato da placa, corrigindo pela posição.

    Args:
        texto: o que o motor leu (ex.: ``"abc-1d23"`` ou ``"0BC1234"``).
        confianca: a confiança do motor nessa leitura, de 0 a 1.

    Returns:
        A placa canônica (``ABC1234`` ou ``ABC1D23``), ou ``None`` se o texto não vira placa
        sem inventar caractere.
    """
    caracteres = list(_SEPARADORES.sub("", texto).upper())
    if len(caracteres) != _TAMANHO:
        return None
    correcoes = 0
    for posicao, caractere in enumerate(caracteres):
        if posicao in _SO_LETRA:
            certo, troca = _LETRAS, _PARA_LETRA
        elif posicao in _SO_NUMERO:
            certo, troca = _NUMEROS, _PARA_NUMERO
        else:
            certo, troca = _LETRAS | _NUMEROS, {}
        if caractere in certo:
            continue
        if caractere not in troca:
            return None
        caracteres[posicao] = troca[caractere]
        correcoes += 1
    return PlacaFormatada(
        placa="".join(caracteres),
        confianca=confianca * PENALIDADE_POR_CORRECAO**correcoes,
        correcoes=correcoes,
    )

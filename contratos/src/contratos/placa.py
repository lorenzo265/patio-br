"""Placa de veículo brasileira: o formato antigo e o Mercosul (SDD 4.2).

A forma canônica é a que circula entre borda e nuvem: maiúsculas, sem hífen nem espaços.
A entrada aceita também a forma como as pessoas escrevem (``abc-1234``), para que o registro
manual e a importação de planilhas usem a mesma regra.

A correção de leitura por posição (``0→O``, ``1→I``...) não é desta regra: ela é do leitor, na
borda, que registra a correção com confiança menor.
"""

import re
from typing import Annotated

from pydantic import BeforeValidator, StringConstraints

FORMATO_CANONICO = "^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"
"""Antiga (``ABC1234``) e Mercosul (``ABC1D23``): só a 5ª posição muda entre as duas."""

_PADRAO = re.compile(FORMATO_CANONICO)
_POSICAO_DO_HIFEN = 3
"""Como as pessoas escrevem: ``ABC-1234`` (o separador vem depois das três letras)."""


class PlacaInvalidaError(ValueError):
    """O texto não é uma placa no formato antigo nem no Mercosul."""

    def __init__(self, texto: str) -> None:
        super().__init__(f"placa inválida: {texto!r} (formatos aceitos: ABC1234 e ABC1D23)")
        self.texto = texto


def normalizar_placa(texto: str) -> str:
    """Devolve a placa na forma canônica: maiúsculas, sem hífen nem espaços.

    Args:
        texto: a placa como foi lida ou escrita (ex.: ``abc-1d23``).

    Returns:
        A placa canônica (ex.: ``ABC1D23``).

    Raises:
        PlacaInvalidaError: se o texto não for uma placa no formato antigo nem no Mercosul.
    """
    candidata = texto.strip().upper()
    if len(candidata) > _POSICAO_DO_HIFEN and candidata[_POSICAO_DO_HIFEN] in "- ":
        candidata = candidata[:_POSICAO_DO_HIFEN] + candidata[_POSICAO_DO_HIFEN + 1 :]
    if not _PADRAO.fullmatch(candidata):
        raise PlacaInvalidaError(texto)
    return candidata


def _normalizar_se_texto(valor: object) -> object:
    # Valor que não é texto segue adiante e é recusado pela validação de str do pydantic.
    return normalizar_placa(valor) if isinstance(valor, str) else valor


Placa = Annotated[
    str,
    StringConstraints(pattern=FORMATO_CANONICO),
    BeforeValidator(_normalizar_se_texto),
]
"""Tipo de campo para modelos pydantic: aceita a placa escrita e guarda a canônica."""

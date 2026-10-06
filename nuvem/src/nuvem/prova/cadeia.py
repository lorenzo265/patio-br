"""A regra do resumo da cadeia de prova (D-69), sem banco: a mesma que o arquivo da prova explica.

O resumo de um elo é o SHA-256, em hexadecimal, do texto: o resumo do elo anterior (64 zeros no
primeiro), uma quebra de linha e o JSON de ``{"tipo", "referencia", "conteudo"}``, com as chaves
em ordem, sem espaços e em UTF-8. Mudar qualquer coisa num elo muda o resumo dele; e, como o
seguinte guarda esse resumo, quebra a ligação dali em diante.
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

INICIO = "0" * 64
"""O "anterior" do primeiro elo de cada visita."""
REGRA = (
    'sha256(anterior + "\\n" + json({"conteudo", "referencia", "tipo"})), em hexadecimal; '
    "o JSON com as chaves em ordem, sem espaços, em UTF-8; o anterior do primeiro elo são 64 zeros"
)
"""A regra, escrita no arquivo da prova para quem quiser conferir sem nós."""


@dataclass(frozen=True)
class Elo:
    """Um elo da cadeia, como está guardado."""

    ordem: int
    tipo: str
    referencia: str
    conteudo: Any
    anterior: str
    resumo: str


@dataclass(frozen=True)
class Quebra:
    """O primeiro elo que não confere, e por quê."""

    ordem: int
    motivo: str


def json_canonico(valor: Any) -> str:
    """O JSON com as chaves em ordem e sem espaços: o mesmo valor dá sempre o mesmo texto."""
    return json.dumps(valor, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def resumo_do_elo(anterior: str, tipo: str, referencia: str, conteudo: Any) -> str:
    """O resumo de um elo, pela regra (``REGRA``)."""
    texto = json_canonico({"conteudo": conteudo, "referencia": referencia, "tipo": tipo})
    return hashlib.sha256(f"{anterior}\n{texto}".encode()).hexdigest()


def primeira_quebra(elos: Sequence[Elo]) -> Quebra | None:
    """Refaz a cadeia na ordem e devolve o primeiro elo que não confere (``None``: íntegra)."""
    anterior = INICIO
    for posicao, elo in enumerate(elos, start=1):
        if elo.ordem != posicao:
            return Quebra(elo.ordem, "falta um elo antes deste")
        if elo.anterior != anterior:
            return Quebra(elo.ordem, "o resumo do anterior não bate")
        if resumo_do_elo(elo.anterior, elo.tipo, elo.referencia, elo.conteudo) != elo.resumo:
            return Quebra(elo.ordem, "o resumo não bate com o conteúdo")
        anterior = elo.resumo
    return None

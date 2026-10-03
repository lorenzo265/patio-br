"""Votação entre os quadros do mesmo veículo (SDD 4.2).

O veículo aparece em vários quadros do vídeo, e o leitor pode errar em alguns. Fica a placa
lida em mais quadros; no empate, a de maior confiança média; no empate total, a primeira em
ordem alfabética (para o resultado não depender da ordem dos quadros).

A confiança final é a média das confianças dos quadros vencedores vezes a fração dos quadros
que concordam: discordância entre quadros é sinal de leitura duvidosa.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean


@dataclass(frozen=True)
class LeituraDoQuadro:
    """A placa (já formatada) lida num quadro, com a confiança."""

    placa: str
    confianca: float


@dataclass(frozen=True)
class ResultadoDaVotacao:
    """A placa escolhida para o veículo."""

    placa: str
    confianca: float
    quadros: int
    """Em quantos quadros a placa escolhida foi lida."""


def votar(leituras: Sequence[LeituraDoQuadro]) -> ResultadoDaVotacao | None:
    """Escolhe a placa do veículo entre as leituras dos quadros.

    Returns:
        A placa escolhida, ou ``None`` se não houve leitura nenhuma.
    """
    if not leituras:
        return None
    por_placa: dict[str, list[float]] = defaultdict(list)
    for leitura in leituras:
        por_placa[leitura.placa].append(leitura.confianca)
    placa, confiancas = min(
        por_placa.items(), key=lambda item: (-len(item[1]), -fmean(item[1]), item[0])
    )
    concordancia = len(confiancas) / len(leituras)
    return ResultadoDaVotacao(
        placa=placa, confianca=fmean(confiancas) * concordancia, quadros=len(confiancas)
    )

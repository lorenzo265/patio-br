"""Composição na caixa (SDD 4.3, D-23): junta, por faixa, o cavalo e o reboque de um caminhão.

A câmera da frente lê o cavalo (reboque não tem placa na frente). A de trás lê a placa traseira
do último reboque, ou a do próprio cavalo quando ele passa sem reboque. As regras:

- leitura da frente: é o cavalo, e espera a de trás até o fim da janela (padrão 30 s);
- leitura de trás com placa diferente: é o reboque da composição mais recente da faixa, que
  se fecha ali; as mais antigas que ainda esperavam saem sozinhas (veio um veículo depois);
- leitura de trás igual à da frente: é o mesmo veículo, sem reboque; fecha só com o cavalo;
- leitura de trás sem frente na janela: sai na hora, com papel ``desconhecido``;
- leitura da frente sem a de trás no fim da janela: sai sozinha, como cavalo;
- leitura sem placa legível (o veículo foi visto, a placa não) segue as mesmas regras, mas não
  vira placa: a frente ilegível deixa a traseira com papel ``desconhecido``, e sem placa
  nenhuma a composição sai vazia (a nuvem trata como exceção).

O tempo é o das leituras (relógio da caixa): ``vencer`` recebe a hora atual e devolve o que já
passou da janela.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from borda.leitor.interface import Quadro
from contratos.passagem import Papel, PlacaLida

Posicao = Literal["frente", "tras"]

JANELA_PADRAO = timedelta(seconds=30)


@dataclass(frozen=True)
class LeituraDeVeiculo:
    """A placa de um veículo numa câmera, já votada entre os quadros (ver ``votacao``)."""

    faixa_id: str
    camera_id: str
    posicao: Posicao
    placa: str | None
    """A placa votada, ou ``None`` se o veículo passou sem placa legível."""
    confianca: float
    quadros: int
    inicio: datetime
    """Quando o veículo apareceu na câmera."""
    fim: datetime
    """Quando saiu dela."""
    recorte: Quadro | None = field(default=None, compare=False, repr=False)
    """O recorte da placa mais confiável, para a foto da passagem."""


@dataclass(frozen=True)
class Composicao:
    """Uma passagem montada: as placas de um veículo numa faixa, com papel."""

    faixa_id: str
    inicio: datetime
    fim: datetime
    placas: tuple[PlacaLida, ...]
    recortes: tuple[Quadro | None, ...] = field(default=(), compare=False, repr=False)
    """O recorte de cada placa, na mesma ordem de ``placas`` (``None`` se não houver)."""


class Compositor:
    """Junta as leituras de cada faixa em composições."""

    def __init__(self, janela: timedelta = JANELA_PADRAO) -> None:
        """Prepara o compositor.

        Args:
            janela: quanto tempo a leitura da frente espera a de trás, contado do fim dela.
        """
        self.janela = janela
        self._esperando: dict[str, list[LeituraDeVeiculo]] = defaultdict(list)
        """Leituras da frente esperando a de trás, por faixa, da mais antiga à mais nova."""

    def receber(self, leitura: LeituraDeVeiculo) -> list[Composicao]:
        """Recebe uma leitura e devolve as composições que ficaram prontas com ela."""
        prontas = self._vencer_faixa(leitura.faixa_id, leitura.inicio)
        esperando = self._esperando[leitura.faixa_id]
        if leitura.posicao == "frente":
            esperando.append(leitura)
            return prontas
        mesma_placa = next(
            (f for f in esperando if leitura.placa and f.placa == leitura.placa), None
        )
        if mesma_placa is not None:
            # A traseira do próprio cavalo: o veículo passou sem reboque.
            esperando.remove(mesma_placa)
            return [*prontas, _compor(mesma_placa, fim=max(mesma_placa.fim, leitura.fim))]
        if not esperando:
            return [*prontas, _compor(leitura, papel="desconhecido")]
        *antigas, cavalo = esperando
        esperando.clear()
        sozinhas = [_compor(antiga) for antiga in antigas]
        if cavalo.placa is None:
            # A frente não se leu: a traseira pode ser reboque ou o próprio cavalo.
            juntas = _compor(leitura, papel="desconhecido", inicio=cavalo.inicio)
            return [*prontas, *sozinhas, juntas]
        return [*prontas, *sozinhas, _compor(cavalo, reboque=leitura)]

    def vencer(self, agora: datetime) -> list[Composicao]:
        """Devolve, como cavalo sozinho, as leituras da frente cuja janela já acabou."""
        prontas: list[Composicao] = []
        for faixa_id in list(self._esperando):
            prontas.extend(self._vencer_faixa(faixa_id, agora))
        return prontas

    def esvaziar(self) -> list[Composicao]:
        """Devolve tudo o que ainda esperava (ao desligar a caixa, nada se perde)."""
        prontas = [_compor(f) for esperando in self._esperando.values() for f in esperando]
        self._esperando.clear()
        return prontas

    def _vencer_faixa(self, faixa_id: str, agora: datetime) -> list[Composicao]:
        esperando = self._esperando[faixa_id]
        vencidas = [f for f in esperando if agora - f.fim >= self.janela]
        for vencida in vencidas:
            esperando.remove(vencida)
        return [_compor(vencida) for vencida in vencidas]


def _compor(
    principal: LeituraDeVeiculo,
    *,
    papel: Papel = "cavalo",
    reboque: LeituraDeVeiculo | None = None,
    inicio: datetime | None = None,
    fim: datetime | None = None,
) -> Composicao:
    leituras = [(principal, papel)] + ([(reboque, "reboque")] if reboque is not None else [])
    legiveis = [(leitura.placa, leitura, p) for leitura, p in leituras if leitura.placa is not None]
    return Composicao(
        faixa_id=principal.faixa_id,
        inicio=min([leitura.inicio for leitura, _ in leituras] + ([inicio] if inicio else [])),
        fim=fim or max(leitura.fim for leitura, _ in leituras),
        placas=tuple(
            PlacaLida(
                placa=placa,
                papel=papel_da_leitura,
                confianca=leitura.confianca,
                camera_id=leitura.camera_id,
                quadros=leitura.quadros,
            )
            for placa, leitura, papel_da_leitura in legiveis
        ),
        recortes=tuple(leitura.recorte for _, leitura, _ in legiveis),
    )

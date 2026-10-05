"""A interface dos conectores de agendamento (SDD 3.4).

Cada origem (o link da transportadora, a planilha do cliente, a API genérica e, depois, os ERPs)
é um conector: recebe os dados de fora e devolve, item a item, o agendamento no formato interno
(``Lido``) ou o motivo da recusa (``Recusado``), sempre dizendo onde estava o item (ex.:
``"linha 7"``). Quem grava é o serviço (``servico.importar``), igual para todos.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from nuvem.agendamento.formato import DadosDoAgendamento, descrever_erros
from nuvem.agendamento.modelos import Origem


@dataclass(frozen=True)
class Lido:
    """Um agendamento que o conector entendeu, já no formato interno."""

    onde: str
    dados: DadosDoAgendamento


@dataclass(frozen=True)
class Recusado:
    """Um item que não entrou, com o motivo em português."""

    onde: str
    motivo: str


class Conector[Entrada](Protocol):
    """O que todo conector faz: transformar a entrada de fora em agendamentos."""

    @property
    def origem(self) -> Origem:
        """De onde vêm os agendamentos (vai em cada um, junto com o código externo)."""
        ...

    def ler(self, entrada: Entrada) -> Iterable[Lido | Recusado]:
        """Cada item da entrada, entendido ou recusado."""
        ...


def ler_dados(onde: str, campos: Mapping[str, object]) -> Lido | Recusado:
    """Confere os campos de um item contra o formato interno.

    Returns:
        O ``Lido``, ou o ``Recusado`` com todos os motivos juntos (separados por ``;``).
    """
    try:
        return Lido(onde=onde, dados=DadosDoAgendamento.model_validate(dict(campos)))
    except ValidationError as erro:
        return Recusado(onde=onde, motivo="; ".join(descrever_erros(erro)))

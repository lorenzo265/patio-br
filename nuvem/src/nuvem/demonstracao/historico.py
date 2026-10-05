"""Os dias inventados da demonstração (D-49): chegadas, chamadas, docas e saídas, sem banco.

Um dia é uma pequena simulação: os caminhões chegam das 6h às 19h (mais de manhã cedo e no começo
da tarde); cada um fica pronto para ser chamado depois da reação do site (o check-in, a conferência)
e vai para a primeira doca que ficar livre. A espera sai da fila de verdade: quando as docas
lotam, ela cresce. O ritmo "antes do sistema" reage mais devagar e não tem check-in automático:
é dele que sai a linha de base de exemplo.

Tudo vem de um ``random.Random``: a mesma semente dá o mesmo dia.
"""

import random
import string
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from nuvem.agendamento.formato import Tipo

PESO_DAS_HORAS = {6: 3, 7: 7, 8: 9, 9: 9, 10: 7, 11: 5, 12: 4, 13: 6, 14: 8, 15: 8, 16: 6,
                  17: 4, 18: 3}  # fmt: skip
"""Quantos caminhões chegam em cada hora, em proporção."""


@dataclass(frozen=True)
class Ritmo:
    """Como o site trabalha, da chegada à doca."""

    reacao_minima: timedelta
    """Da chegada até o caminhão poder ser chamado (o check-in)."""
    reacao_maxima: timedelta
    deslocamento_minimo: timedelta
    """Da chamada até o caminhão encostar na doca."""
    deslocamento_maximo: timedelta
    giro: timedelta
    """Da saída de um caminhão da doca até ela receber o próximo."""
    automatica: float
    """A parte dos check-ins que o sistema faz sozinho."""


COM_O_SISTEMA = Ritmo(
    reacao_minima=timedelta(minutes=3), reacao_maxima=timedelta(minutes=12),
    deslocamento_minimo=timedelta(minutes=4), deslocamento_maximo=timedelta(minutes=10),
    giro=timedelta(minutes=5), automatica=0.93,
)  # fmt: skip
ANTES = Ritmo(
    reacao_minima=timedelta(minutes=20), reacao_maxima=timedelta(minutes=45),
    deslocamento_minimo=timedelta(minutes=10), deslocamento_maximo=timedelta(minutes=25),
    giro=timedelta(minutes=15), automatica=0.0,
)  # fmt: skip
"""Check-in no papel, chamada pelo rádio e doca parada esperando: a linha de base."""


@dataclass(frozen=True)
class Jornada:
    """Um caminhão num dia inventado, da chegada à saída."""

    placa: str
    tipo: Tipo
    toneladas: Decimal | None
    janela_inicio: datetime
    janela_fim: datetime
    chegada: datetime
    chamada: datetime
    inicio: datetime
    fim: datetime
    saida: datetime
    doca: int
    """A posição da doca (0 é a primeira)."""
    automatica: bool


def jornadas_do_dia(
    dia: date,
    *,
    fuso: ZoneInfo,
    docas: int,
    caminhoes: int,
    ritmo: Ritmo,
    gerador: random.Random,
    placas_usadas: set[str],
) -> list[Jornada]:
    """Os caminhões de um dia, pela ordem de chegada.

    ``placas_usadas`` evita repetir placa entre os dias; as novas entram nele.
    """
    chegadas = sorted(_chegada(dia, fuso, gerador) for _ in range(caminhoes))
    livre = [datetime.combine(dia, time(6), fuso)] * docas
    jornadas = []
    for chegada in chegadas:
        tipo: Tipo = "descarga" if gerador.random() < 0.6 else "carga"
        pronto = chegada + _entre(gerador, ritmo.reacao_minima, ritmo.reacao_maxima)
        doca = min(range(docas), key=lambda d: livre[d])
        chamada = max(pronto, livre[doca])
        inicio = chamada + _entre(gerador, ritmo.deslocamento_minimo, ritmo.deslocamento_maximo)
        servico = (timedelta(minutes=50), timedelta(minutes=100)) if tipo == "descarga" else (
            timedelta(minutes=40), timedelta(minutes=80))  # fmt: skip
        fim = inicio + _entre(gerador, *servico)
        livre[doca] = fim + ritmo.giro
        janela = _janela(chegada, gerador)
        jornadas.append(
            Jornada(
                placa=placa_inventada(gerador, placas_usadas),
                tipo=tipo,
                toneladas=toneladas_inventadas(gerador),
                janela_inicio=janela,
                janela_fim=janela + timedelta(hours=2),
                chegada=chegada,
                chamada=chamada,
                inicio=inicio,
                fim=fim,
                saida=fim + _entre(gerador, timedelta(minutes=5), timedelta(minutes=15)),
                doca=doca,
                automatica=gerador.random() < ritmo.automatica,
            )
        )
    return jornadas


def placa_inventada(gerador: random.Random, usadas: set[str]) -> str:
    """Uma placa Mercosul (ABC1D23) que ainda não foi usada; ela entra em ``usadas``."""
    while True:
        letras = "".join(gerador.choices(string.ascii_uppercase, k=3))
        placa = f"{letras}{gerador.randint(0, 9)}{gerador.choice(string.ascii_uppercase)}"
        placa += f"{gerador.randint(0, 99):02d}"
        if placa not in usadas:
            usadas.add(placa)
            return placa


def _chegada(dia: date, fuso: ZoneInfo, gerador: random.Random) -> datetime:
    hora = gerador.choices(list(PESO_DAS_HORAS), weights=list(PESO_DAS_HORAS.values()))[0]
    return datetime.combine(dia, time(hora, gerador.randint(0, 59), gerador.randint(0, 59)), fuso)


def _janela(chegada: datetime, gerador: random.Random) -> datetime:
    """O início da janela de 2 horas: quase sempre a chegada cai dentro dela."""
    cheia = chegada.replace(minute=0, second=0, microsecond=0)
    return cheia - timedelta(hours=gerador.choices((0, 1, 2, -1), weights=(5, 4, 1, 1))[0])


def toneladas_inventadas(gerador: random.Random) -> Decimal | None:
    """De 8 a 32 toneladas; de vez em quando, sem (o extrato conta quantas ficaram sem)."""
    if gerador.random() < 0.04:
        return None
    return Decimal(gerador.randint(80, 320)) / 10


def _entre(gerador: random.Random, menor: timedelta, maior: timedelta) -> timedelta:
    segundos = gerador.randint(int(menor.total_seconds()), int(maior.total_seconds()))
    return timedelta(seconds=segundos)

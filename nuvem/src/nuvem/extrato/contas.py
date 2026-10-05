"""As contas do extrato, sem banco (SDD 5.4, versão 1 da regra, D-48).

- **Quem entra:** as visitas que chegaram no período ``[de, ate)``.
- **Espera:** da chegada à (última) chamada. **Estadia:** da chegada à liberação na doca; quem saiu
  sem passar pela doca não tem estadia.
- **Exposição a estadia:** os minutos acima da franquia vezes as toneladas e o valor; sem
  toneladas, a visita fica fora da soma e é contada.
- **Uso das docas:** do início ao fim na doca (ou à saída, ou ao fim do período), dentro do
  período, dividido pelas horas disponíveis (as docas vezes as horas de operação).
- **Economia:** a estadia por visita liberada contra a linha de base, a portaria pelos postos e,
  com o custo hora-doca, as horas de doca a mais.

Dinheiro em centavos e porcentagens com uma casa, arredondados para cima a partir da metade.
"""

from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

VERSAO_DA_REGRA = 1
"""Muda quando uma conta muda: o extrato guardado diz com qual foi feito."""

VALOR_DA_ESTADIA = Decimal("2.50")
"""R$ por tonelada e hora acima da franquia, em 2026 (SDD 5.4)."""
FRANQUIA = timedelta(hours=5)
"""Lei 11.442: a estadia conta o que passa de 5 horas desde a chegada."""

CENTAVO = Decimal("0.01")
DECIMO = Decimal("0.1")
HORA = Decimal(3600)


@dataclass(frozen=True)
class VisitaMedida:
    """O que as contas precisam de uma visita."""

    chegou_em: datetime
    chamada_em: datetime | None = None
    na_doca_em: datetime | None = None
    liberada_em: datetime | None = None
    saiu_em: datetime | None = None
    toneladas: Decimal | None = None
    automatica: bool = False
    """O check-in foi feito pelo sistema, sem pessoa (D-46)."""


@dataclass(frozen=True)
class Parametros:
    """Os números do site para o extrato (``ParametrosSite``)."""

    valor_da_estadia: Decimal = VALOR_DA_ESTADIA
    franquia: timedelta = FRANQUIA
    postos_antes: Decimal | None = None
    """Pontos de portaria 24 horas antes do sistema."""
    postos_depois: Decimal | None = None
    custo_mensal_do_posto: Decimal | None = None
    custo_hora_doca: Decimal | None = None


@dataclass(frozen=True)
class Medidas:
    """As medidas de um período (do mês ou da linha de base), em totais; as médias saem deles."""

    visitas: int
    automaticas: int
    chamadas: int
    espera_total: timedelta
    liberadas: int
    estadia_total: timedelta
    acima_da_franquia: int
    exposicao: Decimal
    """R$, das liberadas com toneladas."""
    sem_toneladas: int
    """Liberadas acima da franquia sem toneladas: ficaram fora da exposição."""
    horas_de_doca: Decimal
    horas_disponiveis: Decimal

    @property
    def pct_automatico(self) -> Decimal | None:
        return _porcentagem(self.automaticas, self.visitas)

    @property
    def espera_media(self) -> timedelta | None:
        return self.espera_total / self.chamadas if self.chamadas else None

    @property
    def estadia_media(self) -> timedelta | None:
        return self.estadia_total / self.liberadas if self.liberadas else None

    @property
    def pct_acima_da_franquia(self) -> Decimal | None:
        return _porcentagem(self.acima_da_franquia, self.liberadas)

    @property
    def exposicao_por_liberada(self) -> Decimal | None:
        if not self.liberadas:
            return None
        return _reais(self.exposicao / self.liberadas)

    @property
    def uso_das_docas(self) -> Decimal | None:
        if not self.horas_disponiveis:
            return None
        return _um_decimo(self.horas_de_doca * 100 / self.horas_disponiveis)

    def para_json(self) -> dict[str, Any]:
        """Para guardar: tempos em segundos e dinheiro e horas como texto (sem perder casas)."""
        valores = asdict(self)
        for campo, valor in valores.items():
            if isinstance(valor, timedelta):
                valores[campo] = int(valor.total_seconds())
            elif isinstance(valor, Decimal):
                valores[campo] = str(valor)
        return valores

    @classmethod
    def de_json(cls, dados: dict[str, Any]) -> "Medidas":
        """O contrário de ``para_json``."""
        valores: dict[str, Any] = {}
        for campo in fields(cls):
            valor = dados[campo.name]
            if campo.type is timedelta:
                valor = timedelta(seconds=valor)
            elif campo.type is Decimal:
                valor = Decimal(valor)
            valores[campo.name] = valor
        return cls(**valores)


@dataclass(frozen=True)
class Economia:
    """O que o mês poupou contra a linha de base; vazio = não dá para calcular."""

    estadia: Decimal | None
    portaria: Decimal | None
    docas: Decimal | None
    horas_de_espera: Decimal | None
    """Em horas, sem valor em R$."""

    @property
    def total(self) -> Decimal:
        """A soma do que tem valor em R$."""
        partes = (self.estadia, self.portaria, self.docas)
        return sum((parte for parte in partes if parte is not None), Decimal("0.00"))


# --- Medir ------------------------------------------------------------------------------------


def medir(
    visitas: Iterable[VisitaMedida],
    *,
    de: datetime,
    ate: datetime,
    parametros: Parametros,
    horas_disponiveis: Decimal,
) -> Medidas:
    """As medidas do período ``[de, ate)``.

    ``visitas`` traz as que chegaram no período e as que usaram uma doca nele (mesmo tendo
    chegado antes); só as primeiras contam como visitas do período.
    """
    lista = list(visitas)
    do_periodo = [v for v in lista if de <= v.chegou_em < ate]
    chamadas = [v.chamada_em - v.chegou_em for v in do_periodo if v.chamada_em is not None]
    liberadas = [v for v in do_periodo if v.liberada_em is not None]
    estadias = [(v, v.liberada_em - v.chegou_em) for v in liberadas if v.liberada_em is not None]
    acima = [(v, estadia) for v, estadia in estadias if estadia > parametros.franquia]
    exposicao = sum(
        (
            _horas_por_minuto(estadia - parametros.franquia) * v.toneladas
            * parametros.valor_da_estadia
            for v, estadia in acima
            if v.toneladas is not None
        ),
        Decimal(0),
    )  # fmt: skip
    return Medidas(
        visitas=len(do_periodo),
        automaticas=sum(v.automatica for v in do_periodo),
        chamadas=len(chamadas),
        espera_total=sum(chamadas, timedelta(0)),
        liberadas=len(estadias),
        estadia_total=sum((estadia for _, estadia in estadias), timedelta(0)),
        acima_da_franquia=len(acima),
        exposicao=_reais(exposicao),
        sem_toneladas=sum(v.toneladas is None for v, _ in acima),
        horas_de_doca=_um_decimo(sum((_na_doca(v, de, ate) for v in lista), Decimal(0))),
        horas_disponiveis=horas_disponiveis,
    )


def horas_disponiveis(
    de: datetime,
    ate: datetime,
    *,
    fuso: ZoneInfo,
    abre: time | None,
    fecha: time | None,
    docas: int,
) -> Decimal:
    """As docas vezes as horas de operação do site em ``[de, ate)``; sem horário, 24 horas."""
    if abre is None or fecha is None:
        return _horas(ate - de) * docas
    total = timedelta(0)
    # Começa na véspera: o horário de ontem pode passar da meia-noite.
    dia = de.astimezone(fuso).date() - timedelta(days=1)
    while dia <= ate.astimezone(fuso).date():
        inicio, fim = _janela_de_operacao(dia, fuso, abre, fecha)
        total += max(min(fim, ate) - max(inicio, de), timedelta(0))
        dia += timedelta(days=1)
    return _horas(total) * docas


# --- Comparar ---------------------------------------------------------------------------------


def economizar(
    mes: Medidas, base: Medidas, parametros: Parametros, *, fracao_do_mes: Decimal
) -> Economia:
    """A economia do mês contra a linha de base.

    ``fracao_do_mes`` é a parte do mês já passada (1 no mês fechado): a portaria é proporcional.
    """
    return Economia(
        estadia=_estadia_evitada(mes, base),
        portaria=_portaria(parametros, fracao_do_mes),
        docas=_docas(mes, base, parametros),
        horas_de_espera=_horas_de_espera(mes, base),
    )


def _estadia_evitada(mes: Medidas, base: Medidas) -> Decimal | None:
    if not base.liberadas:
        return None
    if not mes.liberadas:
        return Decimal("0.00")
    por_visita = base.exposicao / base.liberadas - mes.exposicao / mes.liberadas
    return _reais(por_visita * mes.liberadas)


def _portaria(parametros: Parametros, fracao_do_mes: Decimal) -> Decimal | None:
    antes, depois = parametros.postos_antes, parametros.postos_depois
    custo = parametros.custo_mensal_do_posto
    if antes is None or depois is None or custo is None:
        return None
    return _reais((antes - depois) * custo * fracao_do_mes)


def _docas(mes: Medidas, base: Medidas, parametros: Parametros) -> Decimal | None:
    custo = parametros.custo_hora_doca
    if custo is None or not mes.horas_disponiveis or not base.horas_disponiveis:
        return None
    uso_a_mais = (
        mes.horas_de_doca / mes.horas_disponiveis - base.horas_de_doca / base.horas_disponiveis
    )
    return _reais(uso_a_mais * mes.horas_disponiveis * custo)


def _horas_de_espera(mes: Medidas, base: Medidas) -> Decimal | None:
    if mes.espera_media is None or base.espera_media is None:
        return None
    poupada = _horas(base.espera_media - mes.espera_media) * mes.chamadas
    return _um_decimo(poupada)


# --- Por dentro -------------------------------------------------------------------------------


def _na_doca(visita: VisitaMedida, de: datetime, ate: datetime) -> Decimal:
    if visita.na_doca_em is None:
        return Decimal(0)
    fim = visita.liberada_em or visita.saiu_em or ate
    return _horas(max(min(fim, ate) - max(visita.na_doca_em, de), timedelta(0)))


def _janela_de_operacao(
    dia: date, fuso: ZoneInfo, abre: time, fecha: time
) -> tuple[datetime, datetime]:
    inicio = datetime.combine(dia, abre, fuso)
    fim_no_dia = dia if fecha > abre else dia + timedelta(days=1)
    return inicio, datetime.combine(fim_no_dia, fecha, fuso)


def _horas(tempo: timedelta) -> Decimal:
    return Decimal(int(tempo.total_seconds())) / HORA


def _horas_por_minuto(tempo: timedelta) -> Decimal:
    """As horas contadas em minutos inteiros (o minuto começado não conta)."""
    return Decimal(int(tempo.total_seconds()) // 60) / 60


def _reais(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, ROUND_HALF_UP)


def _um_decimo(valor: Decimal) -> Decimal:
    return valor.quantize(DECIMO, ROUND_HALF_UP)


def _porcentagem(parte: int, todo: int) -> Decimal | None:
    if not todo:
        return None
    return _um_decimo(Decimal(parte) * 100 / todo)

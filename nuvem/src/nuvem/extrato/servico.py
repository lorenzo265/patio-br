"""O extrato e o painel de um site (SDD 5.4, 6.2 e D-48).

- **Mês fechado:** calculado na primeira vez que é pedido e guardado com a versão da regra, os
  parâmetros e a linha de base usados; depois, vem do que foi guardado.
- **Mês em curso:** parcial, até agora, e a portaria proporcional; não se guarda.
- **Painel:** o dia, o mês até agora e cada dia do mês, de uma leitura só das visitas.

O módulo lê as visitas, os agendamentos e o cadastro pelas funções de serviço deles (SDD 3.3).
Quem lê passa o ``Acesso``; a semente grava pelos ``gravar_*``.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nuvem.agendamento import servico as agendamentos
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.modelos import Site
from nuvem.extrato import contas
from nuvem.extrato.contas import Economia, Medidas, Parametros, VisitaMedida
from nuvem.extrato.modelos import Extrato, LinhaDeBase, OrigemDaLinhaDeBase, ParametrosSite
from nuvem.portaria import visitas


class MesFuturoError(ValueError):
    """O mês ainda não começou no site."""


@dataclass(frozen=True)
class LinhaDeBaseLida:
    """A linha de base de um site, com a origem (exemplo ou modo sombra)."""

    origem: OrigemDaLinhaDeBase
    de: datetime
    ate: datetime
    medidas: Medidas


@dataclass(frozen=True)
class ExtratoDoMes:
    """O extrato de um mês: fechado (guardado) ou parcial (até agora)."""

    mes: date
    de: datetime
    ate: datetime
    """O fim do mês, ou agora, no mês em curso."""
    parcial: bool
    medidas: Medidas
    linha_de_base: LinhaDeBaseLida | None
    economia: Economia | None
    """Vazia sem linha de base."""
    parametros: Parametros
    versao_da_regra: int
    guardado_em: datetime | None


@dataclass(frozen=True)
class Dia:
    """As medidas de um dia (no fuso do site)."""

    dia: date
    medidas: Medidas


@dataclass(frozen=True)
class Painel:
    """O dia, o mês até agora e cada dia do mês."""

    hoje: Medidas
    mes: ExtratoDoMes
    dias: list[Dia]


@dataclass(frozen=True)
class _Site:
    """O que as contas precisam do site, lido uma vez."""

    site: Site
    fuso: ZoneInfo
    docas: int
    parametros: Parametros
    linha_de_base: LinhaDeBaseLida | None

    def horas_disponiveis(self, de: datetime, ate: datetime) -> Decimal:
        return contas.horas_disponiveis(
            de, ate, fuso=self.fuso, abre=self.site.abre, fecha=self.site.fecha, docas=self.docas
        )

    def meia_noite(self, dia: date) -> datetime:
        return datetime.combine(dia, time(0), self.fuso)


# --- Ler --------------------------------------------------------------------------------------


def parametros(sessao: Session, acesso: Acesso, site_id: int) -> Parametros:
    """Os parâmetros do extrato de um site que o usuário vê (sem eles, os da lei).

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    return _parametros(sessao, site)


def do_mes(
    sessao: Session, acesso: Acesso, site_id: int, mes: date, *, agora: datetime
) -> ExtratoDoMes:
    """O extrato de um mês de um site que o usuário vê (``mes``: qualquer dia dele).

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
        MesFuturoError: se o mês ainda não começou.
    """
    lugar = _ler_site(sessao, acesso, site_id)
    primeiro = mes.replace(day=1)
    de, fim = lugar.meia_noite(primeiro), lugar.meia_noite(_mes_seguinte(primeiro))
    if agora < de:
        raise MesFuturoError(f"{primeiro:%m/%Y} ainda não começou")
    if agora < fim:
        lista = _visitas(sessao, acesso, lugar, de, agora)
        return _extrato(lugar, primeiro, de, fim, agora, lista, guardado_em=None)
    guardado = _guardado(sessao, acesso, lugar.site, primeiro)
    if guardado is None:
        lista = _visitas(sessao, acesso, lugar, de, fim)
        calculado = _extrato(lugar, primeiro, de, fim, fim, lista, guardado_em=agora)
        _guardar(sessao, lugar.site, calculado)
        guardado = _guardado(sessao, acesso, lugar.site, primeiro)
        if guardado is None:  # pragma: no cover - acabou de ser gravado e não some
            raise RuntimeError("o extrato guardado não foi encontrado")
    return _ler_extrato(guardado)


def painel(sessao: Session, acesso: Acesso, site_id: int, *, agora: datetime) -> Painel:
    """O painel de um site que o usuário vê: hoje, o mês até agora e cada dia do mês.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    lugar = _ler_site(sessao, acesso, site_id)
    hoje = agora.astimezone(lugar.fuso).date()
    primeiro = hoje.replace(day=1)
    de, fim = lugar.meia_noite(primeiro), lugar.meia_noite(_mes_seguinte(primeiro))
    lista = _visitas(sessao, acesso, lugar, de, agora)
    dias = []
    for numero in range(hoje.day):
        dia = primeiro + timedelta(days=numero)
        inicio, seguinte = lugar.meia_noite(dia), lugar.meia_noite(dia + timedelta(days=1))
        dias.append(Dia(dia, _medir(lugar, lista, inicio, min(seguinte, agora))))
    mes = _extrato(lugar, primeiro, de, fim, agora, lista, guardado_em=None)
    return Painel(hoje=dias[-1].medidas, mes=mes, dias=dias)


# --- Gravar (a semente e, depois, a administração) --------------------------------------------


def gravar_parametros(
    sessao: Session, site: Site, parametros: Parametros, *, agora: datetime
) -> None:
    """Grava (ou troca) os parâmetros do extrato de um site."""
    valores = {
        "valor_da_estadia": parametros.valor_da_estadia,
        "franquia_minutos": int(parametros.franquia.total_seconds() // 60),
        "postos_antes": parametros.postos_antes,
        "postos_depois": parametros.postos_depois,
        "custo_mensal_do_posto": parametros.custo_mensal_do_posto,
        "custo_hora_doca": parametros.custo_hora_doca,
        "atualizado_em": agora,
    }
    sessao.execute(
        insert(ParametrosSite)
        .values(empresa_id=site.empresa_id, site_id=site.id, **valores)
        .on_conflict_do_update(index_elements=["site_id"], set_=valores)
    )


def gravar_linha_de_base(
    sessao: Session,
    site: Site,
    origem: OrigemDaLinhaDeBase,
    *,
    de: datetime,
    ate: datetime,
    medidas: Medidas,
    agora: datetime,
) -> None:
    """Grava (ou troca) a linha de base de um site."""
    valores = {"origem": origem, "de": de, "ate": ate, "medidas": medidas.para_json(),
               "gravada_em": agora}  # fmt: skip
    sessao.execute(
        insert(LinhaDeBase)
        .values(empresa_id=site.empresa_id, site_id=site.id, **valores)
        .on_conflict_do_update(index_elements=["site_id"], set_=valores)
    )


# --- Por dentro -------------------------------------------------------------------------------


def _ler_site(sessao: Session, acesso: Acesso, site_id: int) -> _Site:
    site = cadastro.obter_site(sessao, acesso, site_id)
    return _Site(
        site=site,
        fuso=ZoneInfo(site.fuso),
        docas=len(cadastro.listar_docas(sessao, acesso, site.id)),
        parametros=_parametros(sessao, site),
        linha_de_base=_linha_de_base(sessao, site),
    )


def _parametros(sessao: Session, site: Site) -> Parametros:
    linha = sessao.scalars(
        select(ParametrosSite).where(
            ParametrosSite.empresa_id == site.empresa_id, ParametrosSite.site_id == site.id
        )
    ).one_or_none()
    if linha is None:
        return Parametros()
    return Parametros(
        valor_da_estadia=linha.valor_da_estadia,
        franquia=timedelta(minutes=linha.franquia_minutos),
        postos_antes=linha.postos_antes,
        postos_depois=linha.postos_depois,
        custo_mensal_do_posto=linha.custo_mensal_do_posto,
        custo_hora_doca=linha.custo_hora_doca,
    )


def _linha_de_base(sessao: Session, site: Site) -> LinhaDeBaseLida | None:
    linha = sessao.scalars(
        select(LinhaDeBase).where(
            LinhaDeBase.empresa_id == site.empresa_id, LinhaDeBase.site_id == site.id
        )
    ).one_or_none()
    if linha is None:
        return None
    return LinhaDeBaseLida(linha.origem, linha.de, linha.ate, Medidas.de_json(linha.medidas))


def _visitas(
    sessao: Session, acesso: Acesso, lugar: _Site, de: datetime, ate: datetime
) -> list[VisitaMedida]:
    lidas = visitas.para_o_extrato(sessao, acesso, lugar.site.id, de=de, ate=ate)
    ids = [v.agendamento_id for v, _ in lidas if v.agendamento_id is not None]
    resumos = agendamentos.resumos(sessao, acesso, ids)
    medidas = []
    for visita, automatica in lidas:
        resumo = resumos.get(visita.agendamento_id or 0)
        if visita.chegou_em is None:  # pragma: no cover - o "não veio" não vem
            continue
        medidas.append(
            VisitaMedida(
                chegou_em=visita.chegou_em,
                chamada_em=visita.chamada_em,
                na_doca_em=visita.na_doca_em,
                liberada_em=visita.liberada_em,
                saiu_em=visita.saiu_em,
                toneladas=resumo.toneladas if resumo else None,
                automatica=automatica,
            )
        )
    return medidas


def _medir(lugar: _Site, lista: list[VisitaMedida], de: datetime, ate: datetime) -> Medidas:
    return contas.medir(
        lista, de=de, ate=ate, parametros=lugar.parametros,
        horas_disponiveis=lugar.horas_disponiveis(de, ate),
    )  # fmt: skip


def _extrato(
    lugar: _Site,
    mes: date,
    de: datetime,
    fim: datetime,
    ate: datetime,
    lista: list[VisitaMedida],
    *,
    guardado_em: datetime | None,
) -> ExtratoDoMes:
    medidas = _medir(lugar, lista, de, ate)
    base = lugar.linha_de_base
    economia = None
    if base is not None:
        fracao = Decimal(int((ate - de).total_seconds())) / Decimal(int((fim - de).total_seconds()))
        economia = contas.economizar(medidas, base.medidas, lugar.parametros, fracao_do_mes=fracao)
    return ExtratoDoMes(
        mes=mes, de=de, ate=ate, parcial=ate < fim, medidas=medidas, linha_de_base=base,
        economia=economia, parametros=lugar.parametros, versao_da_regra=contas.VERSAO_DA_REGRA,
        guardado_em=guardado_em,
    )  # fmt: skip


def _guardado(sessao: Session, acesso: Acesso, site: Site, mes: date) -> Extrato | None:
    return sessao.scalars(
        select(Extrato).where(
            Extrato.empresa_id == acesso.empresa_id,
            Extrato.site_id == site.id,
            Extrato.mes == mes,
            Extrato.versao_da_regra == contas.VERSAO_DA_REGRA,
        )
    ).one_or_none()


def _guardar(sessao: Session, site: Site, extrato: ExtratoDoMes) -> None:
    # Dois pedidos ao mesmo tempo: o banco fica com um, e os dois leem o mesmo.
    sessao.execute(
        insert(Extrato)
        .values(
            empresa_id=site.empresa_id,
            site_id=site.id,
            mes=extrato.mes,
            versao_da_regra=extrato.versao_da_regra,
            numeros=_numeros(extrato),
            guardado_em=extrato.guardado_em,
        )
        .on_conflict_do_nothing(index_elements=["site_id", "mes", "versao_da_regra"])
    )


def _numeros(extrato: ExtratoDoMes) -> dict[str, Any]:
    base = extrato.linha_de_base
    return {
        "de": extrato.de.isoformat(),
        "ate": extrato.ate.isoformat(),
        "medidas": extrato.medidas.para_json(),
        "parametros": _em_texto(asdict(extrato.parametros)),
        "linha_de_base": None if base is None else {
            "origem": base.origem, "de": base.de.isoformat(), "ate": base.ate.isoformat(),
            "medidas": base.medidas.para_json(),
        },
        "economia": None if extrato.economia is None else _em_texto(asdict(extrato.economia)),
    }  # fmt: skip


def _ler_extrato(guardado: Extrato) -> ExtratoDoMes:
    numeros = guardado.numeros
    base = numeros["linha_de_base"]
    economia = numeros["economia"]
    parametros = numeros["parametros"]
    return ExtratoDoMes(
        mes=guardado.mes,
        de=datetime.fromisoformat(numeros["de"]),
        ate=datetime.fromisoformat(numeros["ate"]),
        parcial=False,
        medidas=Medidas.de_json(numeros["medidas"]),
        linha_de_base=None if base is None else LinhaDeBaseLida(
            base["origem"], datetime.fromisoformat(base["de"]),
            datetime.fromisoformat(base["ate"]), Medidas.de_json(base["medidas"]),
        ),
        economia=None if economia is None else Economia(
            **{campo: _decimal(valor) for campo, valor in economia.items()}
        ),
        parametros=Parametros(
            valor_da_estadia=Decimal(parametros["valor_da_estadia"]),
            franquia=timedelta(seconds=parametros["franquia"]),
            **{
                campo: _decimal(parametros[campo])
                for campo in ("postos_antes", "postos_depois", "custo_mensal_do_posto",
                              "custo_hora_doca")
            },
        ),
        versao_da_regra=guardado.versao_da_regra,
        guardado_em=guardado.guardado_em,
    )  # fmt: skip


def _em_texto(valores: dict[str, Any]) -> dict[str, Any]:
    """Decimal como texto (sem perder casas) e tempo em segundos, para o JSON."""
    convertidos: dict[str, Any] = {}
    for campo, valor in valores.items():
        if isinstance(valor, Decimal):
            convertidos[campo] = str(valor)
        elif isinstance(valor, timedelta):
            convertidos[campo] = int(valor.total_seconds())
        else:
            convertidos[campo] = valor
    return convertidos


def _decimal(valor: str | None) -> Decimal | None:
    return None if valor is None else Decimal(valor)


def _mes_seguinte(primeiro: date) -> date:
    return (primeiro + timedelta(days=32)).replace(day=1)

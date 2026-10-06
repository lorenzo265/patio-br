"""Regras do agendamento (SDD 3.4, 5.1 e 5.5).

- **Quem grava** é um conector, para um site: ``SiteDoAgendamento`` diz qual (e quem, se for uma
  pessoa do cliente). Para o usuário do cliente, ele nasce de ``site_para_agendar``, que confere
  o ``Acesso``; o link da transportadora tem o seu.
- **Reenvio atualiza** (D-33): o mesmo código externo, pela mesma origem, no mesmo site, muda o
  agendamento que já existe; reenviar igual não muda nada.
- **Cada mudança fica registrada** (``MudancaAgendamento``), inclusive a criação e o
  cancelamento. Trocar o celular apaga a autorização de WhatsApp, que é do número.
- **Cancelado não volta** pelo reenvio: o conector recebe a recusa.
- **Quem lê** passa o ``Acesso``: só vê os sites dele, da empresa dele; o resto "não existe".

As funções gravam com ``flush``; o ``commit`` é de quem chama.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nuvem.agendamento.conectores import Conector, Recusado
from nuvem.agendamento.formato import DadosDoAgendamento, Tipo
from nuvem.agendamento.modelos import (
    Agendamento,
    MudancaAgendamento,
    Origem,
    TipoDeMudanca,
    Via,
)
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso
from nuvem.erros import NaoEncontradoError

CAMPOS = tuple(campo for campo in DadosDoAgendamento.model_fields if campo != "codigo_externo")
"""Os campos que um reenvio pode mudar (o código externo é o que identifica o agendamento)."""

Resultado = Literal["criado", "alterado", "igual"]


@dataclass(frozen=True)
class SiteDoAgendamento:
    """O site onde o conector grava, e quem está gravando: uma pessoa do cliente ou um link."""

    empresa_id: int
    site_id: int
    usuario_id: int | None
    link_id: int | None = None
    """O link da transportadora, quando é ele que grava (vai no agendamento criado)."""


@dataclass(frozen=True)
class Gravado:
    """O agendamento depois de gravado, e o que aconteceu com ele."""

    agendamento: Agendamento
    resultado: Resultado


@dataclass
class Relatorio:
    """O resultado de uma importação: quantos entraram, mudaram ou já estavam iguais, e as
    recusas, cada uma com o lugar e o motivo."""

    criados: int = 0
    alterados: int = 0
    iguais: int = 0
    recusados: list[Recusado] = field(default_factory=list)


class AgendamentoCanceladoError(Exception):
    """O reenvio é de um agendamento que foi cancelado no painel: ele não volta assim."""

    def __init__(self, codigo_externo: str) -> None:
        super().__init__(f"o agendamento {codigo_externo} foi cancelado no painel")


# --- Gravar -----------------------------------------------------------------------------------


def site_para_agendar(sessao: Session, acesso: Acesso, site_id: int) -> SiteDoAgendamento:
    """O site onde o usuário vai gravar agendamentos (ex.: a planilha que o gestor sobe).

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    return SiteDoAgendamento(
        empresa_id=site.empresa_id, site_id=site.id, usuario_id=acesso.usuario_id
    )


def gravar(
    sessao: Session,
    site: SiteDoAgendamento,
    origem: Origem,
    dados: DadosDoAgendamento,
    *,
    agora: datetime,
) -> Gravado:
    """Cria o agendamento ou, se o código externo já existe nesta origem e site, atualiza.

    Raises:
        AgendamentoCanceladoError: se o agendamento com este código foi cancelado.
    """
    existente = _travar(sessao, site, origem, dados.codigo_externo)
    if existente is None:
        valores = _valores(dados)
        novo_id = sessao.scalar(
            insert(Agendamento)
            .values(
                empresa_id=site.empresa_id,
                site_id=site.site_id,
                origem=origem,
                codigo_externo=dados.codigo_externo,
                situacao="ativo",
                link_id=site.link_id,
                criado_em=agora,
                atualizado_em=agora,
                **valores,
            )
            # O mesmo código chegando duas vezes ao mesmo tempo: só um entra.
            .on_conflict_do_nothing(index_elements=["site_id", "origem", "codigo_externo"])
            .returning(Agendamento.id)
        )
        if novo_id is not None:
            agendamento = sessao.get_one(Agendamento, novo_id)
            depois = {"codigo_externo": dados.codigo_externo} | _em_json(valores)
            _registrar(sessao, site, origem, agendamento, "criado", None, depois, agora)
            return Gravado(agendamento, "criado")
        existente = _travar(sessao, site, origem, dados.codigo_externo)
        if existente is None:  # pragma: no cover - o outro acabou de gravar e não some
            raise RuntimeError("o agendamento gravado ao mesmo tempo não foi encontrado")
    return _atualizar(sessao, site, origem, existente, dados, agora)


@dataclass(frozen=True)
class AgendamentoInventado:
    """Um agendamento inventado para a demonstração (D-49): sem motorista, com o celular de um DDD
    que não existe (por isso não passa pelo ``DadosDoAgendamento``, que recusa o DDD)."""

    codigo_externo: str
    janela_inicio: datetime
    janela_fim: datetime
    tipo: Tipo
    placa_cavalo: str
    toneladas: Decimal | None
    motorista_celular: str


def gravar_inventados(
    sessao: Session, site: SiteDoAgendamento, lista: Sequence[AgendamentoInventado]
) -> list[int]:
    """Grava de uma vez os agendamentos inventados da demonstração, cada um com a mudança
    "criado" (pela planilha, um dia antes da janela). Só para a demonstração.

    Returns:
        Os ids, na ordem da ``lista``.
    """
    if not lista:
        return []
    linhas: list[dict[str, Any]] = [
        {
            "empresa_id": site.empresa_id, "site_id": site.site_id, "origem": "planilha",
            "codigo_externo": a.codigo_externo, "situacao": "ativo", "link_id": None,
            "janela_inicio": a.janela_inicio, "janela_fim": a.janela_fim, "tipo": a.tipo,
            "placa_cavalo": a.placa_cavalo, "placas_reboques": [], "motorista_nome": None,
            "motorista_celular": a.motorista_celular,
            "toneladas": a.toneladas, "chave_nfe": None,
            "criado_em": a.janela_inicio - timedelta(days=1),
            "atualizado_em": a.janela_inicio - timedelta(days=1),
        }
        for a in lista
    ]  # fmt: skip
    ids = list(
        sessao.scalars(
            insert(Agendamento).returning(Agendamento.id, sort_by_parameter_order=True), linhas
        )
    )
    sessao.execute(
        insert(MudancaAgendamento),
        [
            {
                "empresa_id": site.empresa_id, "agendamento_id": id_, "tipo": "criado",
                "momento": linha["criado_em"], "via": "planilha", "usuario_id": None,
                "antes": None, "depois": {"codigo_externo": linha["codigo_externo"]},
            }
            for id_, linha in zip(ids, linhas, strict=True)
        ],
    )  # fmt: skip
    return ids


def importar[Entrada](
    sessao: Session,
    site: SiteDoAgendamento,
    conector: Conector[Entrada],
    entrada: Entrada,
    *,
    agora: datetime,
) -> Relatorio:
    """Grava cada agendamento que o conector entendeu e junta as recusas no relatório.

    O mesmo código duas vezes na mesma entrada é recusado na segunda: é engano de quem montou a
    entrada, e não um reenvio.
    """
    relatorio = Relatorio()
    vistos: dict[str, str] = {}
    for item in conector.ler(entrada):
        if isinstance(item, Recusado):
            relatorio.recusados.append(item)
            continue
        codigo = item.dados.codigo_externo
        if codigo in vistos:
            motivo = f"o código {codigo} já apareceu em {vistos[codigo]}"
            relatorio.recusados.append(Recusado(onde=item.onde, motivo=motivo))
            continue
        vistos[codigo] = item.onde
        try:
            gravado = gravar(sessao, site, conector.origem, item.dados, agora=agora)
        except AgendamentoCanceladoError as erro:
            relatorio.recusados.append(Recusado(onde=item.onde, motivo=str(erro)))
            continue
        if gravado.resultado == "criado":
            relatorio.criados += 1
        elif gravado.resultado == "alterado":
            relatorio.alterados += 1
        else:
            relatorio.iguais += 1
    return relatorio


def cancelar(
    sessao: Session, acesso: Acesso, agendamento_id: int, *, agora: datetime
) -> Agendamento:
    """Cancela um agendamento pelo painel; cancelar de novo não muda nada.

    Raises:
        NaoEncontradoError: se o agendamento não for visível para este usuário.
    """
    agendamento = _visivel(sessao, acesso, agendamento_id, travar=True)
    if agendamento.situacao == "cancelado":
        return agendamento
    agendamento.situacao = "cancelado"
    agendamento.atualizado_em = agora
    site = SiteDoAgendamento(
        empresa_id=agendamento.empresa_id,
        site_id=agendamento.site_id,
        usuario_id=acesso.usuario_id,
    )
    antes, depois = {"situacao": "ativo"}, {"situacao": "cancelado"}
    _registrar(sessao, site, "painel", agendamento, "cancelado", antes, depois, agora)
    return agendamento


def _travar(
    sessao: Session, site: SiteDoAgendamento, origem: Origem, codigo_externo: str
) -> Agendamento | None:
    # Trava a linha: dois reenvios ao mesmo tempo mudam um depois do outro.
    return sessao.scalars(
        _do_site(site)
        .where(Agendamento.origem == origem, Agendamento.codigo_externo == codigo_externo)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()


def _atualizar(
    sessao: Session,
    site: SiteDoAgendamento,
    origem: Origem,
    agendamento: Agendamento,
    dados: DadosDoAgendamento,
    agora: datetime,
) -> Gravado:
    if agendamento.situacao == "cancelado":
        raise AgendamentoCanceladoError(dados.codigo_externo)
    antes: dict[str, Any] = {}
    depois: dict[str, Any] = {}
    for campo, valor in _valores(dados).items():
        atual = getattr(agendamento, campo)
        if atual != valor:
            antes[campo], depois[campo] = _json(atual), _json(valor)
            setattr(agendamento, campo, valor)
    if not depois:
        return Gravado(agendamento, "igual")
    agendamento.atualizado_em = agora
    _registrar(sessao, site, origem, agendamento, "alterado", antes, depois, agora)
    return Gravado(agendamento, "alterado")


def _valores(dados: DadosDoAgendamento) -> dict[str, Any]:
    valores = {campo: getattr(dados, campo) for campo in CAMPOS}
    valores["placas_reboques"] = list(dados.placas_reboques)
    return valores


def _registrar(
    sessao: Session,
    site: SiteDoAgendamento,
    via: Via,
    agendamento: Agendamento,
    tipo: TipoDeMudanca,
    antes: dict[str, Any] | None,
    depois: dict[str, Any],
    agora: datetime,
) -> None:
    sessao.add(
        MudancaAgendamento(
            empresa_id=agendamento.empresa_id,
            agendamento_id=agendamento.id,
            momento=agora,
            tipo=tipo,
            via=via,
            usuario_id=site.usuario_id,
            antes=antes,
            depois=depois,
        )
    )
    sessao.flush()


def _em_json(valores: dict[str, Any]) -> dict[str, Any]:
    return {campo: _json(valor) for campo, valor in valores.items()}


def _json(valor: object) -> object:
    # O registro da mudança é JSON: hora em UTC, número sem zeros à toa ("32.5", e não "32.500").
    if isinstance(valor, datetime):
        return valor.astimezone(UTC).isoformat()
    if isinstance(valor, Decimal):
        return format(valor.normalize(), "f")
    if isinstance(valor, tuple):
        return list(valor)
    return valor


# --- Ler --------------------------------------------------------------------------------------


def obter(sessao: Session, acesso: Acesso, agendamento_id: int) -> Agendamento:
    """Um agendamento de um site que o usuário vê.

    Raises:
        NaoEncontradoError: se não existir, ou for de outra empresa ou de um site que o usuário
            não vê.
    """
    return _visivel(sessao, acesso, agendamento_id)


def obter_por_codigo(
    sessao: Session, site: SiteDoAgendamento, origem: Origem, codigo_externo: str
) -> Agendamento:
    """O agendamento de um conector, pelo código externo, no site dele.

    Raises:
        NaoEncontradoError: se não houver agendamento com este código, nesta origem e site.
    """
    agendamento = sessao.scalars(
        _do_site(site).where(
            Agendamento.origem == origem, Agendamento.codigo_externo == codigo_externo
        )
    ).one_or_none()
    if agendamento is None:
        raise NaoEncontradoError(f"agendamento {codigo_externo} ({origem})")
    return agendamento


def ativos_perto(
    sessao: Session, *, empresa_id: int, site_id: int, momento: datetime, folga: timedelta
) -> list[Agendamento]:
    """Os agendamentos ativos de um site cuja janela, alargada pela folga, contém o momento.

    Para o casamento (SDD 5.3): quem chama já sabe o site, pela passagem da caixa.
    """
    return list(
        sessao.scalars(
            select(Agendamento)
            .where(
                Agendamento.empresa_id == empresa_id,
                Agendamento.site_id == site_id,
                Agendamento.situacao == "ativo",
                Agendamento.janela_inicio <= momento + folga,
                Agendamento.janela_fim >= momento - folga,
            )
            .order_by(Agendamento.id)
        )
    )


def ativos_que_terminaram(sessao: Session, *, de: datetime, ate: datetime) -> list[Agendamento]:
    """Os agendamentos ativos, de todos os sites, cuja janela terminou em ``[de, ate)``.

    Para o "não veio" (SDD 5.2), que o worker confere para a plataforma inteira.
    """
    return list(
        sessao.scalars(
            select(Agendamento)
            .where(
                Agendamento.situacao == "ativo",
                Agendamento.janela_fim >= de,
                Agendamento.janela_fim < ate,
            )
            .order_by(Agendamento.janela_fim, Agendamento.id)
        )
    )


def para_confirmar(
    sessao: Session, *, mudados_desde: datetime, agora: datetime
) -> list[Agendamento]:
    """Os agendamentos ativos com celular, de todos os sites, criados ou mudados desde
    ``mudados_desde`` e cuja janela ainda não terminou.

    Para a confirmação ao motorista (D-47), que o worker prepara para a plataforma inteira.
    """
    return list(
        sessao.scalars(
            select(Agendamento)
            .where(
                Agendamento.situacao == "ativo",
                Agendamento.motorista_celular.is_not(None),
                Agendamento.atualizado_em >= mudados_desde,
                Agendamento.janela_fim > agora,
            )
            .order_by(Agendamento.id)
        )
    )


def empresa_do_agendamento(sessao: Session, agendamento_id: int) -> int | None:
    """A empresa de um agendamento de qualquer site, ou ``None`` se ele não existe.

    Para a autorização do WhatsApp (D-58): o motorista manda o número do agendamento, e a
    autorização vale para a empresa dele.
    """
    return sessao.scalar(select(Agendamento.empresa_id).where(Agendamento.id == agendamento_id))


def com_celular(sessao: Session, agendamento_ids: Sequence[int]) -> dict[int, Agendamento]:
    """Os agendamentos com celular entre estes, de todos os sites, por id.

    Para os avisos ao motorista (D-47): quem chama tirou os ids dos eventos das visitas.
    """
    linhas = sessao.scalars(
        select(Agendamento).where(
            Agendamento.id.in_(agendamento_ids), Agendamento.motorista_celular.is_not(None)
        )
    )
    return {agendamento.id: agendamento for agendamento in linhas}


def listar(
    sessao: Session, acesso: Acesso, site_id: int, *, de: datetime, ate: datetime
) -> list[Agendamento]:
    """Os agendamentos de um site cuja janela toca o período ``[de, ate)``, pelo início.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    return list(
        sessao.scalars(
            select(Agendamento)
            .where(
                Agendamento.empresa_id == acesso.empresa_id,
                Agendamento.site_id == site.id,
                Agendamento.janela_inicio < ate,
                Agendamento.janela_fim > de,
            )
            .order_by(Agendamento.janela_inicio, Agendamento.id)
        )
    )


def dias_com_agendamento(
    sessao: Session, acesso: Acesso, site_id: int, *, de: datetime, ate: datetime
) -> set[date]:
    """Os dias, no fuso do site, em que começa algum agendamento do site em ``[de, ate)``.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    dia = func.date(func.timezone(site.fuso, Agendamento.janela_inicio))
    return set(
        sessao.scalars(
            select(dia)
            .where(
                Agendamento.empresa_id == acesso.empresa_id,
                Agendamento.site_id == site.id,
                Agendamento.janela_inicio >= de,
                Agendamento.janela_inicio < ate,
            )
            .distinct()
        )
    )


def codigos_externos(
    sessao: Session, acesso: Acesso, agendamento_ids: Sequence[int]
) -> dict[int, str]:
    """O código externo de cada agendamento (dos sites que o usuário vê), por id."""
    linhas = sessao.execute(
        select(Agendamento.id, Agendamento.codigo_externo).where(
            Agendamento.empresa_id == acesso.empresa_id,
            Agendamento.site_id.in_(acesso.sites),
            Agendamento.id.in_(agendamento_ids),
        )
    )
    return {agendamento_id: codigo for agendamento_id, codigo in linhas}


@dataclass(frozen=True)
class Resumo:
    """O que as telas mostram de um agendamento ao lado de uma visita."""

    codigo: str
    tipo: Tipo
    toneladas: Decimal | None


def resumos(sessao: Session, acesso: Acesso, agendamento_ids: Sequence[int]) -> dict[int, Resumo]:
    """O código, o tipo e as toneladas de cada agendamento (dos sites que o usuário vê), por id."""
    linhas = sessao.execute(
        select(
            Agendamento.id, Agendamento.codigo_externo, Agendamento.tipo, Agendamento.toneladas
        ).where(
            Agendamento.empresa_id == acesso.empresa_id,
            Agendamento.site_id.in_(acesso.sites),
            Agendamento.id.in_(agendamento_ids),
        )
    )
    return {id_: Resumo(codigo, tipo, toneladas) for id_, codigo, tipo, toneladas in linhas}


def mudancas(sessao: Session, acesso: Acesso, agendamento_id: int) -> list[MudancaAgendamento]:
    """O histórico de um agendamento que o usuário vê, da criação até agora.

    Raises:
        NaoEncontradoError: se o agendamento não for visível para este usuário.
    """
    agendamento = _visivel(sessao, acesso, agendamento_id)
    return list(
        sessao.scalars(
            select(MudancaAgendamento)
            .where(
                MudancaAgendamento.empresa_id == acesso.empresa_id,
                MudancaAgendamento.agendamento_id == agendamento.id,
            )
            .order_by(MudancaAgendamento.id)
        )
    )


def _do_site(site: SiteDoAgendamento) -> Select[Agendamento]:
    return select(Agendamento).where(
        Agendamento.empresa_id == site.empresa_id, Agendamento.site_id == site.site_id
    )


def _visivel(
    sessao: Session, acesso: Acesso, agendamento_id: int, *, travar: bool = False
) -> Agendamento:
    consulta = select(Agendamento).where(
        Agendamento.id == agendamento_id,
        Agendamento.empresa_id == acesso.empresa_id,
        Agendamento.site_id.in_(acesso.sites),
    )
    if travar:
        consulta = consulta.with_for_update().execution_options(populate_existing=True)
    agendamento = sessao.scalars(consulta).one_or_none()
    if agendamento is None:
        raise NaoEncontradoError(f"agendamento {agendamento_id}")
    return agendamento

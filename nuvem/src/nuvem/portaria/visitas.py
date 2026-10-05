"""Regras da visita (SDD 5.1, 5.2, 5.5 e D-35): a chegada vira visita, com eventos que ficam.

- **A visita nasce na chegada:** casou, ``NA_FILA``; não casou, ``EXCECAO`` (com a ``Excecao``);
  no prazo do "não veio", ``NAO_VEIO``. Antes disso, o agendamento ativo sem visita é o
  ``AGENDADA`` do diagrama.
- **Cada evento leva a um estado** (``ABRE`` e ``TRANSICOES``); um evento fora do diagrama é
  recusado (``TransicaoInvalidaError``) e nada muda.
- **O evento só se acrescenta:** o banco recusa alterar ou apagar.
- **A composição** diz, de cada placa, se foi lida pela câmera ou inferida do agendamento (D-17).
- **Quem grava** é a nuvem, a partir da passagem (o casamento) ou do porteiro (a resolução da
  exceção e a chegada manual, em ``resolucao``): ``SiteDaVisita`` diz onde. **Quem lê** passa o
  ``Acesso``.

As funções gravam com ``flush``; o ``commit`` é de quem chama.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from contratos.passagem import Papel
from contratos.placa import Placa
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso
from nuvem.erros import NaoEncontradoError
from nuvem.portaria.modelos import (
    EstadoDaVisita,
    Evento,
    Excecao,
    MotivoDaExcecao,
    TipoDeEvento,
    Visita,
)

ABRE: dict[TipoDeEvento, EstadoDaVisita] = {
    "check_in": "NA_FILA",
    "aceita_sem_agendamento": "NA_FILA",
    "excecao": "EXCECAO",
    "nao_veio": "NAO_VEIO",
}
"""Os eventos que abrem uma visita, e o estado em que ela nasce (a chegada manual abre com
``check_in`` ou ``aceita_sem_agendamento``, D-46)."""

TRANSICOES: dict[tuple[EstadoDaVisita, TipoDeEvento], EstadoDaVisita] = {
    ("NA_FILA", "saiu_sem_atendimento"): "SAIU",
    ("EXCECAO", "saiu_sem_atendimento"): "SAIU",
    ("EXCECAO", "check_in"): "NA_FILA",
    ("EXCECAO", "aceita_sem_agendamento"): "NA_FILA",
    ("EXCECAO", "recusada"): "RECUSADA",
    ("EXCECAO", "placa_corrigida"): "EXCECAO",
    ("NA_FILA", "chamada"): "CHAMADA",
    ("CHAMADA", "chamada_cancelada"): "NA_FILA",
    ("CHAMADA", "inicio_na_doca"): "NA_DOCA",
    ("NA_DOCA", "fim_na_doca"): "LIBERADA",
    ("CHAMADA", "saiu_sem_atendimento"): "SAIU",
    ("NA_DOCA", "saiu"): "SAIU",
    ("LIBERADA", "saiu"): "SAIU",
}
"""De um estado, cada evento permitido e o estado seguinte."""

ABERTOS: tuple[EstadoDaVisita, ...] = ("NA_FILA", "EXCECAO", "CHAMADA", "NA_DOCA", "LIBERADA")
"""Os estados de quem ainda está no site (a saída fecha a visita aberta da placa)."""


class TransicaoInvalidaError(ValueError):
    """O evento não cabe no estado atual da visita (SDD 5.2)."""


class PlacaNaVisita(BaseModel):
    """Uma placa da composição confirmada: o papel e se foi lida ou inferida (D-17)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    placa: Placa
    papel: Papel
    como: Literal["lida", "inferida", "digitada"]
    """Lida pela câmera, inferida do agendamento ou digitada pelo porteiro (D-46)."""


@dataclass(frozen=True)
class Candidato:
    """Um agendamento que chegou perto no casamento, com os pontos (SDD 5.3)."""

    agendamento_id: int
    pontos: int


@dataclass(frozen=True)
class SiteDaVisita:
    """O site da visita; quem grava já sabe qual é (pela passagem da caixa ou pelo agendamento)."""

    empresa_id: int
    site_id: int


# --- Gravar -----------------------------------------------------------------------------------


def abrir_visita(
    sessao: Session,
    site: SiteDaVisita,
    evento: TipoDeEvento,
    *,
    momento: datetime,
    agora: datetime,
    agendamento_id: int | None = None,
    composicao: Sequence[PlacaNaVisita] = (),
    passagem_id: UUID | None = None,
    dados: dict[str, Any] | None = None,
    usuario_id: int | None = None,
) -> Visita:
    """Abre uma visita com o primeiro evento (check-in, exceção ou "não veio").

    Raises:
        TransicaoInvalidaError: se o evento não abre visita.
        ValueError: se a composição tiver dois cavalos ou a mesma placa duas vezes.
        sqlalchemy.exc.DBAPIError: se o agendamento já tiver visita, ou for de outra empresa.
    """
    estado = ABRE.get(evento)
    if estado is None:
        raise TransicaoInvalidaError(f"o evento {evento} não abre uma visita")
    visita = Visita(
        empresa_id=site.empresa_id,
        site_id=site.site_id,
        agendamento_id=agendamento_id,
        estado=estado,
        composicao=_composicao(composicao),
        chegou_em=None if estado == "NAO_VEIO" else momento,
        saiu_em=None,
        passagem_entrada_id=passagem_id,
        passagem_saida_id=None,
        criada_em=agora,
    )
    sessao.add(visita)
    sessao.flush()
    _evento(sessao, visita, evento, momento, agora, passagem_id, dados, usuario_id)
    return visita


def abrir_excecao(
    sessao: Session,
    site: SiteDaVisita,
    *,
    passagem_id: UUID,
    momento: datetime,
    agora: datetime,
    motivo: MotivoDaExcecao,
    candidatos: Sequence[Candidato],
    composicao: Sequence[PlacaNaVisita],
) -> Excecao:
    """Abre a visita de uma chegada que não casou, com a exceção para o porteiro resolver."""
    lista = [{"agendamento_id": c.agendamento_id, "pontos": c.pontos} for c in candidatos]
    visita = abrir_visita(
        sessao,
        site,
        "excecao",
        momento=momento,
        agora=agora,
        composicao=composicao,
        passagem_id=passagem_id,
        dados={"motivo": motivo, "candidatos": lista},
    )
    excecao = Excecao(
        empresa_id=site.empresa_id,
        visita_id=visita.id,
        passagem_id=passagem_id,
        motivo=motivo,
        candidatos=lista,
        situacao="aberta",
        criada_em=agora,
    )
    sessao.add(excecao)
    sessao.flush()
    return excecao


def registrar(
    sessao: Session,
    visita: Visita,
    evento: TipoDeEvento,
    *,
    momento: datetime,
    agora: datetime,
    passagem_id: UUID | None = None,
    dados: dict[str, Any] | None = None,
    usuario_id: int | None = None,
    resolucao: str = "",
) -> Visita:
    """Registra um evento numa visita aberta e a leva ao estado seguinte.

    Quando a visita sai de ``EXCECAO``, a exceção fica resolvida por quem registrou (vazio = o
    sistema), com a ``resolucao`` (ou o nome do evento).

    Raises:
        TransicaoInvalidaError: se o evento não cabe no estado atual (nada muda).
    """
    anterior = visita.estado
    novo = TRANSICOES.get((anterior, evento))
    if novo is None:
        raise TransicaoInvalidaError(f"a visita em {anterior} não aceita o evento {evento}")
    visita.estado = novo
    if novo == "SAIU":
        visita.saiu_em = momento
        visita.passagem_saida_id = passagem_id
    if anterior == "EXCECAO" and novo != "EXCECAO":
        texto = resolucao or ("saiu" if novo == "SAIU" else evento)
        _resolver_excecao(sessao, visita, texto, usuario_id, agora)
    _evento(sessao, visita, evento, momento, agora, passagem_id, dados, usuario_id)
    return visita


def _evento(
    sessao: Session,
    visita: Visita,
    tipo: TipoDeEvento,
    momento: datetime,
    agora: datetime,
    passagem_id: UUID | None,
    dados: dict[str, Any] | None,
    usuario_id: int | None,
) -> None:
    sessao.add(
        Evento(
            empresa_id=visita.empresa_id,
            visita_id=visita.id,
            tipo=tipo,
            estado=visita.estado,
            momento=momento,
            registrado_em=agora,
            usuario_id=usuario_id,
            passagem_id=passagem_id,
            dados=dados or {},
        )
    )
    sessao.flush()


def _resolver_excecao(
    sessao: Session, visita: Visita, resolucao: str, usuario_id: int | None, agora: datetime
) -> None:
    excecao = sessao.scalars(
        select(Excecao).where(
            Excecao.empresa_id == visita.empresa_id,
            Excecao.visita_id == visita.id,
            Excecao.situacao == "aberta",
        )
    ).one_or_none()
    if excecao is not None:
        excecao.situacao = "resolvida"
        excecao.resolvida_em = agora
        excecao.resolvida_por = usuario_id
        excecao.resolucao = resolucao


def mudar_composicao(visita: Visita, placas: Sequence[PlacaNaVisita]) -> None:
    """Troca as placas da visita (ex.: o porteiro corrigiu a placa numa exceção).

    Raises:
        ValueError: se a composição tiver dois cavalos ou a mesma placa duas vezes.
    """
    visita.composicao = _composicao(placas)


def composicao_da_visita(visita: Visita) -> tuple[PlacaNaVisita, ...]:
    """As placas da visita, como ``PlacaNaVisita``."""
    return tuple(PlacaNaVisita.model_validate(placa) for placa in visita.composicao)


def _composicao(placas: Sequence[PlacaNaVisita]) -> list[dict[str, Any]]:
    if sum(placa.papel == "cavalo" for placa in placas) > 1:
        raise ValueError("a composição tem mais de um cavalo")
    if len({placa.placa for placa in placas}) < len(placas):
        raise ValueError("a composição tem a mesma placa duas vezes")
    return [placa.model_dump() for placa in placas]


# --- Ler --------------------------------------------------------------------------------------


def obter_visita(sessao: Session, acesso: Acesso, visita_id: int) -> Visita:
    """Uma visita de um site que o usuário vê.

    Raises:
        NaoEncontradoError: se não existir, ou for de outra empresa ou de outro site.
    """
    visita = sessao.scalars(
        select(Visita).where(
            Visita.id == visita_id,
            Visita.empresa_id == acesso.empresa_id,
            Visita.site_id.in_(acesso.sites),
        )
    ).one_or_none()
    if visita is None:
        raise NaoEncontradoError(f"visita {visita_id}")
    return visita


def eventos_da_visita(sessao: Session, acesso: Acesso, visita_id: int) -> list[Evento]:
    """Os eventos de uma visita que o usuário vê, na ordem em que foram registrados.

    Raises:
        NaoEncontradoError: se a visita não for visível para este usuário.
    """
    visita = obter_visita(sessao, acesso, visita_id)
    return list(
        sessao.scalars(
            select(Evento)
            .where(Evento.empresa_id == acesso.empresa_id, Evento.visita_id == visita.id)
            .order_by(Evento.id)
        )
    )


def eventos_recentes(
    sessao: Session, tipos: Sequence[TipoDeEvento], *, desde: datetime
) -> list[tuple[Evento, Visita]]:
    """Os eventos destes tipos registrados desde ``desde``, de todos os sites, com a visita, na
    ordem em que foram registrados; só os das visitas com agendamento.

    Para os avisos ao motorista (D-47), que o worker prepara para a plataforma inteira.
    """
    return list(
        sessao.execute(
            select(Evento, Visita)
            .join(
                Visita, and_(Visita.id == Evento.visita_id, Visita.empresa_id == Evento.empresa_id)
            )
            .where(
                Evento.tipo.in_(tipos),
                Evento.registrado_em >= desde,
                Visita.agendamento_id.is_not(None),
            )
            .order_by(Evento.id)
        )
    )


def excecoes_abertas(sessao: Session, acesso: Acesso, site_id: int) -> list[Excecao]:
    """As exceções abertas de um site, da chegada mais antiga para a mais nova.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    return list(
        sessao.scalars(
            select(Excecao)
            .join(
                Visita,
                and_(Visita.id == Excecao.visita_id, Visita.empresa_id == Excecao.empresa_id),
            )
            .where(
                Excecao.empresa_id == acesso.empresa_id,
                Excecao.situacao == "aberta",
                Visita.site_id == site.id,
            )
            .order_by(Visita.chegou_em, Excecao.id)
        )
    )

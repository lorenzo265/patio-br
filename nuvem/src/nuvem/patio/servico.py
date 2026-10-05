"""O pátio do site: a fila, as docas e os caminhões liberados (SDD 2.2 e 5.2).

- **Fila:** as visitas em ``NA_FILA``, da chegada mais antiga para a mais nova, com o tempo desde
  a chegada e o alerta perto das 5 horas (a lei conta a estadia desde a chegada).
- **Chamar:** a visita da fila vai para uma doca livre do mesmo site (``CHAMADA``). Uma doca tem no
  máximo um caminhão chamado ou carregando; o banco também confere.
- **Começar e terminar:** ``NA_DOCA`` e ``LIBERADA``; liberada, a doca fica livre. A saída fecha a
  visita (no casamento).
- **Cancelar a chamada:** o caminhão não veio à doca; volta para a fila e a doca fica livre.

Cada mudança é um evento, com quem fez. As funções gravam com ``flush``; o ``commit`` é de quem
chama.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, tuple_
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import Tipo
from nuvem.banco import SQLSTATE_UNICIDADE, sqlstate
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.modelos import Doca
from nuvem.erros import NaoEncontradoError
from nuvem.portaria import visitas
from nuvem.portaria.modelos import EstadoDaVisita, Visita

ALERTA_DE_ESTADIA = timedelta(hours=4)
"""Quanto depois da chegada o pátio avisa que as 5 horas estão perto (``[ABERTO-09]``)."""

ESTADIA_DA_LEI = timedelta(hours=5)
"""Depois de 5 horas da chegada, a estadia é devida (Lei 11.442, SDD 5.4)."""

OCUPAM_A_DOCA: tuple[EstadoDaVisita, ...] = ("CHAMADA", "NA_DOCA")
NO_PATIO: tuple[EstadoDaVisita, ...] = ("NA_FILA", "CHAMADA", "NA_DOCA", "LIBERADA")


class DocaOcupadaError(Exception):
    """A doca já tem um caminhão chamado ou carregando."""

    def __init__(self, doca: str) -> None:
        super().__init__(f"a {doca} está ocupada")
        self.doca = doca


@dataclass(frozen=True)
class CaminhaoNoPatio:
    """Uma visita no pátio, como o líder a vê."""

    visita_id: int
    estado: EstadoDaVisita
    placas: tuple[str, ...]
    agendamento_id: int | None
    agendamento: str | None
    """O código do agendamento; vazio se entrou sem agendamento."""
    tipo: Tipo | None
    chegou_em: datetime
    tempo: timedelta
    """Desde a chegada."""
    alerta: bool
    """Perto das 5 horas de estadia."""
    doca: str | None


@dataclass(frozen=True)
class DocaDoPatio:
    """Uma doca, livre (sem caminhão) ou ocupada."""

    doca_id: int
    nome: str
    caminhao: CaminhaoNoPatio | None


@dataclass(frozen=True)
class Quadro:
    """O pátio de um site agora."""

    fila: list[CaminhaoNoPatio]
    docas: list[DocaDoPatio]
    liberados: list[CaminhaoNoPatio]
    """Terminaram na doca e ainda não passaram pela saída."""


# --- Ler --------------------------------------------------------------------------------------


def quadro(sessao: Session, acesso: Acesso, site_id: int, *, agora: datetime) -> Quadro:
    """A fila, as docas e os liberados de um site que o usuário vê.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    docas = _docas_do_site(sessao, acesso, site.id)
    no_patio = list(
        sessao.scalars(
            select(Visita)
            .where(
                Visita.empresa_id == acesso.empresa_id,
                Visita.site_id == site.id,
                Visita.estado.in_(NO_PATIO),
            )
            .order_by(Visita.chegou_em, Visita.id)
        )
    )
    resumos = agendamentos.resumos(
        sessao, acesso, [v.agendamento_id for v in no_patio if v.agendamento_id is not None]
    )
    nomes = {doca.id: doca.nome for doca in docas}
    caminhoes = [_caminhao(v, resumos, nomes, agora) for v in no_patio]
    por_doca = {
        v.doca_id: c for v, c in zip(no_patio, caminhoes, strict=True) if v.estado in OCUPAM_A_DOCA
    }
    return Quadro(
        fila=[c for c in caminhoes if c.estado == "NA_FILA"],
        docas=[DocaDoPatio(doca.id, doca.nome, por_doca.get(doca.id)) for doca in docas],
        liberados=[c for c in caminhoes if c.estado == "LIBERADA"],
    )


def docas_livres(sessao: Session, acesso: Acesso, site_id: int) -> list[Doca]:
    """As docas de um site sem caminhão chamado ou carregando, pelo nome.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    ocupadas = set(
        sessao.scalars(
            select(Visita.doca_id).where(
                Visita.empresa_id == acesso.empresa_id,
                Visita.site_id == site.id,
                Visita.estado.in_(OCUPAM_A_DOCA),
            )
        )
    )
    return [d for d in _docas_do_site(sessao, acesso, site.id) if d.id not in ocupadas]


def obter_caminhao(
    sessao: Session, acesso: Acesso, visita_id: int, *, agora: datetime
) -> CaminhaoNoPatio:
    """Uma visita de um site que o usuário vê, como o líder a vê.

    Raises:
        NaoEncontradoError: se a visita não for visível para este usuário.
    """
    visita = visitas.obter_visita(sessao, acesso, visita_id)
    ids = [visita.agendamento_id] if visita.agendamento_id is not None else []
    nomes = {d.id: d.nome for d in _docas_do_site(sessao, acesso, visita.site_id)}
    return _caminhao(visita, agendamentos.resumos(sessao, acesso, ids), nomes, agora)


def posicao_na_fila(sessao: Session, visita: Visita) -> int:
    """A posição do caminhão na fila do site: 1 mais quantos chegaram antes e ainda esperam.

    Para o aviso do check-in ao motorista (D-47); quem chama já tem a visita. Quem chegou na
    mesma hora fica atrás de quem entrou antes no sistema, como no quadro.
    """
    na_frente = sessao.scalar(
        select(func.count())
        .select_from(Visita)
        .where(
            Visita.empresa_id == visita.empresa_id,
            Visita.site_id == visita.site_id,
            Visita.estado == "NA_FILA",
            tuple_(Visita.chegou_em, Visita.id) < tuple_(visita.chegou_em, visita.id),
        )
    )
    return (na_frente or 0) + 1


# --- Mover ------------------------------------------------------------------------------------


def chamar(
    sessao: Session, acesso: Acesso, visita_id: int, doca_id: int, *, agora: datetime
) -> Visita:
    """Chama o caminhão da fila para uma doca livre do mesmo site.

    Raises:
        NaoEncontradoError: se a visita ou a doca não forem visíveis (ou forem de outro site).
        TransicaoInvalidaError: se a visita não estiver na fila.
        DocaOcupadaError: se a doca já tiver um caminhão chamado ou carregando.
    """
    visita = _travar_visita(sessao, acesso, visita_id)
    doca = _travar_doca(sessao, acesso, doca_id, visita.site_id)
    # Fora da fila, ``registrar`` recusa a chamada; doca ocupada, o índice único do banco recusa,
    # e o erro vira ``DocaOcupadaError``. Nos dois casos, o ponto de volta desfaz a doca e a hora.
    with _sem_outro_caminhao_na_doca(sessao, doca):
        visita.doca_id = doca.id
        visita.chamada_em = agora
        visitas.registrar(
            sessao,
            visita,
            "chamada",
            momento=agora,
            agora=agora,
            dados={"doca_id": doca.id, "doca": doca.nome},
            usuario_id=acesso.usuario_id,
        )
    return visita


def cancelar_chamada(sessao: Session, acesso: Acesso, visita_id: int, *, agora: datetime) -> Visita:
    """O caminhão chamado não veio à doca: volta para a fila, e a doca fica livre.

    Raises:
        NaoEncontradoError: se a visita não for visível para este usuário.
        TransicaoInvalidaError: se a visita não estiver chamada.
    """
    visita = _travar_visita(sessao, acesso, visita_id)
    doca_id = visita.doca_id
    visitas.registrar(
        sessao,
        visita,
        "chamada_cancelada",
        momento=agora,
        agora=agora,
        dados={"doca_id": doca_id},
        usuario_id=acesso.usuario_id,
    )
    visita.doca_id = None
    visita.chamada_em = None
    sessao.flush()
    return visita


def iniciar(sessao: Session, acesso: Acesso, visita_id: int, *, agora: datetime) -> Visita:
    """O caminhão chegou à doca: começa a carga ou a descarga.

    Raises:
        NaoEncontradoError: se a visita não for visível para este usuário.
        TransicaoInvalidaError: se a visita não estiver chamada.
    """
    visita = _travar_visita(sessao, acesso, visita_id)
    visitas.registrar(
        sessao, visita, "inicio_na_doca", momento=agora, agora=agora, usuario_id=acesso.usuario_id
    )
    visita.na_doca_em = agora
    sessao.flush()
    return visita


def finalizar(sessao: Session, acesso: Acesso, visita_id: int, *, agora: datetime) -> Visita:
    """Terminou a carga ou a descarga: o caminhão está liberado, e a doca fica livre.

    Raises:
        NaoEncontradoError: se a visita não for visível para este usuário.
        TransicaoInvalidaError: se a visita não estiver na doca.
    """
    visita = _travar_visita(sessao, acesso, visita_id)
    visitas.registrar(
        sessao, visita, "fim_na_doca", momento=agora, agora=agora, usuario_id=acesso.usuario_id
    )
    visita.liberada_em = agora
    sessao.flush()
    return visita


# --- Por dentro -------------------------------------------------------------------------------


def _docas_do_site(sessao: Session, acesso: Acesso, site_id: int) -> list[Doca]:
    return list(
        sessao.scalars(
            select(Doca)
            .where(Doca.empresa_id == acesso.empresa_id, Doca.site_id == site_id)
            .order_by(Doca.nome, Doca.id)
        )
    )


def _travar_visita(sessao: Session, acesso: Acesso, visita_id: int) -> Visita:
    visita = sessao.scalars(
        select(Visita)
        .where(
            Visita.id == visita_id,
            Visita.empresa_id == acesso.empresa_id,
            Visita.site_id.in_(acesso.sites),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if visita is None:
        raise NaoEncontradoError(f"visita {visita_id}")
    return visita


def _travar_doca(sessao: Session, acesso: Acesso, doca_id: int, site_id: int) -> Doca:
    # A trava da doca põe em fila duas chamadas para a mesma doca.
    doca = sessao.scalars(
        select(Doca)
        .where(Doca.id == doca_id, Doca.empresa_id == acesso.empresa_id, Doca.site_id == site_id)
        .with_for_update()
    ).one_or_none()
    if doca is None:
        raise NaoEncontradoError(f"doca {doca_id}")
    return doca


@contextmanager
def _sem_outro_caminhao_na_doca(sessao: Session, doca: Doca) -> Iterator[None]:
    """Se o banco recusar o segundo caminhão na doca, o erro certo (num ponto de volta)."""
    try:
        with sessao.begin_nested():
            yield
    except DBAPIError as erro:
        if sqlstate(erro) == SQLSTATE_UNICIDADE:
            raise DocaOcupadaError(doca.nome) from None
        raise


def _caminhao(
    visita: Visita,
    resumos: dict[int, agendamentos.Resumo],
    docas: dict[int, str],
    agora: datetime,
) -> CaminhaoNoPatio:
    chegada = visita.chegou_em or visita.criada_em
    resumo = resumos.get(visita.agendamento_id or 0)
    tempo = agora - chegada
    return CaminhaoNoPatio(
        visita_id=visita.id,
        estado=visita.estado,
        placas=_placas(visita),
        agendamento_id=visita.agendamento_id,
        agendamento=resumo.codigo if resumo else None,
        tipo=resumo.tipo if resumo else None,
        chegou_em=chegada,
        tempo=tempo,
        alerta=tempo >= ALERTA_DE_ESTADIA and visita.estado != "LIBERADA",
        doca=docas.get(visita.doca_id or 0) if visita.estado in OCUPAM_A_DOCA else None,
    )


def _placas(visita: Visita) -> tuple[str, ...]:
    composicao: Sequence[dict[str, str]] = visita.composicao
    return tuple(p["placa"] for p in composicao)

"""Fila de tarefas no PostgreSQL e o laço do worker (SDD 6.1, D-16 e D-38).

- **Enfileirar:** a passagem recebida vira a tarefa "casar" (uma só por passagem: a chave), na
  mesma transação que a grava.
- **Pegar:** ``SELECT ... FOR UPDATE SKIP LOCKED``: a tarefa fica travada até o fim da
  transação, e dois workers nunca pegam a mesma.
- **Falhar:** o que a tarefa gravou é desfeito; ela volta para a fila esperando cada vez mais
  (``espera``), até ``MAXIMO_DE_TENTATIVAS``; depois, fica como falhou, com o erro.
- **"Não veio"** (SDD 5.2): a cada 5 minutos, o agendamento ativo sem visita, com a janela
  vencida há mais que a tolerância, ganha a visita em ``NAO_VEIO``. Um worker de cada vez (trava
  do PostgreSQL).
- **Mensagens ao motorista** (D-47): a cada volta, as que faltam (``mensagens.preparar``).
- **Dia de demonstração** (D-49): a cada volta, se o ambiente tiver, as chegadas e o líder
  automático.

O worker roda em outro processo (``python -m nuvem.worker``).
"""

import logging
import threading
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from nuvem.agendamento import servico as agendamentos
from nuvem.banco import Base, texto_de_lista
from nuvem.mensagens import servico as mensagens
from nuvem.portaria import visitas
from nuvem.portaria.casamento import TOLERANCIA_PADRAO, processar_passagem
from nuvem.portaria.modelos import Visita
from nuvem.portaria.visitas import SiteDaVisita
from nuvem.relogio import agora as agora_de_verdade

_registro = logging.getLogger(__name__)

TipoDeTarefa = Literal["casar_passagem"]
SituacaoDaTarefa = Literal["pendente", "feita", "falhou"]

MAXIMO_DE_TENTATIVAS = 8
PRIMEIRA_ESPERA = timedelta(seconds=10)
MAIOR_ESPERA = timedelta(minutes=10)
TAMANHO_DO_ERRO = 500
"""O texto do erro guardado na tarefa é cortado aqui."""

TOLERANCIA_DO_NAO_VEIO = TOLERANCIA_PADRAO
"""Quanto depois do fim da janela o agendamento sem chegada vira "não veio" (``[ABERTO-09]``)."""
INTERVALO_DO_NAO_VEIO = timedelta(minutes=5)
JANELAS_OLHADAS = timedelta(days=7)
"""O "não veio" olha as janelas que terminaram nos últimos 7 dias (cobre o worker parado)."""
TRAVA_DO_NAO_VEIO = 7301
"""Número da trava do PostgreSQL que deixa um worker de cada vez conferir o "não veio"."""

PAUSA = 1.0
"""Segundos de espera quando a fila está vazia."""
PAUSA_DEPOIS_DE_ERRO = 5.0


class TarefaDeFundo(Base):
    """Uma tarefa para o worker. É da plataforma, não de um cliente: os dados dizem o que fazer."""

    __tablename__ = "tarefa_de_fundo"
    __table_args__ = (
        # A mesma chave (ex.: a passagem) não vira duas tarefas do mesmo tipo.
        UniqueConstraint("tipo", "chave"),
        CheckConstraint("tentativas >= 0", name="tentativas_positivas"),
        # O worker procura a próxima pendente pela hora.
        Index(
            "ix_tarefa_de_fundo_pendentes",
            "executar_em",
            postgresql_where=text("situacao = 'pendente'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoDeTarefa] = mapped_column(texto_de_lista(TipoDeTarefa, "tipo_de_tarefa"))
    chave: Mapped[str] = mapped_column(String(100))
    dados: Mapped[dict[str, Any]] = mapped_column(JSONB)
    situacao: Mapped[SituacaoDaTarefa] = mapped_column(
        texto_de_lista(SituacaoDaTarefa, "situacao_da_tarefa")
    )
    tentativas: Mapped[int]
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    executar_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """Não antes desta hora (na falha, a hora da próxima tentativa)."""
    terminada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_erro: Mapped[str | None] = mapped_column(String(TAMANHO_DO_ERRO))


Executor = Callable[[Session, dict[str, Any], datetime], None]


def _casar(sessao: Session, dados: dict[str, Any], agora: datetime) -> None:
    processar_passagem(sessao, UUID(dados["passagem_id"]), agora=agora)


EXECUTORES: dict[str, Executor] = {"casar_passagem": _casar}
"""O que cada tipo de tarefa faz."""


# --- A fila -----------------------------------------------------------------------------------


def enfileirar(
    sessao: Session, tipo: TipoDeTarefa, dados: dict[str, Any], *, chave: str, agora: datetime
) -> None:
    """Põe uma tarefa na fila, para já; a mesma chave do mesmo tipo de novo não muda nada."""
    sessao.execute(
        insert(TarefaDeFundo)
        .values(
            tipo=tipo,
            chave=chave,
            dados=dados,
            situacao="pendente",
            tentativas=0,
            criada_em=agora,
            executar_em=agora,
        )
        .on_conflict_do_nothing(index_elements=["tipo", "chave"])
    )


def pegar_proxima(sessao: Session, *, agora: datetime) -> TarefaDeFundo | None:
    """A tarefa pendente mais antiga que já pode rodar, travada até o fim da transação."""
    return sessao.scalars(
        select(TarefaDeFundo)
        .where(TarefaDeFundo.situacao == "pendente", TarefaDeFundo.executar_em <= agora)
        .order_by(TarefaDeFundo.executar_em, TarefaDeFundo.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).one_or_none()


def situacao_das_tarefas(
    sessao: Session, tipo: TipoDeTarefa, chaves: Sequence[str]
) -> dict[str, SituacaoDaTarefa]:
    """A situação da tarefa de cada chave (ex.: o "casar" de cada passagem), por chave."""
    linhas = sessao.execute(
        select(TarefaDeFundo.chave, TarefaDeFundo.situacao).where(
            TarefaDeFundo.tipo == tipo, TarefaDeFundo.chave.in_(chaves)
        )
    )
    return {chave: situacao for chave, situacao in linhas}


def espera(tentativas: int) -> timedelta:
    """Quanto esperar depois da falha número ``tentativas``: 10 s, 20 s, 40 s ... até 10 min."""
    dobrada: timedelta = PRIMEIRA_ESPERA * 2 ** (tentativas - 1)
    return min(dobrada, MAIOR_ESPERA)


def executar_uma(sessao: Session, *, agora: datetime) -> bool:
    """Executa a próxima tarefa e grava o resultado (com ``commit``).

    Returns:
        ``True`` se havia tarefa para executar.
    """
    tarefa = pegar_proxima(sessao, agora=agora)
    if tarefa is None:
        return False
    try:
        with sessao.begin_nested():  # a falha desfaz só o que a tarefa gravou
            EXECUTORES[tarefa.tipo](sessao, tarefa.dados, agora)
    except Exception as erro:
        _falhou(tarefa, erro, agora)
    else:
        tarefa.situacao = "feita"
        tarefa.terminada_em = agora
    sessao.commit()
    return True


def executar_pendentes(sessao: Session, *, agora: datetime, limite: int = 100) -> int:
    """Executa as tarefas que já podem rodar, até ``limite``; devolve quantas executou."""
    executadas = 0
    while executadas < limite and executar_uma(sessao, agora=agora):
        executadas += 1
    return executadas


def _falhou(tarefa: TarefaDeFundo, erro: Exception, agora: datetime) -> None:
    tarefa.tentativas += 1
    tarefa.ultimo_erro = f"{type(erro).__name__}: {erro}"[:TAMANHO_DO_ERRO]
    if tarefa.tentativas >= MAXIMO_DE_TENTATIVAS:
        tarefa.situacao = "falhou"
        tarefa.terminada_em = agora
        _registro.error(
            "a tarefa %s (%s) falhou %d vezes e saiu da fila: %s",
            tarefa.id,
            tarefa.tipo,
            tarefa.tentativas,
            tarefa.ultimo_erro,
        )
        return
    tarefa.executar_em = agora + espera(tarefa.tentativas)
    _registro.warning(
        "a tarefa %s (%s) falhou (tentativa %d), volta às %s: %s",
        tarefa.id,
        tarefa.tipo,
        tarefa.tentativas,
        tarefa.executar_em.isoformat(),
        tarefa.ultimo_erro,
    )


# --- "Não veio" -------------------------------------------------------------------------------


def conferir_nao_veio(
    sessao: Session, *, agora: datetime, tolerancia: timedelta = TOLERANCIA_DO_NAO_VEIO
) -> int:
    """Abre a visita "não veio" de cada agendamento vencido sem chegada (sem ``commit``).

    Returns:
        Quantas visitas abriu (0 se outro worker já está conferindo).
    """
    if not sessao.scalar(select(func.pg_try_advisory_xact_lock(TRAVA_DO_NAO_VEIO))):
        return 0
    limite = agora - tolerancia
    vencidos = agendamentos.ativos_que_terminaram(sessao, de=limite - JANELAS_OLHADAS, ate=limite)
    com_visita = set(
        sessao.scalars(
            select(Visita.agendamento_id).where(Visita.agendamento_id.in_([a.id for a in vencidos]))
        )
    )
    abertas = 0
    for agendamento in vencidos:
        if agendamento.id in com_visita:
            continue
        visitas.abrir_visita(
            sessao,
            SiteDaVisita(empresa_id=agendamento.empresa_id, site_id=agendamento.site_id),
            "nao_veio",
            momento=agendamento.janela_fim + tolerancia,
            agora=agora,
            agendamento_id=agendamento.id,
        )
        abertas += 1
    return abertas


# --- O laço do worker -------------------------------------------------------------------------


def rodar(
    abrir_sessao: Callable[[], Session],
    parar: threading.Event,
    *,
    relogio: Callable[[], datetime] = agora_de_verdade,
    dormir: Callable[[float], None] = time.sleep,
    demonstracao: Callable[[Session, datetime], int] | None = None,
) -> None:
    """Executa as tarefas, confere o "não veio" e prepara as mensagens até ``parar`` ser ligado.

    Com ``demonstracao`` (só nos ambientes que têm o dia de demonstração, D-49), ela roda antes,
    a cada volta: as passagens que ela manda casam na mesma volta.

    Um erro inesperado (ex.: o banco fora do ar) fica registrado, e o laço segue.
    """
    ultimo_nao_veio: datetime | None = None
    while not parar.is_set():
        try:
            with abrir_sessao() as sessao:
                momento = relogio()
                if demonstracao is not None:
                    demonstracao(sessao, momento)
                    sessao.commit()
                executadas = executar_pendentes(sessao, agora=momento)
                if ultimo_nao_veio is None or momento - ultimo_nao_veio >= INTERVALO_DO_NAO_VEIO:
                    abertas = conferir_nao_veio(sessao, agora=momento)
                    sessao.commit()
                    ultimo_nao_veio = momento
                    if abertas:
                        _registro.info('"não veio": %d visitas', abertas)
                mensagens.preparar(sessao, agora=momento)
                sessao.commit()
        except Exception:
            _registro.exception("erro no laço do worker; ele segue")
            dormir(PAUSA_DEPOIS_DE_ERRO)
            continue
        if executadas == 0:
            dormir(PAUSA)

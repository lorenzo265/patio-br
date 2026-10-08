"""A cópia diária, a restauração de teste e a guarda das cópias (SDD 7.2, D-74).

O worker chama ``cuidar`` de tempos em tempos; o que está pendente roda na hora:

- **a cópia:** uma por dia, a partir das 3h de Brasília. Antes de começar, anota o manifesto
  (a migração, as contagens das tabelas só de acréscimo e o último evento); ao terminar, o
  resumo e o tamanho;
- **a guarda:** apaga as cópias de mais de 30 dias, menos a mais nova;
- **a restauração de teste:** uma por mês, a partir do dia 1º às 4h. Volta a última cópia num
  banco temporário e confere o resumo, a migração e se as contagens e o último evento são pelo
  menos os anotados (a nuvem continua gravando enquanto a cópia é feita). Se falhar, tenta de
  novo no dia seguinte.

Cada parte que falha vira um erro registrado (e um alarme, D-61) e não impede as outras.
"""

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, select, text
from sqlalchemy.orm import Session

from nuvem.config import Configuracao
from nuvem.copias.guarda import (
    GuardaDasCopias,
    Legivel,
    LeitorComResumo,
    guarda_das_copias_da_configuracao,
)
from nuvem.copias.modelos import CopiaDoBanco, RestauracaoDeTeste
from nuvem.copias.postgres import BancoPostgres
from nuvem.portaria.modelos import Evento
from nuvem.registro import mascarar

_registro = logging.getLogger(__name__)

FUSO = ZoneInfo("America/Sao_Paulo")
HORA_DA_COPIA = 3
HORA_DA_RESTAURACAO = 4
GUARDA = timedelta(days=30)
NOVA_TENTATIVA = timedelta(hours=20)
"""Depois de uma restauração de teste que falhou, quanto esperar para tentar de novo."""


class Banco(Protocol):
    """O servidor do banco: de onde sai a cópia e onde ela volta para o teste."""

    def despejar(self) -> AbstractContextManager[Legivel]:
        """A cópia do banco, para ler até o fim."""
        ...

    def restaurar(self, leitor: Legivel) -> AbstractContextManager[Session]:
        """Volta a cópia num banco temporário e dá uma sessão nele (apagado no fim)."""
        ...


@dataclass(frozen=True)
class Copias:
    """O que o worker precisa para as cópias: onde guardar e de onde copiar."""

    guarda: GuardaDasCopias
    banco: Banco


def copias_da_configuracao(configuracao: Configuracao) -> Copias | None:
    """As cópias, se há o balde delas (``PATIO_COPIAS_S3_BALDE``); senão, nenhuma."""
    guarda = guarda_das_copias_da_configuracao(configuracao)
    if guarda is None:
        return None
    return Copias(guarda=guarda, banco=BancoPostgres.da_configuracao(configuracao))


# --- O manifesto ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Manifesto:
    """O que a cópia precisa ter, anotado antes de ela começar."""

    migracao: str
    contagens: dict[str, int]
    ultimo_evento: datetime | None


def tabelas_so_de_acrescimo(sessao: Session) -> list[str]:
    """As tabelas com o gatilho ``so_acrescenta`` (SDD 5.5): só crescem, então dá para contar."""
    return list(
        sessao.scalars(
            text(
                "select distinct c.relname from pg_trigger t"
                " join pg_class c on c.oid = t.tgrelid"
                " join pg_proc p on p.oid = t.tgfoid"
                " where p.proname = 'so_acrescenta' and not t.tgisinternal"
                " order by c.relname"
            )
        )
    )


def _contar(sessao: Session, tabela: str) -> int:
    nome = sessao.get_bind().dialect.identifier_preparer.quote(tabela)
    return sessao.scalar(text(f"select count(*) from {nome}")) or 0  # o nome vem do catálogo


def _migracao(sessao: Session) -> str:
    migracao = sessao.scalar(text("select version_num from alembic_version"))
    return str(migracao)


def manifesto(sessao: Session) -> Manifesto:
    """A migração, as contagens das tabelas só de acréscimo e o último evento, agora."""
    return Manifesto(
        migracao=_migracao(sessao),
        contagens={tabela: _contar(sessao, tabela) for tabela in tabelas_so_de_acrescimo(sessao)},
        ultimo_evento=sessao.scalar(select(func.max(Evento.registrado_em))),
    )


# --- Quando ---------------------------------------------------------------------------------


def marco_da_copia(agora: datetime) -> datetime:
    """As últimas 3h de Brasília até ``agora``: a cópia do dia é a feita depois delas."""
    local = agora.astimezone(FUSO)
    marco = local.replace(hour=HORA_DA_COPIA, minute=0, second=0, microsecond=0)
    if local < marco:
        marco = (local - timedelta(days=1)).replace(
            hour=HORA_DA_COPIA, minute=0, second=0, microsecond=0
        )
    return marco


def marco_da_restauracao(agora: datetime) -> datetime:
    """O último dia 1º às 4h de Brasília até ``agora``: a restauração do mês vem depois dele."""
    local = agora.astimezone(FUSO)
    marco = local.replace(day=1, hour=HORA_DA_RESTAURACAO, minute=0, second=0, microsecond=0)
    if local < marco:
        mes_passado = marco - timedelta(days=1)
        marco = mes_passado.replace(day=1)
    return marco


def copia_pendente(sessao: Session, *, agora: datetime) -> bool:
    """Se ainda não há cópia desde as últimas 3h."""
    return not sessao.scalar(select(exists().where(CopiaDoBanco.feita_em >= marco_da_copia(agora))))


def restauracao_pendente(sessao: Session, *, agora: datetime) -> bool:
    """Se o mês ainda não tem restauração de teste que passou, e a última tentativa já esfriou."""
    passou = sessao.scalar(
        select(
            exists().where(
                RestauracaoDeTeste.ok.is_(True),
                RestauracaoDeTeste.feita_em >= marco_da_restauracao(agora),
            )
        )
    )
    tentou = sessao.scalar(
        select(exists().where(RestauracaoDeTeste.feita_em > agora - NOVA_TENTATIVA))
    )
    return not passou and not tentou


# --- A cópia --------------------------------------------------------------------------------


def nome_da_copia(agora: datetime) -> str:
    """O nome do arquivo no balde, pela hora em UTC (ex.: ``copia-20261006-060000.dump``)."""
    return f"copia-{agora.astimezone(UTC):%Y%m%d-%H%M%S}.dump"


def fazer_copia(sessao: Session, copias: Copias, *, agora: datetime) -> CopiaDoBanco:
    """Anota o manifesto, copia o banco para o balde e registra a cópia.

    Se a cópia falhar no meio, o que subiu é apagado e o erro segue para quem chamou.
    """
    anotado = manifesto(sessao)
    nome = nome_da_copia(agora)
    try:
        with copias.banco.despejar() as leitor:
            gravada = copias.guarda.gravar(nome, leitor)
    except Exception:
        with suppress(Exception):
            copias.guarda.apagar(nome)  # o que subiu pela metade
        raise
    copia = CopiaDoBanco(
        nome=nome,
        feita_em=agora,
        tamanho=gravada.tamanho,
        resumo=gravada.resumo,
        migracao=anotado.migracao,
        contagens=anotado.contagens,
        ultimo_evento=anotado.ultimo_evento,
    )
    sessao.add(copia)
    sessao.flush()
    _registro.info("cópia do banco %s: %d bytes", copia.id, copia.tamanho)
    return copia


def apagar_vencidas(sessao: Session, guarda: GuardaDasCopias, *, agora: datetime) -> int:
    """Apaga as cópias de mais de 30 dias, menos a mais nova; devolve quantas."""
    guardadas = select(CopiaDoBanco).where(CopiaDoBanco.apagada_em.is_(None))
    mais_nova = sessao.scalar(guardadas.order_by(CopiaDoBanco.feita_em.desc()).limit(1))
    vencidas = sessao.scalars(guardadas.where(CopiaDoBanco.feita_em < agora - GUARDA)).all()
    apagadas = 0
    for copia in vencidas:
        if copia is mais_nova:
            continue
        guarda.apagar(copia.nome)
        copia.apagada_em = agora
        apagadas += 1
    sessao.flush()
    return apagadas


# --- A restauração de teste -----------------------------------------------------------------


def conferir(restaurado: Session, copia: CopiaDoBanco) -> list[str]:
    """O que não confere entre o banco restaurado e o manifesto da cópia (vazio: tudo certo)."""
    problemas = []
    migracao = _migracao(restaurado)
    if migracao != copia.migracao:
        problemas.append(f"a migração é {migracao}, e a cópia anotou {copia.migracao}")
    if not copia.contagens:
        problemas.append("a cópia não anotou nenhuma tabela para contar")
    for tabela, anotadas in sorted(copia.contagens.items()):
        linhas = _contar(restaurado, tabela)
        if linhas < anotadas:
            problemas.append(f"{tabela}: {linhas} linhas, menos que as {anotadas} anotadas")
    if copia.ultimo_evento is not None:
        ultimo = restaurado.scalar(select(func.max(Evento.registrado_em)))
        if ultimo is None or ultimo < copia.ultimo_evento:
            problemas.append("o último evento é mais velho que o anotado")
    return problemas


def testar_restauracao(
    sessao: Session, copias: Copias, *, agora: datetime
) -> RestauracaoDeTeste | None:
    """Volta a última cópia num banco temporário, confere e registra o resultado.

    Sem nenhuma cópia ainda, não faz nada (a falta da cópia já é um erro dela).
    """
    copia = sessao.scalar(
        select(CopiaDoBanco)
        .where(CopiaDoBanco.apagada_em.is_(None))
        .order_by(CopiaDoBanco.feita_em.desc())
        .limit(1)
    )
    if copia is None:
        _registro.warning("restauração de teste: ainda não há cópia")
        return None
    try:
        with copias.guarda.abrir(copia.nome) as arquivo:
            leitor = LeitorComResumo(arquivo)
            with copias.banco.restaurar(leitor) as restaurado:
                problemas = conferir(restaurado, copia)
        if (leitor.resumo, leitor.tamanho) != (copia.resumo, copia.tamanho):
            problemas.insert(0, "o arquivo não confere com o resumo anotado")
    except Exception as erro:
        problemas = [mascarar(f"a volta falhou: {erro}")]
    teste = RestauracaoDeTeste(
        copia_id=copia.id, feita_em=agora, ok=not problemas, detalhe="\n".join(problemas) or None
    )
    sessao.add(teste)
    sessao.flush()
    if teste.ok:
        _registro.info("restauração de teste: a cópia %s voltou e conferiu", copia.id)
    else:
        _registro.error(
            "restauração de teste: a cópia %s não passou: %s", copia.id, "; ".join(problemas)
        )
    return teste


# --- O worker -------------------------------------------------------------------------------


def cuidar(sessao: Session, copias: Copias, *, agora: datetime) -> None:
    """Faz o que estiver pendente: a cópia, a guarda e a restauração de teste, nesta ordem.

    Cada parte grava o que fez; a que falha vira um erro registrado e não impede as outras.
    """

    def copiar() -> None:
        if copia_pendente(sessao, agora=agora):
            fazer_copia(sessao, copias, agora=agora)

    def guardar() -> None:
        apagar_vencidas(sessao, copias.guarda, agora=agora)

    def restaurar() -> None:
        if restauracao_pendente(sessao, agora=agora):
            testar_restauracao(sessao, copias, agora=agora)

    partes: tuple[tuple[str, Callable[[], None]], ...] = (
        ("cópia do banco", copiar),
        ("guarda das cópias", guardar),
        ("restauração de teste", restaurar),
    )
    for nome, parte in partes:
        try:
            parte()
            sessao.commit()
        except Exception:
            sessao.rollback()
            _registro.exception("%s: falhou", nome)

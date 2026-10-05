"""Mensagens ao motorista (SDD 2.2 e D-47): nascem dos eventos, pelo worker.

- **Confirmação:** o agendamento ativo com celular, que ainda não terminou, recebe uma para cada
  celular que teve (o celular novo ainda não sabe de nada).
- **Avisos:** o check-in avisa a posição na fila; a chamada, a doca; o fim na doca, que pode
  sair. Cada evento avisa uma vez só, no celular que o agendamento tem na hora.
- **Só o recente:** o worker olha os eventos dos últimos 30 minutos (aviso mais velho chegaria
  tarde) e os agendamentos criados ou mudados no último dia.
- **Canal de demonstração:** a mensagem só fica guardada; o WhatsApp entra no mês 4, aqui.

O texto fica pronto na mensagem, sem o nome do motorista. O módulo lê a portaria, o pátio e o
agendamento só pelas funções de serviço deles (SDD 3.3). ``preparar`` grava sem ``commit``; quem
lê passa o ``Acesso``.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.modelos import Agendamento
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.servico import HorarioDoSite
from nuvem.mensagens.modelos import Canal, Mensagem, ModeloDeMensagem
from nuvem.patio import servico as patio
from nuvem.portaria import visitas
from nuvem.portaria.modelos import Evento, TipoDeEvento, Visita

AVISOS_OLHADOS = timedelta(minutes=30)
"""O evento mais velho que isso não avisa mais: o aviso chegaria tarde (ex.: a doca já mudou)."""

AGENDAMENTOS_OLHADOS = timedelta(days=1)
"""A confirmação olha os agendamentos criados ou mudados no último dia (cobre o worker parado)."""

CANAL: Canal = "demonstracao"
"""O canal do mês 3: só guarda."""

AVISO_DO_EVENTO: dict[TipoDeEvento, ModeloDeMensagem] = {
    "check_in": "na_fila",
    "chamada": "chamada",
    "fim_na_doca": "pode_sair",
}
"""Os eventos da visita que avisam o motorista, e o modelo de cada aviso."""

ULTIMAS_CONVERSAS = 50
"""Quantas conversas a lista de um site mostra."""


@dataclass(frozen=True)
class Conversa:
    """As mensagens de um agendamento, pela última."""

    agendamento_id: int
    ultima: Mensagem
    quantas: int


# --- Preparar ---------------------------------------------------------------------------------


def preparar(sessao: Session, *, agora: datetime) -> int:
    """Grava as mensagens que faltam, de todos os sites (sem ``commit``).

    Dois workers ao mesmo tempo não repetem nada: o banco recusa a segunda, e ela fica de fora.

    Returns:
        Quantas mensagens gravou.
    """
    sites = _Sites(sessao)
    novas = _confirmacoes(sessao, sites, agora) + _avisos(sessao, sites, agora)
    if not novas:
        return 0
    gravadas = sessao.scalars(
        insert(Mensagem).values(novas).on_conflict_do_nothing().returning(Mensagem.id)
    ).all()
    return len(gravadas)


def _confirmacoes(sessao: Session, sites: "_Sites", agora: datetime) -> list[dict[str, Any]]:
    candidatos = agendamentos.para_confirmar(
        sessao, mudados_desde=agora - AGENDAMENTOS_OLHADOS, agora=agora
    )
    confirmados = {
        (agendamento_id, para)
        for agendamento_id, para in sessao.execute(
            select(Mensagem.agendamento_id, Mensagem.para).where(
                Mensagem.modelo == "confirmacao",
                Mensagem.agendamento_id.in_([a.id for a in candidatos]),
            )
        )
    }
    return [
        _mensagem(a, "confirmacao", _confirmacao(a, sites.de(a)), agora)
        for a in candidatos
        if (a.id, a.motorista_celular) not in confirmados
    ]


def _avisos(sessao: Session, sites: "_Sites", agora: datetime) -> list[dict[str, Any]]:
    recentes = visitas.eventos_recentes(
        sessao, tuple(AVISO_DO_EVENTO), desde=agora - AVISOS_OLHADOS
    )
    avisados = set(
        sessao.scalars(
            select(Mensagem.evento_id).where(Mensagem.evento_id.in_([e.id for e, _ in recentes]))
        )
    )
    pendentes = [(evento, visita) for evento, visita in recentes if evento.id not in avisados]
    contatos = agendamentos.com_celular(sessao, [v.agendamento_id or 0 for _, v in pendentes])
    novas = []
    for evento, visita in pendentes:
        agendamento = contatos.get(visita.agendamento_id or 0)
        if agendamento is None:
            continue
        modelo = AVISO_DO_EVENTO[evento.tipo]
        texto = _aviso(sessao, modelo, evento, visita, agendamento, sites.de(agendamento))
        novas.append(_mensagem(agendamento, modelo, texto, agora, evento_id=evento.id))
    return novas


def _mensagem(
    agendamento: Agendamento,
    modelo: ModeloDeMensagem,
    texto: str,
    agora: datetime,
    evento_id: int | None = None,
) -> dict[str, Any]:
    return {
        "empresa_id": agendamento.empresa_id,
        "site_id": agendamento.site_id,
        "agendamento_id": agendamento.id,
        "evento_id": evento_id,
        "modelo": modelo,
        "canal": CANAL,
        "para": agendamento.motorista_celular,
        "texto": texto,
        "situacao": "guardada",
        "criada_em": agora,
    }


class _Sites:
    """O nome e o fuso de cada site, lidos uma vez por preparo."""

    def __init__(self, sessao: Session) -> None:
        self._sessao = sessao
        self._lidos: dict[tuple[int, int], HorarioDoSite] = {}

    def de(self, agendamento: Agendamento) -> HorarioDoSite:
        chave = (agendamento.empresa_id, agendamento.site_id)
        if chave not in self._lidos:
            self._lidos[chave] = cadastro.horario_do_site(
                self._sessao, empresa_id=agendamento.empresa_id, site_id=agendamento.site_id
            )
        return self._lidos[chave]


# --- Os textos --------------------------------------------------------------------------------


def _confirmacao(agendamento: Agendamento, site: HorarioDoSite) -> str:
    fuso = ZoneInfo(site.fuso)
    inicio = agendamento.janela_inicio.astimezone(fuso)
    fim = agendamento.janela_fim.astimezone(fuso)
    return (
        f"Olá! {agendamento.tipo.capitalize()} agendada: {site.nome}, {inicio:%d/%m}, "
        f"das {inicio:%H:%M} às {fim:%H:%M} (agendamento {agendamento.codigo_externo}). "
        "Os avisos da fila e da doca vão chegar por aqui."
    )


def _aviso(
    sessao: Session,
    modelo: ModeloDeMensagem,
    evento: Evento,
    visita: Visita,
    agendamento: Agendamento,
    site: HorarioDoSite,
) -> str:
    if modelo == "na_fila":
        chegada = (visita.chegou_em or evento.momento).astimezone(ZoneInfo(site.fuso))
        posicao = patio.posicao_na_fila(sessao, visita)
        return (
            f"Chegada registrada às {chegada:%H:%M}. Você está na fila, posição {posicao}. "
            "Espere o aviso da doca por aqui."
        )
    if modelo == "chamada":
        return f"Sua vez! Siga para a {evento.dados['doca']}."
    return f"{agendamento.tipo.capitalize()} terminada. Pode sair pela portaria. Boa viagem!"


# --- Ler --------------------------------------------------------------------------------------


def conversa(sessao: Session, acesso: Acesso, agendamento_id: int) -> list[Mensagem]:
    """As mensagens de um agendamento que o usuário vê, na ordem em que foram feitas.

    Raises:
        NaoEncontradoError: se o agendamento não for visível para este usuário.
    """
    agendamento = agendamentos.obter(sessao, acesso, agendamento_id)
    return list(
        sessao.scalars(
            select(Mensagem)
            .where(
                Mensagem.empresa_id == acesso.empresa_id,
                Mensagem.agendamento_id == agendamento.id,
            )
            .order_by(Mensagem.criada_em, Mensagem.id)
        )
    )


def conversas(
    sessao: Session, acesso: Acesso, site_id: int, *, limite: int = ULTIMAS_CONVERSAS
) -> list[Conversa]:
    """As conversas de um site que o usuário vê, da última mensagem para a primeira.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    numeradas = (
        select(
            Mensagem.id,
            func.row_number()
            .over(
                partition_by=Mensagem.agendamento_id,
                order_by=(Mensagem.criada_em.desc(), Mensagem.id.desc()),
            )
            .label("ordem"),
            func.count().over(partition_by=Mensagem.agendamento_id).label("quantas"),
        )
        .where(Mensagem.empresa_id == acesso.empresa_id, Mensagem.site_id == site.id)
        .subquery()
    )
    linhas = sessao.execute(
        select(Mensagem, numeradas.c.quantas)
        .join(numeradas, numeradas.c.id == Mensagem.id)
        .where(numeradas.c.ordem == 1)
        .order_by(Mensagem.criada_em.desc(), Mensagem.id.desc())
        .limit(limite)
    )
    return [Conversa(mensagem.agendamento_id, mensagem, quantas) for mensagem, quantas in linhas]

"""Tabelas da portaria (SDD 3.2, 5.1 e 5.2): passagens, visitas, eventos e exceções.

A passagem é prova da chegada (SDD 5.5): fica guardada exatamente como veio (``como_veio``),
e não se edita. As colunas ao lado repetem o que as consultas usam (site, faixa, horários).

A visita nasce na chegada (D-35). O evento só se acrescenta: um gatilho no banco recusa alterar
ou apagar (migração 0008).
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base, do_pai_na_mesma_empresa, pode_ser_pai, texto_de_lista
from nuvem.cadastro.modelos import Sentido


class PassagemRecebida(Base):
    """Uma passagem que uma caixa de borda mandou."""

    __tablename__ = "passagem"
    __table_args__ = (
        pode_ser_pai(),
        do_pai_na_mesma_empresa("site"),
        do_pai_na_mesma_empresa("faixa"),
        do_pai_na_mesma_empresa("caixa_borda", coluna="caixa_id"),
        # A tela da portaria lista as últimas passagens de um site.
        Index("ix_passagem_site_id_inicio", "site_id", "inicio"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    """O id que a caixa gerou: o mesmo id de novo é a mesma passagem (reenvio seguro)."""
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    caixa_id: Mapped[int]
    faixa_id: Mapped[int]
    sentido: Mapped[Sentido] = mapped_column(texto_de_lista(Sentido, "sentido"))
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """Quando o veículo começou a passar, no relógio da caixa."""
    fim: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recebida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """Quando a nuvem recebeu (pode ser bem depois do ``inicio``, se a internet caiu)."""
    como_veio: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """A passagem inteira, no formato do contrato (``contratos.Passagem``)."""


EstadoDaVisita = Literal["NA_FILA", "EXCECAO", "NAO_VEIO", "SAIU"]
"""Os estados do mês 2 (SDD 5.2); chamada, doca, liberação e recusa entram no mês 3."""

TipoDeEvento = Literal["check_in", "excecao", "nao_veio", "saiu_sem_atendimento"]
"""O que aconteceu com a visita; cada tipo leva a um estado (``visitas.TRANSICOES``)."""

MotivoDaExcecao = Literal["sem_placa", "sem_candidato", "pontos_baixos", "candidatos_proximos"]
"""Por que a chegada não casou (SDD 5.3)."""
SituacaoDaExcecao = Literal["aberta", "resolvida"]


class Visita(Base):
    """A estadia de um caminhão no site, da chegada à saída (ou o "não veio")."""

    __tablename__ = "visita"
    __table_args__ = (
        pode_ser_pai(),
        do_pai_na_mesma_empresa("site"),
        do_pai_na_mesma_empresa("agendamento"),
        do_pai_na_mesma_empresa("passagem", coluna="passagem_entrada_id"),
        do_pai_na_mesma_empresa("passagem", coluna="passagem_saida_id"),
        UniqueConstraint("agendamento_id"),
        # A mesma passagem de novo não cria outra visita nem fecha outra (SDD 5.3).
        UniqueConstraint("passagem_entrada_id"),
        UniqueConstraint("passagem_saida_id"),
        CheckConstraint("(estado = 'NAO_VEIO') = (chegou_em IS NULL)", name="chegada"),
        CheckConstraint("(estado = 'SAIU') = (saiu_em IS NOT NULL)", name="saida"),
        CheckConstraint(
            "estado <> 'NAO_VEIO' OR agendamento_id IS NOT NULL", name="nao_veio_tem_agendamento"
        ),
        # A saída procura a visita aberta do site; as telas listam por estado.
        Index("ix_visita_site_id_estado", "site_id", "estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    agendamento_id: Mapped[int | None]
    """O agendamento casado; vazio na exceção ainda sem resolver e na visita sem agendamento."""
    estado: Mapped[EstadoDaVisita] = mapped_column(texto_de_lista(EstadoDaVisita, "estado"))
    composicao: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    """As placas confirmadas, cada uma lida (pela câmera) ou inferida (do agendamento; D-17)."""
    chegou_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """A hora da passagem de entrada (a prova da chegada); vazia no "não veio"."""
    saiu_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    passagem_entrada_id: Mapped[UUID | None]
    passagem_saida_id: Mapped[UUID | None]
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Evento(Base):
    """Algo que aconteceu com uma visita. Só se acrescenta (SDD 5.5)."""

    __tablename__ = "evento"
    __table_args__ = (
        do_pai_na_mesma_empresa("visita"),
        do_pai_na_mesma_empresa("usuario"),
        do_pai_na_mesma_empresa("passagem"),
        Index("ix_evento_visita_id", "visita_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    visita_id: Mapped[int]
    tipo: Mapped[TipoDeEvento] = mapped_column(texto_de_lista(TipoDeEvento, "tipo_de_evento"))
    estado: Mapped[EstadoDaVisita] = mapped_column(texto_de_lista(EstadoDaVisita, "estado"))
    """O estado em que a visita ficou."""
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """Quando aconteceu (ex.: a hora da passagem, no relógio da caixa)."""
    registrado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usuario_id: Mapped[int | None]
    """Quem fez; vazio = o sistema."""
    passagem_id: Mapped[UUID | None]
    """A passagem do evento (e, por ela, as fotos)."""
    dados: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Excecao(Base):
    """Uma chegada que o sistema não casou com segurança: o porteiro resolve (SDD 5.2)."""

    __tablename__ = "excecao"
    __table_args__ = (
        do_pai_na_mesma_empresa("visita"),
        do_pai_na_mesma_empresa("passagem"),
        do_pai_na_mesma_empresa("usuario", coluna="resolvida_por"),
        UniqueConstraint("visita_id"),
        CheckConstraint(
            "(situacao = 'aberta') = (resolvida_em IS NULL)", name="resolvida_tem_hora"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    visita_id: Mapped[int]
    passagem_id: Mapped[UUID]
    motivo: Mapped[MotivoDaExcecao] = mapped_column(texto_de_lista(MotivoDaExcecao, "motivo"))
    candidatos: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    """Os agendamentos que chegaram perto, com os pontos de cada um (SDD 5.3)."""
    situacao: Mapped[SituacaoDaExcecao] = mapped_column(
        texto_de_lista(SituacaoDaExcecao, "situacao_da_excecao")
    )
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolvida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolvida_por: Mapped[int | None]
    """Quem resolveu; vazio = o sistema (ex.: o caminhão saiu antes)."""
    resolucao: Mapped[str | None] = mapped_column(String(200))

"""Tabelas do agendamento (SDD 5.1): os agendamentos de cada site e as mudanças de cada um.

O agendamento aponta para o site pela dupla (site, empresa), e a mudança aponta para o
agendamento do mesmo jeito (SDD 5.5). A situação é só ativo ou cancelado: o andamento da
chegada é da visita (D-32).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from contratos.placa import FORMATO_CANONICO
from nuvem.agendamento.formato import (
    FORMATO_DA_CHAVE_NFE,
    FORMATO_DO_CELULAR,
    MAXIMO_DE_REBOQUES,
    Tipo,
)
from nuvem.banco import Base, do_pai_na_mesma_empresa, pode_ser_pai, texto_de_lista

Origem = Literal["link", "planilha", "api_generica"]
"""Os conectores do MVP (SDD 3.4); cada conector novo entra aqui."""

Situacao = Literal["ativo", "cancelado"]

Via = Literal["link", "planilha", "api_generica", "painel"]
"""Por onde veio a mudança: por um conector ou pelo painel (ex.: o gestor cancelou)."""

TipoDeMudanca = Literal["criado", "alterado", "cancelado"]


class Agendamento(Base):
    """Um caminhão esperado no site, numa janela de horário."""

    __tablename__ = "agendamento"
    __table_args__ = (
        pode_ser_pai(),
        do_pai_na_mesma_empresa("site"),
        # O reenvio do mesmo código, pela mesma origem, atualiza em vez de duplicar (D-33).
        UniqueConstraint("site_id", "origem", "codigo_externo"),
        CheckConstraint("janela_fim > janela_inicio", name="janela_em_ordem"),
        CheckConstraint(f"placa_cavalo ~ '{FORMATO_CANONICO}'", name="placa_cavalo_formato"),
        CheckConstraint(
            f"cardinality(placas_reboques) <= {MAXIMO_DE_REBOQUES}", name="reboques_no_maximo"
        ),
        CheckConstraint(f"motorista_celular ~ '{FORMATO_DO_CELULAR}'", name="celular_formato"),
        CheckConstraint("toneladas > 0", name="toneladas_positivas"),
        CheckConstraint(f"chave_nfe ~ '{FORMATO_DA_CHAVE_NFE}'", name="chave_nfe_formato"),
        CheckConstraint("char_length(codigo_externo) > 0", name="codigo_externo_preenchido"),
        do_pai_na_mesma_empresa("link_transportadora", coluna="link_id"),
        CheckConstraint("link_id IS NULL OR origem = 'link'", name="link_so_na_origem_link"),
        # A tela e o casamento procuram os agendamentos de um site por dia.
        Index("ix_agendamento_site_id_janela_inicio", "site_id", "janela_inicio"),
        # A confirmação ao motorista procura os agendamentos mudados há pouco (D-47).
        Index("ix_agendamento_atualizado_em", "atualizado_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    janela_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    janela_fim: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tipo: Mapped[Tipo] = mapped_column(texto_de_lista(Tipo, "tipo"))
    placa_cavalo: Mapped[str] = mapped_column(String(7))
    placas_reboques: Mapped[list[str]] = mapped_column(ARRAY(String(7)))
    motorista_nome: Mapped[str | None] = mapped_column(String(120))
    motorista_celular: Mapped[str | None] = mapped_column(String(14))
    """Com o +55 (ex.: ``+5511987654321``)."""
    toneladas: Mapped[Decimal | None] = mapped_column(Numeric(9, 3))
    chave_nfe: Mapped[str | None] = mapped_column(String(44))
    origem: Mapped[Origem] = mapped_column(texto_de_lista(Origem, "origem"))
    codigo_externo: Mapped[str] = mapped_column(String(100))
    situacao: Mapped[Situacao] = mapped_column(texto_de_lista(Situacao, "situacao"))
    link_id: Mapped[int | None]
    """O link da transportadora que criou o agendamento (só na origem ``link``)."""
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MudancaAgendamento(Base):
    """Uma mudança num agendamento: a criação, cada alteração e o cancelamento.

    Só se acrescenta. Guarda os campos que mudaram, como eram e como ficaram (na criação, só
    como ficaram).
    """

    __tablename__ = "agendamento_mudanca"
    __table_args__ = (
        do_pai_na_mesma_empresa("agendamento"),
        do_pai_na_mesma_empresa("usuario"),
        Index("ix_agendamento_mudanca_agendamento_id", "agendamento_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    agendamento_id: Mapped[int]
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tipo: Mapped[TipoDeMudanca] = mapped_column(texto_de_lista(TipoDeMudanca, "tipo_de_mudanca"))
    via: Mapped[Via] = mapped_column(texto_de_lista(Via, "via"))
    usuario_id: Mapped[int | None]
    """Quem fez, se foi uma pessoa do cliente (o link da transportadora não tem)."""
    antes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    depois: Mapped[dict[str, Any]] = mapped_column(JSONB)


class LinkTransportadora(Base):
    """Um link de agendamento que o gestor manda a uma transportadora (SDD 8.2 e D-34).

    O código vai no endereço e aparece uma vez só, para quem gerou; aqui fica só o resumo.
    """

    __tablename__ = "link_transportadora"
    __table_args__ = (
        pode_ser_pai(),
        do_pai_na_mesma_empresa("site"),
        do_pai_na_mesma_empresa("usuario", coluna="criado_por"),
        CheckConstraint("limite_de_envios > 0", name="limite_positivo"),
        CheckConstraint("envios >= 0 AND envios <= limite_de_envios", name="envios_no_limite"),
        CheckConstraint("vence_em > criado_em", name="vence_depois_de_criado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    nome: Mapped[str] = mapped_column(String(120))
    """Para quem é o link (ex.: o nome da transportadora)."""
    codigo_resumo: Mapped[str] = mapped_column(String(64), unique=True)
    """SHA-256 do código do endereço."""
    criado_por: Mapped[int]
    """O gestor que gerou."""
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vence_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    limite_de_envios: Mapped[int]
    """Quantos agendamentos o link pode criar."""
    envios: Mapped[int]
    """Quantos agendamentos o link já criou."""

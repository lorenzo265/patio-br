"""Tabela das mensagens ao motorista (SDD 5.1 e D-47).

A mensagem aponta para o agendamento, para o evento que a gerou e para o site pela dupla (pai,
empresa) (SDD 5.5). O texto fica pronto: é o que o motorista leu.
"""

from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.agendamento.formato import FORMATO_DO_CELULAR
from nuvem.banco import Base, do_pai_na_mesma_empresa, texto_de_lista

ModeloDeMensagem = Literal["confirmacao", "na_fila", "chamada", "pode_sair"]
"""A confirmação do agendamento e os avisos do check-in, da chamada e do fim na doca."""

Canal = Literal["demonstracao"]
"""Por onde a mensagem vai. O de demonstração só guarda; WhatsApp e SMS entram no mês 4."""

SituacaoDaMensagem = Literal["guardada"]
"""No canal de demonstração, a mensagem só fica guardada (no mês 4: enviada, entregue...)."""


class Mensagem(Base):
    """Uma mensagem ao motorista de um agendamento."""

    __tablename__ = "mensagem"
    __table_args__ = (
        do_pai_na_mesma_empresa("site"),
        do_pai_na_mesma_empresa("agendamento"),
        do_pai_na_mesma_empresa("evento"),
        # Cada evento avisa uma vez só; cada celular do agendamento é confirmado uma vez só.
        UniqueConstraint("evento_id"),
        Index(
            "uq_mensagem_confirmacao",
            "agendamento_id",
            "para",
            unique=True,
            postgresql_where=text("modelo = 'confirmacao'"),
        ),
        CheckConstraint("(modelo = 'confirmacao') = (evento_id IS NULL)", name="aviso_tem_evento"),
        CheckConstraint(f"para ~ '{FORMATO_DO_CELULAR}'", name="para_formato"),
        # A tela mostra a conversa de um agendamento e as últimas conversas de um site.
        Index("ix_mensagem_agendamento_id", "agendamento_id"),
        Index("ix_mensagem_site_id_criada_em", "site_id", "criada_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    agendamento_id: Mapped[int]
    evento_id: Mapped[int | None]
    """O evento da visita que gerou o aviso; vazio na confirmação."""
    modelo: Mapped[ModeloDeMensagem] = mapped_column(
        texto_de_lista(ModeloDeMensagem, "modelo_de_mensagem")
    )
    canal: Mapped[Canal] = mapped_column(texto_de_lista(Canal, "canal"))
    para: Mapped[str] = mapped_column(String(14))
    """O celular, com o +55 (o do agendamento na hora da mensagem)."""
    texto: Mapped[str] = mapped_column(String(500))
    situacao: Mapped[SituacaoDaMensagem] = mapped_column(
        texto_de_lista(SituacaoDaMensagem, "situacao_da_mensagem")
    )
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))

"""Tabelas das mensagens ao motorista (SDD 5.1, D-47, D-58 e D-63).

A mensagem aponta para o agendamento, para o evento que a gerou e para o site pela dupla (pai,
empresa) (SDD 5.5). O texto fica pronto: é o que o motorista leu.

A autorização do WhatsApp é do celular, numa empresa (D-58). A mensagem recebida é da
plataforma, como a fila de tarefas: o número do WhatsApp é um só para todos os clientes, e a
empresa só se sabe pelo que o texto diz.
"""

from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.agendamento.formato import FORMATO_DO_CELULAR
from nuvem.banco import Base, do_pai_na_mesma_empresa, texto_de_lista

ModeloDeMensagem = Literal["confirmacao", "na_fila", "chamada", "pode_sair"]
"""A confirmação do agendamento e os avisos do check-in, da chamada e do fim na doca."""

Canal = Literal["demonstracao", "whatsapp", "sms"]
"""Por onde a mensagem vai. O de demonstração só guarda (D-45 e D-63)."""

SituacaoDaMensagem = Literal["guardada", "enviada", "entregue", "lida", "falhou"]
"""Guardada é a que ainda não saiu (no canal de demonstração, nunca sai)."""

ResultadoDaRecebida = Literal["autorizou", "saiu", "ignorada"]


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
        # O aviso da Meta acha a mensagem pelo id dela no canal.
        UniqueConstraint("canal", "id_no_canal"),
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
    variaveis: Mapped[list[str] | None] = mapped_column(JSONB)
    """As variáveis do modelo do WhatsApp, na ordem (``modelos_do_whatsapp``)."""
    situacao: Mapped[SituacaoDaMensagem] = mapped_column(
        texto_de_lista(SituacaoDaMensagem, "situacao_da_mensagem")
    )
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    id_no_canal: Mapped[str | None] = mapped_column(String(100))
    """O id que o canal deu à mensagem (no WhatsApp, o ``wamid``)."""
    enviada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entregue_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    falhou_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erro: Mapped[str | None] = mapped_column(String(300))
    """O código e o texto do erro do canal, quando falhou."""
    cobranca: Mapped[str | None] = mapped_column(String(30))
    """A categoria de cobrança que a Meta avisou (ex.: ``utility``)."""


class AutorizacaoWhatsApp(Base):
    """O celular que autorizou receber os avisos de uma empresa pelo WhatsApp (D-58)."""

    __tablename__ = "autorizacao_whatsapp"
    __table_args__ = (
        Index(
            "uq_autorizacao_whatsapp_ativa",
            "empresa_id",
            "celular",
            unique=True,
            postgresql_where=text("revogada_em IS NULL"),
        ),
        CheckConstraint(f"celular ~ '{FORMATO_DO_CELULAR}'", name="celular_formato"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"))
    celular: Mapped[str] = mapped_column(String(14))
    autorizada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    texto: Mapped[str] = mapped_column(String(1000))
    """O que o motorista mandou: a prova da autorização."""
    id_no_whatsapp: Mapped[str] = mapped_column(String(100))
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MensagemRecebida(Base):
    """Uma mensagem que alguém mandou ao número do produto (D-63)."""

    __tablename__ = "mensagem_recebida"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_no_whatsapp: Mapped[str] = mapped_column(String(100), unique=True)
    de: Mapped[str] = mapped_column(String(20))
    """O número de quem mandou, como o WhatsApp dá."""
    texto: Mapped[str] = mapped_column(String(1000))
    recebida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"))
    """A empresa que o texto diz; vazia quando o texto não diz nenhuma."""
    resultado: Mapped[ResultadoDaRecebida] = mapped_column(
        texto_de_lista(ResultadoDaRecebida, "resultado_da_recebida")
    )
    tratada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))

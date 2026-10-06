"""Tabelas dos alertas (SDD 5.1 e 8.1, D-68).

O alerta e o aviso dele são da empresa do site; os da plataforma (a tarefa que falhou) não têm
empresa nem site. A autorização do WhatsApp é de uma pessoa: um usuário do cliente (com a empresa
dele) ou alguém da administração.
"""

from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base, do_pai_na_mesma_empresa, texto_de_lista

TipoDeAlerta = Literal[
    "estadia_perto",
    "estadia_passou",
    "sem_agendamento",
    "caixa_sem_contato",
    "camera_parada",
    "relogio_errado",
    "motorista_nao_avisado",
    "tarefa_falhou",
]

SituacaoDoAviso = Literal["guardado", "enviado", "falhou"]
"""Guardado (ainda não foi, ou não há WhatsApp), enviado, ou recusado de vez."""


class Alerta(Base):
    """Um alerta: abre uma vez e fecha sozinho quando a situação passa."""

    __tablename__ = "alerta"
    __table_args__ = (
        do_pai_na_mesma_empresa("site"),
        CheckConstraint("(empresa_id IS NULL) = (site_id IS NULL)", name="da_plataforma"),
        # No máximo um aberto do mesmo tipo sobre a mesma coisa.
        Index(
            "uq_alerta_aberto",
            "tipo",
            "chave",
            unique=True,
            postgresql_where=text("fechado_em IS NULL"),
        ),
        Index("ix_alerta_site_id_aberto_em", "site_id", "aberto_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None]
    site_id: Mapped[int | None]
    tipo: Mapped[TipoDeAlerta] = mapped_column(texto_de_lista(TipoDeAlerta, "tipo_de_alerta"))
    chave: Mapped[str] = mapped_column(String(100))
    """Sobre o quê (ex.: ``visita:12``, ``caixa:3``, ``camera:3:21``, ``tarefa:7``)."""
    texto: Mapped[str] = mapped_column(String(300))
    """O que aparece na tela e vai na mensagem."""
    aberto_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fechado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AlertasNoWhatsApp(Base):
    """O pedido de uma pessoa para receber os alertas graves pelo WhatsApp e, depois de ela
    mandar o código, a autorização daquele celular (D-68)."""

    __tablename__ = "alertas_no_whatsapp"
    __table_args__ = (
        do_pai_na_mesma_empresa("usuario"),
        CheckConstraint("(usuario_id IS NULL) <> (administrador_id IS NULL)", name="uma_pessoa"),
        CheckConstraint("(usuario_id IS NULL) = (empresa_id IS NULL)", name="empresa_do_usuario"),
        CheckConstraint(
            "(celular IS NULL) = (autorizada_em IS NULL)", name="celular_na_autorizacao"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None]
    usuario_id: Mapped[int | None]
    administrador_id: Mapped[int | None] = mapped_column(ForeignKey("administrador.id"))
    codigo_resumo: Mapped[str] = mapped_column(String(64), unique=True)
    """SHA-256 do código de uso único (o código só aparece na tela de quem pediu)."""
    pedido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vence_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    celular: Mapped[str | None] = mapped_column(String(14))
    autorizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    texto: Mapped[str | None] = mapped_column(String(1000))
    """O que a pessoa mandou: a prova da autorização."""
    id_no_whatsapp: Mapped[str | None] = mapped_column(String(100))
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AvisoDeAlerta(Base):
    """Um alerta grave mandado pelo WhatsApp a quem autorizou (D-68)."""

    __tablename__ = "aviso_de_alerta"
    __table_args__ = (
        CheckConstraint("(usuario_id IS NULL) <> (administrador_id IS NULL)", name="uma_pessoa"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None]
    """A do alerta (para apagar junto com a empresa de demonstração)."""
    alerta_id: Mapped[int] = mapped_column(ForeignKey("alerta.id"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    administrador_id: Mapped[int | None] = mapped_column(ForeignKey("administrador.id"))
    celular: Mapped[str] = mapped_column(String(14))
    situacao: Mapped[SituacaoDoAviso] = mapped_column(
        texto_de_lista(SituacaoDoAviso, "situacao_do_aviso")
    )
    id_no_canal: Mapped[str | None] = mapped_column(String(100))
    erro: Mapped[str | None] = mapped_column(String(300))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

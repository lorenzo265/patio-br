"""As tabelas da demonstração: o dia (D-49), com o roteiro das chegadas ao vivo e onde ele
está, e o link de demonstração por empresa visitada (D-52 e D-54)."""

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base, do_pai_na_mesma_empresa, texto_de_lista

SituacaoDoDia = Literal["rodando", "terminado"]


class DiaDeDemonstracao(Base):
    """Um "começar o dia" de um site de demonstração."""

    __tablename__ = "dia_de_demonstracao"
    __table_args__ = (
        do_pai_na_mesma_empresa("site"),
        do_pai_na_mesma_empresa("caixa_borda", coluna="caixa_id"),
        do_pai_na_mesma_empresa("usuario", coluna="lider_id"),
        CheckConstraint("termina_em > comecou_em", name="termina_depois"),
        CheckConstraint("enviadas >= 0", name="enviadas_positivas"),
        # Um dia rodando por site.
        Index(
            "uq_dia_de_demonstracao_rodando",
            "site_id",
            unique=True,
            postgresql_where=text("situacao = 'rodando'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    caixa_id: Mapped[int]
    """A caixa de borda (de mentira) em nome de quem as passagens chegam."""
    lider_id: Mapped[int]
    """Em nome de quem o líder automático chama, começa e termina."""
    comecou_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    termina_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    chegadas: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    """As chegadas ao vivo, pela hora: ``em`` (ISO), a ``placa`` certa e a ``lida``."""
    enviadas: Mapped[int]
    """Quantas chegadas já foram mandadas."""
    saidas: Mapped[list[int]] = mapped_column(JSONB)
    """As visitas que o líder já mandou à saída (a passagem de saída ainda pode estar na fila)."""
    ultima_acao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """A última vez que o líder automático fez alguma coisa."""
    situacao: Mapped[SituacaoDoDia] = mapped_column(
        texto_de_lista(SituacaoDoDia, "situacao_do_dia")
    )


class LinkDemonstracao(Base):
    """Um link de demonstração para uma empresa visitada (D-52 e D-54).

    É da plataforma, como a administração que o gera: fica fora das empresas. A empresa de
    demonstração nasce na primeira entrada e é apagada quando o link vence ou é revogado; o
    link fica, para a lista da administração.
    """

    __tablename__ = "link_demonstracao"
    __table_args__ = (CheckConstraint("vence_em > criado_em", name="vence_depois"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    """A empresa visitada, como aparece na página do link."""
    codigo_resumo: Mapped[str] = mapped_column(String(64), unique=True)
    """SHA-256 do código do endereço (o código só aparece uma vez, para quem gerou)."""
    criado_por: Mapped[int] = mapped_column(ForeignKey("administrador.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vence_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"), unique=True)
    """A empresa de demonstração; vazia antes da primeira entrada e depois de apagada."""
    ultima_entrada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    apagada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Quando a empresa de demonstração foi apagada."""

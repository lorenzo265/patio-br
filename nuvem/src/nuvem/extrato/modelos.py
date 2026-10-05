"""Tabelas do extrato (SDD 5.1, 5.4 e D-48): os parâmetros do site, a linha de base e o extrato.

As três apontam para o site pela dupla (site, empresa) (SDD 5.5). O extrato guardado só se
acrescenta: os gatilhos da função so_acrescenta (migração 0008) recusam mudar ou apagar.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import CheckConstraint, Date, DateTime, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base, do_pai_na_mesma_empresa, texto_de_lista

OrigemDaLinhaDeBase = Literal["exemplo", "modo_sombra"]
"""Exemplo: gravada pela semente da demonstração. Modo sombra: medida no site (seção 9)."""


class ParametrosSite(Base):
    """Os números do site para o extrato; sem linha aqui, valem os da lei e nada da portaria."""

    __tablename__ = "parametros_site"
    __table_args__ = (
        do_pai_na_mesma_empresa("site"),
        UniqueConstraint("site_id"),
        CheckConstraint("valor_da_estadia > 0", name="valor_positivo"),
        CheckConstraint("franquia_minutos > 0", name="franquia_positiva"),
        CheckConstraint("postos_antes >= 0 AND postos_depois >= 0", name="postos_positivos"),
        CheckConstraint("custo_mensal_do_posto > 0", name="custo_do_posto_positivo"),
        CheckConstraint("custo_hora_doca > 0", name="custo_hora_doca_positivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    valor_da_estadia: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    """R$ por tonelada e hora acima da franquia."""
    franquia_minutos: Mapped[int]
    postos_antes: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    """Pontos de portaria 24 horas antes do sistema."""
    postos_depois: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    custo_mensal_do_posto: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    custo_hora_doca: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LinhaDeBase(Base):
    """As medidas do site antes do sistema, para comparar cada mês (SDD 5.4)."""

    __tablename__ = "linha_de_base"
    __table_args__ = (
        do_pai_na_mesma_empresa("site"),
        UniqueConstraint("site_id"),
        CheckConstraint("ate > de", name="periodo_em_ordem"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    origem: Mapped[OrigemDaLinhaDeBase] = mapped_column(
        texto_de_lista(OrigemDaLinhaDeBase, "origem_da_linha_de_base")
    )
    de: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ate: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    medidas: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """No formato de ``contas.Medidas.para_json``."""
    gravada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Extrato(Base):
    """O extrato de um mês fechado, como foi calculado na primeira vez. Só se acrescenta."""

    __tablename__ = "extrato"
    __table_args__ = (
        do_pai_na_mesma_empresa("site"),
        UniqueConstraint("site_id", "mes", "versao_da_regra"),
        CheckConstraint("extract(day from mes) = 1", name="mes_no_dia_1"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    mes: Mapped[date] = mapped_column(Date)
    """O dia 1 do mês."""
    versao_da_regra: Mapped[int]
    numeros: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """As medidas, a economia, os parâmetros e a linha de base usados."""
    guardado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))

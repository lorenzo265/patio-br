"""frota: a saúde da caixa (D-65)

Revisão: 0021
Anterior: 0020
Criada em: 2026-10-06

A caixa de borda guarda o último contato, as versões, a última saúde e a diferença do relógio;
o histórico curto (7 dias) fica na tabela nova ``saude_caixa``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saude_caixa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("caixa_id", sa.Integer(), nullable=False),
        sa.Column("recebida_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("momento", sa.DateTime(timezone=True), nullable=False),
        sa.Column("diferenca_do_relogio", sa.Float(), nullable=False),
        sa.Column("cpu", sa.Float(), nullable=False),
        sa.Column("temperatura", sa.Float(), nullable=True),
        sa.Column("memoria", sa.Float(), nullable=False),
        sa.Column("disco", sa.Float(), nullable=False),
        sa.Column("cameras_no_ar", sa.Integer(), nullable=False),
        sa.Column("cameras", sa.Integer(), nullable=False),
        sa.Column("passagens_na_fila", sa.Integer(), nullable=False),
        sa.Column("dados", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["caixa_id", "empresa_id"],
            ["caixa_borda.id", "caixa_borda.empresa_id"],
            name=op.f("fk_saude_caixa_caixa_id_caixa_borda"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saude_caixa")),
    )
    op.create_index(
        "ix_saude_caixa_caixa_id_recebida_em",
        "saude_caixa",
        ["caixa_id", "recebida_em"],
        unique=False,
    )
    op.add_column(
        "caixa_borda", sa.Column("ultimo_contato", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("caixa_borda", sa.Column("versao_programa", sa.String(length=100), nullable=True))
    op.add_column("caixa_borda", sa.Column("versao_leitor", sa.String(length=100), nullable=True))
    op.add_column(
        "caixa_borda",
        sa.Column("ultima_saude", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("caixa_borda", sa.Column("diferenca_do_relogio", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("caixa_borda", "diferenca_do_relogio")
    op.drop_column("caixa_borda", "ultima_saude")
    op.drop_column("caixa_borda", "versao_leitor")
    op.drop_column("caixa_borda", "versao_programa")
    op.drop_column("caixa_borda", "ultimo_contato")
    op.drop_index("ix_saude_caixa_caixa_id_recebida_em", table_name="saude_caixa")
    op.drop_table("saude_caixa")

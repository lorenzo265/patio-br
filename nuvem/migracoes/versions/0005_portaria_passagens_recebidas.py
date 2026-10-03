"""portaria: passagens recebidas da borda

Revisão: 0005
Anterior: 0004
Criada em: 2026-10-03

A passagem aponta para o site, a faixa e a caixa pela dupla (pai, empresa), e fica guardada
como veio (como_veio, JSONB). O autogenerate repetia o CHECK do sentido; ficou um, com o nome
do padrão.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "passagem",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("caixa_id", sa.Integer(), nullable=False),
        sa.Column("faixa_id", sa.Integer(), nullable=False),
        sa.Column(
            "sentido",
            sa.Enum("entrada", "saida", name="sentido", native_enum=False, create_constraint=False),
            nullable=False,
        ),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fim", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recebida_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("como_veio", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("sentido IN ('entrada', 'saida')", name=op.f("ck_passagem_sentido")),
        sa.ForeignKeyConstraint(
            ["caixa_id", "empresa_id"],
            ["caixa_borda.id", "caixa_borda.empresa_id"],
            name=op.f("fk_passagem_caixa_id_caixa_borda"),
        ),
        sa.ForeignKeyConstraint(
            ["faixa_id", "empresa_id"],
            ["faixa.id", "faixa.empresa_id"],
            name=op.f("fk_passagem_faixa_id_faixa"),
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_passagem_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_passagem")),
    )
    op.create_index("ix_passagem_site_id_inicio", "passagem", ["site_id", "inicio"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_passagem_site_id_inicio", table_name="passagem")
    op.drop_table("passagem")

"""demonstração: o dia de demonstração (D-49)

Revisão: 0016
Anterior: 0015
Criada em: 2026-10-05

O dia aponta para o site, para a caixa de borda e para o líder pela dupla (pai, empresa). Um dia
rodando por site (índice único parcial).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dia_de_demonstracao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("caixa_id", sa.Integer(), nullable=False),
        sa.Column("lider_id", sa.Integer(), nullable=False),
        sa.Column("comecou_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("termina_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chegadas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enviadas", sa.Integer(), nullable=False),
        sa.Column("saidas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ultima_acao_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "situacao",
            sa.Enum(
                "rodando",
                "terminado",
                name="situacao_do_dia",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "situacao IN ('rodando', 'terminado')",
            name=op.f("ck_dia_de_demonstracao_situacao_do_dia"),
        ),
        sa.CheckConstraint("enviadas >= 0", name=op.f("ck_dia_de_demonstracao_enviadas_positivas")),
        sa.CheckConstraint(
            "termina_em > comecou_em", name=op.f("ck_dia_de_demonstracao_termina_depois")
        ),
        sa.ForeignKeyConstraint(
            ["caixa_id", "empresa_id"],
            ["caixa_borda.id", "caixa_borda.empresa_id"],
            name=op.f("fk_dia_de_demonstracao_caixa_id_caixa_borda"),
        ),
        sa.ForeignKeyConstraint(
            ["lider_id", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_dia_de_demonstracao_lider_id_usuario"),
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_dia_de_demonstracao_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dia_de_demonstracao")),
    )
    op.create_index(
        "uq_dia_de_demonstracao_rodando",
        "dia_de_demonstracao",
        ["site_id"],
        unique=True,
        postgresql_where=sa.text("situacao = 'rodando'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_dia_de_demonstracao_rodando",
        table_name="dia_de_demonstracao",
        postgresql_where=sa.text("situacao = 'rodando'"),
    )
    op.drop_table("dia_de_demonstracao")

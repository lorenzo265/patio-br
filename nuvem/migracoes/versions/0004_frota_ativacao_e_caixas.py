"""frota: códigos de ativação e caixas de borda

Revisão: 0004
Anterior: 0003
Criada em: 2026-10-03

As duas tabelas são dados do cliente: apontam para o site pela dupla (site, empresa). O banco
guarda só o resumo do código e da chave (SDD 7.4).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "caixa_borda",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("chave_resumo", sa.String(length=64), nullable=False),
        sa.Column("ativada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogada_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_caixa_borda_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_caixa_borda")),
        sa.UniqueConstraint("chave_resumo", name=op.f("uq_caixa_borda_chave_resumo")),
        sa.UniqueConstraint("id", "empresa_id", name=op.f("uq_caixa_borda_id_empresa_id")),
    )
    op.create_table(
        "codigo_ativacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("codigo_resumo", sa.String(length=64), nullable=False),
        sa.Column("criado_por", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["criado_por"],
            ["administrador.id"],
            name=op.f("fk_codigo_ativacao_criado_por_administrador"),
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_codigo_ativacao_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_codigo_ativacao")),
        sa.UniqueConstraint("codigo_resumo", name=op.f("uq_codigo_ativacao_codigo_resumo")),
    )


def downgrade() -> None:
    op.drop_table("codigo_ativacao")
    op.drop_table("caixa_borda")

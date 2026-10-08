"""link de senha (D-75)

Revisão: 0028
Anterior: 0027
Criada em: 2026-10-06

O link de uso único para a pessoa criar a própria senha.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | Sequence[str] | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "link_de_senha",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("codigo_resumo", sa.String(length=64), nullable=False),
        sa.Column("criado_por", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vence_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trocado_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["criado_por"],
            ["administrador.id"],
            name=op.f("fk_link_de_senha_criado_por_administrador"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_link_de_senha_usuario_id_usuario"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_link_de_senha")),
        sa.UniqueConstraint("codigo_resumo", name=op.f("uq_link_de_senha_codigo_resumo")),
    )
    op.create_index(
        op.f("ix_link_de_senha_usuario_id"), "link_de_senha", ["usuario_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_link_de_senha_usuario_id"), table_name="link_de_senha")
    op.drop_table("link_de_senha")

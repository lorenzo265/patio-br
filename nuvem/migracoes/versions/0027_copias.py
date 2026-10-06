"""copias (D-74)

Revisão: 0027
Anterior: 0026
Criada em: 2026-10-06

A batida do worker, as cópias do banco e as restaurações de teste: tabelas da plataforma.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027"
down_revision: str | Sequence[str] | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "batida",
        sa.Column("processo", sa.String(length=30), nullable=False),
        sa.Column("em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("processo", name=op.f("pk_batida")),
    )
    op.create_table(
        "copia_do_banco",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("feita_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tamanho", sa.BigInteger(), nullable=False),
        sa.Column("resumo", sa.String(length=64), nullable=False),
        sa.Column("migracao", sa.String(length=32), nullable=False),
        sa.Column("contagens", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ultimo_evento", sa.DateTime(timezone=True), nullable=True),
        sa.Column("apagada_em", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_copia_do_banco")),
        sa.UniqueConstraint("nome", name=op.f("uq_copia_do_banco_nome")),
    )
    op.create_index("ix_copia_do_banco_feita_em", "copia_do_banco", ["feita_em"], unique=False)
    op.create_table(
        "restauracao_de_teste",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("copia_id", sa.Integer(), nullable=False),
        sa.Column("feita_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("detalhe", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["copia_id"],
            ["copia_do_banco.id"],
            name=op.f("fk_restauracao_de_teste_copia_id_copia_do_banco"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_restauracao_de_teste")),
    )
    op.create_index(
        "ix_restauracao_de_teste_feita_em", "restauracao_de_teste", ["feita_em"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_restauracao_de_teste_feita_em", table_name="restauracao_de_teste")
    op.drop_table("restauracao_de_teste")
    op.drop_index("ix_copia_do_banco_feita_em", table_name="copia_do_banco")
    op.drop_table("copia_do_banco")
    op.drop_table("batida")

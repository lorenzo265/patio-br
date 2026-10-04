"""fila de tarefas do worker (D-38)

Revisão: 0010
Anterior: 0009
Criada em: 2026-10-04

Uma tabela da plataforma (sem empresa): o tipo e a chave únicos juntos, e um índice só das
pendentes, pela hora. O autogenerate repetia o CHECK de cada lista; ficou um, com o nome do
padrão.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tarefa_de_fundo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "casar_passagem", name="tipo_de_tarefa", native_enum=False, create_constraint=False
            ),
            nullable=False,
        ),
        sa.Column("chave", sa.String(length=100), nullable=False),
        sa.Column("dados", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "situacao",
            sa.Enum(
                "pendente",
                "feita",
                "falhou",
                name="situacao_da_tarefa",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("tentativas", sa.Integer(), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executar_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_erro", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "situacao IN ('pendente', 'feita', 'falhou')",
            name=op.f("ck_tarefa_de_fundo_situacao_da_tarefa"),
        ),
        sa.CheckConstraint(
            "tipo IN ('casar_passagem')", name=op.f("ck_tarefa_de_fundo_tipo_de_tarefa")
        ),
        sa.CheckConstraint("tentativas >= 0", name=op.f("ck_tarefa_de_fundo_tentativas_positivas")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tarefa_de_fundo")),
        sa.UniqueConstraint("tipo", "chave", name=op.f("uq_tarefa_de_fundo_tipo_chave")),
    )
    op.create_index(
        "ix_tarefa_de_fundo_pendentes",
        "tarefa_de_fundo",
        ["executar_em"],
        unique=False,
        postgresql_where=sa.text("situacao = 'pendente'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tarefa_de_fundo_pendentes",
        table_name="tarefa_de_fundo",
        postgresql_where=sa.text("situacao = 'pendente'"),
    )
    op.drop_table("tarefa_de_fundo")

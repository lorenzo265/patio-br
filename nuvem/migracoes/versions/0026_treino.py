"""treino (D-71)

Revisão: 0026
Anterior: 0025
Criada em: 2026-10-06

A autorização do treino (a cláusula do contrato de cada empresa) e os rótulos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | Sequence[str] | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "autorizacao_de_treino",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("clausula_em", sa.Date(), nullable=False),
        sa.Column("registrada_por", sa.Integer(), nullable=False),
        sa.Column("registrada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogada_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_autorizacao_de_treino_empresa_id_empresa")
        ),
        sa.ForeignKeyConstraint(
            ["registrada_por"],
            ["administrador.id"],
            name=op.f("fk_autorizacao_de_treino_registrada_por_administrador"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_autorizacao_de_treino")),
    )
    op.create_index(
        "uq_autorizacao_de_treino_ativa",
        "autorizacao_de_treino",
        ["empresa_id"],
        unique=True,
        postgresql_where=sa.text("revogada_em IS NULL"),
    )
    op.create_table(
        "rotulo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("passagem_id", sa.Uuid(), nullable=False),
        sa.Column("foto", sa.Integer(), nullable=False),
        sa.Column("placa", sa.String(length=7), nullable=False),
        sa.Column(
            "origem",
            sa.Enum(
                "conferencia",
                "rotulagem",
                name="origem_do_rotulo",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "situacao",
            sa.Enum(
                "a_revisar",
                "aceito",
                "corrigido",
                "descartado",
                name="situacao_do_rotulo",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "conjunto",
            sa.Enum(
                "treino",
                "regua",
                name="conjunto_do_rotulo",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("recorte", sa.String(length=200), nullable=True),
        sa.Column("resumo", sa.String(length=64), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revisado_por", sa.Integer(), nullable=True),
        sa.Column("revisado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "conjunto IN ('treino', 'regua')", name=op.f("ck_rotulo_conjunto_do_rotulo")
        ),
        sa.CheckConstraint(
            "origem IN ('conferencia', 'rotulagem')", name=op.f("ck_rotulo_origem_do_rotulo")
        ),
        sa.CheckConstraint(
            "situacao IN ('a_revisar', 'aceito', 'corrigido', 'descartado')",
            name=op.f("ck_rotulo_situacao_do_rotulo"),
        ),
        sa.CheckConstraint("foto >= 0", name=op.f("ck_rotulo_foto_positiva")),
        sa.ForeignKeyConstraint(
            ["passagem_id", "empresa_id"],
            ["passagem.id", "passagem.empresa_id"],
            name=op.f("fk_rotulo_passagem_id_passagem"),
        ),
        sa.ForeignKeyConstraint(
            ["revisado_por"],
            ["administrador.id"],
            name=op.f("fk_rotulo_revisado_por_administrador"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rotulo")),
        sa.UniqueConstraint("passagem_id", "foto", name=op.f("uq_rotulo_passagem_id_foto")),
    )
    op.create_index("ix_rotulo_situacao", "rotulo", ["situacao"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rotulo_situacao", table_name="rotulo")
    op.drop_table("rotulo")
    op.drop_index(
        "uq_autorizacao_de_treino_ativa",
        table_name="autorizacao_de_treino",
        postgresql_where=sa.text("revogada_em IS NULL"),
    )
    op.drop_table("autorizacao_de_treino")

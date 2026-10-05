"""portaria: conferência da placa pelo porteiro (D-42)

Revisão: 0011
Anterior: 0010
Criada em: 2026-10-05

A conferência aponta para a passagem e para quem conferiu pela dupla (pai, empresa). Ela só se
acrescenta: os gatilhos da função so_acrescenta (migração 0008) recusam UPDATE, DELETE e
TRUNCATE (SDD 5.5).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conferencia_placa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("passagem_id", sa.Uuid(), nullable=False),
        sa.Column("foto", sa.Integer(), nullable=False),
        sa.Column("placa_lida", sa.String(length=7), nullable=True),
        sa.Column("placa", sa.String(length=7), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("momento", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("foto >= 0", name=op.f("ck_conferencia_placa_foto_positiva")),
        sa.ForeignKeyConstraint(
            ["passagem_id", "empresa_id"],
            ["passagem.id", "passagem.empresa_id"],
            name=op.f("fk_conferencia_placa_passagem_id_passagem"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_conferencia_placa_usuario_id_usuario"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conferencia_placa")),
    )
    op.create_index(
        "ix_conferencia_placa_passagem_id", "conferencia_placa", ["passagem_id"], unique=False
    )
    op.execute(
        "CREATE TRIGGER conferencia_placa_so_acrescenta BEFORE UPDATE OR DELETE"
        " ON conferencia_placa FOR EACH ROW EXECUTE FUNCTION so_acrescenta()"
    )
    op.execute(
        "CREATE TRIGGER conferencia_placa_nao_esvazia BEFORE TRUNCATE"
        " ON conferencia_placa FOR EACH STATEMENT EXECUTE FUNCTION so_acrescenta()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER conferencia_placa_nao_esvazia ON conferencia_placa")
    op.execute("DROP TRIGGER conferencia_placa_so_acrescenta ON conferencia_placa")
    op.drop_index("ix_conferencia_placa_passagem_id", table_name="conferencia_placa")
    op.drop_table("conferencia_placa")

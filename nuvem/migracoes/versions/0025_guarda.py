"""guarda (D-70)

Revisão: 0025
Anterior: 0024
Criada em: 2026-10-06

A foto apagada pelo prazo de guarda e a marca de disputa, só de acréscimo (o gatilho
``so_acrescenta``). A cadeia da prova ganha os dois tipos novos de elo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELAS_DE_PROVA = ("foto_apagada", "marca_de_disputa")
TIPOS_ANTES = "'passagem', 'foto', 'evento', 'conferencia', 'mensagem'"
TIPOS_DEPOIS = TIPOS_ANTES + ", 'disputa', 'foto_apagada'"


def _trocar_os_tipos_do_elo(tipos: str, tamanho: int) -> None:
    op.drop_constraint(op.f("ck_elo_da_prova_tipo_de_elo"), "elo_da_prova", type_="check")
    op.alter_column("elo_da_prova", "tipo", type_=sa.String(tamanho), existing_nullable=False)
    op.create_check_constraint(
        op.f("ck_elo_da_prova_tipo_de_elo"), "elo_da_prova", f"tipo IN ({tipos})"
    )


def upgrade() -> None:
    op.create_table(
        "foto_apagada",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("passagem_id", sa.Uuid(), nullable=False),
        sa.Column("indice", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=200), nullable=False),
        sa.Column("existia", sa.Boolean(), nullable=False),
        sa.Column(
            "motivo",
            sa.Enum(
                "prazo_de_guarda",
                name="motivo_da_foto_apagada",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("apagada_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "motivo IN ('prazo_de_guarda')", name=op.f("ck_foto_apagada_motivo_da_foto_apagada")
        ),
        sa.CheckConstraint("indice >= 0", name=op.f("ck_foto_apagada_indice_positivo")),
        sa.ForeignKeyConstraint(
            ["passagem_id", "empresa_id"],
            ["passagem.id", "passagem.empresa_id"],
            name=op.f("fk_foto_apagada_passagem_id_passagem"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_foto_apagada")),
        sa.UniqueConstraint(
            "passagem_id", "indice", name=op.f("uq_foto_apagada_passagem_id_indice")
        ),
    )
    op.create_index("ix_foto_apagada_apagada_em", "foto_apagada", ["apagada_em"], unique=False)
    op.create_table(
        "marca_de_disputa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("visita_id", sa.Integer(), nullable=False),
        sa.Column(
            "acao",
            sa.Enum(
                "marcar",
                "desmarcar",
                name="acao_da_disputa",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("motivo", sa.String(length=300), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("momento", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "acao IN ('marcar', 'desmarcar')", name=op.f("ck_marca_de_disputa_acao_da_disputa")
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_marca_de_disputa_usuario_id_usuario"),
        ),
        sa.ForeignKeyConstraint(
            ["visita_id", "empresa_id"],
            ["visita.id", "visita.empresa_id"],
            name=op.f("fk_marca_de_disputa_visita_id_visita"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_marca_de_disputa")),
    )
    op.create_index("ix_marca_de_disputa_momento", "marca_de_disputa", ["momento"], unique=False)
    op.create_index(
        "ix_marca_de_disputa_visita_id", "marca_de_disputa", ["visita_id"], unique=False
    )
    for tabela in TABELAS_DE_PROVA:
        op.execute(
            f"CREATE TRIGGER {tabela}_so_acrescenta BEFORE UPDATE OR DELETE ON {tabela}"
            " FOR EACH ROW EXECUTE FUNCTION so_acrescenta()"
        )
        op.execute(
            f"CREATE TRIGGER {tabela}_nao_esvazia BEFORE TRUNCATE ON {tabela}"
            " FOR EACH STATEMENT EXECUTE FUNCTION so_acrescenta()"
        )
    _trocar_os_tipos_do_elo(TIPOS_DEPOIS, 12)


def downgrade() -> None:
    # Volta só sem elos dos tipos novos (o elo não se apaga).
    _trocar_os_tipos_do_elo(TIPOS_ANTES, 11)
    for tabela in TABELAS_DE_PROVA:
        op.execute(f"DROP TRIGGER {tabela}_nao_esvazia ON {tabela}")
        op.execute(f"DROP TRIGGER {tabela}_so_acrescenta ON {tabela}")
    op.drop_index("ix_marca_de_disputa_visita_id", table_name="marca_de_disputa")
    op.drop_index("ix_marca_de_disputa_momento", table_name="marca_de_disputa")
    op.drop_table("marca_de_disputa")
    op.drop_index("ix_foto_apagada_apagada_em", table_name="foto_apagada")
    op.drop_table("foto_apagada")

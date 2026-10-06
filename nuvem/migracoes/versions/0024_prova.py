"""prova (D-69)

Revisão: 0024
Anterior: 0023
Criada em: 2026-10-06

A cadeia de prova de cada visita, o resumo de cada foto e a âncora do dia. O elo e a foto
resumida só se acrescentam (o gatilho ``so_acrescenta``, como nos eventos). A fila de tarefas
ganha o "resumir as fotos".
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELAS_DE_PROVA = ("foto_recebida", "elo_da_prova")
TIPOS_ANTES = (
    "'casar_passagem', 'enviar_mensagem', 'aviso_do_whatsapp', 'aviso_do_sms', 'avisar_alerta'"
)
TIPOS_DEPOIS = TIPOS_ANTES + ", 'resumir_fotos'"


def _trocar_os_tipos(tipos: str) -> None:
    op.drop_constraint(op.f("ck_tarefa_de_fundo_tipo_de_tarefa"), "tarefa_de_fundo", type_="check")
    op.create_check_constraint(
        op.f("ck_tarefa_de_fundo_tipo_de_tarefa"), "tarefa_de_fundo", f"tipo IN ({tipos})"
    )


def upgrade() -> None:
    op.create_table(
        "ancora_do_dia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column("arquivo", sa.String(length=200), nullable=False),
        sa.Column("resumo", sa.String(length=64), nullable=False),
        sa.Column("visitas", sa.Integer(), nullable=False),
        sa.Column("travada", sa.Boolean(), nullable=False),
        sa.Column("gravada_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ancora_do_dia")),
        sa.UniqueConstraint("dia", name=op.f("uq_ancora_do_dia_dia")),
    )
    op.create_table(
        "foto_recebida",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("passagem_id", sa.Uuid(), nullable=False),
        sa.Column("indice", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=200), nullable=False),
        sa.Column("resumo", sa.String(length=64), nullable=False),
        sa.Column("tamanho", sa.Integer(), nullable=False),
        sa.Column("resumida_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("indice >= 0", name=op.f("ck_foto_recebida_indice_positivo")),
        sa.ForeignKeyConstraint(
            ["passagem_id", "empresa_id"],
            ["passagem.id", "passagem.empresa_id"],
            name=op.f("fk_foto_recebida_passagem_id_passagem"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_foto_recebida")),
        sa.UniqueConstraint(
            "passagem_id", "indice", name=op.f("uq_foto_recebida_passagem_id_indice")
        ),
    )
    op.create_index("ix_foto_recebida_resumida_em", "foto_recebida", ["resumida_em"], unique=False)
    op.create_table(
        "elo_da_prova",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("visita_id", sa.Integer(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "passagem",
                "foto",
                "evento",
                "conferencia",
                "mensagem",
                name="tipo_de_elo",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("referencia", sa.String(length=100), nullable=False),
        sa.Column("conteudo", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("anterior", sa.String(length=64), nullable=False),
        sa.Column("resumo", sa.String(length=64), nullable=False),
        sa.Column("selado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('passagem', 'foto', 'evento', 'conferencia', 'mensagem')",
            name=op.f("ck_elo_da_prova_tipo_de_elo"),
        ),
        sa.CheckConstraint("ordem >= 1", name=op.f("ck_elo_da_prova_ordem_positiva")),
        sa.ForeignKeyConstraint(
            ["visita_id", "empresa_id"],
            ["visita.id", "visita.empresa_id"],
            name=op.f("fk_elo_da_prova_visita_id_visita"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_elo_da_prova")),
        sa.UniqueConstraint("visita_id", "ordem", name=op.f("uq_elo_da_prova_visita_id_ordem")),
        sa.UniqueConstraint(
            "visita_id",
            "tipo",
            "referencia",
            name=op.f("uq_elo_da_prova_visita_id_tipo_referencia"),
        ),
    )
    op.create_index("ix_elo_da_prova_selado_em", "elo_da_prova", ["selado_em"], unique=False)
    for tabela in TABELAS_DE_PROVA:
        op.execute(
            f"CREATE TRIGGER {tabela}_so_acrescenta BEFORE UPDATE OR DELETE ON {tabela}"
            " FOR EACH ROW EXECUTE FUNCTION so_acrescenta()"
        )
        op.execute(
            f"CREATE TRIGGER {tabela}_nao_esvazia BEFORE TRUNCATE ON {tabela}"
            " FOR EACH STATEMENT EXECUTE FUNCTION so_acrescenta()"
        )
    _trocar_os_tipos(TIPOS_DEPOIS)


def downgrade() -> None:
    op.execute("DELETE FROM tarefa_de_fundo WHERE tipo = 'resumir_fotos'")
    _trocar_os_tipos(TIPOS_ANTES)
    for tabela in TABELAS_DE_PROVA:
        op.execute(f"DROP TRIGGER {tabela}_nao_esvazia ON {tabela}")
        op.execute(f"DROP TRIGGER {tabela}_so_acrescenta ON {tabela}")
    op.drop_index("ix_elo_da_prova_selado_em", table_name="elo_da_prova")
    op.drop_table("elo_da_prova")
    op.drop_index("ix_foto_recebida_resumida_em", table_name="foto_recebida")
    op.drop_table("foto_recebida")
    op.drop_table("ancora_do_dia")

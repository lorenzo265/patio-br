"""mensagens: as mensagens ao motorista (D-47)

Revisão: 0014
Anterior: 0013
Criada em: 2026-10-05

A mensagem aponta para o site, para o agendamento e para o evento que a gerou pela dupla (pai,
empresa); o evento ganha a dupla (id, empresa) única para isso. Cada evento avisa uma vez só, e
cada celular de um agendamento é confirmado uma vez só (índice único parcial). Os índices novos
no evento e no agendamento servem ao worker, que procura o que mudou há pouco.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(op.f("uq_evento_id_empresa_id"), "evento", ["id", "empresa_id"])
    op.create_table(
        "mensagem",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("agendamento_id", sa.Integer(), nullable=False),
        sa.Column("evento_id", sa.Integer(), nullable=True),
        sa.Column(
            "modelo",
            sa.Enum(
                "confirmacao",
                "na_fila",
                "chamada",
                "pode_sair",
                name="modelo_de_mensagem",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "canal",
            sa.Enum("demonstracao", name="canal", native_enum=False, create_constraint=False),
            nullable=False,
        ),
        sa.Column("para", sa.String(length=14), nullable=False),
        sa.Column("texto", sa.String(length=500), nullable=False),
        sa.Column(
            "situacao",
            sa.Enum(
                "guardada", name="situacao_da_mensagem", native_enum=False, create_constraint=False
            ),
            nullable=False,
        ),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(modelo = 'confirmacao') = (evento_id IS NULL)",
            name=op.f("ck_mensagem_aviso_tem_evento"),
        ),
        sa.CheckConstraint("canal IN ('demonstracao')", name=op.f("ck_mensagem_canal")),
        sa.CheckConstraint(
            "modelo IN ('confirmacao', 'na_fila', 'chamada', 'pode_sair')",
            name=op.f("ck_mensagem_modelo_de_mensagem"),
        ),
        sa.CheckConstraint(
            "para ~ '^\\+55[1-9]{2}9[0-9]{8}$'", name=op.f("ck_mensagem_para_formato")
        ),
        sa.CheckConstraint(
            "situacao IN ('guardada')", name=op.f("ck_mensagem_situacao_da_mensagem")
        ),
        sa.ForeignKeyConstraint(
            ["agendamento_id", "empresa_id"],
            ["agendamento.id", "agendamento.empresa_id"],
            name=op.f("fk_mensagem_agendamento_id_agendamento"),
        ),
        sa.ForeignKeyConstraint(
            ["evento_id", "empresa_id"],
            ["evento.id", "evento.empresa_id"],
            name=op.f("fk_mensagem_evento_id_evento"),
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_mensagem_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mensagem")),
        sa.UniqueConstraint("evento_id", name=op.f("uq_mensagem_evento_id")),
    )
    op.create_index("ix_mensagem_agendamento_id", "mensagem", ["agendamento_id"], unique=False)
    op.create_index(
        "ix_mensagem_site_id_criada_em", "mensagem", ["site_id", "criada_em"], unique=False
    )
    op.create_index(
        "uq_mensagem_confirmacao",
        "mensagem",
        ["agendamento_id", "para"],
        unique=True,
        postgresql_where=sa.text("modelo = 'confirmacao'"),
    )
    op.create_index("ix_agendamento_atualizado_em", "agendamento", ["atualizado_em"], unique=False)
    op.create_index("ix_evento_registrado_em", "evento", ["registrado_em"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evento_registrado_em", table_name="evento")
    op.drop_index("ix_agendamento_atualizado_em", table_name="agendamento")
    op.drop_index(
        "uq_mensagem_confirmacao",
        table_name="mensagem",
        postgresql_where=sa.text("modelo = 'confirmacao'"),
    )
    op.drop_index("ix_mensagem_site_id_criada_em", table_name="mensagem")
    op.drop_index("ix_mensagem_agendamento_id", table_name="mensagem")
    op.drop_table("mensagem")
    op.drop_constraint(op.f("uq_evento_id_empresa_id"), "evento", type_="unique")

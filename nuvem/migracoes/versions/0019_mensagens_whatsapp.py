"""mensagens: o WhatsApp de verdade (D-58 e D-63)

Revisão: 0019
Anterior: 0018
Criada em: 2026-10-06

A mensagem ganha os canais WhatsApp e SMS, as situações do envio, as variáveis do modelo, o id no
canal, os horários, o erro e a cobrança. A autorização do WhatsApp passa a ser do celular numa
empresa (``autorizacao_whatsapp``), e sai a coluna do agendamento, que nunca foi usada. As
mensagens que chegam ao número do produto ficam em ``mensagem_recebida``. A fila de tarefas ganha
"enviar mensagem" e "aviso do WhatsApp".
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPOS_ANTES = "'casar_passagem'"
TIPOS_DEPOIS = "'casar_passagem', 'enviar_mensagem', 'aviso_do_whatsapp'"
CANAIS_ANTES = "'demonstracao'"
CANAIS_DEPOIS = "'demonstracao', 'whatsapp', 'sms'"
SITUACOES_ANTES = "'guardada'"
SITUACOES_DEPOIS = "'guardada', 'enviada', 'entregue', 'lida', 'falhou'"


def _trocar_a_lista(tabela: str, restricao: str, coluna: str, valores: str) -> None:
    op.drop_constraint(op.f(restricao), tabela, type_="check")
    op.create_check_constraint(op.f(restricao), tabela, f"{coluna} IN ({valores})")


def upgrade() -> None:
    op.create_table(
        "autorizacao_whatsapp",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("celular", sa.String(length=14), nullable=False),
        sa.Column("autorizada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("texto", sa.String(length=1000), nullable=False),
        sa.Column("id_no_whatsapp", sa.String(length=100), nullable=False),
        sa.Column("revogada_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "celular ~ '^\\+55[1-9]{2}9[0-9]{8}$'",
            name=op.f("ck_autorizacao_whatsapp_celular_formato"),
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_autorizacao_whatsapp_empresa_id_empresa")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_autorizacao_whatsapp")),
    )
    op.create_index(
        "uq_autorizacao_whatsapp_ativa",
        "autorizacao_whatsapp",
        ["empresa_id", "celular"],
        unique=True,
        postgresql_where=sa.text("revogada_em IS NULL"),
    )
    op.create_table(
        "mensagem_recebida",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_no_whatsapp", sa.String(length=100), nullable=False),
        sa.Column("de", sa.String(length=20), nullable=False),
        sa.Column("texto", sa.String(length=1000), nullable=False),
        sa.Column("recebida_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=True),
        sa.Column(
            "resultado",
            sa.Enum(
                "autorizou",
                "saiu",
                "ignorada",
                name="resultado_da_recebida",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("tratada_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "resultado IN ('autorizou', 'saiu', 'ignorada')",
            name=op.f("ck_mensagem_recebida_resultado_da_recebida"),
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_mensagem_recebida_empresa_id_empresa")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mensagem_recebida")),
        sa.UniqueConstraint("id_no_whatsapp", name=op.f("uq_mensagem_recebida_id_no_whatsapp")),
    )
    op.drop_column("agendamento", "whatsapp_autorizado_em")
    op.add_column(
        "mensagem", sa.Column("variaveis", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column("mensagem", sa.Column("id_no_canal", sa.String(length=100), nullable=True))
    op.add_column("mensagem", sa.Column("enviada_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mensagem", sa.Column("entregue_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mensagem", sa.Column("lida_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mensagem", sa.Column("falhou_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mensagem", sa.Column("erro", sa.String(length=300), nullable=True))
    op.add_column("mensagem", sa.Column("cobranca", sa.String(length=30), nullable=True))
    op.create_unique_constraint(
        op.f("uq_mensagem_canal_id_no_canal"), "mensagem", ["canal", "id_no_canal"]
    )
    _trocar_a_lista("mensagem", "ck_mensagem_canal", "canal", CANAIS_DEPOIS)
    _trocar_a_lista("mensagem", "ck_mensagem_situacao_da_mensagem", "situacao", SITUACOES_DEPOIS)
    op.alter_column(
        "tarefa_de_fundo",
        "tipo",
        existing_type=sa.String(length=14),
        type_=sa.String(length=17),
        existing_nullable=False,
    )
    _trocar_a_lista("tarefa_de_fundo", "ck_tarefa_de_fundo_tipo_de_tarefa", "tipo", TIPOS_DEPOIS)


def downgrade() -> None:
    _trocar_a_lista("tarefa_de_fundo", "ck_tarefa_de_fundo_tipo_de_tarefa", "tipo", TIPOS_ANTES)
    op.alter_column(
        "tarefa_de_fundo",
        "tipo",
        existing_type=sa.String(length=17),
        type_=sa.String(length=14),
        existing_nullable=False,
    )
    _trocar_a_lista("mensagem", "ck_mensagem_situacao_da_mensagem", "situacao", SITUACOES_ANTES)
    _trocar_a_lista("mensagem", "ck_mensagem_canal", "canal", CANAIS_ANTES)
    op.drop_constraint(op.f("uq_mensagem_canal_id_no_canal"), "mensagem", type_="unique")
    op.drop_column("mensagem", "cobranca")
    op.drop_column("mensagem", "erro")
    op.drop_column("mensagem", "falhou_em")
    op.drop_column("mensagem", "lida_em")
    op.drop_column("mensagem", "entregue_em")
    op.drop_column("mensagem", "enviada_em")
    op.drop_column("mensagem", "id_no_canal")
    op.drop_column("mensagem", "variaveis")
    op.add_column(
        "agendamento",
        sa.Column("whatsapp_autorizado_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_table("mensagem_recebida")
    op.drop_index(
        "uq_autorizacao_whatsapp_ativa",
        table_name="autorizacao_whatsapp",
        postgresql_where=sa.text("revogada_em IS NULL"),
    )
    op.drop_table("autorizacao_whatsapp")

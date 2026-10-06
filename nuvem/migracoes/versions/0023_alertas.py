"""alertas (D-68)

Revisão: 0023
Anterior: 0022
Criada em: 2026-10-06

Os alertas (um aberto por tipo e chave), os avisos pelo WhatsApp e as autorizações de quem quer
recebê-los, pelo código de uso único. A fila de tarefas ganha o "avisar alerta".
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TIPOS_ANTES = "'casar_passagem', 'enviar_mensagem', 'aviso_do_whatsapp', 'aviso_do_sms'"
TIPOS_DEPOIS = TIPOS_ANTES + ", 'avisar_alerta'"


def _trocar_os_tipos(tipos: str) -> None:
    op.drop_constraint(op.f("ck_tarefa_de_fundo_tipo_de_tarefa"), "tarefa_de_fundo", type_="check")
    op.create_check_constraint(
        op.f("ck_tarefa_de_fundo_tipo_de_tarefa"), "tarefa_de_fundo", f"tipo IN ({tipos})"
    )


def upgrade() -> None:
    op.create_table(
        "alerta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=True),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column(
            "tipo",
            sa.Enum(
                "estadia_perto",
                "estadia_passou",
                "sem_agendamento",
                "caixa_sem_contato",
                "camera_parada",
                "relogio_errado",
                "motorista_nao_avisado",
                "tarefa_falhou",
                name="tipo_de_alerta",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("chave", sa.String(length=100), nullable=False),
        sa.Column("texto", sa.String(length=300), nullable=False),
        sa.Column("aberto_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fechado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('estadia_perto', 'estadia_passou', 'sem_agendamento', 'caixa_sem_contato',"
            " 'camera_parada', 'relogio_errado', 'motorista_nao_avisado', 'tarefa_falhou')",
            name=op.f("ck_alerta_tipo_de_alerta"),
        ),
        sa.CheckConstraint(
            "(empresa_id IS NULL) = (site_id IS NULL)", name=op.f("ck_alerta_da_plataforma")
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_alerta_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerta")),
    )
    op.create_index("ix_alerta_site_id_aberto_em", "alerta", ["site_id", "aberto_em"], unique=False)
    op.create_index(
        "uq_alerta_aberto",
        "alerta",
        ["tipo", "chave"],
        unique=True,
        postgresql_where=sa.text("fechado_em IS NULL"),
    )
    op.create_table(
        "alertas_no_whatsapp",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("administrador_id", sa.Integer(), nullable=True),
        sa.Column("codigo_resumo", sa.String(length=64), nullable=False),
        sa.Column("pedido_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vence_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("celular", sa.String(length=14), nullable=True),
        sa.Column("autorizada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("texto", sa.String(length=1000), nullable=True),
        sa.Column("id_no_whatsapp", sa.String(length=100), nullable=True),
        sa.Column("revogada_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(celular IS NULL) = (autorizada_em IS NULL)",
            name=op.f("ck_alertas_no_whatsapp_celular_na_autorizacao"),
        ),
        sa.CheckConstraint(
            "(usuario_id IS NULL) <> (administrador_id IS NULL)",
            name=op.f("ck_alertas_no_whatsapp_uma_pessoa"),
        ),
        sa.CheckConstraint(
            "(usuario_id IS NULL) = (empresa_id IS NULL)",
            name=op.f("ck_alertas_no_whatsapp_empresa_do_usuario"),
        ),
        sa.ForeignKeyConstraint(
            ["administrador_id"],
            ["administrador.id"],
            name=op.f("fk_alertas_no_whatsapp_administrador_id_administrador"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_alertas_no_whatsapp_usuario_id_usuario"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alertas_no_whatsapp")),
        sa.UniqueConstraint("codigo_resumo", name=op.f("uq_alertas_no_whatsapp_codigo_resumo")),
    )
    op.create_table(
        "aviso_de_alerta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=True),
        sa.Column("alerta_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("administrador_id", sa.Integer(), nullable=True),
        sa.Column("celular", sa.String(length=14), nullable=False),
        sa.Column(
            "situacao",
            sa.Enum(
                "guardado",
                "enviado",
                "falhou",
                name="situacao_do_aviso",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("id_no_canal", sa.String(length=100), nullable=True),
        sa.Column("erro", sa.String(length=300), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enviado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "situacao IN ('guardado', 'enviado', 'falhou')",
            name=op.f("ck_aviso_de_alerta_situacao_do_aviso"),
        ),
        sa.CheckConstraint(
            "(usuario_id IS NULL) <> (administrador_id IS NULL)",
            name=op.f("ck_aviso_de_alerta_uma_pessoa"),
        ),
        sa.ForeignKeyConstraint(
            ["administrador_id"],
            ["administrador.id"],
            name=op.f("fk_aviso_de_alerta_administrador_id_administrador"),
        ),
        sa.ForeignKeyConstraint(
            ["alerta_id"], ["alerta.id"], name=op.f("fk_aviso_de_alerta_alerta_id_alerta")
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"], name=op.f("fk_aviso_de_alerta_usuario_id_usuario")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aviso_de_alerta")),
    )
    _trocar_os_tipos(TIPOS_DEPOIS)


def downgrade() -> None:
    _trocar_os_tipos(TIPOS_ANTES)
    op.drop_table("aviso_de_alerta")
    op.drop_table("alertas_no_whatsapp")
    op.drop_index(
        "uq_alerta_aberto", table_name="alerta", postgresql_where=sa.text("fechado_em IS NULL")
    )
    op.drop_index("ix_alerta_site_id_aberto_em", table_name="alerta")
    op.drop_table("alerta")

"""agendamento: agendamentos e as mudanças de cada um

Revisão: 0006
Anterior: 0005
Criada em: 2026-10-04

O agendamento aponta para o site pela dupla (site, empresa), e a mudança aponta para o
agendamento e para o usuário do mesmo jeito. O mesmo código externo, pela mesma origem, no mesmo
site, é um agendamento só (D-33). O autogenerate repetia o CHECK de cada lista; ficou um, com o
nome do padrão.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agendamento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("janela_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("janela_fim", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum("carga", "descarga", name="tipo", native_enum=False, create_constraint=False),
            nullable=False,
        ),
        sa.Column("placa_cavalo", sa.String(length=7), nullable=False),
        sa.Column("placas_reboques", postgresql.ARRAY(sa.String(length=7)), nullable=False),
        sa.Column("motorista_nome", sa.String(length=120), nullable=True),
        sa.Column("motorista_celular", sa.String(length=14), nullable=True),
        sa.Column("whatsapp_autorizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("toneladas", sa.Numeric(precision=9, scale=3), nullable=True),
        sa.Column("chave_nfe", sa.String(length=44), nullable=True),
        sa.Column(
            "origem",
            sa.Enum(
                "link",
                "planilha",
                "api_generica",
                name="origem",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("codigo_externo", sa.String(length=100), nullable=False),
        sa.Column(
            "situacao",
            sa.Enum(
                "ativo", "cancelado", name="situacao", native_enum=False, create_constraint=False
            ),
            nullable=False,
        ),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "chave_nfe ~ '^[0-9]{6}[A-Z0-9]{12}[0-9]{26}$'",
            name=op.f("ck_agendamento_chave_nfe_formato"),
        ),
        sa.CheckConstraint(
            "motorista_celular ~ '^\\+55[1-9]{2}9[0-9]{8}$'",
            name=op.f("ck_agendamento_celular_formato"),
        ),
        sa.CheckConstraint(
            "origem IN ('link', 'planilha', 'api_generica')", name=op.f("ck_agendamento_origem")
        ),
        sa.CheckConstraint(
            "placa_cavalo ~ '^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$'",
            name=op.f("ck_agendamento_placa_cavalo_formato"),
        ),
        sa.CheckConstraint(
            "situacao IN ('ativo', 'cancelado')", name=op.f("ck_agendamento_situacao")
        ),
        sa.CheckConstraint("tipo IN ('carga', 'descarga')", name=op.f("ck_agendamento_tipo")),
        sa.CheckConstraint(
            "cardinality(placas_reboques) <= 3", name=op.f("ck_agendamento_reboques_no_maximo")
        ),
        sa.CheckConstraint(
            "char_length(codigo_externo) > 0", name=op.f("ck_agendamento_codigo_externo_preenchido")
        ),
        sa.CheckConstraint(
            "janela_fim > janela_inicio", name=op.f("ck_agendamento_janela_em_ordem")
        ),
        sa.CheckConstraint("toneladas > 0", name=op.f("ck_agendamento_toneladas_positivas")),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_agendamento_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agendamento")),
        sa.UniqueConstraint("id", "empresa_id", name=op.f("uq_agendamento_id_empresa_id")),
        sa.UniqueConstraint(
            "site_id",
            "origem",
            "codigo_externo",
            name=op.f("uq_agendamento_site_id_origem_codigo_externo"),
        ),
    )
    op.create_index(
        "ix_agendamento_site_id_janela_inicio",
        "agendamento",
        ["site_id", "janela_inicio"],
        unique=False,
    )
    op.create_table(
        "agendamento_mudanca",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("agendamento_id", sa.Integer(), nullable=False),
        sa.Column("momento", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "criado",
                "alterado",
                "cancelado",
                name="tipo_de_mudanca",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "via",
            sa.Enum(
                "link",
                "planilha",
                "api_generica",
                "painel",
                name="via",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("antes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("depois", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('criado', 'alterado', 'cancelado')",
            name=op.f("ck_agendamento_mudanca_tipo_de_mudanca"),
        ),
        sa.CheckConstraint(
            "via IN ('link', 'planilha', 'api_generica', 'painel')",
            name=op.f("ck_agendamento_mudanca_via"),
        ),
        sa.ForeignKeyConstraint(
            ["agendamento_id", "empresa_id"],
            ["agendamento.id", "agendamento.empresa_id"],
            name=op.f("fk_agendamento_mudanca_agendamento_id_agendamento"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_agendamento_mudanca_usuario_id_usuario"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agendamento_mudanca")),
    )
    op.create_index(
        "ix_agendamento_mudanca_agendamento_id",
        "agendamento_mudanca",
        ["agendamento_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agendamento_mudanca_agendamento_id", table_name="agendamento_mudanca")
    op.drop_table("agendamento_mudanca")
    op.drop_index("ix_agendamento_site_id_janela_inicio", table_name="agendamento")
    op.drop_table("agendamento")

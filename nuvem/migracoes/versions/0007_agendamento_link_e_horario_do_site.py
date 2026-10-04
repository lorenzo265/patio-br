"""agendamento: link da transportadora e horário de operação do site

Revisão: 0007
Anterior: 0006
Criada em: 2026-10-04

O link aponta para o site e para o gestor que o gerou pela dupla (pai, empresa), e o agendamento
aponta para o link do mesmo jeito. O autogenerate não vê CHECK novo em tabela que já existe: o
do horário do site e o do link só na origem link entram à mão.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "link_transportadora",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("codigo_resumo", sa.String(length=64), nullable=False),
        sa.Column("criado_por", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vence_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("limite_de_envios", sa.Integer(), nullable=False),
        sa.Column("envios", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "envios >= 0 AND envios <= limite_de_envios",
            name=op.f("ck_link_transportadora_envios_no_limite"),
        ),
        sa.CheckConstraint(
            "limite_de_envios > 0", name=op.f("ck_link_transportadora_limite_positivo")
        ),
        sa.CheckConstraint(
            "vence_em > criado_em", name=op.f("ck_link_transportadora_vence_depois_de_criado")
        ),
        sa.ForeignKeyConstraint(
            ["criado_por", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_link_transportadora_criado_por_usuario"),
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_link_transportadora_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_link_transportadora")),
        sa.UniqueConstraint("codigo_resumo", name=op.f("uq_link_transportadora_codigo_resumo")),
        sa.UniqueConstraint("id", "empresa_id", name=op.f("uq_link_transportadora_id_empresa_id")),
    )
    op.add_column("agendamento", sa.Column("link_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_agendamento_link_id_link_transportadora"),
        "agendamento",
        "link_transportadora",
        ["link_id", "empresa_id"],
        ["id", "empresa_id"],
    )
    op.create_check_constraint(
        op.f("ck_agendamento_link_so_na_origem_link"),
        "agendamento",
        "link_id IS NULL OR origem = 'link'",
    )
    op.add_column("site", sa.Column("abre", sa.Time(), nullable=True))
    op.add_column("site", sa.Column("fecha", sa.Time(), nullable=True))
    op.create_check_constraint(
        op.f("ck_site_horario_em_ordem"),
        "site",
        "(abre IS NULL AND fecha IS NULL)"
        " OR (abre IS NOT NULL AND fecha IS NOT NULL AND abre < fecha)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_site_horario_em_ordem"), "site", type_="check")
    op.drop_column("site", "fecha")
    op.drop_column("site", "abre")
    op.drop_constraint(op.f("ck_agendamento_link_so_na_origem_link"), "agendamento", type_="check")
    op.drop_constraint(
        op.f("fk_agendamento_link_id_link_transportadora"), "agendamento", type_="foreignkey"
    )
    op.drop_column("agendamento", "link_id")
    op.drop_table("link_transportadora")

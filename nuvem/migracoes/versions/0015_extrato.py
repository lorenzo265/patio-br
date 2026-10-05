"""extrato: parâmetros do site, linha de base e o extrato guardado (D-48)

Revisão: 0015
Anterior: 0014
Criada em: 2026-10-05

As três tabelas apontam para o site pela dupla (site, empresa). O extrato guardado só se
acrescenta: os gatilhos da função so_acrescenta (migração 0008) recusam UPDATE, DELETE e
TRUNCATE (SDD 5.5).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extrato",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("mes", sa.Date(), nullable=False),
        sa.Column("versao_da_regra", sa.Integer(), nullable=False),
        sa.Column("numeros", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("guardado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("extract(day from mes) = 1", name=op.f("ck_extrato_mes_no_dia_1")),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_extrato_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extrato")),
        sa.UniqueConstraint(
            "site_id", "mes", "versao_da_regra", name=op.f("uq_extrato_site_id_mes_versao_da_regra")
        ),
    )
    op.create_table(
        "linha_de_base",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column(
            "origem",
            sa.Enum(
                "exemplo",
                "modo_sombra",
                name="origem_da_linha_de_base",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("de", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ate", sa.DateTime(timezone=True), nullable=False),
        sa.Column("medidas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("gravada_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "origem IN ('exemplo', 'modo_sombra')",
            name=op.f("ck_linha_de_base_origem_da_linha_de_base"),
        ),
        sa.CheckConstraint("ate > de", name=op.f("ck_linha_de_base_periodo_em_ordem")),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_linha_de_base_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_linha_de_base")),
        sa.UniqueConstraint("site_id", name=op.f("uq_linha_de_base_site_id")),
    )
    op.create_table(
        "parametros_site",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("valor_da_estadia", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("franquia_minutos", sa.Integer(), nullable=False),
        sa.Column("postos_antes", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("postos_depois", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("custo_mensal_do_posto", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("custo_hora_doca", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "custo_hora_doca > 0", name=op.f("ck_parametros_site_custo_hora_doca_positivo")
        ),
        sa.CheckConstraint(
            "custo_mensal_do_posto > 0", name=op.f("ck_parametros_site_custo_do_posto_positivo")
        ),
        sa.CheckConstraint(
            "franquia_minutos > 0", name=op.f("ck_parametros_site_franquia_positiva")
        ),
        sa.CheckConstraint(
            "postos_antes >= 0 AND postos_depois >= 0",
            name=op.f("ck_parametros_site_postos_positivos"),
        ),
        sa.CheckConstraint("valor_da_estadia > 0", name=op.f("ck_parametros_site_valor_positivo")),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_parametros_site_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parametros_site")),
        sa.UniqueConstraint("site_id", name=op.f("uq_parametros_site_site_id")),
    )

    op.execute(
        "CREATE TRIGGER extrato_so_acrescenta BEFORE UPDATE OR DELETE"
        " ON extrato FOR EACH ROW EXECUTE FUNCTION so_acrescenta()"
    )
    op.execute(
        "CREATE TRIGGER extrato_nao_esvazia BEFORE TRUNCATE"
        " ON extrato FOR EACH STATEMENT EXECUTE FUNCTION so_acrescenta()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER extrato_nao_esvazia ON extrato")
    op.execute("DROP TRIGGER extrato_so_acrescenta ON extrato")
    op.drop_table("parametros_site")
    op.drop_table("linha_de_base")
    op.drop_table("extrato")

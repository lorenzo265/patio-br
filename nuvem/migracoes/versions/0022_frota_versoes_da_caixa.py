"""frota: as versões da caixa (D-67)

Revisão: 0022
Anterior: 0021
Criada em: 2026-10-06

As versões do agente (pelo resumo da imagem), as escolhas por alcance (todas as caixas, um site
ou uma caixa) e as atualizações contadas pela caixa. As escolhas e as atualizações só se
acrescentam: os gatilhos da função so_acrescenta (migração 0008) recusam mudar ou apagar.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SO_ACRESCENTAM = ("escolha_de_versao", "atualizacao_caixa")


def upgrade() -> None:
    op.create_table(
        "versao_caixa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=50), nullable=False),
        sa.Column("imagem", sa.String(length=200), nullable=False),
        sa.Column("resumo", sa.String(length=71), nullable=False),
        sa.Column("cadastrada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cadastrada_por", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cadastrada_por"],
            ["administrador.id"],
            name=op.f("fk_versao_caixa_cadastrada_por_administrador"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_versao_caixa")),
        sa.UniqueConstraint("nome", name=op.f("uq_versao_caixa_nome")),
        sa.UniqueConstraint("resumo", name=op.f("uq_versao_caixa_resumo")),
    )
    op.create_table(
        "atualizacao_caixa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("caixa_id", sa.Integer(), nullable=False),
        sa.Column("de", sa.String(length=300), nullable=False),
        sa.Column("versao_id", sa.Integer(), nullable=False),
        sa.Column("comecou_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminou_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "resultado",
            sa.Enum(
                "ok",
                "voltou",
                "falhou",
                name="resultado_da_atualizacao",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("motivo", sa.String(length=500), nullable=False),
        sa.Column("recebida_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "resultado IN ('ok', 'voltou', 'falhou')",
            name=op.f("ck_atualizacao_caixa_resultado_da_atualizacao"),
        ),
        sa.CheckConstraint(
            "terminou_em >= comecou_em", name=op.f("ck_atualizacao_caixa_termina_depois")
        ),
        sa.ForeignKeyConstraint(
            ["caixa_id", "empresa_id"],
            ["caixa_borda.id", "caixa_borda.empresa_id"],
            name=op.f("fk_atualizacao_caixa_caixa_id_caixa_borda"),
        ),
        sa.ForeignKeyConstraint(
            ["versao_id"],
            ["versao_caixa.id"],
            name=op.f("fk_atualizacao_caixa_versao_id_versao_caixa"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_atualizacao_caixa")),
    )
    op.create_index(
        "ix_atualizacao_caixa_caixa_id_recebida_em",
        "atualizacao_caixa",
        ["caixa_id", "recebida_em"],
        unique=False,
    )
    op.create_table(
        "escolha_de_versao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("versao_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=True),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("caixa_id", sa.Integer(), nullable=True),
        sa.Column("escolhida_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("escolhida_por", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(site_id IS NULL OR caixa_id IS NULL)"
            " AND ((site_id IS NULL AND caixa_id IS NULL) = (empresa_id IS NULL))",
            name=op.f("ck_escolha_de_versao_um_alcance"),
        ),
        sa.ForeignKeyConstraint(
            ["caixa_id", "empresa_id"],
            ["caixa_borda.id", "caixa_borda.empresa_id"],
            name=op.f("fk_escolha_de_versao_caixa_id_caixa_borda"),
        ),
        sa.ForeignKeyConstraint(
            ["escolhida_por"],
            ["administrador.id"],
            name=op.f("fk_escolha_de_versao_escolhida_por_administrador"),
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_escolha_de_versao_site_id_site"),
        ),
        sa.ForeignKeyConstraint(
            ["versao_id"],
            ["versao_caixa.id"],
            name=op.f("fk_escolha_de_versao_versao_id_versao_caixa"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_escolha_de_versao")),
    )
    op.create_index(
        "ix_escolha_de_versao_alcance",
        "escolha_de_versao",
        ["caixa_id", "site_id", "escolhida_em"],
        unique=False,
    )
    for tabela in SO_ACRESCENTAM:
        op.execute(
            f"CREATE TRIGGER {tabela}_so_acrescenta BEFORE UPDATE OR DELETE"
            f" ON {tabela} FOR EACH ROW EXECUTE FUNCTION so_acrescenta()"
        )
        op.execute(
            f"CREATE TRIGGER {tabela}_nao_esvazia BEFORE TRUNCATE"
            f" ON {tabela} FOR EACH STATEMENT EXECUTE FUNCTION so_acrescenta()"
        )


def downgrade() -> None:
    for tabela in SO_ACRESCENTAM:
        op.execute(f"DROP TRIGGER {tabela}_nao_esvazia ON {tabela}")
        op.execute(f"DROP TRIGGER {tabela}_so_acrescenta ON {tabela}")
    op.drop_index("ix_escolha_de_versao_alcance", table_name="escolha_de_versao")
    op.drop_table("escolha_de_versao")
    op.drop_index("ix_atualizacao_caixa_caixa_id_recebida_em", table_name="atualizacao_caixa")
    op.drop_table("atualizacao_caixa")
    op.drop_table("versao_caixa")

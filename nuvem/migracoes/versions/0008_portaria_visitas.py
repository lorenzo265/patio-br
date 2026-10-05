"""portaria: visitas, eventos e exceções

Revisão: 0008
Anterior: 0007
Criada em: 2026-10-04

A visita, o evento e a exceção apontam para os pais pela dupla (pai, empresa); a passagem ganha a
dupla (id, empresa) única para isso. O evento e a mudança de agendamento só se acrescentam: o
gatilho so_acrescenta recusa UPDATE, DELETE e TRUNCATE (SDD 5.5), com o código 23001. O
autogenerate repetia o CHECK de cada lista; ficou um, com o nome do padrão.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SO_ACRESCENTA = """
CREATE FUNCTION so_acrescenta() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'a tabela % só aceita acréscimos (SDD 5.5)', TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END
$$
"""

TABELAS_DE_PROVA = ("evento", "agendamento_mudanca")


def upgrade() -> None:
    # Antes das tabelas novas: as chaves estrangeiras compostas apontam para (id, empresa).
    op.create_unique_constraint(op.f("uq_passagem_id_empresa_id"), "passagem", ["id", "empresa_id"])
    op.create_table(
        "visita",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("agendamento_id", sa.Integer(), nullable=True),
        sa.Column(
            "estado",
            sa.Enum(
                "NA_FILA",
                "EXCECAO",
                "NAO_VEIO",
                "SAIU",
                name="estado",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("composicao", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("chegou_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("saiu_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("passagem_entrada_id", sa.Uuid(), nullable=True),
        sa.Column("passagem_saida_id", sa.Uuid(), nullable=True),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(estado = 'NAO_VEIO') = (chegou_em IS NULL)", name=op.f("ck_visita_chegada")
        ),
        sa.CheckConstraint(
            "(estado = 'SAIU') = (saiu_em IS NOT NULL)", name=op.f("ck_visita_saida")
        ),
        sa.CheckConstraint(
            "estado <> 'NAO_VEIO' OR agendamento_id IS NOT NULL",
            name=op.f("ck_visita_nao_veio_tem_agendamento"),
        ),
        sa.CheckConstraint(
            "estado IN ('NA_FILA', 'EXCECAO', 'NAO_VEIO', 'SAIU')", name=op.f("ck_visita_estado")
        ),
        sa.ForeignKeyConstraint(
            ["agendamento_id", "empresa_id"],
            ["agendamento.id", "agendamento.empresa_id"],
            name=op.f("fk_visita_agendamento_id_agendamento"),
        ),
        sa.ForeignKeyConstraint(
            ["passagem_entrada_id", "empresa_id"],
            ["passagem.id", "passagem.empresa_id"],
            name=op.f("fk_visita_passagem_entrada_id_passagem"),
        ),
        sa.ForeignKeyConstraint(
            ["passagem_saida_id", "empresa_id"],
            ["passagem.id", "passagem.empresa_id"],
            name=op.f("fk_visita_passagem_saida_id_passagem"),
        ),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_visita_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visita")),
        sa.UniqueConstraint("agendamento_id", name=op.f("uq_visita_agendamento_id")),
        sa.UniqueConstraint("id", "empresa_id", name=op.f("uq_visita_id_empresa_id")),
    )
    op.create_index("ix_visita_site_id_estado", "visita", ["site_id", "estado"], unique=False)
    op.create_table(
        "evento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("visita_id", sa.Integer(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "check_in",
                "excecao",
                "nao_veio",
                "saiu_sem_atendimento",
                name="tipo_de_evento",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "estado",
            sa.Enum(
                "NA_FILA",
                "EXCECAO",
                "NAO_VEIO",
                "SAIU",
                name="estado",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("momento", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registrado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("passagem_id", sa.Uuid(), nullable=True),
        sa.Column("dados", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "estado IN ('NA_FILA', 'EXCECAO', 'NAO_VEIO', 'SAIU')", name=op.f("ck_evento_estado")
        ),
        sa.CheckConstraint(
            "tipo IN ('check_in', 'excecao', 'nao_veio', 'saiu_sem_atendimento')",
            name=op.f("ck_evento_tipo_de_evento"),
        ),
        sa.ForeignKeyConstraint(
            ["passagem_id", "empresa_id"],
            ["passagem.id", "passagem.empresa_id"],
            name=op.f("fk_evento_passagem_id_passagem"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_evento_usuario_id_usuario"),
        ),
        sa.ForeignKeyConstraint(
            ["visita_id", "empresa_id"],
            ["visita.id", "visita.empresa_id"],
            name=op.f("fk_evento_visita_id_visita"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evento")),
    )
    op.create_index("ix_evento_visita_id", "evento", ["visita_id"], unique=False)
    op.create_table(
        "excecao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("visita_id", sa.Integer(), nullable=False),
        sa.Column("passagem_id", sa.Uuid(), nullable=False),
        sa.Column(
            "motivo",
            sa.Enum(
                "sem_candidato",
                "candidatos_proximos",
                "sem_placa",
                name="motivo",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("candidatos", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "situacao",
            sa.Enum(
                "aberta",
                "resolvida",
                name="situacao_da_excecao",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolvida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolvida_por", sa.Integer(), nullable=True),
        sa.Column("resolucao", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "(situacao = 'aberta') = (resolvida_em IS NULL)",
            name=op.f("ck_excecao_resolvida_tem_hora"),
        ),
        sa.CheckConstraint(
            "motivo IN ('sem_candidato', 'candidatos_proximos', 'sem_placa')",
            name=op.f("ck_excecao_motivo"),
        ),
        sa.CheckConstraint(
            "situacao IN ('aberta', 'resolvida')", name=op.f("ck_excecao_situacao_da_excecao")
        ),
        sa.ForeignKeyConstraint(
            ["passagem_id", "empresa_id"],
            ["passagem.id", "passagem.empresa_id"],
            name=op.f("fk_excecao_passagem_id_passagem"),
        ),
        sa.ForeignKeyConstraint(
            ["resolvida_por", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_excecao_resolvida_por_usuario"),
        ),
        sa.ForeignKeyConstraint(
            ["visita_id", "empresa_id"],
            ["visita.id", "visita.empresa_id"],
            name=op.f("fk_excecao_visita_id_visita"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_excecao")),
        sa.UniqueConstraint("visita_id", name=op.f("uq_excecao_visita_id")),
    )
    op.execute(SO_ACRESCENTA)
    for tabela in TABELAS_DE_PROVA:
        op.execute(
            f"CREATE TRIGGER {tabela}_so_acrescenta BEFORE UPDATE OR DELETE ON {tabela}"
            " FOR EACH ROW EXECUTE FUNCTION so_acrescenta()"
        )
        op.execute(
            f"CREATE TRIGGER {tabela}_nao_esvazia BEFORE TRUNCATE ON {tabela}"
            " FOR EACH STATEMENT EXECUTE FUNCTION so_acrescenta()"
        )


def downgrade() -> None:
    for tabela in TABELAS_DE_PROVA:
        op.execute(f"DROP TRIGGER {tabela}_nao_esvazia ON {tabela}")
        op.execute(f"DROP TRIGGER {tabela}_so_acrescenta ON {tabela}")
    op.execute("DROP FUNCTION so_acrescenta()")
    op.drop_table("excecao")
    op.drop_index("ix_evento_visita_id", table_name="evento")
    op.drop_table("evento")
    op.drop_index("ix_visita_site_id_estado", table_name="visita")
    op.drop_table("visita")
    op.drop_constraint(op.f("uq_passagem_id_empresa_id"), "passagem", type_="unique")

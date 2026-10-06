"""demonstração: o link de demonstração por empresa (D-52 e D-54)

Revisão: 0017
Anterior: 0016
Criada em: 2026-10-05

O link é da plataforma, como a administração que o gera: fica fora das empresas e aponta para a
empresa de demonstração (vazia antes da primeira entrada e depois de apagada).

A função ``so_acrescenta`` passa a deixar apagar uma linha de prova num caso só (D-54): a linha é
de uma empresa que nasceu de um link de demonstração, e a própria transação avisou que está
apagando aquela empresa (``set_config('patio.apagar_empresa', <id>, true)``). Alterar continua
recusado, e o TRUNCATE também.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SO_ACRESCENTA_COM_A_DEMONSTRACAO = """
CREATE OR REPLACE FUNCTION so_acrescenta() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND TG_LEVEL = 'ROW' THEN
        IF OLD.empresa_id::text = current_setting('patio.apagar_empresa', true)
           AND EXISTS (SELECT 1 FROM link_demonstracao WHERE empresa_id = OLD.empresa_id) THEN
            RETURN OLD;
        END IF;
    END IF;
    RAISE EXCEPTION 'a tabela % só aceita acréscimos (SDD 5.5)', TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END
$$
"""

SO_ACRESCENTA_ORIGINAL = """
CREATE OR REPLACE FUNCTION so_acrescenta() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'a tabela % só aceita acréscimos (SDD 5.5)', TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END
$$
"""


def upgrade() -> None:
    op.create_table(
        "link_demonstracao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("codigo_resumo", sa.String(length=64), nullable=False),
        sa.Column("criado_por", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("vence_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("empresa_id", sa.Integer(), nullable=True),
        sa.Column("ultima_entrada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("apagada_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("vence_em > criado_em", name=op.f("ck_link_demonstracao_vence_depois")),
        sa.ForeignKeyConstraint(
            ["criado_por"],
            ["administrador.id"],
            name=op.f("fk_link_demonstracao_criado_por_administrador"),
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_link_demonstracao_empresa_id_empresa")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_link_demonstracao")),
        sa.UniqueConstraint("codigo_resumo", name=op.f("uq_link_demonstracao_codigo_resumo")),
        sa.UniqueConstraint("empresa_id", name=op.f("uq_link_demonstracao_empresa_id")),
    )
    op.execute(SO_ACRESCENTA_COM_A_DEMONSTRACAO)


def downgrade() -> None:
    op.execute(SO_ACRESCENTA_ORIGINAL)
    op.drop_table("link_demonstracao")

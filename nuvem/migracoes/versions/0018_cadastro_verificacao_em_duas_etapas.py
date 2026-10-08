"""cadastro: a verificação em duas etapas (D-60)

Revisão: 0018
Anterior: 0017
Criada em: 2026-10-06

O segredo do app (cifrado), quando a verificação foi ligada e o último código aceito, no usuário
e na administração; quem zerou a do usuário; o que falta à sessão pela metade; e os códigos de
recuperação (só o resumo), de um usuário ou de alguém da administração.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "codigo_recuperacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("empresa_id", sa.Integer(), nullable=True),
        sa.Column("administrador_id", sa.Integer(), nullable=True),
        sa.Column("resumo", sa.String(), nullable=False),
        sa.Column("usado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(usuario_id IS NOT NULL AND empresa_id IS NOT NULL AND administrador_id IS NULL)"
            " OR (usuario_id IS NULL AND empresa_id IS NULL AND administrador_id IS NOT NULL)",
            name=op.f("ck_codigo_recuperacao_de_uma_pessoa_so"),
        ),
        sa.ForeignKeyConstraint(
            ["administrador_id"],
            ["administrador.id"],
            name=op.f("fk_codigo_recuperacao_administrador_id_administrador"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_codigo_recuperacao_usuario_id_usuario"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_codigo_recuperacao")),
    )
    op.create_index(
        op.f("ix_codigo_recuperacao_administrador_id"),
        "codigo_recuperacao",
        ["administrador_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_codigo_recuperacao_usuario_id"), "codigo_recuperacao", ["usuario_id"], unique=False
    )
    op.add_column("administrador", sa.Column("duas_etapas_cifrado", sa.String(), nullable=True))
    op.add_column(
        "administrador", sa.Column("duas_etapas_desde", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("administrador", sa.Column("duas_etapas_passo", sa.BigInteger(), nullable=True))
    op.add_column(
        "sessao_login",
        sa.Column(
            "falta",
            sa.Enum("codigo", "ligar", name="falta", native_enum=False, create_constraint=True),
            nullable=True,
        ),
    )
    op.add_column(
        "usuario", sa.Column("duas_etapas_zerada_em", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("usuario", sa.Column("duas_etapas_zerada_por", sa.Integer(), nullable=True))
    op.add_column("usuario", sa.Column("duas_etapas_cifrado", sa.String(), nullable=True))
    op.add_column(
        "usuario", sa.Column("duas_etapas_desde", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("usuario", sa.Column("duas_etapas_passo", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_usuario_duas_etapas_zerada_por_administrador"),
        "usuario",
        "administrador",
        ["duas_etapas_zerada_por"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_usuario_duas_etapas_zerada_por_administrador"), "usuario", type_="foreignkey"
    )
    op.drop_column("usuario", "duas_etapas_passo")
    op.drop_column("usuario", "duas_etapas_desde")
    op.drop_column("usuario", "duas_etapas_cifrado")
    op.drop_column("usuario", "duas_etapas_zerada_por")
    op.drop_column("usuario", "duas_etapas_zerada_em")
    op.drop_column("sessao_login", "falta")
    op.drop_column("administrador", "duas_etapas_passo")
    op.drop_column("administrador", "duas_etapas_desde")
    op.drop_column("administrador", "duas_etapas_cifrado")
    op.drop_index(op.f("ix_codigo_recuperacao_usuario_id"), table_name="codigo_recuperacao")
    op.drop_index(op.f("ix_codigo_recuperacao_administrador_id"), table_name="codigo_recuperacao")
    op.drop_table("codigo_recuperacao")

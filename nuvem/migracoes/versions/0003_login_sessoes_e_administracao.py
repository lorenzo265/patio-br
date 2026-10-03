"""login: senha e PIN dos usuários, administração, sessões e tentativas

Revisão: 0003
Anterior: 0002
Criada em: 2026-10-03

A administração (nós) fica numa tabela própria, fora das empresas (SDD D-19). A sessão de login
fica no banco, só com o resumo do código do cookie (D-20); a de um usuário aponta para ele pela
dupla (usuário, empresa). Usuários que já existiam ficam sem senha (não entram até ganhar uma).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "administrador",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("senha_resumo", sa.String(), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_administrador")),
        sa.UniqueConstraint("email", name=op.f("uq_administrador_email")),
    )
    op.create_table(
        "tentativa_login",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alvo_resumo", sa.String(length=64), nullable=False),
        sa.Column("momento", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tentativa_login")),
    )
    op.create_index(
        op.f("ix_tentativa_login_alvo_resumo"), "tentativa_login", ["alvo_resumo"], unique=False
    )
    op.create_table(
        "sessao_login",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo_resumo", sa.String(length=64), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("empresa_id", sa.Integer(), nullable=True),
        sa.Column("administrador_id", sa.Integer(), nullable=True),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(usuario_id IS NOT NULL AND empresa_id IS NOT NULL AND administrador_id IS NULL)"
            " OR (usuario_id IS NULL AND empresa_id IS NULL AND administrador_id IS NOT NULL)",
            name=op.f("ck_sessao_login_de_uma_pessoa_so"),
        ),
        sa.ForeignKeyConstraint(
            ["administrador_id"],
            ["administrador.id"],
            name=op.f("fk_sessao_login_administrador_id_administrador"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_sessao_login_usuario_id_usuario"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessao_login")),
        sa.UniqueConstraint("codigo_resumo", name=op.f("uq_sessao_login_codigo_resumo")),
    )
    op.add_column("usuario", sa.Column("senha_resumo", sa.String(), nullable=True))
    op.add_column("usuario", sa.Column("pin_resumo", sa.String(), nullable=True))
    op.add_column(
        "usuario", sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), nullable=False)
    )


def downgrade() -> None:
    op.drop_column("usuario", "ativo")
    op.drop_column("usuario", "pin_resumo")
    op.drop_column("usuario", "senha_resumo")
    op.drop_table("sessao_login")
    op.drop_index(op.f("ix_tentativa_login_alvo_resumo"), table_name="tentativa_login")
    op.drop_table("tentativa_login")
    op.drop_table("administrador")

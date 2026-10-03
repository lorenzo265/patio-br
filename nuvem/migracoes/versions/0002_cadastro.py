"""cadastro: estrutura física, usuários e separação por empresa

Revisão: 0002
Anterior: 0001
Criada em: 2026-10-03

Cada tabela de dados do cliente leva empresa_id, e cada filha aponta para o pai por (pai,
empresa): o banco recusa misturar empresas. As colunas de lista (papel, sentido, posição) são
texto com um CHECK (o autogenerate repetia o CHECK; ficou um por coluna, com o nome do padrão).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "empresa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.CheckConstraint("cnpj ~ '^[0-9A-Z]{12}[0-9]{2}$'", name=op.f("ck_empresa_cnpj_formato")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_empresa")),
        sa.UniqueConstraint("cnpj", name=op.f("uq_empresa_cnpj")),
    )
    op.create_table(
        "site",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("fuso", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_site_empresa_id_empresa")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site")),
        sa.UniqueConstraint("id", "empresa_id", name=op.f("uq_site_id_empresa_id")),
    )
    op.create_index(op.f("ix_site_empresa_id"), "site", ["empresa_id"], unique=False)
    op.create_table(
        "usuario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column(
            "papel",
            sa.Enum(
                "porteiro",
                "patio",
                "gestor",
                name="papel",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "papel IN ('porteiro', 'patio', 'gestor')", name=op.f("ck_usuario_papel")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresa.id"], name=op.f("fk_usuario_empresa_id_empresa")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuario")),
        sa.UniqueConstraint("email", name=op.f("uq_usuario_email")),
        sa.UniqueConstraint("id", "empresa_id", name=op.f("uq_usuario_id_empresa_id")),
    )
    op.create_index(op.f("ix_usuario_empresa_id"), "usuario", ["empresa_id"], unique=False)
    op.create_table(
        "doca",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_doca_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_doca")),
    )
    op.create_table(
        "portaria",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_portaria_site_id_site"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portaria")),
        sa.UniqueConstraint("id", "empresa_id", name=op.f("uq_portaria_id_empresa_id")),
    )
    op.create_table(
        "usuario_site",
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id", "empresa_id"],
            ["site.id", "site.empresa_id"],
            name=op.f("fk_usuario_site_site_id_site"),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["usuario.id", "usuario.empresa_id"],
            name=op.f("fk_usuario_site_usuario_id_usuario"),
        ),
        sa.PrimaryKeyConstraint("usuario_id", "site_id", name=op.f("pk_usuario_site")),
    )
    op.create_table(
        "faixa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("portaria_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column(
            "sentido",
            sa.Enum("entrada", "saida", name="sentido", native_enum=False, create_constraint=False),
            nullable=False,
        ),
        sa.CheckConstraint("sentido IN ('entrada', 'saida')", name=op.f("ck_faixa_sentido")),
        sa.ForeignKeyConstraint(
            ["portaria_id", "empresa_id"],
            ["portaria.id", "portaria.empresa_id"],
            name=op.f("fk_faixa_portaria_id_portaria"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_faixa")),
        sa.UniqueConstraint("id", "empresa_id", name=op.f("uq_faixa_id_empresa_id")),
    )
    op.create_table(
        "camera",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("faixa_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column(
            "posicao",
            sa.Enum(
                "frente",
                "tras",
                "contexto",
                name="posicao",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("endereco", sa.String(), nullable=False),
        sa.Column("login", sa.String(), nullable=False),
        sa.Column("senha_cifrada", sa.String(), nullable=False),
        sa.CheckConstraint(
            "posicao IN ('frente', 'tras', 'contexto')", name=op.f("ck_camera_posicao")
        ),
        sa.ForeignKeyConstraint(
            ["faixa_id", "empresa_id"],
            ["faixa.id", "faixa.empresa_id"],
            name=op.f("fk_camera_faixa_id_faixa"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_camera")),
    )


def downgrade() -> None:
    op.drop_table("camera")
    op.drop_table("faixa")
    op.drop_table("usuario_site")
    op.drop_table("portaria")
    op.drop_table("doca")
    op.drop_index(op.f("ix_usuario_empresa_id"), table_name="usuario")
    op.drop_table("usuario")
    op.drop_index(op.f("ix_site_empresa_id"), table_name="site")
    op.drop_table("site")
    op.drop_table("empresa")

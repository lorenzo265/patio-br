"""pátio: a doca na visita, os estados e os eventos do pátio

Revisão: 0013
Anterior: 0012
Criada em: 2026-10-05

A visita ganha a doca (pela dupla doca, empresa) e as horas da chamada, do início e do fim; os
estados CHAMADA, NA_DOCA e LIBERADA; e os eventos chamada, chamada_cancelada, inicio_na_doca,
fim_na_doca e saiu (SDD 5.2). Uma doca tem no máximo um caminhão chamado ou carregando (índice
único parcial), e a visita chamada ou na doca tem doca (CHECK). O autogenerate não vê CHECK novo
nem mudado numa tabela que já existe; eles entram à mão.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTADOS = "('NA_FILA', 'EXCECAO', 'NAO_VEIO', 'CHAMADA', 'NA_DOCA', 'LIBERADA', 'SAIU', 'RECUSADA')"
ESTADOS_ANTES = "('NA_FILA', 'EXCECAO', 'NAO_VEIO', 'SAIU', 'RECUSADA')"
TIPOS = (
    "('check_in', 'excecao', 'nao_veio', 'saiu_sem_atendimento', 'aceita_sem_agendamento',"
    " 'recusada', 'placa_corrigida', 'chamada', 'chamada_cancelada', 'inicio_na_doca',"
    " 'fim_na_doca', 'saiu')"
)
TIPOS_ANTES = (
    "('check_in', 'excecao', 'nao_veio', 'saiu_sem_atendimento', 'aceita_sem_agendamento',"
    " 'recusada', 'placa_corrigida')"
)
OCUPADA = "estado IN ('CHAMADA', 'NA_DOCA')"


def _trocar(tabela: str, nome: str, coluna: str, valores: str) -> None:
    op.drop_constraint(op.f(nome), tabela, type_="check")
    op.create_check_constraint(op.f(nome), tabela, f"{coluna} IN {valores}")


def upgrade() -> None:
    op.create_unique_constraint(op.f("uq_doca_id_empresa_id"), "doca", ["id", "empresa_id"])
    op.add_column("visita", sa.Column("doca_id", sa.Integer(), nullable=True))
    op.add_column("visita", sa.Column("chamada_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("visita", sa.Column("na_doca_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("visita", sa.Column("liberada_em", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_visita_doca_id_doca"),
        "visita",
        "doca",
        ["doca_id", "empresa_id"],
        ["id", "empresa_id"],
    )
    op.create_index(
        "uq_visita_doca_ocupada",
        "visita",
        ["doca_id"],
        unique=True,
        postgresql_where=sa.text(OCUPADA),
    )
    _trocar("visita", "ck_visita_estado", "estado", ESTADOS)
    _trocar("evento", "ck_evento_estado", "estado", ESTADOS)
    _trocar("evento", "ck_evento_tipo_de_evento", "tipo", TIPOS)
    op.create_check_constraint(
        op.f("ck_visita_doca_na_chamada"),
        "visita",
        "estado NOT IN ('CHAMADA', 'NA_DOCA') OR doca_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_visita_doca_na_chamada"), "visita", type_="check")
    _trocar("evento", "ck_evento_tipo_de_evento", "tipo", TIPOS_ANTES)
    _trocar("evento", "ck_evento_estado", "estado", ESTADOS_ANTES)
    _trocar("visita", "ck_visita_estado", "estado", ESTADOS_ANTES)
    op.drop_index("uq_visita_doca_ocupada", table_name="visita", postgresql_where=sa.text(OCUPADA))
    op.drop_constraint(op.f("fk_visita_doca_id_doca"), "visita", type_="foreignkey")
    op.drop_column("visita", "liberada_em")
    op.drop_column("visita", "na_doca_em")
    op.drop_column("visita", "chamada_em")
    op.drop_column("visita", "doca_id")
    op.drop_constraint(op.f("uq_doca_id_empresa_id"), "doca", type_="unique")

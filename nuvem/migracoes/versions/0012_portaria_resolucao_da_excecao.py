"""portaria: a exceção resolvida pelo porteiro (RECUSADA e os eventos novos)

Revisão: 0012
Anterior: 0011
Criada em: 2026-10-05

A visita ganha o estado RECUSADA, e o evento, os tipos aceita_sem_agendamento, recusada e
placa_corrigida (SDD 5.2 e D-46); o tipo do evento cresce para caber "aceita_sem_agendamento". O
autogenerate não vê CHECK mudado; eles entram à mão.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTADOS = "('NA_FILA', 'EXCECAO', 'NAO_VEIO', 'SAIU', 'RECUSADA')"
ESTADOS_ANTES = "('NA_FILA', 'EXCECAO', 'NAO_VEIO', 'SAIU')"
TIPOS = (
    "('check_in', 'excecao', 'nao_veio', 'saiu_sem_atendimento', 'aceita_sem_agendamento',"
    " 'recusada', 'placa_corrigida')"
)
TIPOS_ANTES = "('check_in', 'excecao', 'nao_veio', 'saiu_sem_atendimento')"


def _trocar(tabela: str, nome: str, coluna: str, valores: str) -> None:
    op.drop_constraint(op.f(nome), tabela, type_="check")
    op.create_check_constraint(op.f(nome), tabela, f"{coluna} IN {valores}")


def upgrade() -> None:
    op.alter_column("evento", "tipo", type_=sa.String(22), existing_type=sa.String(20))
    _trocar("visita", "ck_visita_estado", "estado", ESTADOS)
    _trocar("evento", "ck_evento_estado", "estado", ESTADOS)
    _trocar("evento", "ck_evento_tipo_de_evento", "tipo", TIPOS)


def downgrade() -> None:
    _trocar("evento", "ck_evento_tipo_de_evento", "tipo", TIPOS_ANTES)
    _trocar("evento", "ck_evento_estado", "estado", ESTADOS_ANTES)
    _trocar("visita", "ck_visita_estado", "estado", ESTADOS_ANTES)
    op.alter_column("evento", "tipo", type_=sa.String(20), existing_type=sa.String(22))

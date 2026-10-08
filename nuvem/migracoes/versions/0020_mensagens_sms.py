"""mensagens: o SMS de reserva (D-64)

Revisão: 0020
Anterior: 0019
Criada em: 2026-10-06

A mensagem passa a ser única por aviso e canal: o WhatsApp que falha ganha a cópia pelo SMS, no
mesmo evento (e a confirmação, no mesmo celular). A fila de tarefas ganha o "aviso do SMS".
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPOS_ANTES = "'casar_passagem', 'enviar_mensagem', 'aviso_do_whatsapp'"
TIPOS_DEPOIS = "'casar_passagem', 'enviar_mensagem', 'aviso_do_whatsapp', 'aviso_do_sms'"
SO_A_CONFIRMACAO = "modelo = 'confirmacao'"


def _trocar_os_tipos(tipos: str) -> None:
    op.drop_constraint(op.f("ck_tarefa_de_fundo_tipo_de_tarefa"), "tarefa_de_fundo", type_="check")
    op.create_check_constraint(
        op.f("ck_tarefa_de_fundo_tipo_de_tarefa"), "tarefa_de_fundo", f"tipo IN ({tipos})"
    )


def upgrade() -> None:
    op.drop_constraint(op.f("uq_mensagem_evento_id"), "mensagem", type_="unique")
    op.create_unique_constraint(
        op.f("uq_mensagem_evento_id_canal"), "mensagem", ["evento_id", "canal"]
    )
    op.drop_index("uq_mensagem_confirmacao", table_name="mensagem")
    op.create_index(
        "uq_mensagem_confirmacao",
        "mensagem",
        ["agendamento_id", "para", "canal"],
        unique=True,
        postgresql_where=sa.text(SO_A_CONFIRMACAO),
    )
    _trocar_os_tipos(TIPOS_DEPOIS)


def downgrade() -> None:
    _trocar_os_tipos(TIPOS_ANTES)
    op.drop_index("uq_mensagem_confirmacao", table_name="mensagem")
    op.create_index(
        "uq_mensagem_confirmacao",
        "mensagem",
        ["agendamento_id", "para"],
        unique=True,
        postgresql_where=sa.text(SO_A_CONFIRMACAO),
    )
    op.drop_constraint(op.f("uq_mensagem_evento_id_canal"), "mensagem", type_="unique")
    op.create_unique_constraint(op.f("uq_mensagem_evento_id"), "mensagem", ["evento_id"])

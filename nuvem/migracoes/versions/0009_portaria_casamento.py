"""portaria: o casamento (a passagem única por visita e o motivo pontos_baixos)

Revisão: 0009
Anterior: 0008
Criada em: 2026-10-04

A passagem de entrada e a de saída são únicas entre as visitas: a mesma passagem processada de
novo não cria outra visita nem fecha outra (SDD 5.3). A exceção ganha o motivo pontos_baixos; o
autogenerate não vê CHECK mudado, e ele entra à mão.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_visita_passagem_entrada_id"), "visita", ["passagem_entrada_id"]
    )
    op.create_unique_constraint(
        op.f("uq_visita_passagem_saida_id"), "visita", ["passagem_saida_id"]
    )
    op.drop_constraint(op.f("ck_excecao_motivo"), "excecao", type_="check")
    op.create_check_constraint(
        op.f("ck_excecao_motivo"),
        "excecao",
        "motivo IN ('sem_placa', 'sem_candidato', 'pontos_baixos', 'candidatos_proximos')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_excecao_motivo"), "excecao", type_="check")
    op.create_check_constraint(
        op.f("ck_excecao_motivo"),
        "excecao",
        "motivo IN ('sem_candidato', 'candidatos_proximos', 'sem_placa')",
    )
    op.drop_constraint(op.f("uq_visita_passagem_saida_id"), "visita", type_="unique")
    op.drop_constraint(op.f("uq_visita_passagem_entrada_id"), "visita", type_="unique")

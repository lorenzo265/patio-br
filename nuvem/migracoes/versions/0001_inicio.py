"""Início: o banco passa a ser controlado pelas migrações; ainda sem tabelas.

Revisão: 0001
Anterior:
Criada em: 2026-10-02
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

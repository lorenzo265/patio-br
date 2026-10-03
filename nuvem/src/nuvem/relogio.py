"""A hora de agora, num lugar só: as regras recebem a hora, e os testes escolhem qual é."""

from datetime import UTC, datetime


def agora() -> datetime:
    """Dependência do FastAPI: a hora atual, com fuso (UTC)."""
    return datetime.now(UTC)

"""A batida do worker (D-74): a cada volta, ele marca a hora; o ``/saude`` confere a marca.

Se a marca passa de 2 minutos, o worker parou ou travou: na homologação e na produção, o
``/saude`` responde 503, e a verificação de fora (o Route 53) toca o alarme.
"""

from datetime import datetime, timedelta

from sqlalchemy import DateTime, String, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from nuvem.banco import Base

WORKER = "worker"
INTERVALO = timedelta(seconds=30)
"""De quanto em quanto tempo o worker marca a hora."""
LIMITE = timedelta(minutes=2)
"""A marca mais velha que ainda conta como viva."""


class Batida(Base):
    """A última hora marcada por um processo que roda sempre (hoje, só o worker)."""

    __tablename__ = "batida"

    processo: Mapped[str] = mapped_column(String(30), primary_key=True)
    em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def marcar(sessao: Session, *, agora: datetime, processo: str = WORKER) -> None:
    """Marca a hora do processo (troca a marca anterior)."""
    sessao.execute(
        insert(Batida)
        .values(processo=processo, em=agora)
        .on_conflict_do_update(index_elements=[Batida.processo], set_={"em": agora})
    )


def viva(sessao: Session, *, agora: datetime, processo: str = WORKER) -> bool:
    """Se o processo marcou a hora nos últimos 2 minutos."""
    em = sessao.scalar(select(Batida.em).where(Batida.processo == processo))
    return em is not None and agora - em <= LIMITE

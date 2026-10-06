"""A batida do worker e o ``/saude`` (D-74): o worker marca a hora; parado, o ``/saude`` falha
na homologação e na produção."""

import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, select
from sqlalchemy.orm import Session

from nuvem import batida, relogio
from nuvem import tarefas_de_fundo as fila
from nuvem.banco import obter_sessao
from nuvem.batida import Batida
from nuvem.config import Ambiente, Configuracao
from nuvem.principal import criar_app

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
CHAVE = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="

PedirSaude = Callable[[Ambiente, datetime], tuple[int, object]]


def test_marcar_troca_a_marca_anterior(sessao: Session) -> None:
    batida.marcar(sessao, agora=AGORA)
    batida.marcar(sessao, agora=AGORA + timedelta(seconds=30))

    assert sessao.scalars(select(Batida.em)).all() == [AGORA + timedelta(seconds=30)]


def test_viva_ate_2_minutos_depois_da_marca(sessao: Session) -> None:
    batida.marcar(sessao, agora=AGORA)

    assert batida.viva(sessao, agora=AGORA + timedelta(minutes=2))
    assert not batida.viva(sessao, agora=AGORA + timedelta(minutes=2, seconds=1))


def test_sem_marca_nenhuma_nao_esta_viva(sessao: Session) -> None:
    assert not batida.viva(sessao, agora=AGORA)


def test_a_marca_de_outro_processo_nao_conta(sessao: Session) -> None:
    batida.marcar(sessao, agora=AGORA, processo="outro")

    assert not batida.viva(sessao, agora=AGORA)


# --- O /saude -------------------------------------------------------------------------------


@pytest.fixture
def saude(url_banco_teste: str, conexao: Connection) -> PedirSaude:
    """Pede o ``/saude`` num ambiente, numa hora, dentro da transação do teste."""

    def _pedir(ambiente: Ambiente, agora: datetime) -> tuple[int, object]:
        configuracao = Configuracao(
            url_banco=url_banco_teste, chave_cifra=CHAVE, ambiente=ambiente, _env_file=None
        )
        app = criar_app(configuracao)

        def sessao_do_teste() -> Iterator[Session]:
            with Session(bind=conexao, join_transaction_mode="create_savepoint") as sessao:
                yield sessao

        app.dependency_overrides[obter_sessao] = sessao_do_teste
        app.dependency_overrides[relogio.agora] = lambda: agora
        with TestClient(app) as cliente:
            resposta = cliente.get("/saude")
        return resposta.status_code, resposta.json()

    return _pedir


@pytest.mark.parametrize("ambiente", ["homologacao", "producao"])
def test_o_saude_falha_quando_o_worker_parou(
    saude: PedirSaude, sessao: Session, ambiente: Ambiente
) -> None:
    batida.marcar(sessao, agora=AGORA)
    sessao.commit()

    assert saude(ambiente, AGORA + timedelta(minutes=1)) == (200, {"ok": True})
    assert saude(ambiente, AGORA + timedelta(minutes=3)) == (503, {"ok": False})


@pytest.mark.parametrize("ambiente", ["homologacao", "producao"])
def test_o_saude_falha_quando_o_worker_nunca_bateu(saude: PedirSaude, ambiente: Ambiente) -> None:
    assert saude(ambiente, AGORA) == (503, {"ok": False})


@pytest.mark.parametrize("ambiente", ["local", "demonstracao"])
def test_sem_worker_de_sempre_o_saude_nao_confere_a_batida(
    saude: PedirSaude, ambiente: Ambiente
) -> None:
    assert saude(ambiente, AGORA) == (200, {"ok": True})


# --- O worker -------------------------------------------------------------------------------


def _rodar(sessao: Session, horas: list[datetime]) -> None:
    parar = threading.Event()
    relogio_do_teste = iter(horas)

    def proxima() -> datetime:
        hora = next(relogio_do_teste)
        if hora == horas[-1]:
            parar.set()
        return hora

    fila.rodar(lambda: sessao, parar, relogio=proxima, dormir=lambda _s: None)


def test_o_worker_marca_a_batida_a_cada_30_segundos(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    marcas: list[datetime] = []
    original = batida.marcar

    def anotar(sessao: Session, *, agora: datetime, processo: str = batida.WORKER) -> None:
        marcas.append(agora)
        original(sessao, agora=agora, processo=processo)

    monkeypatch.setattr(batida, "marcar", anotar)
    _rodar(sessao, [AGORA + timedelta(seconds=s) for s in (0, 10, 29, 30, 45, 61)])

    assert marcas == [AGORA + timedelta(seconds=s) for s in (0, 30, 61)]
    assert sessao.scalar(select(func.max(Batida.em))) == AGORA + timedelta(seconds=61)

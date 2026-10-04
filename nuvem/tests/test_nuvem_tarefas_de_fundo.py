"""Fila de tarefas e worker (SDD 6.1 e D-38): o casamento e o "não veio" fora do pedido da caixa."""

import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem import tarefas_de_fundo as fila
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.cadastro.acesso import Acesso
from nuvem.portaria.modelos import Visita
from nuvem.semente import Demonstracao
from nuvem.tarefas_de_fundo import TarefaDeFundo

pytestmark = pytest.mark.integracao

Registrar = Callable[..., Passagem]

AGORA = datetime(2026, 10, 5, 17, 3, tzinfo=UTC)


def _tarefas(sessao: Session) -> list[TarefaDeFundo]:
    return list(sessao.scalars(select(TarefaDeFundo).order_by(TarefaDeFundo.id)))


@pytest.fixture
def agendamento(sessao: Session, cenario: Demonstracao) -> Agendamento:
    """Um agendamento do site_a, das 13h às 15h em São Paulo, para o cavalo ABC1D23."""
    destino = SiteDoAgendamento(
        empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id, usuario_id=None
    )
    dados = DadosDoAgendamento(
        codigo_externo="AG-1",
        janela_inicio=datetime(2026, 10, 5, 16, tzinfo=UTC),
        janela_fim=datetime(2026, 10, 5, 18, tzinfo=UTC),
        tipo="descarga",
        placa_cavalo="ABC1D23",
    )
    return agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento


# --- Enfileirar -------------------------------------------------------------------------------


def test_passagem_recebida_vira_uma_tarefa_casar(
    sessao: Session, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    [tarefa] = _tarefas(sessao)

    assert (tarefa.tipo, tarefa.chave, tarefa.dados, tarefa.situacao, tarefa.tentativas) == (
        "casar_passagem",
        str(passagem.id),
        {"passagem_id": str(passagem.id)},
        "pendente",
        0,
    )


def test_a_mesma_chave_nao_enfileira_de_novo(sessao: Session) -> None:
    for _ in range(2):
        fila.enfileirar(sessao, "casar_passagem", {"passagem_id": "x"}, chave="x", agora=AGORA)

    assert len(_tarefas(sessao)) == 1


# --- Executar ---------------------------------------------------------------------------------


def test_o_worker_casa_a_passagem(
    sessao: Session, agendamento: Agendamento, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    executadas = fila.executar_pendentes(sessao, agora=AGORA)

    assert executadas == 1
    visita = sessao.scalars(select(Visita).where(Visita.passagem_entrada_id == passagem.id)).one()
    assert (visita.estado, visita.agendamento_id) == ("NA_FILA", agendamento.id)
    [tarefa] = _tarefas(sessao)
    assert (tarefa.situacao, tarefa.terminada_em) == ("feita", AGORA)


def test_tarefa_feita_nao_roda_de_novo(sessao: Session, registrar_passagem: Registrar) -> None:
    registrar_passagem()
    fila.executar_pendentes(sessao, agora=AGORA)

    assert fila.executar_pendentes(sessao, agora=AGORA + timedelta(hours=1)) == 0


def test_tarefa_para_depois_espera_a_hora(sessao: Session) -> None:
    fila.enfileirar(
        sessao, "casar_passagem", {"passagem_id": str(uuid4())}, chave="depois",
        agora=AGORA + timedelta(minutes=1),
    )  # fmt: skip

    assert fila.pegar_proxima(sessao, agora=AGORA) is None
    assert fila.pegar_proxima(sessao, agora=AGORA + timedelta(minutes=1)) is not None


def test_a_mais_antiga_sai_primeiro(sessao: Session) -> None:
    for minutos, chave in ((2, "nova"), (0, "velha"), (1, "meio")):
        fila.enfileirar(
            sessao, "casar_passagem", {}, chave=chave, agora=AGORA + timedelta(minutes=minutos)
        )

    tarefa = fila.pegar_proxima(sessao, agora=AGORA + timedelta(hours=1))

    assert tarefa is not None
    assert tarefa.chave == "velha"


# --- Falhas -----------------------------------------------------------------------------------


@pytest.fixture
def falha(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Troca o executor do "casar" por um que sempre falha; conta as chamadas."""
    chamadas: list[int] = []

    def _falhar(sessao: Session, dados: dict[str, Any], agora: datetime) -> None:
        chamadas.append(1)
        raise RuntimeError("falha de propósito")

    monkeypatch.setitem(fila.EXECUTORES, "casar_passagem", _falhar)
    return chamadas


def test_tarefa_com_erro_volta_para_a_fila_esperando_cada_vez_mais(
    sessao: Session, falha: list[int]
) -> None:
    fila.enfileirar(sessao, "casar_passagem", {}, chave="k", agora=AGORA)

    agora = AGORA
    for esperada in (10, 20, 40):
        fila.executar_pendentes(sessao, agora=agora)
        [tarefa] = _tarefas(sessao)
        assert tarefa.situacao == "pendente"
        assert tarefa.executar_em == agora + timedelta(seconds=esperada)
        assert tarefa.ultimo_erro == "RuntimeError: falha de propósito"
        agora = tarefa.executar_em

    assert (tarefa.tentativas, len(falha)) == (3, 3)


def test_a_espera_nao_passa_de_10_minutos() -> None:
    assert [fila.espera(n).total_seconds() for n in (1, 2, 6, 7, 20)] == [
        10,
        20,
        320,
        600,
        600,
    ]


def test_depois_de_8_tentativas_a_tarefa_falhou(sessao: Session, falha: list[int]) -> None:
    fila.enfileirar(sessao, "casar_passagem", {}, chave="k", agora=AGORA)

    agora = AGORA
    for _ in range(fila.MAXIMO_DE_TENTATIVAS):
        fila.executar_pendentes(sessao, agora=agora)
        agora += timedelta(hours=1)

    [tarefa] = _tarefas(sessao)
    assert (tarefa.situacao, tarefa.tentativas, tarefa.terminada_em) == (
        "falhou",
        fila.MAXIMO_DE_TENTATIVAS,
        agora - timedelta(hours=1),
    )
    assert fila.executar_pendentes(sessao, agora=agora) == 0
    assert len(falha) == fila.MAXIMO_DE_TENTATIVAS


def test_o_erro_de_uma_tarefa_nao_desfaz_o_que_outra_gravou(
    sessao: Session,
    agendamento: Agendamento,
    registrar_passagem: Registrar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boa = registrar_passagem()
    ruim = registrar_passagem(inicio=AGORA + timedelta(minutes=1))
    original = fila.EXECUTORES["casar_passagem"]

    def _uma_falha(sessao: Session, dados: dict[str, Any], agora: datetime) -> None:
        if dados["passagem_id"] == str(ruim.id):
            original(sessao, dados, agora)  # grava a visita...
            raise RuntimeError("e falha depois")  # ...e o erro a desfaz
        original(sessao, dados, agora)

    monkeypatch.setitem(fila.EXECUTORES, "casar_passagem", _uma_falha)

    fila.executar_pendentes(sessao, agora=AGORA + timedelta(minutes=2))

    entradas = set(sessao.scalars(select(Visita.passagem_entrada_id)))
    assert entradas == {boa.id}


def test_o_texto_do_erro_e_cortado(sessao: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def _falhar(sessao: Session, dados: dict[str, Any], agora: datetime) -> None:
        raise ValueError("x" * 5000)

    monkeypatch.setitem(fila.EXECUTORES, "casar_passagem", _falhar)
    fila.enfileirar(sessao, "casar_passagem", {}, chave="k", agora=AGORA)

    fila.executar_pendentes(sessao, agora=AGORA)

    [tarefa] = _tarefas(sessao)
    assert tarefa.ultimo_erro is not None
    assert len(tarefa.ultimo_erro) == fila.TAMANHO_DO_ERRO


# --- Dois workers -----------------------------------------------------------------------------


@pytest.fixture
def banco_de_verdade(url_banco_teste: str) -> Iterator[Callable[[], Session]]:
    """Sessões em conexões separadas, com commit de verdade (limpas no fim)."""
    motor = create_engine(url_banco_teste)
    yield lambda: Session(motor)
    with Session(motor) as sessao:
        sessao.execute(delete(TarefaDeFundo))
        sessao.commit()
    motor.dispose()


def test_dois_workers_nunca_pegam_a_mesma_tarefa(
    banco_de_verdade: Callable[[], Session],
) -> None:
    with banco_de_verdade() as sessao:
        for chave in ("a", "b"):
            fila.enfileirar(sessao, "casar_passagem", {}, chave=chave, agora=AGORA)
        sessao.commit()

    with (
        banco_de_verdade() as primeiro,
        banco_de_verdade() as segundo,
        banco_de_verdade() as terceiro,
    ):
        tarefa_1 = fila.pegar_proxima(primeiro, agora=AGORA)  # fica travada até o commit
        tarefa_2 = fila.pegar_proxima(segundo, agora=AGORA)
        tarefa_3 = fila.pegar_proxima(terceiro, agora=AGORA)

        assert tarefa_1 is not None and tarefa_2 is not None
        assert {tarefa_1.chave, tarefa_2.chave} == {"a", "b"}
        assert tarefa_3 is None


# --- "Não veio" (SDD 5.2) ---------------------------------------------------------------------


def test_nao_veio_depois_da_janela_mais_a_tolerancia(
    sessao: Session, agendamento: Agendamento
) -> None:
    prazo = agendamento.janela_fim + fila.TOLERANCIA_DO_NAO_VEIO

    assert fila.conferir_nao_veio(sessao, agora=prazo) == 0
    assert fila.conferir_nao_veio(sessao, agora=prazo + timedelta(seconds=1)) == 1

    visita = sessao.scalars(select(Visita).where(Visita.agendamento_id == agendamento.id)).one()
    assert (visita.estado, visita.chegou_em) == ("NAO_VEIO", None)


def test_nao_veio_nao_mexe_em_quem_chegou(
    sessao: Session, agendamento: Agendamento, registrar_passagem: Registrar
) -> None:
    registrar_passagem()
    fila.executar_pendentes(sessao, agora=AGORA)

    assert fila.conferir_nao_veio(sessao, agora=AGORA + timedelta(days=1)) == 0


def test_nao_veio_nao_mexe_em_cancelado(
    sessao: Session, agendamento: Agendamento, acesso_a: Acesso
) -> None:
    agendamentos.cancelar(sessao, acesso_a, agendamento.id, agora=AGORA)

    assert fila.conferir_nao_veio(sessao, agora=AGORA + timedelta(days=1)) == 0


def test_nao_veio_conferido_de_novo_nao_duplica(sessao: Session, agendamento: Agendamento) -> None:
    depois = AGORA + timedelta(days=1)
    fila.conferir_nao_veio(sessao, agora=depois)

    assert fila.conferir_nao_veio(sessao, agora=depois) == 0
    assert sessao.scalar(select(func.count()).select_from(Visita)) == 1


# --- O laço do worker -------------------------------------------------------------------------


def test_o_laco_roda_as_tarefas_e_o_nao_veio_ate_mandarem_parar(
    sessao: Session, agendamento: Agendamento, registrar_passagem: Registrar
) -> None:
    registrar_passagem()
    parar = threading.Event()
    horas = iter([AGORA, AGORA + timedelta(days=1)])
    voltas: list[int] = []

    def dormir(_segundos: float) -> None:
        voltas.append(1)
        if len(voltas) == 2:
            parar.set()

    fila.rodar(
        lambda: sessao, parar, relogio=lambda: next(horas, AGORA + timedelta(days=1)),
        dormir=dormir,
    )  # fmt: skip

    assert [t.situacao for t in _tarefas(sessao)] == ["feita"]
    assert sessao.scalar(select(func.count()).select_from(Visita)) == 1  # a do check-in


def test_o_laco_segue_depois_de_um_erro_inesperado(
    sessao: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    parar = threading.Event()

    def quebrar(sessao: Session, *, agora: datetime) -> int:
        parar.set()
        raise RuntimeError("banco fora do ar")

    monkeypatch.setattr(fila, "executar_pendentes", quebrar)

    fila.rodar(lambda: sessao, parar, relogio=lambda: AGORA, dormir=lambda _s: None)

    assert "banco fora do ar" in caplog.text

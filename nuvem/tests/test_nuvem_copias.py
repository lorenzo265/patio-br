"""As cópias do banco e a restauração de teste (SDD 7.2, D-74), com um balde na memória e um
servidor de mentira: o banco "restaurado" é o próprio banco do teste."""

import hashlib
import io
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem import tarefas_de_fundo as fila
from nuvem.copias import servico as copias
from nuvem.copias.guarda import Gravada, Legivel
from nuvem.copias.modelos import CopiaDoBanco, RestauracaoDeTeste
from nuvem.copias.postgres import ProgramaFalhouError
from nuvem.copias.servico import Copias
from nuvem.portaria.modelos import Evento

pytestmark = pytest.mark.integracao

ARQUIVO_ALEMBIC = Path(__file__).resolve().parents[1] / "alembic.ini"
AGORA = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
"""9h em Brasília."""
CONTEUDO = b"uma copia inventada do banco"


class GuardaNaMemoria:
    """O balde das cópias num dicionário."""

    def __init__(self) -> None:
        self.arquivos: dict[str, bytes] = {}
        self.apagados: list[str] = []

    def gravar(self, nome: str, leitor: Legivel) -> Gravada:
        dados = b"".join(iter(lambda: leitor.read(5), b""))
        self.arquivos[nome] = dados
        return Gravada(len(dados), hashlib.sha256(dados).hexdigest())

    @contextmanager
    def abrir(self, nome: str) -> Iterator[Legivel]:
        yield io.BytesIO(self.arquivos[nome])

    def apagar(self, nome: str) -> None:
        self.arquivos.pop(nome, None)
        self.apagados.append(nome)


class BancoDeMentira:
    """Copia ``CONTEUDO``; a volta lê tudo e dá a sessão do teste como o banco restaurado."""

    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao
        self.falha_na_copia = False
        self.falha_na_volta = False
        self.voltou: bytes | None = None

    @contextmanager
    def despejar(self) -> Iterator[Legivel]:
        yield io.BytesIO(CONTEUDO)
        if self.falha_na_copia:
            raise ProgramaFalhouError("o pg_dump terminou com 1: sem conexão")

    @contextmanager
    def restaurar(self, leitor: Legivel) -> Iterator[Session]:
        self.voltou = leitor.read()
        if self.falha_na_volta:
            raise ProgramaFalhouError("o pg_restore terminou com 1: placa ABC1D23")
        yield self.sessao


@pytest.fixture
def banco(sessao: Session) -> BancoDeMentira:
    return BancoDeMentira(sessao)


@pytest.fixture
def guarda() -> GuardaNaMemoria:
    return GuardaNaMemoria()


@pytest.fixture
def as_copias(guarda: GuardaNaMemoria, banco: BancoDeMentira) -> Copias:
    return Copias(guarda=guarda, banco=banco)


def _cabeca() -> str:
    cabeca = ScriptDirectory.from_config(Config(ARQUIVO_ALEMBIC)).get_current_head()
    assert cabeca is not None
    return cabeca


def _copia(sessao: Session, feita_em: datetime, **mudancas: object) -> CopiaDoBanco:
    dados: dict[str, object] = {
        "nome": copias.nome_da_copia(feita_em),
        "feita_em": feita_em,
        "tamanho": len(CONTEUDO),
        "resumo": hashlib.sha256(CONTEUDO).hexdigest(),
        "migracao": _cabeca(),
        "contagens": {"evento": 0},
        "ultimo_evento": None,
    }
    dados.update(mudancas)
    copia = CopiaDoBanco(**dados)
    sessao.add(copia)
    sessao.flush()
    return copia


def _teste(sessao: Session, copia: CopiaDoBanco, feita_em: datetime, *, ok: bool) -> None:
    sessao.add(RestauracaoDeTeste(copia_id=copia.id, feita_em=feita_em, ok=ok))
    sessao.flush()


# --- O manifesto ----------------------------------------------------------------------------


def test_as_tabelas_contadas_sao_as_que_so_crescem(sessao: Session) -> None:
    tabelas = copias.tabelas_so_de_acrescimo(sessao)

    assert {"evento", "elo_da_prova", "foto_recebida", "conferencia_placa"} <= set(tabelas)
    assert "visita" not in tabelas  # o estado da visita muda
    assert "passagem" not in tabelas  # sem o gatilho: a guarda e o casamento mexem nela
    assert "copia_do_banco" not in tabelas
    assert tabelas == sorted(tabelas)


def test_o_manifesto_anota_a_migracao_as_contagens_e_o_ultimo_evento(
    sessao: Session, registrar_passagem: Callable[..., Passagem]
) -> None:
    registrar_passagem(fotos=[])
    antes = copias.manifesto(sessao)
    fila.executar_pendentes(sessao, agora=AGORA)  # o casamento grava o evento da chegada

    depois = copias.manifesto(sessao)

    assert antes.migracao == depois.migracao == _cabeca()
    assert set(antes.contagens) == set(copias.tabelas_so_de_acrescimo(sessao))
    assert antes.contagens["evento"] == 0 and antes.ultimo_evento is None
    ultimo = sessao.scalar(select(func.max(Evento.registrado_em)))
    assert depois.contagens["evento"] >= 1 and depois.ultimo_evento == ultimo


# --- Quando ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agora", "marco"),
    [
        # 2h59 em Brasília: ainda vale a cópia de ontem.
        (datetime(2026, 10, 6, 5, 59, tzinfo=UTC), datetime(2026, 10, 5, 6, 0, tzinfo=UTC)),
        (datetime(2026, 10, 6, 6, 0, tzinfo=UTC), datetime(2026, 10, 6, 6, 0, tzinfo=UTC)),
        (datetime(2026, 10, 7, 2, 0, tzinfo=UTC), datetime(2026, 10, 6, 6, 0, tzinfo=UTC)),
    ],
)
def test_o_marco_da_copia_e_as_ultimas_3h_de_brasilia(agora: datetime, marco: datetime) -> None:
    assert copias.marco_da_copia(agora) == marco


@pytest.mark.parametrize(
    ("agora", "marco"),
    [
        (datetime(2026, 11, 1, 6, 59, tzinfo=UTC), datetime(2026, 10, 1, 7, 0, tzinfo=UTC)),
        (datetime(2026, 11, 1, 7, 0, tzinfo=UTC), datetime(2026, 11, 1, 7, 0, tzinfo=UTC)),
        (datetime(2026, 11, 20, 12, 0, tzinfo=UTC), datetime(2026, 11, 1, 7, 0, tzinfo=UTC)),
        (datetime(2027, 1, 1, 5, 0, tzinfo=UTC), datetime(2026, 12, 1, 7, 0, tzinfo=UTC)),
    ],
)
def test_o_marco_da_restauracao_e_o_ultimo_dia_1_as_4h(agora: datetime, marco: datetime) -> None:
    assert copias.marco_da_restauracao(agora) == marco


def test_a_copia_fica_pendente_ate_haver_uma_depois_das_3h(sessao: Session) -> None:
    marco = copias.marco_da_copia(AGORA)
    assert copias.copia_pendente(sessao, agora=AGORA)

    _copia(sessao, marco - timedelta(seconds=1))
    assert copias.copia_pendente(sessao, agora=AGORA)

    _copia(sessao, marco)
    assert not copias.copia_pendente(sessao, agora=AGORA)


def test_a_restauracao_fica_pendente_ate_uma_passar_no_mes(sessao: Session) -> None:
    marco = copias.marco_da_restauracao(AGORA)
    copia = _copia(sessao, AGORA - timedelta(days=40))
    assert copias.restauracao_pendente(sessao, agora=AGORA)

    _teste(sessao, copia, marco - timedelta(seconds=1), ok=True)  # a do mês passado
    assert copias.restauracao_pendente(sessao, agora=AGORA)

    _teste(sessao, copia, marco, ok=True)
    assert not copias.restauracao_pendente(sessao, agora=AGORA)


def test_depois_de_falhar_a_restauracao_espera_para_tentar_de_novo(sessao: Session) -> None:
    copia = _copia(sessao, AGORA - timedelta(days=1))
    _teste(sessao, copia, AGORA - copias.NOVA_TENTATIVA + timedelta(minutes=1), ok=False)
    assert not copias.restauracao_pendente(sessao, agora=AGORA)

    depois = AGORA + timedelta(minutes=1)
    assert copias.restauracao_pendente(sessao, agora=depois)


# --- A cópia --------------------------------------------------------------------------------


def test_a_copia_vai_para_o_balde_com_o_resumo_e_o_manifesto(
    sessao: Session, as_copias: Copias, guarda: GuardaNaMemoria
) -> None:
    anotado = copias.manifesto(sessao)

    copia = copias.fazer_copia(sessao, as_copias, agora=AGORA)

    assert copia.nome == "copia-20261006-120000.dump"
    assert guarda.arquivos == {copia.nome: CONTEUDO}
    assert (copia.tamanho, copia.resumo) == (len(CONTEUDO), hashlib.sha256(CONTEUDO).hexdigest())
    assert (copia.migracao, copia.contagens, copia.ultimo_evento) == (
        anotado.migracao,
        anotado.contagens,
        anotado.ultimo_evento,
    )
    assert copia.feita_em == AGORA and copia.apagada_em is None


def test_a_copia_que_falha_no_meio_e_apagada_do_balde(
    sessao: Session, as_copias: Copias, guarda: GuardaNaMemoria, banco: BancoDeMentira
) -> None:
    banco.falha_na_copia = True

    with pytest.raises(ProgramaFalhouError):
        copias.fazer_copia(sessao, as_copias, agora=AGORA)

    assert guarda.arquivos == {}
    assert guarda.apagados == ["copia-20261006-120000.dump"]
    assert sessao.scalar(select(func.count()).select_from(CopiaDoBanco)) == 0


def test_a_guarda_apaga_as_de_mais_de_30_dias(sessao: Session, guarda: GuardaNaMemoria) -> None:
    velhas = [_copia(sessao, AGORA - timedelta(days=d)) for d in (40, 31)]
    novas = [_copia(sessao, AGORA - timedelta(days=d)) for d in (30, 1)]

    assert copias.apagar_vencidas(sessao, guarda, agora=AGORA) == 2

    assert guarda.apagados == [c.nome for c in velhas]
    assert all(c.apagada_em == AGORA for c in velhas)
    assert all(c.apagada_em is None for c in novas)
    assert copias.apagar_vencidas(sessao, guarda, agora=AGORA) == 0  # já foram


def test_a_guarda_nunca_apaga_a_copia_mais_nova(sessao: Session, guarda: GuardaNaMemoria) -> None:
    _copia(sessao, AGORA - timedelta(days=50))
    mais_nova = _copia(sessao, AGORA - timedelta(days=40))

    assert copias.apagar_vencidas(sessao, guarda, agora=AGORA) == 1

    assert mais_nova.apagada_em is None
    assert guarda.apagados == [copias.nome_da_copia(AGORA - timedelta(days=50))]


# --- A conferência --------------------------------------------------------------------------


def test_a_copia_de_agora_confere_com_o_proprio_banco(
    sessao: Session, as_copias: Copias, registrar_passagem: Callable[..., Passagem]
) -> None:
    registrar_passagem(fotos=[])
    fila.executar_pendentes(sessao, agora=AGORA)
    copia = copias.fazer_copia(sessao, as_copias, agora=AGORA)

    assert copias.conferir(sessao, copia) == []


def test_a_conferencia_aponta_a_tabela_com_menos_linhas(sessao: Session) -> None:
    copia = _copia(sessao, AGORA, contagens={"evento": 0, "elo_da_prova": 1})

    assert copias.conferir(sessao, copia) == ["elo_da_prova: 0 linhas, menos que as 1 anotadas"]


def test_a_conferencia_aponta_a_migracao_diferente(sessao: Session) -> None:
    copia = _copia(sessao, AGORA, migracao="9999")

    assert copias.conferir(sessao, copia) == [f"a migração é {_cabeca()}, e a cópia anotou 9999"]


def test_a_conferencia_aponta_o_ultimo_evento_que_sumiu(
    sessao: Session, registrar_passagem: Callable[..., Passagem]
) -> None:
    sem_evento = _copia(sessao, AGORA, ultimo_evento=AGORA)
    assert copias.conferir(sessao, sem_evento) == ["o último evento é mais velho que o anotado"]

    registrar_passagem(fotos=[])
    fila.executar_pendentes(sessao, agora=AGORA)
    ultimo = sessao.scalar(select(func.max(Evento.registrado_em)))
    assert ultimo is not None
    adiante = _copia(sessao, AGORA + timedelta(hours=1), ultimo_evento=ultimo + timedelta(0, 1))
    assert copias.conferir(sessao, adiante) == ["o último evento é mais velho que o anotado"]
    em_dia = _copia(sessao, AGORA + timedelta(hours=2), ultimo_evento=ultimo)
    assert copias.conferir(sessao, em_dia) == []


def test_a_conferencia_nao_aceita_uma_copia_sem_contagens(sessao: Session) -> None:
    copia = _copia(sessao, AGORA, contagens={})

    assert copias.conferir(sessao, copia) == ["a cópia não anotou nenhuma tabela para contar"]


# --- A restauração de teste -----------------------------------------------------------------


def test_a_restauracao_volta_a_copia_mais_nova_e_registra_que_passou(
    sessao: Session, as_copias: Copias, banco: BancoDeMentira, guarda: GuardaNaMemoria
) -> None:
    antiga = copias.fazer_copia(sessao, as_copias, agora=AGORA - timedelta(days=2))
    guarda.arquivos[antiga.nome] = b"outra coisa"
    nova = copias.fazer_copia(sessao, as_copias, agora=AGORA - timedelta(days=1))

    teste = copias.testar_restauracao(sessao, as_copias, agora=AGORA)

    assert teste is not None
    assert (teste.copia_id, teste.ok, teste.detalhe, teste.feita_em) == (nova.id, True, None, AGORA)
    assert banco.voltou == CONTEUDO


def test_a_restauracao_pula_a_copia_apagada(
    sessao: Session, as_copias: Copias, guarda: GuardaNaMemoria
) -> None:
    guardada = copias.fazer_copia(sessao, as_copias, agora=AGORA - timedelta(days=2))
    apagada = _copia(sessao, AGORA - timedelta(days=1), apagada_em=AGORA)

    teste = copias.testar_restauracao(sessao, as_copias, agora=AGORA)

    assert teste is not None and teste.copia_id == guardada.id != apagada.id


def test_a_restauracao_confere_o_resumo_do_arquivo(
    sessao: Session, as_copias: Copias, guarda: GuardaNaMemoria, caplog: pytest.LogCaptureFixture
) -> None:
    copia = copias.fazer_copia(sessao, as_copias, agora=AGORA - timedelta(days=1))
    guarda.arquivos[copia.nome] = CONTEUDO.replace(b"banco", b"BANCO")

    teste = copias.testar_restauracao(sessao, as_copias, agora=AGORA)

    assert teste is not None and not teste.ok
    assert teste.detalhe == "o arquivo não confere com o resumo anotado"
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_a_restauracao_que_falha_fica_registrada_sem_dado_pessoal(
    sessao: Session,
    as_copias: Copias,
    banco: BancoDeMentira,
    caplog: pytest.LogCaptureFixture,
) -> None:
    copia = copias.fazer_copia(sessao, as_copias, agora=AGORA - timedelta(days=1))
    banco.falha_na_volta = True

    with caplog.at_level(logging.INFO, logger="nuvem.copias"):
        teste = copias.testar_restauracao(sessao, as_copias, agora=AGORA)

    assert teste is not None and (teste.copia_id, teste.ok) == (copia.id, False)
    assert teste.detalhe == "a volta falhou: o pg_restore terminou com 1: placa [placa]"
    [erro] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert str(copia.id) in erro.getMessage() and "ABC1D23" not in erro.getMessage()


def test_sem_copia_a_restauracao_nao_faz_nada(sessao: Session, as_copias: Copias) -> None:
    assert copias.testar_restauracao(sessao, as_copias, agora=AGORA) is None
    assert sessao.scalar(select(func.count()).select_from(RestauracaoDeTeste)) == 0


# --- O worker -------------------------------------------------------------------------------


def test_na_primeira_vez_cuidar_faz_a_copia_e_a_restauracao(
    sessao: Session, as_copias: Copias
) -> None:
    copias.cuidar(sessao, as_copias, agora=AGORA)

    [copia] = sessao.scalars(select(CopiaDoBanco)).all()
    [teste] = sessao.scalars(select(RestauracaoDeTeste)).all()
    assert (teste.copia_id, teste.ok) == (copia.id, True)

    copias.cuidar(sessao, as_copias, agora=AGORA + timedelta(minutes=10))  # nada pendente
    assert sessao.scalar(select(func.count()).select_from(CopiaDoBanco)) == 1
    assert sessao.scalar(select(func.count()).select_from(RestauracaoDeTeste)) == 1


def test_a_copia_que_falha_nao_impede_a_guarda_nem_a_restauracao(
    sessao: Session,
    as_copias: Copias,
    banco: BancoDeMentira,
    guarda: GuardaNaMemoria,
    caplog: pytest.LogCaptureFixture,
) -> None:
    velha = copias.fazer_copia(sessao, as_copias, agora=AGORA - timedelta(days=40))
    ontem = copias.fazer_copia(sessao, as_copias, agora=AGORA - timedelta(days=1))
    sessao.commit()  # como o worker: o que veio antes está gravado
    banco.falha_na_copia = True

    copias.cuidar(sessao, as_copias, agora=AGORA)

    assert "cópia do banco: falhou" in caplog.text
    assert velha.apagada_em == AGORA and velha.nome not in guarda.arquivos
    [teste] = sessao.scalars(select(RestauracaoDeTeste)).all()
    assert (teste.copia_id, teste.ok) == (ontem.id, True)
    assert sessao.scalar(select(func.count()).select_from(CopiaDoBanco)) == 2


def test_um_erro_do_banco_numa_parte_nao_estraga_as_outras(
    sessao: Session, as_copias: Copias, monkeypatch: pytest.MonkeyPatch
) -> None:
    ontem = copias.fazer_copia(sessao, as_copias, agora=AGORA - timedelta(days=1))
    sessao.commit()

    def quebrar(sessao: Session) -> copias.Manifesto:
        sessao.execute(text("select 1 / 0"))  # a transação fica perdida até o rollback
        raise AssertionError("não chega aqui")

    monkeypatch.setattr(copias, "manifesto", quebrar)

    copias.cuidar(sessao, as_copias, agora=AGORA)

    [teste] = sessao.scalars(select(RestauracaoDeTeste)).all()
    assert (teste.copia_id, teste.ok) == (ontem.id, True)


def test_o_worker_cuida_das_copias_a_cada_10_minutos(
    sessao: Session, as_copias: Copias, monkeypatch: pytest.MonkeyPatch
) -> None:
    vezes: list[datetime] = []
    monkeypatch.setattr(copias, "cuidar", lambda _s, _c, *, agora: vezes.append(agora))
    horas = [AGORA + timedelta(minutes=m) for m in (0, 5, 9, 10, 15, 21)]
    relogio = iter(horas)
    parar = threading.Event()

    def proxima() -> datetime:
        hora = next(relogio)
        if hora == horas[-1]:
            parar.set()
        return hora

    fila.rodar(lambda: sessao, parar, relogio=proxima, dormir=lambda _s: None, copias=as_copias)

    assert vezes == [AGORA, AGORA + timedelta(minutes=10), AGORA + timedelta(minutes=21)]


def test_sem_o_balde_o_worker_nao_faz_copia(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    vezes: list[datetime] = []
    monkeypatch.setattr(copias, "cuidar", lambda _s, _c, *, agora: vezes.append(agora))
    parar = threading.Event()

    def proxima() -> datetime:
        parar.set()
        return AGORA

    fila.rodar(lambda: sessao, parar, relogio=proxima, dormir=lambda _s: None)

    assert vezes == []

"""A entrada do worker (``python -m nuvem.worker``): o registro e as cópias do banco (D-74)."""

import logging
import signal
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from nuvem import tarefas_de_fundo, worker
from nuvem.copias.guarda import CopiasNoS3
from nuvem.copias.postgres import BancoPostgres
from nuvem.copias.servico import Copias
from nuvem.registro import MARCA, FormatoJson

CHAVE = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="
S3 = {
    "PATIO_FOTOS_S3_ENDERECO": "https://s3.sa-east-1.amazonaws.com",
    "PATIO_FOTOS_S3_CHAVE": "chave-inventada",
    "PATIO_FOTOS_S3_SEGREDO": "segredo-inventado",
}


@pytest.fixture
def rodar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[dict[str, Any]]:
    """Roda o ``main`` do worker sem o laço; devolve o que ele passaria ao laço."""
    monkeypatch.chdir(tmp_path)  # sem o .env do repositório
    monkeypatch.setenv("PATIO_URL_BANCO", "postgresql+pg8000://patio:x@127.0.0.1:1/patio")
    monkeypatch.setenv("PATIO_CHAVE_CIFRA", CHAVE)
    monkeypatch.setattr(signal, "signal", lambda *_argumentos: None)
    recebido: dict[str, Any] = {}
    monkeypatch.setattr(
        tarefas_de_fundo, "rodar", lambda *_argumentos, **nomeados: recebido.update(nomeados)
    )
    raiz = logging.getLogger()
    antes = (raiz.handlers[:], raiz.level)
    yield recebido
    raiz.handlers[:], nivel = antes
    raiz.setLevel(nivel)


@pytest.mark.parametrize("ambiente", ["homologacao", "producao"])
def test_sem_o_balde_das_copias_o_worker_registra_um_erro(
    rodar: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    ambiente: str,
) -> None:
    monkeypatch.setenv("PATIO_AMBIENTE", ambiente)

    worker.main()

    assert rodar["copias"] is None
    erros = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert erros == ["cópias do banco desligadas: falta o PATIO_COPIAS_S3_BALDE"]


def test_no_ambiente_local_sem_copias_e_normal(
    rodar: dict[str, Any], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("PATIO_AMBIENTE", "local")

    worker.main()

    assert rodar["copias"] is None
    assert not [r for r in caplog.records if r.levelno == logging.ERROR]


def test_com_o_balde_o_worker_copia_o_banco_da_configuracao(
    rodar: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATIO_AMBIENTE", "producao")
    monkeypatch.setenv("PATIO_COPIAS_S3_BALDE", "patio-copias")
    for nome, valor in S3.items():
        monkeypatch.setenv(nome, valor)

    worker.main()

    copias = rodar["copias"]
    assert isinstance(copias, Copias)
    assert isinstance(copias.guarda, CopiasNoS3)
    assert isinstance(copias.banco, BancoPostgres)
    assert copias.banco.url.port == 1


def test_na_producao_o_registro_do_worker_e_json(
    rodar: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATIO_AMBIENTE", "producao")

    worker.main()

    [nosso] = [h for h in logging.getLogger().handlers if getattr(h, MARCA, False)]
    assert isinstance(nosso.formatter, FormatoJson)

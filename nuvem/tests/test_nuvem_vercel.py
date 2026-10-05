"""A entrada da Vercel (D-51 e D-56): o `app`, o `vercel.json` e o `pyproject.toml` combinam."""

import importlib.util
import json
import tomllib
from pathlib import Path

import pytest
from fastapi import FastAPI

RAIZ = Path(__file__).resolve().parents[2]
CHAVE = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="


def _configuracao_da_vercel() -> dict[str, object]:
    return json.loads((RAIZ / "vercel.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_o_pyproject_aponta_para_o_app_da_entrada_da_vercel() -> None:
    pyproject = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))

    modulo, variavel = pyproject["tool"]["vercel"]["entrypoint"].split(":")

    assert (RAIZ / f"{modulo}.py").is_file()
    assert variavel == "app"
    assert f"{modulo}.py" in _configuracao_da_vercel()["functions"]  # type: ignore[operator]


def test_a_entrada_monta_a_nuvem_pelo_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", "postgresql+pg8000://patio:senha@banco:5432/patio")
    monkeypatch.setenv("PATIO_CHAVE_CIFRA", CHAVE)
    monkeypatch.setenv("PATIO_AMBIENTE", "demonstracao")
    monkeypatch.setenv("PATIO_URL_PUBLICA", "https://demonstracao.example")
    monkeypatch.setenv("PATIO_TIQUE", "1")
    especificacao = importlib.util.spec_from_file_location("vercel_app", RAIZ / "vercel_app.py")
    assert especificacao is not None and especificacao.loader is not None
    modulo = importlib.util.module_from_spec(especificacao)

    especificacao.loader.exec_module(modulo)

    assert isinstance(modulo.app, FastAPI)
    assert modulo.app.state.tique is True
    assert modulo.app.state.tem_demonstracao is True


def test_a_funcao_fica_em_sao_paulo_e_o_cron_chama_a_rota_diaria() -> None:
    vercel = _configuracao_da_vercel()

    assert vercel["regions"] == ["gru1"]
    assert vercel["crons"] == [{"path": "/api/cron/diaria", "schedule": "0 9 * * *"}]

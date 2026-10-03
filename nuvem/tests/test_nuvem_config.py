"""Configuração da nuvem: lida do ambiente (variáveis PATIO_*) ou do .env da pasta atual."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from nuvem.config import Configuracao, ConfiguracaoInvalidaError, ler_configuracao

URL = "postgresql+pg8000://patio:s3nh4-de-teste@banco:5432/patio"


def test_le_a_url_do_banco_do_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)

    configuracao = Configuracao(_env_file=None)

    assert configuracao.url_banco.get_secret_value() == URL


def test_sem_url_do_banco_a_nuvem_nao_inicia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PATIO_URL_BANCO", raising=False)

    with pytest.raises(ValidationError, match="url_banco"):
        Configuracao(_env_file=None)


def test_nao_mostra_a_senha_do_banco_ao_imprimir_a_configuracao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)

    assert "s3nh4-de-teste" not in repr(Configuracao(_env_file=None))


@pytest.mark.integracao
def test_le_o_env_da_pasta_atual_e_ignora_as_variaveis_do_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # O mesmo .env serve ao docker compose (POSTGRES_*) e à nuvem (PATIO_*).
    (tmp_path / ".env").write_text(
        f"POSTGRES_SENHA=outra\nPATIO_URL_BANCO={URL}\n", encoding="utf-8"
    )
    monkeypatch.delenv("PATIO_URL_BANCO", raising=False)
    monkeypatch.chdir(tmp_path)

    assert Configuracao().url_banco.get_secret_value() == URL


@pytest.mark.integracao
def test_sem_configuracao_diz_o_que_falta_e_como_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PATIO_URL_BANCO", raising=False)
    monkeypatch.chdir(tmp_path)  # pasta sem .env

    with pytest.raises(ConfiguracaoInvalidaError, match=r"PATIO_URL_BANCO.*\.env\.exemplo"):
        ler_configuracao()

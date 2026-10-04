"""Configuração da nuvem: lida do ambiente (variáveis PATIO_*) ou do .env da pasta atual."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from nuvem.config import Configuracao, ConfiguracaoInvalidaError, ler_configuracao

URL = "postgresql+pg8000://patio:s3nh4-de-teste@banco:5432/patio"
CHAVE = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="


@pytest.fixture(autouse=True)
def chave_no_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATIO_CHAVE_CIFRA", CHAVE)


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


def test_nao_mostra_a_chave_da_cifra_ao_imprimir_a_configuracao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)

    assert CHAVE not in repr(Configuracao(_env_file=None))


def test_chave_da_cifra_invalida_impede_a_nuvem_de_iniciar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    monkeypatch.setenv("PATIO_CHAVE_CIFRA", "curta-demais")

    with pytest.raises(ValidationError, match="chave_cifra"):
        Configuracao(_env_file=None)


def test_endereco_publico_vazio_vale_como_sem_endereco(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    monkeypatch.setenv("PATIO_URL_PUBLICA", "")

    assert Configuracao(_env_file=None).url_publica is None


@pytest.mark.parametrize(
    "url",
    ["https://patio-br.example/patio", "https://patio-br.example/?de=onde", "patio-br.example"],
    ids=["caminho", "consulta", "sem esquema"],
)
def test_endereco_publico_fora_da_regra_impede_a_nuvem_de_iniciar(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    # Os endereços devolvidos à caixa começam com caminho próprio (/api/...): um caminho aqui se
    # perderia sem aviso.
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    monkeypatch.setenv("PATIO_URL_PUBLICA", url)

    with pytest.raises(ValidationError, match="url_publica"):
        Configuracao(_env_file=None)


@pytest.mark.parametrize("ambiente", ["homologacao", "producao"])
def test_fora_do_ambiente_local_o_endereco_publico_e_https(
    monkeypatch: pytest.MonkeyPatch, ambiente: str
) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    monkeypatch.setenv("PATIO_AMBIENTE", ambiente)
    monkeypatch.setenv("PATIO_URL_PUBLICA", "http://patio-br.example")

    with pytest.raises(ValidationError, match="url_publica"):
        Configuracao(_env_file=None)


def test_no_ambiente_local_o_endereco_publico_pode_ser_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    monkeypatch.setenv("PATIO_AMBIENTE", "local")
    monkeypatch.setenv("PATIO_URL_PUBLICA", "http://localhost:18000")

    assert str(Configuracao(_env_file=None).url_publica) == "http://localhost:18000/"


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
    monkeypatch.delenv("PATIO_CHAVE_CIFRA", raising=False)
    monkeypatch.chdir(tmp_path)  # pasta sem .env

    with pytest.raises(
        ConfiguracaoInvalidaError, match=r"PATIO_CHAVE_CIFRA, PATIO_URL_BANCO.*\.env\.exemplo"
    ):
        ler_configuracao()

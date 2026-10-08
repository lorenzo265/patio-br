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


def test_fotos_no_s3_pedem_a_chave_e_o_segredo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    monkeypatch.setenv(
        "PATIO_FOTOS_S3_ENDERECO", "https://projeto.storage.supabase.co/storage/v1/s3"
    )

    with pytest.raises(ValidationError, match="fotos_s3"):
        Configuracao(_env_file=None)


def test_o_segredo_do_cron_vem_do_cron_secret_da_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    monkeypatch.setenv("CRON_SECRET", "segredo-do-cron")

    configuracao = Configuracao(_env_file=None)

    assert configuracao.segredo_do_cron is not None
    assert configuracao.segredo_do_cron.get_secret_value() == "segredo-do-cron"
    assert "segredo-do-cron" not in repr(configuracao)


@pytest.mark.parametrize(
    ("ambiente", "exige"),
    [("local", False), ("demonstracao", False), ("homologacao", True), ("producao", True)],
)
def test_so_a_homologacao_e_a_producao_exigem_as_duas_etapas(
    monkeypatch: pytest.MonkeyPatch, ambiente: str, exige: bool
) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    monkeypatch.setenv("PATIO_AMBIENTE", ambiente)

    assert Configuracao(_env_file=None).exige_duas_etapas is exige


WHATSAPP_COMPLETO = {
    "PATIO_WHATSAPP_TOKEN": "token-inventado",
    "PATIO_WHATSAPP_NUMERO_ID": "1234567890",
    "PATIO_WHATSAPP_NUMERO": "5511900000000",
    "PATIO_WHATSAPP_SEGREDO_DO_APP": "segredo-inventado",
    "PATIO_WHATSAPP_CODIGO_DO_WEBHOOK": "codigo-inventado",
}


def test_o_whatsapp_completo_fica_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    for nome, valor in WHATSAPP_COMPLETO.items():
        monkeypatch.setenv(nome, valor)

    configuracao = Configuracao(_env_file=None)

    assert configuracao.tem_whatsapp
    assert configuracao.whatsapp_versao == "v25.0"


@pytest.mark.parametrize("faltando", list(WHATSAPP_COMPLETO))
def test_o_whatsapp_pela_metade_impede_a_nuvem_de_iniciar(
    monkeypatch: pytest.MonkeyPatch, faltando: str
) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    for nome, valor in WHATSAPP_COMPLETO.items():
        if nome != faltando:
            monkeypatch.setenv(nome, valor)

    with pytest.raises(ValidationError, match="whatsapp"):
        Configuracao(_env_file=None)


def test_sem_whatsapp_nada_e_enviado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)

    assert not Configuracao(_env_file=None).tem_whatsapp


def test_a_demonstracao_nunca_manda_whatsapp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    monkeypatch.setenv("PATIO_AMBIENTE", "demonstracao")
    for nome, valor in WHATSAPP_COMPLETO.items():
        monkeypatch.setenv(nome, valor)

    with pytest.raises(ValidationError, match="demonstração"):
        Configuracao(_env_file=None)


@pytest.mark.parametrize("numero", ["+5511900000000", "11900000000", "55119000a0000"])
def test_o_numero_do_whatsapp_e_so_numeros_com_o_55(
    monkeypatch: pytest.MonkeyPatch, numero: str
) -> None:
    monkeypatch.setenv("PATIO_URL_BANCO", URL)
    for nome, valor in WHATSAPP_COMPLETO.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("PATIO_WHATSAPP_NUMERO", numero)

    with pytest.raises(ValidationError, match="whatsapp_numero"):
        Configuracao(_env_file=None)

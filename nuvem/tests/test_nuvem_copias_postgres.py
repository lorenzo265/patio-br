"""O ``pg_dump`` e o ``pg_restore`` de verdade, no banco de teste (D-74).

Precisam do cliente do PostgreSQL 16 na máquina. Sem ele, os testes que o usam são pulados,
menos na CI (``PATIO_EXIGE_PG_DUMP=1``), onde a falta dele é erro.
"""

import io
import os
import shutil
import ssl
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session

from nuvem.copias import servico as copias
from nuvem.copias.guarda import LeitorComResumo
from nuvem.copias.postgres import (
    ERRO_MAXIMO,
    PREFIXO_DO_TEMPORARIO,
    TAMANHO_DO_PEDACO,
    BancoPostgres,
    ProgramaFalhouError,
    _erros,
    _passar,
)

pytestmark = pytest.mark.integracao

TEM_O_CLIENTE = shutil.which("pg_dump") is not None and shutil.which("pg_restore") is not None
precisa_do_cliente = pytest.mark.skipif(
    not TEM_O_CLIENTE and os.environ.get("PATIO_EXIGE_PG_DUMP") != "1",
    reason="sem o pg_dump e o pg_restore nesta máquina",
)


@pytest.fixture
def banco(url_banco_teste: str) -> BancoPostgres:
    return BancoPostgres(url=make_url(url_banco_teste), contexto=None, certificado=None)


def _temporarios(url_banco_teste: str) -> set[str]:
    motor = create_engine(url_banco_teste)
    with motor.connect() as conexao:
        nomes = set(
            conexao.scalars(
                text("select datname from pg_database where datname like :prefixo"),
                {"prefixo": PREFIXO_DO_TEMPORARIO + "%"},
            )
        )
    motor.dispose()
    return nomes


@pytest.fixture
def sessao_do_banco(url_banco_teste: str) -> Iterator[Session]:
    motor = create_engine(url_banco_teste)
    with Session(motor) as sessao:
        yield sessao
    motor.dispose()


@precisa_do_cliente
def test_a_copia_volta_num_banco_temporario_que_some_no_fim(
    banco: BancoPostgres, url_banco_teste: str, sessao_do_banco: Session
) -> None:
    antes = _temporarios(url_banco_teste)  # o de outra rodada que caiu no meio não conta
    anotado = copias.manifesto(sessao_do_banco)
    with banco.despejar() as leitor:
        copia = leitor.read()
    assert copia.startswith(b"PGDMP")  # o formato do próprio PostgreSQL

    with banco.restaurar(io.BytesIO(copia)) as restaurado:
        [temporario] = _temporarios(url_banco_teste) - antes
        assert copias.manifesto(restaurado) == anotado
        assert copias.tabelas_so_de_acrescimo(restaurado)  # os gatilhos voltaram

    assert temporario.startswith(PREFIXO_DO_TEMPORARIO)
    assert _temporarios(url_banco_teste) == antes


@precisa_do_cliente
def test_a_volta_que_falha_tambem_apaga_o_banco_temporario(
    banco: BancoPostgres, url_banco_teste: str
) -> None:
    antes = _temporarios(url_banco_teste)

    with (
        pytest.raises(ProgramaFalhouError, match="pg_restore terminou com 1"),
        banco.restaurar(io.BytesIO(b"isto nao e uma copia" * 1000)),
    ):
        pytest.fail("não deveria chegar aqui")

    assert _temporarios(url_banco_teste) == antes


@precisa_do_cliente
def test_a_copia_sem_acesso_ao_banco_falha_sem_mostrar_a_senha(url_banco_teste: str) -> None:
    # Porta 1: nada escuta ali, a conexão é recusada na hora.
    url = make_url(url_banco_teste).set(port=1, password="senha-inventada")
    banco = BancoPostgres(url=url, contexto=None, certificado=None)

    with (
        pytest.raises(ProgramaFalhouError, match="pg_dump terminou com 1") as erro,
        banco.despejar() as leitor,
    ):
        assert leitor.read() == b""

    assert "senha-inventada" not in str(erro.value)

    assert "senha-errada-inventada" not in str(erro.value)


@precisa_do_cliente
def test_a_copia_lida_pela_metade_e_um_erro(banco: BancoPostgres) -> None:
    with (
        pytest.raises(ProgramaFalhouError, match="não foi lida até o fim"),
        banco.despejar() as leitor,
    ):
        assert leitor.read(5) == b"PGDMP"


class EntradaFechada:
    """Como a entrada do ``pg_restore`` depois que ele parou."""

    def write(self, _dados: bytes) -> int:
        raise BrokenPipeError

    def close(self) -> None:
        raise BrokenPipeError


def test_se_o_pg_restore_para_antes_a_copia_e_lida_ate_o_fim_mesmo_assim() -> None:
    leitor = LeitorComResumo(io.BytesIO(b"x" * (3 * TAMANHO_DO_PEDACO + 1)))

    _passar(leitor, EntradaFechada())  # type: ignore[arg-type]

    assert leitor.tamanho == 3 * TAMANHO_DO_PEDACO + 1  # o resumo fica completo


def test_o_erro_do_programa_sai_sem_placa_e_so_com_o_fim(tmp_path: Path) -> None:
    with (tmp_path / "erros").open("w+b") as arquivo:
        arquivo.write(b"x" * 1000 + b"\nERROR: placa ABC1D23 duplicada")

        texto = _erros(arquivo)

    assert texto.endswith("ERROR: placa [placa] duplicada")
    assert len(texto) <= ERRO_MAXIMO


def test_a_conexao_vai_pelas_variaveis_do_postgresql(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATIO_CHAVE_CIFRA", "nao-vai-para-o-pg-dump")
    url = make_url("postgresql+pg8000://patio:segredo@banco.exemplo:6543/patio")
    banco = BancoPostgres(url=url, contexto=None, certificado=None)

    ambiente = banco._ambiente(tmp_path)

    assert {k: ambiente[k] for k in ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE")} == {
        "PGHOST": "banco.exemplo",
        "PGPORT": "6543",
        "PGUSER": "patio",
        "PGPASSWORD": "segredo",
        "PGDATABASE": "patio",
    }
    assert "PGSSLMODE" not in ambiente
    assert not any(nome.startswith("PATIO_") for nome in ambiente)  # só o necessário


def test_com_ssl_confere_o_certificado_e_o_nome_do_servidor(tmp_path: Path) -> None:
    url = make_url("postgresql+pg8000://patio:segredo@banco.exemplo/patio")
    contexto = ssl.create_default_context()

    com_autoridade = BancoPostgres(url=url, contexto=contexto, certificado="PEM INVENTADO")
    ambiente = com_autoridade._ambiente(tmp_path)
    assert ambiente["PGSSLMODE"] == "verify-full"
    assert Path(ambiente["PGSSLROOTCERT"]).read_text(encoding="utf-8") == "PEM INVENTADO"

    publica = BancoPostgres(url=url, contexto=contexto, certificado=None)
    assert publica._ambiente(tmp_path)["PGSSLROOTCERT"] == "system"

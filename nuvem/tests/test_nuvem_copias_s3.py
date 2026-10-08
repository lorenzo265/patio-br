"""O balde das cópias (D-74): a cópia vai ao S3 enquanto é lida, com o resumo e o tamanho."""

import hashlib
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import boto3
import pytest
from moto import mock_aws

from nuvem.config import Configuracao
from nuvem.copias import guarda
from nuvem.copias.guarda import CopiasNoS3, LeitorComResumo

pytestmark = pytest.mark.integracao

BALDE = "patio-copias"
CHAVE_QUALQUER = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="


@pytest.fixture
def s3() -> Iterator[Any]:
    with mock_aws():
        cliente = boto3.client("s3", region_name="us-east-1")
        cliente.create_bucket(Bucket=BALDE)
        yield cliente


class SoLeitura:
    """Um leitor que não volta (como a saída do ``pg_dump``)."""

    def __init__(self, dados: bytes) -> None:
        self._dados = io.BytesIO(dados)

    def read(self, tamanho: int = -1, /) -> bytes:
        return self._dados.read(tamanho)


@pytest.mark.parametrize("tamanho", [0, 1000, 9 * 1024 * 1024])  # a grande vai em partes
def test_grava_enquanto_le_com_o_resumo_e_o_tamanho(s3: Any, tamanho: int) -> None:
    dados = bytes(range(256)) * (tamanho // 256) + b"x" * (tamanho % 256)

    gravada = CopiasNoS3(s3, BALDE).gravar("copia-1.dump", SoLeitura(dados))

    assert gravada == guarda.Gravada(len(dados), hashlib.sha256(dados).hexdigest())
    assert s3.get_object(Bucket=BALDE, Key="copia-1.dump")["Body"].read() == dados


def test_abre_para_ler_e_apaga(s3: Any) -> None:
    copias = CopiasNoS3(s3, BALDE)
    copias.gravar("copia-1.dump", SoLeitura(b"conteudo inventado"))

    with copias.abrir("copia-1.dump") as arquivo:
        assert arquivo.read() == b"conteudo inventado"
    copias.apagar("copia-1.dump")
    copias.apagar("copia-1.dump")  # de novo: nada

    assert s3.list_objects_v2(Bucket=BALDE).get("KeyCount") == 0


def test_o_leitor_conta_o_que_passa() -> None:
    leitor = LeitorComResumo(SoLeitura(b"abcdef"))

    assert leitor.read(4) + leitor.read() == b"abcdef"
    assert (leitor.tamanho, leitor.resumo) == (6, hashlib.sha256(b"abcdef").hexdigest())
    assert leitor.readable()


def _configuracao(tmp_path: Path, **valores: Any) -> Configuracao:
    return Configuracao(
        url_banco="postgresql+pg8000://patio:x@localhost/patio",
        chave_cifra=CHAVE_QUALQUER,
        pasta_fotos=tmp_path,
        _env_file=None,
        **valores,
    )


def test_sem_o_balde_nao_ha_copias(tmp_path: Path) -> None:
    assert guarda.guarda_das_copias_da_configuracao(_configuracao(tmp_path)) is None


def test_com_o_balde_as_copias_vao_ao_s3_das_fotos(tmp_path: Path, s3: Any) -> None:
    configuracao = _configuracao(
        tmp_path,
        fotos_s3_endereco="https://s3.us-east-1.amazonaws.com",
        fotos_s3_regiao="us-east-1",
        fotos_s3_chave="chave-inventada",
        fotos_s3_segredo="segredo-inventado",
        copias_s3_balde=BALDE,
    )

    copias = guarda.guarda_das_copias_da_configuracao(configuracao)

    assert isinstance(copias, CopiasNoS3)
    copias.gravar("copia-1.dump", SoLeitura(b"x"))
    assert s3.get_object(Bucket=BALDE, Key="copia-1.dump")["Body"].read() == b"x"

"""As fotos num armazenamento S3 (D-56): o Supabase Storage na demonstração e a AWS no mês 4.

O S3 é imitado pelo moto, na memória: os testes não saem para a rede.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import boto3
import pytest
from botocore.config import Config
from moto import mock_aws

from nuvem.armazenamento import (
    ArmazenamentoS3,
    FotoDiferenteError,
    FotoNaoJpegError,
    RefInvalidoError,
)

BALDE = "fotos"
FOTO = b"\xff\xd8\xff" + b"uma foto"
OUTRA = b"\xff\xd8\xff" + b"outra foto"
AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)


@pytest.fixture
def cliente() -> Iterator[Any]:
    with mock_aws():
        # Como o da_configuracao monta: assinatura s3v4 e o balde no caminho.
        s3 = boto3.client(
            "s3", region_name="sa-east-1", aws_access_key_id="x", aws_secret_access_key="y",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )  # fmt: skip
        s3.create_bucket(
            Bucket=BALDE, CreateBucketConfiguration={"LocationConstraint": "sa-east-1"}
        )
        yield s3


@pytest.fixture
def armazenamento(cliente: Any) -> ArmazenamentoS3:
    return ArmazenamentoS3(cliente, BALDE)


def _chaves(cliente: Any) -> list[str]:
    paginas = cliente.get_paginator("list_objects_v2").paginate(Bucket=BALDE)
    return sorted(objeto["Key"] for pagina in paginas for objeto in pagina.get("Contents", []))


def test_guarda_e_le_a_foto_na_pasta_da_caixa(armazenamento: ArmazenamentoS3, cliente: Any) -> None:
    assert armazenamento.guardar(7, "p/1.jpg", FOTO) is True

    assert armazenamento.ler(7, "p/1.jpg") == FOTO
    assert _chaves(cliente) == ["caixa-7/p/1.jpg"]


def test_foto_que_nao_chegou_e_nada(armazenamento: ArmazenamentoS3) -> None:
    assert armazenamento.ler(7, "p/1.jpg") is None


def test_a_mesma_foto_de_novo_nao_muda_nada(armazenamento: ArmazenamentoS3) -> None:
    armazenamento.guardar(7, "p/1.jpg", FOTO)

    assert armazenamento.guardar(7, "p/1.jpg", FOTO) is False


def test_outra_foto_no_mesmo_ref_e_recusada(armazenamento: ArmazenamentoS3) -> None:
    armazenamento.guardar(7, "p/1.jpg", FOTO)

    with pytest.raises(FotoDiferenteError):
        armazenamento.guardar(7, "p/1.jpg", OUTRA)
    assert armazenamento.ler(7, "p/1.jpg") == FOTO


def test_so_guarda_jpeg(armazenamento: ArmazenamentoS3) -> None:
    with pytest.raises(FotoNaoJpegError):
        armazenamento.guardar(7, "p/1.png", b"\x89PNG")


@pytest.mark.parametrize("ref", ["../outra-caixa/x.jpg", "a/../b.jpg", "NUL", "a b.jpg"])
def test_ref_fora_da_regra_e_recusado(armazenamento: ArmazenamentoS3, ref: str) -> None:
    with pytest.raises(RefInvalidoError):
        armazenamento.ler(7, ref)
    with pytest.raises(RefInvalidoError):
        armazenamento.guardar(7, ref, FOTO)
    with pytest.raises(RefInvalidoError):
        armazenamento.endereco_de_envio(7, ref, agora=AGORA)


def test_uma_caixa_nao_alcanca_a_foto_de_outra(armazenamento: ArmazenamentoS3) -> None:
    armazenamento.guardar(7, "p/1.jpg", FOTO)

    assert armazenamento.ler(8, "p/1.jpg") is None


def test_apagar_da_caixa_apaga_so_as_fotos_dela(
    armazenamento: ArmazenamentoS3, cliente: Any
) -> None:
    for numero in range(3):
        armazenamento.guardar(7, f"p/{numero}.jpg", FOTO)
    armazenamento.guardar(70, "p/1.jpg", FOTO)

    armazenamento.apagar_da_caixa(7)

    assert _chaves(cliente) == ["caixa-70/p/1.jpg"]


def test_apagar_da_caixa_passa_de_mil_fotos(armazenamento: ArmazenamentoS3, cliente: Any) -> None:
    # O S3 lista e apaga de mil em mil.
    for numero in range(1001):
        cliente.put_object(Bucket=BALDE, Key=f"caixa-7/p/{numero}.jpg", Body=FOTO)

    armazenamento.apagar_da_caixa(7)

    assert _chaves(cliente) == []


def test_endereco_de_envio_e_assinado_e_vale_15_minutos(armazenamento: ArmazenamentoS3) -> None:
    endereco = armazenamento.endereco_de_envio(7, "p/1.jpg", agora=AGORA)

    assert "/fotos/caixa-7/p/1.jpg?" in endereco
    assert "X-Amz-Signature=" in endereco
    assert "X-Amz-Expires=900" in endereco


def test_da_configuracao_usa_o_endereco_e_o_caminho_no_endereco() -> None:
    # O Supabase pede o balde no caminho (path-style), e não no nome do servidor.
    armazenamento = ArmazenamentoS3.da_configuracao(
        endereco="https://projeto.storage.supabase.co/storage/v1/s3", regiao="sa-east-1",
        balde=BALDE, chave="chave", segredo="segredo",
    )  # fmt: skip

    endereco = armazenamento.endereco_de_envio(7, "p/1.jpg", agora=AGORA)

    assert endereco.startswith("https://projeto.storage.supabase.co/storage/v1/s3/fotos/caixa-7/")

"""Onde a âncora do dia fica guardada (D-69): no disco, ou num balde S3 travado (Object Lock)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from nuvem.config import Configuracao
from nuvem.prova import ancoras
from nuvem.prova.ancoras import AncoraDiferenteError, AncorasNoDisco, AncorasNoS3

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 6, 0, 15, tzinfo=UTC)
CONTEUDO = b'{"dia":"2026-10-05","visitas":[]}'
CHAVE_QUALQUER = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="
BALDE = "patio-ancoras"


@pytest.fixture
def s3() -> Iterator[Any]:
    with mock_aws():
        cliente = boto3.client("s3", region_name="us-east-1")
        cliente.create_bucket(Bucket=BALDE, ObjectLockEnabledForBucket=True)
        yield cliente


def test_no_disco_grava_uma_vez_e_le(tmp_path: Path) -> None:
    guarda = AncorasNoDisco(tmp_path)

    gravada = guarda.gravar("2026-10-05.json", CONTEUDO, agora=AGORA)
    de_novo = guarda.gravar("2026-10-05.json", CONTEUDO, agora=AGORA)  # o mesmo: tudo bem

    assert gravada == de_novo == ancoras.Gravada("ancoras/2026-10-05.json", travada=False)
    assert guarda.ler(gravada.arquivo) == CONTEUDO
    assert guarda.ler("ancoras/2026-10-04.json") is None
    with pytest.raises(AncoraDiferenteError):
        guarda.gravar("2026-10-05.json", b"{}", agora=AGORA)


def test_no_s3_travada_em_conformidade_por_5_anos(s3: Any) -> None:
    guarda = AncorasNoS3(s3, BALDE, travar=True)

    gravada = guarda.gravar("2026-10-05.json", CONTEUDO, agora=AGORA)

    assert gravada == ancoras.Gravada("ancoras/2026-10-05.json", travada=True)
    cabecalho = s3.head_object(Bucket=BALDE, Key="ancoras/2026-10-05.json")
    assert cabecalho["ObjectLockMode"] == "COMPLIANCE"
    trava = cabecalho["ObjectLockRetainUntilDate"]
    assert AGORA + timedelta(days=365 * 5) <= trava <= AGORA + timedelta(days=366 * 5)
    assert guarda.ler(gravada.arquivo) == CONTEUDO
    # Nem o dono da conta apaga a versão travada.
    (versao,) = s3.list_object_versions(Bucket=BALDE)["Versions"]
    with pytest.raises(ClientError):
        s3.delete_object(Bucket=BALDE, Key=gravada.arquivo, VersionId=versao["VersionId"])


def test_no_s3_nao_troca_a_ancora_gravada(s3: Any) -> None:
    guarda = AncorasNoS3(s3, BALDE, travar=True)
    guarda.gravar("2026-10-05.json", CONTEUDO, agora=AGORA)

    guarda.gravar("2026-10-05.json", CONTEUDO, agora=AGORA)  # a mesma de novo: tudo bem
    with pytest.raises(AncoraDiferenteError):
        guarda.gravar("2026-10-05.json", b"{}", agora=AGORA)

    assert guarda.ler("ancoras/2026-10-05.json") == CONTEUDO
    assert guarda.ler("ancoras/2026-10-04.json") is None


def test_no_s3_sem_trava_na_demonstracao(s3: Any) -> None:
    s3.create_bucket(Bucket="fotos")
    guarda = AncorasNoS3(s3, "fotos", travar=False)

    gravada = guarda.gravar("2026-10-05.json", CONTEUDO, agora=AGORA)

    assert gravada.travada is False
    assert "ObjectLockMode" not in s3.head_object(Bucket="fotos", Key=gravada.arquivo)


def _configuracao(tmp_path: Path, **valores: Any) -> Configuracao:
    return Configuracao(
        url_banco="postgresql+pg8000://u:s@localhost/b",
        chave_cifra=CHAVE_QUALQUER,
        pasta_fotos=tmp_path / "fotos",
        _env_file=None,
        **valores,
    )


def test_a_configuracao_escolhe_onde_a_ancora_fica(tmp_path: Path) -> None:
    s3 = {
        "fotos_s3_endereco": "https://s3.sa-east-1.amazonaws.com",
        "fotos_s3_chave": "chave",
        "fotos_s3_segredo": "segredo",
    }
    with mock_aws():
        no_disco = ancoras.guarda_da_configuracao(_configuracao(tmp_path))
        com_as_fotos = ancoras.guarda_da_configuracao(_configuracao(tmp_path, **s3))
        no_balde = ancoras.guarda_da_configuracao(
            _configuracao(tmp_path, ancoras_s3_balde=BALDE, **s3)
        )

    assert isinstance(no_disco, AncorasNoDisco)
    assert isinstance(com_as_fotos, AncorasNoS3)
    assert (com_as_fotos.balde, com_as_fotos.travar) == ("fotos", False)
    assert isinstance(no_balde, AncorasNoS3)
    assert (no_balde.balde, no_balde.travar) == (BALDE, True)


def test_o_balde_das_ancoras_pede_o_s3(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ancoras_s3_balde"):
        _configuracao(tmp_path, ancoras_s3_balde=BALDE)

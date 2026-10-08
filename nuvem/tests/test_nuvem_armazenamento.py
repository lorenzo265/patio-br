"""Armazenamento local das fotos (SDD 3.2, D-22): endereço temporário, foto que não se edita."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from nuvem.armazenamento import (
    ArmazenamentoLocal,
    EnderecoRecusadoError,
    FotoDiferenteError,
    FotoInvalidaError,
    RefInvalidoError,
    validar_ref,
)
from nuvem.cifra import Cifra

pytestmark = pytest.mark.integracao  # grava no disco

AGORA = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)
JPEG = b"\xff\xd8\xff\xe0" + b"foto-inventada" * 10 + b"\xff\xd9"
PREFIXO = "/api/borda/fotos/envio/"


@pytest.fixture
def armazenamento(tmp_path: Path) -> ArmazenamentoLocal:
    return ArmazenamentoLocal(tmp_path, Cifra(SecretStr(Fernet.generate_key().decode())))


def _codigo(armazenamento: ArmazenamentoLocal, caixa_id: int, ref: str) -> str:
    endereco = armazenamento.endereco_de_envio(caixa_id, ref, agora=AGORA)
    assert endereco.startswith(PREFIXO)
    return endereco.removeprefix(PREFIXO)


def test_foto_enviada_pelo_endereco_fica_guardada(armazenamento: ArmazenamentoLocal) -> None:
    codigo = _codigo(armazenamento, 1, "2026/10/05/p1-placa.jpg")

    assert armazenamento.receber(codigo, JPEG, agora=AGORA) is True
    assert armazenamento.ler(1, "2026/10/05/p1-placa.jpg") == JPEG


def test_endereco_vale_15_minutos(armazenamento: ArmazenamentoLocal) -> None:
    codigo = _codigo(armazenamento, 1, "p1.jpg")

    assert armazenamento.receber(codigo, JPEG, agora=AGORA + timedelta(minutes=14, seconds=59))


def test_endereco_vencido_e_recusado(armazenamento: ArmazenamentoLocal) -> None:
    codigo = _codigo(armazenamento, 1, "p1.jpg")

    with pytest.raises(EnderecoRecusadoError):
        armazenamento.receber(codigo, JPEG, agora=AGORA + timedelta(minutes=16))


def test_endereco_adulterado_e_recusado(armazenamento: ArmazenamentoLocal) -> None:
    codigo = _codigo(armazenamento, 1, "p1.jpg")
    adulterado = codigo[:-4] + ("AAAA" if not codigo.endswith("AAAA") else "BBBB")

    with pytest.raises(EnderecoRecusadoError):
        armazenamento.receber(adulterado, JPEG, agora=AGORA)


def test_reenviar_a_mesma_foto_nao_muda_nada(armazenamento: ArmazenamentoLocal) -> None:
    armazenamento.receber(_codigo(armazenamento, 1, "p1.jpg"), JPEG, agora=AGORA)

    assert armazenamento.receber(_codigo(armazenamento, 1, "p1.jpg"), JPEG, agora=AGORA) is False


def test_foto_diferente_no_mesmo_ref_e_recusada(armazenamento: ArmazenamentoLocal) -> None:
    # A foto é prova (SDD 5.5): não se troca depois de guardada.
    armazenamento.receber(_codigo(armazenamento, 1, "p1.jpg"), JPEG, agora=AGORA)
    outra = JPEG.replace(b"inventada", b"trocada!!")

    with pytest.raises(FotoDiferenteError):
        armazenamento.receber(_codigo(armazenamento, 1, "p1.jpg"), outra, agora=AGORA)
    assert armazenamento.ler(1, "p1.jpg") == JPEG


@pytest.mark.parametrize(
    ("primeiro", "depois"), [("a.jpg", "a.jpg/b.jpg"), ("c/d.jpg", "c")], ids=["foto", "pasta"]
)
def test_ref_que_esbarra_na_pasta_de_outro_e_recusado(
    armazenamento: ArmazenamentoLocal, primeiro: str, depois: str
) -> None:
    # Como uma foto diferente no mesmo ref: 409, e a caixa não fica tentando de novo.
    armazenamento.receber(_codigo(armazenamento, 1, primeiro), JPEG, agora=AGORA)

    with pytest.raises(FotoDiferenteError):
        armazenamento.receber(_codigo(armazenamento, 1, depois), JPEG, agora=AGORA)
    assert armazenamento.ler(1, primeiro) == JPEG


def test_uma_caixa_nao_alcanca_a_foto_de_outra(armazenamento: ArmazenamentoLocal) -> None:
    armazenamento.receber(_codigo(armazenamento, 1, "p1.jpg"), JPEG, agora=AGORA)

    assert armazenamento.ler(2, "p1.jpg") is None


def test_so_aceita_jpeg(armazenamento: ArmazenamentoLocal) -> None:
    with pytest.raises(FotoInvalidaError, match="JPEG"):
        armazenamento.receber(_codigo(armazenamento, 1, "p1.jpg"), b"\x89PNG....", agora=AGORA)


def test_foto_acima_de_2_mb_e_recusada(armazenamento: ArmazenamentoLocal) -> None:
    grande = JPEG[:4] + b"x" * (2 * 1024 * 1024)

    with pytest.raises(FotoInvalidaError, match="2 MB"):
        armazenamento.receber(_codigo(armazenamento, 1, "p1.jpg"), grande, agora=AGORA)


@pytest.mark.parametrize(
    "ref",
    [
        "../fora.jpg",
        "a/../../fora.jpg",
        "/raiz.jpg",
        "com espaco.jpg",
        "",
        "a" * 201,
        "x//y.jpg",
        ".../y.jpg",
        "foto.",
        "NUL",
        "a/con.jpg",
        "Lpt1.jpg",
    ],
    ids=[
        "sobe",
        "sobe no meio",
        "absoluto",
        "espaço",
        "vazio",
        "longo",
        "barra dupla",
        "só pontos",
        "ponto no fim",
        "NUL do Windows",
        "CON com extensão",
        "LPT1 em minúsculas",
    ],
)
def test_ref_que_sairia_da_pasta_ou_foge_da_regra_e_recusado(ref: str) -> None:
    with pytest.raises(RefInvalidoError):
        validar_ref(ref)


def test_ref_com_pastas_e_ponto_vale() -> None:
    validar_ref("2026/10/05/6f1c2c9e-8a0b-4c55-9b1e-2f0a3d4e5b6c_placa-1.jpg")


def test_nao_le_ref_invalido(armazenamento: ArmazenamentoLocal) -> None:
    with pytest.raises(RefInvalidoError):
        armazenamento.ler(1, "../../etc/passwd")


def test_apagar_uma_foto(armazenamento: ArmazenamentoLocal) -> None:
    # O prazo de guarda (D-70): a foto vencida sai; a de outra caixa, não.
    armazenamento.guardar(1, "p/1.jpg", JPEG)
    armazenamento.guardar(2, "p/1.jpg", JPEG)

    assert armazenamento.apagar(1, "p/1.jpg") is True
    assert armazenamento.apagar(1, "p/1.jpg") is False

    assert armazenamento.ler(1, "p/1.jpg") is None
    assert armazenamento.ler(2, "p/1.jpg") == JPEG

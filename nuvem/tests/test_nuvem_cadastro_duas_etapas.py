"""O código do app autenticador (SDD 8.2, D-60): o TOTP da RFC 6238, sem banco."""

import base64
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from nuvem.cadastro import duas_etapas

SEGREDO_DA_RFC = base64.b32encode(b"12345678901234567890").decode()
"""O segredo dos exemplos da RFC 6238 (apêndice B), em base32, como o app recebe."""


def _momento(segundos: int) -> datetime:
    return datetime.fromtimestamp(segundos, UTC)


@pytest.mark.parametrize(
    ("segundos", "codigo"),
    [
        # Os exemplos SHA-1 da RFC 6238 têm 8 números; os 6 do app são os 6 últimos.
        (59, "287082"),
        (1111111109, "081804"),
        (1111111111, "050471"),
        (1234567890, "005924"),
        (2000000000, "279037"),
        (20000000000, "353130"),
    ],
)
def test_o_codigo_bate_com_os_exemplos_da_rfc(segundos: int, codigo: str) -> None:
    passo = duas_etapas.passo_de(_momento(segundos))

    assert duas_etapas.codigo_do_passo(SEGREDO_DA_RFC, passo) == codigo


def test_o_passo_muda_a_cada_30_segundos() -> None:
    assert duas_etapas.passo_de(_momento(0)) == 0
    assert duas_etapas.passo_de(_momento(29)) == 0
    assert duas_etapas.passo_de(_momento(30)) == 1


def test_vale_o_codigo_de_agora_e_devolve_o_passo() -> None:
    agora = _momento(1111111111)

    passo = duas_etapas.conferir(SEGREDO_DA_RFC, "050471", agora=agora, ultimo_passo=None)

    assert passo == duas_etapas.passo_de(agora)


def test_vale_o_codigo_do_intervalo_anterior_e_do_seguinte() -> None:
    agora = _momento(1111111111)
    passo = duas_etapas.passo_de(agora)
    anterior = duas_etapas.codigo_do_passo(SEGREDO_DA_RFC, passo - 1)
    seguinte = duas_etapas.codigo_do_passo(SEGREDO_DA_RFC, passo + 1)

    assert duas_etapas.conferir(SEGREDO_DA_RFC, anterior, agora=agora, ultimo_passo=None) == (
        passo - 1
    )
    assert duas_etapas.conferir(SEGREDO_DA_RFC, seguinte, agora=agora, ultimo_passo=None) == (
        passo + 1
    )


def test_nao_vale_o_codigo_de_dois_intervalos_atras() -> None:
    agora = _momento(1111111111)
    velho = duas_etapas.codigo_do_passo(SEGREDO_DA_RFC, duas_etapas.passo_de(agora) - 2)

    assert duas_etapas.conferir(SEGREDO_DA_RFC, velho, agora=agora, ultimo_passo=None) is None


def test_o_codigo_ja_usado_nao_vale_de_novo() -> None:
    agora = _momento(1111111111)
    passo = duas_etapas.passo_de(agora)

    assert duas_etapas.conferir(SEGREDO_DA_RFC, "050471", agora=agora, ultimo_passo=passo) is None
    # Nem o do intervalo anterior, depois de usado o de agora.
    anterior = duas_etapas.codigo_do_passo(SEGREDO_DA_RFC, passo - 1)
    assert duas_etapas.conferir(SEGREDO_DA_RFC, anterior, agora=agora, ultimo_passo=passo) is None


def test_codigo_errado_ou_mal_escrito_nao_vale() -> None:
    agora = _momento(1111111111)

    for digitado in ("050472", "", "05047", "0504711", "abcdef", "05 04 7a"):
        assert (
            duas_etapas.conferir(SEGREDO_DA_RFC, digitado, agora=agora, ultimo_passo=None) is None
        )


def test_o_codigo_com_espaco_no_meio_vale() -> None:
    agora = _momento(1111111111)

    passo = duas_etapas.conferir(SEGREDO_DA_RFC, " 050 471 ", agora=agora, ultimo_passo=None)

    assert passo == duas_etapas.passo_de(agora)


def test_segredo_novo_tem_160_bits_em_base32_e_muda_a_cada_vez() -> None:
    um, outro = duas_etapas.novo_segredo(), duas_etapas.novo_segredo()

    assert um != outro
    assert re.fullmatch(r"[A-Z2-7]{32}", um)
    assert len(base64.b32decode(um)) == 20


def test_o_endereco_do_app_leva_o_emissor_a_conta_e_o_segredo() -> None:
    endereco = duas_etapas.endereco_do_app(SEGREDO_DA_RFC, "gestor@empresa.example")

    partes = urlsplit(endereco)
    assert (partes.scheme, partes.netloc) == ("otpauth", "totp")
    assert partes.path == "/patio-br:gestor%40empresa.example"
    assert parse_qs(partes.query) == {
        "secret": [SEGREDO_DA_RFC],
        "issuer": ["patio-br"],
        "algorithm": ["SHA1"],
        "digits": ["6"],
        "period": ["30"],
    }


def test_o_qr_sai_em_svg() -> None:
    svg = duas_etapas.qr_em_svg(duas_etapas.endereco_do_app(SEGREDO_DA_RFC, "a@b.example"))

    assert svg.startswith("<svg")
    assert "</svg>" in svg


def test_dez_codigos_de_recuperacao_diferentes_e_faceis_de_digitar() -> None:
    codigos = duas_etapas.novos_codigos_de_recuperacao()

    assert len(codigos) == duas_etapas.CODIGOS_DE_RECUPERACAO == 10
    assert len(set(codigos)) == 10
    for codigo in codigos:
        # Sem 0, o, 1, l e i, que se confundem ao copiar à mão.
        assert re.fullmatch(r"[a-hjkmnp-z2-9]{4}-[a-hjkmnp-z2-9]{4}", codigo)


def test_o_codigo_de_recuperacao_digitado_de_outro_jeito_vale_igual() -> None:
    assert duas_etapas.normalizar_recuperacao(" ABCD efgh ") == "abcd-efgh"
    assert duas_etapas.normalizar_recuperacao("abcdefgh") == "abcd-efgh"
    assert duas_etapas.normalizar_recuperacao("abcd-efgh") == "abcd-efgh"
    assert duas_etapas.normalizar_recuperacao("abc") is None
    assert duas_etapas.normalizar_recuperacao("123456") is None


def test_a_sessao_pela_metade_vale_10_minutos() -> None:
    assert timedelta(minutes=10) == duas_etapas.VALIDADE_DA_SESSAO_PELA_METADE

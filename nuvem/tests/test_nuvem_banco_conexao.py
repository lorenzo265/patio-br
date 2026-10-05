"""Como a nuvem se liga ao banco (D-56): sem pool na função da Vercel e com SSL no Supabase."""

import ssl
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from pydantic import ValidationError
from sqlalchemy.pool import NullPool, QueuePool

from nuvem import banco
from nuvem.config import Configuracao

URL = "postgresql+pg8000://patio:senha@banco:5432/patio"
CHAVE = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="


def _configuracao(**valores: Any) -> Configuracao:
    return Configuracao(url_banco=URL, chave_cifra=CHAVE, _env_file=None, **valores)


def _certificado_inventado() -> str:
    """Um certificado de autoridade feito agora, para o teste (não é de ninguém)."""
    chave = ec.generate_private_key(ec.SECP256R1())
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Autoridade de teste")])
    agora = datetime.now(UTC)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora)
        .not_valid_after(agora + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(chave, hashes.SHA256())
    )
    return certificado.public_bytes(serialization.Encoding.PEM).decode()


def test_por_padrao_o_motor_guarda_conexoes_e_nao_usa_ssl() -> None:
    configuracao = _configuracao()

    assert isinstance(banco.motor_da_configuracao(configuracao).pool, QueuePool)
    assert banco.contexto_ssl(configuracao) is None


def test_na_funcao_da_vercel_o_motor_nao_guarda_conexoes() -> None:
    motor = banco.motor_da_configuracao(_configuracao(banco_sem_pool=True))

    assert isinstance(motor.pool, NullPool)


def test_com_ssl_confere_o_certificado_e_o_nome_do_servidor() -> None:
    contexto = banco.contexto_ssl(_configuracao(banco_ssl=True))

    assert contexto is not None
    assert (contexto.verify_mode, contexto.check_hostname) == (ssl.CERT_REQUIRED, True)


def test_com_o_certificado_do_supabase_confia_nele() -> None:
    contexto = banco.contexto_ssl(_configuracao(banco_ssl=True, banco_ca=_certificado_inventado()))

    assert contexto is not None
    assert any(
        ("commonName", "Autoridade de teste") in campo
        for certificado in contexto.get_ca_certs()
        for campo in certificado["subject"]
    )


def test_o_motor_leva_o_ssl_para_a_conexao(monkeypatch: pytest.MonkeyPatch) -> None:
    recebido: dict[str, Any] = {}

    def criar(url: str, **argumentos: Any) -> object:
        recebido.update(argumentos)
        return object()

    monkeypatch.setattr(banco, "create_engine", criar)

    banco.motor_da_configuracao(_configuracao(banco_ssl=True))

    assert isinstance(recebido["connect_args"]["ssl_context"], ssl.SSLContext)


def test_certificado_que_nao_e_pem_impede_a_nuvem_de_iniciar() -> None:
    with pytest.raises(ValidationError, match="banco_ca"):
        _configuracao(banco_ssl=True, banco_ca="isto não é um certificado")

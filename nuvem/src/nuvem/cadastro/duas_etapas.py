"""O código do app autenticador da verificação em duas etapas (SDD 8.2, D-60).

O app do celular e a nuvem guardam o mesmo segredo. A cada 30 segundos, os dois calculam o
mesmo código de 6 números: o HMAC-SHA1 do segredo com o número do intervalo, cortado como a
RFC 4226 manda. É o TOTP da RFC 6238, o que todo app autenticador usa. A conta é curta e fica
aqui, conferida com os exemplos da própria RFC, sem biblioteca a mais.

Aqui fica só a conta, sem banco; o login com a verificação está em ``nuvem.cadastro.login``.
"""

import base64
import hashlib
import hmac
import re
import secrets
import struct
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

import segno

PASSO = timedelta(seconds=30)
DIGITOS = 6
TOLERANCIA = 1
"""Quantos intervalos antes e depois de agora valem: o relógio do celular erra um pouco."""
EMISSOR = "patio-br"
"""O nome que o app mostra ao lado da conta; muda com o nome do produto (``[ABERTO-01]``)."""

VALIDADE_DA_SESSAO_PELA_METADE = timedelta(minutes=10)
"""Quanto tempo a sessão aberta pela senha espera o código do app (ou a ligação)."""

CODIGOS_DE_RECUPERACAO = 10
LETRAS_DA_RECUPERACAO = "abcdefghjkmnpqrstuvwxyz23456789"
"""Sem 0, o, 1, l e i, que se confundem ao copiar à mão."""
_RECUPERACAO = re.compile(rf"[{LETRAS_DA_RECUPERACAO}]{{8}}")
_CODIGO = re.compile(rf"\d{{{DIGITOS}}}")


def novo_segredo() -> str:
    """Um segredo novo de 160 bits, em base32 sem ``=``, como os apps recebem."""
    return base64.b32encode(secrets.token_bytes(20)).decode()


def passo_de(momento: datetime) -> int:
    """O número do intervalo de 30 segundos em que o momento cai, contado desde 1970."""
    return int(momento.timestamp()) // int(PASSO.total_seconds())


def codigo_do_passo(segredo: str, passo: int) -> str:
    """O código de 6 números do intervalo (RFC 4226, seção 5.3)."""
    chave = base64.b32decode(segredo + "=" * (-len(segredo) % 8))
    resumo = hmac.new(chave, struct.pack(">Q", passo), hashlib.sha1).digest()
    inicio = resumo[-1] & 0x0F
    numero = struct.unpack(">I", resumo[inicio : inicio + 4])[0] & 0x7FFFFFFF
    return str(numero % 10**DIGITOS).zfill(DIGITOS)


def conferir(
    segredo: str, digitado: str, *, agora: datetime, ultimo_passo: int | None
) -> int | None:
    """Confere o código digitado.

    Args:
        ultimo_passo: o intervalo do último código aceito desta conta; ele e os anteriores não
            valem mais (um código já usado não abre outra sessão).

    Returns:
        O intervalo do código, para guardar como o último aceito, ou ``None`` se não vale.
    """
    digitado = "".join(digitado.split())
    if not _CODIGO.fullmatch(digitado):
        return None
    atual = passo_de(agora)
    for passo in range(atual - TOLERANCIA, atual + TOLERANCIA + 1):
        if ultimo_passo is not None and passo <= ultimo_passo:
            continue
        if hmac.compare_digest(codigo_do_passo(segredo, passo), digitado):
            return passo
    return None


def endereco_do_app(segredo: str, conta: str) -> str:
    """O endereço ``otpauth://`` que o QR leva ao app, com o emissor e a conta (o e-mail)."""
    rotulo = quote(f"{EMISSOR}:{conta}", safe=":")
    parametros = urlencode(
        {
            "secret": segredo,
            "issuer": EMISSOR,
            "algorithm": "SHA1",
            "digits": DIGITOS,
            "period": int(PASSO.total_seconds()),
        }
    )
    return f"otpauth://totp/{rotulo}?{parametros}"


def qr_em_svg(texto: str) -> str:
    """O QR do texto, em SVG, para pôr direto na tela (sem arquivo e sem outro servidor)."""
    return str(segno.make_qr(texto, error="m").svg_inline(scale=5, border=2))


def novos_codigos_de_recuperacao() -> list[str]:
    """Os códigos de recuperação, no formato ``abcd-efgh`` (cerca de 40 bits cada)."""
    codigos: set[str] = set()
    while len(codigos) < CODIGOS_DE_RECUPERACAO:
        letras = "".join(secrets.choice(LETRAS_DA_RECUPERACAO) for _ in range(8))
        codigos.add(f"{letras[:4]}-{letras[4:]}")
    return sorted(codigos)


def normalizar_recuperacao(digitado: str) -> str | None:
    """O código de recuperação como foi gerado, ou ``None`` se não tem o formato.

    Aceita maiúsculas, espaços e o traço em qualquer lugar: quem copia à mão erra nisso.
    """
    letras = "".join(digitado.lower().replace("-", "").split())
    if not _RECUPERACAO.fullmatch(letras):
        return None
    return f"{letras[:4]}-{letras[4:]}"

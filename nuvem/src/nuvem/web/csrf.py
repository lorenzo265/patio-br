"""O código anti-CSRF (SDD 8.2, D-55).

Outro site pode fazer o navegador de alguém mandar um formulário para cá, com o cookie da sessão.
Para isso não valer, todo pedido que muda alguma coisa, de quem tem a sessão aberta, leva um
código que outro site não tem como saber: o HMAC do código da sessão com um segredo só da nuvem
(tirado da chave da cifra). Ele muda a cada login, e nada novo se grava no banco.

- **No formulário:** o campo escondido ``_csrf`` (as telas recebem ``csrf`` no contexto).
- **No HTMX:** o cabeçalho ``X-CSRF-Token`` (o ``hx-headers`` do ``<body>``).
- **Ficam de fora** só as rotas em que o cookie não decide quem pede (``ISENTAS``): o login
  (que recusa o envio vindo de outro site), o link da transportadora, o link de senha (D-75), o
  link de demonstração, a
  API da caixa (pela chave), o webhook do WhatsApp (pela assinatura, D-63) e o retorno do SMS
  (pelo segredo no endereço, D-64).
"""

import hashlib
import hmac

from fastapi import Request

from nuvem.cadastro.acesso import COOKIE_DA_SESSAO

CAMPO = "_csrf"
CABECALHO = "X-CSRF-Token"
ISENTAS = (
    "/entrar",
    "/agendar/",
    "/senha/",
    "/demonstracao/link/",
    "/api/borda/",
    "/api/whatsapp",
    "/api/sms/",
)
"""O login e o webhook, exatos; os outros (com a ``/`` no fim), pelo começo do caminho."""
_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})
_FORMULARIOS = ("application/x-www-form-urlencoded", "multipart/form-data")


class CodigoCsrfRecusadoError(Exception):
    """O pedido muda alguma coisa, tem a sessão, e não trouxe o código certo (403)."""


def segredo(chave_cifra: str) -> bytes:
    """O segredo do código, tirado da chave da cifra (só a nuvem tem)."""
    return hmac.new(chave_cifra.encode(), b"anti-csrf", hashlib.sha256).digest()


def codigo(segredo_csrf: bytes, codigo_da_sessao: str) -> str:
    """O código anti-CSRF de uma sessão."""
    return hmac.new(segredo_csrf, codigo_da_sessao.encode(), hashlib.sha256).hexdigest()


def isenta(caminho: str) -> bool:
    """Se a rota fica de fora da conferência (o cookie não decide quem pede nela)."""
    return caminho in ISENTAS or caminho.startswith(tuple(i for i in ISENTAS if i.endswith("/")))


def codigo_do_pedido(request: Request) -> str | None:
    """O código das telas desta sessão, ou ``None`` sem sessão."""
    sessao = request.cookies.get(COOKIE_DA_SESSAO)
    return codigo(request.app.state.segredo_csrf, sessao) if sessao else None


async def conferir(request: Request) -> None:
    """Dependência da aplicação: recusa o pedido que muda alguma coisa sem o código certo.

    Raises:
        CodigoCsrfRecusadoError: com a sessão e sem o código (ou com o de outra sessão).
    """
    if request.method in _SEGUROS or isenta(request.url.path):
        return
    esperado = codigo_do_pedido(request)
    if esperado is None:
        return  # sem sessão, o cookie não dá poder nenhum ao pedido
    enviado: object = request.headers.get(CABECALHO)
    if enviado is None and request.headers.get("content-type", "").startswith(_FORMULARIOS):
        enviado = (await request.form()).get(CAMPO)
    if not isinstance(enviado, str) or not hmac.compare_digest(enviado, esperado):
        raise CodigoCsrfRecusadoError

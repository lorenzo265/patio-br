"""O WhatsApp pela Cloud API da Meta, direto e sem biblioteca dela (SDD 7.5, D-12 e D-63).

- **Mandar:** o modelo aprovado, com as variáveis, por ``POST /<versão>/<número>/messages``; e a
  resposta curta, em texto livre, a quem acabou de mandar uma mensagem.
- **O webhook:** a Meta assina o corpo com o segredo do app (``X-Hub-Signature-256``); aqui se
  confere a assinatura e se lê o aviso (as situações das mensagens e as recebidas).
- **O motorista:** o link ``wa.me`` abre o WhatsApp com a mensagem pronta (D-58), e o texto que
  ele manda diz o que pediu ("AVISOS A<agendamento>", "AVISOS S<site>" ou "SAIR").
"""

import hashlib
import hmac
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote

import httpx

from nuvem.mensagens.canais import Envio, EnvioFalhouError, EnvioRecusadoError, Situacao
from nuvem.mensagens.modelos import Mensagem, ModeloDeMensagem, SituacaoDaMensagem
from nuvem.mensagens.modelos_do_whatsapp import IDIOMA, MODELOS

if TYPE_CHECKING:
    from nuvem.config import Configuracao

VERSAO_PADRAO = "v25.0"
"""A versão da API da Meta (de 02/2026); configurável, porque cada versão vale cerca de 2 anos."""
ENDERECO = "https://graph.facebook.com/{versao}/{numero_id}/messages"
TEMPO_DO_PEDIDO = httpx.Timeout(10.0)

ERROS_PASSAGEIROS = frozenset(
    {1, 2, 4, 17, 190, 80007, 130429, 131000, 131016, 131048, 131056, 133004}
)
"""Os códigos de erro da Meta que passam: o limite de envio, o serviço fora, o token vencido
(até alguém trocar). Os outros (o número sem WhatsApp, o modelo recusado) são definitivos."""

SITUACOES: dict[str, SituacaoDaMensagem] = {
    "sent": "enviada",
    "delivered": "entregue",
    "read": "lida",
    "failed": "falhou",
}
"""A situação que a Meta avisa, no nome daqui."""

_CELULAR_COM_O_9 = re.compile(r"55([1-9]{2})(9\d{8})")
_CELULAR_SEM_O_9 = re.compile(r"55([1-9]{2})([6-9]\d{7})")
_AVISOS = re.compile(r"AVISOS ([AS])(\d{1,12})")
_SAIR = frozenset({"SAIR", "PARAR"})

Pedido = tuple[Literal["agendamento", "site"], int] | tuple[Literal["sair"], None]


@dataclass(frozen=True)
class Recebida:
    """Uma mensagem que alguém mandou ao número do produto."""

    id_no_whatsapp: str
    de: str
    """O número de quem mandou, como o WhatsApp dá (só números)."""
    texto: str
    momento: datetime


class CanalWhatsApp:
    """O canal do WhatsApp: manda os modelos e as respostas pela Cloud API."""

    def __init__(
        self, cliente: httpx.Client, *, versao: str, numero_id: str, token: str, numero: str
    ) -> None:
        """Prepara o canal.

        Args:
            cliente: o cliente HTTP (os testes passam um com a Meta imitada).
            versao: a versão da API (ex.: ``v25.0``).
            numero_id: o id do número do produto na Meta.
            token: o token do usuário de sistema; nunca vai para o registro.
            numero: o número do produto, só números, com o 55 (para os links).
        """
        self._cliente = cliente
        self._endereco = ENDERECO.format(versao=versao, numero_id=numero_id)
        self._token = token
        self._numero = numero

    @property
    def numero(self) -> str:
        """O número do produto, para o link ``wa.me``."""
        return self._numero

    def enviar(self, mensagem: Mensagem) -> Envio:
        """Manda a mensagem pelo modelo dela."""
        return self.enviar_modelo(mensagem.para, mensagem.modelo, mensagem.variaveis or [])

    def enviar_modelo(self, para: str, modelo: ModeloDeMensagem, variaveis: Sequence[str]) -> Envio:
        """Manda um modelo aprovado, com as variáveis na ordem."""
        parametros = [{"type": "text", "text": valor} for valor in variaveis]
        return self._postar(
            {
                "messaging_product": "whatsapp",
                "to": para.removeprefix("+"),
                "type": "template",
                "template": {
                    "name": MODELOS[modelo].nome,
                    "language": {"code": IDIOMA},
                    "components": [{"type": "body", "parameters": parametros}],
                },
            }
        )

    def responder(self, para: str, texto: str) -> Envio:
        """Responde com texto livre (só vale na conversa que o motorista abriu)."""
        return self._postar(
            {
                "messaging_product": "whatsapp",
                "to": para.removeprefix("+"),
                "type": "text",
                "text": {"body": texto},
            }
        )

    def _postar(self, corpo: dict[str, Any]) -> Envio:
        try:
            resposta = self._cliente.post(
                self._endereco,
                json=corpo,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=TEMPO_DO_PEDIDO,
            )
        except httpx.HTTPError as erro:
            raise EnvioFalhouError(f"a Meta não respondeu: {type(erro).__name__}") from erro
        dados = _json(resposta)
        if resposta.status_code >= 500 or resposta.status_code == 429:
            raise EnvioFalhouError(f"a Meta respondeu {resposta.status_code}")
        if resposta.status_code >= 400:
            problema = dados.get("error")
            if not isinstance(problema, dict):
                problema = {}
            codigo, texto = problema.get("code"), str(problema.get("message", ""))
            if codigo in ERROS_PASSAGEIROS:
                raise EnvioFalhouError(f"{codigo}: {texto}")
            raise EnvioRecusadoError(str(codigo), texto)
        try:
            return Envio(id_no_canal=str(dados["messages"][0]["id"]))
        except (KeyError, IndexError, TypeError):
            raise EnvioFalhouError("a Meta respondeu sem o id da mensagem") from None


def _json(resposta: httpx.Response) -> dict[str, Any]:
    try:
        dados = resposta.json()
    except ValueError:
        return {}
    return dados if isinstance(dados, dict) else {}


def assinatura_confere(segredo_do_app: str, corpo: bytes, cabecalho: str | None) -> bool:
    """Se o ``X-Hub-Signature-256`` é o HMAC-SHA256 do corpo com o segredo do app."""
    if not cabecalho or not cabecalho.startswith("sha256="):
        return False
    esperado = hmac.new(segredo_do_app.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(cabecalho.removeprefix("sha256="), esperado)


def celular_do_whatsapp(wa_id: str) -> str | None:
    """O celular do Brasil como o agendamento guarda (``+55``, o DDD e os 9 números).

    O WhatsApp manda alguns números do Brasil sem o 9 do celular: ele volta. Número de fora do
    Brasil, ou que não é de celular, dá ``None``.
    """
    numeros = wa_id.removeprefix("+")
    if achado := _CELULAR_COM_O_9.fullmatch(numeros):
        return f"+55{achado.group(1)}{achado.group(2)}"
    if achado := _CELULAR_SEM_O_9.fullmatch(numeros):
        return f"+55{achado.group(1)}9{achado.group(2)}"
    return None


def link_para_autorizar(numero: str, texto: str) -> str:
    """O link que abre o WhatsApp no número do produto, com o texto já escrito (D-58)."""
    return f"https://wa.me/{numero}?text={quote(texto)}"


def pedido_do_agendamento(agendamento_id: int) -> str:
    """O texto pronto do link do SMS: autoriza a empresa do agendamento."""
    return f"AVISOS A{agendamento_id}"


def pedido_do_site(site_id: int) -> str:
    """O texto pronto do QR da portaria: autoriza a empresa do site."""
    return f"AVISOS S{site_id}"


def o_que_pediu(texto: str) -> Pedido | None:
    """O que o motorista pediu na mensagem, ou ``None`` se não é um pedido."""
    limpo = " ".join(texto.upper().split()).rstrip(".!")
    if limpo in _SAIR:
        return ("sair", None)
    if achado := _AVISOS.fullmatch(limpo):
        tipo: Literal["agendamento", "site"] = "agendamento" if achado.group(1) == "A" else "site"
        return (tipo, int(achado.group(2)))
    return None


def ler_aviso(aviso: dict[str, Any]) -> tuple[list[Situacao], list[Recebida]]:
    """As situações e as mensagens recebidas de um aviso do webhook.

    O que não tem o formato esperado fica de fora, sem derrubar o resto.
    """
    situacoes: list[Situacao] = []
    recebidas: list[Recebida] = []
    for valor in _valores(aviso):
        for item in _lista(valor.get("statuses")):
            if (situacao := _situacao(item)) is not None:
                situacoes.append(situacao)
        for item in _lista(valor.get("messages")):
            if (recebida := _recebida(item)) is not None:
                recebidas.append(recebida)
    return situacoes, recebidas


def _valores(aviso: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for entrada in _lista(aviso.get("entry")):
        for mudanca in _lista(entrada.get("changes")):
            valor = mudanca.get("value")
            if isinstance(valor, dict):
                yield valor


def _lista(valor: object) -> list[dict[str, Any]]:
    if not isinstance(valor, list):
        return []
    return [item for item in valor if isinstance(item, dict)]


def _momento(item: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(item["timestamp"]), UTC)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _situacao(item: dict[str, Any]) -> Situacao | None:
    situacao = SITUACOES.get(str(item.get("status")))
    momento = _momento(item)
    if not item.get("id") or situacao is None or momento is None:
        return None
    erros = _lista(item.get("errors"))
    erro = f"{erros[0].get('code')}: {erros[0].get('title', '')}" if erros else None
    cobranca = item.get("pricing")
    categoria = cobranca.get("category") if isinstance(cobranca, dict) else None
    return Situacao(
        id_no_canal=str(item["id"]),
        situacao=situacao,
        momento=momento,
        erro=erro,
        categoria=str(categoria) if categoria else None,
    )


def _recebida(item: dict[str, Any]) -> Recebida | None:
    momento = _momento(item)
    if not item.get("id") or not item.get("from") or momento is None:
        return None
    texto = item.get("text")
    corpo = texto.get("body") if isinstance(texto, dict) else None
    return Recebida(
        id_no_whatsapp=str(item["id"]),
        de=str(item["from"]),
        texto=str(corpo or ""),
        momento=momento,
    )


def canal_da_configuracao(configuracao: "Configuracao") -> CanalWhatsApp | None:
    """O canal do WhatsApp da configuração, ou ``None`` se ele não está configurado."""
    if (
        configuracao.whatsapp_token is None
        or configuracao.whatsapp_numero_id is None
        or configuracao.whatsapp_numero is None
    ):
        return None
    return CanalWhatsApp(
        httpx.Client(timeout=TEMPO_DO_PEDIDO),
        versao=configuracao.whatsapp_versao,
        numero_id=configuracao.whatsapp_numero_id,
        token=configuracao.whatsapp_token.get_secret_value(),
        numero=configuracao.whatsapp_numero,
    )

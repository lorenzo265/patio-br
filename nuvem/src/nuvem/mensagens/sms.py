"""O SMS de reserva pela Zenvia, direto e sem biblioteca dela (SDD 7.5, D-59 e D-64).

- **Mandar:** ``POST https://api.zenvia.com/v2/channels/sms/messages``, com o token no cabeçalho
  ``X-API-TOKEN`` e o texto pronto da mensagem.
- **O texto:** curto e só com os caracteres do GSM-7, sem acento, para caber num pedaço de 160
  (com um acento do português, o pedaço cai para 70 e o SMS custa o dobro). O da confirmação
  leva o link que abre o WhatsApp com "AVISOS A<agendamento>" (D-58).
- **O retorno:** a Zenvia avisa a entrega com um evento ``MESSAGE_STATUS``.
"""

import unicodedata
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from nuvem.mensagens import whatsapp
from nuvem.mensagens.canais import Envio, EnvioFalhouError, EnvioRecusadoError, Situacao
from nuvem.mensagens.modelos import Mensagem, ModeloDeMensagem, SituacaoDaMensagem

if TYPE_CHECKING:
    from nuvem.config import Configuracao

ENDERECO = "https://api.zenvia.com/v2/channels/sms/messages"
TEMPO_DO_PEDIDO = httpx.Timeout(10.0)
TAMANHO_DO_PEDACO = 160
"""Um pedaço de SMS, só com os caracteres do GSM-7."""
ASSINATURA = "patio-br"
"""Quem manda, no começo do texto; muda com o nome do produto (``[ABERTO-01]``)."""
MENOR_PEDACO_DE_NOME = 8
"""O nome do site (ou da doca) é cortado para caber, mas não fica menor que isto."""

_GSM7 = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
"""A tabela básica do GSM-7 (sem a de extensão, cujos caracteres contam como dois)."""
_TROCAS = str.maketrans(
    {"\u2013": "-", "\u2014": "-", "\u2018": "", "\u2019": "", "\u201c": "", "\u201d": ""}
)
"""Os travessões viram hífen; as aspas curvas somem (não estão no GSM-7)."""

SITUACOES: dict[str, SituacaoDaMensagem] = {
    "SENT": "enviada",
    "DELIVERED": "entregue",
    "NOT_DELIVERED": "falhou",
    "REJECTED": "falhou",
}
"""A situação que a Zenvia avisa, no nome daqui."""


class CanalSMS:
    """O canal de SMS: manda o texto pronto da mensagem pela Zenvia."""

    def __init__(self, cliente: httpx.Client, *, token: str, remetente: str) -> None:
        """Prepara o canal.

        Args:
            cliente: o cliente HTTP (os testes passam um com a Zenvia imitada).
            token: o token da API da Zenvia; nunca vai para o registro.
            remetente: o identificador de quem manda, na conta da Zenvia.
        """
        self._cliente = cliente
        self._token = token
        self._remetente = remetente

    def enviar(self, mensagem: Mensagem) -> Envio:
        """Manda o texto da mensagem para o celular dela."""
        corpo = {
            "from": self._remetente,
            "to": mensagem.para.removeprefix("+"),
            "contents": [{"type": "text", "text": mensagem.texto}],
        }
        try:
            resposta = self._cliente.post(
                ENDERECO, json=corpo, headers={"X-API-TOKEN": self._token}, timeout=TEMPO_DO_PEDIDO
            )
        except httpx.HTTPError as erro:
            raise EnvioFalhouError(f"a Zenvia não respondeu: {type(erro).__name__}") from erro
        dados = _json(resposta)
        if resposta.status_code in (401, 403, 429) or resposta.status_code >= 500:
            # O token errado, o limite e a Zenvia fora passam (ou alguém conserta).
            raise EnvioFalhouError(f"a Zenvia respondeu {resposta.status_code}")
        if resposta.status_code >= 400:
            raise EnvioRecusadoError(str(dados.get("code")), str(dados.get("message", "")))
        if not dados.get("id"):
            raise EnvioFalhouError("a Zenvia respondeu sem o id da mensagem")
        return Envio(id_no_canal=str(dados["id"]))


def _json(resposta: httpx.Response) -> dict[str, Any]:
    try:
        dados = resposta.json()
    except ValueError:
        return {}
    return dados if isinstance(dados, dict) else {}


def para_gsm7(texto: str) -> str:
    """O texto sem acento e só com os caracteres da tabela básica do GSM-7.

    A decomposição separa a letra do acento (``ã`` vira ``a`` e o til), e o acento solto, que
    não está no GSM-7, cai junto com o resto.
    """
    decomposto = unicodedata.normalize("NFKD", texto.translate(_TROCAS))
    return " ".join("".join(letra for letra in decomposto if letra in _GSM7).split())


def texto_do_sms(
    modelo: ModeloDeMensagem,
    variaveis: Sequence[str],
    *,
    agendamento_id: int,
    numero_do_whatsapp: str | None,
) -> str:
    """O texto do SMS de uma mensagem: curto, sem acento e de no máximo 160 caracteres.

    Args:
        variaveis: as mesmas do modelo do WhatsApp (``modelos_do_whatsapp``).
        numero_do_whatsapp: com ele, a confirmação leva o link para autorizar o WhatsApp.
    """
    v = [para_gsm7(valor) for valor in variaveis]
    if modelo == "confirmacao":
        tipo, site, dia, inicio, fim, codigo = v
        if numero_do_whatsapp is None:
            final = "Os avisos da fila chegam por SMS."
        else:
            link = whatsapp.link_para_autorizar(
                numero_do_whatsapp, whatsapp.pedido_do_agendamento(agendamento_id)
            )
            final = f"Avisos pelo WhatsApp: {link}"
        return _caber(
            lambda nome, cod: (
                f"{ASSINATURA}: {tipo} agendada em {nome}, {dia}, {inicio}-{fim} ({cod}). {final}"
            ),
            site,
            codigo,
        )
    if modelo == "na_fila":
        hora, posicao = v
        return (
            f"{ASSINATURA}: chegada as {hora}. Voce esta na fila, posicao {posicao}. "
            "Espere o aviso da doca."
        )
    if modelo == "chamada":
        return _caber(lambda doca, _: f"{ASSINATURA}: sua vez! Siga para a {doca}.", v[0], "")
    return f"{ASSINATURA}: {v[0].lower()} terminada. Pode sair pela portaria. Boa viagem!"


def _caber(montar: Any, nome: str, codigo: str) -> str:
    # Corta o nome (o do site ou da doca) e, se ainda não couber, o código, até caber em 160.
    texto: str = montar(nome, codigo)
    while len(texto) > TAMANHO_DO_PEDACO and len(nome) > MENOR_PEDACO_DE_NOME:
        nome = nome[: max(MENOR_PEDACO_DE_NOME, len(nome) - (len(texto) - TAMANHO_DO_PEDACO))]
        texto = montar(nome.rstrip(), codigo)
    while len(texto) > TAMANHO_DO_PEDACO and codigo:
        codigo = codigo[: len(codigo) - (len(texto) - TAMANHO_DO_PEDACO)]
        texto = montar(nome.rstrip(), codigo)
    return texto


def ler_aviso_do_sms(evento: dict[str, Any]) -> Situacao | None:
    """A situação de uma mensagem nossa, de um evento da Zenvia; ``None`` se não é uma."""
    situacao = evento.get("messageStatus")
    if evento.get("type") != "MESSAGE_STATUS" or not isinstance(situacao, dict):
        return None
    codigo = str(situacao.get("code"))
    traduzida = SITUACOES.get(codigo)
    momento = _momento(situacao.get("timestamp") or evento.get("timestamp"))
    if not evento.get("messageId") or traduzida is None or momento is None:
        return None
    erro = None
    if traduzida == "falhou":
        erro = f"{codigo}: {situacao.get('description', '')}".strip()
    return Situacao(
        id_no_canal=str(evento["messageId"]), situacao=traduzida, momento=momento, erro=erro
    )


def _momento(texto: object) -> datetime | None:
    if not isinstance(texto, str):
        return None
    try:
        momento = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return momento if momento.tzinfo is not None else None


def canal_da_configuracao(configuracao: "Configuracao") -> CanalSMS | None:
    """O canal de SMS da configuração, ou ``None`` se ele não está configurado."""
    if configuracao.sms_token is None or configuracao.sms_remetente is None:
        return None
    return CanalSMS(
        httpx.Client(timeout=TEMPO_DO_PEDIDO),
        token=configuracao.sms_token.get_secret_value(),
        remetente=configuracao.sms_remetente,
    )

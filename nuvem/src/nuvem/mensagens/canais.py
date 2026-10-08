"""Os canais de envio das mensagens ao motorista (SDD 7.5, D-63).

Cada canal (o WhatsApp, o SMS) manda uma mensagem e devolve o id dela no canal. O erro diz se
vale tentar de novo: o **passageiro** (a rede, o limite de envio) faz a tarefa da fila tentar
mais tarde; o **definitivo** (o número sem WhatsApp, o modelo recusado) deixa a mensagem como
falhou. O canal de demonstração não manda nada, e não é um canal de envio.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from nuvem.mensagens.modelos import Mensagem, SituacaoDaMensagem


class EnvioFalhouError(Exception):
    """O envio falhou por um motivo passageiro: a tarefa tenta de novo, mais tarde."""


class EnvioRecusadoError(Exception):
    """O canal recusou a mensagem de vez: tentar de novo não muda nada."""

    def __init__(self, codigo: str, texto: str) -> None:
        """Guarda o código e o texto do erro, como o canal os deu."""
        super().__init__(f"{codigo}: {texto}")
        self.codigo = codigo
        self.texto = texto


@dataclass(frozen=True)
class Situacao:
    """A situação de uma mensagem nossa, como o canal avisou depois do envio."""

    id_no_canal: str
    situacao: "SituacaoDaMensagem"
    momento: datetime
    erro: str | None
    categoria: str | None = None
    """A categoria de cobrança (ex.: ``utility``), quando o canal diz."""


@dataclass(frozen=True)
class Envio:
    """A mensagem aceita pelo canal."""

    id_no_canal: str


class CanalDeEnvio(Protocol):
    """Um canal que manda as mensagens ao motorista."""

    def enviar(self, mensagem: "Mensagem") -> Envio:
        """Manda a mensagem.

        Raises:
            EnvioFalhouError: se vale tentar de novo, mais tarde.
            EnvioRecusadoError: se o canal recusou de vez.
        """
        ...


class CanalDoWhatsApp(CanalDeEnvio, Protocol):
    """O WhatsApp: além de mandar o modelo, manda os alertas, responde a quem escreveu e tem o
    número dos links."""

    @property
    def numero(self) -> str:
        """O número do WhatsApp do produto, só números, com o 55 (para o link ``wa.me``)."""
        ...

    def enviar_alerta(self, para: str, site: str, texto: str) -> Envio:
        """Manda um alerta grave a quem autorizou (o modelo ``patio_alerta``, D-68).

        Raises:
            EnvioFalhouError: se vale tentar de novo.
            EnvioRecusadoError: se o WhatsApp recusou de vez.
        """
        ...

    def responder(self, para: str, texto: str) -> Envio:
        """Responde com texto livre a quem acabou de mandar uma mensagem.

        Raises:
            EnvioFalhouError: se vale tentar de novo.
            EnvioRecusadoError: se o WhatsApp recusou de vez.
        """
        ...


@dataclass(frozen=True)
class Canais:
    """Os canais configurados. Sem o WhatsApp, as mensagens ficam no canal de demonstração."""

    whatsapp: CanalDoWhatsApp | None = None
    sms: CanalDeEnvio | None = None

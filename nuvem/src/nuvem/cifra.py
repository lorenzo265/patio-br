"""Cifra dos segredos que a nuvem precisa guardar e depois ler de volta (ex.: senha da câmera).

Usa Fernet (biblioteca ``cryptography``): AES-128 em modo CBC com HMAC-SHA256, que também
detecta texto alterado. A chave vem da configuração (``PATIO_CHAVE_CIFRA``) e nunca do banco:
quem copia o banco sem a chave não lê os segredos.
"""

from datetime import datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request
from pydantic import SecretStr


class SegredoIlegivelError(Exception):
    """O texto cifrado não abre com esta chave (chave trocada ou texto alterado)."""


class Cifra:
    """Cifra e decifra textos com a chave da configuração."""

    def __init__(self, chave: SecretStr) -> None:
        """Prepara a cifra.

        Raises:
            ValueError: se a chave não for uma chave Fernet (32 bytes em base64 urlsafe).
        """
        try:
            self._fernet = Fernet(chave.get_secret_value())
        except ValueError as erro:
            raise ValueError(
                "chave da cifra inválida: gere outra com Fernet.generate_key()"
            ) from erro

    def cifrar(self, texto: str, *, agora: datetime | None = None) -> str:
        """Devolve o texto cifrado, pronto para gravar no banco ou pôr num endereço.

        Args:
            texto: o que cifrar.
            agora: a hora marcada no cifrado, usada por ``decifrar`` com ``validade`` (o padrão
                é a hora do relógio).
        """
        if agora is None:
            return self._fernet.encrypt(texto.encode()).decode()
        return self._fernet.encrypt_at_time(texto.encode(), int(agora.timestamp())).decode()

    def decifrar(
        self, cifrado: str, *, validade: timedelta | None = None, agora: datetime | None = None
    ) -> str:
        """Devolve o texto original.

        Args:
            cifrado: o que ``cifrar`` devolveu.
            validade: se dada, recusa o cifrado mais velho que isso (ex.: um endereço
                temporário); ``agora`` é a hora da conferência.
            agora: a hora da conferência (o padrão é a hora do relógio).

        Raises:
            SegredoIlegivelError: se o texto não abrir com esta chave, foi alterado ou venceu.
        """
        try:
            if validade is None:
                return self._fernet.decrypt(cifrado.encode()).decode()
            momento = int((agora or datetime.now().astimezone()).timestamp())
            segundos = int(validade.total_seconds())
            return self._fernet.decrypt_at_time(cifrado.encode(), segundos, momento).decode()
        except InvalidToken as erro:
            raise SegredoIlegivelError("o segredo não abre com a chave configurada") from erro


def obter_cifra(request: Request) -> Cifra:
    """Dependência do FastAPI: a cifra da aplicação, com a chave da configuração."""
    cifra: Cifra = request.app.state.cifra
    return cifra

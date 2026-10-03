"""Cifra dos segredos que a nuvem precisa guardar e depois ler de volta (ex.: senha da câmera).

Usa Fernet (biblioteca ``cryptography``): AES-128 em modo CBC com HMAC-SHA256, que também
detecta texto alterado. A chave vem da configuração (``PATIO_CHAVE_CIFRA``) e nunca do banco:
quem copia o banco sem a chave não lê os segredos.
"""

from cryptography.fernet import Fernet, InvalidToken
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

    def cifrar(self, texto: str) -> str:
        """Devolve o texto cifrado, pronto para gravar no banco."""
        return self._fernet.encrypt(texto.encode()).decode()

    def decifrar(self, cifrado: str) -> str:
        """Devolve o texto original.

        Raises:
            SegredoIlegivelError: se o texto não abrir com esta chave.
        """
        try:
            return self._fernet.decrypt(cifrado.encode()).decode()
        except InvalidToken as erro:
            raise SegredoIlegivelError("o segredo não abre com a chave configurada") from erro

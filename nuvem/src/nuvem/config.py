"""Configuração da nuvem, lida do ambiente.

Cada valor vem de uma variável ``PATIO_<NOME>`` ou, no desenvolvimento, do ``.env`` da pasta
atual (o mesmo que o docker compose lê; as variáveis dele, sem o prefixo, são ignoradas aqui).
Valor obrigatório ausente impede a nuvem de iniciar: melhor parar na hora do que rodar errado.
"""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from nuvem.cifra import Cifra

PREFIXO = "PATIO_"

Ambiente = Literal["local", "homologacao", "producao"]


class Configuracao(BaseSettings):
    """Os valores que mudam entre ambientes (local, homologação, produção)."""

    model_config = SettingsConfigDict(env_prefix=PREFIXO, env_file=".env", extra="ignore")

    url_banco: SecretStr
    """Endereço do PostgreSQL, com o driver pg8000 (SDD D-18).

    Ex.: ``postgresql+pg8000://usuario:senha@localhost:15432/patio``. Guardado como segredo para
    a senha não aparecer em registros nem ao imprimir a configuração.
    """

    chave_cifra: SecretStr
    """Chave Fernet que cifra os segredos guardados no banco (ex.: senha da câmera).

    Gere com ``Fernet.generate_key()``. Trocar a chave torna ilegível o que já foi cifrado.
    """

    ambiente: Ambiente = "producao"
    """Onde a nuvem roda: ``local``, ``homologacao`` ou ``producao``.

    Só no ``local`` o cookie da sessão vai sem ``Secure`` (o ambiente local é http://localhost).
    O padrão é ``producao``: esquecer a variável nunca deixa a produção menos segura.
    """

    pasta_fotos: Path = Path("dados/fotos")
    """Pasta das fotos no armazenamento local (``dados/`` fica fora do Git).

    Relativa à pasta onde a nuvem roda; no Docker, ``/app/dados/fotos``, num volume.
    """

    @property
    def cookie_seguro(self) -> bool:
        """Se o cookie da sessão só pode andar por HTTPS (``Secure``)."""
        return self.ambiente != "local"

    @field_validator("chave_cifra")
    @classmethod
    def _chave_valida(cls, chave: SecretStr) -> SecretStr:
        Cifra(chave)  # recusa já na partida uma chave que não serviria
        return chave


class ConfiguracaoInvalidaError(Exception):
    """Falta um valor obrigatório no ambiente, ou um valor não é válido."""


def ler_configuracao() -> Configuracao:
    """Lê a configuração do ambiente e do ``.env`` da pasta atual.

    Raises:
        ConfiguracaoInvalidaError: com as variáveis que faltam ou estão erradas e como resolver.
    """
    try:
        return Configuracao()  # type: ignore[call-arg]  # os valores vêm do ambiente
    except ValidationError as erro:
        variaveis = ", ".join(sorted({f"{PREFIXO}{d['loc'][0]}".upper() for d in erro.errors()}))
        raise ConfiguracaoInvalidaError(
            f"faltam ou estão inválidas: {variaveis}. No desenvolvimento, copie .env.exemplo "
            "para .env na raiz do repositório."
        ) from erro

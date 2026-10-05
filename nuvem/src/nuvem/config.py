"""Configuração da nuvem, lida do ambiente.

Cada valor vem de uma variável ``PATIO_<NOME>`` ou, no desenvolvimento, do ``.env`` da pasta
atual (o mesmo que o docker compose lê; as variáveis dele, sem o prefixo, são ignoradas aqui).
Valor obrigatório ausente impede a nuvem de iniciar: melhor parar na hora do que rodar errado.
"""

from pathlib import Path
from typing import Literal

from pydantic import HttpUrl, SecretStr, ValidationError, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from nuvem.cifra import Cifra

PREFIXO = "PATIO_"

Ambiente = Literal["local", "demonstracao", "homologacao", "producao"]


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
    """Onde a nuvem roda: ``local``, ``demonstracao``, ``homologacao`` ou ``producao``.

    Só no ``local`` o cookie da sessão vai sem ``Secure`` (o ambiente local é http://localhost).
    Só no ``local`` e na ``demonstracao`` existe o dia de demonstração (D-49). O padrão é
    ``producao``: esquecer a variável nunca deixa a produção menos segura.
    """

    pasta_fotos: Path = Path("dados/fotos")
    """Pasta das fotos no armazenamento local (``dados/`` fica fora do Git).

    Relativa à pasta onde a nuvem roda; no Docker, ``/app/dados/fotos``, num volume.
    """

    url_publica: HttpUrl | None = None
    """O endereço pelo qual as caixas alcançam a API, sem caminho (SDD D-28).

    Ex.: ``https://patio-br.example``. Os endereços que a API devolve à caixa (o de envio das
    fotos) partem dele. Sem ele, partem do endereço do pedido, o que basta no ambiente local;
    atrás de um proxy HTTPS, o pedido chega como ``http://``, e a caixa receberia um endereço
    errado. Fora do ambiente local, só ``https://``.
    """

    @property
    def cookie_seguro(self) -> bool:
        """Se o cookie da sessão só pode andar por HTTPS (``Secure``)."""
        return self.ambiente != "local"

    @property
    def tem_demonstracao(self) -> bool:
        """Se o dia de demonstração existe neste ambiente (D-49)."""
        return self.ambiente in ("local", "demonstracao")

    @field_validator("chave_cifra")
    @classmethod
    def _chave_valida(cls, chave: SecretStr) -> SecretStr:
        Cifra(chave)  # recusa já na partida uma chave que não serviria
        return chave

    @field_validator("url_publica", mode="before")
    @classmethod
    def _vazia_e_sem_endereco(cls, url: object) -> object:
        return None if url == "" else url

    @field_validator("url_publica")
    @classmethod
    def _url_publica_valida(cls, url: HttpUrl | None, info: ValidationInfo) -> HttpUrl | None:
        if url is None:
            return None
        if url.path not in (None, "/") or url.query or url.fragment:
            # Os endereços devolvidos à caixa têm caminho próprio (/api/...): um caminho aqui
            # se perderia sem aviso.
            raise ValueError(
                "só esquema, servidor e porta, sem caminho (ex.: https://patio-br.example)"
            )
        if info.data.get("ambiente", "producao") != "local" and url.scheme != "https":
            raise ValueError("fora do ambiente local, o endereço público precisa ser https://")
        return url


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

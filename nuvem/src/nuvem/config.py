"""Configuração da nuvem, lida do ambiente.

Cada valor vem de uma variável ``PATIO_<NOME>`` ou, no desenvolvimento, do ``.env`` da pasta
atual (o mesmo que o docker compose lê; as variáveis dele, sem o prefixo, são ignoradas aqui).
Valor obrigatório ausente impede a nuvem de iniciar: melhor parar na hora do que rodar errado.
"""

import re
import ssl
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    AliasChoices,
    Field,
    HttpUrl,
    SecretStr,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from nuvem.cifra import Cifra

PREFIXO = "PATIO_"

Ambiente = Literal["local", "demonstracao", "homologacao", "producao"]
TAMANHO_DO_SEGREDO = 32
"""O menor segredo de webhook que vai no endereço (ex.: ``secrets.token_urlsafe(32)``)."""


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

    cabecalho_do_ip: str | None = None
    """O cabeçalho de onde vem o endereço de quem pede, atrás de um proxy de confiança (D-55).

    Ex.: ``x-real-ip`` na Vercel, que ela mesma escreve. Sem ele, vale o endereço da conexão:
    sem um proxy que reescreva o cabeçalho, qualquer um o escreveria para fugir do limite de
    login por endereço.
    """

    tique: bool = False
    """Roda o trabalho do worker antes das telas que se atualizam sozinhas (D-56).

    Na Vercel, que não tem processo que fica rodando. Com um worker, fica desligado.
    """

    segredo_do_cron: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("segredo_do_cron", "PATIO_SEGREDO_DO_CRON", "CRON_SECRET"),
    )
    """O segredo que o cron da Vercel manda (``Authorization: Bearer ...``); vem do
    ``CRON_SECRET`` dela. Sem ele, a rota do cron diário não existe."""

    banco_sem_pool: bool = False
    """Uma conexão nova por pedido, sem guardar (na Vercel; quem guarda é o pooler do Supabase)."""

    banco_ssl: bool = False
    """Conexão com o banco por SSL, conferindo o certificado e o nome do servidor (Supabase)."""

    banco_ca: str | None = None
    """O certificado (PEM) da autoridade do banco, quando ela não é pública (o do Supabase)."""

    fotos_s3_endereco: HttpUrl | None = None
    """O endereço S3 das fotos (D-56); sem ele, as fotos ficam na ``pasta_fotos``.

    Ex.: ``https://<projeto>.storage.supabase.co/storage/v1/s3``.
    """

    fotos_s3_regiao: str = "sa-east-1"
    fotos_s3_balde: str = "fotos"
    fotos_s3_chave: SecretStr | None = None
    fotos_s3_segredo: SecretStr | None = None

    ancoras_s3_balde: str | None = None
    """O balde das âncoras da prova, com o Object Lock ligado (D-69), no mesmo S3 das fotos.

    Sem ele, a âncora vai para o armazenamento das fotos, sem trava (a demonstração).
    """

    whatsapp_token: SecretStr | None = None
    """O token do usuário de sistema da Meta, que manda as mensagens (D-63)."""
    whatsapp_numero_id: str | None = None
    """O id do número do produto na Meta (não é o número)."""
    whatsapp_numero: str | None = None
    """O número do produto, só números, com o 55 (ex.: ``5511900000000``): vai no link ``wa.me``."""
    whatsapp_segredo_do_app: SecretStr | None = None
    """O segredo do app da Meta, que assina os avisos do webhook."""
    whatsapp_codigo_do_webhook: SecretStr | None = None
    """O código que a Meta manda ao conferir o webhook (escolhido por nós, ao cadastrá-lo)."""
    whatsapp_versao: str = "v25.0"
    """A versão da API da Meta (de 02/2026)."""

    sms_token: SecretStr | None = None
    """O token da API da Zenvia, que manda os SMS (D-59 e D-64)."""
    sms_remetente: str | None = None
    """Quem manda o SMS, na conta da Zenvia."""
    sms_segredo_do_webhook: SecretStr | None = None
    """O segredo do endereço do retorno da Zenvia (``/api/sms/<segredo>``): ela não assina os
    avisos, e só ela conhece o endereço."""

    @property
    def tem_sms(self) -> bool:
        """Se os SMS saem de verdade (D-64)."""
        return self.sms_token is not None

    @property
    def tem_whatsapp(self) -> bool:
        """Se as mensagens ao motorista saem de verdade (D-63); sem, ficam na demonstração."""
        return self.whatsapp_token is not None

    @property
    def cookie_seguro(self) -> bool:
        """Se o cookie da sessão só pode andar por HTTPS (``Secure``)."""
        return self.ambiente != "local"

    @property
    def exige_duas_etapas(self) -> bool:
        """Se o gestor e a administração passam pela verificação em duas etapas (D-60)."""
        return self.ambiente in ("homologacao", "producao")

    @property
    def tem_demonstracao(self) -> bool:
        """Se o dia de demonstração existe neste ambiente (D-49)."""
        return self.ambiente in ("local", "demonstracao")

    @field_validator("chave_cifra")
    @classmethod
    def _chave_valida(cls, chave: SecretStr) -> SecretStr:
        Cifra(chave)  # recusa já na partida uma chave que não serviria
        return chave

    @field_validator("banco_ca")
    @classmethod
    def _certificado_valido(cls, certificado: str | None) -> str | None:
        if certificado:
            try:
                ssl.create_default_context(cadata=certificado)
            except (ssl.SSLError, ValueError, TypeError) as erro:
                raise ValueError("o certificado do banco precisa ser um PEM válido") from erro
        return certificado or None

    @model_validator(mode="after")
    def _s3_completo(self) -> Self:
        if self.fotos_s3_endereco and not (self.fotos_s3_chave and self.fotos_s3_segredo):
            raise ValueError("fotos_s3: com o endereço, a chave e o segredo são obrigatórios")
        if self.ancoras_s3_balde and not self.fotos_s3_endereco:
            raise ValueError("ancoras_s3_balde: o balde das âncoras fica no S3 das fotos")
        return self

    @model_validator(mode="after")
    def _whatsapp_completo(self) -> Self:
        partes = (
            self.whatsapp_token,
            self.whatsapp_numero_id,
            self.whatsapp_numero,
            self.whatsapp_segredo_do_app,
            self.whatsapp_codigo_do_webhook,
        )
        if any(partes) and not all(partes):
            raise ValueError(
                "whatsapp: o token, o id do número, o número, o segredo do app e o código do "
                "webhook vão juntos"
            )
        if any(partes) and self.ambiente == "demonstracao":
            raise ValueError("whatsapp: a demonstração nunca manda mensagem (D-45)")
        return self

    @model_validator(mode="after")
    def _sms_completo(self) -> Self:
        partes = (self.sms_token, self.sms_remetente, self.sms_segredo_do_webhook)
        if any(partes) and not all(partes):
            raise ValueError("sms: o token, o remetente e o segredo do webhook vão juntos")
        if any(partes) and self.ambiente == "demonstracao":
            raise ValueError("sms: a demonstração nunca manda mensagem (D-45)")
        return self

    @field_validator("sms_segredo_do_webhook")
    @classmethod
    def _segredo_longo(cls, segredo: SecretStr | None) -> SecretStr | None:
        if segredo is not None and len(segredo.get_secret_value()) < TAMANHO_DO_SEGREDO:
            raise ValueError(
                f"sms_segredo_do_webhook: no mínimo {TAMANHO_DO_SEGREDO} caracteres (ele vai "
                "no endereço e protege o retorno)"
            )
        return segredo

    @field_validator("whatsapp_numero")
    @classmethod
    def _numero_do_whatsapp(cls, numero: str | None) -> str | None:
        if numero is not None and not re.fullmatch(r"55\d{10,11}", numero):
            raise ValueError("whatsapp_numero: só números, com o 55 na frente")
        return numero

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

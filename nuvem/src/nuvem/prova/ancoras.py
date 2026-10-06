"""Onde a âncora do dia fica guardada (D-69).

- **No balde das âncoras** (``PATIO_ANCORAS_S3_BALDE``, a produção): cada arquivo vai com o Object
  Lock no modo de conformidade por 5 anos (a guarda da trilha de prova, SDD 8.3). Nem o dono da
  conta apaga ou troca o arquivo antes disso. O balde precisa ter sido criado com a trava ligada.
- **No S3 das fotos, sem trava** (a demonstração, no Supabase, que não tem a trava).
- **Na pasta das fotos**, sem trava (o ambiente local).

Em todos, o arquivo gravado não se troca: gravar o mesmo de novo não faz nada, e gravar outro
conteúdo com o mesmo nome é erro.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from nuvem.armazenamento import cliente_s3
from nuvem.config import Configuracao

PASTA = "ancoras"
TRAVA = timedelta(days=round(365.25 * 5))
"""5 anos: a guarda da trilha de prova (SDD 8.3)."""


class AncoraDiferenteError(Exception):
    """Já existe outra âncora com este nome: a gravada não se troca."""


@dataclass(frozen=True)
class Gravada:
    """Onde a âncora ficou, e se está travada contra apagar e trocar."""

    arquivo: str
    travada: bool


class GuardaDasAncoras(Protocol):
    """Grava e lê os arquivos das âncoras."""

    def gravar(self, nome: str, conteudo: bytes, *, agora: datetime) -> Gravada:
        """Grava a âncora (o mesmo conteúdo de novo não faz nada).

        Raises:
            AncoraDiferenteError: se já houver outro conteúdo com este nome.
        """
        ...

    def ler(self, arquivo: str) -> bytes | None:
        """O arquivo gravado, ou ``None`` se ele não existe."""
        ...


def guarda_da_configuracao(configuracao: Configuracao) -> GuardaDasAncoras:
    """O balde das âncoras, se configurado; senão, o S3 das fotos; senão, a pasta das fotos."""
    if configuracao.fotos_s3_endereco is None:
        return AncorasNoDisco(configuracao.pasta_fotos)
    assert configuracao.fotos_s3_chave and configuracao.fotos_s3_segredo  # a configuração confere
    cliente = cliente_s3(
        endereco=str(configuracao.fotos_s3_endereco),
        regiao=configuracao.fotos_s3_regiao,
        chave=configuracao.fotos_s3_chave.get_secret_value(),
        segredo=configuracao.fotos_s3_segredo.get_secret_value(),
    )
    if configuracao.ancoras_s3_balde:
        return AncorasNoS3(cliente, configuracao.ancoras_s3_balde, travar=True)
    return AncorasNoS3(cliente, configuracao.fotos_s3_balde, travar=False)


class AncorasNoS3:
    """As âncoras num balde S3, em ``ancoras/``; travadas no balde das âncoras."""

    def __init__(self, cliente: Any, balde: str, *, travar: bool) -> None:
        """Prepara a guarda.

        Args:
            cliente: o cliente S3 do boto3.
            balde: o balde (o das âncoras, com o Object Lock ligado, ou o das fotos).
            travar: se cada arquivo vai com o Object Lock (só no balde das âncoras).
        """
        self._cliente = cliente
        self.balde = balde
        self.travar = travar

    def gravar(self, nome: str, conteudo: bytes, *, agora: datetime) -> Gravada:
        """Grava só se o arquivo ainda não existe (``If-None-Match``), travado se for o caso."""
        from botocore.exceptions import ClientError

        arquivo = f"{PASTA}/{nome}"
        trava: dict[str, Any] = {}
        if self.travar:
            trava = {"ObjectLockMode": "COMPLIANCE", "ObjectLockRetainUntilDate": agora + TRAVA}
        try:
            self._cliente.put_object(
                Bucket=self.balde,
                Key=arquivo,
                Body=conteudo,
                ContentType="application/json",
                ChecksumAlgorithm="SHA256",
                IfNoneMatch="*",
                **trava,
            )
        except ClientError as erro:
            if erro.response.get("Error", {}).get("Code") not in ("PreconditionFailed", "412"):
                raise
            if self.ler(arquivo) != conteudo:
                raise AncoraDiferenteError(arquivo) from erro
        return Gravada(arquivo, travada=self.travar)

    def ler(self, arquivo: str) -> bytes | None:
        """O arquivo gravado, ou ``None`` se ele não existe."""
        from botocore.exceptions import ClientError

        try:
            resposta = self._cliente.get_object(Bucket=self.balde, Key=arquivo)
        except ClientError as erro:
            if erro.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        conteudo: bytes = resposta["Body"].read()
        return conteudo


class AncorasNoDisco:
    """As âncoras numa pasta (``<pasta das fotos>/ancoras``), sem trava."""

    def __init__(self, pasta: Path) -> None:
        """Prepara a guarda na pasta dada (a das fotos)."""
        self._pasta = pasta

    def gravar(self, nome: str, conteudo: bytes, *, agora: datetime) -> Gravada:
        """Grava só se o arquivo ainda não existe; o mesmo conteúdo de novo não faz nada."""
        arquivo = f"{PASTA}/{nome}"
        caminho = self._pasta / arquivo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        parcial = caminho.with_name(f"{caminho.name}.{uuid4().hex}.parcial")
        parcial.write_bytes(conteudo)
        try:
            # O link só é criado se o destino não existir: a gravada não se troca.
            os.link(parcial, caminho)
        except FileExistsError:
            if caminho.read_bytes() != conteudo:
                raise AncoraDiferenteError(arquivo) from None
        finally:
            parcial.unlink()
        return Gravada(arquivo, travada=False)

    def ler(self, arquivo: str) -> bytes | None:
        """O arquivo gravado, ou ``None`` se ele não existe."""
        caminho = self._pasta / arquivo
        return caminho.read_bytes() if caminho.is_file() else None

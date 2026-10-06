"""Onde as cópias do banco ficam (D-74): o balde das cópias, no mesmo S3 das fotos.

O arquivo vai do ``pg_dump`` para o balde enquanto é lido, sem passar pelo disco; o resumo e o
tamanho saem no caminho.
"""

import hashlib
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from nuvem.armazenamento import cliente_s3
from nuvem.config import Configuracao


class Legivel(Protocol):
    """Qualquer coisa de onde se leem bytes (o ``pg_dump``, o arquivo no balde)."""

    def read(self, tamanho: int = -1, /) -> bytes:
        """Até ``tamanho`` bytes (``b""`` no fim)."""
        ...


class LeitorComResumo:
    """Lê de outro leitor e conta o tamanho e o resumo (SHA-256) do que passou."""

    def __init__(self, leitor: Legivel) -> None:
        """Prepara a leitura de ``leitor``."""
        self._leitor = leitor
        self._resumo = hashlib.sha256()
        self.tamanho = 0

    def read(self, tamanho: int = -1, /) -> bytes:
        """Lê e conta."""
        pedaco = self._leitor.read(tamanho)
        self._resumo.update(pedaco)
        self.tamanho += len(pedaco)
        return pedaco

    def readable(self) -> bool:
        """Sim (o boto3 pergunta antes de mandar)."""
        return True

    @property
    def resumo(self) -> str:
        """O SHA-256 do que já passou, em hexadecimal."""
        return self._resumo.hexdigest()


@dataclass(frozen=True)
class Gravada:
    """O tamanho e o resumo da cópia gravada."""

    tamanho: int
    resumo: str


class GuardaDasCopias(Protocol):
    """Grava, abre e apaga os arquivos das cópias."""

    def gravar(self, nome: str, leitor: Legivel) -> Gravada:
        """Grava tudo o que ``leitor`` der, com o nome dado."""
        ...

    def abrir(self, nome: str) -> AbstractContextManager[Legivel]:
        """O arquivo gravado, para ler do começo ao fim."""
        ...

    def apagar(self, nome: str) -> None:
        """Apaga o arquivo (se não existe, não faz nada)."""
        ...


class CopiasNoS3:
    """As cópias no balde das cópias (privado e cifrado; o guia da produção diz como criar)."""

    def __init__(self, cliente: Any, balde: str) -> None:
        """Usa o cliente S3 dado (o mesmo endereço e a mesma chave das fotos)."""
        self._cliente = cliente
        self._balde = balde

    def gravar(self, nome: str, leitor: Legivel) -> Gravada:
        """Manda ao balde enquanto lê (em partes de 8 MB, se for grande)."""
        com_resumo = LeitorComResumo(leitor)
        self._cliente.upload_fileobj(com_resumo, self._balde, nome)
        return Gravada(com_resumo.tamanho, com_resumo.resumo)

    @contextmanager
    def abrir(self, nome: str) -> Iterator[Legivel]:
        """Lê do balde enquanto quem pediu consome."""
        corpo = self._cliente.get_object(Bucket=self._balde, Key=nome)["Body"]
        try:
            yield corpo
        finally:
            corpo.close()

    def apagar(self, nome: str) -> None:
        """Apaga do balde."""
        self._cliente.delete_object(Bucket=self._balde, Key=nome)


def guarda_das_copias_da_configuracao(configuracao: Configuracao) -> GuardaDasCopias | None:
    """O balde das cópias, se configurado (``PATIO_COPIAS_S3_BALDE``); senão, nenhum."""
    if configuracao.copias_s3_balde is None:
        return None
    # A configuração confere que o balde das cópias vem com o S3 das fotos completo.
    assert configuracao.fotos_s3_endereco and configuracao.fotos_s3_chave
    assert configuracao.fotos_s3_segredo
    cliente = cliente_s3(
        endereco=str(configuracao.fotos_s3_endereco),
        regiao=configuracao.fotos_s3_regiao,
        chave=configuracao.fotos_s3_chave.get_secret_value(),
        segredo=configuracao.fotos_s3_segredo.get_secret_value(),
    )
    return CopiasNoS3(cliente, configuracao.copias_s3_balde)

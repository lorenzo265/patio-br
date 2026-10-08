"""Onde ficam as cópias dos recortes da base de treino (D-71).

Uma pasta à parte (``treino/``) no mesmo armazenamento das fotos: no disco, ou no S3. Fora da
guarda das fotos (90 dias): a cópia vale enquanto valer a autorização do contrato. Cada empresa
tem a sua pasta, que se apaga inteira quando ela revoga.
"""

import shutil
from pathlib import Path
from typing import Any, Protocol

from nuvem.armazenamento import cliente_s3
from nuvem.config import Configuracao

PASTA = "treino"


class GuardaDoTreino(Protocol):
    """Grava, lê e apaga as cópias dos recortes."""

    def gravar(self, empresa_id: int, nome: str, conteudo: bytes) -> str:
        """Grava a cópia (troca a que houver com o mesmo nome) e devolve onde ficou."""
        ...

    def ler(self, arquivo: str) -> bytes | None:
        """A cópia, ou ``None`` se ela não existe."""
        ...

    def apagar_da_empresa(self, empresa_id: int) -> None:
        """Apaga todas as cópias da empresa."""
        ...


def guarda_do_treino_da_configuracao(configuracao: Configuracao) -> GuardaDoTreino:
    """O S3 das fotos, se configurado; senão, a pasta das fotos."""
    if configuracao.fotos_s3_endereco is None:
        return TreinoNoDisco(configuracao.pasta_fotos)
    assert configuracao.fotos_s3_chave and configuracao.fotos_s3_segredo  # a configuração confere
    cliente = cliente_s3(
        endereco=str(configuracao.fotos_s3_endereco),
        regiao=configuracao.fotos_s3_regiao,
        chave=configuracao.fotos_s3_chave.get_secret_value(),
        segredo=configuracao.fotos_s3_segredo.get_secret_value(),
    )
    return TreinoNoS3(cliente, configuracao.fotos_s3_balde)


def _arquivo(empresa_id: int, nome: str) -> str:
    return f"{PASTA}/empresa-{empresa_id}/{nome}"


class TreinoNoDisco:
    """As cópias numa pasta (``<pasta das fotos>/treino``)."""

    def __init__(self, pasta: Path) -> None:
        """Prepara a guarda na pasta dada (a das fotos)."""
        self._pasta = pasta

    def gravar(self, empresa_id: int, nome: str, conteudo: bytes) -> str:
        """Grava a cópia e devolve onde ficou."""
        arquivo = _arquivo(empresa_id, nome)
        caminho = self._pasta / arquivo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(conteudo)
        return arquivo

    def ler(self, arquivo: str) -> bytes | None:
        """A cópia, ou ``None`` se ela não existe."""
        caminho = self._pasta / arquivo
        return caminho.read_bytes() if caminho.is_file() else None

    def apagar_da_empresa(self, empresa_id: int) -> None:
        """Apaga a pasta da empresa (se existir)."""
        shutil.rmtree(self._pasta / PASTA / f"empresa-{empresa_id}", ignore_errors=True)


class TreinoNoS3:
    """As cópias no balde das fotos, em ``treino/``."""

    def __init__(self, cliente: Any, balde: str) -> None:
        """Prepara a guarda (o cliente S3 do boto3 e o balde)."""
        self._cliente = cliente
        self._balde = balde

    def gravar(self, empresa_id: int, nome: str, conteudo: bytes) -> str:
        """Grava a cópia e devolve onde ficou."""
        arquivo = _arquivo(empresa_id, nome)
        self._cliente.put_object(
            Bucket=self._balde, Key=arquivo, Body=conteudo, ContentType="image/jpeg"
        )
        return arquivo

    def ler(self, arquivo: str) -> bytes | None:
        """A cópia, ou ``None`` se ela não existe."""
        from botocore.exceptions import ClientError

        try:
            resposta = self._cliente.get_object(Bucket=self._balde, Key=arquivo)
        except ClientError as erro:
            if erro.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        conteudo: bytes = resposta["Body"].read()
        return conteudo

    def apagar_da_empresa(self, empresa_id: int) -> None:
        """Apaga as cópias da empresa, de mil em mil (o limite do S3)."""
        paginas = self._cliente.get_paginator("list_objects_v2").paginate(
            Bucket=self._balde, Prefix=f"{PASTA}/empresa-{empresa_id}/"
        )
        for pagina in paginas:
            chaves = [{"Key": objeto["Key"]} for objeto in pagina.get("Contents", [])]
            if chaves:
                self._cliente.delete_objects(
                    Bucket=self._balde, Delete={"Objects": chaves, "Quiet": True}
                )

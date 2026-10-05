"""Armazenamento das fotos das passagens (SDD 3.2, D-22).

A caixa pede um endereço de envio para cada foto e manda a foto direto para ele. O endereço é
temporário (15 minutos) e já autoriza o envio, sem a chave da caixa: é assim que o S3 funciona
(endereço assinado), e é assim que o armazenamento local imita, com um código cifrado no
endereço. A caixa só aprende uma regra: "peça o endereço e envie".

Implementações:

- ``ArmazenamentoLocal``: uma pasta no disco (o ambiente local);
- ``ArmazenamentoS3``: um balde S3, pelo boto3 (D-56): o Supabase Storage na demonstração e a
  AWS no mês 4. O endereço de envio é o endereço assinado do próprio S3.

Cada caixa tem a sua pasta: o ``ref`` que a caixa escolhe nunca alcança a foto de outra.
"""

import json
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from fastapi import Request

from nuvem.cifra import Cifra, SegredoIlegivelError
from nuvem.config import Configuracao

VALIDADE_DO_ENDERECO = timedelta(minutes=15)
TAMANHO_MAXIMO_DA_FOTO = 2 * 1024 * 1024
"""2 MB: um recorte de placa tem dezenas de KB; uma foto de contexto, algumas centenas."""

CAMINHO_DO_ENVIO = "/api/borda/fotos/envio/"
"""Onde o armazenamento local recebe as fotos (o código cifrado vem depois)."""

_PARTE_DO_REF = r"[A-Za-z0-9._-]+"
_FORMATO_DO_REF = re.compile(rf"{_PARTE_DO_REF}(/{_PARTE_DO_REF})*")
_TAMANHO_MAXIMO_DO_REF = 200
_NOMES_RESERVADOS_DO_WINDOWS = frozenset(
    ["CON", "PRN", "AUX", "NUL"] + [f"{nome}{n}" for nome in ("COM", "LPT") for n in range(1, 10)]
)
"""No Windows, ``NUL`` ou ``con.jpg`` não são arquivos, e sim dispositivos (e ``x.`` vira ``x``)."""
_INICIO_DO_JPEG = b"\xff\xd8\xff"


class RefInvalidoError(ValueError):
    """O ``ref`` da foto foge da regra (letras, números, ``.``, ``_``, ``-``, ``/``).

    Nenhuma parte do ``ref`` termina em ``.`` (o que já recusa ``..``) nem é nome reservado do
    Windows.
    """


class EnderecoRecusadoError(Exception):
    """O endereço de envio foi alterado, é de outra chave ou venceu."""


class FotoInvalidaError(ValueError):
    """A foto não serve (a mensagem diz por quê)."""


class FotoNaoJpegError(FotoInvalidaError):
    """A foto não é JPEG."""


class FotoGrandeDemaisError(FotoInvalidaError):
    """A foto passa de 2 MB."""


class FotoDiferenteError(Exception):
    """Já existe outra foto neste ``ref``: a foto guardada não se troca (SDD 5.5).

    Também quando o ``ref`` esbarra na pasta de outro (``a`` e ``a/b``).
    """


def validar_ref(ref: str) -> None:
    """Confere se o ``ref`` da foto segue a regra (e não sairia da pasta da caixa).

    Raises:
        RefInvalidoError: se não seguir.
    """
    partes = ref.split("/")
    if (
        len(ref) > _TAMANHO_MAXIMO_DO_REF
        or not _FORMATO_DO_REF.fullmatch(ref)
        or any(parte.endswith(".") for parte in partes)
        or any(parte.split(".")[0].upper() in _NOMES_RESERVADOS_DO_WINDOWS for parte in partes)
    ):
        raise RefInvalidoError(
            "o ref da foto usa só letras, números, '.', '_', '-' e '/', com até "
            f"{_TAMANHO_MAXIMO_DO_REF} caracteres; nenhuma parte termina em '.' nem é nome "
            "reservado do Windows (CON, NUL, COM1...)"
        )


class Armazenamento(Protocol):
    """O que a nuvem faz com as fotos, seja qual for o armazenamento."""

    def endereco_de_envio(self, caixa_id: int, ref: str, *, agora: datetime) -> str:
        """Devolve o endereço para a caixa enviar a foto (vale ``VALIDADE_DO_ENDERECO``).

        Raises:
            RefInvalidoError: se o ``ref`` fugir da regra.
        """
        ...

    def ler(self, caixa_id: int, ref: str) -> bytes | None:
        """Devolve a foto, ou ``None`` se ela ainda não chegou.

        Raises:
            RefInvalidoError: se o ``ref`` fugir da regra.
        """
        ...

    def guardar(self, caixa_id: int, ref: str, conteudo: bytes) -> bool:
        """Guarda uma foto feita pela própria nuvem (as desenhadas da demonstração, D-49).

        Returns:
            ``True`` se a foto é nova; ``False`` se a mesma foto já estava guardada.

        Raises:
            RefInvalidoError: se o ``ref`` fugir da regra.
            FotoNaoJpegError: se a foto não for JPEG.
            FotoDiferenteError: se já houver outra foto neste ``ref``.
        """
        ...

    def apagar_da_caixa(self, caixa_id: int) -> None:
        """Apaga todas as fotos de uma caixa (a da empresa de demonstração apagada, D-54)."""
        ...


def armazenamento_da_configuracao(configuracao: Configuracao, cifra: Cifra) -> "Armazenamento":
    """O S3, se a configuração tem o endereço dele; senão, a pasta do disco."""
    if configuracao.fotos_s3_endereco is None:
        return ArmazenamentoLocal(configuracao.pasta_fotos, cifra)
    assert configuracao.fotos_s3_chave and configuracao.fotos_s3_segredo  # a configuração confere
    return ArmazenamentoS3.da_configuracao(
        endereco=str(configuracao.fotos_s3_endereco),
        regiao=configuracao.fotos_s3_regiao,
        balde=configuracao.fotos_s3_balde,
        chave=configuracao.fotos_s3_chave.get_secret_value(),
        segredo=configuracao.fotos_s3_segredo.get_secret_value(),
    )


class ArmazenamentoS3:
    """Fotos num balde S3 (D-56), cada caixa na sua pasta (``caixa-<id>/``), como no disco."""

    def __init__(self, cliente: Any, balde: str) -> None:
        """Prepara o armazenamento.

        Args:
            cliente: o cliente S3 do boto3.
            balde: o balde das fotos (privado: as fotos só saem pela nuvem).
        """
        self._cliente = cliente
        self._balde = balde

    @classmethod
    def da_configuracao(
        cls, *, endereco: str, regiao: str, balde: str, chave: str, segredo: str
    ) -> "ArmazenamentoS3":
        """O armazenamento num S3 qualquer; o balde vai no caminho, como o Supabase pede."""
        # Importados aqui: só quem usa o S3 paga o tempo de importar o boto3.
        import boto3
        from botocore.config import Config

        cliente = boto3.client(
            "s3",
            endpoint_url=endereco,
            region_name=regiao,
            aws_access_key_id=chave,
            aws_secret_access_key=segredo,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        return cls(cliente, balde)

    def endereco_de_envio(self, caixa_id: int, ref: str, *, agora: datetime) -> str:
        """Devolve o endereço assinado do S3 para a caixa enviar a foto (15 minutos)."""
        return str(
            self._cliente.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._balde, "Key": self._chave(caixa_id, ref)},
                ExpiresIn=int(VALIDADE_DO_ENDERECO.total_seconds()),
            )
        )

    def ler(self, caixa_id: int, ref: str) -> bytes | None:
        """Devolve a foto, ou ``None`` se ela ainda não chegou."""
        from botocore.exceptions import ClientError

        try:
            resposta = self._cliente.get_object(Bucket=self._balde, Key=self._chave(caixa_id, ref))
        except ClientError as erro:
            if erro.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        conteudo: bytes = resposta["Body"].read()
        return conteudo

    def guardar(self, caixa_id: int, ref: str, conteudo: bytes) -> bool:
        """Guarda uma foto feita pela própria nuvem; a guardada não se troca (SDD 5.5)."""
        if not conteudo.startswith(_INICIO_DO_JPEG):
            raise FotoNaoJpegError("a foto precisa ser JPEG")
        guardada = self.ler(caixa_id, ref)
        if guardada is not None:
            if guardada == conteudo:
                return False
            raise FotoDiferenteError("já existe outra foto neste ref")
        self._cliente.put_object(
            Bucket=self._balde,
            Key=self._chave(caixa_id, ref),
            Body=conteudo,
            ContentType="image/jpeg",
        )
        return True

    def apagar_da_caixa(self, caixa_id: int) -> None:
        """Apaga todas as fotos da caixa, de mil em mil (o limite do S3)."""
        paginas = self._cliente.get_paginator("list_objects_v2").paginate(
            Bucket=self._balde, Prefix=f"caixa-{caixa_id}/"
        )
        for pagina in paginas:
            chaves = [{"Key": objeto["Key"]} for objeto in pagina.get("Contents", [])]
            if chaves:
                self._cliente.delete_objects(
                    Bucket=self._balde, Delete={"Objects": chaves, "Quiet": True}
                )

    @staticmethod
    def _chave(caixa_id: int, ref: str) -> str:
        validar_ref(ref)
        return f"caixa-{caixa_id}/{ref}"


class ArmazenamentoLocal:
    """Fotos numa pasta do disco; o endereço de envio aponta para a própria API."""

    def __init__(self, pasta: Path, cifra: Cifra) -> None:
        """Prepara o armazenamento.

        Args:
            pasta: onde guardar as fotos (criada quando chegar a primeira).
            cifra: cifra os códigos dos endereços de envio (a mesma chave da configuração).
        """
        self._pasta = pasta
        self._cifra = cifra

    def endereco_de_envio(self, caixa_id: int, ref: str, *, agora: datetime) -> str:
        """Devolve o caminho de envio na API, com um código cifrado (caixa, ref e hora)."""
        validar_ref(ref)
        codigo = self._cifra.cifrar(json.dumps({"caixa": caixa_id, "ref": ref}), agora=agora)
        return CAMINHO_DO_ENVIO + codigo

    def receber(self, codigo: str, conteudo: bytes, *, agora: datetime) -> bool:
        """Guarda a foto enviada ao endereço do ``codigo``.

        Returns:
            ``True`` se a foto é nova; ``False`` se a mesma foto já estava guardada.

        Raises:
            EnderecoRecusadoError: se o código foi alterado ou venceu.
            FotoGrandeDemaisError: se a foto passar de 2 MB.
            FotoNaoJpegError: se a foto não for JPEG.
            FotoDiferenteError: se já houver outra foto neste ``ref``.
        """
        try:
            aberto = self._cifra.decifrar(codigo, validade=VALIDADE_DO_ENDERECO, agora=agora)
            destino = json.loads(aberto)
            caixa_id, ref = int(destino["caixa"]), str(destino["ref"])
        except (SegredoIlegivelError, ValueError, KeyError, TypeError) as erro:
            raise EnderecoRecusadoError("endereço de envio inválido ou vencido") from erro
        if len(conteudo) > TAMANHO_MAXIMO_DA_FOTO:
            raise FotoGrandeDemaisError("a foto pode ter até 2 MB")
        if not conteudo.startswith(_INICIO_DO_JPEG):
            raise FotoNaoJpegError("a foto precisa ser JPEG")
        return self._gravar_sem_trocar(self._caminho(caixa_id, ref), conteudo)

    def ler(self, caixa_id: int, ref: str) -> bytes | None:
        """Devolve a foto, ou ``None`` se ela ainda não chegou."""
        caminho = self._caminho(caixa_id, ref)
        return caminho.read_bytes() if caminho.is_file() else None

    def guardar(self, caixa_id: int, ref: str, conteudo: bytes) -> bool:
        """Guarda uma foto feita pela própria nuvem (as desenhadas da demonstração, D-49)."""
        if not conteudo.startswith(_INICIO_DO_JPEG):
            raise FotoNaoJpegError("a foto precisa ser JPEG")
        return self._gravar_sem_trocar(self._caminho(caixa_id, ref), conteudo)

    def apagar_da_caixa(self, caixa_id: int) -> None:
        """Apaga a pasta das fotos da caixa (se ela existir)."""
        shutil.rmtree(self._pasta / f"caixa-{caixa_id}", ignore_errors=True)

    def _caminho(self, caixa_id: int, ref: str) -> Path:
        validar_ref(ref)
        return self._pasta / f"caixa-{caixa_id}" / ref

    @staticmethod
    def _gravar_sem_trocar(caminho: Path, conteudo: bytes) -> bool:
        if caminho.is_file():
            return _mesma_foto(caminho, conteudo)
        try:
            caminho.parent.mkdir(parents=True, exist_ok=True)
        except (FileExistsError, NotADirectoryError) as erro:
            # Uma parte do caminho já é uma foto (``a``, e agora chega ``a/b``).
            raise FotoDiferenteError("o ref da foto esbarra numa foto já guardada") from erro
        parcial = caminho.with_name(f"{caminho.name}.{uuid4().hex}.parcial")
        parcial.write_bytes(conteudo)
        try:
            # O link só é criado se o destino não existir: dois envios ao mesmo tempo não se
            # sobrescrevem, e quem leu a foto nunca a vê pela metade.
            os.link(parcial, caminho)
        except FileExistsError:
            return _mesma_foto(caminho, conteudo)
        finally:
            parcial.unlink()
        return True


def _mesma_foto(caminho: Path, conteudo: bytes) -> bool:
    if not caminho.is_file():
        # O ``ref`` já é uma pasta (``a/b`` guardada, e agora chega ``a``).
        raise FotoDiferenteError("o ref da foto esbarra na pasta de outras fotos")
    if caminho.read_bytes() != conteudo:
        raise FotoDiferenteError("já existe outra foto neste ref")
    return False


def obter_armazenamento(request: Request) -> Armazenamento:
    """Dependência do FastAPI: o armazenamento de fotos da aplicação."""
    armazenamento: Armazenamento = request.app.state.armazenamento
    return armazenamento

"""Armazenamento das fotos das passagens (SDD 3.2, D-22).

A caixa pede um endereço de envio para cada foto e manda a foto direto para ele. O endereço é
temporário (15 minutos) e já autoriza o envio, sem a chave da caixa: é assim que o S3 funciona
(endereço assinado), e é assim que o armazenamento local imita, com um código cifrado no
endereço. A caixa só aprende uma regra: "peça o endereço e envie".

Implementações:

- ``ArmazenamentoLocal``: uma pasta no disco (agora, no ambiente local e na demonstração);
- ``ArmazenamentoS3``: entra no mês 4, com a mesma interface (``Armazenamento``).

Cada caixa tem a sua pasta: o ``ref`` que a caixa escolhe nunca alcança a foto de outra.
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fastapi import Request

from nuvem.cifra import Cifra, SegredoIlegivelError

VALIDADE_DO_ENDERECO = timedelta(minutes=15)
TAMANHO_MAXIMO_DA_FOTO = 2 * 1024 * 1024
"""2 MB: um recorte de placa tem dezenas de KB; uma foto de contexto, algumas centenas."""

CAMINHO_DO_ENVIO = "/api/borda/fotos/envio/"
"""Onde o armazenamento local recebe as fotos (o código cifrado vem depois)."""

_PARTE_DO_REF = r"[A-Za-z0-9._-]+"
_FORMATO_DO_REF = re.compile(rf"{_PARTE_DO_REF}(/{_PARTE_DO_REF})*")
_TAMANHO_MAXIMO_DO_REF = 200
_INICIO_DO_JPEG = b"\xff\xd8\xff"


class RefInvalidoError(ValueError):
    """O ``ref`` da foto foge da regra (letras, números, ``.``, ``_``, ``-``, ``/``; sem ``..``)."""


class EnderecoRecusadoError(Exception):
    """O endereço de envio foi alterado, é de outra chave ou venceu."""


class FotoInvalidaError(ValueError):
    """A foto não serve (a mensagem diz por quê)."""


class FotoNaoJpegError(FotoInvalidaError):
    """A foto não é JPEG."""


class FotoGrandeDemaisError(FotoInvalidaError):
    """A foto passa de 2 MB."""


class FotoDiferenteError(Exception):
    """Já existe outra foto neste ``ref``: a foto guardada não se troca (SDD 5.5)."""


def validar_ref(ref: str) -> None:
    """Confere se o ``ref`` da foto segue a regra (e não sairia da pasta da caixa).

    Raises:
        RefInvalidoError: se não seguir.
    """
    partes = ref.split("/")
    if (
        len(ref) > _TAMANHO_MAXIMO_DO_REF
        or not _FORMATO_DO_REF.fullmatch(ref)
        or any(parte in (".", "..") for parte in partes)
    ):
        raise RefInvalidoError(
            "o ref da foto usa só letras, números, '.', '_', '-' e '/', sem '..', "
            f"com até {_TAMANHO_MAXIMO_DO_REF} caracteres"
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

    def _caminho(self, caixa_id: int, ref: str) -> Path:
        validar_ref(ref)
        return self._pasta / f"caixa-{caixa_id}" / ref

    @staticmethod
    def _gravar_sem_trocar(caminho: Path, conteudo: bytes) -> bool:
        if caminho.is_file():
            return _mesma_foto(caminho, conteudo)
        caminho.parent.mkdir(parents=True, exist_ok=True)
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
    if caminho.read_bytes() != conteudo:
        raise FotoDiferenteError("já existe outra foto neste ref")
    return False


def obter_armazenamento(request: Request) -> Armazenamento:
    """Dependência do FastAPI: o armazenamento de fotos da aplicação."""
    armazenamento: Armazenamento = request.app.state.armazenamento
    return armazenamento

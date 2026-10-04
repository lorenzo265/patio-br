"""Captura (SDD 4.2): os quadros de uma câmera chegam por uma fonte, à taxa configurada.

A fonte entrega quadros com a hora em que foram vistos. ``amostrar`` deixa passar no máximo
``QUADROS_POR_SEGUNDO`` por segundo: caminhão na portaria anda devagar, e 3 a 5 quadros por
segundo bastam (SDD 4.4).

Fontes:

- ``FonteDeCamera``: uma câmera ao vivo (RTSP); se ela cai, a fonte tenta reabrir;
- ``FonteDeArquivo``: um arquivo de vídeo (ex.: uma gravação da portaria);
- ``FonteDePasta``: as imagens de uma pasta, em ordem de nome (os quadros de um vídeo);
- ``FonteDeMemoria``: quadros já prontos (testes e simulador).

O vídeo é lido pelo OpenCV sem interface gráfica, cujo FFmpeg é LGPL (SDD D-27 e D-29).
"""

import logging
import threading
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

import cv2
import numpy as np
from PIL import Image

from borda.leitor.interface import Quadro

QUADROS_POR_SEGUNDO = 5.0

EXTENSOES_DE_IMAGEM = frozenset({".jpg", ".jpeg", ".png", ".bmp"})

ESPERA_INICIAL_DA_CAMERA = 1.0
ESPERA_MAXIMA_DA_CAMERA = 30.0
"""Segundos entre as tentativas de reabrir uma câmera: 1, 2, 4... até 30."""

PRAZO_DA_CAMERA = 10.0
"""Segundos que a câmera tem para abrir e para mandar cada quadro; depois, conta como caída."""

_registro = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuadroNoTempo:
    """Um quadro e a hora em que a câmera o viu (o relógio da caixa)."""

    momento: datetime
    imagem: Quadro = field(compare=False, repr=False)


class FonteDeQuadros(Protocol):
    """De onde vêm os quadros de uma câmera."""

    def quadros(self) -> Iterator[QuadroNoTempo]:
        """Os quadros, na ordem em que foram vistos."""
        ...


def amostrar(
    quadros: Iterable[QuadroNoTempo], por_segundo: float = QUADROS_POR_SEGUNDO
) -> Iterator[QuadroNoTempo]:
    """Deixa passar no máximo ``por_segundo`` quadros por segundo.

    Passa o primeiro quadro e, depois, cada quadro que chega pelo menos ``1 / por_segundo``
    depois do último que passou.

    Raises:
        ValueError: se ``por_segundo`` não for positivo.
    """
    if por_segundo <= 0:
        raise ValueError(f"os quadros por segundo precisam ser positivos: {por_segundo}")
    intervalo = timedelta(seconds=1 / por_segundo)
    # Uma folga de 1 ms: 30 quadros por segundo não dão 1/5 de segundo exato entre eles.
    folga = timedelta(milliseconds=1)
    ultimo: datetime | None = None
    for quadro in quadros:
        if ultimo is None or quadro.momento - ultimo >= intervalo - folga:
            ultimo = quadro.momento
            yield quadro


class FonteAmostrada:
    """Uma fonte com a taxa limitada por ``amostrar`` (ex.: uma pasta de 30 quadros/s a 5)."""

    def __init__(self, fonte: FonteDeQuadros, por_segundo: float = QUADROS_POR_SEGUNDO) -> None:
        """Guarda a fonte e a taxa."""
        self._fonte = fonte
        self._por_segundo = por_segundo

    def quadros(self) -> Iterator[QuadroNoTempo]:
        """Os quadros da fonte, no máximo ``por_segundo`` por segundo."""
        return amostrar(self._fonte.quadros(), self._por_segundo)


class FonteDeMemoria:
    """Quadros já prontos, em memória."""

    def __init__(self, quadros: Sequence[QuadroNoTempo]) -> None:
        """Guarda os quadros."""
        self._quadros = list(quadros)

    def quadros(self) -> Iterator[QuadroNoTempo]:
        """Os quadros, na ordem dada."""
        return iter(self._quadros)


class FonteDePasta:
    """As imagens de uma pasta, em ordem de nome, como quadros de um vídeo."""

    def __init__(
        self, pasta: Path, *, inicio: datetime, por_segundo: float = QUADROS_POR_SEGUNDO
    ) -> None:
        """Prepara a leitura.

        Args:
            pasta: onde estão as imagens (``.jpg``, ``.png``...); outros arquivos são ignorados.
            inicio: a hora do primeiro quadro.
            por_segundo: quantos quadros por segundo as imagens representam (o quadro ``n``
                fica em ``inicio + n / por_segundo``).
        """
        self._pasta = pasta
        self._inicio = inicio
        self._intervalo = timedelta(seconds=1 / por_segundo)

    def quadros(self) -> Iterator[QuadroNoTempo]:
        """Os quadros, em BGR (como a câmera entrega), na ordem dos nomes dos arquivos."""
        imagens = sorted(
            arquivo
            for arquivo in self._pasta.iterdir()
            if arquivo.suffix.lower() in EXTENSOES_DE_IMAGEM
        )
        for indice, arquivo in enumerate(imagens):
            with Image.open(arquivo) as imagem:
                rgb = np.asarray(imagem.convert("RGB"), dtype=np.uint8)
            bgr = np.ascontiguousarray(rgb[:, :, ::-1])
            yield QuadroNoTempo(momento=self._inicio + indice * self._intervalo, imagem=bgr)


class VideoIlegivelError(Exception):
    """O arquivo de vídeo não abre (não existe, ou o formato não é lido)."""


class FonteDeArquivo:
    """Um arquivo de vídeo, lido do começo ao fim (ex.: uma gravação da portaria)."""

    def __init__(self, caminho: Path, *, inicio: datetime) -> None:
        """Prepara a leitura.

        Args:
            caminho: o arquivo (``.mp4``, ``.avi``, ``.mkv``...).
            inicio: a hora do primeiro quadro; o quadro ``n`` fica em ``inicio + n / taxa``,
                pela taxa de quadros do próprio vídeo.
        """
        self._caminho = caminho
        self._inicio = inicio

    def quadros(self) -> Iterator[QuadroNoTempo]:
        """Os quadros, em BGR (como a câmera entrega), na ordem do vídeo.

        Raises:
            VideoIlegivelError: se o arquivo não abre ou não diz a taxa de quadros.
        """
        video = cv2.VideoCapture(str(self._caminho))
        try:
            if not video.isOpened():
                raise VideoIlegivelError(
                    f"o vídeo {self._caminho} não abre (não existe, ou o formato não é lido)"
                )
            por_segundo = video.get(cv2.CAP_PROP_FPS)
            if por_segundo <= 0:
                raise VideoIlegivelError(f"o vídeo {self._caminho} não abre: não diz a taxa")
            intervalo = timedelta(seconds=1 / por_segundo)
            indice = 0
            while True:
                lido, imagem = video.read()
                if not lido:
                    return
                momento = self._inicio + indice * intervalo
                yield QuadroNoTempo(momento=momento, imagem=np.asarray(imagem, dtype=np.uint8))
                indice += 1
        finally:
            video.release()


class VideoAberto(Protocol):
    """Uma câmera aberta."""

    def ler(self) -> Quadro | None:
        """O próximo quadro, em BGR, ou ``None`` se a câmera caiu."""
        ...

    def fechar(self) -> None:
        """Fecha a câmera."""
        ...


class _CameraDoOpenCV:
    def __init__(self, video: cv2.VideoCapture) -> None:
        self._video = video

    def ler(self) -> Quadro | None:
        lido, imagem = self._video.read()
        return np.asarray(imagem, dtype=np.uint8) if lido else None

    def fechar(self) -> None:
        self._video.release()


def abrir_camera(endereco: str) -> VideoAberto | None:
    """Abre a câmera pelo OpenCV, com prazo para abrir e para cada quadro.

    Returns:
        A câmera aberta, ou ``None`` se ela não abriu.
    """
    prazo = int(PRAZO_DA_CAMERA * 1000)
    parametros = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, prazo, cv2.CAP_PROP_READ_TIMEOUT_MSEC, prazo]
    video = cv2.VideoCapture(endereco, cv2.CAP_FFMPEG, parametros)
    if not video.isOpened():
        video.release()
        return None
    return _CameraDoOpenCV(video)


def sem_credenciais(endereco: str) -> str:
    """O endereço sem o login e a senha, para registro.

    Ex.: ``rtsp://leitura:senha@10.0.0.5:554/stream1`` vira ``rtsp://10.0.0.5:554/stream1``.
    """
    partes = urlsplit(endereco)
    if "@" not in partes.netloc:
        return endereco
    servidor = partes.netloc.rsplit("@", 1)[1]
    return urlunsplit(partes._replace(netloc=servidor))


def _agora() -> datetime:
    return datetime.now(UTC)


class FonteDeCamera:
    """Uma câmera ao vivo (RTSP): a hora de cada quadro é a do relógio da caixa.

    Se a câmera não abre ou para de mandar quadros, a fonte tenta de novo, esperando 1 s, 2 s,
    4 s... até 30 s; a espera volta a 1 s quando os quadros voltam. Só para quando ``parar`` é
    ligado. O registro mostra o endereço sem o login e a senha.
    """

    def __init__(
        self,
        endereco: str,
        *,
        parar: threading.Event,
        abrir: Callable[[str], VideoAberto | None] = abrir_camera,
        relogio: Callable[[], datetime] = _agora,
        dormir: Callable[[float], object] | None = None,
    ) -> None:
        """Prepara a leitura.

        Args:
            endereco: o endereço RTSP, com o login e a senha da câmera.
            parar: quando ligado, a fonte para (a caixa está desligando).
            abrir: como abrir a câmera (os testes passam uma câmera falsa).
            relogio: a hora de cada quadro (o relógio da caixa, sincronizado por NTP).
            dormir: como esperar entre as tentativas (o padrão espera ``parar``, que também
                interrompe a espera).
        """
        self._endereco = endereco
        self._nome = sem_credenciais(endereco)
        self._parar = parar
        self._abrir = abrir
        self._relogio = relogio
        self._dormir = dormir or parar.wait

    def quadros(self) -> Iterator[QuadroNoTempo]:
        """Os quadros, enquanto a caixa estiver ligada (a câmera é fechada no fim)."""
        espera = ESPERA_INICIAL_DA_CAMERA
        while not self._parar.is_set():
            video = self._abrir(self._endereco)
            if video is None:
                _registro.warning(
                    "a câmera %s não abriu; tentando de novo em %.0f s", self._nome, espera
                )
            else:
                try:
                    while not self._parar.is_set():
                        imagem = video.ler()
                        if imagem is None:
                            _registro.warning(
                                "a câmera %s parou de mandar quadros; tentando de novo em %.0f s",
                                self._nome,
                                espera,
                            )
                            break
                        espera = ESPERA_INICIAL_DA_CAMERA
                        yield QuadroNoTempo(momento=self._relogio(), imagem=imagem)
                finally:
                    video.fechar()
            if self._parar.is_set():
                return
            self._dormir(espera)
            espera = min(espera * 2, ESPERA_MAXIMA_DA_CAMERA)

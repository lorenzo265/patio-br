"""Captura (SDD 4.2): os quadros chegam por uma fonte, à taxa configurada (padrão 5 por segundo)."""

import logging
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from itertools import count, pairwise
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from borda.captura import (
    ESPERA_MAXIMA_DA_CAMERA,
    QUADROS_POR_SEGUNDO,
    FonteAmostrada,
    FonteDeArquivo,
    FonteDeCamera,
    FonteDeMemoria,
    FonteDePasta,
    QuadroNoTempo,
    VideoIlegivelError,
    amostrar,
    sem_credenciais,
)
from borda.leitor.interface import Quadro

T0 = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)


def _quadros(quantos: int, por_segundo: float) -> list[QuadroNoTempo]:
    imagem = np.zeros((4, 4, 3), dtype=np.uint8)
    return [
        QuadroNoTempo(momento=T0 + timedelta(seconds=i / por_segundo), imagem=imagem)
        for i in range(quantos)
    ]


def test_padrao_e_5_quadros_por_segundo() -> None:
    assert QUADROS_POR_SEGUNDO == 5


def test_amostrar_um_video_de_30_quadros_por_segundo_deixa_5_por_segundo() -> None:
    saida = list(amostrar(_quadros(60, por_segundo=30)))  # 2 segundos

    momentos = [q.momento for q in saida]
    assert len(saida) == 10
    assert momentos[0] == T0
    assert all(b - a >= timedelta(seconds=0.2) for a, b in pairwise(momentos))


def test_fonte_mais_lenta_que_a_taxa_passa_inteira() -> None:
    assert len(list(amostrar(_quadros(6, por_segundo=2), por_segundo=5))) == 6


def test_taxa_precisa_ser_positiva() -> None:
    with pytest.raises(ValueError, match="quadros por segundo"):
        list(amostrar(_quadros(2, por_segundo=5), por_segundo=0))


def test_fonte_de_memoria_devolve_os_quadros_dados() -> None:
    quadros = _quadros(3, por_segundo=5)

    assert list(FonteDeMemoria(quadros).quadros()) == quadros


@pytest.mark.integracao
def test_fonte_de_pasta_le_as_imagens_em_ordem_de_nome(tmp_path: Path) -> None:
    # Os quadros de um vídeo, tirados fora da caixa, numa pasta (até a caixa ler vídeo).
    for indice, vermelho in [(2, 30), (0, 10), (1, 20)]:
        Image.new("RGB", (8, 6), (vermelho, 0, 0)).save(tmp_path / f"quadro-{indice:04d}.png")
    (tmp_path / "LEIA-ME.txt").write_text("não é imagem", encoding="utf-8")

    quadros = list(FonteDePasta(tmp_path, inicio=T0, por_segundo=10).quadros())

    assert [q.momento for q in quadros] == [T0 + timedelta(seconds=i / 10) for i in range(3)]
    assert [q.imagem.shape for q in quadros] == [(6, 8, 3)] * 3
    # Em BGR, como a câmera entrega: o vermelho fica no último canal.
    assert [int(q.imagem[0, 0, 2]) for q in quadros] == [10, 20, 30]
    assert quadros[0].imagem.dtype == np.uint8


@pytest.mark.integracao
def test_fonte_de_pasta_vazia_nao_devolve_nada(tmp_path: Path) -> None:
    assert list(FonteDePasta(tmp_path, inicio=T0).quadros()) == []


# --- Arquivo de vídeo --------------------------------------------------------------------------


def _gravar_video(caminho: Path, quadros: int, por_segundo: float = 10.0) -> None:
    # Um vídeo inventado: o azul sobe 10 a cada quadro, o vermelho fica alto (BGR).
    gravador = cv2.VideoWriter(str(caminho), cv2.VideoWriter.fourcc(*"MJPG"), por_segundo, (64, 48))
    for indice in range(quadros):
        imagem = np.zeros((48, 64, 3), dtype=np.uint8)
        imagem[:, :] = (10 * indice, 0, 200)
        gravador.write(imagem)
    gravador.release()


@pytest.mark.integracao
def test_fonte_de_arquivo_le_os_quadros_com_a_hora_do_video(tmp_path: Path) -> None:
    video = tmp_path / "portaria.avi"
    _gravar_video(video, quadros=6, por_segundo=10.0)

    quadros = list(FonteDeArquivo(video, inicio=T0).quadros())

    assert [q.momento - T0 for q in quadros] == [timedelta(milliseconds=100 * i) for i in range(6)]
    assert quadros[0].imagem.shape == (48, 64, 3)
    # Em BGR, como a câmera entrega: o vermelho (último canal) alto, o azul subindo.
    assert all(int(q.imagem[0, 0, 2]) > 180 for q in quadros)
    azuis = [int(q.imagem[0, 0, 0]) for q in quadros]
    assert azuis == sorted(azuis)
    assert azuis[-1] > 40


@pytest.mark.integracao
def test_fonte_de_arquivo_passa_pela_amostragem(tmp_path: Path) -> None:
    video = tmp_path / "portaria.avi"
    _gravar_video(video, quadros=10, por_segundo=10.0)

    quadros = list(FonteAmostrada(FonteDeArquivo(video, inicio=T0), por_segundo=5).quadros())

    assert len(quadros) == 5


@pytest.mark.integracao
def test_arquivo_que_nao_abre_explica(tmp_path: Path) -> None:
    (tmp_path / "nao-e-video.avi").write_text("texto qualquer", encoding="utf-8")

    for caminho in (tmp_path / "nao-existe.avi", tmp_path / "nao-e-video.avi"):
        with pytest.raises(VideoIlegivelError, match="não abre"):
            list(FonteDeArquivo(caminho, inicio=T0).quadros())


# --- Câmera (RTSP) -------------------------------------------------------------------------------

ENDERECO = "rtsp://leitura:s3nh4-inventada@10.0.0.5:554/stream1"


class VideoFalso:
    def __init__(self, quadros: int, camera: "CameraFalsa") -> None:
        self._restantes = quadros
        self._camera = camera

    def ler(self) -> Quadro | None:
        if self._restantes == 0:
            return None  # a câmera caiu
        self._restantes -= 1
        return np.zeros((4, 4, 3), dtype=np.uint8)

    def fechar(self) -> None:
        self._camera.fechados += 1


class CameraFalsa:
    """Segue um roteiro: cada abertura é ``None`` (não abriu) ou quantos quadros manda antes de
    cair. Quando o roteiro acaba, pede para parar."""

    def __init__(self, roteiro: list[int | None], parar: threading.Event) -> None:
        self.roteiro = roteiro
        self.parar = parar
        self.enderecos: list[str] = []
        self.fechados = 0

    def abrir(self, endereco: str) -> VideoFalso | None:
        self.enderecos.append(endereco)
        if not self.roteiro:
            self.parar.set()
            return None
        quadros = self.roteiro.pop(0)
        return None if quadros is None else VideoFalso(quadros, self)


def _camera(roteiro: list[int | None]) -> tuple[FonteDeCamera, CameraFalsa, list[float]]:
    parar = threading.Event()
    falsa = CameraFalsa(roteiro, parar)
    esperas: list[float] = []
    segundos = count()
    fonte = FonteDeCamera(
        ENDERECO,
        parar=parar,
        abrir=falsa.abrir,
        relogio=lambda: T0 + timedelta(seconds=next(segundos)),
        dormir=esperas.append,
    )
    return fonte, falsa, esperas


def test_camera_entrega_os_quadros_com_a_hora_da_caixa() -> None:
    fonte, _, _ = _camera([3])

    quadros = list(fonte.quadros())

    assert [q.momento - T0 for q in quadros] == [timedelta(seconds=s) for s in range(3)]


def test_camera_que_cai_e_reaberta_e_os_quadros_continuam() -> None:
    fonte, falsa, esperas = _camera([3, 2])

    quadros = list(fonte.quadros())

    assert len(quadros) == 5
    assert esperas[0] == 1
    assert falsa.enderecos[0] == ENDERECO


def test_camera_que_nao_abre_espera_mais_a_cada_vez_ate_30_segundos() -> None:
    fonte, _, esperas = _camera([None] * 7 + [1])

    assert len(list(fonte.quadros())) == 1
    assert esperas[:7] == [1, 2, 4, 8, 16, 30, 30]
    assert ESPERA_MAXIMA_DA_CAMERA == 30


def test_espera_volta_a_1_segundo_depois_que_os_quadros_voltam() -> None:
    fonte, _, esperas = _camera([None, None, 2, None])

    list(fonte.quadros())

    assert esperas[:4] == [1, 2, 1, 2]


def test_camera_e_fechada_mesmo_quando_quem_le_para_no_meio() -> None:
    fonte, falsa, _ = _camera([10])
    quadros: Iterator[QuadroNoTempo] = fonte.quadros()

    next(quadros)
    quadros.close()  # o agente desligou

    assert falsa.fechados == 1


def test_registro_da_camera_nao_mostra_a_senha(caplog: pytest.LogCaptureFixture) -> None:
    fonte, _, _ = _camera([None, 1])

    with caplog.at_level(logging.WARNING):
        list(fonte.quadros())

    assert "rtsp://10.0.0.5:554/stream1" in caplog.text
    assert "s3nh4-inventada" not in caplog.text
    assert "leitura" not in caplog.text


@pytest.mark.parametrize(
    ("endereco", "sem"),
    [
        (ENDERECO, "rtsp://10.0.0.5:554/stream1"),
        ("rtsp://10.0.0.5/stream1", "rtsp://10.0.0.5/stream1"),
        ("rtsp://so-usuario@[fe80::1]:554/s", "rtsp://[fe80::1]:554/s"),
    ],
    ids=["usuario e senha", "sem nada", "ipv6"],
)
def test_sem_credenciais(endereco: str, sem: str) -> None:
    assert sem_credenciais(endereco) == sem

"""Leitor v0 (T15): preparo e decodificação dos modelos, sem OpenCV.

As partes puras são testadas com saídas montadas à mão. Os testes com os modelos de verdade
só rodam depois de ``uv run tarefas modelos`` (os pesos ficam em ``modelos/``, fora do Git).
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from borda.leitor.interface import Regiao
from borda.leitor.v0 import (
    CLASSES_DE_VEICULO,
    LeitorPaddle,
    caixas_de_texto,
    carregar_v0,
    decodificar_ctc,
    decodificar_yolox,
    expandir,
    nms,
    preparar_yolox,
)

PASTA_DOS_MODELOS = Path(__file__).resolve().parents[2] / "modelos" / "v0"
TEM_MODELOS = (PASTA_DOS_MODELOS / "yolox_tiny.onnx").is_file()


# --- Detector (YOLOX) ----------------------------------------------------------------------


def test_preparo_do_yolox_mantem_a_proporcao_e_completa_com_cinza() -> None:
    quadro = np.full((100, 200, 3), 50, dtype=np.uint8)

    tensor, razao = preparar_yolox(quadro, tamanho=416)

    assert tensor.shape == (1, 3, 416, 416)
    assert tensor.dtype == np.float32
    assert razao == pytest.approx(416 / 200)
    assert tensor[0, :, 0, 0].tolist() == [50, 50, 50]  # a imagem, sem normalizar
    assert tensor[0, :, 415, 0].tolist() == [114, 114, 114]  # o preenchimento


def _saida_yolox(*objetos: tuple[int, int, int, float]) -> np.ndarray:
    """Monta a saída crua do YOLOX (416 px): (coluna, linha, classe, nota) na grade de 8 px."""
    saida = np.zeros((1, 3549, 85), dtype=np.float32)
    for coluna, linha, classe, nota in objetos:
        indice = linha * 52 + coluna
        saida[0, indice, :4] = [0.5, 0.5, np.log(10), np.log(5)]  # 80 x 40 px, no centro
        saida[0, indice, 4] = nota
        saida[0, indice, 5 + classe] = 1.0
    return saida


def test_decodifica_o_caminhao_na_escala_do_quadro() -> None:
    saida = _saida_yolox((20, 10, 7, 0.9))  # caminhão (classe 7 do COCO)

    (deteccao,) = decodificar_yolox(saida, razao=0.5, tamanho=416, limiar=0.1)

    # Centro em (20,5 x 8, 10,5 x 8) = (164, 84); caixa de 80 x 40; a razão 0,5 dobra tudo.
    assert deteccao.regiao == Regiao(x=248, y=128, largura=160, altura=80)
    assert deteccao.confianca == pytest.approx(0.9)


def test_so_veiculos_viram_deteccao() -> None:
    saida = _saida_yolox((20, 10, 0, 0.95), (40, 30, 2, 0.8))  # pessoa e carro

    deteccoes = decodificar_yolox(saida, razao=1.0, tamanho=416, limiar=0.1)

    assert [d.confianca for d in deteccoes] == [pytest.approx(0.8)]
    assert set(CLASSES_DE_VEICULO) == {2, 3, 5, 7}


def test_nota_abaixo_do_limiar_fica_de_fora() -> None:
    saida = _saida_yolox((20, 10, 7, 0.05))

    assert decodificar_yolox(saida, razao=1.0, tamanho=416, limiar=0.1) == []


def test_nms_tira_a_caixa_repetida_de_nota_menor() -> None:
    caixas = np.array([[0, 0, 100, 100], [5, 5, 105, 105], [300, 300, 350, 350]], dtype=float)
    notas = np.array([0.9, 0.8, 0.7])

    assert nms(caixas, notas, iou_maximo=0.45) == [0, 2]


# --- Texto (PaddleOCR) ---------------------------------------------------------------------


def test_caixas_de_texto_separa_palavras_longe_e_junta_as_perto() -> None:
    mapa = np.zeros((40, 100), dtype=np.float32)
    mapa[5:15, 10:30] = 0.9  # palavra 1
    mapa[5:15, 32:41] = 0.9  # 2 px depois: continua a palavra 1
    mapa[5:15, 60:80] = 0.9  # longe: palavra 2
    mapa[25:35, 10:50] = 0.4  # acima do limiar, mas fraca demais para ser texto

    caixas = caixas_de_texto(mapa, limiar=0.3, limiar_da_caixa=0.6)

    assert [regiao for regiao, _ in caixas] == [
        Regiao(x=10, y=5, largura=31, altura=10),
        Regiao(x=60, y=5, largura=20, altura=10),
    ]
    assert all(nota == pytest.approx(0.9) for _, nota in caixas)


def test_expandir_alarga_a_caixa_e_respeita_a_imagem() -> None:
    # Como no PaddleOCR: distância = área x 1,5 / perímetro (310 x 1,5 / 82 ≈ 5,7 → 6 px).
    expandida = expandir(Regiao(x=10, y=5, largura=31, altura=10), largura=100, altura=40)

    assert expandida == Regiao(x=4, y=0, largura=43, altura=21)


def test_ctc_junta_repetidos_e_tira_os_brancos() -> None:
    caracteres = ["blank", "A", "B", "C", "1", "D", "2", "3", " "]
    sequencia = ["A", "A", "blank", "B", "C", "C", "1", "blank", "D", "2", "3", "3", "blank"]
    probabilidades = np.full((len(sequencia), len(caracteres)), 0.01, dtype=np.float32)
    for linha, caractere in enumerate(sequencia):
        probabilidades[linha, caracteres.index(caractere)] = 0.9 if linha != 1 else 0.5

    texto, confianca = decodificar_ctc(probabilidades, caracteres)

    assert texto == "ABC1D23"
    assert confianca == pytest.approx(0.9)  # média só dos caracteres que ficaram


def test_ctc_sem_caractere_devolve_texto_vazio() -> None:
    probabilidades = np.zeros((5, 3), dtype=np.float32)
    probabilidades[:, 0] = 1.0

    assert decodificar_ctc(probabilidades, ["blank", "A", "B"]) == ("", 0.0)


# --- Com os modelos de verdade -------------------------------------------------------------


def _placa_inventada() -> np.ndarray:
    """Um quadro cinza com uma placa desenhada: ABC1D23 (inventada)."""
    imagem = Image.new("RGB", (640, 360), (90, 90, 90))
    desenho = ImageDraw.Draw(imagem)
    desenho.rectangle((220, 220, 420, 280), fill=(245, 245, 245))
    try:
        fonte = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
    except OSError:
        fonte = ImageFont.load_default(size=40)
    desenho.text((232, 226), "ABC1D23", fill=(10, 10, 10), font=fonte)
    return np.ascontiguousarray(np.asarray(imagem)[:, :, ::-1])


@pytest.mark.integracao
@pytest.mark.skipif(not TEM_MODELOS, reason="sem os modelos: rode `uv run tarefas modelos`")
def test_v0_le_a_placa_inventada() -> None:
    _, leitor = carregar_v0(PASTA_DOS_MODELOS)

    leituras = leitor.ler(_placa_inventada())

    assert "ABC1D23" in [leitura.texto for leitura in leituras]
    assert isinstance(leitor, LeitorPaddle)


@pytest.mark.integracao
@pytest.mark.skipif(not TEM_MODELOS, reason="sem os modelos: rode `uv run tarefas modelos`")
def test_detector_do_v0_roda_e_devolve_caixas_dentro_do_quadro() -> None:
    detector, _ = carregar_v0(PASTA_DOS_MODELOS)
    quadro = _placa_inventada()

    for deteccao in detector.detectar(quadro):
        assert 0 <= deteccao.regiao.x <= 640
        assert 0 <= deteccao.regiao.y <= 360

"""Leitor v0 (T15): modelos pré-treinados de terceiros, só para avaliação interna (SDD 4.1).

- **Veículos:** YOLOX-Tiny (ONNX publicado pelo projeto; pesos sem licença declarada).
- **Texto:** PP-OCRv5 mobile do PaddleOCR (Apache-2.0): um modelo acha as linhas de texto, outro
  lê cada linha. A regra de formato da placa (``formato``) vem depois, no rastreador.

Tudo roda no ONNX Runtime, com NumPy e Pillow: sem OpenCV, que traz o FFmpeg (SDD
``[ABERTO-13]``). Os pesos ficam em ``modelos/v0`` (``uv run tarefas modelos``).

Não há meta de acerto no v0: ele existe para o fluxo funcionar; o acerto é trabalho do v1, com
pesos nossos (mês 2).
"""

from pathlib import Path

import numpy as np
import numpy.typing as npt
import onnxruntime as ort
from PIL import Image

from borda.leitor.interface import LeituraBruta, Quadro, Regiao
from borda.rastreio import CONFIANCA_MINIMA, Deteccao

Matriz = npt.NDArray[np.float32]

CLASSES_DE_VEICULO = {2: "carro", 3: "moto", 5: "ônibus", 7: "caminhão"}
"""As classes do COCO que contam como veículo."""

TAMANHO_DO_YOLOX = 416
PASSOS_DO_YOLOX = (8, 16, 32)
CINZA_DO_YOLOX = 114

LADO_MAIOR_DO_TEXTO = 960
"""O modelo de texto trabalha com o lado maior da imagem neste tamanho (múltiplo de 32)."""
LIMIAR_DO_TEXTO = 0.3
LIMIAR_DA_CAIXA = 0.6
RAZAO_DE_EXPANSAO = 1.5
ALTURA_DA_LEITURA = 48
LARGURA_MINIMA_DA_LEITURA = 320
MEDIA = np.array([0.485, 0.456, 0.406], dtype=np.float32)
DESVIO = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _sessao(arquivo: Path) -> ort.InferenceSession:
    opcoes = ort.SessionOptions()
    opcoes.log_severity_level = 3  # só erros: os modelos convertidos avisam coisas inofensivas
    return ort.InferenceSession(str(arquivo), opcoes, providers=["CPUExecutionProvider"])


def _redimensionar(quadro: Quadro, largura: int, altura: int) -> Quadro:
    # Pillow trabalha em RGB; o quadro é BGR.
    imagem = Image.fromarray(np.ascontiguousarray(quadro[:, :, ::-1]))
    return np.asarray(imagem.resize((largura, altura), Image.Resampling.BILINEAR))[:, :, ::-1]


# --- Veículos: YOLOX -----------------------------------------------------------------------


def preparar_yolox(quadro: Quadro, tamanho: int = TAMANHO_DO_YOLOX) -> tuple[Matriz, float]:
    """Põe o quadro no tamanho do YOLOX sem distorcer (o resto fica cinza).

    Returns:
        O tensor (1, 3, tamanho, tamanho) e a razão usada (para voltar à escala do quadro).
    """
    altura, largura = quadro.shape[:2]
    razao = min(tamanho / altura, tamanho / largura)
    nova_largura, nova_altura = int(largura * razao), int(altura * razao)
    tela = np.full((tamanho, tamanho, 3), CINZA_DO_YOLOX, dtype=np.float32)
    tela[:nova_altura, :nova_largura] = _redimensionar(quadro, nova_largura, nova_altura)
    return np.ascontiguousarray(tela.transpose(2, 0, 1)[None]), razao


def decodificar_yolox(
    saida: Matriz, *, razao: float, tamanho: int = TAMANHO_DO_YOLOX, limiar: float
) -> list[Deteccao]:
    """Transforma a saída crua do YOLOX em veículos, na escala do quadro."""
    previsoes = saida[0].astype(np.float64)
    grades, passos = [], []
    for passo in PASSOS_DO_YOLOX:
        lado = tamanho // passo
        colunas, linhas = np.meshgrid(np.arange(lado), np.arange(lado))
        grades.append(np.stack((colunas, linhas), axis=2).reshape(-1, 2))
        passos.append(np.full((lado * lado, 1), passo))
    grade, passo_de_cada = np.concatenate(grades), np.concatenate(passos)
    centros = (previsoes[:, :2] + grade) * passo_de_cada
    tamanhos = np.exp(previsoes[:, 2:4]) * passo_de_cada
    classes = previsoes[:, 5:].argmax(axis=1)
    notas = previsoes[:, 4] * previsoes[np.arange(len(classes)), 5 + classes]
    escolhidos = np.isin(classes, list(CLASSES_DE_VEICULO)) & (notas >= limiar)
    caixas = (
        np.concatenate((centros - tamanhos / 2, centros + tamanhos / 2), axis=1)[escolhidos] / razao
    )
    notas = notas[escolhidos]
    return [
        Deteccao(
            regiao=Regiao(
                x=round(caixas[i, 0]),
                y=round(caixas[i, 1]),
                largura=round(caixas[i, 2] - caixas[i, 0]),
                altura=round(caixas[i, 3] - caixas[i, 1]),
            ),
            confianca=float(notas[i]),
        )
        for i in nms(caixas, notas, iou_maximo=0.45)
    ]


def nms(
    caixas: npt.NDArray[np.float64], notas: npt.NDArray[np.float64], *, iou_maximo: float
) -> list[int]:
    """Supressão de não máximos: das caixas que se sobrepõem demais, fica a de nota maior.

    Returns:
        Os índices das caixas que ficam, da nota maior para a menor.
    """
    ordem = list(np.argsort(-notas))
    ficam: list[int] = []
    while ordem:
        melhor, *resto = ordem
        ficam.append(int(melhor))
        x0 = np.maximum(caixas[melhor, 0], caixas[resto, 0])
        y0 = np.maximum(caixas[melhor, 1], caixas[resto, 1])
        x1 = np.minimum(caixas[melhor, 2], caixas[resto, 2])
        y1 = np.minimum(caixas[melhor, 3], caixas[resto, 3])
        comum = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
        areas = (caixas[:, 2] - caixas[:, 0]) * (caixas[:, 3] - caixas[:, 1])
        iou = comum / (areas[melhor] + areas[resto] - comum)
        ordem = [indice for indice, valor in zip(resto, iou, strict=True) if valor <= iou_maximo]
    return ficam


class DetectorYolox:
    """Acha os veículos de um quadro com o YOLOX-Tiny (só avaliação interna)."""

    def __init__(self, arquivo: Path, *, limiar: float = CONFIANCA_MINIMA) -> None:
        """Carrega o modelo (``yolox_tiny.onnx``)."""
        self._sessao = _sessao(arquivo)
        self._entrada = self._sessao.get_inputs()[0].name
        self._limiar = limiar

    def detectar(self, quadro: Quadro) -> list[Deteccao]:
        """Os veículos do quadro."""
        tensor, razao = preparar_yolox(quadro)
        saida = self._sessao.run(None, {self._entrada: tensor})[0]
        return decodificar_yolox(saida, razao=razao, limiar=self._limiar)


# --- Texto: PaddleOCR ----------------------------------------------------------------------


def caixas_de_texto(
    mapa: Matriz, *, limiar: float = LIMIAR_DO_TEXTO, limiar_da_caixa: float = LIMIAR_DA_CAIXA
) -> list[tuple[Regiao, float]]:
    """Acha as linhas de texto no mapa de probabilidade do detector de texto.

    Sem OpenCV: em vez de contornos, separa faixas de linhas e, dentro de cada faixa, trechos
    de colunas (juntando os trechos separados por uma folga pequena, como as letras de uma
    palavra). Placa é texto reto, e isso basta.

    Returns:
        A região de cada linha (na escala do mapa) e a nota média dela; só as com nota boa.
    """
    marcado = mapa > limiar
    caixas = []
    for topo, base in _trechos(marcado.any(axis=1), folga=0):
        faixa = marcado[topo : base + 1]
        folga = max(1, (base - topo + 1) // 2)
        for esquerda, direita in _trechos(faixa.any(axis=0), folga=folga):
            linhas = np.nonzero(faixa[:, esquerda : direita + 1].any(axis=1))[0]
            y0, y1 = topo + int(linhas[0]), topo + int(linhas[-1])
            pedaco = mapa[y0 : y1 + 1, esquerda : direita + 1]
            nota = float(pedaco[pedaco > limiar].mean())
            if nota >= limiar_da_caixa and min(y1 - y0, direita - esquerda) >= 2:
                regiao = Regiao(
                    x=esquerda, y=y0, largura=direita - esquerda + 1, altura=y1 - y0 + 1
                )
                caixas.append((regiao, nota))
    return caixas


def _trechos(marcados: npt.NDArray[np.bool_], *, folga: int) -> list[tuple[int, int]]:
    # Trechos seguidos de posições marcadas; buracos de até `folga` posições não separam.
    indices = np.nonzero(marcados)[0]
    if len(indices) == 0:
        return []
    trechos = []
    inicio = anterior = int(indices[0])
    for indice in map(int, indices[1:]):
        if indice - anterior - 1 > folga:
            trechos.append((inicio, anterior))
            inicio = indice
        anterior = indice
    trechos.append((inicio, anterior))
    return trechos


def expandir(
    regiao: Regiao, *, largura: int, altura: int, razao: float = RAZAO_DE_EXPANSAO
) -> Regiao:
    """Alarga a caixa como o PaddleOCR, sem sair da imagem.

    A distância somada em cada lado é a área vezes a razão, dividida pelo perímetro.
    """
    area = regiao.largura * regiao.altura
    distancia = round(area * razao / (2 * (regiao.largura + regiao.altura)))
    x0, y0 = max(regiao.x - distancia, 0), max(regiao.y - distancia, 0)
    x1 = min(regiao.x + regiao.largura + distancia, largura)
    y1 = min(regiao.y + regiao.altura + distancia, altura)
    return Regiao(x=x0, y=y0, largura=x1 - x0, altura=y1 - y0)


def decodificar_ctc(probabilidades: Matriz, caracteres: list[str]) -> tuple[str, float]:
    """Lê a saída do modelo de leitura: junta repetidos seguidos e tira os brancos (CTC).

    Returns:
        O texto e a confiança (a média das probabilidades dos caracteres que ficaram).
    """
    indices = probabilidades.argmax(axis=1)
    maximos = probabilidades.max(axis=1)
    texto, confiancas, anterior = [], [], -1
    for indice, probabilidade in zip(indices, maximos, strict=True):
        if indice != anterior and indice != 0:
            texto.append(caracteres[indice])
            confiancas.append(float(probabilidade))
        anterior = indice
    return "".join(texto).strip(), float(np.mean(confiancas)) if confiancas else 0.0


class LeitorPaddle:
    """Lê os textos de uma imagem com os modelos do PaddleOCR (PP-OCRv5 mobile)."""

    def __init__(self, deteccao: Path, leitura: Path, dicionario: Path) -> None:
        """Carrega os dois modelos e o dicionário de caracteres do modelo de leitura."""
        self._deteccao = _sessao(deteccao)
        self._leitura = _sessao(leitura)
        dicionario_lido = dicionario.read_text(encoding="utf-8").split("\n")
        saidas = self._leitura.get_outputs()[0].shape[-1]
        # Índice 0 é o "branco" do CTC; o espaço no fim existe quando o modelo tem uma saída a mais.
        espaco = [" "] if saidas == len(dicionario_lido) + 2 else []
        self._caracteres = ["blank", *dicionario_lido, *espaco]

    def ler(self, quadro: Quadro) -> list[LeituraBruta]:
        """Os textos da imagem, com a confiança e a região de cada um."""
        mapa, escala_y, escala_x = self._mapa(quadro)
        leituras = []
        for regiao_no_mapa, _ in caixas_de_texto(mapa):
            no_mapa = expandir(regiao_no_mapa, largura=mapa.shape[1], altura=mapa.shape[0])
            regiao = Regiao(
                x=int(no_mapa.x * escala_x),
                y=int(no_mapa.y * escala_y),
                largura=max(1, int(no_mapa.largura * escala_x)),
                altura=max(1, int(no_mapa.altura * escala_y)),
            )
            recorte = quadro[
                regiao.y : regiao.y + regiao.altura, regiao.x : regiao.x + regiao.largura
            ]
            if recorte.size == 0:
                continue
            texto, confianca = self._ler_linha(recorte)
            if texto:
                leituras.append(LeituraBruta(texto=texto, confianca=confianca, regiao=regiao))
        return leituras

    def _mapa(self, quadro: Quadro) -> tuple[Matriz, float, float]:
        altura, largura = quadro.shape[:2]
        escala = LADO_MAIOR_DO_TEXTO / max(altura, largura)
        nova_altura = max(32, round(altura * escala / 32) * 32)
        nova_largura = max(32, round(largura * escala / 32) * 32)
        imagem = _redimensionar(quadro, nova_largura, nova_altura).astype(np.float32)
        normalizada = (imagem / 255 - MEDIA) / DESVIO
        tensor = np.ascontiguousarray(normalizada.transpose(2, 0, 1)[None], dtype=np.float32)
        entrada = self._deteccao.get_inputs()[0].name
        mapa = self._deteccao.run(None, {entrada: tensor})[0][0, 0]
        return mapa, altura / nova_altura, largura / nova_largura

    def _ler_linha(self, recorte: Quadro) -> tuple[str, float]:
        altura, largura = recorte.shape[:2]
        nova_largura = max(1, int(np.ceil(ALTURA_DA_LEITURA * largura / altura)))
        imagem = _redimensionar(recorte, nova_largura, ALTURA_DA_LEITURA).astype(np.float32)
        tela = np.zeros(
            (ALTURA_DA_LEITURA, max(nova_largura, LARGURA_MINIMA_DA_LEITURA), 3), dtype=np.float32
        )
        tela[:, :nova_largura] = (imagem / 255 - 0.5) / 0.5
        tensor = np.ascontiguousarray(tela.transpose(2, 0, 1)[None])
        entrada = self._leitura.get_inputs()[0].name
        probabilidades = self._leitura.run(None, {entrada: tensor})[0][0]
        return decodificar_ctc(probabilidades, self._caracteres)


def carregar_v0(pasta: Path) -> tuple[DetectorYolox, LeitorPaddle]:
    """Carrega o detector e o leitor do v0 da pasta dos modelos.

    Raises:
        FileNotFoundError: se faltar um modelo (rode ``uv run tarefas modelos``).
    """
    arquivos = {
        nome: pasta / nome
        for nome in (
            "yolox_tiny.onnx",
            "texto_deteccao.onnx",
            "texto_leitura.onnx",
            "texto_leitura_dicionario.txt",
        )
    }
    faltando = [nome for nome, arquivo in arquivos.items() if not arquivo.is_file()]
    if faltando:
        raise FileNotFoundError(
            f"faltam modelos em {pasta}: {', '.join(faltando)}; rode `uv run tarefas modelos`"
        )
    detector = DetectorYolox(arquivos["yolox_tiny.onnx"])
    leitor = LeitorPaddle(
        arquivos["texto_deteccao.onnx"],
        arquivos["texto_leitura.onnx"],
        arquivos["texto_leitura_dicionario.txt"],
    )
    return detector, leitor

"""As variações que imitam o recorte da câmera (D-72).

A perspectiva (a câmera nunca está de frente), o borrão (o movimento e o foco), a luz (o sol, a
sombra e a noite), a sujeira, um pedaço coberto (o engate, o para-choque), o ruído e o tamanho
(o recorte da caixa tem de 60 a 240 pixels de largura). A compressão do JPEG fica para a hora de
gravar. Tudo sai do gerador que se passa: a mesma semente dá a mesma imagem.
"""

import random

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

LARGURA_MINIMA = 60
LARGURA_MAXIMA = 240
FOLGA = 0.12
"""Quanto da imagem em volta da placa entra no recorte (o para-choque), de cada lado."""


def variar(placa: Image.Image, gerador: random.Random) -> Image.Image:
    """A placa como a câmera a recortaria."""
    numeros = np.random.default_rng(gerador.getrandbits(64))
    imagem = _perspectiva(placa, gerador)
    imagem = _luz(imagem, gerador)
    imagem = _sujeira(imagem, gerador)
    if gerador.random() < 0.15:
        imagem = _coberta(imagem, gerador)
    imagem = imagem.filter(ImageFilter.GaussianBlur(gerador.uniform(0, 2.5)))
    largura = gerador.randint(LARGURA_MINIMA, LARGURA_MAXIMA)
    altura = max(1, round(imagem.height * largura / imagem.width))
    imagem = imagem.resize((largura, altura), Image.Resampling.BILINEAR)
    return _ruido(imagem, numeros, gerador.uniform(0, 8))


def _perspectiva(placa: Image.Image, gerador: random.Random) -> Image.Image:
    largura, altura = placa.size
    folga_x, folga_y = round(largura * FOLGA), round(altura * FOLGA * 2)
    tamanho = (largura + 2 * folga_x, altura + 2 * folga_y)
    fundo = tuple(gerador.randint(20, 120) for _ in range(3))
    tela = Image.new("RGB", tamanho, fundo)
    tela.paste(placa, (folga_x, folga_y))
    # Os cantos da placa vão para lugares um pouco tortos; a transformação leva cada ponto da
    # saída de volta ao da entrada.
    cantos = [
        (folga_x, folga_y),
        (folga_x + largura, folga_y),
        (folga_x + largura, folga_y + altura),
        (folga_x, folga_y + altura),
    ]
    tortos = [
        (x + gerador.uniform(-0.06, 0.06) * largura, y + gerador.uniform(-0.12, 0.12) * altura)
        for x, y in cantos
    ]
    coeficientes = _coeficientes(tortos, cantos)
    return tela.transform(
        tamanho,
        Image.Transform.PERSPECTIVE,
        coeficientes,
        Image.Resampling.BILINEAR,
        fillcolor=fundo,
    )


def _coeficientes(
    destino: list[tuple[float, float]], origem: list[tuple[int, int]]
) -> tuple[float, ...]:
    """Os 8 coeficientes da perspectiva do Pillow, que levam o destino de volta à origem."""
    linhas = []
    for (x, y), (u, v) in zip(destino, origem, strict=True):
        linhas.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        linhas.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    matriz = np.array(linhas, dtype=float)
    alvo = np.array([c for ponto in origem for c in ponto], dtype=float)
    return tuple(float(c) for c in np.linalg.solve(matriz, alvo))


def _luz(imagem: Image.Image, gerador: random.Random) -> Image.Image:
    imagem = ImageEnhance.Brightness(imagem).enhance(gerador.uniform(0.45, 1.3))
    imagem = ImageEnhance.Contrast(imagem).enhance(gerador.uniform(0.6, 1.2))
    if gerador.random() < 0.4:
        # A sombra de um lado (o poste, a cabine).
        sombra = Image.new("L", imagem.size, 0)
        desenho = ImageDraw.Draw(sombra)
        corte = gerador.uniform(0.2, 0.8) * imagem.width
        desenho.polygon(
            [
                (0, 0),
                (corte, 0),
                (corte * gerador.uniform(0.6, 1.4), imagem.height),
                (0, imagem.height),
            ],
            fill=gerador.randint(60, 140),
        )
        escura = Image.new("RGB", imagem.size, (0, 0, 0))
        imagem = Image.composite(escura, imagem, sombra.filter(ImageFilter.GaussianBlur(8)))
    return imagem


def _sujeira(imagem: Image.Image, gerador: random.Random) -> Image.Image:
    camada = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
    desenho = ImageDraw.Draw(camada)
    for _ in range(gerador.randint(0, 8)):
        x, y = gerador.uniform(0, imagem.width), gerador.uniform(0, imagem.height)
        raio = gerador.uniform(0.01, 0.06) * imagem.width
        cor = (gerador.randint(60, 110), gerador.randint(45, 80), gerador.randint(20, 50))
        desenho.ellipse(
            (x - raio, y - raio * 0.6, x + raio, y + raio * 0.6),
            fill=(*cor, gerador.randint(30, 110)),
        )
    camada = camada.filter(ImageFilter.GaussianBlur(3))
    return Image.alpha_composite(imagem.convert("RGBA"), camada).convert("RGB")


def _coberta(imagem: Image.Image, gerador: random.Random) -> Image.Image:
    # Um pedaço coberto (o engate, a lona): até 15% da largura, nunca o meio inteiro.
    largura = gerador.uniform(0.05, 0.15) * imagem.width
    x = gerador.choice((gerador.uniform(0, 0.2), gerador.uniform(0.65, 0.85))) * imagem.width
    desenho = ImageDraw.Draw(imagem)
    cor = tuple(gerador.randint(10, 60) for _ in range(3))
    desenho.rectangle((x, 0, x + largura, imagem.height), fill=cor)
    return imagem


def _ruido(imagem: Image.Image, numeros: np.random.Generator, forca: float) -> Image.Image:
    pixels = np.asarray(imagem, dtype=np.float64) + numeros.normal(
        0, forca, (imagem.height, imagem.width, 3)
    )
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), "RGB")

"""As placas de carro e caminhão (400 por 130 mm): a Mercosul e a antiga (D-72).

- **Mercosul:** fundo branco, a faixa azul no alto com "BRASIL", e a cor dos caracteres pela
  categoria (particular preto, comercial vermelho, oficial azul, especial verde, colecionador
  cinza e diplomática dourado). O texto: três letras, um número, uma letra e dois números.
- **Antiga:** fundo cinza (particular), vermelho (comercial) ou branco (oficial), a faixa da
  cidade no alto e o texto com o hífen: três letras e quatro números.

O texto sai sempre no formato válido (SDD 4.2). A placa de moto fica de fora: o pátio é de
caminhões.
"""

import random
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from ml.sinteticas import fonte

TipoDePlaca = Literal["mercosul", "antiga"]
Cor = tuple[int, int, int]

LARGURA_MM = 400
ALTURA_MM = 130
PIXELS_POR_MM = 2
BRANCO: Cor = (255, 255, 255)
PRETO: Cor = (0, 0, 0)
AZUL_DA_FAIXA: Cor = (0, 51, 153)
MARGEM_DO_TEXTO = 0.9
"""O texto ocupa no máximo 90% da largura da placa."""

CATEGORIAS: dict[TipoDePlaca, dict[str, tuple[Cor, Cor]]] = {
    "mercosul": {
        "particular": (BRANCO, PRETO),
        "comercial": (BRANCO, (192, 0, 0)),
        "oficial": (BRANCO, (31, 58, 147)),
        "especial": (BRANCO, (0, 122, 51)),
        "colecionador": (BRANCO, (112, 112, 112)),
        "diplomatica": (BRANCO, (184, 134, 11)),
    },
    "antiga": {
        "particular": ((166, 166, 166), PRETO),
        "comercial": ((178, 34, 34), BRANCO),
        "oficial": (BRANCO, PRETO),
    },
}
"""De cada tipo, as categorias: a cor do fundo e a dos caracteres."""

CIDADES = (
    "SP - SAO PAULO",
    "RS - PORTO ALEGRE",
    "RN - NATAL",
    "MG - BELO HORIZONTE",
    "PR - CURITIBA",
)
"""A faixa da placa antiga (cidades de verdade, sem nenhum dado de pessoa)."""


@dataclass(frozen=True)
class Placa:
    """O que vai numa placa sintética."""

    texto: str
    tipo: TipoDePlaca
    categoria: str


def sortear_texto(gerador: random.Random, tipo: TipoDePlaca) -> str:
    """Um texto de placa no formato do tipo (sem o hífen)."""
    letras = "".join(gerador.choice(string.ascii_uppercase) for _ in range(3))
    if tipo == "antiga":
        return letras + "".join(gerador.choice(string.digits) for _ in range(4))
    return (
        letras
        + gerador.choice(string.digits)
        + gerador.choice(string.ascii_uppercase)
        + "".join(gerador.choice(string.digits) for _ in range(2))
    )


def sortear(gerador: random.Random) -> Placa:
    """Uma placa: o tipo (metade de cada), a categoria (a particular é a mais comum) e o texto."""
    tipo: TipoDePlaca = gerador.choice(("mercosul", "antiga"))
    categorias = list(CATEGORIAS[tipo])
    pesos = [6 if categoria == "particular" else 1 for categoria in categorias]
    categoria = gerador.choices(categorias, weights=pesos)[0]
    return Placa(sortear_texto(gerador, tipo), tipo, categoria)


def desenhar(placa: Placa, *, fonte_ttf: Path | None = None) -> Image.Image:
    """A placa de frente, em RGB, com 2 pixels por milímetro."""
    largura, altura = LARGURA_MM * PIXELS_POR_MM, ALTURA_MM * PIXELS_POR_MM
    fundo, tinta = CATEGORIAS[placa.tipo][placa.categoria]
    imagem = Image.new("RGB", (largura, altura), fundo)
    desenho = ImageDraw.Draw(imagem)
    faixa = round(altura * (0.24 if placa.tipo == "mercosul" else 0.2))
    if placa.tipo == "mercosul":
        desenho.rectangle((0, 0, largura, faixa), fill=AZUL_DA_FAIXA)
        _escrever(
            imagem, "BRASIL", centro=(largura / 2, faixa / 2), altura=faixa * 0.55, cor=BRANCO
        )
        texto = placa.texto
    else:
        cidade = CIDADES[sum(map(ord, placa.texto)) % len(CIDADES)]
        _escrever_frase(
            imagem, cidade, centro=(largura / 2, faixa / 2), altura=faixa * 0.5, cor=tinta
        )
        texto = f"{placa.texto[:3]}-{placa.texto[3:]}"
    area = altura - faixa
    _escrever(
        imagem,
        texto,
        centro=(largura / 2, faixa + area / 2),
        altura=area * 0.68,
        cor=tinta,
        fonte_ttf=fonte_ttf,
    )
    borda = max(2, round(altura * 0.02))
    desenho.rectangle((0, 0, largura - 1, altura - 1), outline=PRETO, width=borda)
    return imagem


def _escrever(
    imagem: Image.Image,
    texto: str,
    *,
    centro: tuple[float, float],
    altura: float,
    cor: Cor,
    fonte_ttf: Path | None = None,
) -> None:
    if not texto:
        return
    if fonte_ttf is not None:
        _escrever_ttf(imagem, texto, centro=centro, altura=altura, cor=cor, fonte_ttf=fonte_ttf)
        return
    total = _largura_do_texto(texto, altura)
    largura_maxima = imagem.width * MARGEM_DO_TEXTO
    if total > largura_maxima:
        # O texto mais comprido (a placa antiga, com o hífen) fica mais baixo para caber.
        altura *= largura_maxima / total
        total = largura_maxima
    espaco = altura * 0.12
    larguras = [fonte.largura_de(altura) for _ in texto]
    x = centro[0] - total / 2
    for caractere, largura in zip(texto, larguras, strict=True):
        fonte.desenhar(imagem, caractere, (x, centro[1] - altura / 2), altura=altura, cor=cor)
        x += largura + espaco


def _largura_do_texto(texto: str, altura: float) -> float:
    return fonte.largura_de(altura) * len(texto) + altura * 0.12 * (len(texto) - 1)


def _escrever_frase(
    imagem: Image.Image, frase: str, *, centro: tuple[float, float], altura: float, cor: Cor
) -> None:
    # A faixa da cidade: as palavras com um espaço entre elas (o espaço não tem traço).
    palavras = [p for p in frase.replace("-", " - ").split(" ") if p]
    espaco = altura * 0.12
    larguras = [len(p) * (fonte.largura_de(altura) + espaco) for p in palavras]
    total = sum(larguras) + altura * 0.4 * (len(palavras) - 1)
    x = centro[0] - total / 2
    for palavra, largura in zip(palavras, larguras, strict=True):
        _escrever(imagem, palavra, centro=(x + largura / 2, centro[1]), altura=altura, cor=cor)
        x += largura + altura * 0.4


def _escrever_ttf(
    imagem: Image.Image,
    texto: str,
    *,
    centro: tuple[float, float],
    altura: float,
    cor: Cor,
    fonte_ttf: Path,
) -> None:
    letra = ImageFont.truetype(str(fonte_ttf), size=round(altura * 1.3))
    desenho = ImageDraw.Draw(imagem)
    desenho.text(centro, texto, fill=cor, font=letra, anchor="mm")

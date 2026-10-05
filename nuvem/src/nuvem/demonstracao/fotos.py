"""As fotos de placa desenhadas da demonstração (D-49): parecem um recorte de placa Mercosul.

São inventadas: nenhuma câmera as tirou. Ficam no armazenamento como as fotos da caixa, e a
portaria as mostra do mesmo jeito (a conferência da placa, D-42).
"""

import io
from functools import cache

from PIL import Image, ImageDraw, ImageFont

LARGURA, ALTURA = 300, 100
AZUL = (0, 51, 153)


@cache
def _fonte(tamanho: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", tamanho)
    except OSError:
        return ImageFont.load_default(size=tamanho)


def placa_desenhada(placa: str) -> bytes:
    """O JPEG de uma placa: fundo branco, a faixa azul com "BRASIL" e os caracteres pretos."""
    imagem = Image.new("RGB", (LARGURA, ALTURA), (238, 240, 236))
    desenho = ImageDraw.Draw(imagem)
    desenho.rounded_rectangle((3, 3, LARGURA - 4, ALTURA - 4), radius=8, fill=(250, 250, 250),
                              outline=(30, 30, 30), width=3)  # fmt: skip
    desenho.rectangle((6, 6, LARGURA - 7, 27), fill=AZUL)
    desenho.text((LARGURA // 2, 17), "BRASIL", fill=(255, 255, 255), font=_fonte(15), anchor="mm")
    desenho.text((LARGURA // 2, 64), placa.upper(), fill=(15, 15, 15), font=_fonte(50), anchor="mm")
    saida = io.BytesIO()
    imagem.save(saida, "JPEG", quality=88)
    return saida.getvalue()

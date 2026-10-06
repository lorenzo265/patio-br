"""O lote de placas sintéticas: ``uv run tarefas sinteticas`` (D-72).

Grava ``imagens/000001.jpg`` em diante e ``rotulos.csv`` (``arquivo,placa,tipo,categoria``) na
pasta de destino (``dados/sinteticas``, que o Git ignora). Cada imagem tem a própria semente,
tirada da semente do lote e do número dela: o mesmo lote sai igual, imagem por imagem.
"""

import argparse
import csv
import random
from collections.abc import Sequence
from pathlib import Path

from ml.sinteticas import placa, variacoes

DESTINO_PADRAO = Path("dados/sinteticas")


def gerar(destino: Path, *, quantas: int, semente: int, fonte_ttf: Path | None = None) -> int:
    """Gera o lote; devolve quantas placas gravou.

    Raises:
        ValueError: se a fonte TTF pedida não existe.
    """
    if fonte_ttf is not None and not fonte_ttf.is_file():
        raise ValueError(f"a fonte {fonte_ttf} não existe")
    imagens = destino / "imagens"
    imagens.mkdir(parents=True, exist_ok=True)
    with (destino / "rotulos.csv").open("w", newline="", encoding="utf-8") as arquivo_csv:
        escritor = csv.writer(arquivo_csv, lineterminator="\n")
        escritor.writerow(["arquivo", "placa", "tipo", "categoria"])
        for numero in range(1, quantas + 1):
            gerador = random.Random(f"{semente}:{numero}")
            sorteada = placa.sortear(gerador)
            recorte = variacoes.variar(placa.desenhar(sorteada, fonte_ttf=fonte_ttf), gerador)
            nome = f"imagens/{numero:06d}.jpg"
            recorte.save(destino / nome, "JPEG", quality=gerador.randint(25, 95))
            escritor.writerow([nome, sorteada.texto, sorteada.tipo, sorteada.categoria])
    return quantas


def principal(argv: Sequence[str] | None = None) -> None:
    """Lê os argumentos, gera o lote e diz quantas placas foram."""
    interpretador = argparse.ArgumentParser(prog="python -m ml.sinteticas", description=__doc__)
    interpretador.add_argument("--quantas", type=int, default=1000)
    interpretador.add_argument("--semente", type=int, default=2026)
    interpretador.add_argument("--destino", type=Path, default=DESTINO_PADRAO)
    interpretador.add_argument(
        "--fonte-ttf", type=Path, default=None, help="uma fonte de licença permissiva ou OFL"
    )
    argumentos = interpretador.parse_args(argv)
    feitas = gerar(
        argumentos.destino,
        quantas=argumentos.quantas,
        semente=argumentos.semente,
        fonte_ttf=argumentos.fonte_ttf,
    )
    print(f"{feitas} placas em {argumentos.destino}")

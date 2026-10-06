"""O gerador de placas sintéticas (SDD 4.6, D-44 e D-72)."""

import csv
import hashlib
import random
from pathlib import Path

import pytest
from PIL import Image

from contratos.placa import normalizar_placa
from ml.sinteticas import fonte, gerar, placa, variacoes
from ml.sinteticas.placa import CATEGORIAS, Placa


@pytest.mark.parametrize("tipo", ["mercosul", "antiga"])
def test_o_texto_sorteado_e_sempre_uma_placa_valida(tipo: str) -> None:
    gerador = random.Random(1)
    for _ in range(2000):
        texto = placa.sortear_texto(gerador, tipo)  # type: ignore[arg-type]
        assert normalizar_placa(texto) == texto
        if tipo == "mercosul":
            assert texto[4].isalpha()
        else:
            assert texto[3:].isdigit()


def test_a_fonte_tem_todas_as_letras_e_numeros() -> None:
    for caractere in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        tracos = fonte.TRACOS[caractere]
        assert tracos
        for linha in tracos:
            assert all(0 <= x <= fonte.LARGURA and 0 <= y <= fonte.ALTURA for x, y in linha)


def test_a_fonte_desenha_cada_caractere_diferente() -> None:
    desenhos = set()
    for caractere in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        imagem = Image.new("L", (60, 100), 255)
        fonte.desenhar(imagem, caractere, (5, 5), altura=90, cor=0)
        assert imagem.getextrema()[0] == 0  # desenhou alguma coisa
        desenhos.add(imagem.tobytes())
    assert len(desenhos) >= 35  # o O e o 0 podem ser iguais


def _cor(imagem: Image.Image, x: float, y: float) -> tuple[int, int, int]:
    pixel = imagem.getpixel((int(x * imagem.width), int(y * imagem.height)))
    assert isinstance(pixel, tuple)
    return pixel[:3]


def test_a_placa_mercosul_tem_a_proporcao_a_faixa_azul_e_a_cor_da_categoria() -> None:
    particular = placa.desenhar(Placa("ABC1D23", "mercosul", "particular"))
    comercial = placa.desenhar(Placa("ABC1D23", "mercosul", "comercial"))

    assert particular.width / particular.height == pytest.approx(400 / 130, rel=0.01)
    azul = _cor(particular, 0.05, 0.08)
    assert azul[2] > 120 and azul[0] < 60  # a faixa azul do alto
    assert _cor(particular, 0.03, 0.9) == (255, 255, 255)  # o fundo branco
    tinta_particular = min(particular.convert("RGB").get_flattened_data(), key=sum)
    assert sum(tinta_particular) < 60  # caracteres pretos
    vermelhos = [
        p for p in comercial.convert("RGB").get_flattened_data() if p[0] > 150 and p[1] < 60
    ]
    assert vermelhos  # caracteres vermelhos


def test_a_placa_antiga_cinza_e_a_vermelha() -> None:
    cinza = placa.desenhar(Placa("ABC1234", "antiga", "particular"))
    vermelha = placa.desenhar(Placa("ABC1234", "antiga", "comercial"))

    fundo = _cor(cinza, 0.03, 0.9)
    assert abs(fundo[0] - fundo[1]) < 10 and 120 < fundo[0] < 200  # cinza
    fundo = _cor(vermelha, 0.03, 0.9)
    assert fundo[0] > 150 and fundo[1] < 80  # vermelho


def test_cada_tipo_tem_as_suas_categorias() -> None:
    assert set(CATEGORIAS["mercosul"]) == {
        "particular", "comercial", "oficial", "especial", "colecionador", "diplomatica"
    }  # fmt: skip
    assert set(CATEGORIAS["antiga"]) == {"particular", "comercial", "oficial"}


def test_as_variacoes_imitam_o_recorte_e_se_repetem_com_a_semente() -> None:
    base = placa.desenhar(Placa("ABC1D23", "mercosul", "particular"))

    um = variacoes.variar(base, random.Random(5))
    dois = variacoes.variar(base, random.Random(5))
    outro = variacoes.variar(base, random.Random(6))

    assert um.tobytes() == dois.tobytes()
    assert um.tobytes() != outro.tobytes()
    assert variacoes.LARGURA_MINIMA <= um.width <= variacoes.LARGURA_MAXIMA
    assert um.mode == "RGB"


def test_o_lote_e_repetivel_e_tem_os_rotulos(tmp_path: Path) -> None:
    gerar.gerar(tmp_path / "um", quantas=12, semente=7)
    gerar.gerar(tmp_path / "dois", quantas=12, semente=7)
    gerar.gerar(tmp_path / "tres", quantas=12, semente=8)

    def resumos(pasta: Path) -> list[str]:
        return [
            hashlib.sha256(arquivo.read_bytes()).hexdigest()
            for arquivo in sorted((pasta / "imagens").glob("*.jpg"))
        ]

    assert len(resumos(tmp_path / "um")) == 12
    assert resumos(tmp_path / "um") == resumos(tmp_path / "dois")
    assert resumos(tmp_path / "um") != resumos(tmp_path / "tres")
    linhas = list(csv.DictReader((tmp_path / "um" / "rotulos.csv").open(encoding="utf-8")))
    assert len(linhas) == 12
    assert set(linhas[0]) == {"arquivo", "placa", "tipo", "categoria"}
    for linha in linhas:
        assert normalizar_placa(linha["placa"]) == linha["placa"]
        assert (tmp_path / "um" / linha["arquivo"]).is_file()
    assert {linha["tipo"] for linha in linhas} == {"mercosul", "antiga"}


def test_uma_fonte_ttf_que_nao_existe_e_recusada(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fonte"):
        gerar.gerar(tmp_path, quantas=1, semente=1, fonte_ttf=tmp_path / "nao.ttf")


def test_pela_linha_de_comando(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gerar.principal(["--quantas", "3", "--semente", "2", "--destino", str(tmp_path)])

    assert len(list((tmp_path / "imagens").glob("*.jpg"))) == 3
    assert "3 placas" in capsys.readouterr().out

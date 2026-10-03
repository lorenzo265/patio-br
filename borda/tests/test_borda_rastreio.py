"""Rastreamento (SDD 4.2, D-25): uma leitura por veículo, com um vídeo sintético feito aqui.

O "vídeo" são quadros desenhados no próprio teste (nenhum dado real): cada veículo é um
retângulo de uma cor que anda da esquerda para a direita. O detector e o leitor falsos
reconhecem o veículo e a placa pela cor.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from borda.captura import QuadroNoTempo
from borda.composicao import LeituraDeVeiculo
from borda.leitor.interface import LeituraBruta, Quadro, Regiao
from borda.rastreio import Deteccao, Rastreador

T0 = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
INTERVALO = timedelta(seconds=0.2)  # 5 quadros por segundo
ALTURA, LARGURA = 180, 480
PLACA_DA_COR = {200: "ABC1234", 150: "XYZ9876"}
"""Cor do veículo → placa. A cor 100 é um veículo sem placa legível."""


@dataclass(frozen=True)
class Veiculo:
    cor: int
    primeiro: int
    """Quadro em que entra na imagem."""
    ultimo: int
    linha: int = 60


def _video(veiculos: Sequence[Veiculo], quadros: int) -> list[QuadroNoTempo]:
    video = []
    for indice in range(quadros):
        imagem = np.zeros((ALTURA, LARGURA, 3), dtype=np.uint8)
        for veiculo in veiculos:
            if veiculo.primeiro <= indice <= veiculo.ultimo:
                x = 10 + (indice - veiculo.primeiro) * 25  # anda 25 px por quadro
                imagem[veiculo.linha : veiculo.linha + 60, x : x + 100] = veiculo.cor
        video.append(QuadroNoTempo(momento=T0 + indice * INTERVALO, imagem=imagem))
    return video


class DetectorPorCor:
    """Acha um veículo para cada cor diferente de preto."""

    def __init__(self, confianca: float = 0.9) -> None:
        self.confianca = confianca

    def detectar(self, quadro: Quadro) -> list[Deteccao]:
        deteccoes = []
        for cor in np.unique(quadro[:, :, 0]):
            if cor == 0:
                continue
            linhas, colunas = np.nonzero(quadro[:, :, 0] == cor)
            regiao = Regiao(
                x=int(colunas.min()),
                y=int(linhas.min()),
                largura=int(colunas.max() - colunas.min() + 1),
                altura=int(linhas.max() - linhas.min() + 1),
            )
            deteccoes.append(Deteccao(regiao=regiao, confianca=self.confianca))
        return deteccoes


class LeitorPorCor:
    """Lê a placa pela cor do recorte; a cada 3 leituras de ABC1234, erra um caractere."""

    def __init__(self) -> None:
        self.leituras: Counter[int] = Counter()

    def ler(self, quadro: Quadro) -> list[LeituraBruta]:
        cor = int(quadro[quadro.shape[0] // 2, quadro.shape[1] // 2, 0])
        placa = PLACA_DA_COR.get(cor)
        if placa is None:
            return []
        self.leituras[cor] += 1
        if placa == "ABC1234" and self.leituras[cor] % 3 == 0:
            placa = "ABC1284"
        regiao = Regiao(x=10, y=20, largura=40, altura=12)
        return [LeituraBruta(texto=placa, confianca=0.9, regiao=regiao)]


def _rastreador(quadros_para_sumir: int = 3) -> Rastreador:
    return Rastreador(
        DetectorPorCor(),
        LeitorPorCor(),
        faixa_id="1",
        camera_id="11",
        posicao="frente",
        quadros_para_sumir=quadros_para_sumir,
    )


def _rodar(rastreador: Rastreador, video: list[QuadroNoTempo]) -> list[LeituraDeVeiculo]:
    leituras: list[LeituraDeVeiculo] = []
    for quadro in video:
        leituras.extend(rastreador.processar(quadro))
    return leituras + rastreador.esvaziar()


def test_dois_veiculos_um_depois_do_outro_dao_exatamente_uma_leitura_cada() -> None:
    video = _video([Veiculo(200, 0, 12), Veiculo(150, 20, 30)], quadros=40)

    leituras = _rodar(_rastreador(), video)

    assert [leitura.placa for leitura in leituras] == ["ABC1234", "XYZ9876"]


def test_leitura_sai_quando_o_veiculo_some_e_traz_os_horarios_dele() -> None:
    rastreador = _rastreador(quadros_para_sumir=3)
    video = _video([Veiculo(200, 0, 12)], quadros=20)

    saidas = [(indice, rastreador.processar(q)) for indice, q in enumerate(video)]

    com_leitura = [(indice, lista) for indice, lista in saidas if lista]
    assert len(com_leitura) == 1
    indice, [leitura] = com_leitura[0]
    assert indice == 12 + 3  # sumiu no quadro 13 e não voltou por 3 quadros
    assert (leitura.inicio, leitura.fim) == (T0, T0 + 12 * INTERVALO)
    assert (leitura.faixa_id, leitura.camera_id, leitura.posicao) == ("1", "11", "frente")


def test_votacao_corrige_os_quadros_em_que_o_leitor_errou() -> None:
    leituras = _rodar(_rastreador(), _video([Veiculo(200, 0, 11)], quadros=20))

    assert [leitura.placa for leitura in leituras] == ["ABC1234"]
    assert leituras[0].quadros == 8  # 12 quadros, 4 lidos como ABC1284
    assert leituras[0].confianca == pytest.approx(0.9 * 8 / 12)


def test_dois_veiculos_ao_mesmo_tempo_em_lugares_diferentes_nao_se_misturam() -> None:
    video = _video([Veiculo(200, 0, 10, linha=10), Veiculo(150, 2, 12, linha=110)], quadros=20)

    leituras = _rodar(_rastreador(), video)

    assert sorted(leitura.placa or "" for leitura in leituras) == ["ABC1234", "XYZ9876"]


def test_veiculo_sem_placa_legivel_vira_leitura_sem_placa() -> None:
    leituras = _rodar(_rastreador(), _video([Veiculo(100, 0, 8)], quadros=15))

    assert [(leitura.placa, leitura.quadros) for leitura in leituras] == [(None, 0)]


def test_mancha_que_aparece_num_quadro_so_nao_vira_veiculo() -> None:
    assert _rodar(_rastreador(), _video([Veiculo(100, 3, 3)], quadros=10)) == []


def test_leitura_leva_o_recorte_da_placa_para_a_foto() -> None:
    leituras = _rodar(_rastreador(), _video([Veiculo(200, 0, 8)], quadros=15))

    recorte = leituras[0].recorte
    assert recorte is not None
    assert recorte.shape == (12, 40, 3)
    assert int(recorte[0, 0, 0]) == 200


def test_veiculo_ainda_na_imagem_sai_ao_esvaziar() -> None:
    rastreador = _rastreador()
    for quadro in _video([Veiculo(150, 0, 30)], quadros=6):
        assert rastreador.processar(quadro) == []

    assert [leitura.placa for leitura in rastreador.esvaziar()] == ["XYZ9876"]


def test_deteccao_de_confianca_baixa_segue_o_veiculo_mas_nao_cria_outro() -> None:
    # Como no ByteTrack: no meio da passagem o detector fica em dúvida (0,3) e o veículo segue.
    detector = DetectorPorCor()
    rastreador = Rastreador(
        detector, LeitorPorCor(), faixa_id="1", camera_id="11", posicao="frente"
    )
    video = _video([Veiculo(150, 0, 12)], quadros=20)
    leituras: list[LeituraDeVeiculo] = []
    for indice, quadro in enumerate(video):
        detector.confianca = 0.3 if 4 <= indice <= 8 else 0.9
        leituras.extend(rastreador.processar(quadro))
    leituras.extend(rastreador.esvaziar())

    assert [leitura.placa for leitura in leituras] == ["XYZ9876"]

    so_baixa = Rastreador(
        DetectorPorCor(confianca=0.3),
        LeitorPorCor(),
        faixa_id="1",
        camera_id="11",
        posicao="frente",
    )
    assert _rodar(so_baixa, video) == []


def test_veiculo_que_entra_longe_logo_depois_de_outro_sair_e_outro_veiculo() -> None:
    # O primeiro some no quadro 6; no 7, outro aparece do outro lado: não é o mesmo veículo.
    video = _video([Veiculo(200, 0, 5, linha=10), Veiculo(150, 7, 14, linha=110)], quadros=22)

    leituras = _rodar(_rastreador(), video)

    assert [leitura.placa for leitura in leituras] == ["ABC1234", "XYZ9876"]

"""O programa da caixa (SDD 7.4): ativa, baixa a configuração, lê as câmeras e guarda passagens."""

import io
import json
import threading
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pytest

from borda.ativacao import CaixaAtivada, ChaveRecusadaError
from borda.caixa import baixar_com_paciencia, principal
from borda.envio import FilaDeEnvio
from borda.leitor.interface import LeituraBruta, Quadro, Regiao
from borda.rastreio import Deteccao

pytestmark = pytest.mark.integracao  # a chave e a fila ficam no disco

NUVEM = "http://nuvem.example"
CODIGO = "AAAA-BBBB-CCCC"
CHAVE = "chave-inventada-7"
SENHA = "s3nh4:inventada"

CONFIGURACAO: dict[str, Any] = {
    "caixa_id": "7",
    "site_id": "3",
    "faixas": [
        {
            "id": "11",
            "nome": "Entrada 1",
            "sentido": "entrada",
            "cameras": [
                {
                    "id": "21",
                    "nome": "frente",
                    "posicao": "frente",
                    "endereco": "rtsp://10.0.0.1:554/1",
                    "login": "leitura",
                    "senha": SENHA,
                },
                {
                    "id": "23",
                    "nome": "contexto",
                    "posicao": "contexto",
                    "endereco": "rtsp://10.0.0.3:554/1",
                    "login": "leitura",
                    "senha": SENHA,
                },
            ],
        },
    ],
}


class NuvemFalsa:
    def __init__(self) -> None:
        self.respostas_da_configuracao: list[int] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        if pedido.url.path == "/api/borda/ativar":
            if json.loads(pedido.content)["codigo"] != CODIGO:
                return httpx.Response(401, json={"detail": "código inválido"})
            return httpx.Response(201, json={"caixa_id": "7", "site_id": "3", "chave": CHAVE})
        if pedido.url.path == "/api/borda/configuracao":
            if self.respostas_da_configuracao:
                return httpx.Response(self.respostas_da_configuracao.pop(0))
            if pedido.headers.get("authorization") != f"Bearer {CHAVE}":
                return httpx.Response(401, json={"detail": "caixa não identificada"})
            return httpx.Response(200, json=CONFIGURACAO)
        return httpx.Response(503)  # o envio da fila: a nuvem "fora do ar", a passagem fica


class DetectorDeTudo:
    """Vê um veículo onde houver pixel aceso."""

    def detectar(self, quadro: Quadro) -> list[Deteccao]:
        linhas, colunas = np.nonzero(quadro[:, :, 0])
        if len(linhas) == 0:
            return []
        regiao = Regiao(
            x=int(colunas.min()),
            y=int(linhas.min()),
            largura=int(colunas.max() - colunas.min() + 1),
            altura=int(linhas.max() - linhas.min() + 1),
        )
        return [Deteccao(regiao=regiao, confianca=0.9)]


class LeitorFixo:
    def ler(self, quadro: Quadro) -> list[LeituraBruta]:
        return [LeituraBruta("ABC1D23", 0.95, Regiao(x=0, y=0, largura=8, altura=4))]


class VideoFalso:
    def __init__(self, imagens: list[Quadro]) -> None:
        self.imagens = imagens

    def ler(self) -> Quadro | None:
        return self.imagens.pop(0) if self.imagens else None

    def fechar(self) -> None:
        pass


class CamerasFalsas:
    """A câmera da frente passa um veículo e cai; ao tentar reabrir, a caixa é desligada."""

    def __init__(self, parar: threading.Event) -> None:
        self.parar = parar
        self.abertas: list[str] = []

    def abrir(self, endereco: str) -> VideoFalso | None:
        self.abertas.append(endereco)
        if len(self.abertas) > 1:
            self.parar.set()
            return None
        imagens = []
        for indice in range(8):
            imagem = np.zeros((60, 120, 3), dtype=np.uint8)
            if indice < 5:
                imagem[10:40, 10 + indice * 5 : 60 + indice * 5] = 200  # um veículo passando
            imagens.append(imagem)
        return VideoFalso(imagens)


@pytest.fixture
def nuvem() -> NuvemFalsa:
    return NuvemFalsa()


@pytest.fixture
def cliente(nuvem: NuvemFalsa) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(nuvem))


def _caixa(argv: list[str], cliente: httpx.Client, **extras: Any) -> tuple[int, str]:
    saida = io.StringIO()
    codigo = principal(argv, cliente=cliente, saida=saida, **extras)
    return codigo, saida.getvalue()


def _ativar(cliente: httpx.Client, pasta: Path) -> None:
    codigo, saida = _caixa(
        ["ativar", "--nuvem", NUVEM, "--codigo", CODIGO, "--pasta", str(pasta)], cliente
    )
    assert codigo == 0, saida


def test_ativar_guarda_a_chave_e_diz_o_proximo_passo(cliente: httpx.Client, tmp_path: Path) -> None:
    codigo, saida = _caixa(
        ["ativar", "--nuvem", NUVEM, "--codigo", CODIGO, "--pasta", str(tmp_path)], cliente
    )

    assert codigo == 0
    assert "caixa rodar" in saida
    assert CHAVE not in saida
    assert json.loads((tmp_path / "caixa.json").read_text(encoding="utf-8"))["chave"] == CHAVE


def test_ativar_com_codigo_recusado_explica(cliente: httpx.Client, tmp_path: Path) -> None:
    codigo, saida = _caixa(
        ["ativar", "--nuvem", NUVEM, "--codigo", "XXXX-XXXX-XXXX", "--pasta", str(tmp_path)],
        cliente,
    )

    assert codigo == 1
    assert "código" in saida
    assert not (tmp_path / "caixa.json").exists()


def test_rodar_sem_ativar_explica(cliente: httpx.Client, tmp_path: Path) -> None:
    codigo, saida = _caixa(["rodar", "--pasta", str(tmp_path)], cliente)

    assert codigo == 1
    assert "caixa ativar" in saida


def test_rodar_com_a_chave_revogada_explica(cliente: httpx.Client, tmp_path: Path) -> None:
    _ativar(cliente, tmp_path)
    caixa = json.loads((tmp_path / "caixa.json").read_text(encoding="utf-8"))
    caixa["chave"] = "chave-revogada"
    (tmp_path / "caixa.json").write_text(json.dumps(caixa), encoding="utf-8")

    codigo, saida = _caixa(["rodar", "--pasta", str(tmp_path)], cliente, parar=threading.Event())

    assert codigo == 1
    assert "ative de novo" in saida


def test_rodar_le_as_cameras_de_placa_e_guarda_a_passagem(
    cliente: httpx.Client, tmp_path: Path
) -> None:
    _ativar(cliente, tmp_path)
    parar = threading.Event()
    cameras = CamerasFalsas(parar)

    codigo, saida = _caixa(
        ["rodar", "--pasta", str(tmp_path), "--por-segundo", "1000"],
        cliente,
        parar=parar,
        abrir=cameras.abrir,
        carregar_modelos=lambda: (DetectorDeTudo(), LeitorFixo()),
    )

    assert codigo == 0, saida
    # Só a câmera de placa, com o login e a senha da configuração (codificados no endereço).
    assert set(cameras.abertas) == {"rtsp://leitura:s3nh4%3Ainventada@10.0.0.1:554/1"}
    assert SENHA not in saida
    fila = FilaDeEnvio(tmp_path / "fila.sqlite")
    item = fila.proxima()
    fila.fechar()
    assert item is not None
    assert [placa.placa for placa in item.passagem.placas] == ["ABC1D23"]
    assert item.passagem.caixa_id == "7"


def test_nuvem_fora_do_ar_no_inicio_tenta_de_novo_esperando_mais(
    cliente: httpx.Client, nuvem: NuvemFalsa
) -> None:
    nuvem.respostas_da_configuracao = [503, 503]
    esperas: list[float] = []
    caixa = CaixaAtivada(nuvem=NUVEM, caixa_id="7", site_id="3", chave=CHAVE)

    configuracao = baixar_com_paciencia(
        cliente, caixa, parar=threading.Event(), dormir=esperas.append
    )

    assert configuracao is not None
    assert esperas == [1, 2]


def test_chave_recusada_no_inicio_nao_fica_tentando(cliente: httpx.Client) -> None:
    caixa = CaixaAtivada(nuvem=NUVEM, caixa_id="7", site_id="3", chave="chave-revogada")

    with pytest.raises(ChaveRecusadaError):
        baixar_com_paciencia(cliente, caixa, parar=threading.Event(), dormir=lambda _s: None)


def test_desligada_enquanto_espera_a_nuvem(cliente: httpx.Client, nuvem: NuvemFalsa) -> None:
    nuvem.respostas_da_configuracao = [503] * 10
    parar = threading.Event()
    caixa = CaixaAtivada(nuvem=NUVEM, caixa_id="7", site_id="3", chave=CHAVE)

    configuracao = baixar_com_paciencia(
        cliente, caixa, parar=parar, dormir=lambda _segundos: parar.set()
    )

    assert configuracao is None

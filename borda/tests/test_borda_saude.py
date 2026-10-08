"""A saúde da caixa (SDD 7.4, D-65): as câmeras, a máquina e o envio a cada minuto."""

import json
import threading
from collections import namedtuple
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

import httpx
import numpy as np
import pytest

from borda import saude
from borda.captura import FonteDeMemoria, QuadroNoTempo
from borda.envio import ContagemDaFila, Nuvem, Resultado
from borda.saude import Maquina, MedidorDasCameras, Pulso
from contratos.saude import Saude

AGORA = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)
ENDERECO = "http://nuvem.example"
CHAVE = "chave-inventada-da-caixa"
IMAGEM = np.zeros((4, 4, 3), dtype=np.uint8)

Sensor = namedtuple("Sensor", "label current high critical")


def _segundos(segundos: float) -> datetime:
    return AGORA + timedelta(seconds=segundos)


def _saude() -> Saude:
    return saude.montar_saude(
        caixa_id="7",
        site_id="3",
        versao_leitor="v0",
        medidor=MedidorDasCameras(["21"]),
        fila=ContagemDaFila(passagens=1, fotos=2, recusadas=0),
        maquina=Maquina(cpu=10, temperatura=None, memoria=20, disco=30),
        agora=AGORA,
    )


# --- As câmeras -----------------------------------------------------------------------------


def test_camera_que_nunca_mandou_quadro_nao_esta_no_ar() -> None:
    medidor = MedidorDasCameras(["21", "22"])

    medidas = medidor.medir(AGORA)

    assert [(m.camera_id, m.no_ar, m.quadros_por_segundo, m.ultimo_quadro) for m in medidas] == [
        ("21", False, 0, None),
        ("22", False, 0, None),
    ]


def test_conta_os_quadros_dos_ultimos_10_segundos() -> None:
    medidor = MedidorDasCameras(["21", "22"])
    for indice in range(75):  # 15 s a 5 quadros por segundo
        medidor.registrar("21", _segundos(-14.9 + indice * 0.2))
    medidor.registrar("22", _segundos(-3))

    camera, outra = medidor.medir(AGORA)

    assert camera.no_ar
    assert camera.quadros_por_segundo == 5.0
    assert camera.ultimo_quadro == _segundos(-14.9 + 74 * 0.2)
    assert (outra.no_ar, outra.quadros_por_segundo) == (True, 0.1)


def test_o_quadro_de_10_segundos_atras_ja_nao_conta_nos_quadros_por_segundo() -> None:
    medidor = MedidorDasCameras(["21"])
    medidor.registrar("21", _segundos(-10))
    medidor.registrar("21", _segundos(-9.999))

    (camera,) = medidor.medir(AGORA)

    assert camera.quadros_por_segundo == 0.1


def test_camera_sem_quadro_ha_mais_de_10_segundos_saiu_do_ar() -> None:
    medidor = MedidorDasCameras(["21", "22"])
    medidor.registrar("21", _segundos(-10))
    medidor.registrar("22", _segundos(-10.001))

    no_limite, fora = medidor.medir(AGORA)

    assert no_limite.no_ar
    assert not fora.no_ar
    assert fora.ultimo_quadro == _segundos(-10.001)


def test_a_conta_segue_a_cada_medida() -> None:
    medidor = MedidorDasCameras(["21"])
    medidor.registrar("21", _segundos(-1))
    medidor.medir(AGORA)

    (depois,) = medidor.medir(_segundos(60))

    assert (depois.no_ar, depois.quadros_por_segundo) == (False, 0)
    assert depois.ultimo_quadro == _segundos(-1)


def test_a_fonte_medida_conta_cada_quadro_que_passa() -> None:
    medidor = MedidorDasCameras(["21"])
    quadros = [QuadroNoTempo(_segundos(-1 + indice * 0.25), IMAGEM) for indice in range(4)]
    fonte = saude.FonteMedida(FonteDeMemoria(quadros), "21", medidor)

    passados = list(fonte.quadros())

    assert passados == quadros
    (camera,) = medidor.medir(AGORA)
    assert (camera.quadros_por_segundo, camera.ultimo_quadro) == (0.4, _segundos(-0.25))


# --- A máquina ------------------------------------------------------------------------------


def test_a_temperatura_e_a_do_sensor_mais_quente() -> None:
    leituras = {
        "acpitz": [Sensor("", 41.0, None, None)],
        "coretemp": [Sensor("Package id 0", 58.0, 100, 100), Sensor("Core 0", 62.5, 100, 100)],
    }

    assert saude.temperatura_mais_quente(leituras) == 62.5


def test_sem_sensor_a_temperatura_fica_vazia() -> None:
    assert saude.temperatura_mais_quente({}) is None
    assert saude.temperatura_mais_quente({"acpitz": []}) is None


@pytest.mark.parametrize("estranha", [-60.1, 150.1, float("nan")])
def test_leitura_impossivel_de_um_sensor_fica_de_fora(estranha: float) -> None:
    leituras = {"x": [Sensor("", estranha, None, None), Sensor("", 55.0, None, None)]}

    assert saude.temperatura_mais_quente(leituras) == 55.0


@pytest.mark.parametrize("extremo", [-60.0, 150.0])
def test_os_extremos_do_contrato_valem(extremo: float) -> None:
    assert saude.temperatura_mais_quente({"x": [Sensor("", extremo, None, None)]}) == extremo


@pytest.mark.integracao  # lê o disco da pasta
def test_mede_a_maquina_de_verdade(tmp_path: Path) -> None:
    maquina = saude.medir_a_maquina(tmp_path)

    for uso in (maquina.cpu, maquina.memoria, maquina.disco):
        assert 0 <= uso <= 100
    assert maquina.temperatura is None or -60 <= maquina.temperatura <= 150


@pytest.mark.integracao  # lê o disco da pasta
def test_a_maquina_le_a_temperatura_dos_sensores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def ler() -> dict[str, list[Sensor]]:
        return {"coretemp": [Sensor("Package id 0", 47.0, 100, 100)]}

    monkeypatch.setattr(saude.psutil, "sensors_temperatures", ler, raising=False)

    assert saude.medir_a_maquina(tmp_path).temperatura == 47.0


@pytest.mark.integracao  # lê o disco da pasta
def test_maquina_sem_sensores_de_temperatura_mede_o_resto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def quebrar() -> dict[str, list[Sensor]]:
        raise OSError("sem acesso aos sensores")

    monkeypatch.setattr(saude.psutil, "sensors_temperatures", quebrar, raising=False)

    assert saude.medir_a_maquina(tmp_path).temperatura is None


# --- A saúde --------------------------------------------------------------------------------


def test_monta_a_saude_com_tudo() -> None:
    medidor = MedidorDasCameras(["21"])
    medidor.registrar("21", _segundos(-1))

    montada = saude.montar_saude(
        caixa_id="7",
        site_id="3",
        versao_leitor="v0",
        medidor=medidor,
        fila=ContagemDaFila(passagens=4, fotos=5, recusadas=1),
        maquina=Maquina(cpu=12.5, temperatura=60.0, memoria=40.0, disco=8.0),
        agora=AGORA,
    )

    assert montada.model_dump(mode="json") == {
        "versao_contrato": 1,
        "caixa_id": "7",
        "site_id": "3",
        "momento": "2026-10-06T14:00:00Z",
        "versao_programa": version("patio-borda"),
        "versao_leitor": "v0",
        "cpu": 12.5,
        "temperatura": 60.0,
        "memoria": 40.0,
        "disco": 8.0,
        "cameras": [
            {
                "camera_id": "21",
                "no_ar": True,
                "quadros_por_segundo": 0.1,
                "ultimo_quadro": "2026-10-06T13:59:59Z",
            }
        ],
        "fila": {"passagens": 4, "fotos": 5, "recusadas": 1},
    }


# --- O envio --------------------------------------------------------------------------------


class NuvemDaSaude:
    def __init__(self, codigos: list[int] | None = None) -> None:
        self.codigos = codigos or []
        self.pedidos: list[httpx.Request] = []
        self.rede_caida = False

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if self.rede_caida:
            raise httpx.ConnectError("a internet caiu", request=pedido)
        return httpx.Response(self.codigos.pop(0) if self.codigos else 204)


def _nuvem(falsa: NuvemDaSaude) -> Nuvem:
    return Nuvem(ENDERECO, CHAVE, cliente=httpx.Client(transport=httpx.MockTransport(falsa)))


def test_manda_a_saude_com_a_chave() -> None:
    falsa = NuvemDaSaude()
    enviada = _saude()

    resposta = _nuvem(falsa).enviar_saude(enviada)

    assert resposta.resultado is Resultado.ACEITA
    (pedido,) = falsa.pedidos
    assert (pedido.method, str(pedido.url)) == ("POST", f"{ENDERECO}/api/borda/saude")
    assert pedido.headers["authorization"] == f"Bearer {CHAVE}"
    assert pedido.headers["content-type"] == "application/json"
    assert Saude.model_validate(json.loads(pedido.content)) == enviada


@pytest.mark.parametrize(
    ("codigo", "resultado"),
    [
        (200, Resultado.ACEITA),
        (204, Resultado.ACEITA),
        (403, Resultado.RECUSADA),
        (422, Resultado.RECUSADA),
        (401, Resultado.DE_NOVO),
        (503, Resultado.DE_NOVO),
    ],
)
def test_o_que_a_nuvem_responde_a_saude(codigo: int, resultado: Resultado) -> None:
    assert _nuvem(NuvemDaSaude([codigo])).enviar_saude(_saude()).resultado is resultado


def test_sem_internet_a_saude_nao_vai() -> None:
    falsa = NuvemDaSaude()
    falsa.rede_caida = True

    resposta = _nuvem(falsa).enviar_saude(_saude())

    assert (resposta.resultado, resposta.codigo) == (Resultado.DE_NOVO, None)


def test_o_pulso_manda_logo_e_depois_a_cada_minuto_sem_reenviar() -> None:
    falsa = NuvemDaSaude([503, 204, 204])
    parar = threading.Event()
    esperas: list[float] = []

    def dormir(segundos: float) -> bool:
        esperas.append(segundos)
        if len(esperas) == 2:
            parar.set()
        return parar.is_set()

    Pulso(_saude, _nuvem(falsa), parar=parar, dormir=dormir).rodar()

    # A primeira falhou e não foi de novo: a seguinte é outra saúde, um minuto depois.
    assert len(falsa.pedidos) == 2
    assert esperas == [60, 60]


def test_um_erro_ao_montar_a_saude_nao_para_o_pulso() -> None:
    falsa = NuvemDaSaude()
    parar = threading.Event()
    montagens: list[int] = []

    def montar() -> Saude:
        montagens.append(1)
        if len(montagens) == 1:
            raise RuntimeError("o psutil falhou")
        return _saude()

    def dormir(_segundos: float) -> bool:
        if len(montagens) == 2:
            parar.set()
        return parar.is_set()

    Pulso(montar, _nuvem(falsa), parar=parar, dormir=dormir).rodar()

    assert len(montagens) == 2
    assert len(falsa.pedidos) == 1


def test_a_caixa_ja_desligada_manda_uma_saude_e_para() -> None:
    falsa = NuvemDaSaude()
    parar = threading.Event()
    parar.set()

    Pulso(_saude, _nuvem(falsa), parar=parar).rodar()

    assert len(falsa.pedidos) == 1

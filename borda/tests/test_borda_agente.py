"""Agente da caixa (SDD 7.4): junta rastreamento, composição e fila numa passagem por veículo."""

import io
import logging
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from borda.agente import Agente, CameraDoAgente, ConfiguracaoDoAgente, rodar, rodar_ao_vivo
from borda.captura import FonteDeMemoria, QuadroNoTempo
from borda.composicao import LeituraDeVeiculo
from borda.envio import FilaDeEnvio
from nuvem.armazenamento import validar_ref  # a regra do ref é da nuvem

pytestmark = pytest.mark.integracao  # a fila fica num arquivo SQLite

T0 = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
PRETO = np.zeros((4, 4, 3), dtype=np.uint8)

CONFIGURACAO_DA_NUVEM: dict[str, Any] = {
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
                    "endereco": "rtsp://10.0.0.1/1",
                    "login": "leitura",
                    "senha": "inventada",
                },
                {
                    "id": "22",
                    "nome": "trás",
                    "posicao": "tras",
                    "endereco": "rtsp://10.0.0.2/1",
                    "login": "leitura",
                    "senha": "inventada",
                },
                {
                    "id": "23",
                    "nome": "contexto",
                    "posicao": "contexto",
                    "endereco": "rtsp://10.0.0.3/1",
                    "login": "leitura",
                    "senha": "inventada",
                },
            ],
        },
        {
            "id": "12",
            "nome": "Saída 1",
            "sentido": "saida",
            "cameras": [
                {
                    "id": "24",
                    "nome": "trás",
                    "posicao": "tras",
                    "endereco": "rtsp://10.0.0.4/1",
                    "login": "leitura",
                    "senha": "inventada",
                },
            ],
        },
    ],
}


class RastreadorRoteirizado:
    """Devolve, no quadro de cada momento, as leituras do roteiro (sem visão computacional)."""

    def __init__(self, camera: CameraDoAgente, roteiro: dict[datetime, list[str | None]]) -> None:
        self.camera = camera
        self.roteiro = roteiro
        self.quadros = 0

    def _leitura(self, placa: str | None, momento: datetime) -> LeituraDeVeiculo:
        recorte = np.full((12, 40, 3), 200, dtype=np.uint8) if placa else None
        return LeituraDeVeiculo(
            faixa_id=self.camera.faixa_id,
            camera_id=self.camera.id,
            posicao="frente" if self.camera.posicao == "frente" else "tras",
            placa=placa,
            confianca=0.9 if placa else 0.0,
            quadros=5 if placa else 0,
            inicio=momento - timedelta(seconds=3),
            fim=momento,
            recorte=recorte,
        )

    def processar(self, quadro: QuadroNoTempo) -> list[LeituraDeVeiculo]:
        self.quadros += 1
        return [self._leitura(p, quadro.momento) for p in self.roteiro.get(quadro.momento, [])]

    def esvaziar(self) -> list[LeituraDeVeiculo]:
        return []


@pytest.fixture
def configuracao() -> ConfiguracaoDoAgente:
    return ConfiguracaoDoAgente.de_json(CONFIGURACAO_DA_NUVEM)


@pytest.fixture
def fila(tmp_path: Path) -> Iterator[FilaDeEnvio]:
    fila = FilaDeEnvio(tmp_path / "fila.sqlite")
    yield fila
    fila.fechar()


def _agente(
    configuracao: ConfiguracaoDoAgente,
    fila: FilaDeEnvio,
    roteiros: dict[str, dict[datetime, list[str | None]]],
) -> tuple[Agente, dict[str, RastreadorRoteirizado]]:
    criados: dict[str, RastreadorRoteirizado] = {}

    def criar(camera: CameraDoAgente) -> RastreadorRoteirizado:
        criados[camera.id] = RastreadorRoteirizado(camera, roteiros.get(camera.id, {}))
        return criados[camera.id]

    return Agente(configuracao, fila, criar_rastreador=criar), criados


def _quadro(segundos: float) -> QuadroNoTempo:
    return QuadroNoTempo(momento=T0 + timedelta(seconds=segundos), imagem=PRETO)


def test_le_a_configuracao_que_a_nuvem_manda(configuracao: ConfiguracaoDoAgente) -> None:
    assert (configuracao.caixa_id, configuracao.site_id) == ("7", "3")
    assert [(f.id, f.sentido) for f in configuracao.faixas] == [("11", "entrada"), ("12", "saida")]
    assert [(c.id, c.faixa_id, c.posicao) for c in configuracao.cameras] == [
        ("21", "11", "frente"),
        ("22", "11", "tras"),
        ("23", "11", "contexto"),
        ("24", "12", "tras"),
    ]


def test_cavalo_e_reboque_viram_uma_passagem_com_as_fotos_na_fila(
    configuracao: ConfiguracaoDoAgente, fila: FilaDeEnvio
) -> None:
    roteiros = {"21": {T0: ["ABC1D23"]}, "22": {T0 + timedelta(seconds=10): ["XYZ9876"]}}
    agente, _ = _agente(configuracao, fila, roteiros)

    agente.processar("21", _quadro(0))
    guardadas = agente.processar("22", _quadro(10))

    (passagem,) = guardadas
    assert (passagem.caixa_id, passagem.site_id, passagem.faixa_id, passagem.sentido) == (
        "7",
        "3",
        "11",
        "entrada",
    )
    assert [(p.placa, p.papel, p.camera_id) for p in passagem.placas] == [
        ("ABC1D23", "cavalo", "21"),
        ("XYZ9876", "reboque", "22"),
    ]
    assert [(f.tipo, f.camera_id) for f in passagem.fotos] == [("placa", "21"), ("placa", "22")]
    na_fila = fila.proxima()
    assert na_fila is not None
    assert na_fila.passagem == passagem
    assert sorted(na_fila.fotos) == sorted(f.ref for f in passagem.fotos)
    for conteudo in na_fila.fotos.values():
        with Image.open(io.BytesIO(conteudo)) as foto:
            assert (foto.format, foto.size) == ("JPEG", (40, 12))


def test_ref_da_foto_segue_a_regra_da_nuvem(
    configuracao: ConfiguracaoDoAgente, fila: FilaDeEnvio
) -> None:
    agente, _ = _agente(configuracao, fila, {"24": {T0: ["ABC1D23"]}})

    (passagem,) = agente.processar("24", _quadro(0))

    validar_ref(passagem.fotos[0].ref)
    assert passagem.fotos[0].ref.startswith("2026/10/05/")


def test_cada_passagem_tem_um_id_novo_e_a_versao_do_leitor(
    configuracao: ConfiguracaoDoAgente, fila: FilaDeEnvio
) -> None:
    roteiro = {T0: ["ABC1D23"], T0 + timedelta(seconds=60): ["XYZ9876"]}
    agente, _ = _agente(configuracao, fila, {"24": roteiro})

    primeira = agente.processar("24", _quadro(0))
    segunda = agente.processar("24", _quadro(60))

    assert primeira[0].id != segunda[0].id
    assert primeira[0].versao_leitor == "v0"


def test_cavalo_sozinho_sai_quando_a_janela_acaba(
    configuracao: ConfiguracaoDoAgente, fila: FilaDeEnvio
) -> None:
    agente, _ = _agente(configuracao, fila, {"21": {T0: ["ABC1D23"]}})
    agente.processar("21", _quadro(0))

    depois = agente.processar("21", _quadro(31))

    assert [[p.placa for p in passagem.placas] for passagem in depois] == [["ABC1D23"]]


def test_camera_de_contexto_nao_le_placa(
    configuracao: ConfiguracaoDoAgente, fila: FilaDeEnvio
) -> None:
    agente, criados = _agente(configuracao, fila, {})

    assert agente.processar("23", _quadro(0)) == []
    assert "23" not in criados


def test_veiculo_sem_placa_vira_passagem_vazia_sem_foto(
    configuracao: ConfiguracaoDoAgente, fila: FilaDeEnvio
) -> None:
    agente, _ = _agente(configuracao, fila, {"24": {T0: [None]}})

    (passagem,) = agente.processar("24", _quadro(0))

    assert (passagem.placas, passagem.fotos) == ((), ())


def test_encerrar_manda_o_que_ainda_esperava(
    configuracao: ConfiguracaoDoAgente, fila: FilaDeEnvio
) -> None:
    agente, _ = _agente(configuracao, fila, {"21": {T0: ["ABC1D23"]}})
    agente.processar("21", _quadro(0))

    assert [p.placas[0].placa for p in agente.encerrar()] == ["ABC1D23"]
    assert fila.pendentes() == 1


def test_rodar_junta_as_cameras_na_ordem_do_tempo(
    configuracao: ConfiguracaoDoAgente, fila: FilaDeEnvio
) -> None:
    roteiros = {"21": {T0: ["ABC1D23"]}, "22": {T0 + timedelta(seconds=10): ["XYZ9876"]}}
    agente, criados = _agente(configuracao, fila, roteiros)
    fontes = {
        "22": FonteDeMemoria([_quadro(s) for s in (5, 10)]),
        "21": FonteDeMemoria([_quadro(s) for s in (0, 6)]),
    }

    passagens = rodar(agente, fontes)

    assert [[p.placa for p in passagem.placas] for passagem in passagens] == [
        ["ABC1D23", "XYZ9876"]
    ]
    assert (criados["21"].quadros, criados["22"].quadros) == (2, 2)


def test_camera_que_nao_esta_na_configuracao_e_recusada(
    configuracao: ConfiguracaoDoAgente, fila: FilaDeEnvio
) -> None:
    agente, _ = _agente(configuracao, fila, {})

    with pytest.raises(KeyError, match="99"):
        agente.processar("99", _quadro(0))


# --- Ao vivo (D-30) ------------------------------------------------------------------------------


class AgenteQueAnota:
    """Anota os quadros que recebe; liga ``parar`` depois de ``ate`` quadros."""

    def __init__(
        self,
        parar: threading.Event,
        ate: int,
        *,
        falhar_no: int | None = None,
        segurar_o_primeiro: threading.Event | None = None,
    ) -> None:
        self.parar = parar
        self.ate = ate
        self.falhar_no = falhar_no
        self.segurar_o_primeiro = segurar_o_primeiro
        self.recebidos: list[str] = []
        self.encerrado = 0

    def processar(self, camera_id: str, quadro: QuadroNoTempo) -> list[object]:
        if self.segurar_o_primeiro is not None and not self.recebidos:
            self.segurar_o_primeiro.wait(5)
        self.recebidos.append(camera_id)
        if len(self.recebidos) >= self.ate:
            self.parar.set()
        if self.falhar_no == len(self.recebidos):
            raise RuntimeError("um quadro estragado")
        return []

    def encerrar(self) -> list[object]:
        self.encerrado += 1
        return []


class CameraCaida:
    """Não entrega nada até a caixa desligar (está esperando para reabrir)."""

    def __init__(self, parar: threading.Event) -> None:
        self.parar = parar

    def quadros(self) -> Iterator[QuadroNoTempo]:
        self.parar.wait()
        yield from ()


class CameraQueDesliga:
    """Entrega os quadros e liga ``parar`` logo depois (a caixa recebeu o sinal de término)."""

    def __init__(
        self, quantos: int, parar: threading.Event, depois: threading.Event | None = None
    ) -> None:
        self.quantos = quantos
        self.parar = parar
        self.depois = depois

    def quadros(self) -> Iterator[QuadroNoTempo]:
        for indice in range(self.quantos):
            yield _quadro(indice)
        if self.depois is not None:
            self.depois.set()
        self.parar.set()


def _ao_vivo(agente: AgenteQueAnota, fontes: dict[str, Any], **extras: Any) -> None:
    # Numa linha à parte, com prazo: se o código travar, o teste falha em vez de ficar parado.
    linha = threading.Thread(
        target=rodar_ao_vivo, args=(agente, fontes, agente.parar), kwargs=extras
    )
    linha.start()
    linha.join(timeout=10)
    assert not linha.is_alive(), "rodar_ao_vivo não terminou"


def test_ao_vivo_processa_os_quadros_de_todas_as_cameras_e_encerra() -> None:
    parar = threading.Event()
    agente = AgenteQueAnota(parar, ate=6)
    fontes = {
        "21": FonteDeMemoria([_quadro(i) for i in range(3)]),
        "22": FonteDeMemoria([_quadro(i) for i in range(3)]),
    }

    _ao_vivo(agente, fontes)

    assert sorted(agente.recebidos) == ["21"] * 3 + ["22"] * 3
    assert agente.encerrado == 1


def test_ao_vivo_uma_camera_caida_nao_segura_as_outras() -> None:
    parar = threading.Event()
    agente = AgenteQueAnota(parar, ate=3)

    _ao_vivo(
        agente, {"21": CameraCaida(parar), "22": FonteDeMemoria([_quadro(i) for i in range(3)])}
    )

    assert agente.recebidos == ["22"] * 3


def test_ao_vivo_um_quadro_com_erro_nao_para_a_caixa(caplog: pytest.LogCaptureFixture) -> None:
    parar = threading.Event()
    agente = AgenteQueAnota(parar, ate=3, falhar_no=1)

    with caplog.at_level(logging.ERROR):
        _ao_vivo(agente, {"21": FonteDeMemoria([_quadro(i) for i in range(3)])})

    assert agente.recebidos == ["21"] * 3
    assert "quadro estragado" in caplog.text


def test_ao_desligar_processa_o_que_ja_tinha_chegado() -> None:
    parar = threading.Event()
    agente = AgenteQueAnota(parar, ate=1000)

    _ao_vivo(agente, {"21": CameraQueDesliga(5, parar)})

    assert agente.recebidos == ["21"] * 5
    assert agente.encerrado == 1


def test_ao_vivo_descarta_o_que_nao_cabe_na_espera(caplog: pytest.LogCaptureFixture) -> None:
    # O agente fica preso no primeiro quadro enquanto a câmera manda os outros.
    parar = threading.Event()
    camera_terminou = threading.Event()
    agente = AgenteQueAnota(parar, ate=1000, segurar_o_primeiro=camera_terminou)

    with caplog.at_level(logging.WARNING):
        _ao_vivo(agente, {"21": CameraQueDesliga(20, parar, depois=camera_terminou)}, espera=2)

    assert len(agente.recebidos) < 20
    assert "descartad" in caplog.text

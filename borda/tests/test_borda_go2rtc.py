"""O go2rtc da caixa (SDD 7.4, D-66): o agente cadastra cada câmera e lê o vídeo de lá."""

import logging

import httpx
import pytest

from borda.go2rtc import Go2rtc

API = "http://go2rtc:1984"
ORIGEM = "rtsp://leitura:s3nh4-inventada@10.0.0.1:554/stream1"
SENHA = "s3nh4-inventada"


class Go2rtcFalso:
    def __init__(self, codigos: list[int] | None = None) -> None:
        self.codigos = codigos or []
        self.pedidos: list[httpx.Request] = []
        self.fora_do_ar = False

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if self.fora_do_ar:
            raise httpx.ConnectError("o go2rtc ainda não subiu", request=pedido)
        return httpx.Response(self.codigos.pop(0) if self.codigos else 200)


def _go2rtc(falso: Go2rtcFalso) -> Go2rtc:
    return Go2rtc(httpx.Client(transport=httpx.MockTransport(falso)), API)


def test_cadastra_a_camera_pela_api_sem_gravar_em_arquivo() -> None:
    falso = Go2rtcFalso()

    assert _go2rtc(falso).cadastrar("21", ORIGEM)

    (pedido,) = falso.pedidos
    # O PATCH cria a câmera só na memória; o PUT gravaria a senha no arquivo do go2rtc.
    assert (pedido.method, pedido.url.path) == ("PATCH", "/api/streams")
    assert dict(pedido.url.params) == {"name": "camera-21", "src": ORIGEM}


def test_o_agente_le_a_camera_pelo_go2rtc() -> None:
    assert _go2rtc(Go2rtcFalso()).endereco("21") == "rtsp://go2rtc:8554/camera-21"


@pytest.mark.parametrize("codigo", [400, 500])
def test_cadastro_recusado(codigo: int) -> None:
    assert not _go2rtc(Go2rtcFalso([codigo])).cadastrar("21", ORIGEM)


def test_go2rtc_fora_do_ar_nao_cadastra(caplog: pytest.LogCaptureFixture) -> None:
    falso = Go2rtcFalso()
    falso.fora_do_ar = True

    with caplog.at_level(logging.WARNING):
        assert not _go2rtc(falso).cadastrar("21", ORIGEM)

    assert "camera-21" in caplog.text
    assert SENHA not in caplog.text


def test_a_senha_nao_vai_para_o_registro_na_recusa(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        _go2rtc(Go2rtcFalso([400])).cadastrar("21", ORIGEM)

    assert caplog.text
    assert SENHA not in caplog.text


def test_abrir_pelo_go2rtc_cadastra_antes() -> None:
    falso = Go2rtcFalso()
    abertos: list[str] = []

    def abrir(endereco: str) -> str:
        abertos.append(endereco)
        return "video"

    abrir_pelo_go2rtc = _go2rtc(falso).abridor("21", ORIGEM, abrir)

    assert abrir_pelo_go2rtc("rtsp://go2rtc:8554/camera-21") == "video"
    assert abertos == ["rtsp://go2rtc:8554/camera-21"]
    assert len(falso.pedidos) == 1


def test_cada_abertura_cadastra_de_novo() -> None:
    # O go2rtc que reinicia esquece as câmeras: a câmera que caiu volta cadastrada.
    falso = Go2rtcFalso()
    abrir_pelo_go2rtc = _go2rtc(falso).abridor("21", ORIGEM, lambda _endereco: "video")

    abrir_pelo_go2rtc("rtsp://go2rtc:8554/camera-21")
    abrir_pelo_go2rtc("rtsp://go2rtc:8554/camera-21")

    assert len(falso.pedidos) == 2


def test_sem_cadastro_nao_abre() -> None:
    abertos: list[str] = []

    def abrir(endereco: str) -> str:
        abertos.append(endereco)
        return "video"

    abrir_pelo_go2rtc = _go2rtc(Go2rtcFalso([503])).abridor("21", ORIGEM, abrir)

    # Sem a câmera no go2rtc, a fonte tenta de novo mais tarde (como a câmera que não abriu).
    assert abrir_pelo_go2rtc("rtsp://go2rtc:8554/camera-21") is None
    assert abertos == []

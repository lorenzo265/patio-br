"""Fila de envio da caixa (SDD 7.4, D-24): nenhuma passagem se perde se a internet cair."""

import json
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from borda.envio import ESPERA_MAXIMA, ContagemDaFila, FilaDeEnvio, Nuvem, Remetente
from contratos.passagem import Passagem

pytestmark = pytest.mark.integracao  # a fila fica num arquivo SQLite

T0 = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
JPEG = b"\xff\xd8\xff\xe0foto-inventada\xff\xd9"
ENDERECO = "http://nuvem.example"
CHAVE = "chave-inventada-da-caixa"


def _passagem(segundos: float = 0, fotos: tuple[str, ...] = ()) -> Passagem:
    inicio = T0 + timedelta(seconds=segundos)
    return Passagem.model_validate(
        {
            "versao_contrato": 1,
            "id": str(uuid4()),
            "caixa_id": "1",
            "site_id": "1",
            "faixa_id": "1",
            "sentido": "entrada",
            "inicio": inicio.isoformat(),
            "fim": (inicio + timedelta(seconds=5)).isoformat(),
            "placas": [],
            "fotos": [{"tipo": "placa", "camera_id": "1", "ref": ref} for ref in fotos],
            "versao_leitor": "0.1.0",
        }
    )


class NuvemFalsa:
    """Responde como a nuvem, seguindo um roteiro de falhas; registra o que recebeu."""

    def __init__(self) -> None:
        self.respostas_da_passagem: list[int] = []
        """Códigos a responder às próximas passagens (depois do roteiro, 201)."""
        self.respostas_da_foto: list[int] = []
        self.falhas_de_rede = 0
        self.erros_inesperados = 0
        self.corpos_do_endereco: list[str] = []
        """Respostas 200 sem o endereço da foto (ex.: a página de um portal de wi-fi)."""
        self.pedidos: list[httpx.Request] = []
        self.passagens: list[str] = []
        self.fotos: dict[str, bytes] = {}

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if self.falhas_de_rede:
            self.falhas_de_rede -= 1
            raise httpx.ConnectError("a internet caiu", request=pedido)
        if self.erros_inesperados:
            self.erros_inesperados -= 1
            raise RuntimeError("um erro que ninguém previu")
        caminho = pedido.url.path
        if caminho == "/api/borda/fotos/endereco" and self.corpos_do_endereco:
            return httpx.Response(200, text=self.corpos_do_endereco.pop(0))
        if caminho == "/api/borda/fotos/endereco":
            ref = json.loads(pedido.content)["ref"]
            return httpx.Response(200, json={"ref": ref, "endereco": f"{ENDERECO}/envio/{ref}"})
        if caminho.startswith("/envio/"):
            codigo = self.respostas_da_foto.pop(0) if self.respostas_da_foto else 201
            if codigo in (200, 201):
                self.fotos[caminho.removeprefix("/envio/")] = pedido.content
            return httpx.Response(codigo)
        if caminho == "/api/borda/passagens":
            codigo = self.respostas_da_passagem.pop(0) if self.respostas_da_passagem else 201
            if codigo in (200, 201):
                self.passagens.append(json.loads(pedido.content)["id"])
            return httpx.Response(codigo, json={"detail": "roteiro do teste"})
        return httpx.Response(404)


@pytest.fixture
def nuvem_falsa() -> NuvemFalsa:
    return NuvemFalsa()


@pytest.fixture
def fila(tmp_path: Path) -> Iterator[FilaDeEnvio]:
    fila = FilaDeEnvio(tmp_path / "fila.sqlite")
    yield fila
    fila.fechar()


@pytest.fixture
def esperas() -> list[float]:
    return []


@pytest.fixture
def remetente(fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, esperas: list[float]) -> Remetente:
    cliente = httpx.Client(transport=httpx.MockTransport(nuvem_falsa))
    nuvem = Nuvem(ENDERECO, CHAVE, cliente=cliente)
    return Remetente(fila, nuvem, dormir=esperas.append)


def test_passagem_fica_gravada_no_disco_antes_de_ir(tmp_path: Path) -> None:
    arquivo = tmp_path / "fila.sqlite"
    fila = FilaDeEnvio(arquivo)
    fila.guardar(_passagem())
    fila.fechar()

    reaberta = FilaDeEnvio(arquivo)  # a caixa reiniciou: a passagem continua lá

    assert reaberta.pendentes() == 1
    reaberta.fechar()


def test_nuvem_que_falha_3_vezes_e_depois_aceita_recebe_a_passagem_uma_vez(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente, esperas: list[float]
) -> None:
    passagem = _passagem()
    fila.guardar(passagem)
    nuvem_falsa.respostas_da_passagem = [503, 503, 503]

    remetente.enviar_pendentes()

    assert nuvem_falsa.passagens == [str(passagem.id)]
    assert esperas == [1, 2, 4]
    assert fila.pendentes() == 0


def test_espera_dobra_ate_5_minutos(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente, esperas: list[float]
) -> None:
    fila.guardar(_passagem())
    nuvem_falsa.respostas_da_passagem = [500] * 12

    remetente.enviar_pendentes()

    assert esperas == [1, 2, 4, 8, 16, 32, 64, 128, 256, 300, 300, 300]
    assert ESPERA_MAXIMA == 300


def test_espera_volta_a_1_segundo_depois_de_um_envio_que_deu_certo(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente, esperas: list[float]
) -> None:
    fila.guardar(_passagem(0))
    fila.guardar(_passagem(10))
    nuvem_falsa.respostas_da_passagem = [500, 500, 201, 500]

    remetente.enviar_pendentes()

    assert esperas == [1, 2, 1]


def test_erro_de_rede_tenta_de_novo(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente, esperas: list[float]
) -> None:
    fila.guardar(_passagem())
    nuvem_falsa.falhas_de_rede = 2

    remetente.enviar_pendentes()

    assert (len(nuvem_falsa.passagens), esperas) == (1, [1, 2])


def test_envia_na_ordem_em_que_as_passagens_aconteceram(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente
) -> None:
    depois, antes = _passagem(60), _passagem(0)
    fila.guardar(depois)
    fila.guardar(antes)

    remetente.enviar_pendentes()

    assert nuvem_falsa.passagens == [str(antes.id), str(depois.id)]


def test_nao_passa_a_frente_de_uma_passagem_que_falhou(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente
) -> None:
    primeira, segunda = _passagem(0), _passagem(60)
    fila.guardar(primeira)
    fila.guardar(segunda)
    nuvem_falsa.respostas_da_passagem = [503]

    remetente.enviar_pendentes()

    enviadas = [json.loads(p.content)["id"] for p in nuvem_falsa.pedidos]
    assert enviadas == [str(primeira.id), str(primeira.id), str(segunda.id)]


def test_resposta_200_de_passagem_repetida_tambem_tira_da_fila(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente
) -> None:
    fila.guardar(_passagem())
    nuvem_falsa.respostas_da_passagem = [200]

    remetente.enviar_pendentes()

    assert fila.pendentes() == 0


@pytest.mark.parametrize("codigo", [403, 409, 422])
def test_recusa_definitiva_sai_da_fila_e_fica_guardada_a_parte(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente, codigo: int
) -> None:
    recusada, seguinte = _passagem(0), _passagem(60)
    fila.guardar(recusada)
    fila.guardar(seguinte)
    nuvem_falsa.respostas_da_passagem = [codigo]

    remetente.enviar_pendentes()

    assert nuvem_falsa.passagens == [str(seguinte.id)]
    assert [(r.passagem.id, r.codigo) for r in fila.recusadas()] == [(recusada.id, codigo)]


def test_chave_recusada_tenta_de_novo_sem_jogar_a_passagem_fora(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente
) -> None:
    # 401: a chave foi revogada ou trocada; a passagem espera a caixa ser ativada de novo.
    fila.guardar(_passagem())
    nuvem_falsa.respostas_da_passagem = [401, 401]

    remetente.enviar_pendentes()

    assert (len(nuvem_falsa.passagens), fila.recusadas()) == (1, [])


def test_fotos_vao_antes_da_passagem_e_sem_a_chave(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente
) -> None:
    passagem = _passagem(fotos=("p/1.jpg",))
    fila.guardar(passagem, {"p/1.jpg": JPEG})

    remetente.enviar_pendentes()

    caminhos = [p.url.path for p in nuvem_falsa.pedidos]
    assert caminhos == ["/api/borda/fotos/endereco", "/envio/p/1.jpg", "/api/borda/passagens"]
    envio_da_foto = nuvem_falsa.pedidos[1]
    assert envio_da_foto.method == "PUT"
    assert "authorization" not in envio_da_foto.headers
    assert nuvem_falsa.pedidos[0].headers["authorization"] == f"Bearer {CHAVE}"
    assert nuvem_falsa.fotos == {"p/1.jpg": JPEG}


def test_foto_que_falhou_vai_de_novo_antes_da_passagem(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente
) -> None:
    fila.guardar(_passagem(fotos=("p/1.jpg",)), {"p/1.jpg": JPEG})
    nuvem_falsa.respostas_da_foto = [403]  # endereço vencido: pede outro

    remetente.enviar_pendentes()

    caminhos = [p.url.path for p in nuvem_falsa.pedidos]
    assert caminhos.count("/api/borda/fotos/endereco") == 2
    assert caminhos[-1] == "/api/borda/passagens"


@pytest.mark.parametrize("codigo", [409, 413, 415])
def test_foto_recusada_de_vez_fica_de_fora_e_a_passagem_segue(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente, codigo: int
) -> None:
    passagem = _passagem(fotos=("p/1.jpg",))
    fila.guardar(passagem, {"p/1.jpg": JPEG})
    nuvem_falsa.respostas_da_foto = [codigo]

    remetente.enviar_pendentes()

    assert nuvem_falsa.passagens == [str(passagem.id)]


@pytest.mark.parametrize(
    "corpo", ["<html>entre na rede</html>", '{"ref": "p/1.jpg"}'], ids=["página", "sem endereço"]
)
def test_resposta_200_sem_o_endereco_da_foto_tenta_de_novo(
    fila: FilaDeEnvio,
    nuvem_falsa: NuvemFalsa,
    remetente: Remetente,
    esperas: list[float],
    corpo: str,
) -> None:
    # Um portal de wi-fi ou um proxy pode responder 200 com uma página no lugar da nuvem.
    passagem = _passagem(fotos=("p/1.jpg",))
    fila.guardar(passagem, {"p/1.jpg": JPEG})
    nuvem_falsa.corpos_do_endereco = [corpo]

    remetente.enviar_pendentes()

    assert (nuvem_falsa.passagens, esperas) == ([str(passagem.id)], [1])
    assert nuvem_falsa.fotos == {"p/1.jpg": JPEG}


def test_erro_inesperado_nao_para_o_envio(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, esperas: list[float]
) -> None:
    # Na caixa, o envio roda numa linha à parte: se ela morresse, a fila só cresceria.
    parar = threading.Event()
    cliente = httpx.Client(transport=httpx.MockTransport(nuvem_falsa))
    remetente = Remetente(
        fila, Nuvem(ENDERECO, CHAVE, cliente=cliente), dormir=esperas.append, parar=parar
    )
    passagem = _passagem()
    fila.guardar(passagem)
    nuvem_falsa.erros_inesperados = 1

    linha = threading.Thread(target=remetente.rodar)
    linha.start()
    prazo = time.monotonic() + 3
    while not nuvem_falsa.passagens and time.monotonic() < prazo:
        time.sleep(0.01)
    parar.set()
    linha.join(timeout=3)

    assert (nuvem_falsa.passagens, esperas) == ([str(passagem.id)], [1])


def test_foto_ja_enviada_nao_vai_de_novo_quando_a_passagem_falha(
    fila: FilaDeEnvio, nuvem_falsa: NuvemFalsa, remetente: Remetente
) -> None:
    fila.guardar(_passagem(fotos=("p/1.jpg",)), {"p/1.jpg": JPEG})
    nuvem_falsa.respostas_da_passagem = [503]

    remetente.enviar_pendentes()

    caminhos = [p.url.path for p in nuvem_falsa.pedidos]
    assert caminhos.count("/envio/p/1.jpg") == 1


def test_guardar_a_mesma_passagem_duas_vezes_nao_duplica(fila: FilaDeEnvio) -> None:
    passagem = _passagem()
    fila.guardar(passagem)
    fila.guardar(passagem)

    assert fila.pendentes() == 1


def test_passagem_volta_da_fila_igual_ao_que_entrou(fila: FilaDeEnvio) -> None:
    passagem = _passagem(fotos=("p/1.jpg",))
    fila.guardar(passagem, {"p/1.jpg": JPEG})

    proxima = fila.proxima()

    assert proxima is not None
    assert (proxima.passagem, proxima.fotos) == (passagem, {"p/1.jpg": JPEG})


def test_a_contagem_da_fila_para_a_saude(fila: FilaDeEnvio) -> None:
    assert fila.contagem() == ContagemDaFila(passagens=0, fotos=0, recusadas=0)
    recusada = _passagem(0, fotos=("r/1.jpg",))
    fila.guardar(recusada, {"r/1.jpg": JPEG})
    refs = ("a/1.jpg", "a/2.jpg", "a/3.jpg")
    fila.guardar(_passagem(60, fotos=refs), dict.fromkeys(refs, JPEG))
    fila.guardar(_passagem(120))

    fila.recusar(recusada.id, 422, "faixa de outro site")

    assert fila.contagem() == ContagemDaFila(passagens=2, fotos=3, recusadas=1)

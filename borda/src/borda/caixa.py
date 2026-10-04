"""O programa da caixa de borda (SDD 7.4): ativa, baixa a configuração, lê as câmeras e envia.

Uso::

    caixa ativar --nuvem https://patio-br.example --codigo XXXX-XXXX-XXXX
    caixa rodar

- ``ativar`` troca o código (gerado pela administração para o site) pela chave da caixa e a
  guarda em ``dados/caixa/caixa.json``, que só o dono lê.
- ``rodar`` baixa a configuração, abre as câmeras de placa por RTSP, roda o agente e o remetente
  da fila (``dados/caixa/fila.sqlite``) até receber o sinal de término (ou Ctrl+C). Os modelos
  do leitor v0 ficam em ``modelos/v0`` (``uv run tarefas modelos``).

A configuração vale até o programa reiniciar. Sem a nuvem no ar, a caixa espera para começar:
a configuração não fica no disco, porque traz as senhas das câmeras.
"""

import argparse
import logging
import os
import signal
import sys
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

import httpx

from borda.agente import Agente, CameraDoAgente, ConfiguracaoDoAgente, rodar_ao_vivo
from borda.ativacao import (
    CaixaAtivada,
    ChaveRecusadaError,
    CodigoRecusadoError,
    ativar,
    baixar_configuracao,
    guardar_caixa,
    ler_caixa,
)
from borda.captura import (
    QUADROS_POR_SEGUNDO,
    FonteAmostrada,
    FonteDeCamera,
    FonteDeQuadros,
    VideoAberto,
    abrir_camera,
    com_credenciais,
)
from borda.composicao import Posicao
from borda.envio import ESPERA_MAXIMA, FilaDeEnvio, Nuvem, Remetente
from borda.leitor.interface import LeitorDePlacas
from borda.rastreio import DetectorDeVeiculos, Rastreador

PASTA_PADRAO = Path("dados") / "caixa"
PASTA_DOS_MODELOS = Path("modelos") / "v0"

CarregarModelos = Callable[[], tuple[DetectorDeVeiculos, LeitorDePlacas]]

_registro = logging.getLogger(__name__)


def principal(
    argv: Sequence[str] | None = None,
    *,
    cliente: httpx.Client | None = None,
    parar: threading.Event | None = None,
    abrir: Callable[[str], VideoAberto | None] = abrir_camera,
    carregar_modelos: CarregarModelos | None = None,
    saida: TextIO = sys.stdout,
) -> int:
    """Ponto de entrada do comando ``caixa``.

    Args:
        argv: argumentos da linha de comando (padrão: os do processo).
        cliente: o cliente HTTP (os testes passam uma nuvem falsa).
        parar: quando ligado, ``rodar`` desliga; sem ele, o programa liga um e o aciona com o
            sinal de término ou Ctrl+C.
        abrir: como abrir uma câmera (os testes passam câmeras falsas).
        carregar_modelos: monta o detector e o leitor (padrão: o leitor v0).
        saida: onde escrever as mensagens.

    Returns:
        0 se deu certo; 1 se algo precisa de ação (a mensagem diz o quê).
    """
    argumentos = _interpretador().parse_args(argv)
    pasta = Path(argumentos.pasta)
    cliente = cliente or httpx.Client(timeout=30)
    try:
        if argumentos.comando == "ativar":
            return _ativar(cliente, argumentos.nuvem, argumentos.codigo, pasta, saida)
        return _rodar(
            cliente,
            pasta,
            argumentos.por_segundo,
            parar,
            abrir,
            carregar_modelos or _carregar_v0,
            saida,
        )
    except httpx.HTTPError as erro:
        print(f"erro: a nuvem não respondeu como esperado: {erro}", file=saida)
        return 1


def main() -> None:
    """O comando ``caixa`` de verdade: registro no terminal e o FFmpeg com RTSP por TCP."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # RTSP por TCP: na rede da portaria, o UDP perde pacotes e estraga quadros. O FFmpeg só
    # registra erros. As duas coisas podem ser trocadas pelo ambiente.
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "16")
    raise SystemExit(principal())


def _interpretador() -> argparse.ArgumentParser:
    interpretador = argparse.ArgumentParser(
        prog="caixa", description="O programa da caixa de borda (SDD 7.4)."
    )
    comandos = interpretador.add_subparsers(dest="comando", required=True)
    ativacao = comandos.add_parser("ativar", help="troca o código de ativação pela chave")
    ativacao.add_argument("--nuvem", required=True, help="endereço da nuvem (ex.: https://...)")
    ativacao.add_argument("--codigo", required=True, help="código gerado pela administração")
    rodada = comandos.add_parser("rodar", help="lê as câmeras e envia as passagens")
    rodada.add_argument(
        "--por-segundo",
        type=float,
        default=QUADROS_POR_SEGUNDO,
        help=f"quadros por segundo de cada câmera (padrão: {QUADROS_POR_SEGUNDO:g})",
    )
    for comando in (ativacao, rodada):
        comando.add_argument(
            "--pasta",
            default=str(PASTA_PADRAO),
            help=f"onde guardar a chave e a fila ({PASTA_PADRAO})",
        )
    return interpretador


def _ativar(cliente: httpx.Client, nuvem: str, codigo: str, pasta: Path, saida: TextIO) -> int:
    try:
        caixa = ativar(cliente, nuvem, codigo)
    except CodigoRecusadoError as erro:
        print(f"erro: {erro}", file=saida)
        return 1
    guardar_caixa(caixa, pasta / "caixa.json")
    print(f"caixa {caixa.caixa_id} ativada no site {caixa.site_id}; agora: caixa rodar", file=saida)
    return 0


def _rodar(
    cliente: httpx.Client,
    pasta: Path,
    por_segundo: float,
    parar: threading.Event | None,
    abrir: Callable[[str], VideoAberto | None],
    carregar_modelos: CarregarModelos,
    saida: TextIO,
) -> int:
    caixa = ler_caixa(pasta / "caixa.json")
    if caixa is None:
        print(
            "erro: a caixa não está ativada; rode antes: "
            "caixa ativar --nuvem <endereço> --codigo <código>",
            file=saida,
        )
        return 1
    if parar is None:
        parar = threading.Event()
        _desligar_com_sinal(parar)
    try:
        configuracao = baixar_com_paciencia(cliente, caixa, parar=parar)
    except ChaveRecusadaError as erro:
        print(f"erro: {erro}", file=saida)
        return 1
    if configuracao is None:
        return 0  # desligada antes de a nuvem responder
    try:
        detector, leitor = carregar_modelos()
    except FileNotFoundError as erro:
        print(f"erro: {erro}", file=saida)
        return 1
    fila = FilaDeEnvio(pasta / "fila.sqlite")
    try:
        _rodar_com(caixa, configuracao, fila, cliente, parar, abrir, detector, leitor, por_segundo)
    finally:
        fila.fechar()
    return 0


def baixar_com_paciencia(
    cliente: httpx.Client,
    caixa: CaixaAtivada,
    *,
    parar: threading.Event,
    dormir: Callable[[float], object] | None = None,
) -> ConfiguracaoDoAgente | None:
    """Baixa a configuração; se a nuvem não responde, tenta de novo, esperando 1 s, 2 s, 4 s...
    até 5 min.

    Returns:
        A configuração, ou ``None`` se a caixa foi desligada antes.

    Raises:
        ChaveRecusadaError: se a nuvem recusar a chave (tentar de novo não adianta).
    """
    dormir = dormir or parar.wait
    espera = 1.0
    while not parar.is_set():
        try:
            return baixar_configuracao(cliente, caixa)
        except httpx.HTTPError as erro:
            _registro.warning(
                "a nuvem não deu a configuração (%s); tentando de novo em %.0f s", erro, espera
            )
        dormir(espera)
        espera = min(espera * 2, ESPERA_MAXIMA)
    return None


def _rodar_com(
    caixa: CaixaAtivada,
    configuracao: ConfiguracaoDoAgente,
    fila: FilaDeEnvio,
    cliente: httpx.Client,
    parar: threading.Event,
    abrir: Callable[[str], VideoAberto | None],
    detector: DetectorDeVeiculos,
    leitor: LeitorDePlacas,
    por_segundo: float,
) -> None:
    def criar(camera: CameraDoAgente) -> Rastreador:
        posicao: Posicao = "frente" if camera.posicao == "frente" else "tras"
        return Rastreador(
            detector, leitor, faixa_id=camera.faixa_id, camera_id=camera.id, posicao=posicao
        )

    agente = Agente(configuracao, fila, criar_rastreador=criar)
    # Só as câmeras de placa: a foto de contexto entra com o borrão de rostos (SDD 8.3).
    fontes: dict[str, FonteDeQuadros] = {
        camera.id: FonteAmostrada(
            FonteDeCamera(
                com_credenciais(camera.endereco, camera.login, camera.senha),
                parar=parar,
                abrir=abrir,
            ),
            por_segundo,
        )
        for camera in configuracao.cameras
        if camera.posicao != "contexto"
    }
    remetente = Remetente(fila, Nuvem(caixa.nuvem, caixa.chave, cliente=cliente), parar=parar)
    envio = threading.Thread(target=remetente.rodar, name="envio", daemon=True)
    envio.start()
    _registro.info(
        "caixa %s no ar: %d câmeras de placa no site %s",
        caixa.caixa_id,
        len(fontes),
        caixa.site_id,
    )
    rodar_ao_vivo(agente, fontes, parar)
    envio.join(timeout=5)
    _registro.info("caixa %s desligada; o que não foi enviado fica na fila", caixa.caixa_id)


def _carregar_v0() -> tuple[DetectorDeVeiculos, LeitorDePlacas]:
    from borda.leitor.v0 import carregar_v0  # só aqui: carrega o ONNX Runtime

    return carregar_v0(PASTA_DOS_MODELOS)


def _desligar_com_sinal(parar: threading.Event) -> None:
    def desligar(_sinal: int, _quadro: object) -> None:
        parar.set()

    signal.signal(signal.SIGINT, desligar)
    signal.signal(signal.SIGTERM, desligar)


if __name__ == "__main__":
    main()

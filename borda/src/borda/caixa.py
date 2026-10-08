"""O programa da caixa de borda (SDD 7.4): ativa, baixa a configuração, lê as câmeras e envia.

Uso::

    caixa ativar --nuvem https://patio-br.example --codigo XXXX-XXXX-XXXX
    caixa rodar

- ``ativar`` troca o código (gerado pela administração para o site) pela chave da caixa e a
  guarda em ``dados/caixa/caixa.json``, que só o dono lê; a configuração guardada de antes (de
  outro site, talvez) é apagada.
- ``rodar`` baixa a configuração, abre as câmeras de placa por RTSP, roda o agente, o remetente
  da fila (``dados/caixa/fila.sqlite``) e o pulso da saúde (a cada minuto, D-65) até receber o
  sinal de término (ou Ctrl+C). Os modelos do leitor v0 ficam em ``modelos/v0``
  (``uv run tarefas modelos``).

A configuração baixada fica guardada em ``dados/caixa/configuracao.json``, que só o dono lê (o
disco da caixa é cifrado, D-66): sem a nuvem no ar, a caixa começa com ela. A configuração vale
até o programa reiniciar. Com ``--go2rtc`` (ou ``PATIO_GO2RTC``), as câmeras são lidas pelo
go2rtc, como nos contêineres da caixa.
"""

import argparse
import logging
import os
import signal
import sys
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

import httpx

from borda.agente import (
    VERSAO_DO_LEITOR,
    Agente,
    CameraDoAgente,
    ConfiguracaoDoAgente,
    rodar_ao_vivo,
)
from borda.ativacao import (
    CaixaAtivada,
    ChaveRecusadaError,
    CodigoRecusadoError,
    apagar_configuracao,
    ativar,
    baixar_configuracao,
    guardar_caixa,
    guardar_configuracao,
    ler_caixa,
    ler_configuracao,
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
from borda.go2rtc import Go2rtc
from borda.leitor.interface import LeitorDePlacas
from borda.rastreio import DetectorDeVeiculos, Rastreador
from borda.saude import FonteMedida, MedidorDasCameras, Pulso, medir_a_maquina, montar_saude
from contratos.saude import Saude

PASTA_PADRAO = Path("dados") / "caixa"
PASTA_DOS_MODELOS = Path("modelos") / "v0"

ARQUIVO_DA_CONFIGURACAO = "configuracao.json"

CarregarModelos = Callable[[], tuple[DetectorDeVeiculos, LeitorDePlacas]]
AbrirACamera = Callable[[CameraDoAgente], tuple[str, Callable[[str], VideoAberto | None]]]
"""De uma câmera da configuração: o endereço que a fonte abre e como abrir."""

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
            argumentos.go2rtc,
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
    rodada.add_argument(
        "--go2rtc",
        default=os.environ.get("PATIO_GO2RTC") or None,
        help="ler as câmeras pelo go2rtc (ex.: http://go2rtc:1984; padrão: PATIO_GO2RTC)",
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
    apagar_configuracao(pasta / ARQUIVO_DA_CONFIGURACAO)
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
    go2rtc: str | None,
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
        configuracao = baixar_com_paciencia(
            cliente, caixa, parar=parar, arquivo=pasta / ARQUIVO_DA_CONFIGURACAO
        )
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
        _rodar_com(
            caixa,
            configuracao,
            fila,
            pasta,
            cliente,
            parar,
            _com_o_go2rtc(cliente, go2rtc, abrir),
            detector,
            leitor,
            por_segundo,
        )
    finally:
        fila.fechar()
    return 0


def baixar_com_paciencia(
    cliente: httpx.Client,
    caixa: CaixaAtivada,
    *,
    parar: threading.Event,
    dormir: Callable[[float], object] | None = None,
    arquivo: Path | None = None,
) -> ConfiguracaoDoAgente | None:
    """Baixa a configuração; se a nuvem não responde, tenta de novo, esperando 1 s, 2 s, 4 s...
    até 5 min.

    Com ``arquivo`` (D-66), a configuração baixada fica guardada nele; se a nuvem não responde e há
    configuração guardada, a caixa começa com ela, sem esperar. A chave recusada apaga a
    configuração guardada: as senhas das câmeras não ficam na caixa revogada.

    Returns:
        A configuração, ou ``None`` se a caixa foi desligada antes.

    Raises:
        ChaveRecusadaError: se a nuvem recusar a chave (tentar de novo não adianta).
    """
    dormir = dormir or parar.wait
    espera = 1.0
    while not parar.is_set():
        try:
            configuracao = baixar_configuracao(cliente, caixa)
        except ChaveRecusadaError:
            if arquivo is not None:
                apagar_configuracao(arquivo)
            raise
        except httpx.HTTPError as erro:
            guardada = ler_configuracao(arquivo) if arquivo is not None else None
            if guardada is not None:
                _registro.warning(
                    "a nuvem não deu a configuração (%s); começando com a guardada", erro
                )
                return guardada
            _registro.warning(
                "a nuvem não deu a configuração (%s); tentando de novo em %.0f s", erro, espera
            )
        else:
            if arquivo is not None:
                guardar_configuracao(configuracao, arquivo)
            return configuracao
        dormir(espera)
        espera = min(espera * 2, ESPERA_MAXIMA)
    return None


def _rodar_com(
    caixa: CaixaAtivada,
    configuracao: ConfiguracaoDoAgente,
    fila: FilaDeEnvio,
    pasta: Path,
    cliente: httpx.Client,
    parar: threading.Event,
    abrir_a_camera: "AbrirACamera",
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
    de_placa = [camera for camera in configuracao.cameras if camera.posicao != "contexto"]
    medidor = MedidorDasCameras(camera.id for camera in de_placa)
    fontes: dict[str, FonteDeQuadros] = {}
    for camera in de_placa:
        endereco, abrir = abrir_a_camera(camera)
        fontes[camera.id] = FonteMedida(
            FonteAmostrada(FonteDeCamera(endereco, parar=parar, abrir=abrir), por_segundo),
            camera.id,
            medidor,
        )
    nuvem = Nuvem(caixa.nuvem, caixa.chave, cliente=cliente)

    def saude_de_agora() -> Saude:
        return montar_saude(
            caixa_id=configuracao.caixa_id,
            site_id=configuracao.site_id,
            versao_leitor=VERSAO_DO_LEITOR,
            medidor=medidor,
            fila=fila.contagem(),
            maquina=medir_a_maquina(pasta),
            agora=datetime.now(UTC),
        )

    remetente = Remetente(fila, nuvem, parar=parar)
    envio = threading.Thread(target=remetente.rodar, name="envio", daemon=True)
    envio.start()
    pulso = threading.Thread(
        target=Pulso(saude_de_agora, nuvem, parar=parar, arquivo=pasta / "saude.json").rodar,
        name="saude",
        daemon=True,
    )
    pulso.start()
    _registro.info(
        "caixa %s no ar: %d câmeras de placa no site %s",
        caixa.caixa_id,
        len(fontes),
        caixa.site_id,
    )
    rodar_ao_vivo(agente, fontes, parar)
    envio.join(timeout=5)
    pulso.join(timeout=5)
    _registro.info("caixa %s desligada; o que não foi enviado fica na fila", caixa.caixa_id)


def _com_o_go2rtc(
    cliente: httpx.Client, go2rtc: str | None, abrir: Callable[[str], VideoAberto | None]
) -> "AbrirACamera":
    """Como abrir cada câmera: direto, ou pelo go2rtc (cadastrando a câmera antes, D-66)."""

    def abrir_a_camera(camera: CameraDoAgente) -> tuple[str, Callable[[str], VideoAberto | None]]:
        origem = com_credenciais(camera.endereco, camera.login, camera.senha)
        if go2rtc is None:
            return origem, abrir
        servidor = Go2rtc(cliente, go2rtc)
        return servidor.endereco(camera.id), servidor.abridor(camera.id, origem, abrir)

    return abrir_a_camera


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

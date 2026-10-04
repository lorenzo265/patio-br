"""O agente da caixa (SDD 7.4): junta captura, leitura, rastreamento, composição e fila.

Para cada câmera de placa (frente ou trás) há um rastreador; as leituras dos veículos passam,
por faixa, pela composição; cada composição vira uma passagem (com ``id`` novo e a hora da
caixa) e vai para a fila de envio com a foto de cada placa, em JPEG. A câmera de contexto não
lê placa; a foto dela entra com o borrão de rostos (SDD 8.3), depois.

O remetente (``envio.Remetente``) esvazia a fila em outra linha de execução.

Dois jeitos de rodar: ``rodar`` junta fontes que acabam (arquivos, pastas) pela hora dos
quadros; ``rodar_ao_vivo`` lê câmeras ao vivo, cada uma na sua linha, até a caixa desligar
(SDD D-30).
"""

import heapq
import io
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal, Protocol
from uuid import uuid4

from PIL import Image

from borda.captura import FonteDeQuadros, QuadroNoTempo
from borda.composicao import JANELA_PADRAO, Composicao, Compositor, LeituraDeVeiculo
from borda.envio import FilaDeEnvio
from borda.leitor.interface import Quadro
from contratos.passagem import Foto, Passagem, Sentido

VERSAO_DO_LEITOR = "v0"
"""Vai em cada passagem (``versao_leitor``): o leitor v0, com pesos de terceiros (T15)."""

QUALIDADE_DO_JPEG = 90

ESPERA_DE_QUADROS = 60
"""Quantos quadros podem esperar o agente ao vivo (cerca de 2 s de 6 câmeras a 5 por segundo)."""

PRAZO_PARA_DESLIGAR = 5.0
"""Segundos para processar, ao desligar, os quadros que já tinham chegado."""

_registro = logging.getLogger(__name__)

PosicaoDaCamera = Literal["frente", "tras", "contexto"]


@dataclass(frozen=True)
class FaixaDoAgente:
    """Uma faixa do site, como a nuvem a manda."""

    id: str
    nome: str
    sentido: Sentido


@dataclass(frozen=True)
class CameraDoAgente:
    """Uma câmera do site, com o que a caixa precisa para ler o vídeo."""

    id: str
    nome: str
    faixa_id: str
    posicao: PosicaoDaCamera
    endereco: str
    login: str
    senha: str


@dataclass(frozen=True)
class ConfiguracaoDoAgente:
    """A configuração que a caixa baixa da nuvem (``GET /api/borda/configuracao``)."""

    caixa_id: str
    site_id: str
    faixas: tuple[FaixaDoAgente, ...]
    cameras: tuple[CameraDoAgente, ...]

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "ConfiguracaoDoAgente":
        """Monta a partir da resposta da nuvem."""
        faixas, cameras = [], []
        for faixa in dados["faixas"]:
            faixas.append(
                FaixaDoAgente(id=faixa["id"], nome=faixa["nome"], sentido=faixa["sentido"])
            )
            for camera in faixa["cameras"]:
                cameras.append(
                    CameraDoAgente(
                        id=camera["id"],
                        nome=camera["nome"],
                        faixa_id=faixa["id"],
                        posicao=camera["posicao"],
                        endereco=camera["endereco"],
                        login=camera["login"],
                        senha=camera["senha"],
                    )
                )
        return cls(
            caixa_id=dados["caixa_id"],
            site_id=dados["site_id"],
            faixas=tuple(faixas),
            cameras=tuple(cameras),
        )


class RastreadorDeCamera(Protocol):
    """O que o agente usa de um rastreador (``rastreio.Rastreador``)."""

    def processar(self, quadro: QuadroNoTempo) -> list[LeituraDeVeiculo]:
        """As leituras dos veículos que acabaram de sair da imagem."""
        ...

    def esvaziar(self) -> list[LeituraDeVeiculo]:
        """As leituras dos veículos ainda na imagem."""
        ...


class Agente:
    """O processo da caixa, uma câmera de cada vez (quem chama decide a ordem dos quadros)."""

    def __init__(
        self,
        configuracao: ConfiguracaoDoAgente,
        fila: FilaDeEnvio,
        *,
        criar_rastreador: Callable[[CameraDoAgente], RastreadorDeCamera],
        janela: timedelta = JANELA_PADRAO,
        versao_leitor: str = VERSAO_DO_LEITOR,
    ) -> None:
        """Prepara o agente.

        Args:
            configuracao: faixas e câmeras do site, baixadas da nuvem.
            fila: onde as passagens ficam até a nuvem confirmar.
            criar_rastreador: monta o rastreador de uma câmera de placa (frente ou trás).
            janela: quanto o cavalo espera o reboque (padrão 30 s).
            versao_leitor: vai em cada passagem.
        """
        self._configuracao = configuracao
        self._fila = fila
        self._faixas = {faixa.id: faixa for faixa in configuracao.faixas}
        self._cameras = {camera.id: camera for camera in configuracao.cameras}
        self._rastreadores = {
            camera.id: criar_rastreador(camera)
            for camera in configuracao.cameras
            if camera.posicao != "contexto"
        }
        self._compositor = Compositor(janela=janela)
        self._versao_leitor = versao_leitor

    def processar(self, camera_id: str, quadro: QuadroNoTempo) -> list[Passagem]:
        """Processa um quadro de uma câmera e devolve as passagens que foram para a fila.

        Raises:
            KeyError: se a câmera não estiver na configuração.
        """
        if camera_id not in self._cameras:
            raise KeyError(f"câmera {camera_id} não está na configuração da caixa")
        rastreador = self._rastreadores.get(camera_id)
        prontas: list[Composicao] = []
        if rastreador is not None:
            for leitura in rastreador.processar(quadro):
                prontas.extend(self._compositor.receber(leitura))
        prontas.extend(self._compositor.vencer(quadro.momento))
        return [self._guardar(composicao) for composicao in prontas]

    def encerrar(self) -> list[Passagem]:
        """Encerra os veículos e composições em aberto (fim do vídeo ou desligamento)."""
        prontas: list[Composicao] = []
        for rastreador in self._rastreadores.values():
            for leitura in rastreador.esvaziar():
                prontas.extend(self._compositor.receber(leitura))
        prontas.extend(self._compositor.esvaziar())
        return [self._guardar(composicao) for composicao in prontas]

    def _guardar(self, composicao: Composicao) -> Passagem:
        faixa = self._faixas[composicao.faixa_id]
        passagem_id = uuid4()
        fotos: dict[str, bytes] = {}
        referencias = []
        for indice, (placa, recorte) in enumerate(
            zip(composicao.placas, composicao.recortes, strict=True)
        ):
            if recorte is None:
                continue
            ref = f"{composicao.inicio:%Y/%m/%d}/{passagem_id}-{indice}.jpg"
            fotos[ref] = _jpeg(recorte)
            referencias.append(Foto(tipo="placa", camera_id=placa.camera_id, ref=ref))
        passagem = Passagem(
            versao_contrato=1,
            id=passagem_id,
            caixa_id=self._configuracao.caixa_id,
            site_id=self._configuracao.site_id,
            faixa_id=faixa.id,
            sentido=faixa.sentido,
            inicio=composicao.inicio,
            fim=composicao.fim,
            placas=composicao.placas,
            fotos=tuple(referencias),
            versao_leitor=self._versao_leitor,
        )
        self._fila.guardar(passagem, fotos)
        return passagem


def rodar(agente: Agente, fontes: Mapping[str, FonteDeQuadros]) -> list[Passagem]:
    """Roda o agente sobre as fontes (uma por câmera), na ordem do tempo, até acabarem.

    Returns:
        Todas as passagens que foram para a fila, inclusive as do encerramento.
    """
    correntes = [_com_a_camera(camera_id, fonte) for camera_id, fonte in fontes.items()]
    passagens: list[Passagem] = []
    for camera_id, quadro in heapq.merge(*correntes, key=lambda item: (item[1].momento, item[0])):
        passagens.extend(agente.processar(camera_id, quadro))
    passagens.extend(agente.encerrar())
    return passagens


def _com_a_camera(camera_id: str, fonte: FonteDeQuadros) -> Iterator[tuple[str, QuadroNoTempo]]:
    # Uma função, e não um gerador dentro de outro: cada corrente guarda a própria câmera.
    for quadro in fonte.quadros():
        yield camera_id, quadro


def _jpeg(recorte: Quadro) -> bytes:
    # O recorte é BGR, como a câmera entrega; o JPEG guarda RGB.
    saida = io.BytesIO()
    Image.fromarray(recorte[:, :, ::-1].copy()).save(saida, "JPEG", quality=QUALIDADE_DO_JPEG)
    return saida.getvalue()


class AgenteAoVivo(Protocol):
    """O que ``rodar_ao_vivo`` usa do agente."""

    def processar(self, camera_id: str, quadro: QuadroNoTempo) -> object:
        """Processa um quadro de uma câmera."""
        ...

    def encerrar(self) -> object:
        """Encerra o que estava em aberto."""
        ...


def rodar_ao_vivo(
    agente: AgenteAoVivo,
    fontes: Mapping[str, FonteDeQuadros],
    parar: threading.Event,
    *,
    espera: int = ESPERA_DE_QUADROS,
) -> None:
    """Roda o agente sobre câmeras ao vivo até ``parar`` ser ligado (SDD D-30).

    Cada câmera é lida na própria linha de execução, e os quadros são processados na ordem em que
    chegam: uma câmera caída não segura as outras. Se o agente fica para trás, os quadros que não
    cabem na espera são descartados, com registro. Um quadro que dá erro fica registrado e não
    para a caixa. Ao desligar, processa o que já tinha chegado (por até ``PRAZO_PARA_DESLIGAR``)
    e encerra os veículos e as composições em aberto.
    """
    chegados: queue.Queue[tuple[str, QuadroNoTempo]] = queue.Queue(maxsize=espera)
    linhas = [
        threading.Thread(
            target=_ler_camera,
            args=(camera_id, fonte, chegados, parar),
            name=f"camera-{camera_id}",
            daemon=True,
        )
        for camera_id, fonte in fontes.items()
    ]
    for linha in linhas:
        linha.start()
    while not parar.is_set():
        try:
            camera_id, quadro = chegados.get(timeout=0.5)
        except queue.Empty:
            continue
        _processar(agente, camera_id, quadro)
    prazo = time.monotonic() + PRAZO_PARA_DESLIGAR
    while time.monotonic() < prazo:
        try:
            camera_id, quadro = chegados.get_nowait()
        except queue.Empty:
            break
        _processar(agente, camera_id, quadro)
    agente.encerrar()


def _ler_camera(
    camera_id: str,
    fonte: FonteDeQuadros,
    chegados: "queue.Queue[tuple[str, QuadroNoTempo]]",
    parar: threading.Event,
) -> None:
    descartados = 0
    try:
        for quadro in fonte.quadros():
            if parar.is_set():
                return
            try:
                chegados.put_nowait((camera_id, quadro))
            except queue.Full:
                descartados += 1
                if descartados == 1 or descartados % 500 == 0:
                    _registro.warning(
                        "câmera %s: %d quadros descartados (o agente não dá conta)",
                        camera_id,
                        descartados,
                    )
    except Exception:
        _registro.exception("a leitura da câmera %s parou com um erro", camera_id)


def _processar(agente: AgenteAoVivo, camera_id: str, quadro: QuadroNoTempo) -> None:
    try:
        agente.processar(camera_id, quadro)
    except Exception:
        _registro.exception("erro num quadro da câmera %s; a caixa segue", camera_id)

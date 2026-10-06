"""A saúde da caixa (SDD 7.4, D-65): a cada minuto, a caixa conta à nuvem como está.

- **As câmeras:** ``FonteMedida`` anota cada quadro que chega ao agente (depois da amostragem);
  ``MedidorDasCameras`` diz se cada câmera está no ar (mandou quadro nos últimos 10 s), os
  quadros por segundo dos últimos 10 s e a hora do último quadro.
- **A máquina:** o psutil (BSD-3) mede a CPU (a média desde a medida anterior), a memória, o
  disco da pasta da fila e a temperatura do sensor mais quente.
- **O pulso:** manda uma saúde logo ao começar e outra a cada minuto. A saúde não entra na
  fila: a que não chega fica registrada e não vai de novo.
"""

import logging
import threading
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Any

import psutil

from borda.captura import FonteDeQuadros, QuadroNoTempo
from borda.envio import ContagemDaFila, Nuvem, Resultado
from contratos.saude import (
    TEMPERATURA_MAXIMA,
    TEMPERATURA_MINIMA,
    FilaDaCaixa,
    Saude,
    SaudeDaCamera,
)

INTERVALO = 60.0
"""Segundos entre duas saúdes."""

JANELA_DOS_QUADROS = timedelta(seconds=10)
"""Os quadros por segundo são os desta janela; a câmera sem quadro nela saiu do ar."""

MAXIMO_DE_QUADROS_GUARDADOS = 1000
"""Por câmera: o bastante para 100 quadros por segundo na janela."""

_registro = logging.getLogger(__name__)


class MedidorDasCameras:
    """Os quadros que chegam de cada câmera, contados para a saúde.

    As linhas das câmeras anotam e o pulso mede, cada um na sua linha de execução.
    """

    def __init__(self, cameras: Iterable[str]) -> None:
        """Prepara a contagem das câmeras, na ordem dada."""
        self._trava = threading.Lock()
        self._quadros: dict[str, deque[datetime]] = {
            camera: deque(maxlen=MAXIMO_DE_QUADROS_GUARDADOS) for camera in cameras
        }
        self._ultimo: dict[str, datetime] = {}

    def registrar(self, camera_id: str, momento: datetime) -> None:
        """Anota um quadro da câmera, visto em ``momento``."""
        with self._trava:
            self._quadros[camera_id].append(momento)
            self._ultimo[camera_id] = momento

    def medir(self, agora: datetime) -> tuple[SaudeDaCamera, ...]:
        """Como estava cada câmera em ``agora``."""
        inicio = agora - JANELA_DOS_QUADROS
        medidas = []
        with self._trava:
            for camera_id, quadros in self._quadros.items():
                while quadros and quadros[0] <= inicio:
                    quadros.popleft()
                ultimo = self._ultimo.get(camera_id)
                medidas.append(
                    SaudeDaCamera(
                        camera_id=camera_id,
                        no_ar=ultimo is not None and agora - ultimo <= JANELA_DOS_QUADROS,
                        quadros_por_segundo=len(quadros) / JANELA_DOS_QUADROS.total_seconds(),
                        ultimo_quadro=ultimo,
                    )
                )
        return tuple(medidas)


class FonteMedida:
    """Uma fonte cujos quadros são anotados no medidor, um a um, quando passam."""

    def __init__(self, fonte: FonteDeQuadros, camera_id: str, medidor: MedidorDasCameras) -> None:
        """Guarda a fonte, a câmera dela e o medidor."""
        self._fonte = fonte
        self._camera_id = camera_id
        self._medidor = medidor

    def quadros(self) -> Iterator[QuadroNoTempo]:
        """Os quadros da fonte, anotados no medidor."""
        for quadro in self._fonte.quadros():
            self._medidor.registrar(self._camera_id, quadro.momento)
            yield quadro


@dataclass(frozen=True)
class Maquina:
    """A máquina da caixa num momento."""

    cpu: float
    temperatura: float | None
    memoria: float
    disco: float


def medir_a_maquina(pasta: Path) -> Maquina:
    """A CPU (desde a medida anterior), a temperatura, a memória e o disco da ``pasta``."""
    return Maquina(
        cpu=psutil.cpu_percent(interval=None),
        temperatura=temperatura_mais_quente(_sensores()),
        memoria=psutil.virtual_memory().percent,
        disco=psutil.disk_usage(str(pasta)).percent,
    )


def _sensores() -> Mapping[str, Sequence[Any]]:
    # Só o Linux e o FreeBSD têm os sensores no psutil; e o acesso a eles pode falhar.
    ler = getattr(psutil, "sensors_temperatures", None)
    if ler is None:
        return {}
    try:
        leituras: Mapping[str, Sequence[Any]] = ler()
    except Exception:
        _registro.warning("os sensores de temperatura não responderam", exc_info=True)
        return {}
    return leituras


def temperatura_mais_quente(leituras: Mapping[str, Sequence[Any]]) -> float | None:
    """A temperatura do sensor mais quente, em °C; ``None`` sem sensor.

    A leitura impossível (fora de -60 a 150 °C, como um sensor sem nada ligado) fica de fora.
    """
    validas = [
        float(sensor.current)
        for sensores in leituras.values()
        for sensor in sensores
        # A comparação com NaN dá falso: a leitura NaN também fica de fora.
        if TEMPERATURA_MINIMA <= sensor.current <= TEMPERATURA_MAXIMA
    ]
    return max(validas, default=None)


def montar_saude(
    *,
    caixa_id: str,
    site_id: str,
    versao_leitor: str,
    medidor: MedidorDasCameras,
    fila: ContagemDaFila,
    maquina: Maquina,
    agora: datetime,
) -> Saude:
    """A saúde da caixa em ``agora``, no formato do contrato."""
    return Saude(
        versao_contrato=1,
        caixa_id=caixa_id,
        site_id=site_id,
        momento=agora,
        versao_programa=version("patio-borda"),
        versao_leitor=versao_leitor,
        cpu=maquina.cpu,
        temperatura=maquina.temperatura,
        memoria=maquina.memoria,
        disco=maquina.disco,
        cameras=medidor.medir(agora),
        fila=FilaDaCaixa(passagens=fila.passagens, fotos=fila.fotos, recusadas=fila.recusadas),
    )


class Pulso:
    """Manda a saúde logo ao começar e, depois, a cada minuto, até a caixa desligar."""

    def __init__(
        self,
        montar: Callable[[], Saude],
        nuvem: Nuvem,
        *,
        parar: threading.Event,
        dormir: Callable[[float], bool] | None = None,
    ) -> None:
        """Prepara o pulso.

        Args:
            montar: monta a saúde de agora.
            nuvem: para onde ela vai.
            parar: quando ligado, o pulso para.
            dormir: como esperar entre as saúdes; devolve ``True`` se é para parar (o padrão
                espera o evento ``parar``; os testes só anotam quanto esperariam).
        """
        self._montar = montar
        self._nuvem = nuvem
        self._dormir = dormir or parar.wait

    def rodar(self) -> None:
        """Manda uma saúde agora e outra a cada minuto, até pedirem para parar."""
        self._enviar()
        while not self._dormir(INTERVALO):
            self._enviar()

    def _enviar(self) -> None:
        try:
            resposta = self._nuvem.enviar_saude(self._montar())
        except Exception:
            # Um erro ao medir não pode calar a caixa de vez: a próxima saúde vai em um minuto.
            _registro.exception("erro ao montar a saúde; a próxima vai em um minuto")
            return
        if resposta.resultado is not Resultado.ACEITA:
            _registro.warning(
                "a saúde não chegou (%s); a próxima vai em um minuto",
                resposta.motivo or resposta.codigo,
            )

"""Rastreamento (SDD 4.2, D-25): segue cada veículo entre os quadros de uma câmera.

Um rastreador nosso, no estilo do ByteTrack, sem o filtro de Kalman:

1. o detector acha os veículos do quadro;
2. as detecções de confiança alta se juntam às trilhas abertas pela maior sobreposição (IoU);
   depois, as de confiança baixa se juntam às trilhas que sobraram (o veículo segue mesmo
   quando o detector fica em dúvida), mas nunca abrem trilha nova;
3. em cada veículo achado, o leitor lê a placa no recorte do veículo;
4. a trilha que fica alguns quadros sem detecção se fecha: as leituras passam pela votação e
   viram uma ``LeituraDeVeiculo``, com o recorte da placa mais confiável para a foto.

Na portaria o caminhão anda devagar: a 5 quadros por segundo, a caixa de um quadro cobre boa
parte da do seguinte, e a sobreposição basta para seguir o veículo.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from itertools import count
from typing import Protocol

import numpy as np

from borda.captura import QuadroNoTempo
from borda.composicao import LeituraDeVeiculo, Posicao
from borda.leitor.formato import formatar
from borda.leitor.interface import LeitorDePlacas, Quadro, Regiao
from borda.leitor.votacao import LeituraDoQuadro, votar

CONFIANCA_ALTA = 0.5
"""Detecção que abre trilha nova e tem a preferência."""
CONFIANCA_MINIMA = 0.1
"""Abaixo disso, a detecção é ignorada."""
IOU_MINIMO = 0.3
"""Sobreposição mínima para dizer que é o mesmo veículo do quadro anterior."""
QUADROS_PARA_SUMIR = 3
"""Quadros seguidos sem o veículo para dar a passagem dele por encerrada."""
QUADROS_MINIMOS = 3
"""Trilha sem placa lida só vira leitura (sem placa) se o veículo apareceu nesses quadros."""


@dataclass(frozen=True)
class Deteccao:
    """Um veículo achado num quadro."""

    regiao: Regiao
    confianca: float


class DetectorDeVeiculos(Protocol):
    """Acha os veículos (caminhões, carros, ônibus) num quadro."""

    def detectar(self, quadro: Quadro) -> list[Deteccao]:
        """Os veículos do quadro (pode não haver nenhum)."""
        ...


@dataclass
class _Trilha:
    """Um veículo sendo seguido."""

    regiao: Regiao
    inicio: datetime
    fim: datetime
    vistos: int = 1
    perdidos: int = 0
    leituras: list[LeituraDoQuadro] = field(default_factory=list)
    melhores: dict[str, tuple[float, Quadro]] = field(default_factory=dict)
    """Por placa, a leitura mais confiável e o recorte dela (para a foto)."""


class Rastreador:
    """Segue os veículos de uma câmera e entrega uma leitura por veículo."""

    def __init__(
        self,
        detector: DetectorDeVeiculos,
        leitor: LeitorDePlacas,
        *,
        faixa_id: str,
        camera_id: str,
        posicao: Posicao,
        quadros_para_sumir: int = QUADROS_PARA_SUMIR,
    ) -> None:
        """Prepara o rastreador de uma câmera.

        Args:
            detector: acha os veículos.
            leitor: lê as placas no recorte de cada veículo.
            faixa_id: a faixa da câmera (id da nuvem, em texto).
            camera_id: a câmera (id da nuvem, em texto).
            posicao: se a câmera vê a frente ou a traseira dos veículos.
            quadros_para_sumir: quadros seguidos sem o veículo para encerrar a passagem dele.
        """
        self._detector = detector
        self._leitor = leitor
        self._faixa_id = faixa_id
        self._camera_id = camera_id
        self._posicao = posicao
        self._quadros_para_sumir = quadros_para_sumir
        self._numeros = count()
        self._trilhas: dict[int, _Trilha] = {}

    def processar(self, quadro: QuadroNoTempo) -> list[LeituraDeVeiculo]:
        """Processa um quadro e devolve as leituras dos veículos que acabaram de sair."""
        deteccoes = [
            d for d in self._detector.detectar(quadro.imagem) if d.confianca >= CONFIANCA_MINIMA
        ]
        altas = [d for d in deteccoes if d.confianca >= CONFIANCA_ALTA]
        baixas = [d for d in deteccoes if d.confianca < CONFIANCA_ALTA]
        pares = _casar(self._trilhas, altas)
        sobraram = {n: t for n, t in self._trilhas.items() if n not in pares}
        pares.update(_casar(sobraram, baixas))
        usadas = {id(d) for d in pares.values()}
        for numero, deteccao in pares.items():
            trilha = self._trilhas[numero]
            trilha.regiao, trilha.fim = deteccao.regiao, quadro.momento
            trilha.vistos += 1
            trilha.perdidos = 0
            self._ler(trilha, quadro.imagem)
        for deteccao in altas:
            if id(deteccao) not in usadas:
                nova = _Trilha(regiao=deteccao.regiao, inicio=quadro.momento, fim=quadro.momento)
                self._trilhas[next(self._numeros)] = nova
                self._ler(nova, quadro.imagem)
        prontas = []
        for numero in [n for n in self._trilhas if n not in pares]:
            trilha = self._trilhas[numero]
            if trilha.inicio == quadro.momento:
                continue  # acabou de nascer neste quadro
            trilha.perdidos += 1
            if trilha.perdidos >= self._quadros_para_sumir:
                del self._trilhas[numero]
                prontas.append(self._encerrar(trilha))
        return [leitura for leitura in prontas if leitura is not None]

    def esvaziar(self) -> list[LeituraDeVeiculo]:
        """Encerra todos os veículos ainda na imagem (ao fim do vídeo ou ao desligar)."""
        trilhas = sorted(self._trilhas.values(), key=lambda t: t.inicio)
        self._trilhas.clear()
        return [leitura for t in trilhas if (leitura := self._encerrar(t)) is not None]

    def _ler(self, trilha: _Trilha, imagem: Quadro) -> None:
        recorte = _recortar(imagem, trilha.regiao)
        if recorte.size == 0:
            return
        for bruta in self._leitor.ler(recorte):
            formatada = formatar(bruta.texto, bruta.confianca)
            if formatada is None:
                continue
            trilha.leituras.append(LeituraDoQuadro(formatada.placa, formatada.confianca))
            melhor = trilha.melhores.get(formatada.placa)
            if melhor is None or formatada.confianca > melhor[0]:
                foto = np.ascontiguousarray(_recortar(recorte, bruta.regiao))
                trilha.melhores[formatada.placa] = (formatada.confianca, foto)

    def _encerrar(self, trilha: _Trilha) -> LeituraDeVeiculo | None:
        voto = votar(trilha.leituras)
        if voto is None and trilha.vistos < QUADROS_MINIMOS:
            return None  # uma mancha de um ou dois quadros não é um veículo
        return LeituraDeVeiculo(
            faixa_id=self._faixa_id,
            camera_id=self._camera_id,
            posicao=self._posicao,
            placa=voto.placa if voto else None,
            confianca=voto.confianca if voto else 0.0,
            quadros=voto.quadros if voto else 0,
            inicio=trilha.inicio,
            fim=trilha.fim,
            recorte=trilha.melhores[voto.placa][1] if voto else None,
        )


def _casar(trilhas: dict[int, _Trilha], deteccoes: list[Deteccao]) -> dict[int, Deteccao]:
    # Junta pela maior sobreposição primeiro; cada trilha e cada detecção entram uma vez só.
    candidatos: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for numero, trilha in trilhas.items():
        for indice, deteccao in enumerate(deteccoes):
            sobreposicao = iou(trilha.regiao, deteccao.regiao)
            if sobreposicao >= IOU_MINIMO:
                candidatos[numero].append((sobreposicao, indice))
    ordenados = sorted(
        ((s, numero, indice) for numero, lista in candidatos.items() for s, indice in lista),
        reverse=True,
    )
    pares: dict[int, Deteccao] = {}
    usadas: set[int] = set()
    for _, numero, indice in ordenados:
        if numero not in pares and indice not in usadas:
            pares[numero] = deteccoes[indice]
            usadas.add(indice)
    return pares


def iou(a: Regiao, b: Regiao) -> float:
    """A sobreposição de duas regiões: a área em comum dividida pela área das duas juntas."""
    largura = min(a.x + a.largura, b.x + b.largura) - max(a.x, b.x)
    altura = min(a.y + a.altura, b.y + b.altura) - max(a.y, b.y)
    if largura <= 0 or altura <= 0:
        return 0.0
    comum = largura * altura
    return comum / (a.largura * a.altura + b.largura * b.altura - comum)


def _recortar(imagem: Quadro, regiao: Regiao) -> Quadro:
    x, y = max(regiao.x, 0), max(regiao.y, 0)
    return imagem[y : regiao.y + regiao.altura, x : regiao.x + regiao.largura]

"""O go2rtc da caixa (SDD 7.4, D-66): recebe cada câmera uma vez só e a repassa ao agente.

O agente cadastra cada câmera de placa pela API do go2rtc (``PATCH /api/streams``, que guarda a
câmera só na memória: o ``PUT`` gravaria o endereço, com a senha, no arquivo do go2rtc) e lê o
vídeo de ``rtsp://<go2rtc>:8554/camera-<id>``. A cada vez que a câmera é reaberta, o cadastro é
refeito: o go2rtc que reinicia esquece as câmeras.
"""

import logging
from collections.abc import Callable
from typing import TypeVar
from urllib.parse import urlsplit

import httpx

from borda.captura import sem_credenciais

PORTA_DO_RTSP = 8554
TEMPO_DO_PEDIDO = httpx.Timeout(5.0)

_registro = logging.getLogger(__name__)

Video = TypeVar("Video")


class Go2rtc:
    """A API do go2rtc, vista do agente."""

    def __init__(self, cliente: httpx.Client, endereco: str) -> None:
        """Prepara o acesso.

        Args:
            cliente: o cliente HTTP (os testes passam um go2rtc falso).
            endereco: o endereço da API (ex.: ``http://go2rtc:1984``).
        """
        self._cliente = cliente
        self._api = endereco.rstrip("/")
        self._servidor = urlsplit(self._api).hostname or "localhost"

    def endereco(self, camera_id: str) -> str:
        """O endereço RTSP de onde o agente lê a câmera (sem senha)."""
        return f"rtsp://{self._servidor}:{PORTA_DO_RTSP}/{_nome(camera_id)}"

    def cadastrar(self, camera_id: str, origem: str) -> bool:
        """Cadastra (ou recadastra) a câmera no go2rtc.

        Args:
            origem: o endereço RTSP da câmera, com o login e a senha.

        Returns:
            ``True`` se o go2rtc aceitou; ``False`` se não respondeu ou recusou (fica registrado,
            sem a senha).
        """
        nome = _nome(camera_id)
        try:
            resposta = self._cliente.patch(
                f"{self._api}/api/streams",
                params={"name": nome, "src": origem},
                timeout=TEMPO_DO_PEDIDO,
            )
        except httpx.HTTPError as erro:
            _registro.warning(
                "o go2rtc não respondeu ao cadastro de %s: %s", nome, type(erro).__name__
            )
            return False
        if resposta.status_code != httpx.codes.OK:
            _registro.warning(
                "o go2rtc recusou %s (%s) para %s",
                nome,
                resposta.status_code,
                sem_credenciais(origem),
            )
            return False
        return True

    def abridor(
        self, camera_id: str, origem: str, abrir: Callable[[str], Video | None]
    ) -> Callable[[str], Video | None]:
        """Um ``abrir`` que cadastra a câmera no go2rtc antes de abrir o vídeo de lá.

        Sem o cadastro, não abre (``None``): a fonte tenta de novo mais tarde, como faria com a
        câmera que não abriu.
        """

        def abrir_pelo_go2rtc(endereco: str) -> Video | None:
            if not self.cadastrar(camera_id, origem):
                return None
            return abrir(endereco)

        return abrir_pelo_go2rtc


def _nome(camera_id: str) -> str:
    # Com o prefixo: o go2rtc trata como apelido a câmera cujo caminho RTSP é o nome de outra.
    return f"camera-{camera_id}"

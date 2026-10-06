"""O atualizador da caixa (SDD 7.4, D-14 e D-67): troca a versão do agente e volta para a anterior
se a saúde não vier.

Roda no próprio Ubuntu da caixa, fora dos contêineres (um timer do systemd a cada 5 minutos), no
Python do sistema: por isso usa **só a biblioteca padrão**. Uma imagem ruim do agente não leva
junto quem volta atrás. Uso::

    python3 /opt/patio/atualizador.py --pasta /opt/patio/caixa

1. Pergunta à nuvem a versão da caixa, com a chave dela (``GET /api/borda/versao``). Se é a que
   já roda, ou uma que já falhou nesta caixa, não faz nada.
2. Baixa a imagem pelo resumo (o Docker confere o resumo).
3. Troca o agente: grava a imagem e o nome da versão no ``.env`` do compose e sobe o agente.
4. Espera a saúde do agente novo por até 5 minutos: no ar, com as câmeras de placa no ar e aceita
   pela nuvem (o agente grava a última saúde no volume dos dados, ``saude.json``).
5. Se a saúde não vem, volta para a imagem anterior.
6. Conta o resultado à nuvem (``POST /api/borda/atualizacoes``); se a nuvem não responde, o relato
   fica guardado e vai da próxima vez.
"""

import argparse
import json
import logging
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

PRAZO_DA_SAUDE = 300.0
"""Segundos que o agente novo tem para mandar uma saúde boa."""
INTERVALO = 10.0
"""Segundos entre duas leituras da saúde."""
TEMPO_DO_PEDIDO = 30.0
TEMPO_DO_DOCKER = 900.0
"""Segundos para baixar uma imagem ou subir o agente."""

VOLUME_DOS_DADOS = "patio-caixa_dados"
"""O volume ``dados`` do compose ``patio-caixa``: a chave, a configuração, a fila e a saúde."""
IMAGEM_DA_PREPARACAO = "patio-caixa:local"
VERSAO_DA_PREPARACAO = "local"
PREFIXO_DO_RESUMO = "sha256:"
LETRAS_DO_RESUMO = frozenset("0123456789abcdef")

_registro = logging.getLogger("atualizador")


class DockerFalhouError(Exception):
    """O Docker não fez o que foi pedido (a mensagem é a última linha do erro dele)."""


@dataclass(frozen=True)
class Versao:
    """A versão que a nuvem escolheu para a caixa: o nome e a imagem pelo resumo."""

    nome: str
    imagem: str

    @property
    def resumo(self) -> str:
        """O resumo da imagem (``sha256:…``)."""
        return self.imagem.rsplit("@", 1)[1]


class Nuvem(Protocol):
    """O que o atualizador usa da nuvem."""

    def versao(self) -> Versao | None:
        """A versão escolhida para a caixa, ou ``None``."""
        ...

    def contar(self, relato: dict[str, str]) -> None:
        """Conta uma troca de versão."""
        ...


class Docker(Protocol):
    """O que o atualizador usa do Docker."""

    def em_uso(self) -> tuple[str, str]:
        """A imagem e o nome da versão do agente de agora."""
        ...

    def baixar(self, imagem: str) -> None:
        """Baixa a imagem."""
        ...

    def trocar(self, imagem: str, nome: str) -> None:
        """Sobe o agente com a imagem."""
        ...


@dataclass
class Estado:
    """O que o atualizador lembra entre uma vez e outra (num arquivo JSON)."""

    falhas: list[str] = field(default_factory=list)
    """Os resumos que falharam ou voltaram nesta caixa: não são tentados de novo."""
    pendentes: list[dict[str, str]] = field(default_factory=list)
    """Os relatos que a nuvem ainda não recebeu."""

    @classmethod
    def ler(cls, arquivo: Path) -> "Estado":
        """O estado guardado; vazio se não há arquivo ou se ele está estragado."""
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
            falhas, pendentes = dados["falhas"], dados["pendentes"]
        except (OSError, ValueError, KeyError, TypeError):
            return cls()
        if not (
            isinstance(falhas, list)
            and all(isinstance(resumo, str) for resumo in falhas)
            and isinstance(pendentes, list)
            and all(isinstance(relato, dict) for relato in pendentes)
        ):
            return cls()
        return cls(falhas=falhas, pendentes=pendentes)

    def gravar(self, arquivo: Path) -> None:
        """Guarda o estado (grava ao lado e troca de uma vez)."""
        provisorio = arquivo.with_name(f"{arquivo.name}.novo")
        provisorio.write_text(
            json.dumps({"falhas": self.falhas, "pendentes": self.pendentes}), encoding="utf-8"
        )
        provisorio.replace(arquivo)


def atualizar(
    nuvem: Nuvem,
    docker: Docker,
    ler_saude: Callable[[], dict[str, Any] | None],
    estado: Estado,
    *,
    agora: Callable[[], datetime],
    dormir: Callable[[float], object],
    prazo: float = PRAZO_DA_SAUDE,
    intervalo: float = INTERVALO,
) -> str | None:
    """Uma volta do atualizador.

    Returns:
        ``"ok"``, ``"voltou"`` ou ``"falhou"``; ``None`` se não havia o que trocar.
    """
    _mandar_os_pendentes(nuvem, estado)
    try:
        versao = nuvem.versao()
    except (OSError, ValueError) as erro:
        _registro.warning("a nuvem não disse a versão: %s", erro)
        return None
    imagem_antiga, nome_antigo = docker.em_uso()
    if versao is None or versao.imagem == imagem_antiga or versao.resumo in estado.falhas:
        return None
    comeco = agora()
    _registro.info("trocando %s por %s (%s)", imagem_antiga, versao.imagem, versao.nome)
    try:
        docker.baixar(versao.imagem)
    except DockerFalhouError as erro:
        return _terminar(
            nuvem, estado, versao, imagem_antiga, comeco, agora(), "falhou",
            f"a imagem não baixou: {erro}",
        )  # fmt: skip
    try:
        docker.trocar(versao.imagem, versao.nome)
    except DockerFalhouError as erro:
        motivo = f"o agente novo não subiu: {erro}"
    else:
        motivo = _esperar_a_saude(ler_saude, versao, agora(), agora, dormir, prazo, intervalo)
        if not motivo:
            return _terminar(nuvem, estado, versao, imagem_antiga, comeco, agora(), "ok", "")
    try:
        docker.trocar(imagem_antiga, nome_antigo)
    except DockerFalhouError as erro:
        _registro.error("a versão anterior também não subiu: %s", erro)
    return _terminar(nuvem, estado, versao, imagem_antiga, comeco, agora(), "voltou", motivo)


def _esperar_a_saude(
    ler_saude: Callable[[], dict[str, Any] | None],
    versao: Versao,
    trocou_em: datetime,
    agora: Callable[[], datetime],
    dormir: Callable[[float], object],
    prazo: float,
    intervalo: float,
) -> str:
    # Devolve o motivo de a saúde não servir; vazio se ela veio boa.
    motivo = "a saúde do agente novo não chegou em 5 minutos"
    while True:
        lida = ler_saude()
        if lida is not None and _do_agente_novo(lida, versao, trocou_em):
            paradas = [
                str(camera["camera_id"])
                for camera in lida["saude"]["cameras"]
                if not camera["no_ar"]
            ]
            if not lida["aceita"]:
                motivo = "a nuvem não aceitou a saúde do agente novo"
            elif paradas:
                motivo = f"câmeras fora do ar: {', '.join(paradas)}"
            else:
                return ""
        if (agora() - trocou_em).total_seconds() >= prazo:
            return motivo
        dormir(intervalo)


def _do_agente_novo(lida: dict[str, Any], versao: Versao, trocou_em: datetime) -> bool:
    try:
        gravada_em = datetime.fromisoformat(lida["gravada_em"])
        return bool(gravada_em > trocou_em and lida["saude"]["versao_programa"] == versao.nome)
    except (KeyError, TypeError, ValueError):
        return False


def _terminar(
    nuvem: Nuvem,
    estado: Estado,
    versao: Versao,
    de: str,
    comeco: datetime,
    fim: datetime,
    resultado: str,
    motivo: str,
) -> str:
    if resultado != "ok":
        estado.falhas.append(versao.resumo)
        _registro.error("a versão %s %s: %s", versao.nome, resultado, motivo)
    else:
        _registro.info("a versão %s deu certo", versao.nome)
    estado.pendentes.append(
        {
            "de": de,
            "para": versao.resumo,
            "comecou_em": comeco.isoformat(),
            "terminou_em": fim.isoformat(),
            "resultado": resultado,
            "motivo": motivo,
        }
    )
    _mandar_os_pendentes(nuvem, estado)
    return resultado


def _mandar_os_pendentes(nuvem: Nuvem, estado: Estado) -> None:
    while estado.pendentes:
        try:
            nuvem.contar(estado.pendentes[0])
        except OSError as erro:
            _registro.warning("a nuvem não recebeu o relato; vai da próxima vez: %s", erro)
            return
        estado.pendentes.pop(0)


# --- A nuvem, com a chave da caixa ----------------------------------------------------------

Abrir = Callable[..., Any]


class NuvemDaCaixa:
    """A nuvem, pela chave da caixa (a mesma do agente)."""

    def __init__(self, endereco: str, chave: str, *, abrir: Abrir = urllib.request.urlopen) -> None:
        """Prepara os pedidos.

        Args:
            endereco: o endereço da nuvem.
            chave: a chave que a caixa recebeu na ativação.
            abrir: como fazer o pedido (os testes passam uma nuvem falsa).
        """
        self._endereco = endereco.rstrip("/")
        self._chave = chave
        self._abrir = abrir

    def versao(self) -> Versao | None:
        """A versão escolhida para a caixa, ou ``None`` (204).

        Raises:
            OSError: se a nuvem não responde ou recusa.
            ValueError: se a imagem não vem pelo resumo (uma etiqueta muda por baixo).
        """
        pedido = self._pedido("/api/borda/versao")
        with self._abrir(pedido, timeout=TEMPO_DO_PEDIDO) as resposta:
            if resposta.status == 204:
                return None
            dados = json.loads(resposta.read())
        versao = Versao(nome=str(dados["nome"]), imagem=str(dados["imagem"]))
        _, _, resumo = versao.imagem.partition("@")
        letras = resumo.removeprefix(PREFIXO_DO_RESUMO)
        if not (
            resumo.startswith(PREFIXO_DO_RESUMO)
            and len(letras) == 64
            and set(letras) <= LETRAS_DO_RESUMO
        ):
            raise ValueError(f"a imagem não vem pelo resumo: {versao.imagem!r}")
        return versao

    def contar(self, relato: dict[str, str]) -> None:
        """Conta uma troca de versão à nuvem.

        Raises:
            OSError: se a nuvem não responde ou recusa.
        """
        pedido = self._pedido("/api/borda/atualizacoes", json.dumps(relato).encode())
        with self._abrir(pedido, timeout=TEMPO_DO_PEDIDO):
            pass

    def _pedido(self, caminho: str, corpo: bytes | None = None) -> urllib.request.Request:
        cabecalhos = {"Authorization": f"Bearer {self._chave}"}
        if corpo is not None:
            cabecalhos["Content-Type"] = "application/json"
        return urllib.request.Request(
            f"{self._endereco}{caminho}",
            data=corpo,
            headers=cabecalhos,
            method="POST" if corpo is not None else "GET",
        )


# --- O Docker, pelo compose da caixa --------------------------------------------------------

Rodar = Callable[[list[str], Path], "subprocess.CompletedProcess[str]"]


def _rodar(comando: list[str], pasta: Path) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        comando, cwd=pasta, capture_output=True, text=True, timeout=TEMPO_DO_DOCKER, check=False
    )


class DockerDoCompose:
    """O Docker da caixa: o compose de ``pasta`` (``/opt/patio/caixa``) e o ``.env`` dele."""

    def __init__(self, pasta: Path, *, rodar: Rodar = _rodar) -> None:
        """Prepara.

        Args:
            pasta: onde estão o ``compose.yml`` e o ``.env`` da caixa.
            rodar: como rodar um comando (os testes passam um Docker falso).
        """
        self._pasta = pasta
        self._rodar = rodar

    def em_uso(self) -> tuple[str, str]:
        """A imagem e o nome da versão do agente, como estão no ``.env``."""
        valores = self._env()
        return (
            valores.get("IMAGEM_DO_AGENTE", IMAGEM_DA_PREPARACAO),
            valores.get("VERSAO_DO_AGENTE", VERSAO_DA_PREPARACAO),
        )

    def baixar(self, imagem: str) -> None:
        """Baixa a imagem pelo resumo."""
        self._comando(["docker", "pull", imagem])

    def trocar(self, imagem: str, nome: str) -> None:
        """Grava a imagem e o nome no ``.env`` e sobe o agente com eles."""
        valores = self._env()
        valores["IMAGEM_DO_AGENTE"] = imagem
        valores["VERSAO_DO_AGENTE"] = nome
        arquivo = self._pasta / ".env"
        provisorio = arquivo.with_name(".env.novo")
        provisorio.write_text(
            "".join(f"{chave}={valor}\n" for chave, valor in valores.items()), encoding="utf-8"
        )
        provisorio.replace(arquivo)
        self._comando(["docker", "compose", "up", "-d", "--wait", "agente"])

    def ler_do_volume(self, nome: str) -> dict[str, Any] | None:
        """Um arquivo JSON do volume dos dados (a chave da caixa, a última saúde), ou ``None``."""
        saida = self._comando(
            ["docker", "volume", "inspect", "--format", "{{.Mountpoint}}", VOLUME_DOS_DADOS]
        )
        try:
            dados = json.loads((Path(saida.strip()) / nome).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return dados if isinstance(dados, dict) else None

    def _env(self) -> dict[str, str]:
        arquivo = self._pasta / ".env"
        if not arquivo.is_file():
            return {}
        valores = {}
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            chave, igual, valor = linha.partition("=")
            if igual and not chave.lstrip().startswith("#"):
                valores[chave.strip()] = valor.strip()
        return valores

    def _comando(self, comando: list[str]) -> str:
        resultado = self._rodar(comando, self._pasta)
        if resultado.returncode != 0:
            linhas = [
                linha for linha in (resultado.stderr or resultado.stdout).splitlines() if linha
            ]
            raise DockerFalhouError(linhas[-1] if linhas else f"{comando[1]} falhou")
        return resultado.stdout


# --- O programa -----------------------------------------------------------------------------


def principal(argv: list[str] | None = None) -> int:
    """Uma volta do atualizador (o timer do systemd chama a cada 5 minutos).

    Returns:
        0 se deu tudo certo ou não havia o que fazer; 1 se a versão voltou, falhou, ou se falta a
        caixa ativada.
    """
    interpretador = argparse.ArgumentParser(
        prog="atualizador", description="O atualizador da caixa de borda (SDD 7.4, D-67)."
    )
    interpretador.add_argument("--pasta", required=True, help="a pasta do compose da caixa")
    pasta = Path(interpretador.parse_args(argv).pasta)
    docker = DockerDoCompose(pasta)
    try:
        caixa = docker.ler_do_volume("caixa.json")
    except DockerFalhouError as erro:
        _registro.error("o volume dos dados não abriu: %s", erro)
        return 1
    if caixa is None:
        _registro.error("a caixa não está ativada: nada a atualizar")
        return 1
    arquivo_do_estado = pasta / "atualizador.json"
    estado = Estado.ler(arquivo_do_estado)
    resultado = atualizar(
        NuvemDaCaixa(str(caixa["nuvem"]), str(caixa["chave"])),
        docker,
        lambda: docker.ler_do_volume("saude.json"),
        estado,
        agora=lambda: datetime.now(UTC),
        dormir=time.sleep,
    )
    estado.gravar(arquivo_do_estado)
    return 0 if resultado in (None, "ok") else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(principal())

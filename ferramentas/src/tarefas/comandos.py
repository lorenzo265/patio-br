"""Comandos do dia a dia do projeto: ``uv run tarefas <comando>``.

Cada comando é uma sequência de etapas (programas externos) que roda na raiz do repositório
e para na primeira falha. As ferramentas são chamadas como ``python -m <ferramenta>`` com o
mesmo Python do ambiente, o que funciona igual em Windows, Linux e Mac.

Novos comandos entram junto com a tarefa que cria o que eles executam.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

MARCA_DO_WORKSPACE = "[tool.uv.workspace]"
"""Trecho que só aparece no pyproject.toml da raiz do repositório."""

ARQUIVO_COMPOSE = "infra/docker-compose.yml"
"""Serviços do ambiente local, relativos à raiz do repositório."""

ARQUIVO_ALEMBIC = "nuvem/alembic.ini"
"""Configuração das migrações da nuvem, relativa à raiz do repositório."""

CODIGO_PROGRAMA_NAO_ENCONTRADO = 127
"""Mesmo código que o shell devolve quando o programa não existe."""

Executor = Callable[[Sequence[str], Path], int]
"""Roda um programa (argumentos) numa pasta e devolve o código de saída."""


class RaizNaoEncontradaError(Exception):
    """Nenhuma pasta acima do ponto de partida é a raiz do repositório."""


class ProgramaNaoEncontradoError(Exception):
    """O programa de uma etapa não está instalado (ex.: o docker)."""

    def __init__(self, programa: str) -> None:
        super().__init__(programa)
        self.programa = programa


@dataclass(frozen=True)
class Etapa:
    """Um programa a rodar, com um nome curto para o relatório."""

    nome: str
    argumentos: tuple[str, ...]


def _ferramenta(modulo: str, *argumentos: str) -> tuple[str, ...]:
    return (sys.executable, "-m", modulo, *argumentos)


def etapas_do_check() -> list[Etapa]:
    """Devolve as verificações completas: estilo, formato, tipos e testes, nessa ordem."""
    return [
        Etapa("ruff check", _ferramenta("ruff", "check", ".")),
        Etapa("ruff format", _ferramenta("ruff", "format", "--check", ".")),
        Etapa("mypy", _ferramenta("mypy")),
        Etapa("pytest", _ferramenta("pytest")),
    ]


def _compose(*argumentos: str) -> tuple[str, ...]:
    # --project-directory .: o .env usado é o da raiz do repositório, não o de infra/.
    return ("docker", "compose", "-f", ARQUIVO_COMPOSE, "--project-directory", ".", *argumentos)


def etapas_do_up() -> list[Etapa]:
    """Devolve a etapa que reconstrói a API, sobe os serviços locais e espera ficarem saudáveis."""
    return [Etapa("docker compose up", _compose("up", "--build", "-d", "--wait"))]


def etapas_do_down() -> list[Etapa]:
    """Devolve a etapa que derruba os serviços locais, mantendo os dados do banco."""
    return [Etapa("docker compose down", _compose("down"))]


def etapas_do_migrar() -> list[Etapa]:
    """Devolve a etapa que aplica as migrações da nuvem no banco de ``PATIO_URL_BANCO``."""
    return [Etapa("migrações", _ferramenta("alembic", "-c", ARQUIVO_ALEMBIC, "upgrade", "head"))]


def etapas_do_semente() -> list[Etapa]:
    """Devolve a etapa que grava os dados de demonstração no banco de ``PATIO_URL_BANCO``."""
    return [Etapa("dados de demonstração", _ferramenta("nuvem.semente"))]


def etapas_do_modelos() -> list[Etapa]:
    """Devolve a etapa que baixa os modelos do leitor v0 para ``modelos/v0`` (fora do Git)."""
    return [Etapa("modelos do leitor v0", _ferramenta("ml.baixar_modelos"))]


def etapas_do_demo() -> list[Etapa]:
    """Devolve a demonstração do mês 1: sobe tudo, migra, semeia e roda o simulador.

    O simulador ativa uma caixa com a administração da semente e manda a amostra (passagens
    inventadas, com foto desenhada), que aparece na tela da portaria.
    """
    simulador = _ferramenta("simulador", "--demonstracao", "--passagens", "amostra")
    return [
        *etapas_do_up(),
        *etapas_do_migrar(),
        *etapas_do_semente(),
        Etapa("simulador", simulador),
    ]


def etapas_do_test(extras: Sequence[str]) -> list[Etapa]:
    """Devolve só a etapa de testes, repassando ``extras`` ao pytest (ex.: ``-k placa``)."""
    return [Etapa("pytest", _ferramenta("pytest", *extras))]


def encontrar_raiz(partida: Path) -> Path:
    """Sobe a partir de ``partida`` até a pasta cujo pyproject.toml declara o workspace.

    Raises:
        RaizNaoEncontradaError: se nenhuma pasta acima de ``partida`` for a raiz.
    """
    for pasta in (partida, *partida.parents):
        arquivo = pasta / "pyproject.toml"
        if arquivo.is_file() and MARCA_DO_WORKSPACE in arquivo.read_text(encoding="utf-8"):
            return pasta
    raise RaizNaoEncontradaError(f"rode dentro do repositório patio-br (partida: {partida})")


def executar_etapas(etapas: Sequence[Etapa], raiz: Path, executor: Executor, saida: TextIO) -> int:
    """Roda as etapas em ordem dentro de ``raiz`` e para na primeira que falhar.

    Returns:
        0 se todas passaram; senão, o código de saída da etapa que falhou.
    """
    for etapa in etapas:
        print(f"==> {etapa.nome}", file=saida, flush=True)
        codigo = executor(etapa.argumentos, raiz)
        if codigo != 0:
            print(f"falhou: {etapa.nome} (código {codigo})", file=saida)
            return codigo
    print("ok", file=saida)
    return 0


def executar_processo(argumentos: Sequence[str], raiz: Path) -> int:
    """Executor real: roda o programa em ``raiz`` mostrando a saída dele no terminal.

    Raises:
        ProgramaNaoEncontradoError: se o programa não estiver instalado.
    """
    try:
        return subprocess.run(argumentos, cwd=raiz, check=False).returncode
    except FileNotFoundError as erro:
        raise ProgramaNaoEncontradoError(argumentos[0]) from erro


_SEM_ARGUMENTOS: dict[str, Callable[[], list[Etapa]]] = {
    "check": etapas_do_check,
    "up": etapas_do_up,
    "down": etapas_do_down,
    "migrar": etapas_do_migrar,
    "semente": etapas_do_semente,
    "modelos": etapas_do_modelos,
    "demo": etapas_do_demo,
}
"""Comandos que não aceitam argumentos extras e as etapas de cada um."""


def _interpretador() -> argparse.ArgumentParser:
    interpretador = argparse.ArgumentParser(prog="tarefas", description=__doc__)
    comandos = interpretador.add_subparsers(dest="comando", required=True)
    comandos.add_parser("check", help="estilo, formato, tipos e testes")
    comandos.add_parser("test", help="só os testes; o que vier depois vai para o pytest")
    comandos.add_parser("up", help="sobe o ambiente local (bancos e API) e espera ficar pronto")
    comandos.add_parser("down", help="derruba o ambiente local, mantendo os dados")
    comandos.add_parser("migrar", help="aplica as migrações da nuvem no banco de desenvolvimento")
    comandos.add_parser(
        "semente", help="grava os dados de demonstração no banco de desenvolvimento"
    )
    comandos.add_parser("modelos", help="baixa os modelos do leitor v0 (conferindo o SHA-256)")
    comandos.add_parser(
        "demo", help="demonstração: sobe tudo, semeia e manda passagens pelo simulador"
    )
    return interpretador


def principal(
    argv: Sequence[str] | None = None,
    *,
    partida: Path | None = None,
    executor: Executor = executar_processo,
    saida: TextIO = sys.stdout,
) -> int:
    """Ponto de entrada do comando ``tarefas``.

    Args:
        argv: argumentos da linha de comando (padrão: os do processo).
        partida: pasta a partir da qual procurar a raiz (padrão: a pasta atual).
        executor: quem roda cada etapa (os testes trocam por um falso).
        saida: onde escrever o relatório.

    Returns:
        O código de saída do comando (0 = sucesso).
    """
    interpretador = _interpretador()
    # parse_known_args: opções do pytest como `-k placa` não são do `tarefas`; ficam em extras.
    argumentos, extras = interpretador.parse_known_args(argv)
    if argumentos.comando == "test":
        etapas = etapas_do_test(extras)
    else:
        if extras:
            interpretador.error(f"argumentos não reconhecidos: {' '.join(extras)}")
        etapas = _SEM_ARGUMENTOS[argumentos.comando]()
    try:
        raiz = encontrar_raiz(partida or Path.cwd())
    except RaizNaoEncontradaError as erro:
        print(f"erro: {erro}", file=saida)
        return 1
    try:
        return executar_etapas(etapas, raiz, executor, saida)
    except ProgramaNaoEncontradoError as erro:
        print(
            f"erro: o programa '{erro.programa}' não foi encontrado; instale-o e tente de novo "
            "(o docker vem com o Docker Desktop, que precisa estar aberto)",
            file=saida,
        )
        return CODIGO_PROGRAMA_NAO_ENCONTRADO

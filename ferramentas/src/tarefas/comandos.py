"""Comandos do dia a dia do projeto: ``uv run tarefas <comando>``.

Cada comando é uma sequência de etapas (programas externos) que roda na raiz do repositório
e para na primeira falha. As ferramentas são chamadas como ``python -m <ferramenta>`` com o
mesmo Python do ambiente, o que funciona igual em Windows, Linux e Mac.

Novos comandos entram junto com a tarefa que cria o que eles executam (``up``/``down`` na
T04, ``migrar`` na T07, ``semente`` na T08, ``demo`` na T19).
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

Executor = Callable[[Sequence[str], Path], int]
"""Roda um programa (argumentos) numa pasta e devolve o código de saída."""


class RaizNaoEncontradaError(Exception):
    """Nenhuma pasta acima do ponto de partida é a raiz do repositório."""


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
    """Executor real: roda o programa em ``raiz`` mostrando a saída dele no terminal."""
    return subprocess.run(argumentos, cwd=raiz, check=False).returncode


def _interpretador() -> argparse.ArgumentParser:
    interpretador = argparse.ArgumentParser(prog="tarefas", description=__doc__)
    comandos = interpretador.add_subparsers(dest="comando", required=True)
    comandos.add_parser("check", help="estilo, formato, tipos e testes")
    comandos.add_parser("test", help="só os testes; o que vier depois vai para o pytest")
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
    if argumentos.comando == "check":
        if extras:
            interpretador.error(f"argumentos não reconhecidos: {' '.join(extras)}")
        etapas = etapas_do_check()
    else:
        etapas = etapas_do_test(extras)
    try:
        raiz = encontrar_raiz(partida or Path.cwd())
    except RaizNaoEncontradaError as erro:
        print(f"erro: {erro}", file=saida)
        return 1
    return executar_etapas(etapas, raiz, executor, saida)

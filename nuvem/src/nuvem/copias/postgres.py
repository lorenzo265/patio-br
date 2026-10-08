"""O banco de verdade da cópia e da restauração de teste: o ``pg_dump`` e o ``pg_restore`` (D-74).

Os dois são do cliente do PostgreSQL da mesma versão do servidor (16), que vem na imagem da
nuvem. A conexão vai pelas variáveis do próprio PostgreSQL (``PGHOST``, ``PGPASSWORD`` ...),
montadas da ``PATIO_URL_BANCO``: a senha não aparece na lista de processos.

A restauração de teste cria um banco temporário no mesmo servidor (``patio_restauracao_...``),
volta a cópia nele e o apaga no fim, dê certo ou não. Nada é apagado fora dele.
"""

import os
import re
import ssl
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import IO
from uuid import uuid4

from sqlalchemy import URL, Engine, make_url, text
from sqlalchemy.orm import Session

from nuvem.banco import contexto_ssl, criar_motor
from nuvem.config import Configuracao
from nuvem.copias.guarda import Legivel
from nuvem.registro import mascarar

PREFIXO_DO_TEMPORARIO = "patio_restauracao_"
NOME_DO_TEMPORARIO = re.compile(PREFIXO_DO_TEMPORARIO + "[0-9a-f]{12}")
TAMANHO_DO_PEDACO = 1024 * 1024
ERRO_MAXIMO = 500
"""Quantos caracteres do fim do erro do ``pg_dump`` ou do ``pg_restore`` entram na mensagem."""


class ProgramaFalhouError(Exception):
    """O ``pg_dump`` ou o ``pg_restore`` terminou com erro."""


def _erros(arquivo: IO[bytes]) -> str:
    arquivo.seek(0)
    texto = arquivo.read().decode("utf-8", errors="replace").strip()
    return mascarar(texto[-ERRO_MAXIMO:])


@dataclass(frozen=True)
class BancoPostgres:
    """O servidor do banco da nuvem, para copiar e para a restauração de teste."""

    url: URL
    contexto: ssl.SSLContext | None
    """O SSL das conexões do SQLAlchemy (o mesmo da nuvem)."""
    certificado: str | None
    """O certificado da autoridade do banco (PEM), quando não é pública (o do RDS)."""

    @classmethod
    def da_configuracao(cls, configuracao: Configuracao) -> "BancoPostgres":
        """O banco da ``PATIO_URL_BANCO``, com o SSL da configuração."""
        return cls(
            url=make_url(configuracao.url_banco.get_secret_value()),
            contexto=contexto_ssl(configuracao),
            certificado=configuracao.banco_ca if configuracao.banco_ssl else None,
        )

    def _ambiente(self, pasta: Path) -> dict[str, str]:
        ambiente = {
            "PATH": os.environ.get("PATH", os.defpath),
            "PGHOST": self.url.host or "localhost",
            "PGPORT": str(self.url.port or 5432),
            "PGUSER": self.url.username or "",
            "PGPASSWORD": self.url.password or "",
            "PGDATABASE": self.url.database or "",
            "PGCONNECT_TIMEOUT": "10",
            "PGAPPNAME": "patio-copias",
        }
        if self.contexto is not None:
            # Como a nuvem: confere o certificado e o nome do servidor.
            ambiente["PGSSLMODE"] = "verify-full"
            if self.certificado:
                arquivo = pasta / "autoridade.pem"
                arquivo.write_text(self.certificado, encoding="utf-8")
                ambiente["PGSSLROOTCERT"] = str(arquivo)
            else:
                ambiente["PGSSLROOTCERT"] = "system"
        return ambiente

    @contextmanager
    def despejar(self) -> Iterator[Legivel]:
        """O ``pg_dump`` do banco (no formato do próprio PostgreSQL), para ler até o fim.

        Raises:
            ProgramaFalhouError: se o ``pg_dump`` terminar com erro (ao sair do ``with``).
        """
        with tempfile.TemporaryDirectory() as pasta, tempfile.TemporaryFile() as erros:
            processo = subprocess.Popen(
                ["pg_dump", "--format=custom"],
                stdout=subprocess.PIPE,
                stderr=erros,
                env=self._ambiente(Path(pasta)),
            )
            assert processo.stdout is not None
            try:
                yield processo.stdout
                sobrou = processo.stdout.read(1)
            except BaseException:
                processo.kill()
                processo.wait()
                raise
            if sobrou:
                processo.kill()
                processo.wait()
                raise ProgramaFalhouError("a cópia não foi lida até o fim")
            codigo = processo.wait()
            if codigo != 0:
                raise ProgramaFalhouError(f"o pg_dump terminou com {codigo}: {_erros(erros)}")

    @contextmanager
    def restaurar(self, leitor: Legivel) -> Iterator[Session]:
        """Volta a cópia num banco temporário e dá uma sessão nele; no fim, apaga o banco.

        Raises:
            ProgramaFalhouError: se o ``pg_restore`` terminar com erro.
        """
        nome = PREFIXO_DO_TEMPORARIO + uuid4().hex[:12]
        servidor = self._motor(self.url)
        try:
            self._sem_transacao(servidor, f'CREATE DATABASE "{nome}"')
            try:
                self._pg_restore(nome, leitor)
                temporario = self._motor(self.url.set(database=nome))
                try:
                    with Session(temporario) as sessao:
                        yield sessao
                finally:
                    temporario.dispose()
            finally:
                assert NOME_DO_TEMPORARIO.fullmatch(nome)  # nunca outro banco
                self._sem_transacao(servidor, f'DROP DATABASE IF EXISTS "{nome}" WITH (FORCE)')
        finally:
            servidor.dispose()

    def _motor(self, url: URL) -> Engine:
        return criar_motor(
            url.render_as_string(hide_password=False), sem_pool=True, contexto=self.contexto
        )

    @staticmethod
    def _sem_transacao(motor: Engine, comando: str) -> None:
        # CREATE e DROP DATABASE não rodam dentro de uma transação.
        with motor.connect() as conexao:
            conexao.execution_options(isolation_level="AUTOCOMMIT").execute(text(comando))

    def _pg_restore(self, nome: str, leitor: Legivel) -> None:
        with tempfile.TemporaryDirectory() as pasta, tempfile.TemporaryFile() as erros:
            processo = subprocess.Popen(
                ["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error",
                 "--dbname", nome],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=erros,
                env=self._ambiente(Path(pasta)),
            )  # fmt: skip
            assert processo.stdin is not None
            try:
                _passar(leitor, processo.stdin)
            except BaseException:
                processo.kill()
                processo.wait()
                raise
            codigo = processo.wait()
            if codigo != 0:
                raise ProgramaFalhouError(f"o pg_restore terminou com {codigo}: {_erros(erros)}")


def _passar(leitor: Legivel, entrada: IO[bytes]) -> None:
    """Passa tudo de ``leitor`` para ``entrada`` e a fecha; lê até o fim mesmo se ela fechar.

    Ler até o fim deixa o resumo de quem lê completo; se o ``pg_restore`` parou antes, o código
    de saída dele diz por quê.
    """
    try:
        while pedaco := leitor.read(TAMANHO_DO_PEDACO):
            entrada.write(pedaco)
    except BrokenPipeError:
        while leitor.read(TAMANHO_DO_PEDACO):
            pass
    with suppress(BrokenPipeError):
        entrada.close()

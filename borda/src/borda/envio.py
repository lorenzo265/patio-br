"""Fila de envio da caixa (SDD 7.4, D-24): nenhuma passagem se perde se a internet cair.

1. Toda passagem é gravada primeiro na fila (SQLite, no disco da caixa), com as fotos.
2. O remetente envia na ordem em que as passagens aconteceram: as fotos e depois a passagem.
3. Falha passageira (rede, 5xx, 401, 408, 429): espera 1 s, 2 s, 4 s... até 5 min e tenta a
   mesma passagem de novo, sem passar à frente.
4. 201 ou 200: a passagem sai da fila.
5. Recusa definitiva (403, 409, 422): a passagem sai da fila e fica guardada à parte, com o
   motivo, para não travar as seguintes. Foto recusada de vez (409, 413, 415) fica de fora.
"""

import logging
import sqlite3
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from uuid import UUID

import httpx

from contratos.passagem import Passagem
from contratos.saude import Saude

ESPERA_INICIAL = 1.0
ESPERA_MAXIMA = 300.0
"""5 minutos: o máximo entre duas tentativas, com a internet fora."""

RECUSA_DA_PASSAGEM = frozenset({403, 409, 422})
"""Respostas que não mudam se a mesma passagem for de novo (outro site, id de outra caixa,
campo que não confere)."""

RECUSA_DA_FOTO = frozenset({409, 413, 415})
"""Outra foto no mesmo ref, grande demais, não é JPEG."""

RECUSA_DA_SAUDE = frozenset({403, 422})
"""A saúde de outra caixa, ou fora do formato: a próxima vai do mesmo jeito."""

_registro = logging.getLogger(__name__)

_TABELAS = """
create table if not exists passagem (
    id text primary key,
    inicio real not null,
    conteudo text not null,
    guardada_em real not null
);
create table if not exists foto (
    passagem_id text not null references passagem (id) on delete cascade,
    ref text not null,
    conteudo blob not null,
    primary key (passagem_id, ref)
);
create table if not exists recusada (
    id text primary key,
    conteudo text not null,
    codigo integer not null,
    motivo text not null,
    recusada_em real not null
);
"""


@dataclass(frozen=True)
class PassagemNaFila:
    """A próxima passagem a enviar, com as fotos que ainda não foram."""

    passagem: Passagem
    fotos: dict[str, bytes]


@dataclass(frozen=True)
class ContagemDaFila:
    """O tamanho da fila, para a saúde da caixa (D-65)."""

    passagens: int
    """As passagens esperando o envio."""
    fotos: int
    """As fotos esperando o envio."""
    recusadas: int
    """As passagens recusadas de vez, guardadas à parte."""


@dataclass(frozen=True)
class PassagemRecusada:
    """Uma passagem que a nuvem recusou de vez, guardada para o suporte ver."""

    passagem: Passagem
    codigo: int
    motivo: str


class FilaDeEnvio:
    """As passagens que ainda não chegaram à nuvem, num arquivo SQLite."""

    def __init__(self, arquivo: Path) -> None:
        """Abre (ou cria) a fila no arquivo."""
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        # Uma conexão só, protegida por uma trava: a captura guarda e o remetente envia, cada
        # um na sua linha de execução.
        self._conexao = sqlite3.connect(arquivo, check_same_thread=False, isolation_level=None)
        self._trava = threading.Lock()
        with self._trava:
            self._conexao.execute("pragma journal_mode = wal")
            self._conexao.execute("pragma synchronous = full")  # gravada = no disco
            self._conexao.execute("pragma foreign_keys = on")
            self._conexao.executescript(_TABELAS)

    def guardar(self, passagem: Passagem, fotos: Mapping[str, bytes] | None = None) -> None:
        """Grava a passagem e as fotos dela na fila (a mesma passagem de novo não duplica)."""
        with self._trava, self._conexao:
            self._conexao.execute("begin")
            self._conexao.execute(
                "insert or ignore into passagem (id, inicio, conteudo, guardada_em)"
                " values (?, ?, ?, ?)",
                (
                    str(passagem.id),
                    passagem.inicio.timestamp(),
                    passagem.model_dump_json(),
                    time.time(),
                ),
            )
            self._conexao.executemany(
                "insert or ignore into foto (passagem_id, ref, conteudo) values (?, ?, ?)",
                [(str(passagem.id), ref, conteudo) for ref, conteudo in (fotos or {}).items()],
            )

    def pendentes(self) -> int:
        """Quantas passagens esperam o envio."""
        with self._trava:
            linha = self._conexao.execute("select count(*) from passagem").fetchone()
        return int(linha[0])

    def contagem(self) -> ContagemDaFila:
        """Quantas passagens e fotos esperam o envio, e quantas passagens foram recusadas."""
        with self._trava:
            passagens, fotos, recusadas = self._conexao.execute(
                "select (select count(*) from passagem), (select count(*) from foto),"
                " (select count(*) from recusada)"
            ).fetchone()
        return ContagemDaFila(passagens=passagens, fotos=fotos, recusadas=recusadas)

    def proxima(self) -> PassagemNaFila | None:
        """A passagem mais antiga (pelo início), com as fotos que faltam enviar."""
        with self._trava:
            linha = self._conexao.execute(
                "select id, conteudo from passagem order by inicio, rowid limit 1"
            ).fetchone()
            if linha is None:
                return None
            fotos = self._conexao.execute(
                "select ref, conteudo from foto where passagem_id = ? order by ref", (linha[0],)
            ).fetchall()
        passagem = Passagem.model_validate_json(linha[1])
        return PassagemNaFila(passagem=passagem, fotos={ref: bytes(c) for ref, c in fotos})

    def tirar_foto(self, passagem_id: UUID, ref: str) -> None:
        """A foto chegou (ou foi recusada de vez): não vai mais."""
        with self._trava:
            self._conexao.execute(
                "delete from foto where passagem_id = ? and ref = ?", (str(passagem_id), ref)
            )

    def retirar(self, passagem_id: UUID) -> None:
        """A passagem chegou à nuvem: sai da fila."""
        with self._trava:
            self._conexao.execute("delete from passagem where id = ?", (str(passagem_id),))

    def recusar(self, passagem_id: UUID, codigo: int, motivo: str) -> None:
        """A nuvem recusou a passagem de vez: sai da fila e fica guardada à parte."""
        with self._trava, self._conexao:
            self._conexao.execute("begin")
            self._conexao.execute(
                "insert or replace into recusada (id, conteudo, codigo, motivo, recusada_em)"
                " select id, conteudo, ?, ?, ? from passagem where id = ?",
                (codigo, motivo, time.time(), str(passagem_id)),
            )
            self._conexao.execute("delete from passagem where id = ?", (str(passagem_id),))

    def recusadas(self) -> list[PassagemRecusada]:
        """As passagens recusadas de vez, das mais antigas para as mais novas."""
        with self._trava:
            linhas = self._conexao.execute(
                "select conteudo, codigo, motivo from recusada order by recusada_em, rowid"
            ).fetchall()
        return [
            PassagemRecusada(Passagem.model_validate_json(conteudo), int(codigo), str(motivo))
            for conteudo, codigo, motivo in linhas
        ]

    def fechar(self) -> None:
        """Fecha o arquivo da fila."""
        with self._trava:
            self._conexao.close()


class Resultado(Enum):
    """O que a nuvem respondeu, do ponto de vista da fila."""

    ACEITA = "aceita"
    DE_NOVO = "de novo"
    RECUSADA = "recusada"


@dataclass(frozen=True)
class Resposta:
    """A resposta da nuvem a um envio."""

    resultado: Resultado
    codigo: int | None = None
    """O código HTTP (``None`` quando nem chegou à nuvem)."""
    motivo: str = ""


class Nuvem:
    """O lado da nuvem que a caixa usa: fotos e passagens, com a chave da caixa."""

    def __init__(self, endereco: str, chave: str, *, cliente: httpx.Client | None = None) -> None:
        """Prepara o envio.

        Args:
            endereco: o endereço da nuvem (ex.: ``https://patio.exemplo.com.br``).
            chave: a chave que a caixa recebeu na ativação.
            cliente: o cliente HTTP (os testes passam uma nuvem falsa).
        """
        self._endereco = endereco.rstrip("/")
        self._autorizacao = {"Authorization": f"Bearer {chave}"}
        self._cliente = cliente or httpx.Client(timeout=30)

    def enviar_foto(self, ref: str, conteudo: bytes) -> Resposta:
        """Pede o endereço de envio e manda a foto para ele (sem a chave, como no S3)."""
        try:
            pedido = self._cliente.post(
                f"{self._endereco}/api/borda/fotos/endereco",
                json={"ref": ref},
                headers=self._autorizacao,
            )
            if pedido.status_code == httpx.codes.UNPROCESSABLE_ENTITY:
                return Resposta(Resultado.RECUSADA, pedido.status_code, pedido.text)
            if pedido.status_code != httpx.codes.OK:
                return Resposta(Resultado.DE_NOVO, pedido.status_code, pedido.text)
            endereco = _endereco_de_envio(pedido)
            if endereco is None:
                # Ex.: um portal de wi-fi ou um proxy que responde 200 com uma página.
                motivo = "a resposta não trouxe o endereço de envio"
                return Resposta(Resultado.DE_NOVO, pedido.status_code, motivo)
            envio = self._cliente.put(
                endereco, content=conteudo, headers={"Content-Type": "image/jpeg"}
            )
        except httpx.HTTPError as erro:
            return Resposta(Resultado.DE_NOVO, motivo=f"sem resposta da nuvem: {erro}")
        return _classificar(envio, recusa=RECUSA_DA_FOTO)

    def enviar_passagem(self, passagem: Passagem) -> Resposta:
        """Manda a passagem (as fotos dela já devem ter ido)."""
        try:
            resposta = self._cliente.post(
                f"{self._endereco}/api/borda/passagens",
                content=passagem.model_dump_json(),
                headers={**self._autorizacao, "Content-Type": "application/json"},
            )
        except httpx.HTTPError as erro:
            return Resposta(Resultado.DE_NOVO, motivo=f"sem resposta da nuvem: {erro}")
        return _classificar(resposta, recusa=RECUSA_DA_PASSAGEM)

    def enviar_saude(self, saude: Saude) -> Resposta:
        """Manda a saúde da caixa (D-65); quem chama não tenta de novo, só registra."""
        try:
            resposta = self._cliente.post(
                f"{self._endereco}/api/borda/saude",
                content=saude.model_dump_json(),
                headers={**self._autorizacao, "Content-Type": "application/json"},
            )
        except httpx.HTTPError as erro:
            return Resposta(Resultado.DE_NOVO, motivo=f"sem resposta da nuvem: {erro}")
        if resposta.status_code == httpx.codes.NO_CONTENT:
            return Resposta(Resultado.ACEITA, resposta.status_code)
        return _classificar(resposta, recusa=RECUSA_DA_SAUDE)


def _endereco_de_envio(pedido: httpx.Response) -> str | None:
    try:
        endereco = pedido.json()["endereco"]
    except (ValueError, KeyError, TypeError):
        return None
    return endereco if isinstance(endereco, str) else None


def _classificar(resposta: httpx.Response, *, recusa: frozenset[int]) -> Resposta:
    if resposta.status_code in (httpx.codes.OK, httpx.codes.CREATED):
        return Resposta(Resultado.ACEITA, resposta.status_code)
    resultado = Resultado.RECUSADA if resposta.status_code in recusa else Resultado.DE_NOVO
    return Resposta(resultado, resposta.status_code, resposta.text)


class Remetente:
    """Esvazia a fila, na ordem, esperando mais a cada falha seguida."""

    def __init__(
        self,
        fila: FilaDeEnvio,
        nuvem: Nuvem,
        *,
        dormir: Callable[[float], object] | None = None,
        parar: threading.Event | None = None,
    ) -> None:
        """Prepara o remetente.

        Args:
            fila: de onde as passagens saem.
            nuvem: para onde vão.
            dormir: como esperar entre tentativas (o padrão é esperar o evento ``parar``,
                que também interrompe a espera; os testes só anotam quanto esperariam).
            parar: quando ligado, o remetente para depois do envio em curso.
        """
        self._fila = fila
        self._nuvem = nuvem
        self._parar = parar or threading.Event()
        self._dormir = dormir or self._parar.wait
        self._espera = ESPERA_INICIAL

    def enviar_pendentes(self) -> None:
        """Envia até a fila esvaziar (ou até pedirem para parar)."""
        while not self._parar.is_set() and self._fila.pendentes():
            if self.enviar_uma():
                self._espera = ESPERA_INICIAL
            else:
                self._dormir(self._espera)
                self._espera = min(self._espera * 2, ESPERA_MAXIMA)

    def rodar(self) -> None:
        """Fica enviando até pedirem para parar (o processo da caixa roda isto numa linha)."""
        while not self._parar.is_set():
            try:
                self.enviar_pendentes()
            except Exception:
                # Um erro que ninguém previu não pode parar o envio de vez (a fila só cresceria):
                # fica registrado, e o envio tenta de novo, esperando mais a cada vez.
                _registro.exception("erro inesperado no envio; tentando de novo")
                self._dormir(self._espera)
                self._espera = min(self._espera * 2, ESPERA_MAXIMA)
            self._parar.wait(1)

    def enviar_uma(self) -> bool:
        """Tenta enviar a próxima passagem.

        Returns:
            ``True`` se ela saiu da fila (aceita ou recusada de vez); ``False`` se a fila está
            vazia ou se é preciso tentar de novo mais tarde.
        """
        item = self._fila.proxima()
        if item is None:
            return False
        passagem = item.passagem
        for ref, conteudo in item.fotos.items():
            resposta = self._nuvem.enviar_foto(ref, conteudo)
            if resposta.resultado is Resultado.DE_NOVO:
                _registro.warning("foto %s não foi: %s", ref, resposta.motivo or resposta.codigo)
                return False
            if resposta.resultado is Resultado.RECUSADA:
                _registro.error("foto %s recusada de vez (%s)", ref, resposta.codigo)
            self._fila.tirar_foto(passagem.id, ref)
        resposta = self._nuvem.enviar_passagem(passagem)
        if resposta.resultado is Resultado.ACEITA:
            self._fila.retirar(passagem.id)
            return True
        if resposta.resultado is Resultado.RECUSADA:
            _registro.error("passagem %s recusada de vez (%s)", passagem.id, resposta.codigo)
            self._fila.recusar(passagem.id, resposta.codigo or 0, resposta.motivo)
            return True
        _registro.warning(
            "passagem %s não foi: %s", passagem.id, resposta.motivo or resposta.codigo
        )
        return False

"""Resumo de senhas e PINs com argon2id (SDD 8.2).

Guarda-se só o resumo: dá para conferir se uma senha bate, nunca para recuperá-la. O argon2 é
lento de propósito (e gasta memória), o que torna caro adivinhar senhas a partir de um banco
copiado. O resumo leva junto o sal e o custo usado, então mudar o custo não invalida os resumos
antigos: eles são refeitos quando a pessoa entra.
"""

import hashlib
import threading
from functools import cached_property

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request

RESUMOS_AO_MESMO_TEMPO = 4
"""Quantos resumos o processo faz ao mesmo tempo; os outros esperam a vez (SDD 8.2).

Cada resumo gasta 64 MiB: sem limite, uma enxurrada de logins (cada um com outro e-mail, o que
o limite de tentativas não barra) esgotaria a memória do servidor.
"""


class Senhas:
    """Faz e confere resumos de senhas e PINs."""

    def __init__(
        self, resumidor: PasswordHasher | None = None, ao_mesmo_tempo: int = RESUMOS_AO_MESMO_TEMPO
    ) -> None:
        """Prepara o resumidor.

        Args:
            resumidor: o argon2 configurado; o padrão segue a recomendação de baixa memória da
                RFC 9106 (64 MiB). Os testes passam um de custo mínimo.
            ao_mesmo_tempo: quantos resumos podem correr juntos.
        """
        self._resumidor = resumidor or PasswordHasher()
        self._vez = threading.BoundedSemaphore(ao_mesmo_tempo)

    def resumir(self, segredo: str) -> str:
        """Devolve o resumo do segredo, pronto para gravar."""
        with self._vez:
            return self._resumidor.hash(segredo)

    def confere(self, resumo: str, segredo: str) -> bool:
        """Diz se o segredo é o que gerou o resumo (resumo estragado nunca confere)."""
        try:
            with self._vez:
                return self._resumidor.verify(resumo, segredo)
        except (VerificationError, InvalidHashError):
            return False

    def precisa_refazer(self, resumo: str) -> bool:
        """Diz se o resumo foi feito com um custo diferente do atual."""
        return self._resumidor.check_needs_rehash(resumo)

    def gastar_o_mesmo_tempo(self, segredo: str) -> None:
        """Gasta o tempo de uma conferência, sem conferir nada.

        Usado quando não há resumo para comparar (e-mail que não existe): assim o tempo da
        resposta não revela quais e-mails existem.
        """
        self.confere(self._resumo_qualquer, segredo)

    @cached_property
    def _resumo_qualquer(self) -> str:
        return self.resumir("resumo-que-nenhuma-senha-confere")


def resumo_rapido(texto: str) -> str:
    """Resumo SHA-256 (64 caracteres), para códigos aleatórios e longos que a nuvem só confere.

    Serve ao código da sessão, à chave da caixa e ao código de ativação: sorteados pela nuvem,
    já são impossíveis de adivinhar, e o resumo só impede que uma cópia do banco os entregue.
    Senha e PIN, que pessoas escolhem, usam ``Senhas`` (argon2), que é lento de propósito.
    Também resume o alvo das tentativas de login, só para a tabela não guardar o e-mail.
    """
    return hashlib.sha256(texto.encode()).hexdigest()


def obter_senhas(request: Request) -> Senhas:
    """Dependência do FastAPI: o resumidor de senhas da aplicação."""
    senhas: Senhas = request.app.state.senhas
    return senhas

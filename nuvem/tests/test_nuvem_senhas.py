"""Resumo de senhas e PINs com argon2 (SDD 8.2): guarda-se o resumo, nunca o texto."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from argon2 import PasswordHasher, extract_parameters

from nuvem.senhas import Senhas

RAPIDAS = Senhas(PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
MEMORIA_MINIMA_KIB = 19 * 1024
"""Mínimo de memória recomendado pela OWASP para o argon2id (19 MiB)."""


def test_resumo_nao_contem_a_senha() -> None:
    assert "segredo-do-teste" not in RAPIDAS.resumir("segredo-do-teste")


def test_resumo_usa_argon2id() -> None:
    assert RAPIDAS.resumir("segredo-do-teste").startswith("$argon2id$")


def test_confere_a_senha_certa() -> None:
    resumo = RAPIDAS.resumir("segredo-do-teste")

    assert RAPIDAS.confere(resumo, "segredo-do-teste")


def test_recusa_a_senha_errada() -> None:
    resumo = RAPIDAS.resumir("segredo-do-teste")

    assert not RAPIDAS.confere(resumo, "segredo-do-tesTe")


def test_a_mesma_senha_da_resumos_diferentes() -> None:
    # Cada resumo leva um sal aleatório: dois usuários com a mesma senha não se denunciam.
    assert RAPIDAS.resumir("segredo-do-teste") != RAPIDAS.resumir("segredo-do-teste")


def test_resumo_estragado_nao_confere() -> None:
    assert not RAPIDAS.confere("isto-nao-e-um-resumo", "segredo-do-teste")


def test_o_padrao_usa_pelo_menos_o_custo_recomendado() -> None:
    parametros = extract_parameters(Senhas().resumir("segredo-do-teste"))

    assert parametros.memory_cost >= MEMORIA_MINIMA_KIB


def test_resumo_feito_com_custo_menor_pede_para_ser_refeito() -> None:
    # Ao entrar, a senha certa refaz o resumo com o custo atual (ex.: depois de subir o custo).
    assert Senhas().precisa_refazer(RAPIDAS.resumir("segredo-do-teste"))


def test_gastar_o_mesmo_tempo_nao_falha() -> None:
    # Usado quando o e-mail não existe: o tempo da resposta não pode revelar quem existe.
    RAPIDAS.gastar_o_mesmo_tempo("qualquer-senha")


class _ResumidorQueConta(PasswordHasher):
    """Confere devagar e anota quantas conferências correram ao mesmo tempo."""

    def __init__(self) -> None:
        super().__init__(time_cost=1, memory_cost=8, parallelism=1)
        self._trava = threading.Lock()
        self._correndo = 0
        self.maximo = 0

    def verify(self, hash: str | bytes, password: str | bytes) -> Literal[True]:
        with self._trava:
            self._correndo += 1
            self.maximo = max(self.maximo, self._correndo)
        time.sleep(0.02)
        with self._trava:
            self._correndo -= 1
        return True


def test_resumos_ao_mesmo_tempo_tem_limite() -> None:
    # Cada resumo de verdade gasta 64 MiB: sem limite, muitos logins juntos esgotam a memória.
    resumidor = _ResumidorQueConta()
    senhas = Senhas(resumidor, ao_mesmo_tempo=2)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: senhas.confere("resumo", "segredo"), range(16)))

    assert resumidor.maximo == 2

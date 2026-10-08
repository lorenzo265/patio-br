"""O comando da administração no servidor (SDD 8.2): ``python -m nuvem.administracao``.

- ``uv run python -m nuvem.administracao --nome "Fulano" --email fulano@exemplo.com`` pede a
  senha duas vezes, sem mostrar, e cria a conta no banco de ``PATIO_URL_BANCO``. É assim que a
  administração nasce fora do ambiente local, onde a semente não roda.
- ``uv run python -m nuvem.administracao --zerar-duas-etapas --email fulano@exemplo.com`` zera a
  verificação em duas etapas de quem perdeu o celular e fecha as sessões dele (D-60). Na
  próxima entrada, ele liga a verificação de novo. Serve para a administração, que não tem
  quem a zere pelo painel (o usuário do cliente, a administração zera pelo painel).
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence
from contextlib import closing
from datetime import UTC, datetime
from typing import TextIO

from sqlalchemy.orm import Session

from nuvem.banco import motor_da_configuracao
from nuvem.cadastro import login
from nuvem.cadastro import servico as cadastro
from nuvem.config import ConfiguracaoInvalidaError, ler_configuracao
from nuvem.erros import DadoInvalidoError
from nuvem.senhas import Senhas


def principal(
    argumentos: Sequence[str] | None = None,
    *,
    abrir_sessao: Callable[[], Session] | None = None,
    senhas: Senhas | None = None,
    ler_senha: Callable[[str], str] = getpass.getpass,
    saida: TextIO = sys.stdout,
) -> int:
    """Cria a conta, ou zera a verificação em duas etapas; devolve 0 se deu certo, 1 se não.

    A mensagem diz por quê, sem a senha.

    Args:
        abrir_sessao: de onde vem a sessão do banco; sem ela, do ``PATIO_URL_BANCO``.
        ler_senha: como a senha é pedida (os testes trocam).
    """
    interpretador = argparse.ArgumentParser(
        prog="python -m nuvem.administracao",
        description="Cria alguém da administração, ou zera a verificação em duas etapas.",
    )
    interpretador.add_argument("--nome")
    interpretador.add_argument("--email", required=True)
    interpretador.add_argument("--zerar-duas-etapas", action="store_true")
    opcoes = interpretador.parse_args(argumentos)
    if not opcoes.zerar_duas_etapas and not opcoes.nome:
        interpretador.error("para criar a conta, diga o --nome")

    def trabalho(sessao: Session) -> int:
        if opcoes.zerar_duas_etapas:
            return _zerar(sessao, opcoes.email, saida)
        return _criar(sessao, senhas or Senhas(), opcoes.nome, opcoes.email, senha, saida)

    senha = ""
    if not opcoes.zerar_duas_etapas:
        senha = ler_senha("Senha (de 10 a 128 caracteres): ")
        if ler_senha("A mesma senha, de novo: ") != senha:
            print("erro: as senhas não conferem; nada mudou", file=saida)
            return 1
    if abrir_sessao is None:
        try:
            configuracao = ler_configuracao()
        except ConfiguracaoInvalidaError as erro:
            print(f"erro: {erro}", file=saida)
            return 1
        motor = motor_da_configuracao(configuracao)
        try:
            with closing(Session(motor)) as sessao:
                return trabalho(sessao)
        finally:
            motor.dispose()
    return trabalho(abrir_sessao())


def _zerar(sessao: Session, email: str, saida: TextIO) -> int:
    conta = login.conta_por_email(sessao, email)
    if conta is None:
        print("erro: nenhuma conta com este e-mail; nada mudou", file=saida)
        return 1
    login.zerar_duas_etapas(sessao, conta, agora=datetime.now(UTC))
    sessao.commit()
    print(f"verificação em duas etapas zerada: {conta.email}", file=saida)
    return 0


def _criar(
    sessao: Session, senhas: Senhas, nome: str, email: str, senha: str, saida: TextIO
) -> int:
    try:
        conta = cadastro.criar_administrador(sessao, senhas, nome=nome, email=email, senha=senha)
    except DadoInvalidoError as erro:
        sessao.rollback()
        print(f"erro: {erro}; nada mudou", file=saida)
        return 1
    sessao.commit()
    print(f"administração criada: {conta.email}", file=saida)
    return 0


if __name__ == "__main__":
    sys.exit(principal())

"""O comando que cria alguém da administração (SDD 8.2): ``python -m nuvem.administracao``.

``uv run python -m nuvem.administracao --nome "Fulano" --email fulano@exemplo.com`` pede a senha
duas vezes, sem mostrar, e cria a conta no banco de ``PATIO_URL_BANCO``. Serve em qualquer
ambiente: é assim que a administração nasce fora do ambiente local, onde a semente não roda. A
verificação em duas etapas vem no mês 4, com a do gestor.
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence
from contextlib import closing
from typing import TextIO

from sqlalchemy.orm import Session

from nuvem.banco import criar_motor
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
    """Cria a conta; devolve 0 se criou, 1 se não (a mensagem diz por quê, sem a senha).

    Args:
        abrir_sessao: de onde vem a sessão do banco; sem ela, do ``PATIO_URL_BANCO``.
        ler_senha: como a senha é pedida (os testes trocam).
    """
    interpretador = argparse.ArgumentParser(
        prog="python -m nuvem.administracao", description="Cria alguém da administração."
    )
    interpretador.add_argument("--nome", required=True)
    interpretador.add_argument("--email", required=True)
    opcoes = interpretador.parse_args(argumentos)
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
        motor = criar_motor(configuracao.url_banco.get_secret_value())
        try:
            with closing(Session(motor)) as sessao:
                return _criar(sessao, senhas or Senhas(), opcoes.nome, opcoes.email, senha, saida)
        finally:
            motor.dispose()
    return _criar(abrir_sessao(), senhas or Senhas(), opcoes.nome, opcoes.email, senha, saida)


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

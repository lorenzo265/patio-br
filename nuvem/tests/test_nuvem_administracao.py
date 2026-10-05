"""O comando que cria a administração (SDD 8.2): ``python -m nuvem.administracao``."""

import io
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem import administracao
from nuvem.cadastro import login
from nuvem.cadastro.modelos import Administrador
from nuvem.semente import Demonstracao
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao

SENHA = "uma-senha-bem-comprida"


def _respostas(*senhas: str) -> Callable[[str], str]:
    restantes: Iterator[str] = iter(senhas)
    return lambda _pergunta: next(restantes)


def _rodar(
    sessao: Session, senhas: Senhas, argumentos: list[str], *digitadas: str
) -> tuple[int, str]:
    saida = io.StringIO()
    codigo = administracao.principal(
        argumentos,
        abrir_sessao=lambda: sessao,
        senhas=senhas,
        ler_senha=_respostas(*digitadas),
        saida=saida,
    )
    return codigo, saida.getvalue()


def test_cria_a_administracao_que_entra_com_a_senha(sessao: Session, senhas: Senhas) -> None:
    codigo, saida = _rodar(
        sessao, senhas, ["--nome", "Lorenzo", "--email", "Nova@Patio-BR.example"], SENHA, SENHA
    )

    assert codigo == 0
    assert "nova@patio-br.example" in saida
    assert SENHA not in saida
    agora = datetime(2026, 10, 5, tzinfo=UTC)
    codigo_da_sessao = login.entrar(
        sessao, senhas, email="nova@patio-br.example", senha=SENHA, agora=agora
    )
    conta = login.conta_da_sessao(sessao, codigo_da_sessao, agora)
    assert isinstance(conta, Administrador)
    assert conta.nome == "Lorenzo"


def test_confirmacao_diferente_nao_cria_nada(sessao: Session, senhas: Senhas) -> None:
    codigo, saida = _rodar(
        sessao, senhas, ["--nome", "x", "--email", "x@patio-br.example"], SENHA, SENHA + "!"
    )

    assert codigo == 1
    assert "não conferem" in saida
    consulta = select(Administrador).where(Administrador.email == "x@patio-br.example")
    assert sessao.scalar(consulta) is None


def test_email_que_ja_existe_e_recusado(
    sessao: Session, senhas: Senhas, cenario: Demonstracao
) -> None:
    codigo, saida = _rodar(
        sessao, senhas, ["--nome", "x", "--email", cenario.administrador.email], SENHA, SENHA
    )

    assert codigo == 1
    assert "erro" in saida


def test_senha_curta_demais_e_recusada(sessao: Session, senhas: Senhas) -> None:
    codigo, saida = _rodar(
        sessao, senhas, ["--nome", "x", "--email", "y@patio-br.example"], "curta", "curta"
    )

    assert codigo == 1
    assert "curta" not in saida

"""Usuários e administração: senha e PIN só como resumo, regras de tamanho e e-mail único."""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from nuvem.cadastro import servico
from nuvem.erros import DadoInvalidoError
from nuvem.semente import PIN_DA_DEMONSTRACAO, SENHA_DA_DEMONSTRACAO, Demonstracao
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao


def _gravado(sessao: Session, coluna: str, usuario_id: int) -> str:
    return str(
        sessao.execute(
            text(f"select {coluna} from usuario where id = :id"), {"id": usuario_id}
        ).scalar_one()
    )


def test_senha_do_usuario_fica_so_como_resumo(sessao: Session, cenario: Demonstracao) -> None:
    gravada = _gravado(sessao, "senha_resumo", cenario.gestor_a.id)

    assert gravada.startswith("$argon2id$")
    assert SENHA_DA_DEMONSTRACAO not in gravada


def test_pin_do_porteiro_fica_so_como_resumo(sessao: Session, cenario: Demonstracao) -> None:
    gravado = _gravado(sessao, "pin_resumo", cenario.porteiro_a.id)

    assert gravado.startswith("$argon2id$")
    assert PIN_DA_DEMONSTRACAO not in gravado


def test_senha_do_administrador_fica_so_como_resumo(sessao: Session, cenario: Demonstracao) -> None:
    gravada = sessao.execute(
        text("select senha_resumo from administrador where id = :id"),
        {"id": cenario.administrador.id},
    ).scalar_one()

    assert SENHA_DA_DEMONSTRACAO not in gravada


def test_aceita_senha_de_10_caracteres(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    servico.definir_senha(sessao, senhas, cenario.gestor_a, "0123456789")

    assert cenario.gestor_a.senha_resumo is not None
    assert senhas.confere(cenario.gestor_a.senha_resumo, "0123456789")


@pytest.mark.parametrize("senha", ["012345678", "x" * 129], ids=["9 caracteres", "129 caracteres"])
def test_recusa_senha_fora_do_tamanho(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, senha: str
) -> None:
    with pytest.raises(DadoInvalidoError, match="de 10 a 128 caracteres"):
        servico.definir_senha(sessao, senhas, cenario.gestor_a, senha)


@pytest.mark.parametrize(
    "pin",
    ["12345", "1234567", "12345a", "١٢٣٤٥٦"],
    ids=["5 números", "7 números", "com letra", "algarismos arábicos"],
)
def test_pin_tem_exatamente_6_numeros(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, pin: str
) -> None:
    with pytest.raises(DadoInvalidoError, match="6 números"):
        servico.definir_pin(sessao, senhas, cenario.porteiro_a, pin)


def test_so_porteiro_tem_pin(sessao: Session, cenario: Demonstracao, senhas: Senhas) -> None:
    with pytest.raises(DadoInvalidoError, match="porteiro"):
        servico.definir_pin(sessao, senhas, cenario.gestor_a, "135790")


def test_email_da_administracao_nao_vira_usuario_de_cliente(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    # Um e-mail, uma pessoa: o login não pode ficar em dúvida sobre quem está entrando.
    with pytest.raises(DadoInvalidoError, match="e-mail"):
        servico.criar_usuario(
            sessao,
            senhas,
            cenario.empresa_a,
            nome="Repetido",
            email=cenario.administrador.email.upper(),
            papel="gestor",
            sites=[cenario.site_a],
        )


def test_email_de_usuario_de_cliente_nao_vira_administracao(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    with pytest.raises(DadoInvalidoError, match="e-mail"):
        servico.criar_administrador(
            sessao,
            senhas,
            nome="Repetido",
            email=f"  {cenario.gestor_a.email} ",
            senha=SENHA_DA_DEMONSTRACAO,
        )


def test_usuario_pode_ser_criado_sem_senha(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    # Ainda sem senha definida: existe, mas não entra (ver os testes do login).
    usuario = servico.criar_usuario(
        sessao,
        senhas,
        cenario.empresa_a,
        nome="Novo",
        email="novo@empresa-a.example",
        papel="patio",
        sites=[cenario.site_a],
    )

    assert usuario.senha_resumo is None

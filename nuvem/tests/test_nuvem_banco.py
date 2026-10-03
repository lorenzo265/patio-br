"""O banco de teste: migrado do zero no início e limpo a cada teste."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ARQUIVO_ALEMBIC = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.mark.integracao
@pytest.mark.parametrize("vez", [1, 2])
def test_o_que_um_teste_grava_nao_sobra_para_o_proximo(sessao: Session, vez: int) -> None:
    # Se a primeira vez não fosse desfeita, a segunda falharia: a tabela já existiria.
    sessao.execute(text("create table prova_de_isolamento (vez int)"))
    sessao.execute(text("insert into prova_de_isolamento values (:vez)"), {"vez": vez})
    sessao.commit()  # nem o commit do código testado escapa

    assert sessao.execute(text("select count(*) from prova_de_isolamento")).scalar_one() == 1


@pytest.mark.integracao
def test_banco_de_teste_tem_as_migracoes_aplicadas(sessao: Session) -> None:
    versoes = sessao.execute(text("select count(*) from alembic_version")).scalar_one()

    assert versoes == 1


@pytest.mark.integracao
def test_migracoes_cobrem_todos_os_modelos(url_banco_teste: str) -> None:
    # Modelo mudou sem migração nova? O Alembic acha a diferença e o teste falha.
    motor = create_engine(url_banco_teste)
    with motor.connect() as conexao:
        alembic = Config(ARQUIVO_ALEMBIC)
        alembic.attributes["connection"] = conexao
        command.check(alembic)
    motor.dispose()

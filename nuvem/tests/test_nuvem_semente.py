"""Dados de demonstração (`uv run tarefas semente`)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nuvem.cadastro.modelos import Empresa
from nuvem.cifra import Cifra
from nuvem.semente import Demonstracao, semear

pytestmark = pytest.mark.integracao


def test_semente_cria_duas_empresas(sessao: Session, cenario: Demonstracao) -> None:
    assert sessao.scalar(select(func.count()).select_from(Empresa)) == 2


def test_semente_rodada_de_novo_nao_duplica_nada(
    sessao: Session, cenario: Demonstracao, cifra: Cifra
) -> None:
    assert semear(sessao, cifra) is None

"""Dados de demonstração (`uv run tarefas semente`)."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nuvem.cadastro.modelos import Empresa
from nuvem.cifra import Cifra
from nuvem.semente import Demonstracao, principal, semear
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao


def test_semente_cria_duas_empresas(sessao: Session, cenario: Demonstracao) -> None:
    assert sessao.scalar(select(func.count()).select_from(Empresa)) == 2


def test_semente_rodada_de_novo_nao_duplica_nada(
    sessao: Session, cenario: Demonstracao, cifra: Cifra, senhas: Senhas
) -> None:
    assert semear(sessao, cifra, senhas) is None


@pytest.mark.parametrize("ambiente", ["homologacao", "producao"])
def test_semente_so_roda_no_ambiente_local(monkeypatch: pytest.MonkeyPatch, ambiente: str) -> None:
    # Ela cria contas com a senha pública da demonstração, inclusive uma da administração.
    monkeypatch.setenv("PATIO_AMBIENTE", ambiente)
    monkeypatch.setenv("PATIO_URL_BANCO", "postgresql+pg8000://ninguem:x@localhost:1/nenhum")
    monkeypatch.setenv("PATIO_CHAVE_CIFRA", Fernet.generate_key().decode())

    with pytest.raises(SystemExit, match="só no ambiente local"):
        principal()

"""Rotas do cadastro: só com usuário identificado, só dentro da empresa dele, sem senhas."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro.acesso import Acesso, obter_acesso
from nuvem.config import Configuracao
from nuvem.principal import criar_app
from nuvem.semente import SENHA_DAS_CAMERAS, Demonstracao

pytestmark = pytest.mark.integracao

CHAVE_QUALQUER = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="


@pytest.fixture
def app(url_banco_teste: str, sessao: Session) -> FastAPI:
    """A aplicação usando a sessão do teste (transação desfeita no fim)."""
    app = criar_app(
        Configuracao(url_banco=url_banco_teste, chave_cifra=CHAVE_QUALQUER, _env_file=None)
    )

    def sessao_do_teste() -> Iterator[Session]:
        yield sessao

    app.dependency_overrides[obter_sessao] = sessao_do_teste
    return app


def _como(app: FastAPI, acesso: Acesso) -> TestClient:
    app.dependency_overrides[obter_acesso] = lambda: acesso
    return TestClient(app)


def test_sem_usuario_identificado_a_rota_responde_401(app: FastAPI, cenario: Demonstracao) -> None:
    # O login entra na T09; até lá, nenhuma rota do cadastro abre para ninguém.
    resposta = TestClient(app).get(f"/api/cadastro/sites/{cenario.site_a.id}")

    assert resposta.status_code == 401


def test_site_de_outra_empresa_responde_404(
    app: FastAPI, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    resposta = _como(app, acesso_a).get(f"/api/cadastro/sites/{cenario.site_b.id}")

    assert (resposta.status_code, resposta.json()) == (404, {"detail": "não encontrado"})


def test_lista_os_sites_do_usuario(app: FastAPI, cenario: Demonstracao, acesso_a: Acesso) -> None:
    resposta = _como(app, acesso_a).get("/api/cadastro/sites")

    assert [site["id"] for site in resposta.json()] == [cenario.site_a.id]


def test_cameras_saem_sem_a_senha(app: FastAPI, cenario: Demonstracao, acesso_a: Acesso) -> None:
    resposta = _como(app, acesso_a).get(f"/api/cadastro/sites/{cenario.site_a.id}/cameras")

    assert resposta.status_code == 200
    assert "senha" not in resposta.text
    assert SENHA_DAS_CAMERAS not in resposta.text
    assert cenario.camera_a.senha_cifrada not in resposta.text

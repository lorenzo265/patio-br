"""Rotas de leitura dos agendamentos: só dentro da empresa, só nos sites de quem pede."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from nuvem.agendamento import servico
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento
from nuvem.cadastro.acesso import Acesso
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

INICIO = datetime(2026, 11, 5, 11, 0, tzinfo=UTC)


@pytest.fixture
def agendamento_a(sessao: Session, cenario: Demonstracao, acesso_a: Acesso) -> Agendamento:
    """Um agendamento da planilha no site_a."""
    site = servico.site_para_agendar(sessao, acesso_a, cenario.site_a.id)
    dados = DadosDoAgendamento(
        codigo_externo="AG-1",
        janela_inicio=INICIO,
        janela_fim=INICIO + timedelta(hours=2),
        tipo="descarga",
        placa_cavalo="ABC1D23",
        placas_reboques=("DEF4G56",),
        motorista_celular="11987654321",
    )
    return servico.gravar(sessao, site, "planilha", dados, agora=INICIO).agendamento


def _periodo(site_id: int, **mudancas: Any) -> dict[str, Any]:
    return {
        "site_id": site_id,
        "de": INICIO.isoformat(),
        "ate": (INICIO + timedelta(days=1)).isoformat(),
    } | mudancas


def test_sem_login_responde_401(app: FastAPI, agendamento_a: Agendamento) -> None:
    assert TestClient(app).get(f"/api/agendamentos/{agendamento_a.id}").status_code == 401


def test_gestor_le_o_agendamento_do_proprio_site(
    entrar: Entrar, cenario: Demonstracao, agendamento_a: Agendamento
) -> None:
    resposta = entrar(cenario.gestor_a.email).get(f"/api/agendamentos/{agendamento_a.id}")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["id"] == agendamento_a.id
    assert corpo["site_id"] == cenario.site_a.id
    assert (corpo["placa_cavalo"], corpo["placas_reboques"]) == ("ABC1D23", ["DEF4G56"])
    assert corpo["motorista_celular"] == "+5511987654321"
    assert (corpo["origem"], corpo["codigo_externo"], corpo["situacao"]) == (
        "planilha",
        "AG-1",
        "ativo",
    )
    assert datetime.fromisoformat(corpo["janela_inicio"]) == INICIO


def test_porteiro_do_site_tambem_le(
    entrar: Entrar, cenario: Demonstracao, agendamento_a: Agendamento
) -> None:
    resposta = entrar(cenario.porteiro_a.email).get(f"/api/agendamentos/{agendamento_a.id}")

    assert resposta.status_code == 200


def test_agendamento_de_outra_empresa_responde_404(
    entrar: Entrar, cenario: Demonstracao, agendamento_a: Agendamento
) -> None:
    # O teste obrigatório da separação (SDD 5.5), pela rota, com login de verdade.
    gestor_b = entrar(cenario.gestor_b.email)

    resposta = gestor_b.get(f"/api/agendamentos/{agendamento_a.id}")

    assert (resposta.status_code, resposta.json()) == (404, {"detail": "não encontrado"})


def test_agendamento_que_nao_existe_responde_o_mesmo_404(
    entrar: Entrar, cenario: Demonstracao, agendamento_a: Agendamento
) -> None:
    resposta = entrar(cenario.gestor_b.email).get(f"/api/agendamentos/{agendamento_a.id + 1000}")

    assert (resposta.status_code, resposta.json()) == (404, {"detail": "não encontrado"})


def test_administracao_nao_usa_a_rota_do_cliente(
    entrar: Entrar, cenario: Demonstracao, agendamento_a: Agendamento
) -> None:
    resposta = entrar(cenario.administrador.email).get(f"/api/agendamentos/{agendamento_a.id}")

    assert resposta.status_code == 403


def test_lista_os_agendamentos_do_periodo(
    entrar: Entrar, cenario: Demonstracao, agendamento_a: Agendamento
) -> None:
    resposta = entrar(cenario.gestor_a.email).get(
        "/api/agendamentos", params=_periodo(cenario.site_a.id)
    )

    assert resposta.status_code == 200
    assert [a["id"] for a in resposta.json()] == [agendamento_a.id]


def test_lista_de_site_de_outra_empresa_responde_404(
    entrar: Entrar, cenario: Demonstracao, agendamento_a: Agendamento
) -> None:
    resposta = entrar(cenario.gestor_b.email).get(
        "/api/agendamentos", params=_periodo(cenario.site_a.id)
    )

    assert resposta.status_code == 404


@pytest.mark.parametrize(
    "mudanca",
    [
        {"ate": INICIO.isoformat()},  # período vazio
        {"ate": (INICIO + timedelta(days=32)).isoformat()},  # mais de 31 dias
        {"de": "2026-11-05T08:00:00"},  # sem fuso
    ],
)
def test_periodo_fora_da_regra_responde_422(
    entrar: Entrar, cenario: Demonstracao, mudanca: dict[str, Any]
) -> None:
    resposta = entrar(cenario.gestor_a.email).get(
        "/api/agendamentos", params=_periodo(cenario.site_a.id, **mudanca)
    )

    assert resposta.status_code == 422

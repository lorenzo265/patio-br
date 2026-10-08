"""Os alertas nas telas (SDD 6.2 e 8.1, D-68): o sino, a lista e o link do WhatsApp."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from nuvem.alertas import servico as alertas
from nuvem.portaria import visitas
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

AGORA = datetime(2026, 10, 6, 17, 0, tzinfo=UTC)
NUMERO = "5511900000000"


@pytest.fixture
def no_relogio(app: FastAPI) -> FastAPI:
    app.dependency_overrides[agora] = lambda: AGORA
    return app


@pytest.fixture
def com_alerta(sessao: Session, cenario: Demonstracao) -> None:
    visitas.abrir_visita(
        sessao, SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id),
        "check_in", momento=AGORA - timedelta(hours=6), agora=AGORA - timedelta(hours=6),
        composicao=(PlacaNaVisita(placa="ABC1D23", papel="cavalo", como="lida"),),
    )  # fmt: skip
    alertas.conferir(sessao, agora=AGORA)


# --- O sino ---------------------------------------------------------------------------------


@pytest.mark.parametrize("papel", ["gestor_a", "porteiro_a", "patio_a"])
def test_o_sino_aparece_em_todas_as_telas_de_quem_e_do_cliente(
    no_relogio: FastAPI, entrar: Entrar, cenario: Demonstracao, papel: str
) -> None:
    texto = entrar(getattr(cenario, papel).email).get("/").text

    assert 'hx-get="/alertas/sino"' in texto
    assert '<script src="/estatico/htmx-2.0.11.min.js"' in texto


def test_o_sino_conta_os_alertas_abertos_dos_sites(
    no_relogio: FastAPI, entrar: Entrar, cenario: Demonstracao, com_alerta: None
) -> None:
    da_a = entrar(cenario.porteiro_a.email).get("/alertas/sino").text
    da_b = entrar(cenario.gestor_b.email).get("/alertas/sino").text

    assert "1 alerta aberto" in da_a
    assert 'href="/alertas"' in da_a
    assert 'href="/alertas"' in da_b  # o caminho para a tela fica, sem o número
    assert "aberto" not in da_b


def test_a_tela_dos_alertas(
    no_relogio: FastAPI, entrar: Entrar, cenario: Demonstracao, com_alerta: None
) -> None:
    resposta = entrar(cenario.patio_a.email).get("/alertas")

    assert resposta.status_code == 200
    assert "ABC1D23 no site há 6 horas" in resposta.text
    assert "aberto desde 06/10 14:00" in resposta.text


def test_sem_login_o_sino_nao_aparece(app: FastAPI, cenario: Demonstracao) -> None:
    assert 'hx-get="/alertas/sino"' not in TestClient(app).get("/entrar").text


# --- O link do WhatsApp ---------------------------------------------------------------------


def test_o_gestor_pede_o_link_do_whatsapp(
    no_relogio: FastAPI, entrar: Entrar, cenario: Demonstracao
) -> None:
    no_relogio.state.whatsapp_numero = NUMERO
    gestor = entrar(cenario.gestor_a.email)
    assert 'action="/alertas/whatsapp"' in gestor.get("/alertas").text

    resposta = gestor.post("/alertas/whatsapp")

    assert resposta.status_code == 200
    assert f"https://wa.me/{NUMERO}?text={quote('ALERTAS ')}" in resposta.text
    assert "10 minutos" in resposta.text
    assert "no-store" in resposta.headers["cache-control"]


def test_sem_o_whatsapp_ligado_o_link_explica(
    no_relogio: FastAPI, entrar: Entrar, cenario: Demonstracao
) -> None:
    resposta = entrar(cenario.gestor_a.email).post("/alertas/whatsapp")

    assert resposta.status_code == 200
    assert "wa.me" not in resposta.text
    assert "WhatsApp ainda não está ligado" in resposta.text


def test_o_porteiro_nao_pede_o_link(
    no_relogio: FastAPI, entrar: Entrar, cenario: Demonstracao
) -> None:
    porteiro = entrar(cenario.porteiro_a.email)

    assert 'action="/alertas/whatsapp"' not in porteiro.get("/alertas").text
    assert porteiro.post("/alertas/whatsapp").status_code == 403


# --- A administração ------------------------------------------------------------------------


def test_a_administracao_ve_os_alertas_dela(
    no_relogio: FastAPI, entrar: Entrar, cenario: Demonstracao, sessao: Session
) -> None:
    from sqlalchemy import select

    from nuvem import tarefas_de_fundo

    tarefas_de_fundo.enfileirar(
        sessao, "enviar_mensagem", {"mensagem_id": 1}, chave="mensagem:1", agora=AGORA
    )
    tarefa = sessao.scalars(select(tarefas_de_fundo.TarefaDeFundo)).one()
    tarefa.situacao, tarefa.ultimo_erro = "falhou", "RuntimeError: a Meta caiu"
    alertas.conferir(sessao, agora=AGORA)
    administracao = entrar(cenario.administrador.email)

    tela = administracao.get("/administracao/alertas").text
    sino = administracao.get("/administracao/alertas/sino").text
    inicio = administracao.get("/").text

    assert f"A tarefa {tarefa.id} (enviar_mensagem) falhou de vez" in tela
    assert 'action="/administracao/alertas/whatsapp"' in tela
    assert "1 alerta" in sino
    assert 'hx-get="/administracao/alertas/sino"' in inicio


def test_quem_e_do_cliente_nao_ve_os_alertas_da_administracao(
    no_relogio: FastAPI, entrar: Entrar, cenario: Demonstracao
) -> None:
    assert entrar(cenario.gestor_a.email).get("/administracao/alertas").status_code == 403

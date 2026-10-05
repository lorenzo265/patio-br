"""A tela do celular do motorista (T43, SDD 6.2 e D-47): as mensagens que ele receberia."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.modelos import Doca
from nuvem.mensagens import servico as mensagens
from nuvem.patio import servico as patio
from nuvem.portaria import visitas
from nuvem.portaria.modelos import Visita
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]
Agendar = Callable[..., Agendamento]

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
"""14h em São Paulo."""


@pytest.fixture(autouse=True)
def _hora_fixa(app: FastAPI) -> None:
    app.dependency_overrides[agora] = lambda: AGORA


@pytest.fixture
def agendar(sessao: Session, cenario: Demonstracao) -> Agendar:
    """Um agendamento de descarga do site_a, das 13h às 15h de 05/10."""
    destino = SiteDoAgendamento(
        empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id, usuario_id=None
    )

    def _agendar(
        codigo: str = "AG-1", placa: str = "ABC1D23", celular: str | None = "+5511987654321"
    ) -> Agendamento:
        dados = DadosDoAgendamento(
            codigo_externo=codigo,
            janela_inicio=datetime(2026, 10, 5, 16, tzinfo=UTC),
            janela_fim=datetime(2026, 10, 5, 18, tzinfo=UTC),
            tipo="descarga",
            placa_cavalo=placa,
            motorista_celular=celular,
        )
        return agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento

    return _agendar


def _chegar(sessao: Session, agendamento: Agendamento) -> Visita:
    site = SiteDaVisita(empresa_id=agendamento.empresa_id, site_id=agendamento.site_id)
    return visitas.abrir_visita(
        sessao, site, "check_in", momento=AGORA, agora=AGORA, agendamento_id=agendamento.id,
        composicao=(PlacaNaVisita(placa=agendamento.placa_cavalo, papel="cavalo", como="lida"),),
    )  # fmt: skip


def _conversa(cliente: TestClient, agendamento: Agendamento) -> str:
    resposta = cliente.get(f"/mensagens/agendamentos/{agendamento.id}/conversa")
    assert resposta.status_code == 200, resposta.text
    return resposta.text


# --- Quem vê ----------------------------------------------------------------------------------


def test_sem_login_vai_para_a_tela_de_entrar(app: FastAPI) -> None:
    resposta = TestClient(app).get("/mensagens", follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


def test_todos_do_cliente_veem_as_mensagens(entrar: Entrar, cenario: Demonstracao) -> None:
    for pessoa in (cenario.porteiro_a, cenario.patio_a, cenario.gestor_a):
        assert entrar(pessoa.email).get("/mensagens").status_code == 200


def test_o_inicio_leva_as_mensagens(entrar: Entrar, cenario: Demonstracao) -> None:
    assert 'href="/mensagens"' in entrar(cenario.porteiro_a.email).get("/").text


def test_agendamento_de_outra_empresa_responde_404(
    entrar: Entrar, cenario: Demonstracao, agendar: Agendar
) -> None:
    agendamento = agendar()
    gestor_b = entrar(cenario.gestor_b.email)

    for caminho in ("", "/conversa"):
        resposta = gestor_b.get(f"/mensagens/agendamentos/{agendamento.id}{caminho}")
        assert resposta.status_code == 404


def test_site_de_outra_empresa_responde_404(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.gestor_a.email).get(f"/mensagens?site={cenario.site_b.id}")

    assert resposta.status_code == 404


# --- As conversas do site ---------------------------------------------------------------------


def test_a_lista_mostra_as_conversas_pela_ultima_mensagem(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, agendar: Agendar
) -> None:
    primeiro, segundo = agendar("AG-1", "ABC1D23"), agendar("AG-2", "BRA2E19")
    mensagens.preparar(sessao, agora=AGORA - timedelta(minutes=1))
    _chegar(sessao, segundo)
    mensagens.preparar(sessao, agora=AGORA)

    texto = entrar(cenario.gestor_a.email).get("/mensagens").text

    assert texto.index("AG-2") < texto.index("AG-1")
    assert "Você está na fila, posição 1." in texto
    assert f'href="/mensagens/agendamentos/{primeiro.id}"' in texto
    assert f'href="/mensagens/agendamentos/{segundo.id}"' in texto


def test_a_lista_sem_conversas_avisa(entrar: Entrar, cenario: Demonstracao) -> None:
    assert "Nenhuma mensagem ainda" in entrar(cenario.gestor_a.email).get("/mensagens").text


# --- O celular --------------------------------------------------------------------------------


def test_o_celular_se_atualiza_e_esconde_o_numero(
    entrar: Entrar, cenario: Demonstracao, agendar: Agendar
) -> None:
    agendamento = agendar()

    texto = entrar(cenario.gestor_a.email).get(f"/mensagens/agendamentos/{agendamento.id}").text

    assert f'hx-get="/mensagens/agendamentos/{agendamento.id}/conversa"' in texto
    assert "(11) •••••-4321" in texto
    assert "98765" not in texto
    assert "CD Exemplo" in texto and "AG-1" in texto


def test_o_celular_diz_que_nada_e_enviado(
    entrar: Entrar, cenario: Demonstracao, agendar: Agendar
) -> None:
    agendamento = agendar()

    texto = entrar(cenario.gestor_a.email).get(f"/mensagens/agendamentos/{agendamento.id}").text

    assert "nada é enviado" in texto


def test_agendamento_sem_celular_avisa(
    entrar: Entrar, cenario: Demonstracao, agendar: Agendar
) -> None:
    agendamento = agendar(celular=None)

    texto = entrar(cenario.gestor_a.email).get(f"/mensagens/agendamentos/{agendamento.id}").text

    assert "O agendamento não tem celular" in texto


def test_a_conversa_mostra_as_mensagens_em_ordem_com_a_hora(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    acesso_a: Acesso,
    agendar: Agendar,
) -> None:
    agendamento = agendar()
    mensagens.preparar(sessao, agora=AGORA - timedelta(hours=20))  # 18h do dia 4
    visita = _chegar(sessao, agendamento)
    doca = sessao.scalars(select(Doca).where(Doca.site_id == cenario.site_a.id)).first()
    assert doca is not None
    patio.chamar(sessao, acesso_a, visita.id, doca.id, agora=AGORA)
    mensagens.preparar(sessao, agora=AGORA)

    texto = _conversa(entrar(cenario.gestor_a.email), agendamento)

    assert texto.index("Descarga agendada") < texto.index("Você está na fila")
    assert texto.index("Você está na fila") < texto.index("Sua vez!")
    dia_4, dia_5 = texto.index('class="dia"><span>04/10'), texto.index('class="dia"><span>05/10')
    assert dia_4 < texto.index('class="hora">18:00') < dia_5 < texto.index('class="hora">14:00')
    assert texto.count('class="dia"') == 2


def test_a_conversa_vazia_avisa(entrar: Entrar, cenario: Demonstracao, agendar: Agendar) -> None:
    agendamento = agendar()

    assert "Nenhuma mensagem ainda" in _conversa(entrar(cenario.gestor_a.email), agendamento)


# --- Os caminhos até o celular ----------------------------------------------------------------


def test_o_quadro_do_patio_leva_ao_celular(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, agendar: Agendar
) -> None:
    agendamento = agendar()
    _chegar(sessao, agendamento)

    texto = entrar(cenario.patio_a.email).get(f"/patio/quadro?site={cenario.site_a.id}").text

    assert f'href="/mensagens/agendamentos/{agendamento.id}"' in texto


def test_a_tela_de_agendamentos_leva_ao_celular(
    entrar: Entrar, cenario: Demonstracao, agendar: Agendar
) -> None:
    com_celular, sem_celular = agendar("AG-1", "ABC1D23"), agendar("AG-2", "BRA2E19", None)

    texto = entrar(cenario.gestor_a.email).get("/agendamentos?dia=2026-10-05").text

    assert f'href="/mensagens/agendamentos/{com_celular.id}"' in texto
    assert f'href="/mensagens/agendamentos/{sem_celular.id}"' not in texto

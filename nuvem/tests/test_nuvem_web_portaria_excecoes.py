"""Exceções na tela da portaria (T34): o porteiro vê, com a foto e os candidatos; resolver é no
mês 3."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import acesso_do_usuario
from nuvem.erros import NaoEncontradoError
from nuvem.portaria import servico as portaria
from nuvem.portaria.casamento import processar_passagem
from nuvem.semente import Demonstracao
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]
Registrar = Callable[..., Passagem]

AGORA = datetime(2026, 10, 5, 17, 3, tzinfo=UTC)


@pytest.fixture
def agendar(sessao: Session, cenario: Demonstracao) -> Callable[..., Agendamento]:
    """Grava um agendamento do cavalo ABC1D23 no site_a, com a janela que começa em ``inicio``."""

    def _agendar(codigo: str, inicio: datetime) -> Agendamento:
        destino = SiteDoAgendamento(
            empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id, usuario_id=None
        )
        dados = DadosDoAgendamento(
            codigo_externo=codigo,
            janela_inicio=inicio,
            janela_fim=inicio + timedelta(hours=2),
            tipo="descarga",
            placa_cavalo="ABC1D23",
            placas_reboques=("DEF4G56",),
        )
        return agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento

    return _agendar


def _excecoes(cliente: TestClient, cenario: Demonstracao) -> str:
    resposta = cliente.get(f"/portaria/excecoes?site={cenario.site_a.id}")
    assert resposta.status_code == 200, resposta.text
    return resposta.text


def test_a_tela_da_portaria_busca_as_excecoes_a_cada_2_segundos(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    tela = entrar(cenario.porteiro_a.email).get("/portaria").text

    assert f'hx-get="/portaria/excecoes?site={cenario.site_a.id}"' in tela


def test_excecao_com_dois_candidatos_aparece_com_a_foto_e_os_pontos(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    registrar_passagem: Registrar,
) -> None:
    # Às 14h02 (São Paulo): na janela do CEDO (13h) e na tolerância do TARDE (15h30).
    agendar("CEDO", datetime(2026, 10, 5, 16, tzinfo=UTC))
    agendar("TARDE", datetime(2026, 10, 5, 18, 30, tzinfo=UTC))
    passagem = registrar_passagem()
    processar_passagem(sessao, passagem.id, agora=AGORA)

    texto = _excecoes(entrar(cenario.porteiro_a.email), cenario)

    assert "mais de um agendamento possível" in texto
    assert "14:02:11" in texto
    assert "ABC1D23" in texto
    assert f'src="/portaria/fotos/{passagem.id}/0"' in texto
    assert texto.index("CEDO") < texto.index("TARDE")  # do maior para o menor
    assert "80 pontos" in texto and "70 pontos" in texto
    assert "13:00 às 15:00" in texto  # a janela do candidato, no fuso do site
    assert "DEF4G56" in texto  # as placas esperadas do candidato


def test_excecao_sem_candidato(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    processar_passagem(sessao, registrar_passagem().id, agora=AGORA)

    texto = _excecoes(entrar(cenario.porteiro_a.email), cenario)

    assert "sem agendamento com estas placas" in texto
    assert "Nenhum candidato" in texto


def test_excecao_sem_placa(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    processar_passagem(sessao, registrar_passagem(placas=[], fotos=[]).id, agora=AGORA)

    assert "nenhuma placa lida" in _excecoes(entrar(cenario.porteiro_a.email), cenario)


def test_sem_excecao_aberta_a_lista_avisa(entrar: Entrar, cenario: Demonstracao) -> None:
    assert "Nenhuma exceção aberta" in _excecoes(entrar(cenario.porteiro_a.email), cenario)


def test_check_in_nao_aparece_como_excecao(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    registrar_passagem: Registrar,
) -> None:
    agendar("UNICO", datetime(2026, 10, 5, 16, tzinfo=UTC))
    processar_passagem(sessao, registrar_passagem().id, agora=AGORA)

    assert "Nenhuma exceção aberta" in _excecoes(entrar(cenario.porteiro_a.email), cenario)


def test_quem_nao_e_da_portaria_nao_ve(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.patio_a.email).get(f"/portaria/excecoes?site={cenario.site_a.id}")

    assert resposta.status_code == 403


def test_site_de_outra_empresa_responde_404(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    processar_passagem(sessao, registrar_passagem().id, agora=AGORA)

    resposta = entrar(cenario.porteiro_b.email).get(f"/portaria/excecoes?site={cenario.site_a.id}")

    assert resposta.status_code == 404


def test_obter_passagem_so_do_site_de_quem_pede(
    sessao: Session, senhas: Senhas, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    # Alguém da empresa A que só vê o site_a2 não lê a passagem do site_a.
    usuario = cadastro.criar_usuario(
        sessao, senhas, cenario.empresa_a, nome="Só do A2", email="a2@empresa-a.example",
        papel="porteiro", sites=[cenario.site_a2],
    )  # fmt: skip
    passagem = registrar_passagem()

    with pytest.raises(NaoEncontradoError):
        portaria.obter_passagem(sessao, acesso_do_usuario(sessao, usuario.id), passagem.id)
    assert (
        portaria.obter_passagem(
            sessao, acesso_do_usuario(sessao, cenario.porteiro_a.id), passagem.id
        ).id
        == passagem.id
    )

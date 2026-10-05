"""O resultado do casamento na lista de passagens da portaria (T35, SDD 6.2)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem import tarefas_de_fundo as fila
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.cadastro import servico as cadastro
from nuvem.semente import Demonstracao
from nuvem.tarefas_de_fundo import TarefaDeFundo

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]
Registrar = Callable[..., Passagem]

AGORA = datetime(2026, 10, 5, 17, 3, tzinfo=UTC)
DEPOIS_DA_SAIDA = AGORA + timedelta(hours=1, minutes=1)
"""A passagem de saída (uma hora depois) já terminou e chegou à nuvem."""


@pytest.fixture
def agendado(sessao: Session, cenario: Demonstracao) -> None:
    """O agendamento AG-1 do cavalo ABC1D23, das 13h às 15h em São Paulo."""
    destino = SiteDoAgendamento(
        empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id, usuario_id=None
    )
    dados = DadosDoAgendamento(
        codigo_externo="AG-1",
        janela_inicio=datetime(2026, 10, 5, 16, tzinfo=UTC),
        janela_fim=datetime(2026, 10, 5, 18, tzinfo=UTC),
        tipo="descarga",
        placa_cavalo="ABC1D23",
    )
    agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA)


@pytest.fixture
def saida(
    sessao: Session, cenario: Demonstracao, registrar_passagem: Registrar
) -> Callable[..., Passagem]:
    """Registra uma passagem pela faixa de saída do site_a."""
    estrutura = cadastro.estrutura_do_site(
        sessao, empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id
    )
    faixa = next(f for f in estrutura.values() if f.sentido == "saida")
    camera = str(min(faixa.cameras))

    def _sair(placa: str) -> Passagem:
        lida = {"placa": placa, "papel": "desconhecido", "confianca": 0.9, "camera_id": camera,
                "quadros": 4}  # fmt: skip
        return registrar_passagem(
            faixa_id=str(faixa.id), sentido="saida", inicio=AGORA + timedelta(hours=1),
            placas=[lida], fotos=[],
        )  # fmt: skip

    return _sair


def _linha(cliente: TestClient, cenario: Demonstracao, passagem: Passagem) -> str:
    texto = cliente.get(f"/portaria/passagens?site={cenario.site_a.id}").text
    inicio = texto.index(f'id="passagem-{passagem.id}"')
    return texto[inicio : texto.index("</tr>", inicio)]


def test_entrada_que_casou_mostra_o_check_in_com_o_codigo(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    agendado: None,
    registrar_passagem: Registrar,
) -> None:
    passagem = registrar_passagem()
    fila.executar_pendentes(sessao, agora=AGORA)

    assert "check-in AG-1" in _linha(entrar(cenario.porteiro_a.email), cenario, passagem)


def test_entrada_que_nao_casou_mostra_excecao(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    fila.executar_pendentes(sessao, agora=AGORA)

    assert "exceção" in _linha(entrar(cenario.porteiro_a.email), cenario, passagem)


def test_entrada_ainda_na_fila_mostra_que_aguarda(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    linha = _linha(entrar(cenario.porteiro_a.email), cenario, passagem)

    assert "aguardando o casamento" in linha


def test_saida_fecha_e_a_entrada_mostra_que_saiu(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    agendado: None,
    registrar_passagem: Registrar,
    saida: Callable[..., Passagem],
) -> None:
    entrada = registrar_passagem()
    fila.executar_pendentes(sessao, agora=AGORA)
    de_saida = saida("ABC1D23")
    fila.executar_pendentes(sessao, agora=DEPOIS_DA_SAIDA)
    porteiro = entrar(cenario.porteiro_a.email)

    assert "check-in AG-1 · saiu" in _linha(porteiro, cenario, entrada)
    assert "saída" in _linha(porteiro, cenario, de_saida)


def test_saida_sem_visita_aberta(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, saida: Callable[..., Passagem]
) -> None:
    de_saida = saida("XYZ9K87")
    fila.executar_pendentes(sessao, agora=DEPOIS_DA_SAIDA)

    linha = _linha(entrar(cenario.porteiro_a.email), cenario, de_saida)

    assert "saída sem visita aberta" in linha


def test_casamento_que_falhou_avisa(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    tarefa = sessao.scalars(select(TarefaDeFundo)).one()
    tarefa.situacao, tarefa.terminada_em = "falhou", AGORA
    sessao.flush()

    linha = _linha(entrar(cenario.porteiro_a.email), cenario, passagem)

    assert "o casamento falhou" in linha

"""Pátio e docas (T42, SDD 2.2 e 5.2): a fila, a chamada para a doca, o início e o fim."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.banco import SQLSTATE_CHECK, SQLSTATE_UNICIDADE, sqlstate
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, acesso_do_usuario
from nuvem.cadastro.modelos import Doca
from nuvem.erros import NaoEncontradoError
from nuvem.patio import servico as patio
from nuvem.patio.servico import DocaOcupadaError
from nuvem.portaria import visitas
from nuvem.portaria.casamento import processar_passagem
from nuvem.portaria.modelos import Evento, Visita
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita, TransicaoInvalidaError
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Registrar = Callable[..., Passagem]
Chegar = Callable[..., Visita]

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
"""14h em São Paulo."""


@pytest.fixture
def lider(sessao: Session, cenario: Demonstracao) -> Acesso:
    """O líder de pátio do site_a."""
    return acesso_do_usuario(sessao, cenario.patio_a.id)


@pytest.fixture
def docas(sessao: Session, cenario: Demonstracao) -> list[Doca]:
    """As docas do site_a ("Doca 1" e "Doca 2")."""
    return list(
        sessao.scalars(select(Doca).where(Doca.site_id == cenario.site_a.id).order_by(Doca.nome))
    )


@pytest.fixture
def chegar(sessao: Session, cenario: Demonstracao) -> Chegar:
    """Abre uma visita na fila do site_a: o caminhão chegou ``ha`` tempo atrás."""
    site = SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id)
    destino = SiteDoAgendamento(
        empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id, usuario_id=None
    )

    def _chegar(placa: str, ha: timedelta, codigo: str | None = None) -> Visita:
        agendamento_id = None
        if codigo is not None:
            dados = DadosDoAgendamento(
                codigo_externo=codigo, janela_inicio=AGORA - ha,
                janela_fim=AGORA - ha + timedelta(hours=2), tipo="descarga", placa_cavalo=placa,
            )  # fmt: skip
            agendamento_id = agendamentos.gravar(
                sessao, destino, "planilha", dados, agora=AGORA
            ).agendamento.id
        return visitas.abrir_visita(
            sessao, site, "check_in", momento=AGORA - ha, agora=AGORA - ha,
            agendamento_id=agendamento_id,
            composicao=(PlacaNaVisita(placa=placa, papel="cavalo", como="lida"),),
        )  # fmt: skip

    return _chegar


def _eventos(sessao: Session, visita: Visita) -> list[Evento]:
    return list(
        sessao.scalars(select(Evento).where(Evento.visita_id == visita.id).order_by(Evento.id))
    )


# --- O quadro do pátio ------------------------------------------------------------------------


def test_fila_pela_ordem_de_chegada_com_o_tempo_e_o_alerta_perto_das_5_horas(
    sessao: Session, lider: Acesso, cenario: Demonstracao, chegar: Chegar
) -> None:
    chegar("BRA2E19", timedelta(hours=1))
    chegar("ABC1D23", timedelta(hours=4, minutes=10), codigo="AG-1")

    quadro = patio.quadro(sessao, lider, cenario.site_a.id, agora=AGORA)

    assert [(c.placas, c.tempo, c.alerta) for c in quadro.fila] == [
        (("ABC1D23",), timedelta(hours=4, minutes=10), True),
        (("BRA2E19",), timedelta(hours=1), False),
    ]
    assert (quadro.fila[0].agendamento, quadro.fila[0].tipo) == ("AG-1", "descarga")
    assert (quadro.fila[1].agendamento, quadro.fila[1].tipo) == (None, None)


def test_quadro_mostra_as_docas_livres_e_ocupadas(
    sessao: Session, lider: Acesso, cenario: Demonstracao, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(minutes=30))
    patio.chamar(sessao, lider, visita.id, docas[0].id, agora=AGORA)

    quadro = patio.quadro(sessao, lider, cenario.site_a.id, agora=AGORA)

    assert quadro.fila == []
    assert [(d.nome, d.caminhao.placas if d.caminhao else None) for d in quadro.docas] == [
        ("Doca 1", ("ABC1D23",)), ("Doca 2", None),
    ]  # fmt: skip
    assert [d.nome for d in patio.docas_livres(sessao, lider, cenario.site_a.id)] == ["Doca 2"]


def test_quadro_de_site_que_nao_ve(
    sessao: Session, acesso_b: Acesso, cenario: Demonstracao
) -> None:
    with pytest.raises(NaoEncontradoError):
        patio.quadro(sessao, acesso_b, cenario.site_a.id, agora=AGORA)


# --- Chamar, começar e terminar ---------------------------------------------------------------


def test_chamar_leva_a_visita_para_a_doca(
    sessao: Session, lider: Acesso, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(minutes=30))

    patio.chamar(sessao, lider, visita.id, docas[0].id, agora=AGORA)

    assert (visita.estado, visita.doca_id, visita.chamada_em) == ("CHAMADA", docas[0].id, AGORA)
    ultimo = _eventos(sessao, visita)[-1]
    assert (ultimo.tipo, ultimo.usuario_id, ultimo.dados) == (
        "chamada", lider.usuario_id, {"doca_id": docas[0].id, "doca": "Doca 1"},
    )  # fmt: skip


def test_doca_ocupada_nao_recebe_outro_caminhao(
    sessao: Session, lider: Acesso, chegar: Chegar, docas: list[Doca]
) -> None:
    primeira, segunda = chegar("ABC1D23", timedelta(hours=1)), chegar("BRA2E19", timedelta(0))
    patio.chamar(sessao, lider, primeira.id, docas[0].id, agora=AGORA)

    with pytest.raises(DocaOcupadaError):
        patio.chamar(sessao, lider, segunda.id, docas[0].id, agora=AGORA)

    assert segunda.estado == "NA_FILA"


def test_doca_de_outra_empresa_nao_e_encontrada(
    sessao: Session, lider: Acesso, cenario: Demonstracao, chegar: Chegar
) -> None:
    visita = chegar("ABC1D23", timedelta(0))
    de_fora = cadastro.criar_doca(sessao, cenario.site_b, nome="Doca da B")

    with pytest.raises(NaoEncontradoError):
        patio.chamar(sessao, lider, visita.id, de_fora.id, agora=AGORA)


def test_visita_de_outra_empresa_nao_e_encontrada(
    sessao: Session, acesso_b: Acesso, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(0))

    with pytest.raises(NaoEncontradoError):
        patio.chamar(sessao, acesso_b, visita.id, docas[0].id, agora=AGORA)


def test_so_chama_quem_esta_na_fila(
    sessao: Session, lider: Acesso, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(0))
    patio.chamar(sessao, lider, visita.id, docas[0].id, agora=AGORA)

    with pytest.raises(TransicaoInvalidaError):
        patio.chamar(sessao, lider, visita.id, docas[1].id, agora=AGORA)


def test_chamar_de_novo_para_a_mesma_doca_e_fora_de_ordem(
    sessao: Session, lider: Acesso, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(0))
    patio.chamar(sessao, lider, visita.id, docas[0].id, agora=AGORA)

    with pytest.raises(TransicaoInvalidaError):
        patio.chamar(sessao, lider, visita.id, docas[0].id, agora=AGORA)


def test_comecar_e_terminar_liberam_a_doca(
    sessao: Session, lider: Acesso, cenario: Demonstracao, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(hours=1))
    patio.chamar(sessao, lider, visita.id, docas[0].id, agora=AGORA)

    patio.iniciar(sessao, lider, visita.id, agora=AGORA + timedelta(minutes=5))
    assert (visita.estado, visita.na_doca_em) == ("NA_DOCA", AGORA + timedelta(minutes=5))
    patio.finalizar(sessao, lider, visita.id, agora=AGORA + timedelta(hours=1))

    assert (visita.estado, visita.liberada_em) == ("LIBERADA", AGORA + timedelta(hours=1))
    assert [e.tipo for e in _eventos(sessao, visita)] == [
        "check_in", "chamada", "inicio_na_doca", "fim_na_doca",
    ]  # fmt: skip
    quadro = patio.quadro(sessao, lider, cenario.site_a.id, agora=AGORA + timedelta(hours=1))
    assert all(d.caminhao is None for d in quadro.docas)
    assert [c.placas for c in quadro.liberados] == [("ABC1D23",)]


def test_terminar_sem_comecar_e_recusado(
    sessao: Session, lider: Acesso, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(0))
    patio.chamar(sessao, lider, visita.id, docas[0].id, agora=AGORA)

    with pytest.raises(TransicaoInvalidaError):
        patio.finalizar(sessao, lider, visita.id, agora=AGORA)


def test_cancelar_a_chamada_volta_para_a_fila_e_libera_a_doca(
    sessao: Session, lider: Acesso, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(0))
    patio.chamar(sessao, lider, visita.id, docas[0].id, agora=AGORA)

    patio.cancelar_chamada(sessao, lider, visita.id, agora=AGORA)

    assert (visita.estado, visita.doca_id, visita.chamada_em) == ("NA_FILA", None, None)
    assert _eventos(sessao, visita)[-1].tipo == "chamada_cancelada"
    outra = chegar("BRA2E19", timedelta(0))
    patio.chamar(sessao, lider, outra.id, docas[0].id, agora=AGORA)  # a doca está livre


# --- A saída ----------------------------------------------------------------------------------


@pytest.fixture
def sair(
    sessao: Session, cenario: Demonstracao, registrar_passagem: Registrar
) -> Callable[[str], str]:
    """Passa um caminhão pela saída do site_a e devolve o que o casamento fez."""
    estrutura = cadastro.estrutura_do_site(
        sessao, empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id
    )
    faixa = next(f for f in estrutura.values() if f.sentido == "saida")
    camera = str(min(faixa.cameras))

    def _sair(placa: str) -> str:
        lida = {"placa": placa, "papel": "desconhecido", "confianca": 0.9, "camera_id": camera,
                "quadros": 4}  # fmt: skip
        passagem = registrar_passagem(
            faixa_id=str(faixa.id), sentido="saida", inicio=AGORA + timedelta(hours=2),
            placas=[lida], fotos=[],
        )  # fmt: skip
        return processar_passagem(sessao, passagem.id, agora=AGORA).resultado

    return _sair


def test_saida_de_quem_foi_liberado_e_a_saida_normal(
    sessao: Session,
    lider: Acesso,
    chegar: Chegar,
    docas: list[Doca],
    sair: Callable[[str], str],
) -> None:
    visita = chegar("ABC1D23", timedelta(hours=1))
    patio.chamar(sessao, lider, visita.id, docas[0].id, agora=AGORA)
    patio.iniciar(sessao, lider, visita.id, agora=AGORA)
    patio.finalizar(sessao, lider, visita.id, agora=AGORA)

    assert sair("ABC1D23") == "saida"

    assert visita.estado == "SAIU"
    assert _eventos(sessao, visita)[-1].tipo == "saiu"


def test_saida_de_quem_ainda_estava_na_doca_tambem_fecha(
    sessao: Session,
    lider: Acesso,
    chegar: Chegar,
    docas: list[Doca],
    sair: Callable[[str], str],
) -> None:
    visita = chegar("ABC1D23", timedelta(hours=1))
    patio.chamar(sessao, lider, visita.id, docas[0].id, agora=AGORA)
    patio.iniciar(sessao, lider, visita.id, agora=AGORA)

    assert sair("ABC1D23") == "saida"

    assert (visita.estado, _eventos(sessao, visita)[-1].tipo) == ("SAIU", "saiu")


def test_saida_de_quem_foi_chamado_e_nao_atendido(
    sessao: Session,
    lider: Acesso,
    chegar: Chegar,
    docas: list[Doca],
    sair: Callable[[str], str],
) -> None:
    visita = chegar("ABC1D23", timedelta(hours=1))
    patio.chamar(sessao, lider, visita.id, docas[0].id, agora=AGORA)

    sair("ABC1D23")

    assert (visita.estado, _eventos(sessao, visita)[-1].tipo) == ("SAIU", "saiu_sem_atendimento")


# --- O banco também confere -------------------------------------------------------------------


def test_banco_recusa_duas_visitas_na_mesma_doca(
    sessao: Session, chegar: Chegar, docas: list[Doca]
) -> None:
    primeira, segunda = chegar("ABC1D23", timedelta(0)), chegar("BRA2E19", timedelta(0))

    with pytest.raises(DBAPIError) as erro:
        sessao.execute(
            update(Visita)
            .where(Visita.id.in_([primeira.id, segunda.id]))
            .values(estado="CHAMADA", doca_id=docas[0].id, chamada_em=AGORA)
        )

    assert sqlstate(erro.value) == SQLSTATE_UNICIDADE


def test_banco_recusa_chamada_sem_doca(sessao: Session, chegar: Chegar) -> None:
    visita = chegar("ABC1D23", timedelta(0))

    with pytest.raises(DBAPIError) as erro:
        sessao.execute(update(Visita).where(Visita.id == visita.id).values(estado="CHAMADA"))

    assert sqlstate(erro.value) == SQLSTATE_CHECK

"""O casamento no banco (SDD 5.3): a passagem que chega vira check-in ou exceção; a saída fecha."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso
from nuvem.erros import NaoEncontradoError
from nuvem.portaria import visitas
from nuvem.portaria.casamento import Processada, processar_passagem
from nuvem.portaria.modelos import Evento, Excecao, Visita
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Registrar = Callable[..., Passagem]

CHEGADA = datetime(2026, 10, 5, 17, 2, 11, tzinfo=UTC)
"""A hora da passagem das fixtures (14h02 em São Paulo)."""
AGORA = CHEGADA + timedelta(seconds=5)


def _agendar(
    sessao: Session,
    empresa_id: int,
    site_id: int,
    codigo: str,
    *,
    cavalo: str = "ABC1D23",
    reboques: tuple[str, ...] = ("DEF4G56",),
    inicio: datetime = datetime(2026, 10, 5, 16, tzinfo=UTC),
) -> Agendamento:
    destino = SiteDoAgendamento(empresa_id=empresa_id, site_id=site_id, usuario_id=None)
    dados = DadosDoAgendamento(
        codigo_externo=codigo,
        janela_inicio=inicio,
        janela_fim=inicio + timedelta(hours=2),
        tipo="descarga",
        placa_cavalo=cavalo,
        placas_reboques=reboques,
    )
    return agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento


@pytest.fixture
def agendar(sessao: Session, cenario: Demonstracao) -> Callable[..., Agendamento]:
    """Grava um agendamento no site_a (das 13h às 15h em São Paulo, por padrão)."""

    def _no_site_a(codigo: str = "AG-1", **mais: Any) -> Agendamento:
        return _agendar(sessao, cenario.empresa_a.id, cenario.site_a.id, codigo, **mais)

    return _no_site_a


@pytest.fixture
def saida(
    sessao: Session, cenario: Demonstracao, registrar_passagem: Registrar
) -> Callable[..., Passagem]:
    """Registra uma passagem na faixa de saída do site_a (só câmera traseira)."""
    estrutura = cadastro.estrutura_do_site(
        sessao, empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id
    )
    faixa = next(f for f in estrutura.values() if f.sentido == "saida")
    camera = str(min(faixa.cameras))

    def _sair(*placas: str, inicio: datetime = CHEGADA + timedelta(hours=2)) -> Passagem:
        return registrar_passagem(
            faixa_id=str(faixa.id),
            sentido="saida",
            inicio=inicio,
            placas=[
                {
                    "placa": p,
                    "papel": "desconhecido",
                    "confianca": 0.9,
                    "camera_id": camera,
                    "quadros": 4,
                }
                for p in placas
            ],
            fotos=[],
        )

    return _sair


def _processar(sessao: Session, passagem: Passagem) -> Processada:
    return processar_passagem(sessao, passagem.id, agora=AGORA)


def _placas(cenario: Demonstracao, *placas: tuple[str, str]) -> list[dict[str, Any]]:
    camera = str(cenario.camera_a.id)
    return [
        {"placa": placa, "papel": papel, "confianca": 0.95, "camera_id": camera, "quadros": 5}
        for placa, papel in placas
    ]


# --- Entrada ----------------------------------------------------------------------------------


def test_chegada_que_casa_faz_o_check_in(
    sessao: Session, agendar: Callable[..., Agendamento], registrar_passagem: Registrar
) -> None:
    agendamento = agendar()
    passagem = registrar_passagem()  # só o cavalo ABC1D23, às 14h02 (janela das 13h às 15h)

    processada = _processar(sessao, passagem)

    assert processada.resultado == "check_in"
    visita = sessao.get_one(Visita, processada.visita_id)
    assert (visita.estado, visita.agendamento_id, visita.chegou_em) == (
        "NA_FILA",
        agendamento.id,
        passagem.inicio,
    )
    assert visita.composicao == [
        {"placa": "ABC1D23", "papel": "cavalo", "como": "lida"},
        {"placa": "DEF4G56", "papel": "reboque", "como": "inferida"},
    ]
    evento = sessao.scalars(select(Evento).where(Evento.visita_id == visita.id)).one()
    assert (evento.tipo, evento.dados) == ("check_in", {"pontos": 80, "segundo": None})


def test_chegada_sem_agendamento_vira_excecao(
    sessao: Session, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    processada = _processar(sessao, passagem)

    assert processada.resultado == "excecao"
    excecao = sessao.scalars(select(Excecao).where(Excecao.visita_id == processada.visita_id)).one()
    assert (excecao.motivo, excecao.candidatos, excecao.passagem_id) == (
        "sem_candidato",
        [],
        passagem.id,
    )
    visita = sessao.get_one(Visita, processada.visita_id)
    assert visita.composicao == [{"placa": "ABC1D23", "papel": "cavalo", "como": "lida"}]


def test_dois_agendamentos_da_mesma_placa_viram_excecao_com_os_dois(
    sessao: Session, agendar: Callable[..., Agendamento], registrar_passagem: Registrar
) -> None:
    # Um às 13h, outro às 15h (São Paulo): a chegada às 14h02 fica na janela de um e na
    # tolerância do outro (80 contra 70).
    cedo = agendar("CEDO")
    tarde = agendar("TARDE", inicio=datetime(2026, 10, 5, 18, 30, tzinfo=UTC))

    processada = _processar(sessao, registrar_passagem())

    excecao = sessao.scalars(select(Excecao).where(Excecao.visita_id == processada.visita_id)).one()
    assert excecao.motivo == "candidatos_proximos"
    assert excecao.candidatos == [
        {"agendamento_id": cedo.id, "pontos": 80},
        {"agendamento_id": tarde.id, "pontos": 70},
    ]


def test_reboque_lido_ajuda_a_casar(
    sessao: Session,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    registrar_passagem: Registrar,
) -> None:
    # Cavalo com troca fácil (40) + reboque (20) + janela (20) = 80.
    agendamento = agendar(cavalo="ABC1823")
    passagem = registrar_passagem(
        placas=_placas(cenario, ("ABC1B23", "cavalo"), ("DEF4G56", "reboque"))
    )

    processada = _processar(sessao, passagem)

    assert processada.resultado == "check_in"
    visita = sessao.get_one(Visita, processada.visita_id)
    assert visita.agendamento_id == agendamento.id
    assert visita.composicao == [
        {"placa": "ABC1823", "papel": "cavalo", "como": "lida"},
        {"placa": "DEF4G56", "papel": "reboque", "como": "lida"},
    ]


def test_placa_antiga_na_agenda_casa_com_a_mercosul_lida(
    sessao: Session,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    registrar_passagem: Registrar,
) -> None:
    agendar(cavalo="ABC1334", reboques=())  # a Mercosul dela é ABC1D34

    passagem = registrar_passagem(placas=_placas(cenario, ("ABC1D34", "cavalo")))

    processada = _processar(sessao, passagem)

    assert processada.resultado == "check_in"


def test_passagem_sem_placa_vira_excecao_sem_placa(
    sessao: Session, agendar: Callable[..., Agendamento], registrar_passagem: Registrar
) -> None:
    agendar()

    processada = _processar(sessao, registrar_passagem(placas=[], fotos=[]))

    excecao = sessao.scalars(select(Excecao).where(Excecao.visita_id == processada.visita_id)).one()
    assert excecao.motivo == "sem_placa"


# --- Quem é candidato -------------------------------------------------------------------------


def test_agendamento_cancelado_nao_e_candidato(
    sessao: Session,
    agendar: Callable[..., Agendamento],
    registrar_passagem: Registrar,
    acesso_a: Acesso,
) -> None:
    agendamento = agendar()
    agendamentos.cancelar(sessao, acesso_a, agendamento.id, agora=AGORA)

    assert _processar(sessao, registrar_passagem()).resultado == "excecao"


def test_agendamento_que_ja_tem_visita_nao_e_candidato(
    sessao: Session, agendar: Callable[..., Agendamento], registrar_passagem: Registrar
) -> None:
    agendar()
    _processar(sessao, registrar_passagem())

    # O mesmo cavalo de novo, meia hora depois: o agendamento já foi usado.
    de_novo = registrar_passagem(inicio=CHEGADA + timedelta(minutes=30))

    assert _processar(sessao, de_novo).resultado == "excecao"


def test_agendamento_de_outra_empresa_ou_de_outro_site_nao_e_candidato(
    sessao: Session, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    _agendar(sessao, cenario.empresa_b.id, cenario.site_b.id, "DA-B")
    _agendar(sessao, cenario.empresa_a.id, cenario.site_a2.id, "DO-A2")

    processada = _processar(sessao, registrar_passagem())

    assert processada.resultado == "excecao"
    excecao = sessao.scalars(select(Excecao).where(Excecao.visita_id == processada.visita_id)).one()
    assert excecao.candidatos == []


def test_chegada_fora_da_tolerancia_nao_casa(
    sessao: Session, agendar: Callable[..., Agendamento], registrar_passagem: Registrar
) -> None:
    agendar(inicio=CHEGADA + timedelta(hours=4, minutes=1))

    assert _processar(sessao, registrar_passagem()).resultado == "excecao"


# --- A mesma passagem de novo -----------------------------------------------------------------


def test_processar_a_mesma_entrada_de_novo_nao_cria_outra_visita(
    sessao: Session, agendar: Callable[..., Agendamento], registrar_passagem: Registrar
) -> None:
    agendar()
    passagem = registrar_passagem()
    primeira = _processar(sessao, passagem)

    segunda = _processar(sessao, passagem)

    assert segunda == Processada("repetida", primeira.visita_id)
    assert sessao.scalar(select(func.count()).select_from(Visita)) == 1


def test_passagem_que_nao_existe(sessao: Session, cenario: Demonstracao) -> None:
    with pytest.raises(NaoEncontradoError):
        processar_passagem(sessao, uuid4(), agora=AGORA)


# --- Saída (D-37) -----------------------------------------------------------------------------


def test_saida_pela_placa_do_reboque_fecha_a_visita(
    sessao: Session,
    agendar: Callable[..., Agendamento],
    registrar_passagem: Registrar,
    saida: Callable[..., Passagem],
) -> None:
    agendar()
    visita_id = _processar(sessao, registrar_passagem()).visita_id
    # A câmera da saída é traseira: vê o reboque (que na entrada foi inferido).
    passagem_de_saida = saida("DEF4G56")

    processada = _processar(sessao, passagem_de_saida)

    assert processada == Processada("saida", visita_id)
    visita = sessao.get_one(Visita, visita_id)
    assert (visita.estado, visita.saiu_em, visita.passagem_saida_id) == (
        "SAIU",
        passagem_de_saida.inicio,
        passagem_de_saida.id,
    )


def test_saida_de_quem_estava_em_excecao_resolve_a_excecao(
    sessao: Session, registrar_passagem: Registrar, saida: Callable[..., Passagem]
) -> None:
    visita_id = _processar(sessao, registrar_passagem()).visita_id

    _processar(sessao, saida("ABC1D23"))

    excecao = sessao.scalars(select(Excecao).where(Excecao.visita_id == visita_id)).one()
    assert (excecao.situacao, excecao.resolucao) == ("resolvida", "saiu")


def test_saida_sem_visita_aberta_fica_so_como_passagem(
    sessao: Session, saida: Callable[..., Passagem]
) -> None:
    assert _processar(sessao, saida("XYZ9K87")) == Processada("saida_sem_visita", None)


def test_processar_a_mesma_saida_de_novo_nao_muda_nada(
    sessao: Session,
    agendar: Callable[..., Agendamento],
    registrar_passagem: Registrar,
    saida: Callable[..., Passagem],
) -> None:
    agendar()
    visita_id = _processar(sessao, registrar_passagem()).visita_id
    passagem_de_saida = saida("ABC1D23")
    _processar(sessao, passagem_de_saida)

    assert _processar(sessao, passagem_de_saida) == Processada("repetida", visita_id)


def test_saida_nao_fecha_visita_de_outro_site(
    sessao: Session,
    cenario: Demonstracao,
    registrar_passagem: Registrar,
    saida: Callable[..., Passagem],
) -> None:
    # Uma visita aberta no site_a2 com a mesma placa não é desta portaria.
    outra = visitas.abrir_visita(
        sessao, SiteDaVisita(cenario.empresa_a.id, cenario.site_a2.id), "check_in",
        momento=CHEGADA, agora=AGORA,
        composicao=(PlacaNaVisita(placa="ABC1D23", papel="cavalo", como="lida"),),
    )  # fmt: skip

    assert _processar(sessao, saida("ABC1D23")).resultado == "saida_sem_visita"
    assert outra.estado == "NA_FILA"

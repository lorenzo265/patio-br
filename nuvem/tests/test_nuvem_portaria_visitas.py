"""Visita, eventos e exceções (SDD 5.1, 5.2, 5.5 e D-35): a chegada vira visita, com prova."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento, MudancaAgendamento
from nuvem.banco import (
    SQLSTATE_CHAVE_ESTRANGEIRA,
    SQLSTATE_CHECK,
    SQLSTATE_SO_ACRESCENTA,
    SQLSTATE_UNICIDADE,
    sqlstate,
)
from nuvem.cadastro.acesso import Acesso
from nuvem.erros import NaoEncontradoError
from nuvem.portaria import visitas
from nuvem.portaria.modelos import Evento, Excecao, Visita
from nuvem.portaria.visitas import (
    Candidato,
    PlacaNaVisita,
    SiteDaVisita,
    TransicaoInvalidaError,
)
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Registrar = Callable[..., Passagem]

CHEGADA = datetime(2026, 10, 5, 17, 2, 11, tzinfo=UTC)
AGORA = CHEGADA + timedelta(seconds=3)
CAVALO = PlacaNaVisita(placa="ABC1D23", papel="cavalo", como="lida")
REBOQUE_INFERIDO = PlacaNaVisita(placa="DEF4G56", papel="reboque", como="inferida")


@pytest.fixture
def site_a(cenario: Demonstracao) -> SiteDaVisita:
    """O site_a, como o casamento o recebe da passagem."""
    return SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id)


@pytest.fixture
def agendamento(sessao: Session, cenario: Demonstracao, acesso_a: Acesso) -> Agendamento:
    """Um agendamento do site_a, para 14h–16h em São Paulo."""
    destino = agendamentos.site_para_agendar(sessao, acesso_a, cenario.site_a.id)
    dados = DadosDoAgendamento(
        codigo_externo="AG-1",
        janela_inicio=datetime(2026, 10, 5, 17, tzinfo=UTC),
        janela_fim=datetime(2026, 10, 5, 19, tzinfo=UTC),
        tipo="descarga",
        placa_cavalo="ABC1D23",
        placas_reboques=("DEF4G56",),
    )
    return agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento


def _check_in(
    sessao: Session,
    site: SiteDaVisita,
    agendamento: Agendamento,
    passagem: Passagem,
    **mais: Any,
) -> Visita:
    return visitas.abrir_visita(
        sessao,
        site,
        "check_in",
        momento=passagem.inicio,
        agora=AGORA,
        agendamento_id=agendamento.id,
        composicao=(CAVALO, REBOQUE_INFERIDO),
        passagem_id=passagem.id,
        dados={"pontos": 100},
        **mais,
    )


def _eventos(sessao: Session, visita: Visita) -> list[Evento]:
    return list(
        sessao.scalars(select(Evento).where(Evento.visita_id == visita.id).order_by(Evento.id))
    )


# --- Abrir a visita na chegada (D-35) ---------------------------------------------------------


def test_check_in_abre_a_visita_na_fila_com_o_evento(
    sessao: Session,
    cenario: Demonstracao,
    site_a: SiteDaVisita,
    agendamento: Agendamento,
    registrar_passagem: Registrar,
) -> None:
    passagem = registrar_passagem()

    visita = _check_in(sessao, site_a, agendamento, passagem)

    assert (visita.estado, visita.agendamento_id, visita.site_id) == (
        "NA_FILA",
        agendamento.id,
        cenario.site_a.id,
    )
    assert (visita.chegou_em, visita.saiu_em, visita.passagem_entrada_id) == (
        passagem.inicio,
        None,
        passagem.id,
    )
    assert visita.composicao == [
        {"placa": "ABC1D23", "papel": "cavalo", "como": "lida"},
        {"placa": "DEF4G56", "papel": "reboque", "como": "inferida"},
    ]
    [evento] = _eventos(sessao, visita)
    assert (evento.tipo, evento.estado, evento.momento, evento.registrado_em) == (
        "check_in",
        "NA_FILA",
        passagem.inicio,
        AGORA,
    )
    assert (evento.usuario_id, evento.passagem_id, evento.dados) == (
        None,
        passagem.id,
        {"pontos": 100},
    )


def test_excecao_abre_a_visita_em_excecao_com_os_candidatos(
    sessao: Session, site_a: SiteDaVisita, agendamento: Agendamento, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    excecao = visitas.abrir_excecao(
        sessao,
        site_a,
        passagem_id=passagem.id,
        momento=passagem.inicio,
        agora=AGORA,
        motivo="candidatos_proximos",
        candidatos=(Candidato(agendamento_id=agendamento.id, pontos=70),),
        composicao=(CAVALO,),
    )

    visita = sessao.get_one(Visita, excecao.visita_id)
    assert (visita.estado, visita.agendamento_id, visita.chegou_em) == (
        "EXCECAO",
        None,
        passagem.inicio,
    )
    assert (excecao.motivo, excecao.situacao, excecao.passagem_id) == (
        "candidatos_proximos",
        "aberta",
        passagem.id,
    )
    assert excecao.candidatos == [{"agendamento_id": agendamento.id, "pontos": 70}]
    [evento] = _eventos(sessao, visita)
    assert (evento.tipo, evento.estado) == ("excecao", "EXCECAO")
    assert evento.dados == {"motivo": "candidatos_proximos", "candidatos": excecao.candidatos}


def test_nao_veio_abre_a_visita_sem_chegada(
    sessao: Session, site_a: SiteDaVisita, agendamento: Agendamento
) -> None:
    prazo = agendamento.janela_fim + timedelta(hours=4)

    visita = visitas.abrir_visita(
        sessao, site_a, "nao_veio", momento=prazo, agora=AGORA, agendamento_id=agendamento.id
    )

    assert (visita.estado, visita.chegou_em, visita.composicao) == ("NAO_VEIO", None, [])
    assert [(e.tipo, e.momento) for e in _eventos(sessao, visita)] == [("nao_veio", prazo)]


def test_evento_que_nao_abre_visita_e_recusado(
    sessao: Session, site_a: SiteDaVisita, agendamento: Agendamento
) -> None:
    with pytest.raises(TransicaoInvalidaError):
        visitas.abrir_visita(
            sessao, site_a, "saiu_sem_atendimento", momento=CHEGADA, agora=AGORA,
            agendamento_id=agendamento.id,
        )  # fmt: skip


def test_um_agendamento_tem_no_maximo_uma_visita(
    sessao: Session, site_a: SiteDaVisita, agendamento: Agendamento, registrar_passagem: Registrar
) -> None:
    _check_in(sessao, site_a, agendamento, registrar_passagem())

    with pytest.raises(DBAPIError) as erro:
        _check_in(sessao, site_a, agendamento, registrar_passagem())

    assert sqlstate(erro.value) == SQLSTATE_UNICIDADE


# --- Transições -------------------------------------------------------------------------------


def test_saida_da_fila_e_saiu_sem_atendimento(
    sessao: Session, site_a: SiteDaVisita, agendamento: Agendamento, registrar_passagem: Registrar
) -> None:
    visita = _check_in(sessao, site_a, agendamento, registrar_passagem())
    saida = registrar_passagem(inicio=CHEGADA + timedelta(hours=3))

    visitas.registrar(
        sessao, visita, "saiu_sem_atendimento", momento=saida.inicio, agora=AGORA,
        passagem_id=saida.id,
    )  # fmt: skip

    assert (visita.estado, visita.saiu_em, visita.passagem_saida_id) == (
        "SAIU",
        saida.inicio,
        saida.id,
    )
    assert [(e.tipo, e.estado) for e in _eventos(sessao, visita)] == [
        ("check_in", "NA_FILA"),
        ("saiu_sem_atendimento", "SAIU"),
    ]


def test_sair_em_excecao_resolve_a_excecao_pelo_sistema(
    sessao: Session, site_a: SiteDaVisita, registrar_passagem: Registrar
) -> None:
    excecao = visitas.abrir_excecao(
        sessao, site_a, passagem_id=registrar_passagem().id, momento=CHEGADA, agora=AGORA,
        motivo="sem_candidato", candidatos=(), composicao=(CAVALO,),
    )  # fmt: skip
    visita = sessao.get_one(Visita, excecao.visita_id)
    saiu = CHEGADA + timedelta(minutes=20)

    visitas.registrar(sessao, visita, "saiu_sem_atendimento", momento=saiu, agora=AGORA)

    assert visita.estado == "SAIU"
    assert (excecao.situacao, excecao.resolvida_em, excecao.resolvida_por, excecao.resolucao) == (
        "resolvida",
        AGORA,
        None,
        "saiu",
    )


@pytest.mark.parametrize("evento", ["check_in", "excecao", "nao_veio"])
def test_transicao_fora_do_diagrama_e_recusada(
    sessao: Session,
    site_a: SiteDaVisita,
    agendamento: Agendamento,
    registrar_passagem: Registrar,
    evento: visitas.TipoDeEvento,
) -> None:
    visita = _check_in(sessao, site_a, agendamento, registrar_passagem())

    with pytest.raises(TransicaoInvalidaError, match=f"NA_FILA.*{evento}"):
        visitas.registrar(sessao, visita, evento, momento=CHEGADA, agora=AGORA)

    assert visita.estado == "NA_FILA"
    assert len(_eventos(sessao, visita)) == 1


@pytest.mark.parametrize("estado", ["SAIU", "NAO_VEIO"])
def test_estado_final_nao_muda_mais(
    sessao: Session,
    site_a: SiteDaVisita,
    agendamento: Agendamento,
    registrar_passagem: Registrar,
    estado: str,
) -> None:
    if estado == "SAIU":
        visita = _check_in(sessao, site_a, agendamento, registrar_passagem())
        visitas.registrar(sessao, visita, "saiu_sem_atendimento", momento=CHEGADA, agora=AGORA)
    else:
        visita = visitas.abrir_visita(
            sessao, site_a, "nao_veio", momento=CHEGADA, agora=AGORA,
            agendamento_id=agendamento.id,
        )  # fmt: skip

    with pytest.raises(TransicaoInvalidaError):
        visitas.registrar(sessao, visita, "saiu_sem_atendimento", momento=CHEGADA, agora=AGORA)


# --- A composição (D-17) ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "composicao",
    [
        (CAVALO, CAVALO.model_copy(update={"placa": "XYZ9K87"})),  # dois cavalos
        (CAVALO, REBOQUE_INFERIDO, REBOQUE_INFERIDO),  # a mesma placa duas vezes
    ],
)
def test_composicao_fora_da_regra_e_recusada(
    sessao: Session,
    site_a: SiteDaVisita,
    agendamento: Agendamento,
    registrar_passagem: Registrar,
    composicao: tuple[PlacaNaVisita, ...],
) -> None:
    with pytest.raises(ValueError, match="composição"):
        visitas.abrir_visita(
            sessao, site_a, "check_in", momento=CHEGADA, agora=AGORA,
            agendamento_id=agendamento.id, composicao=composicao,
            passagem_id=registrar_passagem().id,
        )  # fmt: skip


def test_placa_da_composicao_segue_a_regra_e_diz_se_foi_lida_ou_inferida() -> None:
    assert PlacaNaVisita(placa="abc-1d23", papel="cavalo", como="lida").placa == "ABC1D23"
    for errado in ({"placa": "ABC12"}, {"como": "chutada"}, {"papel": "carreta"}):
        with pytest.raises(ValidationError):
            PlacaNaVisita.model_validate(
                {"placa": "ABC1D23", "papel": "cavalo", "como": "lida"} | errado
            )


# --- Prova: o evento só se acrescenta (SDD 5.5) -----------------------------------------------


def test_banco_recusa_alterar_um_evento(
    sessao: Session, site_a: SiteDaVisita, agendamento: Agendamento, registrar_passagem: Registrar
) -> None:
    visita = _check_in(sessao, site_a, agendamento, registrar_passagem())

    with pytest.raises(DBAPIError) as erro:
        sessao.execute(update(Evento).where(Evento.visita_id == visita.id).values(dados={}))

    assert sqlstate(erro.value) == SQLSTATE_SO_ACRESCENTA


def test_banco_recusa_apagar_um_evento(
    sessao: Session, site_a: SiteDaVisita, agendamento: Agendamento, registrar_passagem: Registrar
) -> None:
    visita = _check_in(sessao, site_a, agendamento, registrar_passagem())

    with pytest.raises(DBAPIError) as erro:
        sessao.execute(delete(Evento).where(Evento.visita_id == visita.id))

    assert sqlstate(erro.value) == SQLSTATE_SO_ACRESCENTA


def test_banco_recusa_esvaziar_a_tabela_de_eventos(sessao: Session) -> None:
    with pytest.raises(DBAPIError) as erro:
        sessao.execute(text("truncate evento"))

    assert sqlstate(erro.value) == SQLSTATE_SO_ACRESCENTA


def test_banco_recusa_alterar_uma_mudanca_de_agendamento(
    sessao: Session, agendamento: Agendamento
) -> None:
    with pytest.raises(DBAPIError) as erro:
        sessao.execute(
            update(MudancaAgendamento)
            .where(MudancaAgendamento.agendamento_id == agendamento.id)
            .values(depois={})
        )

    assert sqlstate(erro.value) == SQLSTATE_SO_ACRESCENTA


# --- O banco também confere -------------------------------------------------------------------


def test_banco_recusa_visita_ligada_a_agendamento_de_outra_empresa(
    sessao: Session, cenario: Demonstracao, agendamento: Agendamento
) -> None:
    site_b = SiteDaVisita(empresa_id=cenario.empresa_b.id, site_id=cenario.site_b.id)

    with pytest.raises(DBAPIError) as erro:
        visitas.abrir_visita(
            sessao, site_b, "nao_veio", momento=CHEGADA, agora=AGORA,
            agendamento_id=agendamento.id,
        )  # fmt: skip

    assert sqlstate(erro.value) == SQLSTATE_CHAVE_ESTRANGEIRA


def test_banco_recusa_visita_que_nao_veio_com_chegada(
    sessao: Session, site_a: SiteDaVisita, agendamento: Agendamento
) -> None:
    visita = visitas.abrir_visita(
        sessao, site_a, "nao_veio", momento=CHEGADA, agora=AGORA, agendamento_id=agendamento.id
    )
    visita.chegou_em = CHEGADA

    with pytest.raises(DBAPIError) as erro:
        sessao.flush()

    assert sqlstate(erro.value) == SQLSTATE_CHECK


def test_banco_recusa_visita_que_saiu_sem_hora_de_saida(
    sessao: Session, site_a: SiteDaVisita, agendamento: Agendamento, registrar_passagem: Registrar
) -> None:
    visita = _check_in(sessao, site_a, agendamento, registrar_passagem())
    visita.estado = "SAIU"

    with pytest.raises(DBAPIError) as erro:
        sessao.flush()

    assert sqlstate(erro.value) == SQLSTATE_CHECK


# --- Ler, com o Acesso de quem pede (SDD 5.5) -------------------------------------------------


def test_le_a_visita_e_os_eventos_do_proprio_site(
    sessao: Session,
    site_a: SiteDaVisita,
    agendamento: Agendamento,
    registrar_passagem: Registrar,
    acesso_a: Acesso,
    acesso_b: Acesso,
) -> None:
    visita = _check_in(sessao, site_a, agendamento, registrar_passagem())

    assert visitas.obter_visita(sessao, acesso_a, visita.id) == visita
    assert [e.tipo for e in visitas.eventos_da_visita(sessao, acesso_a, visita.id)] == ["check_in"]
    for leitura in (visitas.obter_visita, visitas.eventos_da_visita):
        with pytest.raises(NaoEncontradoError):
            leitura(sessao, acesso_b, visita.id)


def test_excecoes_abertas_do_site_da_mais_velha_a_mais_nova(
    sessao: Session,
    cenario: Demonstracao,
    site_a: SiteDaVisita,
    registrar_passagem: Registrar,
    acesso_a: Acesso,
    acesso_b: Acesso,
) -> None:
    def abrir(minutos: int) -> Excecao:
        return visitas.abrir_excecao(
            sessao, site_a, passagem_id=registrar_passagem().id,
            momento=CHEGADA + timedelta(minutes=minutos), agora=AGORA,
            motivo="sem_candidato", candidatos=(), composicao=(CAVALO,),
        )  # fmt: skip

    depois, antes, resolvida = abrir(10), abrir(0), abrir(5)
    visitas.registrar(
        sessao, sessao.get_one(Visita, resolvida.visita_id), "saiu_sem_atendimento",
        momento=CHEGADA, agora=AGORA,
    )  # fmt: skip

    assert visitas.excecoes_abertas(sessao, acesso_a, cenario.site_a.id) == [antes, depois]
    with pytest.raises(NaoEncontradoError):
        visitas.excecoes_abertas(sessao, acesso_b, cenario.site_a.id)


def test_visita_de_site_fora_do_alcance_nao_e_encontrada(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    # O site_a2 é da empresa A, mas o gestor A não o vê.
    site_a2 = SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a2.id)
    destino = agendamentos.SiteDoAgendamento(
        empresa_id=cenario.empresa_a.id, site_id=cenario.site_a2.id, usuario_id=None
    )
    dados = DadosDoAgendamento(
        codigo_externo="A2-1", janela_inicio=CHEGADA, janela_fim=CHEGADA + timedelta(hours=1),
        tipo="carga", placa_cavalo="ABC1D23",
    )  # fmt: skip
    do_a2 = agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento
    visita = visitas.abrir_visita(
        sessao, site_a2, "nao_veio", momento=CHEGADA, agora=AGORA, agendamento_id=do_a2.id
    )

    with pytest.raises(NaoEncontradoError):
        visitas.obter_visita(sessao, acesso_a, visita.id)

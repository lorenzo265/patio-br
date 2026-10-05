"""O porteiro resolve a exceção, corrige a placa e registra a chegada à mão (T41, D-46)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from contratos.placa import PlacaInvalidaError
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.cadastro.acesso import Acesso, acesso_do_usuario
from nuvem.erros import NaoEncontradoError
from nuvem.portaria import resolucao, visitas
from nuvem.portaria.casamento import processar_passagem
from nuvem.portaria.modelos import ConferenciaPlaca, Evento, Excecao, Visita
from nuvem.portaria.resolucao import AgendamentoIndisponivelError, ExcecaoJaResolvidaError
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Registrar = Callable[..., Passagem]
Agendar = Callable[..., Agendamento]

AGORA = datetime(2026, 10, 5, 17, 5, tzinfo=UTC)
"""14:05 em São Paulo; a passagem da fixture é das 14:02."""
CEDO = datetime(2026, 10, 5, 16, tzinfo=UTC)
"""13h às 15h: a passagem das 14:02 cai na janela."""
TARDE = datetime(2026, 10, 5, 18, 30, tzinfo=UTC)
"""15h30 às 17h30: a passagem das 14:02 cai só na tolerância."""


@pytest.fixture
def porteiro(sessao: Session, cenario: Demonstracao) -> Acesso:
    return acesso_do_usuario(sessao, cenario.porteiro_a.id)


@pytest.fixture
def agendar(sessao: Session, cenario: Demonstracao) -> Agendar:
    """Grava um agendamento no site_a com a janela de 2 horas que começa em ``inicio``."""

    def _agendar(
        codigo: str, inicio: datetime, cavalo: str = "ABC1D23", reboques: tuple[str, ...] = ()
    ) -> Agendamento:
        destino = SiteDoAgendamento(
            empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id, usuario_id=None
        )
        dados = DadosDoAgendamento(
            codigo_externo=codigo,
            janela_inicio=inicio,
            janela_fim=inicio + timedelta(hours=2),
            tipo="descarga",
            placa_cavalo=cavalo,
            placas_reboques=reboques,
        )
        return agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento

    return _agendar


@pytest.fixture
def excecao_de(sessao: Session, registrar_passagem: Registrar) -> Callable[..., Excecao]:
    """Registra uma passagem, casa, e devolve a exceção que ela abriu."""

    def _excecao(**mudancas: object) -> Excecao:
        passagem = registrar_passagem(**mudancas)
        processada = processar_passagem(sessao, passagem.id, agora=AGORA)
        assert processada.resultado == "excecao", processada
        return sessao.scalars(select(Excecao).where(Excecao.passagem_id == passagem.id)).one()

    return _excecao


def _lida(placa: str, camera: str) -> dict[str, object]:
    return {"placa": placa, "papel": "cavalo", "confianca": 0.9, "camera_id": camera, "quadros": 4}


def _visita(sessao: Session, excecao: Excecao) -> Visita:
    sessao.expire_all()
    return sessao.get_one(Visita, excecao.visita_id)


def _eventos(sessao: Session, visita: Visita) -> list[Evento]:
    return list(
        sessao.scalars(select(Evento).where(Evento.visita_id == visita.id).order_by(Evento.id))
    )


# --- As opções do porteiro --------------------------------------------------------------------


def test_opcoes_trazem_os_agendamentos_perto_sem_visita_pelos_pontos(
    sessao: Session, porteiro: Acesso, agendar: Agendar, excecao_de: Callable[..., Excecao]
) -> None:
    agendar("TARDE", TARDE)
    agendar("CEDO", CEDO)
    agendar("AMANHA", CEDO + timedelta(days=1))
    excecao = excecao_de()  # 80 e 70 pontos: candidatos próximos

    opcoes = resolucao.opcoes(sessao, porteiro, excecao.id)

    assert [(o.codigo, o.pontos) for o in opcoes] == [("CEDO", 80), ("TARDE", 70)]


def test_opcoes_de_outra_empresa_nao_sao_encontradas(
    sessao: Session, acesso_b: Acesso, agendar: Agendar, excecao_de: Callable[..., Excecao]
) -> None:
    agendar("CEDO", CEDO)
    agendar("TARDE", TARDE)
    excecao = excecao_de()

    with pytest.raises(NaoEncontradoError):
        resolucao.opcoes(sessao, acesso_b, excecao.id)


# --- "É este" ---------------------------------------------------------------------------------


def test_e_este_liga_ao_agendamento_e_a_visita_vai_para_a_fila(
    sessao: Session, porteiro: Acesso, agendar: Agendar, excecao_de: Callable[..., Excecao]
) -> None:
    cedo = agendar("CEDO", CEDO, reboques=("DEF4G56",))
    agendar("TARDE", TARDE, reboques=("DEF4G56",))
    excecao = excecao_de()

    resolucao.ligar_ao_agendamento(sessao, porteiro, excecao.id, cedo.id, agora=AGORA)

    visita = _visita(sessao, excecao)
    assert (visita.estado, visita.agendamento_id) == ("NA_FILA", cedo.id)
    assert visita.composicao == [
        {"placa": "ABC1D23", "papel": "cavalo", "como": "lida"},
        {"placa": "DEF4G56", "papel": "reboque", "como": "inferida"},
    ]
    resolvida = sessao.get_one(Excecao, excecao.id)
    assert (resolvida.situacao, resolvida.resolvida_por, resolvida.resolvida_em) == (
        "resolvida", porteiro.usuario_id, AGORA,
    )  # fmt: skip
    assert resolvida.resolucao == "ligada ao agendamento CEDO"
    ultimo = _eventos(sessao, visita)[-1]
    assert (ultimo.tipo, ultimo.estado, ultimo.usuario_id) == (
        "check_in", "NA_FILA", porteiro.usuario_id,
    )  # fmt: skip


def test_agendamento_que_ja_tem_visita_nao_serve(
    sessao: Session, porteiro: Acesso, agendar: Agendar, excecao_de: Callable[..., Excecao]
) -> None:
    cedo = agendar("CEDO", CEDO)
    agendar("TARDE", TARDE)
    primeira, segunda = excecao_de(), excecao_de()
    resolucao.ligar_ao_agendamento(sessao, porteiro, primeira.id, cedo.id, agora=AGORA)

    with pytest.raises(AgendamentoIndisponivelError):
        resolucao.ligar_ao_agendamento(sessao, porteiro, segunda.id, cedo.id, agora=AGORA)

    assert _visita(sessao, segunda).estado == "EXCECAO"


def test_agendamento_longe_da_hora_cancelado_ou_de_outra_empresa_nao_serve(
    sessao: Session,
    porteiro: Acesso,
    acesso_b: Acesso,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    excecao = excecao_de()  # sem agendamento perto: sem candidato
    amanha = agendar("AMANHA", CEDO + timedelta(days=1))
    cancelado = agendar("CANCELADO", CEDO)
    agendamentos.cancelar(sessao, porteiro, cancelado.id, agora=AGORA)
    destino_b = agendamentos.site_para_agendar(sessao, acesso_b, cenario.site_b.id)
    dados_b = DadosDoAgendamento(
        codigo_externo="B-1", janela_inicio=CEDO, janela_fim=CEDO + timedelta(hours=2),
        tipo="carga", placa_cavalo="ABC1D23",
    )  # fmt: skip
    de_fora = agendamentos.gravar(sessao, destino_b, "planilha", dados_b, agora=AGORA).agendamento

    for agendamento in (amanha, cancelado, de_fora):
        with pytest.raises(AgendamentoIndisponivelError):
            resolucao.ligar_ao_agendamento(
                sessao, porteiro, excecao.id, agendamento.id, agora=AGORA
            )


# --- Sem agendamento e recusa -----------------------------------------------------------------


def test_aceitar_sem_agendamento_leva_a_visita_para_a_fila(
    sessao: Session, porteiro: Acesso, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de()

    resolucao.aceitar_sem_agendamento(sessao, porteiro, excecao.id, agora=AGORA)

    visita = _visita(sessao, excecao)
    assert (visita.estado, visita.agendamento_id) == ("NA_FILA", None)
    assert sessao.get_one(Excecao, excecao.id).resolucao == "aceita sem agendamento"
    assert _eventos(sessao, visita)[-1].tipo == "aceita_sem_agendamento"


def test_recusar_leva_a_visita_a_recusada_e_tira_das_excecoes_abertas(
    sessao: Session, porteiro: Acesso, cenario: Demonstracao, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de()

    resolucao.recusar(sessao, porteiro, excecao.id, agora=AGORA)

    visita = _visita(sessao, excecao)
    assert visita.estado == "RECUSADA"
    assert _eventos(sessao, visita)[-1].tipo == "recusada"
    assert sessao.get_one(Excecao, excecao.id).resolucao == "recusada"
    assert visitas.excecoes_abertas(sessao, porteiro, cenario.site_a.id) == []


def test_excecao_resolvida_nao_se_resolve_de_novo(
    sessao: Session, porteiro: Acesso, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de()
    resolucao.aceitar_sem_agendamento(sessao, porteiro, excecao.id, agora=AGORA)

    with pytest.raises(ExcecaoJaResolvidaError):
        resolucao.recusar(sessao, porteiro, excecao.id, agora=AGORA)

    assert _visita(sessao, excecao).estado == "NA_FILA"


def test_excecao_de_outra_empresa_nao_e_encontrada(
    sessao: Session, acesso_b: Acesso, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de()

    with pytest.raises(NaoEncontradoError):
        resolucao.aceitar_sem_agendamento(sessao, acesso_b, excecao.id, agora=AGORA)


# --- Corrigir a placa numa exceção casa de novo -----------------------------------------------


def test_conferir_a_placa_numa_excecao_casa_de_novo(
    sessao: Session,
    porteiro: Acesso,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    agendamento = agendar("AG-1", CEDO, reboques=("DEF4G56",))
    # O leitor errou um número (3 → 8): sem candidato.
    excecao = excecao_de(placas=[_lida("ABC1D28", str(cenario.camera_a.id))])

    resolucao.conferir_placa(sessao, porteiro, excecao.passagem_id, 0, "ABC1D23", agora=AGORA)

    visita = _visita(sessao, excecao)
    assert (visita.estado, visita.agendamento_id) == ("NA_FILA", agendamento.id)
    assert visita.composicao[0] == {"placa": "ABC1D23", "papel": "cavalo", "como": "digitada"}
    resolvida = sessao.get_one(Excecao, excecao.id)
    assert (resolvida.situacao, resolvida.resolucao, resolvida.resolvida_por) == (
        "resolvida", "placa corrigida, ligada ao agendamento AG-1", porteiro.usuario_id,
    )  # fmt: skip
    conferida = sessao.scalars(select(ConferenciaPlaca)).one()
    assert (conferida.placa_lida, conferida.placa) == ("ABC1D28", "ABC1D23")


def test_placa_corrigida_sem_casamento_seguro_atualiza_os_candidatos(
    sessao: Session,
    porteiro: Acesso,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    cedo, tarde = agendar("CEDO", CEDO), agendar("TARDE", TARDE)
    excecao = excecao_de(placas=[_lida("ABC1D28", str(cenario.camera_a.id))])

    resolucao.conferir_placa(sessao, porteiro, excecao.passagem_id, 0, "ABC1D23", agora=AGORA)

    visita = _visita(sessao, excecao)
    assert visita.estado == "EXCECAO"
    aberta = sessao.get_one(Excecao, excecao.id)
    assert (aberta.situacao, aberta.motivo) == ("aberta", "candidatos_proximos")
    assert aberta.candidatos == [
        {"agendamento_id": cedo.id, "pontos": 80}, {"agendamento_id": tarde.id, "pontos": 70},
    ]  # fmt: skip
    ultimo = _eventos(sessao, visita)[-1]
    assert (ultimo.tipo, ultimo.estado, ultimo.usuario_id) == (
        "placa_corrigida", "EXCECAO", porteiro.usuario_id,
    )  # fmt: skip
    assert visita.composicao == [{"placa": "ABC1D23", "papel": "cavalo", "como": "digitada"}]


def test_conferir_a_foto_de_uma_excecao_sem_placa_lida(
    sessao: Session, porteiro: Acesso, agendar: Agendar, excecao_de: Callable[..., Excecao]
) -> None:
    agendamento = agendar("AG-1", CEDO)
    excecao = excecao_de(placas=[])  # a foto chegou, mas o leitor não leu nada

    resolucao.conferir_placa(sessao, porteiro, excecao.passagem_id, 0, "ABC1D23", agora=AGORA)

    visita = _visita(sessao, excecao)
    assert (visita.estado, visita.agendamento_id) == ("NA_FILA", agendamento.id)


def test_confirmar_a_placa_numa_excecao_nao_muda_nada(
    sessao: Session,
    porteiro: Acesso,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    agendar("CEDO", CEDO)
    agendar("TARDE", TARDE)
    excecao = excecao_de()  # ABC1D23 lida certa, mas dois agendamentos perto
    eventos_antes = len(_eventos(sessao, _visita(sessao, excecao)))

    resolucao.conferir_placa(sessao, porteiro, excecao.passagem_id, 0, "ABC1D23", agora=AGORA)

    visita = _visita(sessao, excecao)
    assert visita.estado == "EXCECAO"
    assert len(_eventos(sessao, visita)) == eventos_antes


def test_digitar_o_cavalo_troca_a_placa_lida_errada(
    sessao: Session,
    porteiro: Acesso,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    agendamento = agendar("AG-1", CEDO)
    excecao = excecao_de(placas=[_lida("ABC1D28", str(cenario.camera_a.id))], fotos=[])

    resolucao.digitar_cavalo(sessao, porteiro, excecao.id, "ABC1D23", agora=AGORA)

    visita = _visita(sessao, excecao)
    assert visita.agendamento_id == agendamento.id
    assert [p["placa"] for p in visita.composicao] == ["ABC1D23"]


def test_digitar_o_cavalo_sem_casamento_seguro_troca_a_placa_na_excecao(
    sessao: Session,
    porteiro: Acesso,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    agendar("CEDO", CEDO)
    agendar("TARDE", TARDE)
    excecao = excecao_de(placas=[_lida("ABC1D28", str(cenario.camera_a.id))], fotos=[])

    resolucao.digitar_cavalo(sessao, porteiro, excecao.id, "ABC1D23", agora=AGORA)

    visita = _visita(sessao, excecao)
    assert visita.estado == "EXCECAO"
    assert visita.composicao == [{"placa": "ABC1D23", "papel": "cavalo", "como": "digitada"}]


def test_digitar_a_placa_do_cavalo_quando_nao_ha_foto(
    sessao: Session, porteiro: Acesso, agendar: Agendar, excecao_de: Callable[..., Excecao]
) -> None:
    agendamento = agendar("AG-1", CEDO)
    excecao = excecao_de(placas=[], fotos=[])  # nenhuma placa lida

    resolucao.digitar_cavalo(sessao, porteiro, excecao.id, " abc-1d23 ", agora=AGORA)

    visita = _visita(sessao, excecao)
    assert (visita.estado, visita.agendamento_id) == ("NA_FILA", agendamento.id)


def test_placa_digitada_fora_do_formato_nao_muda_nada(
    sessao: Session, porteiro: Acesso, agendar: Agendar, excecao_de: Callable[..., Excecao]
) -> None:
    agendar("AG-1", CEDO)
    excecao = excecao_de(placas=[], fotos=[])

    with pytest.raises(PlacaInvalidaError):
        resolucao.digitar_cavalo(sessao, porteiro, excecao.id, "AB12", agora=AGORA)

    assert _visita(sessao, excecao).estado == "EXCECAO"


def test_conferir_fora_de_excecao_nao_muda_a_visita(
    sessao: Session, porteiro: Acesso, agendar: Agendar, registrar_passagem: Registrar
) -> None:
    agendamento = agendar("AG-1", CEDO)
    passagem = registrar_passagem()
    processar_passagem(sessao, passagem.id, agora=AGORA)  # check-in automático

    resolucao.conferir_placa(sessao, porteiro, passagem.id, 0, "XYZ9876", agora=AGORA)

    visita = sessao.scalars(select(Visita)).one()
    assert (visita.estado, visita.agendamento_id) == ("NA_FILA", agendamento.id)
    assert visita.composicao[0]["placa"] == "ABC1D23"


# --- Chegada registrada à mão -----------------------------------------------------------------


def test_sugestoes_da_chegada_manual_pelos_pontos(
    sessao: Session, porteiro: Acesso, cenario: Demonstracao, agendar: Agendar
) -> None:
    agendar("TARDE", TARDE)
    agendar("CEDO", CEDO)
    agendar("OUTRO", CEDO, cavalo="XYZ9876")

    sugestoes = resolucao.sugestoes(sessao, porteiro, cenario.site_a.id, ["abc1d23"], agora=AGORA)

    assert [(s.codigo, s.pontos) for s in sugestoes] == [("CEDO", 80), ("TARDE", 70), ("OUTRO", 20)]


def test_chegada_manual_com_agendamento(
    sessao: Session, porteiro: Acesso, cenario: Demonstracao, agendar: Agendar
) -> None:
    agendamento = agendar("AG-1", CEDO, reboques=("DEF4G56",))

    visita = resolucao.registrar_chegada_manual(
        sessao, porteiro, cenario.site_a.id, ["ABC1D23"], agendamento.id, agora=AGORA
    )

    assert (visita.estado, visita.agendamento_id, visita.chegou_em) == (
        "NA_FILA", agendamento.id, AGORA,
    )  # fmt: skip
    assert visita.passagem_entrada_id is None
    assert visita.composicao == [
        {"placa": "ABC1D23", "papel": "cavalo", "como": "digitada"},
        {"placa": "DEF4G56", "papel": "reboque", "como": "inferida"},
    ]
    (evento,) = _eventos(sessao, visita)
    assert (evento.tipo, evento.usuario_id, evento.dados["manual"]) == (
        "check_in", porteiro.usuario_id, True,
    )  # fmt: skip


def test_chegada_manual_sem_agendamento(
    sessao: Session, porteiro: Acesso, cenario: Demonstracao
) -> None:
    visita = resolucao.registrar_chegada_manual(
        sessao, porteiro, cenario.site_a.id, ["ABC1D23", "DEF4G56"], None, agora=AGORA
    )

    assert (visita.estado, visita.agendamento_id) == ("NA_FILA", None)
    assert visita.composicao == [
        {"placa": "ABC1D23", "papel": "cavalo", "como": "digitada"},
        {"placa": "DEF4G56", "papel": "reboque", "como": "digitada"},
    ]
    assert _eventos(sessao, visita)[0].tipo == "aceita_sem_agendamento"


def test_chegada_manual_com_agendamento_indisponivel(
    sessao: Session, porteiro: Acesso, cenario: Demonstracao, agendar: Agendar
) -> None:
    amanha = agendar("AMANHA", CEDO + timedelta(days=1))

    with pytest.raises(AgendamentoIndisponivelError):
        resolucao.registrar_chegada_manual(
            sessao, porteiro, cenario.site_a.id, ["ABC1D23"], amanha.id, agora=AGORA
        )


def test_chegada_manual_precisa_de_placa_valida(
    sessao: Session, porteiro: Acesso, cenario: Demonstracao
) -> None:
    for placas in ([], ["AB12"]):
        with pytest.raises(PlacaInvalidaError):
            resolucao.registrar_chegada_manual(
                sessao, porteiro, cenario.site_a.id, placas, None, agora=AGORA
            )

    assert sessao.scalars(select(Visita)).all() == []


def test_chegada_manual_em_site_que_nao_ve(
    sessao: Session, acesso_b: Acesso, cenario: Demonstracao
) -> None:
    with pytest.raises(NaoEncontradoError):
        resolucao.registrar_chegada_manual(
            sessao, acesso_b, cenario.site_a.id, ["ABC1D23"], None, agora=AGORA
        )

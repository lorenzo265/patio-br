"""O extrato com o banco (T44, SDD 5.4 e D-48): as visitas do site, o mês guardado e o parcial."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.banco import SQLSTATE_SO_ACRESCENTA, sqlstate
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.modelos import Doca
from nuvem.erros import NaoEncontradoError
from nuvem.extrato import servico as extrato
from nuvem.extrato.contas import Parametros
from nuvem.extrato.modelos import Extrato, LinhaDeBase, ParametrosSite
from nuvem.extrato.servico import MesFuturoError
from nuvem.patio import servico as patio
from nuvem.portaria import visitas
from nuvem.portaria.modelos import Visita
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Jornada = Callable[..., Visita]

SETEMBRO = date(2026, 9, 1)
OUTUBRO = date(2026, 10, 1)
AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
"""14h de 05/10 em São Paulo."""
DIA_10 = datetime(2026, 9, 10, 11, 0, tzinfo=UTC)
"""8h de 10/09 em São Paulo."""


@pytest.fixture
def jornada(sessao: Session, cenario: Demonstracao, acesso_a: Acesso) -> Jornada:
    """Um caminhão no site_a: chega e, se pedir, é chamado, começa e termina na doca."""
    docas = list(sessao.scalars(select(Doca).where(Doca.site_id == cenario.site_a.id)))
    contador = iter(range(1, 1000))

    def _jornada(
        chegada: datetime,
        *,
        chamada: timedelta | None = None,
        inicio: timedelta | None = None,
        fim: timedelta | None = None,
        toneladas: str | None = None,
        automatica: bool = True,
        site_id: int | None = None,
        empresa_id: int | None = None,
    ) -> Visita:
        numero = next(contador)
        site = SiteDaVisita(
            empresa_id=empresa_id or cenario.empresa_a.id, site_id=site_id or cenario.site_a.id
        )
        destino = SiteDoAgendamento(site.empresa_id, site.site_id, None)
        dados = DadosDoAgendamento(
            codigo_externo=f"AG-{numero}", janela_inicio=chegada, tipo="descarga",
            janela_fim=chegada + timedelta(hours=2), placa_cavalo=f"ABC{numero:04d}",
            toneladas=Decimal(toneladas) if toneladas else None,
        )  # fmt: skip
        agendamento = agendamentos.gravar(sessao, destino, "planilha", dados, agora=chegada)
        visita = visitas.abrir_visita(
            sessao, site, "check_in", momento=chegada, agora=chegada,
            agendamento_id=agendamento.agendamento.id,
            composicao=(PlacaNaVisita(placa=f"ABC{numero:04d}", papel="cavalo", como="lida"),),
            usuario_id=None if automatica else cenario.porteiro_a.id,
        )  # fmt: skip
        if chamada is not None:
            livre = next(
                d for d in docas if d in patio.docas_livres(sessao, acesso_a, site.site_id)
            )
            patio.chamar(sessao, acesso_a, visita.id, livre.id, agora=chegada + chamada)
        if inicio is not None:
            patio.iniciar(sessao, acesso_a, visita.id, agora=chegada + inicio)
        if fim is not None:
            patio.finalizar(sessao, acesso_a, visita.id, agora=chegada + fim)
        return visita

    return _jornada


def _completa(jornada: Jornada, chegada: datetime, **mudancas: object) -> Visita:
    """Chamada em 1 h, começa em 1h10 e termina em 2h10 (salvo o que mudar)."""
    horas: dict[str, object] = {
        "chamada": timedelta(hours=1), "inicio": timedelta(hours=1, minutes=10),
        "fim": timedelta(hours=2, minutes=10),
    }  # fmt: skip
    return jornada(chegada, **(horas | mudancas))


# --- Os parâmetros e a linha de base ----------------------------------------------------------


def test_parametros_do_site_vem_da_semente(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    parametros = extrato.parametros(sessao, acesso_a, cenario.site_a.id)

    assert (parametros.postos_antes, parametros.postos_depois) == (Decimal(3), Decimal(2))
    assert parametros.custo_mensal_do_posto == Decimal("21500.00")
    assert (parametros.valor_da_estadia, parametros.franquia) == (
        Decimal("2.50"), timedelta(hours=5),
    )  # fmt: skip


def test_site_sem_parametros_usa_os_da_lei(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    sessao.execute(delete(ParametrosSite))

    assert extrato.parametros(sessao, acesso_a, cenario.site_a.id) == Parametros()


def test_a_linha_de_base_da_semente_e_de_exemplo(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    mes = extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA)

    assert mes.linha_de_base is not None
    assert mes.linha_de_base.origem == "exemplo"
    assert mes.linha_de_base.medidas.visitas > 0


def test_sem_linha_de_base_nao_ha_economia(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    sessao.execute(delete(LinhaDeBase))

    mes = extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA)

    assert (mes.linha_de_base, mes.economia) == (None, None)


# --- As medidas do mês ------------------------------------------------------------------------


def test_as_medidas_saem_das_visitas_do_site(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, jornada: Jornada
) -> None:
    # 5h30 de estadia com 30 t: R$ 37,50 de exposição
    _completa(jornada, DIA_10, inicio=timedelta(hours=4), fim=timedelta(hours=5, minutes=30),
              toneladas="30")  # fmt: skip
    _completa(jornada, DIA_10 + timedelta(hours=6), automatica=False)
    jornada(DIA_10 + timedelta(days=1))  # ainda na fila
    jornada(DIA_10, site_id=cenario.site_a2.id)  # outro site
    jornada(DIA_10, site_id=cenario.site_b.id, empresa_id=cenario.empresa_b.id)  # outra empresa

    medidas = extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA).medidas

    assert (medidas.visitas, medidas.automaticas, medidas.chamadas, medidas.liberadas) == (
        3, 2, 2, 2,
    )  # fmt: skip
    assert (medidas.acima_da_franquia, medidas.exposicao) == (1, Decimal("37.50"))
    assert medidas.espera_media == timedelta(hours=1)
    assert medidas.horas_de_doca == Decimal("2.5")  # 1h30 + 1h


def test_as_horas_disponiveis_sao_as_docas_no_horario_do_site(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    medidas = extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA).medidas

    assert medidas.horas_disponiveis == Decimal(30 * 16 * 2)  # das 6h às 22h, 2 docas


def test_a_doca_usada_na_virada_do_mes_conta_nos_dois(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, jornada: Jornada
) -> None:
    virada = datetime(2026, 10, 1, 3, 0, tzinfo=UTC)  # meia-noite de 01/10 em São Paulo
    jornada(virada - timedelta(hours=2), chamada=timedelta(0), inicio=timedelta(hours=1),
            fim=timedelta(hours=3))  # fmt: skip

    setembro = extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA)
    outubro = extrato.do_mes(sessao, acesso_a, cenario.site_a.id, OUTUBRO, agora=AGORA)

    assert (setembro.medidas.horas_de_doca, outubro.medidas.horas_de_doca) == (
        Decimal("1.0"), Decimal("1.0"),
    )  # fmt: skip
    assert (setembro.medidas.visitas, outubro.medidas.visitas) == (1, 0)


def test_o_check_in_pela_pessoa_nao_vira_automatico(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, jornada: Jornada
) -> None:
    visita = jornada(DIA_10, automatica=False)
    # A saída sem atendimento é do sistema, mas não é um check-in.
    visitas.registrar(sessao, visita, "saiu_sem_atendimento", momento=DIA_10, agora=DIA_10)

    medidas = extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA).medidas

    assert (medidas.visitas, medidas.automaticas) == (1, 0)


def test_doca_ocupada_desde_o_mes_passado_conta_no_mes(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, jornada: Jornada
) -> None:
    virada = datetime(2026, 10, 1, 3, 0, tzinfo=UTC)
    jornada(virada - timedelta(hours=2), chamada=timedelta(0), inicio=timedelta(hours=1))

    outubro = extrato.do_mes(
        sessao, acesso_a, cenario.site_a.id, OUTUBRO, agora=virada + timedelta(hours=3)
    )

    assert outubro.medidas.horas_de_doca == Decimal("3.0")


def test_as_visitas_do_extrato_sao_as_do_periodo(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, jornada: Jornada
) -> None:
    dentro = jornada(DIA_10)
    jornada(DIA_10 + timedelta(days=30))  # chegou depois do período

    lidas = visitas.para_o_extrato(
        sessao, acesso_a, cenario.site_a.id, de=DIA_10, ate=DIA_10 + timedelta(days=1)
    )

    assert [(v.id, automatica) for v, automatica in lidas] == [(dentro.id, True)]


def test_site_de_outra_empresa_responde_nao_encontrado(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    with pytest.raises(NaoEncontradoError):
        extrato.do_mes(sessao, acesso_a, cenario.site_b.id, SETEMBRO, agora=AGORA)


# --- O mês fechado e o mês em curso -----------------------------------------------------------


def test_o_mes_fechado_e_guardado_e_nao_muda_depois(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, jornada: Jornada
) -> None:
    _completa(jornada, DIA_10)
    primeiro = extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA)

    sessao.execute(update(ParametrosSite).values(postos_depois=Decimal(1)))
    _completa(jornada, DIA_10 + timedelta(days=1))
    de_novo = extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA)

    assert (primeiro.parcial, primeiro.ate) == (False, datetime(2026, 10, 1, 3, tzinfo=UTC))
    assert primeiro.guardado_em == AGORA
    assert de_novo == primeiro
    assert primeiro.economia is not None and primeiro.economia.portaria == Decimal("21500.00")
    assert sessao.scalar(select(func.count()).select_from(Extrato)) == 1


def test_o_mes_guardado_nao_le_as_visitas_de_novo(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, monkeypatch: pytest.MonkeyPatch
) -> None:
    extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA)

    def nao_devia_ler(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("leu as visitas de um mês já guardado")

    monkeypatch.setattr(extrato.visitas, "para_o_extrato", nao_devia_ler)

    extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA)


def test_o_mes_comeca_a_meia_noite_do_site(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    novembro = date(2026, 11, 1)
    meia_noite = datetime(2026, 11, 1, 3, 0, tzinfo=UTC)

    with pytest.raises(MesFuturoError):
        extrato.do_mes(
            sessao, acesso_a, cenario.site_a.id, novembro, agora=meia_noite - timedelta(seconds=1)
        )
    assert extrato.do_mes(sessao, acesso_a, cenario.site_a.id, novembro, agora=meia_noite).parcial


def test_extrato_guardado_por_outra_versao_da_regra_nao_vale(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    sessao.execute(
        insert(Extrato).values(
            empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id, mes=SETEMBRO,
            versao_da_regra=0, numeros={}, guardado_em=AGORA - timedelta(days=1),
        )
    )  # fmt: skip

    mes = extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA)

    assert (mes.versao_da_regra, mes.guardado_em) == (1, AGORA)


def test_o_mes_em_curso_e_parcial_e_nao_se_guarda(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    mes = extrato.do_mes(sessao, acesso_a, cenario.site_a.id, OUTUBRO, agora=AGORA)

    assert (mes.parcial, mes.ate, mes.guardado_em) == (True, AGORA, None)
    # 4 dias e 14 horas de 31 dias: a portaria é proporcional
    assert mes.economia is not None
    assert mes.economia.portaria == Decimal("3178.76")
    assert sessao.scalar(select(func.count()).select_from(Extrato)) == 0


def test_o_mes_que_nao_comecou_nao_tem_extrato(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    with pytest.raises(MesFuturoError):
        extrato.do_mes(sessao, acesso_a, cenario.site_a.id, date(2026, 11, 1), agora=AGORA)


def test_banco_recusa_mudar_um_extrato_guardado(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    extrato.do_mes(sessao, acesso_a, cenario.site_a.id, SETEMBRO, agora=AGORA)

    with pytest.raises(DBAPIError) as erro:
        sessao.execute(update(Extrato).values(versao_da_regra=2))

    assert sqlstate(erro.value) == SQLSTATE_SO_ACRESCENTA


# --- O painel ---------------------------------------------------------------------------------


def test_o_painel_traz_o_dia_o_mes_e_cada_dia(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, jornada: Jornada
) -> None:
    hoje_cedo = datetime(2026, 10, 5, 11, 0, tzinfo=UTC)  # 8h
    _completa(jornada, hoje_cedo)
    jornada(hoje_cedo + timedelta(hours=1))
    _completa(jornada, datetime(2026, 10, 2, 12, 0, tzinfo=UTC))

    painel = extrato.painel(sessao, acesso_a, cenario.site_a.id, agora=AGORA)

    assert (painel.hoje.visitas, painel.mes.medidas.visitas) == (2, 3)
    assert painel.hoje.horas_disponiveis == Decimal(16)  # das 6h às 14h, 2 docas
    assert [d.dia for d in painel.dias] == [date(2026, 10, dia) for dia in range(1, 6)]
    assert [d.medidas.visitas for d in painel.dias] == [0, 1, 0, 0, 2]

"""As contas do extrato (SDD 5.4 e D-48), sem banco: quem entra, as medidas e a economia em R$."""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from nuvem.extrato.contas import (
    Medidas,
    Parametros,
    VisitaMedida,
    economizar,
    horas_disponiveis,
    medir,
)

DE = datetime(2026, 9, 1, 3, 0, tzinfo=UTC)
"""Meia-noite de 01/09 em São Paulo."""
ATE = datetime(2026, 10, 1, 3, 0, tzinfo=UTC)
SP = ZoneInfo("America/Sao_Paulo")
PADRAO = Parametros()


def _visita(chegada: datetime = DE + timedelta(days=1), **horas: object) -> VisitaMedida:
    """Uma visita que chegou em ``chegada``; ``horas`` traz as outras, em ``timedelta`` dela."""
    valores: dict[str, object] = {}
    for campo, valor in horas.items():
        valores[campo] = chegada + valor if isinstance(valor, timedelta) else valor
    return VisitaMedida(chegou_em=chegada, **valores)  # type: ignore[arg-type]


def _medir(*visitas: VisitaMedida, disponiveis: Decimal = Decimal(0)) -> Medidas:
    return medir(visitas, de=DE, ate=ATE, parametros=PADRAO, horas_disponiveis=disponiveis)


# --- Quem entra no mês ------------------------------------------------------------------------


def test_entram_as_visitas_que_chegaram_no_periodo() -> None:
    medidas = _medir(
        _visita(DE - timedelta(seconds=1)),
        _visita(DE),
        _visita(ATE - timedelta(seconds=1)),
        _visita(ATE),
    )

    assert medidas.visitas == 2


def test_check_in_automatico_e_a_parte_feita_pelo_sistema() -> None:
    medidas = _medir(_visita(automatica=True), _visita(automatica=True), _visita(), _visita())

    assert (medidas.automaticas, medidas.pct_automatico) == (2, Decimal("50.0"))


def test_sem_visitas_nao_ha_porcentagens_nem_medias() -> None:
    medidas = _medir()

    assert (medidas.pct_automatico, medidas.espera_media, medidas.estadia_media) == (
        None, None, None,
    )  # fmt: skip
    assert (medidas.pct_acima_da_franquia, medidas.exposicao_por_liberada) == (None, None)
    assert medidas.uso_das_docas is None


# --- Espera e estadia -------------------------------------------------------------------------


def test_espera_media_das_visitas_chamadas() -> None:
    medidas = _medir(
        _visita(chamada_em=timedelta(hours=1)),
        _visita(chamada_em=timedelta(hours=3)),
        _visita(),  # ainda não chamada
    )

    assert (medidas.chamadas, medidas.espera_media) == (2, timedelta(hours=2))


def test_estadia_das_liberadas_e_acima_da_franquia() -> None:
    medidas = _medir(
        _visita(liberada_em=timedelta(hours=4)),
        _visita(liberada_em=timedelta(hours=5)),  # bem na franquia: não passa
        _visita(liberada_em=timedelta(hours=6), toneladas=Decimal(1)),
        _visita(saiu_em=timedelta(hours=9)),  # saiu sem passar pela doca: sem estadia
    )

    assert (medidas.liberadas, medidas.estadia_media) == (3, timedelta(hours=5))
    assert (medidas.acima_da_franquia, medidas.pct_acima_da_franquia) == (1, Decimal("33.3"))


# --- Exposição a estadia ----------------------------------------------------------------------


def test_exposicao_conta_o_que_passa_da_franquia_por_minuto() -> None:
    medidas = _medir(
        _visita(liberada_em=timedelta(hours=5, minutes=30), toneladas=Decimal("30")),
        _visita(liberada_em=timedelta(hours=5, seconds=59), toneladas=Decimal("30")),
        _visita(liberada_em=timedelta(hours=7, minutes=1), toneladas=Decimal("12.5")),
    )

    # 0,5 h * 30 t * R$ 2,50 + 0 + (121/60) h * 12,5 t * R$ 2,50
    assert medidas.exposicao == Decimal("100.52")
    assert medidas.exposicao_por_liberada == Decimal("33.51")


def test_exposicao_sem_toneladas_fica_fora_e_e_contada() -> None:
    medidas = _medir(
        _visita(liberada_em=timedelta(hours=6)),
        _visita(liberada_em=timedelta(hours=4)),  # dentro da franquia: não importa
    )

    assert (medidas.exposicao, medidas.sem_toneladas) == (Decimal("0.00"), 1)


def test_exposicao_usa_o_valor_e_a_franquia_do_site() -> None:
    parametros = Parametros(valor_da_estadia=Decimal("3.00"), franquia=timedelta(hours=4))
    visita = _visita(liberada_em=timedelta(hours=5), toneladas=Decimal("10"))

    medidas = medir([visita], de=DE, ate=ATE, parametros=parametros, horas_disponiveis=Decimal(0))

    assert (medidas.acima_da_franquia, medidas.exposicao) == (1, Decimal("30.00"))


# --- Uso das docas ----------------------------------------------------------------------------


def test_uso_das_docas_do_inicio_ao_fim_dentro_do_periodo() -> None:
    medidas = _medir(
        _visita(na_doca_em=timedelta(hours=1), liberada_em=timedelta(hours=3)),  # 2 h
        _visita(na_doca_em=timedelta(hours=1), saiu_em=timedelta(hours=2)),  # saiu da doca: 1 h
        # chegou antes do período: não é visita do mês, mas a doca foi usada 1 h dentro dele
        _visita(
            DE - timedelta(hours=3), na_doca_em=timedelta(hours=2), liberada_em=timedelta(hours=4)
        ),
        # ainda na doca no fim do período: conta até o fim
        _visita(ATE - timedelta(hours=2), na_doca_em=timedelta(hours=1)),
        disponiveis=Decimal(100),
    )

    assert medidas.horas_de_doca == Decimal("5.0")
    assert medidas.uso_das_docas == Decimal("5.0")


def test_horas_disponiveis_sem_horario_sao_24_horas_por_doca() -> None:
    assert horas_disponiveis(
        DE, DE + timedelta(days=2), fuso=SP, abre=None, fecha=None, docas=3
    ) == (Decimal(144))


def test_horas_disponiveis_pelo_horario_do_site() -> None:
    um_dia = horas_disponiveis(
        DE, DE + timedelta(days=1), fuso=SP, abre=time(6), fecha=time(22), docas=2
    )
    ate_as_14h = horas_disponiveis(
        DE, DE + timedelta(hours=14), fuso=SP, abre=time(6), fecha=time(22), docas=2
    )

    assert (um_dia, ate_as_14h) == (Decimal(32), Decimal(16))


def test_horas_disponiveis_com_o_horario_passando_da_meia_noite() -> None:
    assert horas_disponiveis(
        DE, DE + timedelta(days=1), fuso=SP, abre=time(22), fecha=time(6), docas=1
    ) == Decimal(8)


# --- A economia -------------------------------------------------------------------------------


def _medidas(**valores: object) -> Medidas:
    padrao: dict[str, object] = {
        "visitas": 100, "automaticas": 0, "chamadas": 100, "espera_total": timedelta(hours=300),
        "liberadas": 100, "estadia_total": timedelta(hours=400), "acima_da_franquia": 20,
        "exposicao": Decimal("4000.00"), "sem_toneladas": 0, "horas_de_doca": Decimal(500),
        "horas_disponiveis": Decimal(1000),
    }  # fmt: skip
    return Medidas(**(padrao | valores))  # type: ignore[arg-type]


def test_economia_da_estadia_por_visita_liberada() -> None:
    base = _medidas()  # R$ 40 por liberada
    mes = _medidas(liberadas=50, exposicao=Decimal("500.00"))  # R$ 10 por liberada

    economia = economizar(mes, base, PADRAO, fracao_do_mes=Decimal(1))

    assert economia.estadia == Decimal("1500.00")


def test_economia_da_estadia_sem_liberadas_na_base_nao_se_calcula() -> None:
    economia = economizar(_medidas(), _medidas(liberadas=0), PADRAO, fracao_do_mes=Decimal(1))

    assert economia.estadia is None


def test_mes_sem_liberadas_nao_economiza_estadia() -> None:
    mes = _medidas(liberadas=0, exposicao=Decimal(0))

    assert economizar(mes, _medidas(), PADRAO, fracao_do_mes=Decimal(1)).estadia == Decimal("0.00")


def test_economia_da_portaria_pelos_postos_e_proporcional_no_mes_parcial() -> None:
    parametros = Parametros(
        postos_antes=Decimal(3), postos_depois=Decimal(2), custo_mensal_do_posto=Decimal("21500")
    )

    inteiro = economizar(_medidas(), _medidas(), parametros, fracao_do_mes=Decimal(1))
    metade = economizar(_medidas(), _medidas(), parametros, fracao_do_mes=Decimal("0.5"))

    assert (inteiro.portaria, metade.portaria) == (Decimal("21500.00"), Decimal("10750.00"))


@pytest.mark.parametrize("faltando", ["postos_antes", "postos_depois", "custo_mensal_do_posto"])
def test_sem_os_numeros_da_portaria_ela_nao_entra(faltando: str) -> None:
    valores = {
        "postos_antes": Decimal(3), "postos_depois": Decimal(2),
        "custo_mensal_do_posto": Decimal("21500"),
    } | {faltando: None}  # fmt: skip
    parametros = Parametros(**valores)  # type: ignore[arg-type]

    assert economizar(_medidas(), _medidas(), parametros, fracao_do_mes=Decimal(1)).portaria is None


def test_economia_das_docas_so_com_o_custo_hora_doca() -> None:
    mes = _medidas(horas_de_doca=Decimal(600))  # 60% contra 50%
    com_custo = Parametros(custo_hora_doca=Decimal("100"))

    assert economizar(mes, _medidas(), com_custo, fracao_do_mes=Decimal(1)).docas == Decimal(
        "10000.00"
    )
    assert economizar(mes, _medidas(), PADRAO, fracao_do_mes=Decimal(1)).docas is None


def test_linha_de_base_sem_horas_de_doca_nao_da_economia_de_docas() -> None:
    base = _medidas(horas_de_doca=Decimal(0), horas_disponiveis=Decimal(0))

    economia = economizar(
        _medidas(), base, Parametros(custo_hora_doca=Decimal(100)), fracao_do_mes=Decimal(1)
    )

    assert economia.docas is None


def test_sem_chamadas_nao_ha_horas_de_espera_poupadas() -> None:
    sem_chamadas = _medidas(chamadas=0, espera_total=timedelta(0))

    assert (
        economizar(sem_chamadas, _medidas(), PADRAO, fracao_do_mes=Decimal(1)).horas_de_espera
        is None
    )
    assert (
        economizar(_medidas(), sem_chamadas, PADRAO, fracao_do_mes=Decimal(1)).horas_de_espera
        is None
    )


def test_horas_de_espera_poupadas() -> None:
    mes = _medidas(chamadas=50, espera_total=timedelta(hours=50))  # 1 h contra 3 h

    economia = economizar(mes, _medidas(), PADRAO, fracao_do_mes=Decimal(1))

    assert economia.horas_de_espera == Decimal("100.0")


def test_o_total_soma_o_que_tem_valor_em_reais() -> None:
    parametros = Parametros(
        postos_antes=Decimal(3), postos_depois=Decimal(2), custo_mensal_do_posto=Decimal("1000")
    )
    mes = _medidas(exposicao=Decimal("3000.00"))  # R$ 10 a menos por liberada

    economia = economizar(mes, _medidas(), parametros, fracao_do_mes=Decimal(1))

    assert (economia.estadia, economia.portaria, economia.docas) == (
        Decimal("1000.00"), Decimal("1000.00"), None,
    )  # fmt: skip
    assert economia.total == Decimal("2000.00")


def test_o_total_inclui_as_docas_quando_ha_custo() -> None:
    mes = _medidas(horas_de_doca=Decimal(600), exposicao=Decimal("3000.00"))

    economia = economizar(
        mes, _medidas(), Parametros(custo_hora_doca=Decimal(10)), fracao_do_mes=Decimal(1)
    )

    assert economia.total == Decimal("2000.00")  # R$ 1.000 da estadia + R$ 1.000 das docas


def test_meio_centavo_arredonda_para_cima() -> None:
    assert _medidas(liberadas=2, exposicao=Decimal("0.25")).exposicao_por_liberada == Decimal(
        "0.13"
    )


def test_as_medidas_vao_e_voltam_do_json() -> None:
    medidas = _medidas(exposicao=Decimal("123.45"), horas_de_doca=Decimal("10.5"))

    assert Medidas.de_json(medidas.para_json()) == medidas

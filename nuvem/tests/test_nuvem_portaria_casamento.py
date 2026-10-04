"""As regras puras do casamento (SDD 5.3, D-17, D-23, D-36 e D-37), sem banco."""

from datetime import UTC, datetime, timedelta

import pytest

from contratos.passagem import Papel, PlacaLida
from nuvem.portaria.casamento import (
    PESOS_INICIAIS,
    TOLERANCIA_PADRAO,
    CheckIn,
    Esperado,
    ParaExcecao,
    Pontuado,
    compor,
    decidir,
    escolher_saida,
    mesma_placa,
    pontuar,
    troca_facil,
)
from nuvem.portaria.visitas import PlacaNaVisita

INICIO = datetime(2026, 11, 5, 11, 0, tzinfo=UTC)
FIM = INICIO + timedelta(hours=2)
NA_JANELA = INICIO + timedelta(minutes=30)


def _lida(placa: str, papel: Papel = "cavalo") -> PlacaLida:
    return PlacaLida(placa=placa, papel=papel, confianca=0.9, camera_id="1", quadros=5)


def _esperado(
    cavalo: str = "ABC1D23", reboques: tuple[str, ...] = (), agendamento_id: int = 1
) -> Esperado:
    return Esperado(
        agendamento_id=agendamento_id,
        placa_cavalo=cavalo,
        placas_reboques=reboques,
        janela_inicio=INICIO,
        janela_fim=FIM,
    )


def _pontos(
    lidas: list[PlacaLida], esperado: Esperado, chegada: datetime = NA_JANELA
) -> int | None:
    pontuado = pontuar(lidas, esperado, chegada, pesos=PESOS_INICIAIS, tolerancia=TOLERANCIA_PADRAO)
    return None if pontuado is None else pontuado.pontos


# --- A mesma placa (D-36) e a troca fácil -----------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("ABC1D23", "ABC1D23"),
        ("ABC1234", "ABC1C34"),
        ("ABC1C34", "ABC1234"),
        ("ABC1034", "ABC1A34"),
    ],
)
def test_mesma_placa_inclui_a_antiga_e_a_mercosul_que_a_substituiu(a: str, b: str) -> None:
    assert mesma_placa(a, b)


@pytest.mark.parametrize(("a", "b"), [("ABC1234", "ABC1D34"), ("ABC1D23", "ABC1D24")])
def test_placas_diferentes(a: str, b: str) -> None:
    assert not mesma_placa(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        # A troca só aparece na 5ª posição, a única que aceita letra ou número.
        ("ABC1O23", "ABC1023"),  # O/0
        ("ABC1B23", "ABC1823"),  # B/8
        ("ABC1S23", "ABC1523"),  # S/5
        ("ABC1I23", "ABC1123"),  # I/1
    ],
)
def test_troca_facil_de_um_caractere(a: str, b: str) -> None:
    assert troca_facil(a, b)
    assert troca_facil(b, a)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("ABC1D23", "ABC1D23"),  # igual não é troca
        ("ABC1D23", "ABC1023"),  # D/0 não é troca fácil
        ("ABC1O23", "ABC1028"),  # duas diferenças
        ("ABC1D23", "XYZ9K87"),
    ],
)
def test_nao_e_troca_facil(a: str, b: str) -> None:
    assert not troca_facil(a, b)


def test_troca_facil_tambem_contra_a_forma_mercosul() -> None:
    # Agenda com a placa antiga ABC1235 (= Mercosul ABC1C35); a câmera leu ABC1C3S.
    assert troca_facil("ABC1C3S", "ABC1235")


# --- Pontos (SDD 5.3) -------------------------------------------------------------------------


def test_cavalo_identico_na_janela_faz_80() -> None:
    assert _pontos([_lida("ABC1D23")], _esperado()) == 80


def test_cavalo_com_troca_facil_faz_40_mais_a_janela() -> None:
    assert _pontos([_lida("ABC1B23")], _esperado("ABC1823")) == 60


def test_cada_reboque_identico_faz_20_ate_2() -> None:
    lidas = [_lida("ABC1D23"), _lida("DEF4G56", "reboque"), _lida("GHI7J89", "reboque"),
             _lida("JKL1M23", "reboque")]  # fmt: skip

    pontos = _pontos(lidas, _esperado(reboques=("DEF4G56", "GHI7J89", "JKL1M23")))

    assert pontos == 60 + 2 * 20 + 20


def test_chegada_na_tolerancia_faz_10_e_fora_dela_nao_e_candidato() -> None:
    esperado = _esperado()

    assert _pontos([_lida("ABC1D23")], esperado, INICIO - timedelta(hours=1)) == 70
    assert _pontos([_lida("ABC1D23")], esperado, FIM + timedelta(hours=4)) == 70
    assert _pontos([_lida("ABC1D23")], esperado, FIM + timedelta(hours=4, seconds=1)) is None
    assert _pontos([_lida("ABC1D23")], esperado, INICIO - timedelta(hours=4, seconds=1)) is None


def test_placa_lida_so_pela_traseira_vale_como_cavalo() -> None:
    # D-23: sem a frente, a traseira vem com papel desconhecido.
    assert _pontos([_lida("ABC1D23", "desconhecido")], _esperado()) == 80


def test_placa_desconhecida_vale_como_reboque() -> None:
    lidas = [_lida("ABC1D23"), _lida("DEF4G56", "desconhecido")]

    assert _pontos(lidas, _esperado(reboques=("DEF4G56",))) == 100


def test_a_mesma_placa_nao_conta_como_cavalo_e_reboque() -> None:
    # A agenda erra e põe a placa do cavalo também como reboque: conta uma vez só.
    esperado = _esperado(reboques=("ABC1D23",))

    assert _pontos([_lida("ABC1D23", "desconhecido")], esperado) == 80


def test_placa_lida_como_reboque_nao_conta_como_cavalo() -> None:
    lidas = [_lida("XYZ9K87"), _lida("ABC1D23", "reboque")]

    assert _pontos(lidas, _esperado()) == 20


def test_cavalo_lido_pela_frente_e_pela_traseira_com_a_agenda_repetindo_o_cavalo() -> None:
    # Cavalo sem reboque: as duas câmeras leem a mesma placa; a agenda a repete como reboque.
    lidas = [_lida("ABC1D23"), _lida("ABC1D23", "desconhecido")]

    assert _pontos(lidas, _esperado(reboques=("ABC1D23",))) == 80


def test_placa_lida_como_cavalo_nao_conta_como_reboque() -> None:
    lidas = [_lida("XYZ9K87"), _lida("DEF4G56", "cavalo")]

    assert _pontos(lidas, _esperado(reboques=("DEF4G56",))) == 20


def test_reboque_trocado_fica_so_com_o_cavalo() -> None:
    lidas = [_lida("ABC1D23"), _lida("XYZ9K87", "reboque")]

    assert _pontos(lidas, _esperado(reboques=("DEF4G56",))) == 80


# --- A decisão --------------------------------------------------------------------------------


def _p(agendamento_id: int, pontos: int, placas: int | None = None) -> Pontuado:
    return Pontuado(
        agendamento_id=agendamento_id,
        pontos=pontos,
        pontos_de_placa=pontos - 20 if placas is None else placas,
    )


def test_check_in_com_80_e_20_a_frente() -> None:
    decisao = decidir([_lida("ABC1D23")], [_p(2, 60), _p(1, 80)], PESOS_INICIAIS)

    assert decisao == CheckIn(escolhido=_p(1, 80), segundo=_p(2, 60))


def test_check_in_sozinho() -> None:
    assert decidir([_lida("ABC1D23")], [_p(1, 80)], PESOS_INICIAIS) == CheckIn(
        escolhido=_p(1, 80), segundo=None
    )


def test_dois_candidatos_proximos_viram_excecao() -> None:
    decisao = decidir([_lida("ABC1D23")], [_p(1, 80), _p(2, 70)], PESOS_INICIAIS)

    assert decisao == ParaExcecao(motivo="candidatos_proximos", candidatos=(_p(1, 80), _p(2, 70)))


def test_abaixo_de_80_vira_excecao_com_pontos_baixos() -> None:
    decisao = decidir([_lida("ABC1B23")], [_p(1, 60)], PESOS_INICIAIS)

    assert decisao == ParaExcecao(motivo="pontos_baixos", candidatos=(_p(1, 60),))


def test_so_a_janela_nao_e_candidato() -> None:
    decisao = decidir([_lida("XYZ9K87")], [_p(1, 20, placas=0)], PESOS_INICIAIS)

    assert decisao == ParaExcecao(motivo="sem_candidato", candidatos=())


def test_passagem_sem_placa_vira_excecao_sem_placa() -> None:
    assert decidir([], [_p(1, 80)], PESOS_INICIAIS) == ParaExcecao(
        motivo="sem_placa", candidatos=()
    )


def test_a_excecao_lista_no_maximo_5_candidatos_do_maior_ao_menor() -> None:
    pontuados = [_p(n, 40 + n) for n in range(1, 8)]

    decisao = decidir([_lida("ABC1D23")], pontuados, PESOS_INICIAIS)

    assert isinstance(decisao, ParaExcecao)
    assert [c.agendamento_id for c in decisao.candidatos] == [7, 6, 5, 4, 3]


def test_empate_decide_pelo_agendamento_mais_antigo() -> None:
    decisao = decidir([_lida("ABC1D23")], [_p(9, 80), _p(3, 80)], PESOS_INICIAIS)

    assert isinstance(decisao, ParaExcecao)
    assert [c.agendamento_id for c in decisao.candidatos] == [3, 9]


# --- A composição da visita (D-17) ------------------------------------------------------------


def _na_visita(placa: str, papel: Papel, como: str) -> PlacaNaVisita:
    return PlacaNaVisita.model_validate({"placa": placa, "papel": papel, "como": como})


def test_reboque_que_a_camera_nao_viu_entra_inferido() -> None:
    composicao = compor([_lida("ABC1D23")], _esperado(reboques=("DEF4G56", "GHI7J89")))

    assert composicao == (
        _na_visita("ABC1D23", "cavalo", "lida"),
        _na_visita("DEF4G56", "reboque", "inferida"),
        _na_visita("GHI7J89", "reboque", "inferida"),
    )


def test_reboque_visto_entra_lido_com_a_placa_que_a_camera_leu() -> None:
    # A agenda tem a antiga (DEF4656); o reboque tem a Mercosul que a substituiu (D-36).
    lidas = [_lida("ABC1D23"), _lida("DEF4G56", "desconhecido")]

    composicao = compor(lidas, _esperado(reboques=("DEF4656",)))

    assert composicao == (
        _na_visita("ABC1D23", "cavalo", "lida"),
        _na_visita("DEF4G56", "reboque", "lida"),
    )


def test_cavalo_lido_com_troca_facil_fica_com_a_placa_da_agenda() -> None:
    composicao = compor([_lida("ABC1B23")], _esperado("ABC1823"))

    assert composicao == (_na_visita("ABC1823", "cavalo", "lida"),)


def test_reboque_trocado_entra_lido_e_os_da_agenda_nao_sao_inferidos() -> None:
    lidas = [_lida("ABC1D23"), _lida("XYZ9K87", "reboque")]

    composicao = compor(lidas, _esperado(reboques=("DEF4G56",)))

    assert composicao == (
        _na_visita("ABC1D23", "cavalo", "lida"),
        _na_visita("XYZ9K87", "reboque", "lida"),
    )


# --- A saída (D-37) ---------------------------------------------------------------------------


def test_saida_pela_placa_do_ultimo_reboque() -> None:
    abertas = [
        (1, ("ABC1D23", "DEF4G56"), INICIO),
        (2, ("XYZ9K87",), INICIO),
    ]

    assert escolher_saida([_lida("DEF4G56", "desconhecido")], abertas) == 1


def test_saida_com_a_placa_em_duas_visitas_fecha_a_mais_recente() -> None:
    abertas = [(1, ("ABC1D23",), INICIO), (2, ("ABC1D23",), INICIO + timedelta(hours=3))]

    assert escolher_saida([_lida("ABC1D23", "desconhecido")], abertas) == 2


def test_saida_pela_forma_mercosul() -> None:
    assert escolher_saida([_lida("ABC1C34", "desconhecido")], [(5, ("ABC1234",), INICIO)]) == 5


def test_saida_sem_visita_aberta() -> None:
    assert escolher_saida([_lida("XYZ9K87", "desconhecido")], [(1, ("ABC1D23",), INICIO)]) is None
    assert escolher_saida([], [(1, ("ABC1D23",), INICIO)]) is None

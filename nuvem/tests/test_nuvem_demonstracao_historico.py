"""Os dias inventados da demonstração (T45, D-49), sem banco: chegadas, docas e ritmos."""

import random
import re
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise
from zoneinfo import ZoneInfo

from nuvem.demonstracao import historico
from nuvem.demonstracao.historico import ANTES, COM_O_SISTEMA, Jornada, Ritmo

SP = ZoneInfo("America/Sao_Paulo")
DIA = date(2026, 9, 10)


def _dia(ritmo: Ritmo = COM_O_SISTEMA, semente: int = 7, caminhoes: int = 60) -> list[Jornada]:
    return historico.jornadas_do_dia(
        DIA, fuso=SP, docas=6, caminhoes=caminhoes, ritmo=ritmo, gerador=random.Random(semente),
        placas_usadas=set(),
    )  # fmt: skip


def test_as_chegadas_sao_do_dia_entre_6h_e_19h_em_ordem() -> None:
    jornadas = _dia()

    assert len(jornadas) == 60
    locais = [j.chegada.astimezone(SP) for j in jornadas]
    assert all(c.date() == DIA and 6 <= c.hour < 19 for c in locais)
    assert locais == sorted(locais)


def test_cada_doca_tem_um_caminhao_por_vez() -> None:
    por_doca: dict[int, list[Jornada]] = {}
    for jornada in _dia():
        por_doca.setdefault(jornada.doca, []).append(jornada)

    assert set(por_doca) <= set(range(6))
    for jornadas in por_doca.values():
        jornadas.sort(key=lambda j: j.chamada)
        for antes, depois in pairwise(jornadas):
            assert depois.chamada >= antes.fim + COM_O_SISTEMA.giro


def test_as_horas_vem_em_ordem() -> None:
    for j in _dia():
        assert j.chegada + COM_O_SISTEMA.reacao_minima <= j.chamada < j.inicio < j.fim < j.saida
        assert j.janela_fim - j.janela_inicio == timedelta(hours=2)


def test_as_placas_sao_mercosul_e_unicas() -> None:
    usadas: set[str] = set()
    primeiro = historico.jornadas_do_dia(
        DIA, fuso=SP, docas=6, caminhoes=60, ritmo=COM_O_SISTEMA, gerador=random.Random(1),
        placas_usadas=usadas,
    )  # fmt: skip
    segundo = historico.jornadas_do_dia(
        DIA + timedelta(days=1), fuso=SP, docas=6, caminhoes=60, ritmo=COM_O_SISTEMA,
        gerador=random.Random(1), placas_usadas=usadas,
    )  # fmt: skip

    placas = [j.placa for j in primeiro + segundo]
    assert len(set(placas)) == len(placas) == len(usadas)
    assert all(re.fullmatch(r"[A-Z]{3}[0-9][A-Z][0-9]{2}", p) for p in placas)


def test_a_mesma_semente_da_o_mesmo_dia() -> None:
    assert _dia(semente=3) == _dia(semente=3)
    assert _dia(semente=3) != _dia(semente=4)


def test_antes_do_sistema_a_espera_e_maior_e_nada_e_automatico() -> None:
    def espera_media(jornadas: list[Jornada]) -> timedelta:
        return sum((j.chamada - j.chegada for j in jornadas), timedelta(0)) / len(jornadas)

    com, sem = _dia(COM_O_SISTEMA), _dia(ANTES)

    assert espera_media(sem) > espera_media(com) + timedelta(minutes=30)
    assert not any(j.automatica for j in sem)
    assert sum(j.automatica for j in com) > len(com) * 0.8


def test_as_toneladas_ficam_entre_8_e_32_ou_faltam() -> None:
    toneladas = [j.toneladas for j in _dia(caminhoes=200)]

    assert all(t is None or Decimal(8) <= t <= Decimal(32) for t in toneladas)
    assert any(t is None for t in toneladas)

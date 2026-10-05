"""O painel do gestor e o extrato na tela (T44, SDD 6.2 e D-48)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from nuvem.cadastro.acesso import acesso_do_usuario
from nuvem.cadastro.modelos import Doca
from nuvem.extrato.modelos import Extrato, LinhaDeBase, ParametrosSite
from nuvem.patio import servico as patio
from nuvem.portaria import visitas
from nuvem.portaria.modelos import Visita
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
"""14h de 05/10 em São Paulo."""


@pytest.fixture(autouse=True)
def _hora_fixa(app: FastAPI) -> None:
    app.dependency_overrides[agora] = lambda: AGORA


def _chegar(sessao: Session, cenario: Demonstracao, momento: datetime, placa: str) -> None:
    site = SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id)
    visitas.abrir_visita(
        sessao, site, "aceita_sem_agendamento", momento=momento, agora=momento,
        composicao=(PlacaNaVisita(placa=placa, papel="cavalo", como="lida"),),
    )  # fmt: skip


# --- Quem vê ----------------------------------------------------------------------------------


def test_sem_login_vai_para_a_tela_de_entrar(app: FastAPI) -> None:
    for caminho in ("/painel", "/extrato"):
        resposta = TestClient(app).get(caminho, follow_redirects=False)
        assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


def test_so_o_gestor_ve_o_painel_e_o_extrato(entrar: Entrar, cenario: Demonstracao) -> None:
    for pessoa in (cenario.porteiro_a, cenario.patio_a):
        cliente = entrar(pessoa.email)
        for caminho in ("/painel", "/extrato", "/extrato.csv"):
            assert cliente.get(caminho).status_code == 403


def test_o_inicio_do_gestor_leva_ao_painel(entrar: Entrar, cenario: Demonstracao) -> None:
    assert 'href="/painel"' in entrar(cenario.gestor_a.email).get("/").text
    assert 'href="/painel"' not in entrar(cenario.porteiro_a.email).get("/").text


def test_site_de_outra_empresa_responde_404(entrar: Entrar, cenario: Demonstracao) -> None:
    gestor = entrar(cenario.gestor_a.email)

    for caminho in ("/painel", "/extrato", "/extrato.csv"):
        assert gestor.get(f"{caminho}?site={cenario.site_b.id}").status_code == 404


# --- O painel ---------------------------------------------------------------------------------


def test_o_painel_mostra_hoje_o_mes_e_cada_dia(
    sessao: Session, entrar: Entrar, cenario: Demonstracao
) -> None:
    _chegar(sessao, cenario, datetime(2026, 10, 5, 11, tzinfo=UTC), "ABC1D23")
    _chegar(sessao, cenario, datetime(2026, 10, 5, 12, tzinfo=UTC), "BRA2E19")
    _chegar(sessao, cenario, datetime(2026, 10, 2, 12, tzinfo=UTC), "CCC3C33")

    texto = entrar(cenario.gestor_a.email).get("/painel").text

    assert "Hoje" in texto and "Outubro até agora" in texto
    assert 'title="05/10: 2 chegadas"' in texto
    assert 'title="02/10: 1 chegada"' in texto
    assert 'title="01/10: 0 chegadas"' in texto
    assert 'href="/extrato?site=' in texto


def test_o_painel_compara_com_a_linha_de_base_de_exemplo(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    texto = entrar(cenario.gestor_a.email).get("/painel").text

    assert "Linha de base de exemplo" in texto
    assert "2h40" in texto  # a espera média da linha de base


# --- O extrato --------------------------------------------------------------------------------


def test_o_extrato_do_mes_fechado_em_reais(entrar: Entrar, cenario: Demonstracao) -> None:
    texto = entrar(cenario.gestor_a.email).get("/extrato?mes=2026-09").text

    assert "Extrato de setembro de 2026" in texto
    assert "R$ 21.500,00" in texto  # um posto de portaria a menos
    assert "Linha de base de exemplo" in texto
    assert "versão 1 da regra" in texto
    assert "parcial" not in texto


def test_o_extrato_do_mes_fechado_fica_guardado(
    sessao: Session, entrar: Entrar, cenario: Demonstracao
) -> None:
    entrar(cenario.gestor_a.email).get("/extrato?mes=2026-09")

    assert sessao.scalar(select(func.count()).select_from(Extrato)) == 1


def test_economia_negativa_aparece_com_o_sinal(
    sessao: Session, entrar: Entrar, cenario: Demonstracao
) -> None:
    sessao.execute(update(ParametrosSite).values(postos_depois=Decimal(4)))  # um posto a mais

    assert "-R$ 21.500,00" in entrar(cenario.gestor_a.email).get("/extrato?mes=2026-09").text


def test_o_mes_de_agora_e_o_do_fuso_do_site(
    app: FastAPI, entrar: Entrar, cenario: Demonstracao
) -> None:
    # 01/11 à 1h em Brasília ainda é 31/10 às 22h em São Paulo.
    app.dependency_overrides[agora] = lambda: datetime(2026, 11, 1, 1, 0, tzinfo=UTC)

    assert "Extrato de outubro de 2026" in entrar(cenario.gestor_a.email).get("/extrato").text


def test_porcentagem_com_uma_casa_e_espera_a_mais(
    sessao: Session, entrar: Entrar, cenario: Demonstracao
) -> None:
    chegada = datetime(2026, 9, 10, 12, tzinfo=UTC)
    _chegar(sessao, cenario, chegada, "ABC1D23")
    visita = sessao.scalars(select(Visita).where(Visita.chegou_em == chegada)).one()
    doca = sessao.scalars(select(Doca).where(Doca.site_id == cenario.site_a.id)).first()
    assert doca is not None
    gestor = acesso_do_usuario(sessao, cenario.gestor_a.id)
    patio.chamar(sessao, gestor, visita.id, doca.id, agora=chegada + timedelta(hours=4))

    texto = entrar(cenario.gestor_a.email).get("/extrato?mes=2026-09").text

    assert "58,0%" in texto  # o uso das docas da linha de base
    assert "1,3 h a mais" in texto  # 4h de espera contra 2h40


def test_o_extrato_do_mes_em_curso_e_parcial(entrar: Entrar, cenario: Demonstracao) -> None:
    texto = entrar(cenario.gestor_a.email).get("/extrato").text

    assert "Extrato de outubro de 2026" in texto
    assert "parcial, até 05/10 às 14:00" in texto


def test_o_extrato_sem_linha_de_base_avisa(
    sessao: Session, entrar: Entrar, cenario: Demonstracao
) -> None:
    sessao.execute(delete(LinhaDeBase))

    texto = entrar(cenario.gestor_a.email).get("/extrato?mes=2026-09").text

    assert "Sem linha de base" in texto
    assert "R$ 21.500,00" not in texto


def test_o_extrato_leva_aos_meses_vizinhos(entrar: Entrar, cenario: Demonstracao) -> None:
    texto = entrar(cenario.gestor_a.email).get("/extrato?mes=2026-09").text

    assert "mes=2026-08" in texto and "mes=2026-10" in texto


def test_o_mes_em_curso_nao_leva_ao_seguinte(entrar: Entrar, cenario: Demonstracao) -> None:
    assert "mes=2026-11" not in entrar(cenario.gestor_a.email).get("/extrato").text


def test_mes_escrito_errado_responde_422(entrar: Entrar, cenario: Demonstracao) -> None:
    assert entrar(cenario.gestor_a.email).get("/extrato?mes=setembro").status_code == 422


def test_mes_que_nao_comecou_responde_404(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.gestor_a.email).get("/extrato?mes=2026-11")

    assert resposta.status_code == 404
    assert "ainda não começou" in resposta.text


# --- A planilha -------------------------------------------------------------------------------


def test_a_planilha_do_extrato(sessao: Session, entrar: Entrar, cenario: Demonstracao) -> None:
    _chegar(sessao, cenario, datetime(2026, 9, 10, 12, tzinfo=UTC), "ABC1D23")

    resposta = entrar(cenario.gestor_a.email).get("/extrato.csv?mes=2026-09")

    assert resposta.headers["content-type"].startswith("text/csv")
    assert "extrato-2026-09.csv" in resposta.headers["content-disposition"]
    linhas = resposta.content.decode("utf-8-sig").splitlines()
    assert linhas[0] == "Medida;Linha de base;Mês"
    assert "Visitas;682;1" in linhas
    assert "Economia com a portaria (R$);;21500,00" in linhas


def test_a_planilha_diz_quando_e_parcial(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.gestor_a.email).get("/extrato.csv")

    assert "Parcial até;;05/10/2026 14:00" in resposta.content.decode("utf-8-sig").splitlines()


def test_o_mes_fechado_nao_muda_com_o_que_chega_depois(
    sessao: Session, entrar: Entrar, cenario: Demonstracao
) -> None:
    gestor = entrar(cenario.gestor_a.email)
    antes = gestor.get("/extrato.csv?mes=2026-09").content

    _chegar(sessao, cenario, datetime(2026, 9, 10, 12, tzinfo=UTC), "ABC1D23")

    assert gestor.get("/extrato.csv?mes=2026-09").content == antes

"""Resolver a exceção e registrar a chegada à mão pela tela da portaria (T41, SDD 5.2 e D-46)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.portaria.casamento import processar_passagem
from nuvem.portaria.modelos import Excecao, Visita
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]
Registrar = Callable[..., Passagem]
Agendar = Callable[..., Agendamento]

AGORA = datetime(2026, 10, 5, 17, 5, tzinfo=UTC)
"""14:05 em São Paulo; a passagem da fixture é das 14:02."""
CEDO = datetime(2026, 10, 5, 16, tzinfo=UTC)
TARDE = datetime(2026, 10, 5, 18, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _hora_fixa(app: FastAPI) -> None:
    app.dependency_overrides[agora] = lambda: AGORA


@pytest.fixture
def agendar(sessao: Session, cenario: Demonstracao) -> Agendar:
    def _agendar(codigo: str, inicio: datetime) -> Agendamento:
        destino = SiteDoAgendamento(
            empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id, usuario_id=None
        )
        dados = DadosDoAgendamento(
            codigo_externo=codigo, janela_inicio=inicio, janela_fim=inicio + timedelta(hours=2),
            tipo="descarga", placa_cavalo="ABC1D23",
        )  # fmt: skip
        return agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento

    return _agendar


@pytest.fixture
def excecao_de(sessao: Session, registrar_passagem: Registrar) -> Callable[..., Excecao]:
    def _excecao(**mudancas: object) -> Excecao:
        passagem = registrar_passagem(**mudancas)
        assert processar_passagem(sessao, passagem.id, agora=AGORA).resultado == "excecao"
        return sessao.scalars(select(Excecao).where(Excecao.passagem_id == passagem.id)).one()

    return _excecao


def _visita(sessao: Session, excecao: Excecao) -> Visita:
    sessao.expire_all()
    return sessao.get_one(Visita, excecao.visita_id)


# --- Quem resolve -----------------------------------------------------------------------------


def test_sem_login_vai_para_a_tela_de_entrar(
    app: FastAPI, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de()

    resposta = TestClient(app).get(f"/portaria/excecoes/{excecao.id}", follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


def test_o_lider_de_patio_nao_resolve(
    entrar: Entrar, cenario: Demonstracao, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de()
    patio = entrar(cenario.patio_a.email)

    assert patio.get(f"/portaria/excecoes/{excecao.id}").status_code == 403
    assert patio.post(f"/portaria/excecoes/{excecao.id}/recusar").status_code == 403


def test_excecao_de_outra_empresa_responde_404(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de()
    de_fora = entrar(cenario.porteiro_b.email)

    assert de_fora.get(f"/portaria/excecoes/{excecao.id}").status_code == 404
    assert de_fora.post(f"/portaria/excecoes/{excecao.id}/recusar").status_code == 404
    assert _visita(sessao, excecao).estado == "EXCECAO"


# --- A página da exceção ----------------------------------------------------------------------


def test_o_cartao_da_excecao_leva_a_pagina_de_resolver(
    entrar: Entrar, cenario: Demonstracao, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de()

    lista = entrar(cenario.porteiro_a.email).get(f"/portaria/excecoes?site={cenario.site_a.id}")

    assert f'href="/portaria/excecoes/{excecao.id}"' in lista.text


def test_a_pagina_mostra_as_opcoes_pelos_pontos(
    entrar: Entrar,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    agendar("TARDE", TARDE)
    agendar("CEDO", CEDO)
    excecao = excecao_de()

    texto = entrar(cenario.porteiro_a.email).get(f"/portaria/excecoes/{excecao.id}").text

    assert texto.index("CEDO") < texto.index("TARDE")
    assert "80 pontos" in texto and "70 pontos" in texto
    assert "mais de um agendamento possível" in texto
    assert f'src="/portaria/fotos/{excecao.passagem_id}/0"' in texto


def test_e_este_pela_tela(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    cedo = agendar("CEDO", CEDO)
    agendar("TARDE", TARDE)
    excecao = excecao_de()

    resposta = entrar(cenario.porteiro_a.email).post(
        f"/portaria/excecoes/{excecao.id}/agendamento",
        data={"agendamento_id": str(cedo.id)},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == f"/portaria?site={cenario.site_a.id}"
    visita = _visita(sessao, excecao)
    assert (visita.estado, visita.agendamento_id) == ("NA_FILA", cedo.id)


def test_aceitar_sem_agendamento_pela_tela(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de()

    entrar(cenario.porteiro_a.email).post(f"/portaria/excecoes/{excecao.id}/sem-agendamento")

    assert _visita(sessao, excecao).estado == "NA_FILA"


def test_recusar_pela_tela(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de()

    entrar(cenario.porteiro_a.email).post(f"/portaria/excecoes/{excecao.id}/recusar")

    assert _visita(sessao, excecao).estado == "RECUSADA"


def test_excecao_ja_resolvida_avisa_e_mostra_como_ficou(
    entrar: Entrar, cenario: Demonstracao, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de()
    porteiro = entrar(cenario.porteiro_a.email)
    porteiro.post(f"/portaria/excecoes/{excecao.id}/sem-agendamento")

    resposta = porteiro.post(f"/portaria/excecoes/{excecao.id}/recusar")

    assert resposta.status_code == 409
    assert "Esta exceção já foi resolvida" in resposta.text
    assert "aceita sem agendamento" in resposta.text


def test_agendamento_indisponivel_avisa(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    excecao = excecao_de()
    amanha = agendar("AMANHA", CEDO + timedelta(days=1))

    resposta = entrar(cenario.porteiro_a.email).post(
        f"/portaria/excecoes/{excecao.id}/agendamento", data={"agendamento_id": str(amanha.id)}
    )

    assert resposta.status_code == 409
    assert "Esse agendamento não está disponível" in resposta.text
    assert _visita(sessao, excecao).estado == "EXCECAO"


# --- Corrigir a placa numa exceção ------------------------------------------------------------


def test_corrigir_a_placa_pela_tela_casa_de_novo(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    agendamento = agendar("AG-1", CEDO)
    camera = str(cenario.camera_a.id)
    lida = {"placa": "ABC1D28", "papel": "cavalo", "confianca": 0.9, "camera_id": camera,
            "quadros": 4}  # fmt: skip
    excecao = excecao_de(placas=[lida])
    porteiro = entrar(cenario.porteiro_a.email)

    resposta = porteiro.post(
        f"/portaria/excecoes/{excecao.id}/conferir",
        data={"foto": "0", "placa": "ABC1D23"},
        follow_redirects=False,
    )

    assert resposta.headers["location"] == f"/portaria/excecoes/{excecao.id}"
    assert _visita(sessao, excecao).agendamento_id == agendamento.id
    pagina = porteiro.get(resposta.headers["location"]).text
    assert "Resolvida às 14:05: placa corrigida, ligada ao agendamento AG-1" in pagina


def test_digitar_o_cavalo_quando_nao_ha_foto(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    agendamento = agendar("AG-1", CEDO)
    excecao = excecao_de(placas=[], fotos=[])
    porteiro = entrar(cenario.porteiro_a.email)
    assert "Placa do cavalo" in porteiro.get(f"/portaria/excecoes/{excecao.id}").text

    porteiro.post(f"/portaria/excecoes/{excecao.id}/cavalo", data={"placa": "abc-1d23"})

    assert _visita(sessao, excecao).agendamento_id == agendamento.id


def test_placa_fora_do_formato_na_excecao_mostra_o_motivo(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, excecao_de: Callable[..., Excecao]
) -> None:
    excecao = excecao_de(placas=[], fotos=[])

    resposta = entrar(cenario.porteiro_a.email).post(
        f"/portaria/excecoes/{excecao.id}/cavalo", data={"placa": "AB12"}
    )

    assert resposta.status_code == 422
    assert "não está no formato antigo (ABC1234) nem no Mercosul (ABC1D23)" in resposta.text
    assert _visita(sessao, excecao).estado == "EXCECAO"


def test_conferir_pela_pagina_de_conferencia_numa_excecao_tambem_casa_de_novo(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    agendar: Agendar,
    excecao_de: Callable[..., Excecao],
) -> None:
    agendamento = agendar("AG-1", CEDO)
    camera = str(cenario.camera_a.id)
    lida = {"placa": "ABC1D28", "papel": "cavalo", "confianca": 0.9, "camera_id": camera,
            "quadros": 4}  # fmt: skip
    excecao = excecao_de(placas=[lida])

    entrar(cenario.porteiro_a.email).post(
        f"/portaria/conferir/{excecao.passagem_id}", data={"foto": "0", "placa": "ABC1D23"}
    )

    assert _visita(sessao, excecao).agendamento_id == agendamento.id


# --- Chegada manual ---------------------------------------------------------------------------


def test_a_portaria_leva_a_chegada_manual(entrar: Entrar, cenario: Demonstracao) -> None:
    tela = entrar(cenario.porteiro_a.email).get(f"/portaria?site={cenario.site_a.id}").text

    assert f'href="/portaria/chegada-manual?site={cenario.site_a.id}"' in tela


def test_chegada_manual_sugere_os_agendamentos(
    entrar: Entrar, cenario: Demonstracao, agendar: Agendar
) -> None:
    agendar("TARDE", TARDE)
    agendar("CEDO", CEDO)

    texto = (
        entrar(cenario.porteiro_a.email)
        .get(f"/portaria/chegada-manual?site={cenario.site_a.id}&cavalo=abc1d23")
        .text
    )

    assert texto.index("CEDO") < texto.index("TARDE")
    assert 'name="agendamento_id"' in texto


def test_chegada_manual_com_agendamento_pela_tela(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, agendar: Agendar
) -> None:
    agendamento = agendar("AG-1", CEDO)

    resposta = entrar(cenario.porteiro_a.email).post(
        f"/portaria/chegada-manual?site={cenario.site_a.id}",
        data={"cavalo": "ABC1D23", "reboques": "", "agendamento_id": str(agendamento.id)},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == f"/portaria?site={cenario.site_a.id}"
    visita = sessao.scalars(select(Visita)).one()
    assert (visita.estado, visita.agendamento_id) == ("NA_FILA", agendamento.id)


def test_chegada_manual_sem_agendamento_pela_tela(
    sessao: Session, entrar: Entrar, cenario: Demonstracao
) -> None:
    entrar(cenario.porteiro_a.email).post(
        f"/portaria/chegada-manual?site={cenario.site_a.id}",
        data={"cavalo": "ABC1D23", "reboques": "DEF4G56 XYZ9876", "agendamento_id": ""},
    )

    visita = sessao.scalars(select(Visita)).one()
    assert visita.agendamento_id is None
    assert [p["placa"] for p in visita.composicao] == ["ABC1D23", "DEF4G56", "XYZ9876"]


def test_chegada_manual_com_placa_fora_do_formato_mostra_o_motivo(
    sessao: Session, entrar: Entrar, cenario: Demonstracao
) -> None:
    resposta = entrar(cenario.porteiro_a.email).post(
        f"/portaria/chegada-manual?site={cenario.site_a.id}",
        data={"cavalo": "AB12", "reboques": "", "agendamento_id": ""},
    )

    assert resposta.status_code == 422
    assert "não está no formato antigo (ABC1234) nem no Mercosul (ABC1D23)" in resposta.text
    assert sessao.scalars(select(Visita)).all() == []

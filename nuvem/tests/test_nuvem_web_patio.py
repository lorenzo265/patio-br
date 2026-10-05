"""A tela do pátio e das docas (T42, SDD 6.2): o líder vê a fila e as docas e move os caminhões."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem.cadastro.modelos import Doca
from nuvem.portaria import visitas
from nuvem.portaria.modelos import Visita
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]
Chegar = Callable[..., Visita]

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
"""14h em São Paulo."""


@pytest.fixture(autouse=True)
def _hora_fixa(app: FastAPI) -> None:
    app.dependency_overrides[agora] = lambda: AGORA


@pytest.fixture
def docas(sessao: Session, cenario: Demonstracao) -> list[Doca]:
    return list(
        sessao.scalars(select(Doca).where(Doca.site_id == cenario.site_a.id).order_by(Doca.nome))
    )


@pytest.fixture
def chegar(sessao: Session, cenario: Demonstracao) -> Chegar:
    site = SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id)

    def _chegar(placa: str, ha: timedelta) -> Visita:
        return visitas.abrir_visita(
            sessao, site, "aceita_sem_agendamento", momento=AGORA - ha, agora=AGORA - ha,
            composicao=(PlacaNaVisita(placa=placa, papel="cavalo", como="lida"),),
        )  # fmt: skip

    return _chegar


def _estado(sessao: Session, visita: Visita) -> str:
    sessao.expire_all()
    return sessao.get_one(Visita, visita.id).estado


def _quadro(cliente: TestClient, cenario: Demonstracao) -> str:
    resposta = cliente.get(f"/patio/quadro?site={cenario.site_a.id}")
    assert resposta.status_code == 200, resposta.text
    return resposta.text


# --- Quem vê ----------------------------------------------------------------------------------


def test_sem_login_vai_para_a_tela_de_entrar(app: FastAPI) -> None:
    resposta = TestClient(app).get("/patio", follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


def test_o_porteiro_nao_ve_o_patio(entrar: Entrar, cenario: Demonstracao) -> None:
    assert entrar(cenario.porteiro_a.email).get("/patio").status_code == 403


def test_o_lider_e_o_gestor_veem_o_patio_que_se_atualiza(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    for pessoa in (cenario.patio_a, cenario.gestor_a):
        tela = entrar(pessoa.email).get("/patio").text
        assert f'hx-get="/patio/quadro?site={cenario.site_a.id}"' in tela


def test_o_inicio_do_lider_leva_ao_patio(entrar: Entrar, cenario: Demonstracao) -> None:
    assert 'href="/patio"' in entrar(cenario.patio_a.email).get("/").text


def test_site_de_outra_empresa_responde_404(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.patio_a.email).get(f"/patio/quadro?site={cenario.site_b.id}")

    assert resposta.status_code == 404


# --- O quadro ---------------------------------------------------------------------------------


def test_quadro_mostra_a_fila_com_o_tempo_e_o_alerta(
    entrar: Entrar, cenario: Demonstracao, chegar: Chegar
) -> None:
    chegar("XYZ9876", timedelta(hours=5, minutes=30))
    chegar("ABC1D23", timedelta(hours=4, minutes=10))
    chegar("BRA2E19", timedelta(minutes=35))

    texto = _quadro(entrar(cenario.patio_a.email), cenario)

    assert texto.index("XYZ9876") < texto.index("ABC1D23") < texto.index("BRA2E19")
    assert "5h30" in texto and "4h10" in texto and "0h35" in texto
    assert texto.count("passou das 5 horas") == 1
    assert texto.count("perto das 5 horas") == 1


def test_quadro_mostra_as_docas(
    entrar: Entrar, cenario: Demonstracao, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(minutes=30))
    lider = entrar(cenario.patio_a.email)
    lider.post(f"/patio/visitas/{visita.id}/chamar", data={"doca_id": str(docas[0].id)})

    texto = _quadro(lider, cenario)

    doca_1 = texto[texto.index("Doca 1") : texto.index("Doca 2")]
    assert "ABC1D23" in doca_1 and "chamado" in doca_1
    assert "livre" in texto[texto.index("Doca 2") :]


# --- Mover os caminhões -----------------------------------------------------------------------


def test_chamar_mostra_so_as_docas_livres(
    entrar: Entrar, cenario: Demonstracao, chegar: Chegar, docas: list[Doca]
) -> None:
    primeira, segunda = chegar("ABC1D23", timedelta(hours=1)), chegar("BRA2E19", timedelta(0))
    lider = entrar(cenario.patio_a.email)
    lider.post(f"/patio/visitas/{primeira.id}/chamar", data={"doca_id": str(docas[0].id)})

    texto = lider.get(f"/patio/visitas/{segunda.id}/chamar").text

    assert f'value="{docas[1].id}"' in texto
    assert f'value="{docas[0].id}"' not in texto


def test_chamar_comecar_e_terminar_pela_tela(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(hours=1))
    lider = entrar(cenario.patio_a.email)

    resposta = lider.post(
        f"/patio/visitas/{visita.id}/chamar",
        data={"doca_id": str(docas[0].id)},
        follow_redirects=False,
    )
    assert (resposta.status_code, resposta.headers["location"]) == (
        303, f"/patio?site={cenario.site_a.id}",
    )  # fmt: skip
    assert _estado(sessao, visita) == "CHAMADA"
    lider.post(f"/patio/visitas/{visita.id}/comecar")
    assert _estado(sessao, visita) == "NA_DOCA"
    lider.post(f"/patio/visitas/{visita.id}/terminar")
    assert _estado(sessao, visita) == "LIBERADA"


def test_cancelar_a_chamada_pela_tela(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(hours=1))
    lider = entrar(cenario.patio_a.email)
    lider.post(f"/patio/visitas/{visita.id}/chamar", data={"doca_id": str(docas[0].id)})

    lider.post(f"/patio/visitas/{visita.id}/cancelar-chamada")

    assert _estado(sessao, visita) == "NA_FILA"


def test_doca_ocupada_avisa(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, chegar: Chegar, docas: list[Doca]
) -> None:
    primeira, segunda = chegar("ABC1D23", timedelta(hours=1)), chegar("BRA2E19", timedelta(0))
    lider = entrar(cenario.patio_a.email)
    lider.post(f"/patio/visitas/{primeira.id}/chamar", data={"doca_id": str(docas[0].id)})

    resposta = lider.post(f"/patio/visitas/{segunda.id}/chamar", data={"doca_id": str(docas[0].id)})

    assert resposta.status_code == 409
    assert "A Doca 1 está ocupada" in resposta.text
    assert _estado(sessao, segunda) == "NA_FILA"


def test_mudanca_fora_de_ordem_avisa(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, chegar: Chegar
) -> None:
    visita = chegar("ABC1D23", timedelta(hours=1))

    resposta = entrar(cenario.patio_a.email).post(f"/patio/visitas/{visita.id}/terminar")

    assert resposta.status_code == 409
    assert "O caminhão mudou de situação" in resposta.text
    assert _estado(sessao, visita) == "NA_FILA"


def test_visita_de_outra_empresa_responde_404(
    entrar: Entrar, cenario: Demonstracao, chegar: Chegar, docas: list[Doca]
) -> None:
    visita = chegar("ABC1D23", timedelta(hours=1))

    resposta = entrar(cenario.gestor_b.email).post(
        f"/patio/visitas/{visita.id}/chamar", data={"doca_id": str(docas[0].id)}
    )

    assert resposta.status_code == 404

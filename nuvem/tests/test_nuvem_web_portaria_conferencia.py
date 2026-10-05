"""A conferência da placa na tela da portaria (T38, SDD D-42)."""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem.portaria.modelos import ConferenciaPlaca
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]
Registrar = Callable[..., Passagem]

AGORA = datetime(2026, 10, 5, 17, 5, tzinfo=UTC)
"""14:05 em São Paulo."""


@pytest.fixture(autouse=True)
def _hora_fixa(app: FastAPI) -> None:
    app.dependency_overrides[agora] = lambda: AGORA


def _conferencias(sessao: Session) -> list[tuple[int, str | None, str]]:
    sessao.expire_all()
    feitas = sessao.scalars(select(ConferenciaPlaca).order_by(ConferenciaPlaca.id))
    return [(c.foto, c.placa_lida, c.placa) for c in feitas]


# --- Quem vê ----------------------------------------------------------------------------------


def test_sem_login_vai_para_a_tela_de_entrar(app: FastAPI, registrar_passagem: Registrar) -> None:
    passagem = registrar_passagem()

    resposta = TestClient(app).get(f"/portaria/conferir/{passagem.id}", follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


def test_o_lider_de_patio_nao_confere(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    patio = entrar(cenario.patio_a.email)

    assert patio.get(f"/portaria/conferir/{passagem.id}").status_code == 403
    resposta = patio.post(
        f"/portaria/conferir/{passagem.id}", data={"foto": "0", "placa": "ABC1D23"}
    )
    assert resposta.status_code == 403


def test_passagem_de_outra_empresa_responde_404(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    de_fora = entrar(cenario.porteiro_b.email)

    assert de_fora.get(f"/portaria/conferir/{passagem.id}").status_code == 404
    resposta = de_fora.post(
        f"/portaria/conferir/{passagem.id}", data={"foto": "0", "placa": "ABC1D23"}
    )
    assert resposta.status_code == 404
    assert _conferencias(sessao) == []


# --- Conferir ---------------------------------------------------------------------------------


def test_pagina_mostra_o_recorte_e_a_leitura(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    texto = entrar(cenario.porteiro_a.email).get(f"/portaria/conferir/{passagem.id}").text

    assert f'src="/portaria/fotos/{passagem.id}/0"' in texto
    assert "O leitor leu <strong>ABC1D23</strong>" in texto
    assert f'href="/portaria?site={cenario.site_a.id}"' in texto


def test_recorte_sem_leitura_avisa(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem(placas=[])

    texto = entrar(cenario.porteiro_a.email).get(f"/portaria/conferir/{passagem.id}").text

    assert "O leitor não leu nenhuma placa" in texto


def test_confirmar_pela_tela(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    porteiro = entrar(cenario.porteiro_a.email)

    resposta = porteiro.post(
        f"/portaria/conferir/{passagem.id}",
        data={"foto": "0", "placa": "ABC1D23"},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == f"/portaria/conferir/{passagem.id}"
    assert _conferencias(sessao) == [(0, "ABC1D23", "ABC1D23")]
    assert (
        "Conferida em 05/10 às 14:05: <strong>ABC1D23</strong>, certa"
        in porteiro.get(resposta.headers["location"]).text
    )


def test_corrigir_pela_tela(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    porteiro = entrar(cenario.porteiro_a.email)

    porteiro.post(f"/portaria/conferir/{passagem.id}", data={"foto": "0", "placa": "abc1d28"})

    assert _conferencias(sessao) == [(0, "ABC1D23", "ABC1D28")]
    texto = porteiro.get(f"/portaria/conferir/{passagem.id}").text
    assert "Conferida em 05/10 às 14:05: <strong>ABC1D28</strong>, corrigida" in texto


def test_placa_fora_do_formato_mostra_o_motivo(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    resposta = entrar(cenario.porteiro_a.email).post(
        f"/portaria/conferir/{passagem.id}", data={"foto": "0", "placa": "AB12"}
    )

    assert resposta.status_code == 422
    assert "não está no formato antigo (ABC1234) nem no Mercosul (ABC1D23)" in resposta.text
    assert _conferencias(sessao) == []


def test_foto_que_nao_e_recorte_de_placa_responde_404(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    resposta = entrar(cenario.porteiro_a.email).post(
        f"/portaria/conferir/{passagem.id}", data={"foto": "3", "placa": "ABC1D23"}
    )

    assert resposta.status_code == 404
    assert _conferencias(sessao) == []


def test_o_gestor_tambem_confere(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    entrar(cenario.gestor_a.email).post(
        f"/portaria/conferir/{passagem.id}", data={"foto": "0", "placa": "ABC1D23"}
    )

    assert _conferencias(sessao) == [(0, "ABC1D23", "ABC1D23")]


# --- Na lista de passagens --------------------------------------------------------------------


def _linha(cliente: TestClient, cenario: Demonstracao, passagem: Passagem) -> str:
    texto = cliente.get(f"/portaria/passagens?site={cenario.site_a.id}").text
    inicio = texto.index(f'id="passagem-{passagem.id}"')
    return texto[inicio : texto.index("</tr>", inicio)]


def test_lista_leva_a_conferencia(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    linha = _linha(entrar(cenario.porteiro_a.email), cenario, passagem)

    assert f'href="/portaria/conferir/{passagem.id}"' in linha


def test_passagem_sem_foto_de_placa_nao_tem_o_que_conferir(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem(placas=[], fotos=[])

    linha = _linha(entrar(cenario.porteiro_a.email), cenario, passagem)

    assert "/portaria/conferir/" not in linha


def test_lista_mostra_o_que_foi_conferido(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    certa, corrigida = registrar_passagem(), registrar_passagem()
    porteiro = entrar(cenario.porteiro_a.email)
    porteiro.post(f"/portaria/conferir/{certa.id}", data={"foto": "0", "placa": "ABC1D23"})
    porteiro.post(f"/portaria/conferir/{corrigida.id}", data={"foto": "0", "placa": "ABC1D28"})

    assert "placa certa" in _linha(porteiro, cenario, certa)
    assert "corrigida: ABC1D28" in _linha(porteiro, cenario, corrigida)

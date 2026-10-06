"""As telas da saúde da caixa (SDD 6.2 e 8.1, D-65): a frota de borda da administração e o
"site sem conexão" da portaria."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from contratos.saude import Saude
from nuvem.frota import saude as frota
from nuvem.frota import servico
from nuvem.frota.servico import AcessoDaCaixa, CaixaAtivada
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

AGORA = datetime(2026, 10, 6, 17, 0, tzinfo=UTC)
"""14:00 em São Paulo, o fuso dos sites da demonstração."""


@pytest.fixture
def caixa(sessao: Session, caixa_a: CaixaAtivada) -> AcessoDaCaixa:
    identificada = servico.caixa_da_chave(sessao, caixa_a.chave)
    assert identificada is not None
    return identificada


def _receber(
    sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa, momento: datetime
) -> None:
    dados: dict[str, Any] = {
        "versao_contrato": 1,
        "caixa_id": str(caixa.caixa_id),
        "site_id": str(caixa.site_id),
        "momento": (momento + timedelta(seconds=2.5)).isoformat(),
        "versao_programa": "0.1.0",
        "versao_leitor": "v0",
        "cpu": 31.0,
        "temperatura": 58.0,
        "memoria": 42.0,
        "disco": 11.0,
        "cameras": [
            {
                "camera_id": str(cenario.camera_a.id),
                "no_ar": True,
                "quadros_por_segundo": 4.9,
                "ultimo_quadro": momento.isoformat(),
            }
        ],
        "fila": {"passagens": 6, "fotos": 2, "recusadas": 1},
    }
    frota.receber_saude(sessao, caixa, Saude.model_validate(dados), agora=momento)


def _no_relogio(app: FastAPI, momento: datetime) -> None:
    app.dependency_overrides[agora] = lambda: momento


# --- A frota de borda -----------------------------------------------------------------------


def test_a_frota_mostra_a_caixa_e_a_saude(
    app: FastAPI, entrar: Entrar, sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    _receber(sessao, cenario, caixa, AGORA)
    _no_relogio(app, AGORA + timedelta(minutes=1))

    resposta = entrar(cenario.administrador.email).get("/administracao/frota")

    assert resposta.status_code == 200
    texto = resposta.text
    for esperado in (
        "Empresa A (demonstração)",
        "CD Exemplo",
        "0.1.0",
        "v0",
        "no ar",
        "06/10 14:00",
        "Entrada 1 — frente",
        "<td>6 passagens, 2 fotos, 1 recusada</td>",
        "+2,5 s",
        f'href="/administracao/frota/{caixa.caixa_id}"',
    ):
        assert esperado in texto, esperado


def test_a_frota_mostra_a_caixa_sem_contato_e_a_que_nunca_deu_sinal(
    app: FastAPI, entrar: Entrar, sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    gerado = servico.gerar_codigo_de_ativacao(
        sessao, cenario.site_b.id, administrador_id=cenario.administrador.id, agora=AGORA
    )
    servico.ativar(sessao, gerado.codigo, agora=AGORA)
    _receber(sessao, cenario, caixa, AGORA)
    _no_relogio(app, AGORA + timedelta(minutes=5))

    texto = entrar(cenario.administrador.email).get("/administracao/frota").text

    assert "sem contato desde 06/10 14:00" in texto
    assert "nunca deu sinal" in texto


def test_a_caixa_hora_a_hora(
    app: FastAPI, entrar: Entrar, sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    _receber(sessao, cenario, caixa, AGORA + timedelta(minutes=5))
    _receber(sessao, cenario, caixa, AGORA + timedelta(minutes=6))
    _no_relogio(app, AGORA + timedelta(minutes=7))

    resposta = entrar(cenario.administrador.email).get(f"/administracao/frota/{caixa.caixa_id}")

    assert resposta.status_code == 200
    texto = resposta.text
    for esperado in ("CD Exemplo", "06/10 14h", "2 de 60", "Entrada 1 — frente", "4,9"):
        assert esperado in texto, esperado


def test_caixa_que_nao_existe_responde_404(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.administrador.email).get("/administracao/frota/999999")

    assert resposta.status_code == 404


def test_o_inicio_da_administracao_leva_a_frota(entrar: Entrar, cenario: Demonstracao) -> None:
    assert 'href="/administracao/frota"' in entrar(cenario.administrador.email).get("/").text


@pytest.mark.parametrize("caminho", ["/administracao/frota", "/administracao/frota/1"])
def test_quem_e_do_cliente_nao_ve_a_frota(
    entrar: Entrar, cenario: Demonstracao, caminho: str
) -> None:
    assert entrar(cenario.gestor_a.email).get(caminho).status_code == 403


def test_sem_login_a_frota_leva_a_tela_de_entrar(app: FastAPI, cenario: Demonstracao) -> None:
    resposta = TestClient(app).get("/administracao/frota", follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


# --- A portaria -----------------------------------------------------------------------------


def test_a_portaria_confere_a_conexao_sozinha(entrar: Entrar, cenario: Demonstracao) -> None:
    texto = entrar(cenario.porteiro_a.email).get("/portaria").text

    assert f'hx-get="/portaria/conexao?site={cenario.site_a.id}"' in texto
    assert 'hx-trigger="load, every 30s"' in texto


def test_a_portaria_avisa_o_site_sem_conexao(
    app: FastAPI, entrar: Entrar, sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    _receber(sessao, cenario, caixa, AGORA)
    _no_relogio(app, AGORA)  # a sessão do porteiro começa na hora do teste
    porteiro = entrar(cenario.porteiro_a.email)
    caminho = f"/portaria/conexao?site={cenario.site_a.id}"

    _no_relogio(app, AGORA + timedelta(minutes=2))
    com_conexao = porteiro.get(caminho)
    _no_relogio(app, AGORA + timedelta(minutes=3))
    sem_conexao = porteiro.get(caminho)

    assert com_conexao.status_code == 200
    assert "sem conexão" not in com_conexao.text
    assert "Site sem conexão desde 14:00" in sem_conexao.text
    assert f'href="/portaria/chegada-manual?site={cenario.site_a.id}"' in sem_conexao.text


def test_a_caixa_que_sumiu_ontem_mostra_a_data(
    app: FastAPI, entrar: Entrar, sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    _receber(sessao, cenario, caixa, AGORA)
    _no_relogio(app, AGORA + timedelta(days=1))
    porteiro = entrar(cenario.porteiro_a.email)

    texto = porteiro.get(f"/portaria/conexao?site={cenario.site_a.id}").text

    assert "Site sem conexão desde 06/10 às 14:00" in texto


def test_a_conexao_do_site_de_outra_empresa_responde_404(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    resposta = entrar(cenario.porteiro_b.email).get(f"/portaria/conexao?site={cenario.site_a.id}")

    assert resposta.status_code == 404

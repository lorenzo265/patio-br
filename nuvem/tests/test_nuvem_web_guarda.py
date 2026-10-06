"""A disputa na página da prova e o pedido do titular na administração (SDD 6.2, D-70)."""

import json
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem import tarefas_de_fundo as fila
from nuvem.cadastro.acesso import acesso_do_usuario
from nuvem.frota.servico import CaixaAtivada
from nuvem.guarda import servico as guarda
from nuvem.guarda.modelos import MarcaDeDisputa
from nuvem.portaria import resolucao
from nuvem.portaria.modelos import Evento, Excecao
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

AGORA = datetime(2026, 10, 5, 17, 10, tzinfo=UTC)


@pytest.fixture
def visita_id(sessao: Session, app: FastAPI, registrar_passagem: Callable[..., Passagem]) -> int:
    app.dependency_overrides[agora] = lambda: AGORA
    passagem = registrar_passagem(fotos=[])
    fila.executar_pendentes(sessao, agora=AGORA)
    return sessao.scalars(select(Evento.visita_id).where(Evento.passagem_id == passagem.id)).one()


# --- A disputa ------------------------------------------------------------------------------


def test_o_gestor_marca_e_desmarca_a_disputa(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, visita_id: int
) -> None:
    gestor = entrar(cenario.gestor_a.email)
    pagina = gestor.get(f"/prova/visitas/{visita_id}").text
    assert f'action="/prova/visitas/{visita_id}/disputa"' in pagina
    assert "Não está em disputa" in pagina

    resposta = gestor.post(
        f"/prova/visitas/{visita_id}/disputa",
        data={"acao": "marcar", "motivo": "estadia contestada"},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == f"/prova/visitas/{visita_id}"
    pagina = gestor.get(f"/prova/visitas/{visita_id}").text
    assert "Em disputa desde 05/10 14:10: estadia contestada" in pagina
    gestor.post(
        f"/prova/visitas/{visita_id}/disputa",
        data={"acao": "desmarcar", "motivo": "acordo"},
        follow_redirects=False,
    )
    acoes = [m.acao for m in sessao.scalars(select(MarcaDeDisputa))]
    assert acoes == ["marcar", "desmarcar"]


def test_so_o_gestor_marca_a_disputa(entrar: Entrar, cenario: Demonstracao, visita_id: int) -> None:
    porteiro = entrar(cenario.porteiro_a.email)
    gestor_b = entrar(cenario.gestor_b.email)
    dados = {"acao": "marcar", "motivo": "x"}

    assert porteiro.post(f"/prova/visitas/{visita_id}/disputa", data=dados).status_code == 403
    assert gestor_b.post(f"/prova/visitas/{visita_id}/disputa", data=dados).status_code == 404


def test_a_disputa_pede_uma_acao_conhecida(
    entrar: Entrar, cenario: Demonstracao, visita_id: int
) -> None:
    gestor = entrar(cenario.gestor_a.email)

    resposta = gestor.post(
        f"/prova/visitas/{visita_id}/disputa", data={"acao": "apagar", "motivo": "x"}
    )

    assert resposta.status_code == 422


def test_a_foto_apagada_pela_guarda_aparece_na_prova(
    sessao: Session,
    app: FastAPI,
    entrar: Entrar,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    registrar_passagem: Callable[..., Passagem],
) -> None:
    app.dependency_overrides[agora] = lambda: AGORA
    armazenamento = app.state.armazenamento
    armazenamento.guardar(caixa_a.caixa_id, "p/1.jpg", b"\xff\xd8\xff" + b"recorte")
    camera = str(cenario.camera_a.id)
    passagem = registrar_passagem(
        fotos=[
            {"tipo": "placa", "camera_id": camera, "ref": "p/1.jpg"},
            {"tipo": "contexto", "camera_id": camera, "ref": "nunca/veio.jpg"},
        ]
    )
    fila.executar_pendentes(
        sessao, agora=AGORA, contexto=fila.Contexto(armazenamento=armazenamento)
    )
    visita_id = sessao.scalars(
        select(Evento.visita_id).where(Evento.passagem_id == passagem.id)
    ).one()
    # Sem agendamento, a chegada é exceção: aceita, ela deixa de segurar as fotos.
    (excecao_id,) = sessao.scalars(select(Excecao.id).where(Excecao.visita_id == visita_id))
    porteiro = acesso_do_usuario(sessao, cenario.porteiro_a.id)
    resolucao.aceitar_sem_agendamento(sessao, porteiro, excecao_id, agora=AGORA)
    depois = datetime(2027, 1, 10, 12, 0, tzinfo=UTC)
    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=depois, dias=90) == 1

    texto = entrar(cenario.gestor_a.email).get(f"/prova/visitas/{visita_id}").text

    assert "foto apagada pelo prazo de guarda em 10/01" in texto
    # A que nunca chegou continua "não chegou": não havia o que apagar.
    assert texto.count("foto apagada pelo prazo de guarda") == 1
    assert "não chegou" in texto
    assert "Cadeia íntegra" in texto


# --- O pedido do titular --------------------------------------------------------------------


def test_a_administracao_levanta_a_placa(
    entrar: Entrar, cenario: Demonstracao, visita_id: int
) -> None:
    administracao = entrar(cenario.administrador.email)
    tela = administracao.get("/administracao/titular").text
    # A placa e o celular vão no corpo do pedido, e não no endereço (o registro de acesso).
    assert '<form method="post" action="/administracao/titular">' in tela
    assert cenario.empresa_a.nome in tela

    resposta = administracao.post(
        "/administracao/titular", data={"empresa": cenario.empresa_a.id, "placa": "ABC1D23"}
    )

    assert resposta.status_code == 200
    assert f"Visita {visita_id}" in resposta.text
    assert "no-store" in resposta.headers["cache-control"]


def test_o_levantamento_do_titular_em_arquivo(
    entrar: Entrar, cenario: Demonstracao, visita_id: int
) -> None:
    administracao = entrar(cenario.administrador.email)

    resposta = administracao.post(
        "/administracao/titular",
        data={"empresa": cenario.empresa_a.id, "placa": "ABC1D23", "formato": "json"},
    )

    assert resposta.status_code == 200
    assert resposta.headers["content-disposition"].startswith('attachment; filename="titular-')
    assert "ABC1D23" not in resposta.headers["content-disposition"]
    assert [v["id"] for v in json.loads(resposta.content)["visitas"]] == [visita_id]


def test_o_pedido_invalido_explica(entrar: Entrar, cenario: Demonstracao) -> None:
    administracao = entrar(cenario.administrador.email)

    resposta = administracao.post(
        "/administracao/titular", data={"empresa": cenario.empresa_a.id, "placa": "ABC"}
    )

    assert resposta.status_code == 400
    assert "placa" in resposta.text.lower()


def test_quem_e_do_cliente_nao_levanta_o_titular(entrar: Entrar, cenario: Demonstracao) -> None:
    gestor = entrar(cenario.gestor_a.email)

    assert gestor.get("/administracao/titular").status_code == 403
    dados = {"empresa": cenario.empresa_a.id, "placa": "ABC1D23"}
    assert gestor.post("/administracao/titular", data=dados).status_code == 403

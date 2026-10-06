"""A prova da visita nas telas (SDD 6.2, D-69): a busca, a página e o arquivo, só do gestor."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem import tarefas_de_fundo as fila
from nuvem.frota.servico import CaixaAtivada
from nuvem.portaria.modelos import Evento, PassagemRecebida, Visita
from nuvem.prova import cadeia
from nuvem.prova.modelos import EloDaProva
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

AGORA = datetime(2026, 10, 5, 17, 10, tzinfo=UTC)
FOTO = b"\xff\xd8\xff" + b"recorte inventado"


@pytest.fixture
def no_relogio(app: FastAPI) -> FastAPI:
    app.dependency_overrides[agora] = lambda: AGORA
    return app


@pytest.fixture
def chegada(
    sessao: Session,
    no_relogio: FastAPI,
    caixa_a: CaixaAtivada,
    registrar_passagem: Callable[..., Passagem],
) -> tuple[Passagem, Visita]:
    """Uma passagem sem agendamento (vira exceção), com a foto já resumida."""
    armazenamento = no_relogio.state.armazenamento
    armazenamento.guardar(caixa_a.caixa_id, "p/1.jpg", FOTO)
    passagem = registrar_passagem()
    fila.executar_pendentes(
        sessao, agora=AGORA, contexto=fila.Contexto(armazenamento=armazenamento)
    )
    evento = sessao.scalars(select(Evento).where(Evento.passagem_id == passagem.id)).one()
    visita = sessao.get(Visita, evento.visita_id)
    assert visita is not None
    return passagem, visita


def test_o_gestor_busca_a_visita_pela_placa(
    entrar: Entrar, cenario: Demonstracao, chegada: tuple[Passagem, Visita]
) -> None:
    _, visita = chegada
    gestor = entrar(cenario.gestor_a.email)

    assert f'href="/prova/visitas/{visita.id}"' in gestor.get("/prova?placa=abc1d23").text
    assert f'href="/prova/visitas/{visita.id}"' not in gestor.get("/prova?placa=XYZ9K87").text
    assert f'href="/prova/visitas/{visita.id}"' in gestor.get("/prova").text
    assert 'href="/prova"' in gestor.get("/").text


def test_a_pagina_da_prova_sela_e_confere(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    chegada: tuple[Passagem, Visita],
) -> None:
    passagem, visita = chegada

    resposta = entrar(cenario.gestor_a.email).get(f"/prova/visitas/{visita.id}")

    assert resposta.status_code == 200
    texto = resposta.text
    for trecho in (
        "Prova da visita",
        "ABC1D23",
        "97%",
        "Entrada 1",
        "Entrada 1 — frente",
        "05/10 14:02:11",  # a hora da caixa, no fuso do site
        f'src="/portaria/fotos/{passagem.id}/0"',
        "exceção",
        "Cadeia íntegra",
        "ainda sem âncora",
        "sha256(anterior + ",
    ):
        assert trecho in texto, trecho
    elos = sessao.scalar(
        select(func.count()).select_from(EloDaProva).where(EloDaProva.visita_id == visita.id)
    )
    assert elos and elos >= 3


def test_o_arquivo_da_prova_confere_sem_nos(
    entrar: Entrar, cenario: Demonstracao, chegada: tuple[Passagem, Visita]
) -> None:
    _, visita = chegada

    resposta = entrar(cenario.gestor_a.email).get(f"/prova/visitas/{visita.id}.json")

    assert resposta.status_code == 200
    assert (
        resposta.headers["content-disposition"]
        == f'attachment; filename="prova-visita-{visita.id}.json"'
    )
    arquivo: dict[str, Any] = json.loads(resposta.content)
    assert arquivo["regra"] == cadeia.REGRA
    assert arquivo["visita"] == visita.id
    elos = [
        cadeia.Elo(
            e["ordem"], e["tipo"], e["referencia"], e["conteudo"], e["anterior"], e["resumo"]
        )
        for e in arquivo["elos"]
    ]
    assert elos
    assert cadeia.primeira_quebra(elos) is None
    assert arquivo["conferencia"]["integra"] is True


def test_o_elo_quebrado_aparece_na_pagina(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, chegada: tuple[Passagem, Visita]
) -> None:
    passagem, visita = chegada
    gestor = entrar(cenario.gestor_a.email)
    gestor.get(f"/prova/visitas/{visita.id}")  # sela
    recebida = sessao.get(PassagemRecebida, passagem.id)
    assert recebida is not None
    sessao.execute(
        update(PassagemRecebida)
        .where(PassagemRecebida.id == passagem.id)
        .values(como_veio={**recebida.como_veio, "versao_leitor": "outra"})
    )

    texto = gestor.get(f"/prova/visitas/{visita.id}").text

    assert "Elo quebrado" in texto
    assert "o registro mudou depois de selado" in texto
    assert "Cadeia íntegra" not in texto


@pytest.mark.parametrize("papel", ["porteiro_a", "patio_a"])
def test_so_o_gestor_ve_a_prova(
    entrar: Entrar, cenario: Demonstracao, chegada: tuple[Passagem, Visita], papel: str
) -> None:
    _, visita = chegada
    cliente = entrar(getattr(cenario, papel).email)

    assert cliente.get("/prova").status_code == 403
    assert cliente.get(f"/prova/visitas/{visita.id}").status_code == 403
    assert cliente.get(f"/prova/visitas/{visita.id}.json").status_code == 403


def test_a_prova_de_outra_empresa_nao_existe(
    entrar: Entrar, cenario: Demonstracao, chegada: tuple[Passagem, Visita]
) -> None:
    _, visita = chegada
    gestor_b = entrar(cenario.gestor_b.email)

    assert gestor_b.get(f"/prova/visitas/{visita.id}").status_code == 404
    assert gestor_b.get(f"/prova/visitas/{visita.id}.json").status_code == 404
    assert f'href="/prova/visitas/{visita.id}"' not in gestor_b.get("/prova?placa=ABC1D23").text

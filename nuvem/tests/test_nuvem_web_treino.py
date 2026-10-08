"""A base de treino na administração (SDD 6.2, D-71): a cláusula e a rotulagem."""

from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem.cadastro.acesso import AcessoAdmin, acesso_do_usuario
from nuvem.frota.servico import CaixaAtivada
from nuvem.portaria import conferencia
from nuvem.relogio import agora
from nuvem.semente import Demonstracao
from nuvem.treino import servico as treino
from nuvem.treino.guarda import TreinoNoDisco
from nuvem.treino.modelos import AutorizacaoDeTreino, Rotulo

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

AGORA = datetime(2026, 10, 5, 17, 10, tzinfo=UTC)
FOTO = b"\xff\xd8\xff" + b"recorte inventado"


@pytest.fixture
def rotulo_id(
    sessao: Session,
    app: FastAPI,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    registrar_passagem: Callable[..., Passagem],
) -> int:
    """Um rótulo a revisar, com o recorte na base de treino da aplicação."""
    app.dependency_overrides[agora] = lambda: AGORA
    administracao = AcessoAdmin(administrador_id=cenario.administrador.id)
    treino.autorizar(
        sessao, administracao, cenario.empresa_a.id, clausula_em=date(2026, 10, 1), agora=AGORA
    )
    app.state.armazenamento.guardar(caixa_a.caixa_id, "p/1.jpg", FOTO)
    passagem = registrar_passagem()
    porteiro = acesso_do_usuario(sessao, cenario.porteiro_a.id)
    conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D23", agora=AGORA)
    treino.rotular(sessao, app.state.armazenamento, app.state.base_de_treino, agora=AGORA)
    return sessao.scalars(select(Rotulo.id)).one()


def test_a_tela_mostra_as_empresas_e_os_rotulos_a_revisar(
    entrar: Entrar, cenario: Demonstracao, rotulo_id: int
) -> None:
    administracao = entrar(cenario.administrador.email)

    tela = administracao.get("/administracao/treino").text
    recorte = administracao.get(f"/administracao/treino/rotulos/{rotulo_id}/recorte")

    assert cenario.empresa_a.nome in tela
    assert "cláusula de 01/10/2026" in tela
    assert f'src="/administracao/treino/rotulos/{rotulo_id}/recorte"' in tela
    assert f'action="/administracao/treino/rotulos/{rotulo_id}"' in tela
    assert 'value="ABC1D23"' in tela
    assert recorte.status_code == 200
    assert recorte.headers["content-type"] == "image/jpeg"
    assert recorte.content == FOTO
    assert "no-store" in recorte.headers["cache-control"]


@pytest.mark.parametrize(
    ("acao", "placa", "situacao"),
    [
        ("aceitar", "ABC1D23", "aceito"),
        ("corrigir", "BRA2E19", "corrigido"),
        ("descartar", "", "descartado"),
    ],
)
def test_a_rotulagem_pela_tela(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    rotulo_id: int,
    acao: str,
    placa: str,
    situacao: str,
) -> None:
    administracao = entrar(cenario.administrador.email)

    resposta = administracao.post(
        f"/administracao/treino/rotulos/{rotulo_id}",
        data={"acao": acao, "placa": placa},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    rotulo = sessao.get(Rotulo, rotulo_id)
    assert rotulo is not None
    sessao.refresh(rotulo)
    assert rotulo.situacao == situacao


def test_a_correcao_com_placa_invalida_explica(
    entrar: Entrar, cenario: Demonstracao, rotulo_id: int
) -> None:
    administracao = entrar(cenario.administrador.email)

    resposta = administracao.post(
        f"/administracao/treino/rotulos/{rotulo_id}", data={"acao": "corrigir", "placa": "ABC"}
    )

    assert resposta.status_code == 400
    assert "placa inválida" in resposta.text


def test_registrar_e_revogar_a_clausula(
    sessao: Session, entrar: Entrar, cenario: Demonstracao, rotulo_id: int
) -> None:
    administracao = entrar(cenario.administrador.email)

    resposta = administracao.post(
        "/administracao/treino/autorizacoes",
        data={"empresa": cenario.empresa_b.id, "clausula_em": "2026-09-15"},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    revogada = administracao.post(
        f"/administracao/treino/autorizacoes/{cenario.empresa_a.id}/revogar",
        follow_redirects=False,
    )

    assert revogada.status_code == 303
    ativas = sessao.scalars(
        select(AutorizacaoDeTreino.empresa_id).where(AutorizacaoDeTreino.revogada_em.is_(None))
    ).all()
    assert ativas == [cenario.empresa_b.id]
    assert sessao.scalars(select(Rotulo)).all() == []


def test_quem_e_do_cliente_nao_entra_no_treino(
    entrar: Entrar, cenario: Demonstracao, rotulo_id: int
) -> None:
    gestor = entrar(cenario.gestor_a.email)

    assert gestor.get("/administracao/treino").status_code == 403
    assert gestor.get(f"/administracao/treino/rotulos/{rotulo_id}/recorte").status_code == 403
    assert (
        gestor.post(
            f"/administracao/treino/rotulos/{rotulo_id}", data={"acao": "aceitar"}
        ).status_code
        == 403
    )


def test_a_base_de_treino_da_aplicacao_fica_na_pasta_das_fotos(app: FastAPI) -> None:
    assert isinstance(app.state.base_de_treino, TreinoNoDisco)

"""As versões da caixa nas telas da administração (SDD 6.2, D-67)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from nuvem.cadastro.acesso import AcessoAdmin
from nuvem.frota import servico, versoes
from nuvem.frota.servico import AcessoDaCaixa, CaixaAtivada
from nuvem.frota.versoes import RelatoDeAtualizacao
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

AGORA = datetime(2026, 10, 6, 17, 0, tzinfo=UTC)
IMAGEM = "ghcr.io/exemplo/patio-caixa"
RESUMO = "sha256:" + "a" * 64


@pytest.fixture
def caixa(sessao: Session, caixa_a: CaixaAtivada) -> AcessoDaCaixa:
    identificada = servico.caixa_da_chave(sessao, caixa_a.chave)
    assert identificada is not None
    return identificada


@pytest.fixture
def administracao(app: FastAPI, entrar: Entrar, cenario: Demonstracao) -> TestClient:
    app.dependency_overrides[agora] = lambda: AGORA
    return entrar(cenario.administrador.email)


def _versao(sessao: Session, cenario: Demonstracao) -> int:
    acesso = AcessoAdmin(administrador_id=cenario.administrador.id)
    return versoes.cadastrar_versao(
        sessao, acesso, nome="0.2.0", imagem=IMAGEM, resumo=RESUMO, agora=AGORA
    ).id


def _relato(resultado: str, motivo: str = "") -> RelatoDeAtualizacao:
    return RelatoDeAtualizacao.model_validate(
        {
            "de": "patio-caixa:local",
            "para": RESUMO,
            "comecou_em": AGORA.isoformat(),
            "terminou_em": (AGORA + timedelta(minutes=6)).isoformat(),
            "resultado": resultado,
            "motivo": motivo,
        }
    )


def test_a_tela_das_versoes(
    administracao: TestClient, sessao: Session, cenario: Demonstracao
) -> None:
    _versao(sessao, cenario)

    resposta = administracao.get("/administracao/frota/versoes")

    assert resposta.status_code == 200
    texto = resposta.text
    for esperado in ("0.2.0", "sha256:aaaaaaaaaaaa", "ainda não deu certo em nenhuma caixa"):
        assert esperado in texto, esperado
    assert texto.count('name="_csrf"') >= 2  # cadastrar e escolher


def test_cadastra_a_versao_pela_tela(administracao: TestClient) -> None:
    resposta = administracao.post(
        "/administracao/frota/versoes",
        data={"nome": "0.2.0", "imagem": IMAGEM, "resumo": RESUMO},
        follow_redirects=False,
    )

    assert (resposta.status_code, resposta.headers["location"]) == (
        303,
        "/administracao/frota/versoes",
    )
    assert "0.2.0" in administracao.get("/administracao/frota/versoes").text


def test_versao_fora_do_formato_explica(administracao: TestClient) -> None:
    resposta = administracao.post(
        "/administracao/frota/versoes",
        data={"nome": "0.2.0", "imagem": IMAGEM, "resumo": "sha256:curto"},
    )

    assert resposta.status_code == 400
    assert "resumo" in resposta.text


def test_escolhe_para_uma_caixa_pela_tela(
    administracao: TestClient, sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    versao_id = _versao(sessao, cenario)

    resposta = administracao.post(
        f"/administracao/frota/versoes/{versao_id}/escolher",
        # O formulário manda as duas listas; vale a do alcance.
        data={
            "alcance": "caixa",
            "caixa_id": str(caixa.caixa_id),
            "site_id": str(cenario.site_a.id),
        },
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    escolhida = versoes.versao_da_caixa(sessao, caixa)
    assert escolhida is not None
    assert escolhida.id == versao_id


def test_escolher_para_todas_antes_de_uma_caixa_explica(
    administracao: TestClient, sessao: Session, cenario: Demonstracao
) -> None:
    versao_id = _versao(sessao, cenario)

    resposta = administracao.post(
        f"/administracao/frota/versoes/{versao_id}/escolher",
        data={"alcance": "todas", "site_id": str(cenario.site_a.id), "caixa_id": "1"},
    )

    assert resposta.status_code == 409
    assert "primeiro numa caixa" in resposta.text


def test_escolhe_para_o_site_depois_de_dar_certo(
    administracao: TestClient, sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    versao_id = _versao(sessao, cenario)
    versoes.registrar_atualizacao(sessao, caixa, _relato("ok"), agora=AGORA)

    resposta = administracao.post(
        f"/administracao/frota/versoes/{versao_id}/escolher",
        data={
            "alcance": "site",
            "site_id": str(cenario.site_a.id),
            "caixa_id": str(caixa.caixa_id),
        },
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert "<td>deu certo em 1 caixa</td>" in administracao.get("/administracao/frota/versoes").text


def test_a_caixa_mostra_as_atualizacoes(
    administracao: TestClient, sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    _versao(sessao, cenario)
    versoes.registrar_atualizacao(
        sessao, caixa, _relato("voltou", "câmeras fora do ar: 21"), agora=AGORA
    )

    texto = administracao.get(f"/administracao/frota/{caixa.caixa_id}").text

    for esperado in (
        "Atualizações",
        "patio-caixa:local",
        "0.2.0",
        "voltou",
        "câmeras fora do ar: 21",
    ):
        assert esperado in texto, esperado


def test_a_frota_leva_as_versoes(administracao: TestClient) -> None:
    assert 'href="/administracao/frota/versoes"' in administracao.get("/administracao/frota").text


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("get", "/administracao/frota/versoes"),
        ("post", "/administracao/frota/versoes"),
        ("post", "/administracao/frota/versoes/1/escolher"),
    ],
)
def test_quem_e_do_cliente_nao_ve_as_versoes(
    entrar: Entrar, cenario: Demonstracao, metodo: str, caminho: str
) -> None:
    gestor = entrar(cenario.gestor_a.email)

    assert getattr(gestor, metodo)(caminho).status_code == 403

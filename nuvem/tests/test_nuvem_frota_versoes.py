"""As versões da caixa (SDD 7.4, D-67): cadastrar, escolher por alcance, a ordem (uma caixa antes
das outras) e as atualizações contadas pela caixa."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nuvem.banco import SQLSTATE_SO_ACRESCENTA, sqlstate
from nuvem.cadastro.acesso import AcessoAdmin
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.frota import servico, versoes
from nuvem.frota.modelos import AtualizacaoCaixa, EscolhaDeVersao
from nuvem.frota.servico import AcessoDaCaixa, CaixaAtivada
from nuvem.frota.versoes import RelatoDeAtualizacao, VersaoNaoProvadaError
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 6, 17, 0, tzinfo=UTC)
IMAGEM = "ghcr.io/exemplo/patio-caixa"
RESUMO_1 = "sha256:" + "1" * 64
RESUMO_2 = "sha256:" + "2" * 64


@pytest.fixture
def administracao(cenario: Demonstracao) -> AcessoAdmin:
    return AcessoAdmin(administrador_id=cenario.administrador.id)


@pytest.fixture
def caixa(sessao: Session, caixa_a: CaixaAtivada) -> AcessoDaCaixa:
    identificada = servico.caixa_da_chave(sessao, caixa_a.chave)
    assert identificada is not None
    return identificada


def _ativar(sessao: Session, cenario: Demonstracao, site_id: int) -> AcessoDaCaixa:
    gerado = servico.gerar_codigo_de_ativacao(
        sessao, site_id, administrador_id=cenario.administrador.id, agora=AGORA
    )
    identificada = servico.caixa_da_chave(
        sessao, servico.ativar(sessao, gerado.codigo, agora=AGORA).chave
    )
    assert identificada is not None
    return identificada


def _versao(
    sessao: Session, administracao: AcessoAdmin, nome: str = "0.2.0", resumo: str = RESUMO_1
) -> int:
    return versoes.cadastrar_versao(
        sessao, administracao, nome=nome, imagem=IMAGEM, resumo=resumo, agora=AGORA
    ).id


def _relato(resumo: str = RESUMO_1, resultado: str = "ok", **mais: Any) -> RelatoDeAtualizacao:
    dados: dict[str, Any] = {
        "de": "patio-caixa:local",
        "para": resumo,
        "comecou_em": AGORA.isoformat(),
        "terminou_em": (AGORA + timedelta(minutes=2)).isoformat(),
        "resultado": resultado,
        "motivo": "",
    }
    return RelatoDeAtualizacao.model_validate(dados | mais)


def _provar(sessao: Session, caixa: AcessoDaCaixa, resumo: str = RESUMO_1) -> None:
    versoes.registrar_atualizacao(sessao, caixa, _relato(resumo), agora=AGORA)


# --- Cadastrar ------------------------------------------------------------------------------


def test_cadastra_a_versao_pelo_resumo(sessao: Session, administracao: AcessoAdmin) -> None:
    versao = versoes.cadastrar_versao(
        sessao, administracao, nome="0.2.0", imagem=IMAGEM, resumo=RESUMO_1, agora=AGORA
    )

    assert (versao.nome, versao.imagem, versao.resumo) == ("0.2.0", IMAGEM, RESUMO_1)
    assert versao.referencia == f"{IMAGEM}@{RESUMO_1}"


def test_o_resumo_em_maiusculas_vira_minusculas(
    sessao: Session, administracao: AcessoAdmin
) -> None:
    versao = versoes.cadastrar_versao(
        sessao, administracao, nome="0.2.0", imagem=IMAGEM, resumo=RESUMO_1.upper(), agora=AGORA
    )

    assert versao.resumo == RESUMO_1


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("resumo", "sha256:123"),
        ("resumo", "md5:" + "1" * 64),
        ("resumo", "sha256:" + "G" * 64),
        ("imagem", "ghcr.io/exemplo/patio-caixa:latest"),
        ("imagem", "ghcr.io/exemplo/patio-caixa@" + RESUMO_1),
        ("imagem", ""),
        ("nome", ""),
        ("nome", "0.2.0 beta"),
        ("nome", "x" * 51),
    ],
)
def test_versao_fora_do_formato_e_recusada(
    sessao: Session, administracao: AcessoAdmin, campo: str, valor: str
) -> None:
    dados = {"nome": "0.2.0", "imagem": IMAGEM, "resumo": RESUMO_1} | {campo: valor}

    with pytest.raises(DadoInvalidoError):
        versoes.cadastrar_versao(sessao, administracao, agora=AGORA, **dados)


@pytest.mark.parametrize("repetido", ["nome", "resumo"])
def test_nome_ou_resumo_repetido_e_recusado(
    sessao: Session, administracao: AcessoAdmin, repetido: str
) -> None:
    _versao(sessao, administracao)
    outra = {"nome": "0.3.0", "resumo": RESUMO_2} | {
        repetido: {"nome": "0.2.0", "resumo": RESUMO_1}[repetido]
    }

    with pytest.raises(DadoInvalidoError):
        versoes.cadastrar_versao(sessao, administracao, imagem=IMAGEM, agora=AGORA, **outra)


# --- Escolher e a versão de cada caixa ------------------------------------------------------


def test_sem_escolha_a_caixa_fica_como_esta(sessao: Session, caixa: AcessoDaCaixa) -> None:
    assert versoes.versao_da_caixa(sessao, caixa) is None


def test_a_escolha_para_uma_caixa(
    sessao: Session, administracao: AcessoAdmin, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    outra = _ativar(sessao, cenario, cenario.site_a.id)
    versao_id = _versao(sessao, administracao)

    versoes.escolher_versao(sessao, administracao, versao_id, caixa_id=caixa.caixa_id, agora=AGORA)

    escolhida = versoes.versao_da_caixa(sessao, caixa)
    assert escolhida is not None
    assert escolhida.id == versao_id
    assert versoes.versao_da_caixa(sessao, outra) is None


def test_a_versao_nova_vai_primeiro_para_uma_caixa_so(
    sessao: Session, administracao: AcessoAdmin, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    versao_id = _versao(sessao, administracao)

    with pytest.raises(VersaoNaoProvadaError):
        versoes.escolher_versao(sessao, administracao, versao_id, agora=AGORA)
    with pytest.raises(VersaoNaoProvadaError):
        versoes.escolher_versao(
            sessao, administracao, versao_id, site_id=cenario.site_a.id, agora=AGORA
        )


def test_a_versao_que_deu_certo_numa_caixa_vai_para_o_site_e_para_todas(
    sessao: Session, administracao: AcessoAdmin, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    versao_id = _versao(sessao, administracao)
    _provar(sessao, caixa)
    da_b = _ativar(sessao, cenario, cenario.site_b.id)

    versoes.escolher_versao(
        sessao, administracao, versao_id, site_id=cenario.site_a.id, agora=AGORA
    )
    so_o_site = versoes.versao_da_caixa(sessao, da_b)
    versoes.escolher_versao(sessao, administracao, versao_id, agora=AGORA)

    assert so_o_site is None
    escolhida = versoes.versao_da_caixa(sessao, da_b)
    assert escolhida is not None
    assert escolhida.id == versao_id


@pytest.mark.parametrize("resultado", ["voltou", "falhou"])
def test_a_versao_que_voltou_nao_conta_como_provada(
    sessao: Session, administracao: AcessoAdmin, caixa: AcessoDaCaixa, resultado: str
) -> None:
    versao_id = _versao(sessao, administracao)
    versoes.registrar_atualizacao(sessao, caixa, _relato(resultado=resultado), agora=AGORA)

    with pytest.raises(VersaoNaoProvadaError):
        versoes.escolher_versao(sessao, administracao, versao_id, agora=AGORA)


def test_vence_a_escolha_mais_especifica_e_em_cada_alcance_a_ultima(
    sessao: Session, administracao: AcessoAdmin, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    v1 = _versao(sessao, administracao, "0.2.0", RESUMO_1)
    v2 = _versao(sessao, administracao, "0.3.0", RESUMO_2)
    _provar(sessao, caixa, RESUMO_1)
    _provar(sessao, caixa, RESUMO_2)
    site = cenario.site_a.id

    def vale() -> int | None:
        escolhida = versoes.versao_da_caixa(sessao, caixa)
        return escolhida.id if escolhida else None

    versoes.escolher_versao(sessao, administracao, v1, agora=AGORA)
    assert vale() == v1
    versoes.escolher_versao(sessao, administracao, v2, site_id=site, agora=AGORA + timedelta(1))
    assert vale() == v2  # o site vence todas
    versoes.escolher_versao(sessao, administracao, v1, agora=AGORA + timedelta(2))
    assert vale() == v2  # todas mais nova não vence o site
    versoes.escolher_versao(
        sessao, administracao, v1, caixa_id=caixa.caixa_id, agora=AGORA + timedelta(3)
    )
    assert vale() == v1  # a caixa vence o site
    versoes.escolher_versao(
        sessao, administracao, v2, caixa_id=caixa.caixa_id, agora=AGORA + timedelta(4)
    )
    assert vale() == v2  # na mesma caixa, vale a última


def test_a_escolha_do_site_nao_vale_para_outro_site(
    sessao: Session, administracao: AcessoAdmin, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    versao_id = _versao(sessao, administracao)
    _provar(sessao, caixa)
    ao_lado = _ativar(sessao, cenario, cenario.site_a2.id)

    versoes.escolher_versao(
        sessao, administracao, versao_id, site_id=cenario.site_a.id, agora=AGORA
    )

    assert versoes.versao_da_caixa(sessao, ao_lado) is None


def test_escolher_o_que_nao_existe(
    sessao: Session, administracao: AcessoAdmin, caixa: AcessoDaCaixa
) -> None:
    versao_id = _versao(sessao, administracao)

    with pytest.raises(NaoEncontradoError):
        versoes.escolher_versao(sessao, administracao, 999999, caixa_id=caixa.caixa_id, agora=AGORA)
    with pytest.raises(NaoEncontradoError):
        versoes.escolher_versao(sessao, administracao, versao_id, caixa_id=999999, agora=AGORA)
    with pytest.raises(NaoEncontradoError):
        versoes.escolher_versao(sessao, administracao, versao_id, site_id=999999, agora=AGORA)


def test_escolher_o_site_e_a_caixa_juntos_e_recusado(
    sessao: Session, administracao: AcessoAdmin, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    versao_id = _versao(sessao, administracao)

    with pytest.raises(DadoInvalidoError):
        versoes.escolher_versao(
            sessao, administracao, versao_id,
            site_id=cenario.site_a.id, caixa_id=caixa.caixa_id, agora=AGORA,
        )  # fmt: skip


def test_a_escolha_so_se_acrescenta(
    sessao: Session, administracao: AcessoAdmin, caixa: AcessoDaCaixa
) -> None:
    versao_id = _versao(sessao, administracao)
    versoes.escolher_versao(sessao, administracao, versao_id, caixa_id=caixa.caixa_id, agora=AGORA)

    with pytest.raises(DBAPIError) as erro:
        sessao.execute(update(EscolhaDeVersao).values(escolhida_em=AGORA + timedelta(1)))
    assert sqlstate(erro.value) == SQLSTATE_SO_ACRESCENTA


# --- As atualizações ------------------------------------------------------------------------


def test_a_caixa_conta_a_atualizacao(
    sessao: Session, administracao: AcessoAdmin, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    versao_id = _versao(sessao, administracao)

    versoes.registrar_atualizacao(
        sessao, caixa, _relato(resultado="voltou", motivo="câmeras fora do ar: 21"), agora=AGORA
    )

    (registro,) = sessao.scalars(select(AtualizacaoCaixa))
    assert (registro.empresa_id, registro.caixa_id, registro.versao_id) == (
        cenario.empresa_a.id, caixa.caixa_id, versao_id,
    )  # fmt: skip
    assert (registro.de, registro.resultado, registro.motivo) == (
        "patio-caixa:local", "voltou", "câmeras fora do ar: 21",
    )  # fmt: skip
    assert (registro.comecou_em, registro.terminou_em, registro.recebida_em) == (
        AGORA, AGORA + timedelta(minutes=2), AGORA,
    )  # fmt: skip


def test_atualizacao_para_versao_desconhecida_e_recusada(
    sessao: Session, caixa: AcessoDaCaixa
) -> None:
    with pytest.raises(DadoInvalidoError):
        versoes.registrar_atualizacao(sessao, caixa, _relato(RESUMO_2), agora=AGORA)


def test_o_relato_fora_do_formato_e_recusado() -> None:
    with pytest.raises(ValueError, match="terminou"):
        _relato(terminou_em=(AGORA - timedelta(seconds=1)).isoformat())
    with pytest.raises(ValueError):
        _relato(resultado="talvez")
    with pytest.raises(ValueError):
        _relato(para="sha256:curto")
    with pytest.raises(ValueError):
        _relato(motivo="x" * 501)


def test_a_atualizacao_so_se_acrescenta(
    sessao: Session, administracao: AcessoAdmin, caixa: AcessoDaCaixa
) -> None:
    _versao(sessao, administracao)
    _provar(sessao, caixa)

    with pytest.raises(DBAPIError) as erro:
        sessao.execute(text("delete from atualizacao_caixa"))
    assert sqlstate(erro.value) == SQLSTATE_SO_ACRESCENTA


def test_as_atualizacoes_da_caixa_das_mais_novas(
    sessao: Session, administracao: AcessoAdmin, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    _versao(sessao, administracao)
    outra = _ativar(sessao, cenario, cenario.site_a.id)
    versoes.registrar_atualizacao(sessao, caixa, _relato(resultado="voltou"), agora=AGORA)
    versoes.registrar_atualizacao(sessao, caixa, _relato(), agora=AGORA + timedelta(1))
    versoes.registrar_atualizacao(sessao, outra, _relato(), agora=AGORA)

    lista = versoes.atualizacoes_da_caixa(sessao, administracao, caixa.caixa_id)

    assert [(registro.resultado, versao.nome) for registro, versao in lista] == [
        ("ok", "0.2.0"), ("voltou", "0.2.0"),
    ]  # fmt: skip


def test_a_lista_das_versoes_conta_as_caixas_em_que_deu_certo(
    sessao: Session, administracao: AcessoAdmin, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    v1 = _versao(sessao, administracao, "0.2.0", RESUMO_1)
    v2 = _versao(sessao, administracao, "0.3.0", RESUMO_2)
    outra = _ativar(sessao, cenario, cenario.site_b.id)
    _provar(sessao, caixa)
    _provar(sessao, outra)
    _provar(sessao, outra)  # a mesma caixa duas vezes conta uma
    terceira = _ativar(sessao, cenario, cenario.site_a2.id)
    versoes.registrar_atualizacao(sessao, terceira, _relato(resultado="voltou"), agora=AGORA)

    lista = versoes.listar_versoes(sessao, administracao)

    assert [(item.versao.id, item.caixas_com_sucesso) for item in lista] == [(v2, 0), (v1, 2)]


# --- As rotas -------------------------------------------------------------------------------


@pytest.fixture
def da_caixa(app: FastAPI, caixa_a: CaixaAtivada) -> TestClient:
    app.dependency_overrides[agora] = lambda: AGORA
    return TestClient(app, headers={"Authorization": f"Bearer {caixa_a.chave}"})


def test_a_caixa_pergunta_a_versao(
    da_caixa: TestClient, sessao: Session, administracao: AcessoAdmin, caixa: AcessoDaCaixa
) -> None:
    assert da_caixa.get("/api/borda/versao").status_code == 204
    versao_id = _versao(sessao, administracao)
    versoes.escolher_versao(sessao, administracao, versao_id, caixa_id=caixa.caixa_id, agora=AGORA)

    resposta = da_caixa.get("/api/borda/versao")

    assert resposta.status_code == 200
    assert resposta.json() == {"nome": "0.2.0", "imagem": f"{IMAGEM}@{RESUMO_1}"}


def test_a_caixa_conta_a_atualizacao_pela_rota(
    da_caixa: TestClient, sessao: Session, administracao: AcessoAdmin
) -> None:
    _versao(sessao, administracao)

    resposta = da_caixa.post("/api/borda/atualizacoes", json=_relato().model_dump(mode="json"))

    assert resposta.status_code == 201, resposta.text
    assert len(list(sessao.scalars(select(AtualizacaoCaixa)))) == 1


def test_atualizacao_desconhecida_pela_rota_responde_422(da_caixa: TestClient) -> None:
    resposta = da_caixa.post("/api/borda/atualizacoes", json=_relato().model_dump(mode="json"))

    assert resposta.status_code == 422


def test_versao_sem_a_chave_responde_401(app: FastAPI) -> None:
    assert TestClient(app).get("/api/borda/versao").status_code == 401


def test_a_administracao_cadastra_e_escolhe_pela_api(
    entrar: Any, cenario: Demonstracao, sessao: Session, caixa: AcessoDaCaixa
) -> None:
    administracao = entrar(cenario.administrador.email)

    criada = administracao.post(
        "/api/admin/versoes", json={"nome": "0.2.0", "imagem": IMAGEM, "resumo": RESUMO_1}
    )
    versao_id = criada.json()["id"]
    para_todas = administracao.post(f"/api/admin/versoes/{versao_id}/escolher", json={})
    para_a_caixa = administracao.post(
        f"/api/admin/versoes/{versao_id}/escolher", json={"caixa_id": caixa.caixa_id}
    )

    assert criada.status_code == 201, criada.text
    assert para_todas.status_code == 409
    assert para_a_caixa.status_code == 201
    repetida = administracao.post(
        "/api/admin/versoes", json={"nome": "0.2.0", "imagem": IMAGEM, "resumo": RESUMO_1}
    )
    assert repetida.status_code == 422


def test_quem_e_do_cliente_nao_mexe_nas_versoes(entrar: Any, cenario: Demonstracao) -> None:
    gestor = entrar(cenario.gestor_a.email)

    resposta = gestor.post(
        "/api/admin/versoes", json={"nome": "0.2.0", "imagem": IMAGEM, "resumo": RESUMO_1}
    )

    assert resposta.status_code == 403

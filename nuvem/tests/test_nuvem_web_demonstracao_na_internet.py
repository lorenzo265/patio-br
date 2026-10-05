"""A demonstração na Vercel, por dentro (T47 parte 2, D-51 e D-56): o tique, o cron diário, a
API da caixa fechada e as fotos no S3."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nuvem.armazenamento import ArmazenamentoS3
from nuvem.cadastro.acesso import AcessoAdmin
from nuvem.cadastro.modelos import Empresa
from nuvem.cifra import Cifra
from nuvem.config import Configuracao
from nuvem.demonstracao import dia, empresa
from nuvem.demonstracao import link as links
from nuvem.demonstracao.empresa import EmpresaDeDemonstracao
from nuvem.mensagens.modelos import Mensagem
from nuvem.principal import criar_app
from nuvem.relogio import agora
from nuvem.semente import Demonstracao
from nuvem.senhas import Senhas
from nuvem.tarefas_de_fundo import TarefaDeFundo

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
SENHA = "senha-da-demonstracao"
SEGREDO_DO_CRON = "segredo-do-cron-de-teste"
CHAVE_QUALQUER = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="


class Relogio:
    """A hora dos pedidos, que o teste adianta."""

    def __init__(self) -> None:
        self.agora = AGORA

    def __call__(self) -> datetime:
        return self.agora


@pytest.fixture
def relogio(app: FastAPI) -> Relogio:
    relogio = Relogio()
    app.dependency_overrides[agora] = relogio
    return relogio


def _configuracao(url_banco_teste: str, tmp_path: Path, **valores: Any) -> Configuracao:
    return Configuracao(
        url_banco=url_banco_teste,
        chave_cifra=CHAVE_QUALQUER,
        ambiente="demonstracao",
        pasta_fotos=tmp_path / "fotos",
        url_publica="https://demonstracao.example",
        _env_file=None,
        **valores,
    )


@pytest.fixture
def vercel(
    app: FastAPI, relogio: Relogio, url_banco_teste: str, senhas: Senhas, tmp_path: Path
) -> FastAPI:
    """A nuvem como na Vercel: ambiente de demonstração, tique e o segredo do cron."""
    configuracao = _configuracao(
        url_banco_teste, tmp_path, tique=True, segredo_do_cron=SEGREDO_DO_CRON
    )
    na_vercel = criar_app(configuracao, senhas=senhas)
    na_vercel.dependency_overrides = app.dependency_overrides
    return na_vercel


@pytest.fixture
def demo(
    sessao: Session, senhas: Senhas, cifra: Cifra, cenario: Demonstracao
) -> EmpresaDeDemonstracao:
    criada = empresa.criar(
        sessao, senhas, cifra, nome="Empresa de demonstração", cnpj="DEMO0000000V00",
        dominio="vercel.demonstracao.example", senha=SENHA, pin="246802",
        administrador_id=cenario.administrador.id, agora=AGORA, dias=1, semente=1,
    )  # fmt: skip
    sessao.commit()
    return criada


def _gestor(
    aplicacao: FastAPI, demo: EmpresaDeDemonstracao, com_csrf: Callable[[TestClient], TestClient]
) -> TestClient:
    cliente = com_csrf(TestClient(aplicacao, base_url="https://testserver"))
    resposta = cliente.post(
        "/entrar", data={"email": demo.gestor.email, "senha": SENHA}, follow_redirects=False
    )
    assert resposta.status_code == 303
    return cliente


def _chegadas(texto: str) -> int:
    trecho = texto.split(" de 24 chegadas")[0]
    return int(trecho.rsplit(" ", 1)[-1])


# --- O tique ----------------------------------------------------------------------------------


def test_o_tique_faz_o_dia_andar_quando_a_tela_se_atualiza(
    vercel: FastAPI,
    relogio: Relogio,
    sessao: Session,
    demo: EmpresaDeDemonstracao,
    com_csrf: Callable[[TestClient], TestClient],
) -> None:
    gestor = _gestor(vercel, demo, com_csrf)
    gestor.post("/demonstracao/comecar", data={"site": demo.site.id})
    relogio.agora = AGORA + timedelta(seconds=30)

    texto = gestor.get(f"/demonstracao?site={demo.site.id}").text

    assert _chegadas(texto) >= 2
    # O tique também casou as passagens (a fila) e preparou as mensagens.
    situacoes = dict(
        sessao.execute(
            select(TarefaDeFundo.situacao, func.count()).group_by(TarefaDeFundo.situacao)
        ).all()
    )
    assert situacoes.get("feita", 0) >= 2
    assert "pendente" not in situacoes
    mensagens = select(func.count()).select_from(Mensagem)
    assert sessao.scalar(mensagens.where(Mensagem.empresa_id == demo.empresa.id))


def test_sem_o_tique_o_dia_espera_o_worker(
    app: FastAPI,
    relogio: Relogio,
    demo: EmpresaDeDemonstracao,
    com_csrf: Callable[[TestClient], TestClient],
) -> None:
    gestor = _gestor(app, demo, com_csrf)
    gestor.post("/demonstracao/comecar", data={"site": demo.site.id})
    relogio.agora = AGORA + timedelta(seconds=30)

    assert _chegadas(gestor.get(f"/demonstracao?site={demo.site.id}").text) == 0


def test_o_tique_so_roda_nas_telas_que_se_atualizam(
    vercel: FastAPI,
    relogio: Relogio,
    demo: EmpresaDeDemonstracao,
    com_csrf: Callable[[TestClient], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gestor = _gestor(vercel, demo, com_csrf)
    voltas: list[datetime] = []
    monkeypatch.setattr(
        dia, "avancar", lambda _sessao, *, agora, armazenamento: voltas.append(agora)
    )

    gestor.get("/")
    gestor.get("/painel")
    gestor.post("/demonstracao/papel", data={"papel": "gestor"}, follow_redirects=False)
    assert voltas == []
    gestor.get(f"/portaria/passagens?site={demo.site.id}")
    gestor.get(f"/patio/quadro?site={demo.site.id}")
    assert len(voltas) == 2


def test_um_erro_no_tique_nao_derruba_a_tela(
    vercel: FastAPI,
    demo: EmpresaDeDemonstracao,
    com_csrf: Callable[[TestClient], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gestor = _gestor(vercel, demo, com_csrf)

    def quebrado(*_argumentos: object, **_nomeados: object) -> int:
        raise RuntimeError("o tique quebrou")

    monkeypatch.setattr(dia, "avancar", quebrado)

    assert gestor.get(f"/demonstracao?site={demo.site.id}").status_code == 200


# --- O cron diário ----------------------------------------------------------------------------


def test_o_cron_sem_o_segredo_e_recusado(vercel: FastAPI) -> None:
    cliente = TestClient(vercel, base_url="https://testserver")

    sem = cliente.get("/api/cron/diaria")
    errado = cliente.get("/api/cron/diaria", headers={"Authorization": "Bearer outro"})

    assert (sem.status_code, errado.status_code) == (401, 401)


def test_sem_segredo_configurado_o_cron_nao_existe(app: FastAPI) -> None:
    resposta = TestClient(app).get(
        "/api/cron/diaria", headers={"Authorization": f"Bearer {SEGREDO_DO_CRON}"}
    )

    assert resposta.status_code == 404


def test_o_cron_apaga_as_empresas_dos_links_vencidos(
    vercel: FastAPI,
    sessao: Session,
    senhas: Senhas,
    cifra: Cifra,
    cenario: Demonstracao,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(empresa, "DIAS_DE_HISTORICO", 1)
    administracao = AcessoAdmin(cenario.administrador.id)
    gerado = links.gerar_link(sessao, administracao, nome="Vencida", agora=AGORA)
    links.entrar_pelo_link(sessao, senhas, cifra, gerado.codigo, agora=AGORA)
    links.revogar_link(sessao, administracao, gerado.link.id, agora=AGORA)
    empresa_id = gerado.link.empresa_id
    sessao.commit()

    resposta = TestClient(vercel, base_url="https://testserver").get(
        "/api/cron/diaria", headers={"Authorization": f"Bearer {SEGREDO_DO_CRON}"}
    )

    assert resposta.status_code == 200
    assert resposta.json()["empresas_apagadas"] == 1
    sessao.expire_all()
    assert sessao.get(Empresa, empresa_id) is None


# --- A API da caixa e as fotos ----------------------------------------------------------------


def test_na_demonstracao_a_api_da_caixa_nao_existe(vercel: FastAPI, app: FastAPI) -> None:
    corpo = {"codigo": "XXXX-XXXX-XXXX"}

    na_vercel = TestClient(vercel, base_url="https://testserver").post(
        "/api/borda/ativar", json=corpo
    )
    no_local = TestClient(app).post("/api/borda/ativar", json=corpo)

    assert (na_vercel.status_code, no_local.status_code) == (404, 401)


def test_com_o_s3_configurado_as_fotos_vao_para_ele(
    url_banco_teste: str, senhas: Senhas, tmp_path: Path
) -> None:
    configuracao = _configuracao(
        url_banco_teste, tmp_path,
        fotos_s3_endereco="https://projeto.storage.supabase.co/storage/v1/s3",
        fotos_s3_regiao="sa-east-1", fotos_s3_chave="chave", fotos_s3_segredo="segredo",
    )  # fmt: skip
    with mock_aws():
        aplicacao = criar_app(configuracao, senhas=senhas)

    assert isinstance(aplicacao.state.armazenamento, ArmazenamentoS3)

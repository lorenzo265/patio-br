"""A saúde da caixa na nuvem (SDD 7.4, D-65): o último contato, o histórico e a frota."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.saude import Saude
from nuvem.cadastro.acesso import Acesso, AcessoAdmin
from nuvem.erros import NaoEncontradoError
from nuvem.frota import saude as frota
from nuvem.frota import servico
from nuvem.frota.modelos import CaixaBorda, SaudeCaixa
from nuvem.frota.saude import SaudeDeOutraCaixaError
from nuvem.frota.servico import AcessoDaCaixa, CaixaAtivada
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 6, 17, 0, tzinfo=UTC)
"""14:00 em São Paulo, o fuso dos sites da demonstração."""


def _saude(caixa: AcessoDaCaixa, **mudancas: Any) -> Saude:
    dados: dict[str, Any] = {
        "versao_contrato": 1,
        "caixa_id": str(caixa.caixa_id),
        "site_id": str(caixa.site_id),
        "momento": AGORA.isoformat(),
        "versao_programa": "0.1.0",
        "versao_leitor": "v0",
        "cpu": 30.0,
        "temperatura": 55.0,
        "memoria": 40.0,
        "disco": 10.0,
        "cameras": [
            {
                "camera_id": "21",
                "no_ar": True,
                "quadros_por_segundo": 5.0,
                "ultimo_quadro": AGORA.isoformat(),
            },
            {"camera_id": "22", "no_ar": False, "quadros_por_segundo": 0, "ultimo_quadro": None},
        ],
        "fila": {"passagens": 3, "fotos": 4, "recusadas": 1},
    }
    dados.update(mudancas)
    return Saude.model_validate(dados)


def _acesso(sessao: Session, ativada: CaixaAtivada) -> AcessoDaCaixa:
    caixa = servico.caixa_da_chave(sessao, ativada.chave)
    assert caixa is not None
    return caixa


def _ativar(sessao: Session, cenario: Demonstracao, site_id: int) -> AcessoDaCaixa:
    gerado = servico.gerar_codigo_de_ativacao(
        sessao, site_id, administrador_id=cenario.administrador.id, agora=AGORA
    )
    return _acesso(sessao, servico.ativar(sessao, gerado.codigo, agora=AGORA))


@pytest.fixture
def caixa(sessao: Session, caixa_a: CaixaAtivada) -> AcessoDaCaixa:
    return _acesso(sessao, caixa_a)


@pytest.fixture
def administracao(cenario: Demonstracao) -> AcessoAdmin:
    return AcessoAdmin(administrador_id=cenario.administrador.id)


def _receber(sessao: Session, caixa: AcessoDaCaixa, recebida: datetime, **mudancas: Any) -> None:
    # Sem dizer, a caixa está com o relógio certo.
    mudancas.setdefault("momento", recebida.isoformat())
    frota.receber_saude(sessao, caixa, _saude(caixa, **mudancas), agora=recebida)


def _historico(sessao: Session, caixa: AcessoDaCaixa) -> list[SaudeCaixa]:
    return list(
        sessao.scalars(
            select(SaudeCaixa)
            .where(SaudeCaixa.caixa_id == caixa.caixa_id)
            .order_by(SaudeCaixa.recebida_em)
        )
    )


# --- Receber --------------------------------------------------------------------------------


def test_a_saude_atualiza_a_caixa(sessao: Session, caixa: AcessoDaCaixa) -> None:
    saude = _saude(caixa, momento=(AGORA + timedelta(seconds=1.5)).isoformat())

    frota.receber_saude(sessao, caixa, saude, agora=AGORA)

    registro = sessao.get(CaixaBorda, caixa.caixa_id)
    assert registro is not None
    assert registro.ultimo_contato == AGORA
    assert (registro.versao_programa, registro.versao_leitor) == ("0.1.0", "v0")
    assert registro.ultima_saude == saude.model_dump(mode="json")
    assert registro.diferenca_do_relogio == 1.5


def test_o_relogio_atrasado_da_diferenca_negativa(sessao: Session, caixa: AcessoDaCaixa) -> None:
    _receber(sessao, caixa, AGORA, momento=(AGORA - timedelta(seconds=4)).isoformat())

    registro = sessao.get(CaixaBorda, caixa.caixa_id)
    assert registro is not None
    assert registro.diferenca_do_relogio == -4


def test_a_saude_entra_no_historico(
    sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    saude = _saude(caixa, momento=(AGORA + timedelta(seconds=2)).isoformat())

    frota.receber_saude(sessao, caixa, saude, agora=AGORA)

    (linha,) = _historico(sessao, caixa)
    assert (linha.empresa_id, linha.recebida_em, linha.momento) == (
        cenario.empresa_a.id,
        AGORA,
        AGORA + timedelta(seconds=2),
    )
    assert (linha.cpu, linha.temperatura, linha.memoria, linha.disco) == (30, 55, 40, 10)
    assert (linha.cameras_no_ar, linha.cameras, linha.passagens_na_fila) == (1, 2, 3)
    assert linha.diferenca_do_relogio == 2
    assert linha.dados == saude.model_dump(mode="json")


def test_a_ultima_saude_fica_na_caixa(sessao: Session, caixa: AcessoDaCaixa) -> None:
    _receber(sessao, caixa, AGORA, versao_programa="0.1.0")
    _receber(sessao, caixa, AGORA + timedelta(minutes=1), versao_programa="0.2.0")

    registro = sessao.get(CaixaBorda, caixa.caixa_id)
    assert registro is not None
    assert (registro.ultimo_contato, registro.versao_programa) == (
        AGORA + timedelta(minutes=1),
        "0.2.0",
    )
    assert len(_historico(sessao, caixa)) == 2


@pytest.mark.parametrize("campo", ["caixa_id", "site_id"])
def test_a_saude_de_outra_caixa_ou_de_outro_site_e_recusada(
    sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa, campo: str
) -> None:
    outro = {"caixa_id": str(caixa.caixa_id + 1), "site_id": str(cenario.site_b.id)}[campo]

    with pytest.raises(SaudeDeOutraCaixaError):
        _receber(sessao, caixa, AGORA, **{campo: outro})

    registro = sessao.get(CaixaBorda, caixa.caixa_id)
    assert registro is not None
    assert registro.ultimo_contato is None
    assert _historico(sessao, caixa) == []


def test_o_historico_guarda_7_dias(sessao: Session, caixa: AcessoDaCaixa) -> None:
    sete_dias = timedelta(days=7)
    _receber(sessao, caixa, AGORA - sete_dias - timedelta(seconds=1))
    _receber(sessao, caixa, AGORA - sete_dias)

    _receber(sessao, caixa, AGORA)

    assert [linha.recebida_em for linha in _historico(sessao, caixa)] == [AGORA - sete_dias, AGORA]


def test_o_historico_de_outra_caixa_fica_para_quando_ela_mandar(
    sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    outra = _ativar(sessao, cenario, cenario.site_a.id)  # da mesma empresa
    _receber(sessao, outra, AGORA - timedelta(days=8))

    _receber(sessao, caixa, AGORA)

    assert len(_historico(sessao, outra)) == 1


# --- A portaria: "site sem conexão desde HH:MM" ---------------------------------------------


def test_o_site_fica_sem_conexao_depois_de_3_minutos(
    sessao: Session, acesso_a: Acesso, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    _receber(sessao, caixa, AGORA)
    site = cenario.site_a.id

    antes = frota.sem_conexao_desde(sessao, acesso_a, site, agora=AGORA + timedelta(seconds=179))
    depois = frota.sem_conexao_desde(sessao, acesso_a, site, agora=AGORA + timedelta(minutes=3))

    assert (antes, depois) == (None, AGORA)


def test_a_caixa_que_nunca_mandou_saude_nao_deixa_o_site_sem_conexao(
    sessao: Session, acesso_a: Acesso, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    momento = AGORA + timedelta(days=1)

    assert frota.sem_conexao_desde(sessao, acesso_a, cenario.site_a.id, agora=momento) is None


def test_site_sem_caixa_nao_fica_sem_conexao(
    sessao: Session, acesso_b: Acesso, cenario: Demonstracao
) -> None:
    assert frota.sem_conexao_desde(sessao, acesso_b, cenario.site_b.id, agora=AGORA) is None


def test_a_caixa_revogada_nao_conta(
    sessao: Session, acesso_a: Acesso, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    _receber(sessao, caixa, AGORA)
    servico.revogar(sessao, caixa.caixa_id, agora=AGORA)
    momento = AGORA + timedelta(minutes=10)

    assert frota.sem_conexao_desde(sessao, acesso_a, cenario.site_a.id, agora=momento) is None


def test_com_duas_caixas_vale_a_que_sumiu(
    sessao: Session, acesso_a: Acesso, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    outra = _ativar(sessao, cenario, cenario.site_a.id)
    _receber(sessao, caixa, AGORA)
    _receber(sessao, outra, AGORA + timedelta(minutes=2))
    site = cenario.site_a.id

    so_uma = frota.sem_conexao_desde(sessao, acesso_a, site, agora=AGORA + timedelta(minutes=4))
    as_duas = frota.sem_conexao_desde(sessao, acesso_a, site, agora=AGORA + timedelta(minutes=9))

    assert (so_uma, as_duas) == (AGORA, AGORA)


def test_a_caixa_de_outro_site_da_empresa_nao_conta(
    sessao: Session, acesso_a: Acesso, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    ao_lado = _ativar(sessao, cenario, cenario.site_a2.id)
    _receber(sessao, ao_lado, AGORA)
    momento = AGORA + timedelta(minutes=10)

    assert frota.sem_conexao_desde(sessao, acesso_a, cenario.site_a.id, agora=momento) is None


def test_a_caixa_do_site_de_outra_empresa_nao_conta(
    sessao: Session, acesso_b: Acesso, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    _receber(sessao, caixa, AGORA)

    with pytest.raises(NaoEncontradoError):
        frota.sem_conexao_desde(sessao, acesso_b, cenario.site_a.id, agora=AGORA)


# --- A frota da administração ---------------------------------------------------------------


def test_a_frota_mostra_cada_caixa_com_a_saude(
    sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa, administracao: AcessoAdmin
) -> None:
    outra = _ativar(sessao, cenario, cenario.site_b.id)
    cameras = [
        {"camera_id": str(cenario.camera_a.id), "no_ar": True, "quadros_por_segundo": 4.8,
         "ultimo_quadro": AGORA.isoformat()},
        {"camera_id": "999999", "no_ar": False, "quadros_por_segundo": 0, "ultimo_quadro": None},
        # A câmera de outra empresa não empresta o nome.
        {"camera_id": str(cenario.camera_b.id), "no_ar": False, "quadros_por_segundo": 0,
         "ultimo_quadro": None},
    ]  # fmt: skip
    _receber(sessao, caixa, AGORA, cameras=cameras)

    lista = frota.frota(sessao, administracao, agora=AGORA + timedelta(minutes=1))

    assert [item.caixa_id for item in lista] == [outra.caixa_id, caixa.caixa_id]
    nova, com_saude = lista
    assert (nova.empresa, nova.site, nova.ultimo_contato, nova.saude) == (
        "Empresa B (demonstração)", "CD Outra Empresa", None, None,
    )  # fmt: skip
    assert not nova.sem_contato
    assert (com_saude.empresa, com_saude.site) == ("Empresa A (demonstração)", "CD Exemplo")
    assert com_saude.ultimo_contato == AGORA
    assert not com_saude.sem_contato
    assert com_saude.saude == _saude(caixa, cameras=cameras)
    assert [(c.nome, c.no_ar) for c in com_saude.cameras] == [
        ("Entrada 1 — frente", True),
        ("câmera 999999", False),
        (f"câmera {cenario.camera_b.id}", False),
    ]


def test_a_frota_marca_a_caixa_sem_contato(
    sessao: Session, caixa: AcessoDaCaixa, administracao: AcessoAdmin
) -> None:
    _receber(sessao, caixa, AGORA)

    (item,) = frota.frota(sessao, administracao, agora=AGORA + timedelta(minutes=3))

    assert item.sem_contato


def test_a_caixa_revogada_sai_da_frota(
    sessao: Session, caixa: AcessoDaCaixa, administracao: AcessoAdmin
) -> None:
    servico.revogar(sessao, caixa.caixa_id, agora=AGORA)

    assert frota.frota(sessao, administracao, agora=AGORA) == []


def test_o_historico_hora_a_hora_no_fuso_do_site(
    sessao: Session, caixa: AcessoDaCaixa, administracao: AcessoAdmin
) -> None:
    # 14:05, 14:10 e 15:30 em São Paulo; e uma de 8 dias atrás, que já não aparece.
    _receber(sessao, caixa, AGORA - timedelta(days=8))
    paradas = [
        {"camera_id": numero, "no_ar": False, "quadros_por_segundo": 0, "ultimo_quadro": None}
        for numero in ("21", "22")
    ]
    _receber(sessao, caixa, AGORA + timedelta(minutes=5), cpu=20.0, temperatura=50.0,
             fila={"passagens": 7, "fotos": 0, "recusadas": 0}, cameras=paradas)  # fmt: skip
    _receber(sessao, caixa, AGORA + timedelta(minutes=10), cpu=60.0, disco=12.0,
             momento=(AGORA + timedelta(minutes=10, seconds=-3)).isoformat())  # fmt: skip
    _receber(sessao, caixa, AGORA + timedelta(minutes=90), temperatura=70.0,
             cameras=[])  # fmt: skip

    horas = frota.historico_por_hora(
        sessao, administracao, caixa.caixa_id, agora=AGORA + timedelta(hours=2)
    )

    assert [(h.hora.isoformat(), h.contatos) for h in horas] == [
        ("2026-10-06T15:00:00-03:00", 1),
        ("2026-10-06T14:00:00-03:00", 2),
    ]
    quinze, catorze = horas
    assert (catorze.cpu, catorze.temperatura, catorze.disco) == (60, 55, 12)
    assert (catorze.cameras_no_ar, catorze.cameras, catorze.passagens_na_fila) == (0, 2, 7)
    assert catorze.diferenca_do_relogio == -3
    assert (quinze.temperatura, quinze.cameras_no_ar, quinze.cameras) == (70, 0, 0)


def test_o_historico_da_caixa_que_parou_de_mandar_mostra_so_7_dias(
    sessao: Session, caixa: AcessoDaCaixa, administracao: AcessoAdmin
) -> None:
    _receber(sessao, caixa, AGORA - timedelta(days=7, seconds=1))

    assert frota.historico_por_hora(sessao, administracao, caixa.caixa_id, agora=AGORA) == []


def test_o_historico_e_so_da_caixa_pedida(
    sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa, administracao: AcessoAdmin
) -> None:
    outra = _ativar(sessao, cenario, cenario.site_a.id)
    _receber(sessao, outra, AGORA)

    assert frota.historico_por_hora(sessao, administracao, caixa.caixa_id, agora=AGORA) == []


def test_o_historico_de_caixa_que_nao_existe(sessao: Session, administracao: AcessoAdmin) -> None:
    with pytest.raises(NaoEncontradoError):
        frota.historico_por_hora(sessao, administracao, 999999, agora=AGORA)
    with pytest.raises(NaoEncontradoError):
        frota.caixa_da_frota(sessao, administracao, 999999, agora=AGORA)


# --- A rota da caixa ------------------------------------------------------------------------


@pytest.fixture
def chamada(app: FastAPI, caixa_a: CaixaAtivada) -> TestClient:
    app.dependency_overrides[agora] = lambda: AGORA
    return TestClient(app, headers={"Authorization": f"Bearer {caixa_a.chave}"})


def test_a_caixa_manda_a_saude(chamada: TestClient, sessao: Session, caixa: AcessoDaCaixa) -> None:
    resposta = chamada.post("/api/borda/saude", json=_saude(caixa).model_dump(mode="json"))

    assert resposta.status_code == 204, resposta.text
    sessao.expire_all()
    registro = sessao.get(CaixaBorda, caixa.caixa_id)
    assert registro is not None
    assert registro.ultimo_contato == AGORA


def test_saude_sem_a_chave_responde_401(app: FastAPI, caixa: AcessoDaCaixa) -> None:
    resposta = TestClient(app).post("/api/borda/saude", json=_saude(caixa).model_dump(mode="json"))

    assert resposta.status_code == 401


def test_saude_de_outra_caixa_responde_403(chamada: TestClient, caixa: AcessoDaCaixa) -> None:
    corpo = _saude(caixa, caixa_id=str(caixa.caixa_id + 1)).model_dump(mode="json")

    resposta = chamada.post("/api/borda/saude", json=corpo)

    assert resposta.status_code == 403


def test_saude_fora_do_formato_responde_422(chamada: TestClient, caixa: AcessoDaCaixa) -> None:
    corpo = _saude(caixa).model_dump(mode="json") | {"cpu": 101}

    assert chamada.post("/api/borda/saude", json=corpo).status_code == 422


def test_a_api_da_administracao_mostra_o_ultimo_contato(
    entrar: Any, cenario: Demonstracao, chamada: TestClient, caixa: AcessoDaCaixa
) -> None:
    chamada.post("/api/borda/saude", json=_saude(caixa).model_dump(mode="json"))

    (publica,) = entrar(cenario.administrador.email).get("/api/admin/caixas").json()

    assert publica["ultimo_contato"] == "2026-10-06T17:00:00Z"
    assert (publica["versao_programa"], publica["versao_leitor"]) == ("0.1.0", "v0")

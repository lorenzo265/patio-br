"""Tela de agendamentos (SDD 6.2): o gestor vê e alimenta os agendamentos dos sites dele."""

import io
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import openpyxl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from nuvem.agendamento import link as links
from nuvem.agendamento import servico
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento, LinkTransportadora
from nuvem.cadastro.acesso import Acesso
from nuvem.relogio import agora
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

AGORA = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)
"""15h de 04/11 em São Paulo: o "hoje" da tela."""


@pytest.fixture(autouse=True)
def _hora_fixa(app: FastAPI) -> None:
    app.dependency_overrides[agora] = lambda: AGORA


def _gravar(
    sessao: Session, acesso: Acesso, site_id: int, codigo: str, inicio: datetime, **mais: object
) -> Agendamento:
    destino = servico.site_para_agendar(sessao, acesso, site_id)
    dados = DadosDoAgendamento.model_validate(
        {
            "codigo_externo": codigo,
            "janela_inicio": inicio,
            "janela_fim": inicio + timedelta(hours=2),
            "tipo": "descarga",
            "placa_cavalo": "ABC1D23",
            **mais,
        }
    )
    return servico.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento


@pytest.fixture
def agenda(sessao: Session, cenario: Demonstracao, acesso_a: Acesso) -> dict[str, Agendamento]:
    """Hoje às 17h e amanhã às 8h (hora de São Paulo), no site_a."""
    site = cenario.site_a.id
    return {
        "hoje": _gravar(
            sessao, acesso_a, site, "HOJE-1", datetime(2026, 11, 4, 20, tzinfo=UTC),
            motorista_nome="Motorista <Inventado>", motorista_celular="11987654321",
            toneladas="32.5",
        ),
        "amanha": _gravar(
            sessao, acesso_a, site, "AMANHA-1", datetime(2026, 11, 5, 11, tzinfo=UTC)
        ),
    }  # fmt: skip


# --- Quem vê ----------------------------------------------------------------------------------


def test_sem_login_vai_para_a_tela_de_entrar(app: FastAPI) -> None:
    resposta = TestClient(app).get("/agendamentos", follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


def test_so_o_gestor_ve_a_tela(entrar: Entrar, cenario: Demonstracao) -> None:
    for pessoa in (cenario.porteiro_a, cenario.patio_a):
        assert entrar(pessoa.email).get("/agendamentos").status_code == 403


def test_site_de_outra_empresa_responde_404(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = entrar(cenario.gestor_a.email).get(f"/agendamentos?site={cenario.site_b.id}")

    assert resposta.status_code == 404


def test_o_inicio_do_gestor_leva_aos_agendamentos(entrar: Entrar, cenario: Demonstracao) -> None:
    assert 'href="/agendamentos"' in entrar(cenario.gestor_a.email).get("/").text
    assert 'href="/agendamentos"' not in entrar(cenario.porteiro_a.email).get("/").text


# --- A lista ----------------------------------------------------------------------------------


def test_lista_de_hoje_no_fuso_do_site(
    entrar: Entrar, cenario: Demonstracao, agenda: dict[str, Agendamento]
) -> None:
    resposta = entrar(cenario.gestor_a.email).get("/agendamentos")

    assert resposta.status_code == 200
    assert cenario.site_a.nome in resposta.text
    assert "04/11/2026" in resposta.text
    assert "HOJE-1" in resposta.text
    assert "17:00 às 19:00" in resposta.text  # 20h UTC = 17h em São Paulo
    assert "AMANHA-1" not in resposta.text
    assert "Motorista &lt;Inventado&gt;" in resposta.text
    assert "(11) 98765-4321" in resposta.text
    assert "32,5" in resposta.text


def test_lista_de_outro_dia(
    entrar: Entrar, cenario: Demonstracao, agenda: dict[str, Agendamento]
) -> None:
    resposta = entrar(cenario.gestor_a.email).get("/agendamentos?dia=2026-11-05")

    assert "AMANHA-1" in resposta.text
    assert "HOJE-1" not in resposta.text
    assert 'href="/agendamentos?site=' in resposta.text  # navegação entre os dias


def test_lista_da_semana_traz_os_7_dias(
    entrar: Entrar, cenario: Demonstracao, agenda: dict[str, Agendamento]
) -> None:
    resposta = entrar(cenario.gestor_a.email).get("/agendamentos?dia=2026-11-04&dias=7")

    assert "HOJE-1" in resposta.text
    assert "AMANHA-1" in resposta.text
    assert "04/11/2026 a 10/11/2026" in resposta.text


@pytest.mark.parametrize("consulta", ["dia=amanha", "dias=3", "dias=0"])
def test_dia_ou_periodo_fora_da_regra_responde_422(
    entrar: Entrar, cenario: Demonstracao, consulta: str
) -> None:
    assert entrar(cenario.gestor_a.email).get(f"/agendamentos?{consulta}").status_code == 422


# --- Cancelar ---------------------------------------------------------------------------------


def test_cancelar_pela_tela(
    entrar: Entrar, sessao: Session, cenario: Demonstracao, acesso_a: Acesso,
    agenda: dict[str, Agendamento],
) -> None:  # fmt: skip
    gestor = entrar(cenario.gestor_a.email)
    alvo = agenda["hoje"]

    resposta = gestor.post(f"/agendamentos/{alvo.id}/cancelar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == f"/agendamentos?site={cenario.site_a.id}&dia=2026-11-04"
    sessao.expire_all()
    assert servico.obter(sessao, acesso_a, alvo.id).situacao == "cancelado"
    assert "cancelado" in gestor.get(resposta.headers["location"]).text


def test_cancelar_agendamento_de_outra_empresa_responde_404(
    entrar: Entrar, cenario: Demonstracao, agenda: dict[str, Agendamento]
) -> None:
    resposta = entrar(cenario.gestor_b.email).post(f"/agendamentos/{agenda['hoje'].id}/cancelar")

    assert resposta.status_code == 404


# --- Planilha ---------------------------------------------------------------------------------


def _subir(cliente: TestClient, site_id: int, conteudo: bytes, nome: str = "agenda.csv") -> object:
    return cliente.post(
        f"/agendamentos/planilha?site={site_id}",
        files={"arquivo": (nome, conteudo, "text/csv")},
    )


def test_importar_pela_tela_mostra_o_relatorio(
    entrar: Entrar, sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    conteudo = (
        "código;dia;início;fim;tipo;placa do cavalo\n"
        "AG-1;05/11/2026;08:00;10:00;descarga;ABC1D23\n"
        "AG-2;05/11/2026;09:00;11:00;carga;ABC12\n"
    ).encode()

    resposta = _subir(entrar(cenario.gestor_a.email), cenario.site_a.id, conteudo)

    assert resposta.status_code == 200  # type: ignore[attr-defined]
    texto = resposta.text  # type: ignore[attr-defined]
    assert "1 novo" in texto
    assert "linha 3" in texto
    assert "placa inválida: &#39;ABC12&#39;" in texto
    destino = servico.site_para_agendar(sessao, acesso_a, cenario.site_a.id)
    assert servico.obter_por_codigo(sessao, destino, "planilha", "AG-1").placa_cavalo == "ABC1D23"


def test_planilha_que_nao_serve_mostra_o_motivo(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = _subir(entrar(cenario.gestor_a.email), cenario.site_a.id, b"x", "agenda.xls")

    assert resposta.status_code == 422  # type: ignore[attr-defined]
    assert "a planilha precisa ser .csv ou .xlsx" in resposta.text  # type: ignore[attr-defined]


def test_importar_em_site_de_outra_empresa_responde_404(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    resposta = _subir(entrar(cenario.gestor_a.email), cenario.site_b.id, b"")

    assert resposta.status_code == 404  # type: ignore[attr-defined]


def test_baixar_os_modelos(entrar: Entrar, cenario: Demonstracao) -> None:
    gestor = entrar(cenario.gestor_a.email)

    csv = gestor.get("/agendamentos/modelo.csv")
    xlsx = gestor.get("/agendamentos/modelo.xlsx")

    assert csv.status_code == xlsx.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert 'filename="modelo-agendamentos.csv"' in csv.headers["content-disposition"]
    assert csv.content.decode("utf-8-sig").startswith("código;dia;início;fim")
    pasta = openpyxl.load_workbook(io.BytesIO(xlsx.content))
    assert pasta.sheetnames == ["agenda", "exemplo"]


def test_modelos_tambem_so_para_o_gestor(entrar: Entrar, cenario: Demonstracao) -> None:
    assert entrar(cenario.porteiro_a.email).get("/agendamentos/modelo.csv").status_code == 403


# --- Links ------------------------------------------------------------------------------------


def test_gerar_link_mostra_o_endereco_uma_vez(
    entrar: Entrar, sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    gestor = entrar(cenario.gestor_a.email)

    resposta = gestor.post(
        f"/agendamentos/links?site={cenario.site_a.id}",
        data={"nome": "Transportadora Inventada", "dias": "15", "limite": "20"},
    )

    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == "no-store"
    endereco = re.search(r"http://testserver/agendar/[A-Za-z0-9_-]+", resposta.text)
    assert endereco is not None
    [link] = links.listar_links(sessao, acesso_a, cenario.site_a.id)
    assert (link.nome, link.limite_de_envios) == ("Transportadora Inventada", 20)
    assert link.vence_em == AGORA + timedelta(days=15)
    # O endereço funciona, e não aparece de novo na tela.
    assert gestor.get(endereco[0].removeprefix("http://testserver")).status_code == 200
    assert endereco[0] not in gestor.get("/agendamentos").text


def test_gerar_link_com_valores_fora_da_regra_mostra_o_motivo(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    resposta = entrar(cenario.gestor_a.email).post(
        f"/agendamentos/links?site={cenario.site_a.id}",
        data={"nome": "Transportadora", "dias": "500", "limite": "20"},
    )

    assert resposta.status_code == 422
    assert "o link vale de 1 a 180 dias" in resposta.text


def test_a_tela_mostra_a_situacao_de_cada_link(
    entrar: Entrar, sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    site = cenario.site_a.id
    ativo = links.gerar_link(sessao, acesso_a, site, nome="Ativo", agora=AGORA)
    revogado = links.gerar_link(sessao, acesso_a, site, nome="Revogado", agora=AGORA)
    links.revogar_link(sessao, acesso_a, revogado.link.id, agora=AGORA)
    esgotado = links.gerar_link(sessao, acesso_a, site, nome="Esgotado", agora=AGORA, limite=1)
    esgotado.link.envios = 1
    vencido = links.gerar_link(
        sessao, acesso_a, site, nome="Vencido", agora=AGORA - timedelta(days=2),
        validade=timedelta(days=1),
    )  # fmt: skip
    sessao.flush()

    texto = entrar(cenario.gestor_a.email).get("/agendamentos").text

    for link, situacao in (
        (ativo.link, "ativo"),
        (revogado.link, "revogado"),
        (esgotado.link, "esgotado"),
        (vencido.link, "vencido"),
    ):
        assert re.search(rf"{link.nome}</td>.*?<td>{situacao}</td>", texto, re.DOTALL), link.nome


def test_revogar_link_pela_tela(
    entrar: Entrar, sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    gerado = links.gerar_link(sessao, acesso_a, cenario.site_a.id, nome="Uma", agora=AGORA)

    resposta = entrar(cenario.gestor_a.email).post(
        f"/agendamentos/links/{gerado.link.id}/revogar", follow_redirects=False
    )

    assert resposta.status_code == 303
    sessao.expire_all()
    assert sessao.get(LinkTransportadora, gerado.link.id).revogado_em == AGORA  # type: ignore[union-attr]


def test_revogar_link_de_outra_empresa_responde_404(
    entrar: Entrar, sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    gerado = links.gerar_link(sessao, acesso_a, cenario.site_a.id, nome="Uma", agora=AGORA)

    resposta = entrar(cenario.gestor_b.email).post(f"/agendamentos/links/{gerado.link.id}/revogar")

    assert resposta.status_code == 404


def test_hoje_e_o_dia_no_fuso_do_site(
    app: FastAPI, entrar: Entrar, cenario: Demonstracao, agenda: dict[str, Agendamento]
) -> None:
    # 1h de 05/11 em UTC ainda é 22h de 04/11 em São Paulo.
    app.dependency_overrides[agora] = lambda: datetime(2026, 11, 5, 1, 0, tzinfo=UTC)

    resposta = entrar(cenario.gestor_a.email).get("/agendamentos")

    assert "<h2>04/11/2026</h2>" in resposta.text
    assert "HOJE-1" in resposta.text

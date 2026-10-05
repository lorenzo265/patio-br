"""Importar a planilha no banco e pela API (SDD 3.4): só o gestor, só nos sites dele."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from nuvem.agendamento import servico
from nuvem.agendamento.planilha import Planilha, PlanilhaInvalidaError, importar_planilha
from nuvem.cadastro.acesso import Acesso
from nuvem.erros import NaoEncontradoError
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

AGORA = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)
CABECALHO = "código;dia;início;fim;tipo;placa do cavalo;toneladas"


def _planilha(*linhas: str) -> Planilha:
    return Planilha(nome="agenda.csv", conteudo="\n".join((CABECALHO, *linhas)).encode())


def test_importar_grava_e_relata_por_linha(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    planilha = _planilha(
        "AG-1;05/11/2026;08:00;10:00;descarga;ABC1D23;30",
        "AG-2;05/11/2026;09:00;11:00;carga;ABC12;10",
        "AG-3;05/11/2026;10:00;12:00;carga;XYZ9K87;12",
    )

    relatorio = importar_planilha(sessao, acesso_a, cenario.site_a.id, planilha, agora=AGORA)

    assert (relatorio.criados, relatorio.alterados, relatorio.iguais) == (2, 0, 0)
    assert [(r.onde, r.motivo.split(":")[0]) for r in relatorio.recusados] == [
        ("linha 3", "placa do cavalo")
    ]
    lista = servico.listar(
        sessao, acesso_a, cenario.site_a.id, de=AGORA, ate=AGORA + timedelta(days=2)
    )
    assert [(a.codigo_externo, a.origem) for a in lista] == [
        ("AG-1", "planilha"),
        ("AG-3", "planilha"),
    ]


def test_reimportar_a_mesma_planilha_corrigida_nao_duplica(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    importar_planilha(
        sessao,
        acesso_a,
        cenario.site_a.id,
        _planilha("AG-1;05/11/2026;08:00;10:00;descarga;ABC1D23;30"),
        agora=AGORA,
    )

    relatorio = importar_planilha(
        sessao,
        acesso_a,
        cenario.site_a.id,
        _planilha(
            "AG-1;05/11/2026;08:00;10:00;descarga;ABC1D23;31",
            "AG-2;05/11/2026;09:00;11:00;carga;XYZ9K87;12",
        ),
        agora=AGORA + timedelta(hours=1),
    )

    assert (relatorio.criados, relatorio.alterados, relatorio.iguais) == (1, 1, 0)
    agendamento = servico.obter_por_codigo(
        sessao, servico.site_para_agendar(sessao, acesso_a, cenario.site_a.id), "planilha", "AG-1"
    )
    assert str(agendamento.toneladas) == "31.000"


def test_importar_em_site_fora_do_alcance_nao_encontra(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    with pytest.raises(NaoEncontradoError):
        importar_planilha(sessao, acesso_a, cenario.site_b.id, _planilha(), agora=AGORA)


def test_planilha_sem_coluna_obrigatoria_nao_grava_nada(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    planilha = Planilha(nome="agenda.csv", conteudo=b"codigo;placa\nAG-1;ABC1D23")

    with pytest.raises(PlanilhaInvalidaError):
        importar_planilha(sessao, acesso_a, cenario.site_a.id, planilha, agora=AGORA)


# --- Pela API ---------------------------------------------------------------------------------


def _subir(cliente: TestClient, site_id: int, conteudo: bytes, nome: str = "agenda.csv") -> object:
    return cliente.post(
        "/api/agendamentos/planilha",
        params={"site_id": site_id},
        files={"arquivo": (nome, conteudo, "text/csv")},
    )


def test_gestor_sobe_a_planilha_e_recebe_o_relatorio(entrar: Entrar, cenario: Demonstracao) -> None:
    conteudo = "\n".join(
        (
            CABECALHO,
            "AG-1;05/11/2026;08:00;10:00;descarga;ABC1D23;30",
            "AG-2;05/11/2026;09:00;11:00;carga;ABC12;10",
        )
    ).encode()

    resposta = _subir(entrar(cenario.gestor_a.email), cenario.site_a.id, conteudo)

    assert resposta.status_code == 200  # type: ignore[attr-defined]
    corpo = resposta.json()  # type: ignore[attr-defined]
    assert (corpo["criados"], corpo["alterados"], corpo["iguais"]) == (1, 0, 0)
    assert corpo["recusados"] == [
        {
            "onde": "linha 3",
            "motivo": "placa do cavalo: placa inválida: 'ABC12' "
            "(formatos aceitos: ABC1234 e ABC1D23)",
        }
    ]


def test_o_que_a_api_importou_fica_gravado(
    entrar: Entrar, sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    conteudo = f"{CABECALHO}\nAG-1;05/11/2026;08:00;10:00;descarga;ABC1D23;30".encode()

    _subir(entrar(cenario.gestor_a.email), cenario.site_a.id, conteudo)

    destino = servico.site_para_agendar(sessao, acesso_a, cenario.site_a.id)
    assert servico.obter_por_codigo(sessao, destino, "planilha", "AG-1").placa_cavalo == "ABC1D23"


def test_so_o_gestor_sobe_planilha(entrar: Entrar, cenario: Demonstracao) -> None:
    resposta = _subir(entrar(cenario.porteiro_a.email), cenario.site_a.id, b"")

    assert resposta.status_code == 403  # type: ignore[attr-defined]


def test_sem_login_responde_401(app: FastAPI, cenario: Demonstracao) -> None:
    assert _subir(TestClient(app), cenario.site_a.id, b"").status_code == 401  # type: ignore[attr-defined]


def test_site_de_outra_empresa_responde_404(entrar: Entrar, cenario: Demonstracao) -> None:
    conteudo = f"{CABECALHO}\nAG-1;05/11/2026;08:00;10:00;descarga;ABC1D23;30".encode()

    resposta = _subir(entrar(cenario.gestor_b.email), cenario.site_a.id, conteudo)

    assert resposta.status_code == 404  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("nome", "conteudo", "detalhe"),
    [
        ("agenda.xls", b"qualquer", "a planilha precisa ser .csv ou .xlsx"),
        ("agenda.csv", b"codigo;placa\nAG-1;ABC1D23", "faltam as colunas: dia, início, fim, tipo"),
        ("agenda.csv", b"x" * (5 * 1024 * 1024 + 10), "o arquivo é grande demais (até 5 MB)"),
    ],
)
def test_arquivo_que_nao_serve_responde_422_com_o_motivo(
    entrar: Entrar, cenario: Demonstracao, nome: str, conteudo: bytes, detalhe: str
) -> None:
    resposta = _subir(entrar(cenario.gestor_a.email), cenario.site_a.id, conteudo, nome)

    assert resposta.status_code == 422  # type: ignore[attr-defined]
    assert resposta.json() == {"detail": detalhe}  # type: ignore[attr-defined]

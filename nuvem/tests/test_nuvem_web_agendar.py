"""Telas do link da transportadora (SDD 6.2 e 8.2): o formulário, a confirmação e os avisos."""

import logging
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from nuvem.agendamento import link as links
from nuvem.agendamento import servico
from nuvem.agendamento.link import FormularioDoLink
from nuvem.cadastro.acesso import Acesso
from nuvem.config import Configuracao
from nuvem.principal import criar_app
from nuvem.relogio import agora
from nuvem.semente import Demonstracao
from nuvem.web.agendar import EsconderCodigoDoLink

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)

FORMULARIO = asdict(
    FormularioDoLink(
        data="2026-11-05",
        hora_inicio="08:00",
        hora_fim="10:00",
        tipo="descarga",
        placa_cavalo="ABC1D23",
        reboque_1="DEF4G56",
        motorista_nome="Motorista Inventado",
        motorista_celular="(11) 98765-4321",
        toneladas="32,5",
    )
)


@pytest.fixture
def navegador(app: FastAPI) -> TestClient:
    """O celular da transportadora: sem login, com a hora fixa."""
    app.dependency_overrides[agora] = lambda: AGORA
    return TestClient(app)


@pytest.fixture
def gerado(sessao: Session, cenario: Demonstracao, acesso_a: Acesso) -> links.LinkGerado:
    """Um link do site_a."""
    return links.gerar_link(
        sessao, acesso_a, cenario.site_a.id, nome="Transportadora Inventada", agora=AGORA
    )


def _enviar(navegador: TestClient, codigo: str, **mudancas: Any) -> Any:
    return navegador.post(f"/agendar/{codigo}", data=FORMULARIO | mudancas, follow_redirects=False)


def test_formulario_mostra_o_site_o_horario_e_para_quem_e(
    navegador: TestClient, cenario: Demonstracao, gerado: links.LinkGerado
) -> None:
    resposta = navegador.get(f"/agendar/{gerado.codigo}")

    assert resposta.status_code == 200
    assert cenario.site_a.nome in resposta.text
    assert "Transportadora Inventada" in resposta.text
    assert "das 06:00 às 22:00" in resposta.text
    assert f'action="/agendar/{gerado.codigo}"' in resposta.text
    for campo in FORMULARIO:
        assert f'name="{campo}"' in resposta.text


def test_paginas_do_link_nao_vazam_o_endereco_nem_ficam_no_cache(
    navegador: TestClient, gerado: links.LinkGerado
) -> None:
    for resposta in (
        navegador.get(f"/agendar/{gerado.codigo}"),
        navegador.get(f"/agendar/{gerado.codigo}x"),
        _enviar(navegador, gerado.codigo, placa_cavalo="ABC12"),
    ):
        assert resposta.headers["referrer-policy"] == "no-referrer"
        assert resposta.headers["cache-control"] == "no-store"
        assert resposta.headers["x-robots-tag"] == "noindex"


def test_link_inventado_responde_404_com_aviso(navegador: TestClient) -> None:
    resposta = navegador.get("/agendar/codigo-inventado")

    assert resposta.status_code == 404
    assert "Este link não vale mais" in resposta.text


def test_link_revogado_responde_o_mesmo_404(
    navegador: TestClient, sessao: Session, acesso_a: Acesso, gerado: links.LinkGerado
) -> None:
    links.revogar_link(sessao, acesso_a, gerado.link.id, agora=AGORA)

    assert navegador.get(f"/agendar/{gerado.codigo}").status_code == 404
    assert _enviar(navegador, gerado.codigo).status_code == 404


def test_link_vencido_responde_404(
    app: FastAPI, navegador: TestClient, gerado: links.LinkGerado
) -> None:
    app.dependency_overrides[agora] = lambda: gerado.link.vence_em

    assert navegador.get(f"/agendar/{gerado.codigo}").status_code == 404


def test_link_no_limite_responde_429(
    navegador: TestClient, sessao: Session, gerado: links.LinkGerado
) -> None:
    gerado.link.envios = gerado.link.limite_de_envios
    sessao.flush()

    for resposta in (navegador.get(f"/agendar/{gerado.codigo}"), _enviar(navegador, gerado.codigo)):
        assert resposta.status_code == 429
        assert "chegou ao limite" in resposta.text


def test_enviar_agenda_e_leva_a_confirmacao(
    navegador: TestClient, cenario: Demonstracao, acesso_a: Acesso, gerado: links.LinkGerado
) -> None:
    resposta = _enviar(navegador, gerado.codigo)

    assert resposta.status_code == 303
    numero = f"{gerado.link.id}-1"
    assert resposta.headers["location"] == f"/agendar/{gerado.codigo}/feito/{numero}"
    confirmacao = navegador.get(resposta.headers["location"])
    assert confirmacao.status_code == 200
    assert numero in confirmacao.text
    assert "05/11/2026, das 08:00 às 10:00" in confirmacao.text  # no fuso do site
    assert "ABC1D23" in confirmacao.text


def test_o_agendamento_fica_gravado_de_verdade(
    navegador: TestClient, sessao: Session, cenario: Demonstracao, acesso_a: Acesso,
    gerado: links.LinkGerado,
) -> None:  # fmt: skip
    _enviar(navegador, gerado.codigo)

    # A sessão do teste é outra: o que a rota gravasse sem commit teria se perdido.
    lista = servico.listar(
        sessao, acesso_a, cenario.site_a.id, de=AGORA, ate=AGORA + timedelta(days=2)
    )
    assert [(a.origem, a.placa_cavalo) for a in lista] == [("link", "ABC1D23")]


def test_formulario_com_erro_volta_com_os_valores_e_os_motivos(
    navegador: TestClient, gerado: links.LinkGerado
) -> None:
    resposta = _enviar(navegador, gerado.codigo, placa_cavalo="ABC12", hora_inicio="05:00")

    assert resposta.status_code == 422
    assert "a janela precisa ficar dentro do horário do site" in resposta.text
    assert "placa inválida: &#39;ABC12&#39;" in resposta.text
    assert 'value="Motorista Inventado"' in resposta.text  # o que estava certo continua lá


def test_confirmacao_de_agendamento_de_outro_link_responde_404(
    navegador: TestClient, sessao: Session, cenario: Demonstracao, acesso_a: Acesso,
    gerado: links.LinkGerado,
) -> None:  # fmt: skip
    _enviar(navegador, gerado.codigo)
    outro = links.gerar_link(sessao, acesso_a, cenario.site_a.id, nome="Outra", agora=AGORA)

    resposta = navegador.get(f"/agendar/{outro.codigo}/feito/{gerado.link.id}-1")

    assert resposta.status_code == 404


def test_texto_digitado_aparece_escapado(navegador: TestClient, gerado: links.LinkGerado) -> None:
    resposta = _enviar(navegador, gerado.codigo, motorista_nome="<script>x</script>", toneladas="")

    assert "<script>x</script>" not in resposta.text
    assert "&lt;script&gt;x&lt;/script&gt;" in resposta.text


# --- O registro de acesso não guarda o código (D-34) ------------------------------------------


def _registro_de_acesso(caminho: str) -> logging.LogRecord:
    # O mesmo formato do registro de acesso do uvicorn.
    return logging.LogRecord(
        "uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
        ("10.0.0.1:5000", "GET", caminho, "1.1", 200), None,
    )  # fmt: skip


@pytest.mark.parametrize(
    ("caminho", "registrado"),
    [
        ("/agendar/AbC-123_xyz", "/agendar/***"),
        ("/agendar/AbC-123_xyz/feito/12-3", "/agendar/***/feito/12-3"),
        ("/portaria/passagens?site=1", "/portaria/passagens?site=1"),
    ],
)
def test_registro_de_acesso_esconde_o_codigo_do_link(caminho: str, registrado: str) -> None:
    registro = _registro_de_acesso(caminho)

    assert EsconderCodigoDoLink().filter(registro)
    assert registro.getMessage() == f'10.0.0.1:5000 - "GET {registrado} HTTP/1.1" 200'


def test_a_aplicacao_liga_o_filtro_uma_vez_so(url_banco_teste: str, tmp_path: Path) -> None:
    configuracao = Configuracao(
        url_banco=url_banco_teste,
        chave_cifra=Fernet.generate_key().decode(),
        ambiente="local",
        pasta_fotos=tmp_path,
        _env_file=None,
    )

    criar_app(configuracao)
    criar_app(configuracao)
    filtros = logging.getLogger("uvicorn.access").filters

    assert sum(isinstance(filtro, EsconderCodigoDoLink) for filtro in filtros) == 1

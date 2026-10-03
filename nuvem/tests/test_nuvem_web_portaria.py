"""Tela crua da portaria (T12): as últimas passagens do site, atualizadas a cada 2 segundos."""

from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem.armazenamento import ArmazenamentoLocal
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import acesso_do_usuario
from nuvem.frota import servico as frota
from nuvem.frota.servico import CaixaAtivada
from nuvem.portaria import servico as portaria
from nuvem.relogio import agora
from nuvem.semente import SENHA_DA_DEMONSTRACAO, Demonstracao
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]
Registrar = Callable[..., Passagem]
JPEG = b"\xff\xd8\xff\xe0" + b"foto-inventada" * 10 + b"\xff\xd9"


def _enviar_foto(app: FastAPI, caixa: CaixaAtivada, ref: str) -> None:
    armazenamento: ArmazenamentoLocal = app.state.armazenamento
    endereco = armazenamento.endereco_de_envio(caixa.caixa_id, ref, agora=agora())
    armazenamento.receber(endereco.rsplit("/", 1)[1], JPEG, agora=agora())


def test_tela_da_portaria_atualiza_sozinha_a_cada_2_segundos(
    entrar: Entrar, cenario: Demonstracao
) -> None:
    resposta = entrar(cenario.porteiro_a.email).get("/portaria")

    assert resposta.status_code == 200
    assert f'hx-get="/portaria/passagens?site={cenario.site_a.id}"' in resposta.text
    assert 'hx-trigger="load, every 2s"' in resposta.text
    assert '<script src="/estatico/htmx-2.0.11.min.js"' in resposta.text


def test_htmx_e_servido_pela_propria_api(app: FastAPI) -> None:
    resposta = TestClient(app).get("/estatico/htmx-2.0.11.min.js")

    assert resposta.status_code == 200
    assert resposta.text.startswith("var htmx=")


def test_lista_mostra_horario_no_fuso_do_site_faixa_placa_e_confianca(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    registrar_passagem()  # 17:02:11 UTC = 14:02:11 em São Paulo

    lista = entrar(cenario.porteiro_a.email).get(f"/portaria/passagens?site={cenario.site_a.id}")

    assert lista.status_code == 200
    for esperado in ("14:02:11", "Entrada 1", "entrada", "ABC1D23", "cavalo", "97%"):
        assert esperado in lista.text


def test_lista_mostra_a_foto_da_placa(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    lista = entrar(cenario.porteiro_a.email).get(f"/portaria/passagens?site={cenario.site_a.id}")

    assert f'src="/portaria/fotos/{passagem.id}/0"' in lista.text


def test_ultimas_passagens_primeiro(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    primeira = registrar_passagem()
    segunda = registrar_passagem(inicio=primeira.inicio + timedelta(minutes=5))

    lista = entrar(cenario.porteiro_a.email).get(f"/portaria/passagens?site={cenario.site_a.id}")

    assert lista.text.index(str(segunda.id)) < lista.text.index(str(primeira.id))


def test_lista_tem_no_maximo_50_passagens(
    sessao: Session, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    base = registrar_passagem().inicio
    for minuto in (1, 2):
        registrar_passagem(inicio=base + timedelta(minutes=minuto))
    acesso = acesso_do_usuario(sessao, cenario.porteiro_a.id)

    ultimas = portaria.ultimas_passagens(sessao, acesso, cenario.site_a.id, limite=2)

    assert [p.inicio for p in ultimas] == [base + timedelta(minutes=m) for m in (2, 1)]
    assert portaria.LIMITE_DA_TELA == 50


def test_sem_passagens_a_lista_avisa(entrar: Entrar, cenario: Demonstracao) -> None:
    lista = entrar(cenario.porteiro_a.email).get(f"/portaria/passagens?site={cenario.site_a.id}")

    assert "Nenhuma passagem ainda" in lista.text


def test_gestor_de_outra_empresa_nao_ve_as_passagens_nem_as_fotos(
    app: FastAPI,
    entrar: Entrar,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    registrar_passagem: Registrar,
) -> None:
    passagem = registrar_passagem()
    _enviar_foto(app, caixa_a, "p/1.jpg")  # a foto existe: o 404 é pela separação
    gestor_b = entrar(cenario.gestor_b.email)

    lista = gestor_b.get(f"/portaria/passagens?site={cenario.site_a.id}")
    foto = gestor_b.get(f"/portaria/fotos/{passagem.id}/0")

    assert (lista.status_code, foto.status_code) == (404, 404)
    assert str(passagem.id) not in lista.text


def test_passagem_de_outro_site_da_mesma_empresa_nao_aparece(
    sessao: Session,
    entrar: Entrar,
    cenario: Demonstracao,
    registrar_passagem: Registrar,
) -> None:
    # Uma caixa no site_a2 manda uma passagem; o porteiro do site_a não a vê.
    portaria_2 = cadastro.criar_portaria(sessao, cenario.site_a2, nome="Portaria 2")
    faixa_2 = cadastro.criar_faixa(sessao, portaria_2, nome="Entrada 2", sentido="entrada")
    gerado = frota.gerar_codigo_de_ativacao(
        sessao, cenario.site_a2.id, administrador_id=cenario.administrador.id, agora=agora()
    )
    ativada = frota.ativar(sessao, gerado.codigo, agora=agora())
    caixa_2 = frota.caixa_da_chave(sessao, ativada.chave)
    assert caixa_2 is not None
    passagem_2 = Passagem.model_validate(
        registrar_passagem().model_dump(mode="json")
        | {
            "id": "00000000-0000-4000-8000-000000000002",
            "caixa_id": str(ativada.caixa_id),
            "site_id": str(cenario.site_a2.id),
            "faixa_id": str(faixa_2.id),
            "placas": [],
            "fotos": [],
        }
    )
    portaria.receber_passagem(sessao, caixa_2, passagem_2, agora=agora())

    lista = entrar(cenario.porteiro_a.email).get(f"/portaria/passagens?site={cenario.site_a.id}")

    assert str(passagem_2.id) not in lista.text


def test_foto_da_placa_sai_pela_tela(
    app: FastAPI,
    entrar: Entrar,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    registrar_passagem: Registrar,
) -> None:
    passagem = registrar_passagem()
    _enviar_foto(app, caixa_a, "p/1.jpg")

    resposta = entrar(cenario.porteiro_a.email).get(f"/portaria/fotos/{passagem.id}/0")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "image/jpeg"
    assert resposta.content == JPEG


def test_foto_que_ainda_nao_chegou_responde_404(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    resposta = entrar(cenario.porteiro_a.email).get(f"/portaria/fotos/{passagem.id}/0")

    assert resposta.status_code == 404


def test_foto_que_a_passagem_nao_tem_responde_404(
    entrar: Entrar, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    resposta = entrar(cenario.porteiro_a.email).get(f"/portaria/fotos/{passagem.id}/7")

    assert resposta.status_code == 404


def test_lider_de_patio_nao_ve_a_tela_da_portaria(entrar: Entrar, cenario: Demonstracao) -> None:
    assert entrar(cenario.patio_a.email).get("/portaria").status_code == 403


def test_sem_login_a_tela_leva_a_entrar(app: FastAPI) -> None:
    resposta = TestClient(app).get("/portaria", follow_redirects=False)

    assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


def test_atualizacao_sem_login_manda_o_htmx_para_a_tela_de_entrar(
    app: FastAPI, cenario: Demonstracao
) -> None:
    # A sessão venceu com a tela aberta: o HTMX recebe o aviso e leva à tela de entrar.
    resposta = TestClient(app).get(
        f"/portaria/passagens?site={cenario.site_a.id}",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    assert resposta.status_code == 401
    assert resposta.headers["hx-redirect"] == "/entrar"


def test_inicio_do_porteiro_leva_a_tela_da_portaria(entrar: Entrar, cenario: Demonstracao) -> None:
    assert 'href="/portaria"' in entrar(cenario.porteiro_a.email).get("/").text


def test_porteiro_de_outro_site_da_mesma_empresa_nao_ve_a_foto(
    app: FastAPI,
    sessao: Session,
    senhas: Senhas,
    entrar: Entrar,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    registrar_passagem: Registrar,
) -> None:
    passagem = registrar_passagem()
    _enviar_foto(app, caixa_a, "p/1.jpg")
    cadastro.criar_usuario(
        sessao,
        senhas,
        cenario.empresa_a,
        nome="Porteiro do site 2",
        email="porteiro-site2@empresa-a.example",
        papel="porteiro",
        sites=[cenario.site_a2],
        senha=SENHA_DA_DEMONSTRACAO,
    )

    resposta = entrar("porteiro-site2@empresa-a.example").get(f"/portaria/fotos/{passagem.id}/0")

    assert resposta.status_code == 404

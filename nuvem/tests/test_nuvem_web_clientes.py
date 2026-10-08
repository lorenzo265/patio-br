"""As telas do cadastro do cliente e o link de senha (SDD 6.2 e 8.2, D-75). Nomes, e-mails e
CNPJs inventados."""

import logging
import re
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nuvem.cadastro.modelos import Camera, Doca, Empresa, Faixa, LinkDeSenha, Portaria, Site
from nuvem.cifra import Cifra
from nuvem.semente import Demonstracao
from nuvem.senhas import resumo_rapido
from nuvem.web.agendar import EsconderCodigoDoLink

pytestmark = pytest.mark.integracao

Entrar = Callable[..., TestClient]

SENHA_NOVA = "uma senha longa inventada"
LINK = re.compile(r"/senha/([A-Za-z0-9_-]{40,})")


@pytest.fixture
def admin(entrar: Entrar, cenario: Demonstracao) -> TestClient:
    return entrar(cenario.administrador.email)


def _ficha(cenario: Demonstracao) -> str:
    return f"/administracao/clientes/{cenario.empresa_a.id}"


# --- Quem entra -----------------------------------------------------------------------------


def test_so_a_administracao_cadastra(entrar: Entrar, cenario: Demonstracao) -> None:
    gestor = entrar(cenario.gestor_a.email)

    assert gestor.get("/administracao/clientes").status_code == 403
    assert gestor.get(_ficha(cenario)).status_code == 403
    dados = {
        "nome": "X",
        "email": "x@exemplo.invalid",
        "papel": "gestor",
        "sites": cenario.site_a.id,
    }
    assert gestor.post(f"{_ficha(cenario)}/pessoas", data=dados).status_code == 403


def test_sem_login_vai_para_o_login(app: FastAPI, cenario: Demonstracao) -> None:
    resposta = TestClient(app).get("/administracao/clientes", follow_redirects=False)

    assert resposta.status_code in (303, 401)


def test_o_inicio_da_administracao_leva_aos_clientes(admin: TestClient) -> None:
    assert 'href="/administracao/clientes"' in admin.get("/").text


# --- A empresa e a estrutura ----------------------------------------------------------------


def test_a_empresa_nova_abre_a_ficha(admin: TestClient, sessao: Session) -> None:
    resposta = admin.post(
        "/administracao/clientes",
        data={"nome": "Distribuidora Inventada", "cnpj": "12.ABC.345/01DE-35"},
        follow_redirects=False,
    )

    empresa = sessao.scalars(select(Empresa).where(Empresa.cnpj == "12ABC34501DE35")).one()
    assert resposta.status_code == 303
    assert resposta.headers["location"] == f"/administracao/clientes/{empresa.id}"
    assert "Distribuidora Inventada" in admin.get(resposta.headers["location"]).text
    assert "Distribuidora Inventada" in admin.get("/administracao/clientes").text


def test_o_cnpj_errado_volta_com_o_erro(admin: TestClient, sessao: Session) -> None:
    antes = sessao.scalar(select(func.count()).select_from(Empresa))

    resposta = admin.post(
        "/administracao/clientes", data={"nome": "Inventada", "cnpj": "11.222.333/0001-82"}
    )

    assert resposta.status_code == 400
    assert "não confere" in resposta.text and 'value="Inventada"' in resposta.text
    assert sessao.scalar(select(func.count()).select_from(Empresa)) == antes


def test_a_estrutura_toda_pela_ficha(
    admin: TestClient, sessao: Session, cenario: Demonstracao, cifra: Cifra
) -> None:
    ficha = _ficha(cenario)
    assert (
        admin.post(
            f"{ficha}/sites",
            data={"nome": "CD Norte", "fuso": "America/Manaus", "abre": "06:00", "fecha": "22:00"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    site = sessao.scalars(select(Site).where(Site.nome == "CD Norte")).one()
    admin.post(f"{ficha}/portarias", data={"site": site.id, "nome": "Principal"})
    portaria = sessao.scalars(select(Portaria).where(Portaria.site_id == site.id)).one()
    admin.post(
        f"{ficha}/faixas", data={"portaria": portaria.id, "nome": "Entrada 1", "sentido": "entrada"}
    )
    faixa = sessao.scalars(select(Faixa).where(Faixa.portaria_id == portaria.id)).one()
    admin.post(
        f"{ficha}/cameras",
        data={
            "faixa": faixa.id,
            "nome": "Frente",
            "posicao": "frente",
            "endereco": "rtsp://10.0.0.21/1",
            "login": "leitor",
            "senha": "senha-da-camera",
        },
    )
    admin.post(f"{ficha}/docas", data={"site": site.id, "nome": "Doca 1"})

    camera = sessao.scalars(select(Camera).where(Camera.faixa_id == faixa.id)).one()
    assert cifra.decifrar(camera.senha_cifrada) == "senha-da-camera"
    assert sessao.scalars(select(Doca.nome).where(Doca.site_id == site.id)).all() == ["Doca 1"]
    pagina = admin.get(ficha).text
    for texto in (
        "CD Norte",
        "das 06:00 às 22:00",
        "Portaria Principal",
        "Faixa Entrada 1 (entrada)",
        "rtsp://10.0.0.21/1",
        "login leitor",
        "Doca 1",
    ):
        assert texto in pagina, texto
    assert "senha-da-camera" not in pagina


def test_a_camera_troca_o_endereco_e_mantem_a_senha(
    admin: TestClient, sessao: Session, cenario: Demonstracao, cifra: Cifra
) -> None:
    camera = cenario.camera_a
    senha_antes = cifra.decifrar(camera.senha_cifrada)

    resposta = admin.post(
        f"{_ficha(cenario)}/cameras/{camera.id}",
        data={"endereco": "rtsp://10.0.0.99/novo", "login": "outro", "senha": ""},
        follow_redirects=False,
    )

    sessao.refresh(camera)
    assert resposta.status_code == 303
    assert (camera.endereco, camera.login) == ("rtsp://10.0.0.99/novo", "outro")
    assert cifra.decifrar(camera.senha_cifrada) == senha_antes


def test_o_que_e_de_outra_empresa_nao_existe_pela_ficha(
    admin: TestClient, cenario: Demonstracao
) -> None:
    ficha = _ficha(cenario)

    assert (
        admin.post(f"{ficha}/portarias", data={"site": cenario.site_b.id, "nome": "X"}).status_code
        == 404
    )
    assert (
        admin.post(
            f"{ficha}/cameras/{cenario.camera_b.id}", data={"endereco": "rtsp://x/1"}
        ).status_code
        == 404
    )
    assert admin.post(f"{ficha}/pessoas/{cenario.gestor_b.id}/link").status_code == 404
    assert admin.get("/administracao/clientes/999999").status_code == 404


def test_o_erro_volta_na_ficha(admin: TestClient, cenario: Demonstracao) -> None:
    resposta = admin.post(
        f"{_ficha(cenario)}/cameras",
        data={
            "faixa": cenario.faixa_a.id,
            "nome": "X",
            "posicao": "frente",
            "endereco": "rtsp://l:s@10.0.0.1/1",
        },
    )

    assert resposta.status_code == 400
    assert "não pode levar usuário nem senha" in resposta.text


# --- As pessoas e o link de senha -----------------------------------------------------------


def _nova_pessoa(
    admin: TestClient, cenario: Demonstracao, papel: str = "gestor"
) -> tuple[str, str]:
    """Cadastra uma pessoa e devolve o código do link e a página da resposta."""
    resposta = admin.post(
        f"{_ficha(cenario)}/pessoas",
        data={
            "nome": "Fulana Inventada",
            "email": f"fulana.{papel}@exemplo.invalid",
            "papel": papel,
            "sites": [cenario.site_a.id, cenario.site_a2.id],
        },
    )
    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == "no-store"
    achado = LINK.search(resposta.text)
    assert achado is not None
    return achado.group(1), resposta.text


def test_a_pessoa_nova_mostra_o_link_uma_vez_so(
    admin: TestClient, sessao: Session, cenario: Demonstracao
) -> None:
    codigo, pagina = _nova_pessoa(admin, cenario)

    assert "aparece só agora" in pagina
    assert "http://testserver/senha/" in pagina
    link = sessao.scalars(
        select(LinkDeSenha).where(LinkDeSenha.codigo_resumo == resumo_rapido(codigo))
    ).one()
    assert link.empresa_id == cenario.empresa_a.id
    ficha = admin.get(_ficha(cenario)).text
    assert codigo not in ficha  # a ficha de depois não mostra o código
    assert "fulana.gestor@exemplo.invalid" in ficha and "ainda não" in ficha


def test_a_pessoa_sem_site_volta_com_o_erro(admin: TestClient, cenario: Demonstracao) -> None:
    resposta = admin.post(
        f"{_ficha(cenario)}/pessoas",
        data={"nome": "X", "email": "x@exemplo.invalid", "papel": "gestor"},
    )

    assert resposta.status_code == 400
    assert "pelo menos um site" in resposta.text
    assert LINK.search(resposta.text) is None


def test_a_pessoa_cria_a_senha_pelo_link_e_entra(
    admin: TestClient, app: FastAPI, cenario: Demonstracao
) -> None:
    codigo, _ = _nova_pessoa(admin, cenario)
    navegador = TestClient(app)

    formulario = navegador.get(f"/senha/{codigo}")
    assert formulario.status_code == 200
    assert "Fulana Inventada" in formulario.text and 'name="pin"' not in formulario.text
    assert formulario.headers["referrer-policy"] == "no-referrer"
    assert formulario.headers["cache-control"] == "no-store"

    diferente = navegador.post(
        f"/senha/{codigo}", data={"senha": SENHA_NOVA, "confirmacao": "outra senha longa"}
    )
    assert diferente.status_code == 400 and "não são iguais" in diferente.text

    pronto = navegador.post(
        f"/senha/{codigo}", data={"senha": SENHA_NOVA, "confirmacao": SENHA_NOVA}
    )
    assert pronto.status_code == 200 and "a senha está criada" in pronto.text

    entrou = navegador.post(
        "/entrar",
        data={"email": "fulana.gestor@exemplo.invalid", "senha": SENHA_NOVA},
        follow_redirects=False,
    )
    assert entrou.status_code == 303
    assert navegador.get(f"/senha/{codigo}").status_code == 404  # uma vez só


def test_o_porteiro_cria_o_pin_junto(
    admin: TestClient, app: FastAPI, cenario: Demonstracao
) -> None:
    codigo, _ = _nova_pessoa(admin, cenario, papel="porteiro")
    navegador = TestClient(app)

    assert 'name="pin"' in navegador.get(f"/senha/{codigo}").text
    sem_pin = navegador.post(
        f"/senha/{codigo}", data={"senha": SENHA_NOVA, "confirmacao": SENHA_NOVA}
    )
    assert sem_pin.status_code == 400 and "PIN" in sem_pin.text
    pronto = navegador.post(
        f"/senha/{codigo}", data={"senha": SENHA_NOVA, "confirmacao": SENHA_NOVA, "pin": "246810"}
    )
    assert pronto.status_code == 200


def test_o_link_inventado_nao_vale(app: FastAPI, cenario: Demonstracao) -> None:
    resposta = TestClient(app).get("/senha/inventado")

    assert resposta.status_code == 404
    assert "não vale mais" in resposta.text
    assert (
        TestClient(app)
        .post("/senha/inventado", data={"senha": SENHA_NOVA, "confirmacao": SENHA_NOVA})
        .status_code
        == 404
    )


def test_o_link_novo_troca_o_anterior(
    admin: TestClient, app: FastAPI, cenario: Demonstracao
) -> None:
    antigo, _ = _nova_pessoa(admin, cenario)
    pessoa = re.search(
        r"/pessoas/(\d+)/link", admin.get(_ficha(cenario)).text.split("fulana.gestor")[1]
    )
    assert pessoa is not None

    resposta = admin.post(f"{_ficha(cenario)}/pessoas/{pessoa.group(1)}/link")

    novo = LINK.search(resposta.text)
    assert resposta.status_code == 200 and novo is not None and novo.group(1) != antigo
    assert TestClient(app).get(f"/senha/{antigo}").status_code == 404
    assert TestClient(app).get(f"/senha/{novo.group(1)}").status_code == 200


def test_desativar_tira_a_pessoa_e_reativar_volta(
    admin: TestClient, entrar: Entrar, sessao: Session, cenario: Demonstracao
) -> None:
    porteiro = entrar(cenario.porteiro_a.email)
    url = f"{_ficha(cenario)}/pessoas/{cenario.porteiro_a.id}/situacao"

    resposta = admin.post(url, data={"ativa": "false"}, follow_redirects=False)

    assert resposta.status_code == 303
    sessao.refresh(cenario.porteiro_a)
    assert not cenario.porteiro_a.ativo
    assert porteiro.get("/portaria", follow_redirects=False).status_code != 200
    assert "(desativada)" in admin.get(_ficha(cenario)).text
    admin.post(url, data={"ativa": "true"})
    sessao.refresh(cenario.porteiro_a)
    assert cenario.porteiro_a.ativo


def test_o_link_de_senha_nao_pede_o_codigo_anti_csrf(
    admin: TestClient, entrar: Entrar, cenario: Demonstracao
) -> None:
    # O código do endereço decide quem pede; o cookie de outra sessão não muda nada.
    codigo, _ = _nova_pessoa(admin, cenario)
    com_sessao = entrar(cenario.gestor_b.email)
    com_sessao.event_hooks["request"].clear()  # sem o código anti-CSRF

    resposta = com_sessao.post(
        f"/senha/{codigo}", data={"senha": SENHA_NOVA, "confirmacao": SENHA_NOVA}
    )

    assert resposta.status_code == 200


def test_o_registro_de_acesso_esconde_o_codigo_do_link_de_senha() -> None:
    registro = logging.LogRecord(
        "uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
        ("10.0.0.1:5000", "POST", "/senha/AbC-123_xyz", "1.1", 200), None,
    )  # fmt: skip

    assert EsconderCodigoDoLink().filter(registro)
    assert registro.getMessage() == '10.0.0.1:5000 - "POST /senha/*** HTTP/1.1" 200'

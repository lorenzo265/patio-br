"""As telas "em breve" do recebimento e do estoque em 3D (T46, D-43 e D-45), e os arquivos de
terceiros que o painel serve."""

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nuvem.principal import PASTA_ESTATICA
from nuvem.semente import Demonstracao
from nuvem.web import em_breve

Entrar = Callable[..., TestClient]

integracao = pytest.mark.integracao


# --- Os arquivos de terceiros -----------------------------------------------------------------


def _hashes_do_leia_me() -> dict[str, str]:
    texto = (PASTA_ESTATICA / "LEIA-ME.md").read_text(encoding="utf-8")
    return dict(re.findall(r"^- `([^`]+)`: `([0-9a-f]{64})`$", texto, flags=re.MULTILINE))


def test_cada_arquivo_de_terceiros_confere_com_o_hash_do_leia_me() -> None:
    hashes = _hashes_do_leia_me()

    assert "three-0.186.1/three.module.js" in hashes
    for arquivo, esperado in hashes.items():
        conteudo = (PASTA_ESTATICA / arquivo).read_bytes()
        assert hashlib.sha256(conteudo).hexdigest() == esperado, arquivo


def test_todo_codigo_de_terceiros_esta_no_leia_me() -> None:
    servidos = {
        caminho.relative_to(PASTA_ESTATICA).as_posix()
        for caminho in Path(PASTA_ESTATICA).rglob("*.js")
    }

    assert servidos == set(_hashes_do_leia_me())


def test_a_licenca_do_three_vai_junto() -> None:
    licenca = (PASTA_ESTATICA / "three-0.186.1" / "LICENSE.txt").read_text(encoding="utf-8")

    assert licenca.startswith("The MIT License")


# --- Quem vê ----------------------------------------------------------------------------------


@integracao
def test_sem_login_vai_para_a_tela_de_entrar(app: FastAPI) -> None:
    for caminho in ("/recebimento", "/estoque"):
        resposta = TestClient(app).get(caminho, follow_redirects=False)
        assert (resposta.status_code, resposta.headers["location"]) == (303, "/entrar")


@integracao
def test_todos_do_cliente_veem_as_duas_telas(entrar: Entrar, cenario: Demonstracao) -> None:
    for pessoa in (cenario.porteiro_a, cenario.patio_a, cenario.gestor_a):
        cliente = entrar(pessoa.email)
        for caminho in ("/recebimento", "/estoque"):
            resposta = cliente.get(caminho)
            assert resposta.status_code == 200
            assert "Em breve" in resposta.text


@integracao
def test_o_inicio_leva_as_duas_telas(entrar: Entrar, cenario: Demonstracao) -> None:
    texto = entrar(cenario.porteiro_a.email).get("/").text

    assert 'href="/recebimento"' in texto and 'href="/estoque"' in texto


# --- O recebimento ----------------------------------------------------------------------------


def test_a_nota_de_exemplo_tem_uma_falta_uma_sobra_e_itens_a_contar() -> None:
    situacoes = [item.situacao for item in em_breve.NOTA_DE_EXEMPLO.itens]

    assert situacoes.count("falta") == 1
    assert situacoes.count("sobra") == 1
    assert "a contar" in situacoes
    assert all(s in ("confere", "falta", "sobra", "a contar") for s in situacoes)


def test_a_diferenca_e_o_contado_menos_a_nota() -> None:
    item = em_breve.ItemDaNota("X-1", "Teste", "cx", na_nota=10, contado=7)

    assert (item.diferenca, item.situacao) == (-3, "falta")
    assert em_breve.ItemDaNota("X-2", "Teste", "cx", na_nota=10, contado=None).diferenca is None


@integracao
def test_o_recebimento_mostra_a_nota_item_por_item(entrar: Entrar, cenario: Demonstracao) -> None:
    texto = entrar(cenario.gestor_a.email).get("/recebimento").text

    for item in em_breve.NOTA_DE_EXEMPLO.itens:
        assert item.descricao in texto
    assert "falta de 2" in texto
    assert "6 de 8 itens contados; 2 com diferença." in texto
    assert "dados inventados" in texto


# --- O estoque em 3D --------------------------------------------------------------------------


def test_cada_item_do_estoque_tem_um_lugar_que_existe_e_so_dele() -> None:
    lugares = [(i.rua, i.predio, i.nivel) for i in em_breve.ESTOQUE_DE_EXEMPLO.itens]
    armazem = em_breve.ESTOQUE_DE_EXEMPLO

    assert len(set(lugares)) == len(lugares)
    for rua, predio, nivel in lugares:
        assert rua in armazem.ruas
        assert 1 <= predio <= armazem.predios
        assert 1 <= nivel <= armazem.niveis


@integracao
def test_o_estoque_traz_o_3d_e_os_dados(entrar: Entrar, cenario: Demonstracao) -> None:
    texto = entrar(cenario.gestor_a.email).get("/estoque").text

    assert '"three": "/estatico/three-0.186.1/three.module.js"' in texto
    dados = re.search(
        r'<script type="application/json" id="dados-do-estoque">(.*?)</script>', texto, re.DOTALL
    )
    assert dados is not None
    lido = json.loads(dados.group(1))
    assert len(lido["itens"]) == len(em_breve.ESTOQUE_DE_EXEMPLO.itens)
    assert lido["ruas"] == list(em_breve.ESTOQUE_DE_EXEMPLO.ruas)


@integracao
def test_o_nome_de_um_item_nao_fecha_o_script(
    entrar: Entrar, cenario: Demonstracao, monkeypatch: pytest.MonkeyPatch
) -> None:
    perigoso = em_breve.ItemNoEstoque("</script><script>alert(1)</script>", "A", 1, 1, 1, "cx")
    monkeypatch.setattr(
        em_breve, "ESTOQUE_DE_EXEMPLO",
        em_breve.EstoqueDeExemplo(ruas=("A",), predios=1, niveis=1, itens=(perigoso,)),
    )  # fmt: skip

    texto = entrar(cenario.gestor_a.email).get("/estoque").text

    assert "<script>alert(1)" not in texto
    assert "\\u003c/script>" in texto


@integracao
def test_o_three_e_servido_pela_propria_api(app: FastAPI) -> None:
    resposta = TestClient(app).get("/estatico/three-0.186.1/three.module.js")

    assert resposta.status_code == 200
    assert "javascript" in resposta.headers["content-type"]

"""Rotas da borda para passagens e fotos: respostas que a fila da caixa entende."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.config import Configuracao
from nuvem.frota.servico import CaixaAtivada
from nuvem.principal import criar_app
from nuvem.semente import Demonstracao
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao

JPEG = b"\xff\xd8\xff\xe0" + b"foto-inventada" * 10 + b"\xff\xd9"
CHAVE_QUALQUER = "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw="


def _caixa(app: FastAPI, caixa: CaixaAtivada) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {caixa.chave}"})


def _passagem(cenario: Demonstracao, caixa: CaixaAtivada, **mudancas: Any) -> dict[str, Any]:
    inicio = datetime.now(UTC)
    dados: dict[str, Any] = {
        "versao_contrato": 1,
        "id": str(uuid4()),
        "caixa_id": str(caixa.caixa_id),
        "site_id": str(cenario.site_a.id),
        "faixa_id": str(cenario.faixa_a.id),
        "sentido": "entrada",
        "inicio": inicio.isoformat(),
        "fim": (inicio + timedelta(seconds=8)).isoformat(),
        "placas": [
            {
                "placa": "ABC1D23",
                "papel": "cavalo",
                "confianca": 0.97,
                "camera_id": str(cenario.camera_a.id),
                "quadros": 6,
            }
        ],
        "fotos": [],
        "versao_leitor": "0.1.0",
    }
    dados.update(mudancas)
    return dados


# --- Passagens -----------------------------------------------------------------------------


def test_passagem_nova_responde_201_e_repetida_200(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    caixa = _caixa(app, caixa_a)
    passagem = _passagem(cenario, caixa_a)

    primeira = caixa.post("/api/borda/passagens", json=passagem)
    segunda = caixa.post("/api/borda/passagens", json=passagem)

    assert (primeira.status_code, primeira.json()) == (201, {"id": passagem["id"]})
    assert (segunda.status_code, segunda.json()) == (200, {"id": passagem["id"]})


def test_passagem_sem_chave_responde_401(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    resposta = TestClient(app).post("/api/borda/passagens", json=_passagem(cenario, caixa_a))

    assert resposta.status_code == 401


def test_passagem_de_outro_site_responde_403(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    passagem = _passagem(cenario, caixa_a, site_id=str(cenario.site_b.id))

    resposta = _caixa(app, caixa_a).post("/api/borda/passagens", json=passagem)

    assert (resposta.status_code, resposta.json()) == (
        403,
        {"detail": "a passagem é de outro site ou de outra caixa"},
    )


def test_passagem_fora_do_contrato_responde_422_apontando_o_campo(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    placa = {
        "placa": "AB12345",
        "papel": "cavalo",
        "confianca": 0.9,
        "camera_id": str(cenario.camera_a.id),
        "quadros": 1,
    }
    passagem = _passagem(cenario, caixa_a, placas=[placa])

    resposta = _caixa(app, caixa_a).post("/api/borda/passagens", json=passagem)

    assert resposta.status_code == 422
    assert [erro["loc"] for erro in resposta.json()["detail"]] == [["body", "placas", 0, "placa"]]


def test_faixa_de_outro_site_responde_422_apontando_o_campo(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    passagem = _passagem(cenario, caixa_a, faixa_id="999999")

    resposta = _caixa(app, caixa_a).post("/api/borda/passagens", json=passagem)

    assert resposta.status_code == 422
    assert [erro["loc"] for erro in resposta.json()["detail"]] == [["body", "faixa_id"]]


def test_id_de_outra_caixa_responde_409(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada, entrar: Any
) -> None:
    passagem = _passagem(cenario, caixa_a)
    _caixa(app, caixa_a).post("/api/borda/passagens", json=passagem)
    administracao = entrar(cenario.administrador.email)
    codigo = administracao.post(f"/api/admin/sites/{cenario.site_a.id}/codigos-de-ativacao").json()[
        "codigo"
    ]
    outra = TestClient(app).post("/api/borda/ativar", json={"codigo": codigo}).json()
    passagem.update(caixa_id=outra["caixa_id"])

    resposta = TestClient(app, headers={"Authorization": f"Bearer {outra['chave']}"}).post(
        "/api/borda/passagens", json=passagem
    )

    assert resposta.status_code == 409


# --- Fotos ---------------------------------------------------------------------------------


def _endereco(app: FastAPI, caixa_a: CaixaAtivada, ref: str = "2026/10/05/p1-placa.jpg") -> str:
    resposta = _caixa(app, caixa_a).post("/api/borda/fotos/endereco", json={"ref": ref})
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["ref"] == ref
    return str(corpo["endereco"])


def test_sem_endereco_publico_o_envio_parte_do_endereco_do_pedido(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    assert _endereco(app, caixa_a).startswith("http://testserver/api/borda/fotos/envio/")


def test_o_envio_parte_do_endereco_publico(
    url_banco_teste: str,
    sessao: Session,
    senhas: Senhas,
    tmp_path: Path,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
) -> None:
    # Atrás de um proxy HTTPS, o pedido chega como http://; a caixa precisa do endereço público.
    configuracao = Configuracao(
        url_banco=url_banco_teste,
        chave_cifra=CHAVE_QUALQUER,
        ambiente="producao",
        url_publica="https://patio-br.example",
        pasta_fotos=tmp_path,
        _env_file=None,
    )
    app = criar_app(configuracao, senhas=senhas)
    app.dependency_overrides[obter_sessao] = lambda: sessao

    endereco = _endereco(app, caixa_a)

    assert endereco.startswith("https://patio-br.example/api/borda/fotos/envio/")


def test_foto_vai_pelo_endereco_sem_a_chave(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    endereco = _endereco(app, caixa_a)

    # Como no S3: o endereço já autoriza o envio; a chave da caixa não vai junto.
    resposta = TestClient(app).put(endereco, content=JPEG, headers={"Content-Type": "image/jpeg"})

    assert resposta.status_code == 201


def test_mesma_foto_de_novo_responde_200_e_outra_409(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    cliente = TestClient(app)
    cliente.put(_endereco(app, caixa_a), content=JPEG)

    de_novo = cliente.put(_endereco(app, caixa_a), content=JPEG)
    outra = cliente.put(_endereco(app, caixa_a), content=JPEG.replace(b"inventada", b"trocada!!"))

    assert (de_novo.status_code, outra.status_code) == (200, 409)


def test_endereco_adulterado_responde_403(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    endereco = _endereco(app, caixa_a)

    resposta = TestClient(app).put(endereco[:-4] + "AAAA", content=JPEG)

    assert resposta.status_code == 403


def test_foto_que_nao_e_jpeg_responde_415(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    resposta = TestClient(app).put(_endereco(app, caixa_a), content=b"\x89PNG....")

    assert resposta.status_code == 415


def test_foto_grande_demais_responde_413(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    grande = JPEG[:4] + b"x" * (2 * 1024 * 1024)

    resposta = TestClient(app).put(_endereco(app, caixa_a), content=grande)

    assert resposta.status_code == 413


def test_ref_fora_da_regra_responde_422_apontando_o_campo(
    app: FastAPI, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    resposta = _caixa(app, caixa_a).post("/api/borda/fotos/endereco", json={"ref": "../fora.jpg"})

    assert resposta.status_code == 422
    assert [erro["loc"] for erro in resposta.json()["detail"]] == [["body", "ref"]]


def test_endereco_de_foto_so_com_a_chave(app: FastAPI) -> None:
    resposta = TestClient(app).post("/api/borda/fotos/endereco", json={"ref": "p1.jpg"})

    assert resposta.status_code == 401

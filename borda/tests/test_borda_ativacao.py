"""Ativação da caixa e configuração baixada da nuvem (SDD 7.4)."""

import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest

from borda.agente import ConfiguracaoDoAgente
from borda.ativacao import (
    CaixaAtivada,
    ChaveRecusadaError,
    CodigoRecusadoError,
    apagar_configuracao,
    ativar,
    baixar_configuracao,
    guardar_caixa,
    guardar_configuracao,
    ler_caixa,
    ler_configuracao,
)

NUVEM = "http://nuvem.example"
CODIGO = "AAAA-BBBB-CCCC"
CHAVE = "chave-inventada-7"

CONFIGURACAO: dict[str, Any] = {
    "caixa_id": "7",
    "site_id": "3",
    "faixas": [
        {
            "id": "11",
            "nome": "Entrada 1",
            "sentido": "entrada",
            "cameras": [
                {
                    "id": "21",
                    "nome": "frente",
                    "posicao": "frente",
                    "endereco": "rtsp://10.0.0.1:554/1",
                    "login": "leitura",
                    "senha": "s3nh4-inventada",
                },
            ],
        },
    ],
}


class NuvemFalsa:
    """Responde como a nuvem às rotas da caixa."""

    def __init__(self) -> None:
        self.respostas_da_configuracao: list[int] = []
        """Códigos a responder antes do 200 (ex.: 503 enquanto a nuvem está fora do ar)."""

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        if pedido.url.path == "/api/borda/ativar":
            if json.loads(pedido.content)["codigo"] != CODIGO:
                return httpx.Response(401, json={"detail": "código inválido"})
            return httpx.Response(201, json={"caixa_id": "7", "site_id": "3", "chave": CHAVE})
        if pedido.url.path == "/api/borda/configuracao":
            if self.respostas_da_configuracao:
                return httpx.Response(self.respostas_da_configuracao.pop(0))
            if pedido.headers.get("authorization") != f"Bearer {CHAVE}":
                return httpx.Response(401, json={"detail": "caixa não identificada"})
            return httpx.Response(200, json=CONFIGURACAO)
        return httpx.Response(404)


@pytest.fixture
def nuvem() -> NuvemFalsa:
    return NuvemFalsa()


@pytest.fixture
def cliente(nuvem: NuvemFalsa) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(nuvem))


def test_ativar_troca_o_codigo_pela_chave(cliente: httpx.Client) -> None:
    caixa = ativar(cliente, NUVEM, CODIGO)

    assert caixa == CaixaAtivada(nuvem=NUVEM, caixa_id="7", site_id="3", chave=CHAVE)


def test_codigo_recusado(cliente: httpx.Client) -> None:
    with pytest.raises(CodigoRecusadoError):
        ativar(cliente, NUVEM, "XXXX-XXXX-XXXX")


def test_baixa_a_configuracao_com_a_chave(cliente: httpx.Client) -> None:
    caixa = ativar(cliente, NUVEM, CODIGO)

    configuracao = baixar_configuracao(cliente, caixa)

    assert [c.endereco for c in configuracao.cameras] == ["rtsp://10.0.0.1:554/1"]


def test_chave_recusada(cliente: httpx.Client) -> None:
    caixa = CaixaAtivada(nuvem=NUVEM, caixa_id="7", site_id="3", chave="chave-revogada")

    with pytest.raises(ChaveRecusadaError):
        baixar_configuracao(cliente, caixa)


def test_nuvem_com_problema_e_erro_de_rede_para_quem_chama(
    cliente: httpx.Client, nuvem: NuvemFalsa
) -> None:
    caixa = ativar(cliente, NUVEM, CODIGO)
    nuvem.respostas_da_configuracao = [503]

    with pytest.raises(httpx.HTTPStatusError):
        baixar_configuracao(cliente, caixa)


def test_a_chave_nao_aparece_ao_imprimir_a_caixa() -> None:
    caixa = CaixaAtivada(nuvem=NUVEM, caixa_id="7", site_id="3", chave=CHAVE)

    assert CHAVE not in repr(caixa)


@pytest.mark.integracao  # grava no disco
def test_caixa_guardada_volta_igual(tmp_path: Path) -> None:
    caixa = CaixaAtivada(nuvem=NUVEM, caixa_id="7", site_id="3", chave=CHAVE)

    guardar_caixa(caixa, tmp_path / "caixa" / "caixa.json")

    assert ler_caixa(tmp_path / "caixa" / "caixa.json") == caixa


@pytest.mark.integracao
@pytest.mark.skipif(os.name == "nt", reason="as permissões de arquivo do Windows são outras")
def test_so_o_dono_le_a_chave_guardada(tmp_path: Path) -> None:
    arquivo = tmp_path / "caixa.json"

    guardar_caixa(CaixaAtivada(nuvem=NUVEM, caixa_id="7", site_id="3", chave=CHAVE), arquivo)

    assert arquivo.stat().st_mode & 0o777 == 0o600


def test_sem_caixa_guardada(tmp_path: Path) -> None:
    assert ler_caixa(tmp_path / "caixa.json") is None


# --- A configuração guardada (D-66) ---------------------------------------------------------


def test_a_configuracao_volta_ao_formato_da_nuvem() -> None:
    com_faixa_vazia = CONFIGURACAO | {
        "faixas": [
            *CONFIGURACAO["faixas"],
            {"id": "12", "nome": "Saída", "sentido": "saida", "cameras": []},
        ]
    }

    assert ConfiguracaoDoAgente.de_json(com_faixa_vazia).para_json() == com_faixa_vazia


@pytest.mark.integracao  # grava no disco
def test_configuracao_guardada_volta_igual(tmp_path: Path) -> None:
    configuracao = ConfiguracaoDoAgente.de_json(CONFIGURACAO)

    guardar_configuracao(configuracao, tmp_path / "caixa" / "configuracao.json")

    assert ler_configuracao(tmp_path / "caixa" / "configuracao.json") == configuracao


@pytest.mark.integracao
@pytest.mark.skipif(os.name == "nt", reason="as permissões de arquivo do Windows são outras")
def test_so_o_dono_le_a_configuracao_guardada(tmp_path: Path) -> None:
    arquivo = tmp_path / "configuracao.json"
    arquivo.write_text("{}", encoding="utf-8")
    arquivo.chmod(0o644)

    guardar_configuracao(ConfiguracaoDoAgente.de_json(CONFIGURACAO), arquivo)

    # As senhas das câmeras estão nela.
    assert arquivo.stat().st_mode & 0o777 == 0o600


def test_sem_configuracao_guardada(tmp_path: Path) -> None:
    assert ler_configuracao(tmp_path / "configuracao.json") is None


@pytest.mark.integracao
@pytest.mark.parametrize("conteudo", ["não é json", "[]", "{}", '{"caixa_id": "7"}'])
def test_configuracao_guardada_estragada_e_ignorada(tmp_path: Path, conteudo: str) -> None:
    arquivo = tmp_path / "configuracao.json"
    arquivo.write_text(conteudo, encoding="utf-8")

    assert ler_configuracao(arquivo) is None


@pytest.mark.integracao
def test_apagar_a_configuracao_guardada(tmp_path: Path) -> None:
    arquivo = tmp_path / "configuracao.json"
    guardar_configuracao(ConfiguracaoDoAgente.de_json(CONFIGURACAO), arquivo)

    apagar_configuracao(arquivo)
    apagar_configuracao(arquivo)  # apagar de novo não é erro

    assert not arquivo.exists()

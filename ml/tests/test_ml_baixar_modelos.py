"""Download dos modelos do leitor v0 (T15): só com o resumo SHA-256 conferido, fora do Git."""

import hashlib
import re
from pathlib import Path

import httpx
import pytest

from ml.baixar_modelos import (
    MODELOS_V0,
    PASTA_PADRAO,
    ArquivoDeModelo,
    ResumoErradoError,
    baixar,
    extrair_dicionario,
)

pytestmark = pytest.mark.integracao  # grava no disco

CONTEUDO = b"pesos-inventados-do-teste"


def _modelo(conteudo: bytes = CONTEUDO) -> ArquivoDeModelo:
    return ArquivoDeModelo(
        arquivo="teste.onnx",
        endereco="https://modelos.example/teste.onnx",
        sha256=hashlib.sha256(conteudo).hexdigest(),
        licenca="inventada",
        uso="avaliação interna",
    )


class Servidor:
    def __init__(self, conteudo: bytes = CONTEUDO) -> None:
        self.conteudo = conteudo
        self.pedidos = 0

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos += 1
        return httpx.Response(200, content=self.conteudo)


def _cliente(servidor: Servidor) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(servidor))


def test_baixa_e_confere_o_resumo(tmp_path: Path) -> None:
    baixar([_modelo()], tmp_path, _cliente(Servidor()))

    assert (tmp_path / "teste.onnx").read_bytes() == CONTEUDO


def test_resumo_errado_e_recusado_e_nao_deixa_arquivo(tmp_path: Path) -> None:
    with pytest.raises(ResumoErradoError, match=r"teste\.onnx"):
        baixar([_modelo()], tmp_path, _cliente(Servidor(b"outro-conteudo")))

    assert list(tmp_path.iterdir()) == []


def test_arquivo_ja_baixado_e_certo_nao_baixa_de_novo(tmp_path: Path) -> None:
    (tmp_path / "teste.onnx").write_bytes(CONTEUDO)
    servidor = Servidor()

    baixar([_modelo()], tmp_path, _cliente(servidor))

    assert servidor.pedidos == 0


def test_arquivo_estragado_e_baixado_de_novo(tmp_path: Path) -> None:
    (tmp_path / "teste.onnx").write_bytes(b"pela-metade")
    servidor = Servidor()

    baixar([_modelo()], tmp_path, _cliente(servidor))

    assert (servidor.pedidos, (tmp_path / "teste.onnx").read_bytes()) == (1, CONTEUDO)


def test_extrai_o_dicionario_de_caracteres_da_configuracao(tmp_path: Path) -> None:
    configuracao = tmp_path / "inference.yml"
    configuracao.write_text(
        "PostProcess:\n  name: CTCLabelDecode\n  character_dict:\n  - '0'\n  - A\n  - ' '\n",
        encoding="utf-8",
    )

    extrair_dicionario(configuracao, tmp_path / "dicionario.txt")

    assert (tmp_path / "dicionario.txt").read_text(encoding="utf-8").split("\n") == ["0", "A", " "]


def test_modelos_do_v0_tem_resumo_licenca_e_versao_fixa() -> None:
    for modelo in MODELOS_V0:
        assert re.fullmatch(r"[0-9a-f]{64}", modelo.sha256), modelo.arquivo
        assert modelo.endereco.startswith("https://")
        assert modelo.licenca and modelo.uso
        if "huggingface.co" in modelo.endereco:
            # A versão do repositório fica fixa: o mesmo endereço sempre baixa o mesmo arquivo.
            assert re.search(r"/resolve/[0-9a-f]{40}/", modelo.endereco), modelo.arquivo


def test_detector_do_v0_fica_marcado_so_para_avaliacao_interna() -> None:
    # T13: os pesos do YOLOX não têm licença declarada (SDD 4.1).
    detector = next(m for m in MODELOS_V0 if m.arquivo.startswith("yolox"))

    assert detector.uso == "só avaliação interna"


def test_pasta_padrao_fica_dentro_de_modelos_que_o_git_ignora() -> None:
    assert PASTA_PADRAO.parts[:2] == ("modelos", "v0")

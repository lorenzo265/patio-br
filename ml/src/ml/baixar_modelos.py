"""Baixa os modelos do leitor v0 para ``modelos/v0`` (fora do Git): ``uv run tarefas modelos``.

Cada arquivo tem endereço com versão fixa e resumo SHA-256 conferido depois do download: o que
chega é exatamente o que foi conferido na T13. A licença e o uso permitido de cada um estão em
``docs/validacao/fatos-tecnicos-stack.md``. O detector (YOLOX) não tem licença declarada para os
pesos: só avaliação interna e a demonstração do mês 1 (SDD 4.1).
"""

import hashlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml

PASTA_PADRAO = Path("modelos") / "v0"
"""Relativa à raiz do repositório (``modelos/`` fica fora do Git)."""


@dataclass(frozen=True)
class ArquivoDeModelo:
    """Um arquivo de modelo: onde baixar, como conferir e o que a licença deixa fazer."""

    arquivo: str
    endereco: str
    sha256: str
    licenca: str
    uso: str


_HF_DET = "https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det_onnx/resolve/e6f4fa85f00e168c862bc462aebca69eef9b3d3d"
_HF_REC = "https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_onnx/resolve/3fafbc3b5dcf93dd72add9f48368be8a3a2cd33b"

MODELOS_V0: tuple[ArquivoDeModelo, ...] = (
    ArquivoDeModelo(
        arquivo="yolox_tiny.onnx",
        endereco=(
            "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/"
            "yolox_tiny.onnx"
        ),
        # O projeto não publica o resumo; este é o do arquivo baixado em 2026-10-03 (T15).
        sha256="427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7",
        licenca="código Apache-2.0; pesos sem licença declarada (treinados no COCO)",
        uso="só avaliação interna",
    ),
    ArquivoDeModelo(
        arquivo="texto_deteccao.onnx",
        endereco=f"{_HF_DET}/inference.onnx",
        sha256="a431985659dc921974177a95adcfbb90fd9e51989a5e04d70d0b75f597b6e61d",
        licenca="Apache-2.0 declarada no cartão do modelo (PP-OCRv5_mobile_det)",
        uso="permitido pela licença; no produto, só pesos nossos (SDD 4.1)",
    ),
    ArquivoDeModelo(
        arquivo="texto_leitura.onnx",
        endereco=f"{_HF_REC}/inference.onnx",
        sha256="b5f833dfc5d0eb71da397b4efa06ebeee9b431b690a47d6af40d77d8eabc557f",
        licenca="Apache-2.0 declarada no cartão do modelo (en_PP-OCRv5_mobile_rec)",
        uso="permitido pela licença; no produto, só pesos nossos (SDD 4.1)",
    ),
    ArquivoDeModelo(
        arquivo="texto_leitura.yml",
        endereco=f"{_HF_REC}/inference.yml",
        sha256="27e91d0582f40168aa218303c76e184bc78fa7a5d105aad0cfbad8458b441067",
        licenca="Apache-2.0 (o mesmo modelo)",
        uso="configuração do modelo de leitura (o dicionário de caracteres)",
    ),
)

DICIONARIO = "texto_leitura_dicionario.txt"
"""Os caracteres que o modelo de leitura conhece, um por linha (tirados do ``.yml``)."""


class ResumoErradoError(Exception):
    """O arquivo baixado não tem o resumo SHA-256 esperado (foi trocado ou veio pela metade)."""


def baixar(modelos: Sequence[ArquivoDeModelo], pasta: Path, cliente: httpx.Client) -> None:
    """Baixa os modelos que faltam (ou estão estragados) e confere o resumo de cada um.

    Raises:
        ResumoErradoError: se um arquivo baixado não tiver o resumo esperado (ele é apagado).
        httpx.HTTPError: se o download falhar.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    for modelo in modelos:
        destino = pasta / modelo.arquivo
        if destino.is_file() and _resumo(destino.read_bytes()) == modelo.sha256:
            continue
        resposta = cliente.get(modelo.endereco, follow_redirects=True)
        resposta.raise_for_status()
        if _resumo(resposta.content) != modelo.sha256:
            destino.unlink(missing_ok=True)
            raise ResumoErradoError(f"{modelo.arquivo}: o resumo não confere com o da T13")
        parcial = destino.with_name(destino.name + ".parcial")
        parcial.write_bytes(resposta.content)
        parcial.replace(destino)


def extrair_dicionario(configuracao: Path, destino: Path) -> None:
    """Grava os caracteres do modelo de leitura (``PostProcess.character_dict``), um por linha."""
    dados = yaml.safe_load(configuracao.read_text(encoding="utf-8"))
    caracteres = [str(c) for c in dados["PostProcess"]["character_dict"]]
    destino.write_text("\n".join(caracteres), encoding="utf-8")


def _resumo(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def principal(pasta: Path = PASTA_PADRAO) -> int:
    """Baixa os modelos do v0 e prepara o dicionário; devolve o código de saída."""
    print(f"modelos do leitor v0 em {pasta} (licenças: docs/validacao/fatos-tecnicos-stack.md)")
    try:
        with httpx.Client(timeout=120) as cliente:
            baixar(MODELOS_V0, pasta, cliente)
    except (ResumoErradoError, httpx.HTTPError) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    extrair_dicionario(pasta / "texto_leitura.yml", pasta / DICIONARIO)
    for modelo in MODELOS_V0:
        print(f"  {modelo.arquivo}: {modelo.uso}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())

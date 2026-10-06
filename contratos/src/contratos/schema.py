"""JSON Schema de cada formato do contrato (a Passagem e a Saude), gerado a partir do modelo.

Os arquivos de ``contratos/schema/`` (``passagem.v1.json``, ``saude.v1.json``) descrevem o
contrato para quem não usa Python. Eles nunca são editados à mão: depois de mudar um modelo,
rode ``uv run python -m contratos.schema``. Um teste falha se um arquivo estiver desatualizado.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from contratos.passagem import Passagem
from contratos.saude import Saude

PASTA_DOS_SCHEMAS = Path(__file__).resolve().parents[2] / "schema"
"""``contratos/schema/``, fora do código do pacote."""

SCHEMAS: dict[str, type[BaseModel]] = {"passagem.v1.json": Passagem, "saude.v1.json": Saude}
"""Cada arquivo e o modelo de onde ele sai."""

VERSAO_DO_JSON_SCHEMA = "https://json-schema.org/draft/2020-12/schema"


def gerar_schema(modelo: type[BaseModel]) -> str:
    """Devolve o JSON Schema do modelo como texto, pronto para gravar no arquivo."""
    schema = {"$schema": VERSAO_DO_JSON_SCHEMA, **modelo.model_json_schema()}
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def principal() -> None:
    """Grava cada schema em :data:`PASTA_DOS_SCHEMAS` (com fim de linha ``\\n`` em qualquer
    sistema)."""
    PASTA_DOS_SCHEMAS.mkdir(exist_ok=True)
    for nome, modelo in SCHEMAS.items():
        arquivo = PASTA_DOS_SCHEMAS / nome
        arquivo.write_text(gerar_schema(modelo), encoding="utf-8", newline="\n")
        print(f"gravado: {arquivo}")


if __name__ == "__main__":
    principal()

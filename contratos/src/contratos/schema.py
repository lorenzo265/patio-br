"""JSON Schema da Passagem, gerado a partir do modelo.

O arquivo ``contratos/schema/passagem.v1.json`` descreve o contrato para quem não usa Python.
Ele nunca é editado à mão: depois de mudar o modelo, rode ``uv run python -m contratos.schema``.
Um teste falha se o arquivo estiver desatualizado.
"""

import json
from pathlib import Path

from contratos.passagem import Passagem

ARQUIVO_SCHEMA = Path(__file__).resolve().parents[2] / "schema" / "passagem.v1.json"
"""Fica em ``contratos/schema/``, fora do código do pacote."""

VERSAO_DO_JSON_SCHEMA = "https://json-schema.org/draft/2020-12/schema"


def gerar_schema() -> str:
    """Devolve o JSON Schema da Passagem como texto, pronto para gravar no arquivo."""
    schema = {"$schema": VERSAO_DO_JSON_SCHEMA, **Passagem.model_json_schema()}
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def principal() -> None:
    """Grava o schema em :data:`ARQUIVO_SCHEMA` (com fim de linha ``\\n`` em qualquer sistema)."""
    ARQUIVO_SCHEMA.parent.mkdir(exist_ok=True)
    ARQUIVO_SCHEMA.write_text(gerar_schema(), encoding="utf-8", newline="\n")
    print(f"gravado: {ARQUIVO_SCHEMA}")


if __name__ == "__main__":
    principal()

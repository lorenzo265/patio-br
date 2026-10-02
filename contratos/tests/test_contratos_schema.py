"""O JSON Schema da Passagem é gerado do modelo e fica em contratos/schema/."""

import json

import pytest

from contratos.schema import ARQUIVO_SCHEMA, gerar_schema


@pytest.mark.integracao
def test_arquivo_do_schema_esta_em_dia_com_o_modelo() -> None:
    gravado = ARQUIVO_SCHEMA.read_text(encoding="utf-8")

    assert gravado == gerar_schema(), (
        f"{ARQUIVO_SCHEMA.name} está desatualizado: rode `uv run python -m contratos.schema`"
    )


def test_schema_declara_a_versao_do_json_schema() -> None:
    assert json.loads(gerar_schema())["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_exige_placa_no_formato_canonico() -> None:
    placa_lida = json.loads(gerar_schema())["$defs"]["PlacaLida"]

    assert placa_lida["properties"]["placa"]["pattern"] == "^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"

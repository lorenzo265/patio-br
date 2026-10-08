"""O JSON Schema de cada formato (a Passagem e a Saude) é gerado do modelo e fica em
contratos/schema/."""

import json

import pytest

from contratos.passagem import Passagem
from contratos.saude import Saude
from contratos.schema import PASTA_DOS_SCHEMAS, SCHEMAS, gerar_schema


@pytest.mark.integracao
@pytest.mark.parametrize("nome", list(SCHEMAS))
def test_arquivo_do_schema_esta_em_dia_com_o_modelo(nome: str) -> None:
    gravado = (PASTA_DOS_SCHEMAS / nome).read_text(encoding="utf-8")

    assert gravado == gerar_schema(SCHEMAS[nome]), (
        f"{nome} está desatualizado: rode `uv run python -m contratos.schema`"
    )


def test_cada_formato_tem_o_seu_arquivo() -> None:
    assert {"passagem.v1.json": Passagem, "saude.v1.json": Saude} == SCHEMAS


def test_schema_declara_a_versao_do_json_schema() -> None:
    for modelo in SCHEMAS.values():
        assert json.loads(gerar_schema(modelo))["$schema"] == (
            "https://json-schema.org/draft/2020-12/schema"
        )


def test_schema_exige_placa_no_formato_canonico() -> None:
    placa_lida = json.loads(gerar_schema(Passagem))["$defs"]["PlacaLida"]

    assert placa_lida["properties"]["placa"]["pattern"] == "^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"

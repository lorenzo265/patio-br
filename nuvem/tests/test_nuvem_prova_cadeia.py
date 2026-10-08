"""A regra do resumo da cadeia de prova (D-69), sem banco."""

import hashlib
import json
from dataclasses import replace

from nuvem.prova import cadeia
from nuvem.prova.cadeia import Elo


def _cadeia(*conteudos: dict[str, object]) -> list[Elo]:
    elos: list[Elo] = []
    anterior = cadeia.INICIO
    for ordem, conteudo in enumerate(conteudos, start=1):
        resumo = cadeia.resumo_do_elo(anterior, "evento", str(ordem), conteudo)
        elos.append(Elo(ordem, "evento", str(ordem), conteudo, anterior, resumo))
        anterior = resumo
    return elos


def test_o_resumo_segue_a_regra_escrita_no_arquivo() -> None:
    conteudo = {"tipo": "check_in", "momento": "2026-10-06T17:00:00+00:00", "placa": "ÁBC"}

    resumo = cadeia.resumo_do_elo(cadeia.INICIO, "evento", "12", conteudo)

    # A regra, refeita à mão: anterior, quebra de linha e o JSON com as chaves em ordem.
    texto = json.dumps(
        {"conteudo": conteudo, "referencia": "12", "tipo": "evento"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    esperado = hashlib.sha256(f"{'0' * 64}\n{texto}".encode()).hexdigest()
    assert resumo == esperado
    assert len(resumo) == 64


def test_a_ordem_das_chaves_nao_muda_o_resumo() -> None:
    um = cadeia.resumo_do_elo(cadeia.INICIO, "evento", "1", {"a": 1, "b": [1, 2]})
    outro = cadeia.resumo_do_elo(cadeia.INICIO, "evento", "1", {"b": [1, 2], "a": 1})

    assert um == outro


def test_qualquer_mudanca_muda_o_resumo() -> None:
    base = cadeia.resumo_do_elo(cadeia.INICIO, "evento", "1", {"a": 1})

    assert cadeia.resumo_do_elo(cadeia.INICIO, "evento", "1", {"a": 2}) != base
    assert cadeia.resumo_do_elo(cadeia.INICIO, "evento", "2", {"a": 1}) != base
    assert cadeia.resumo_do_elo(cadeia.INICIO, "foto", "1", {"a": 1}) != base
    assert cadeia.resumo_do_elo("1" * 64, "evento", "1", {"a": 1}) != base


def test_a_cadeia_inteira_confere() -> None:
    assert cadeia.primeira_quebra(_cadeia({"a": 1}, {"b": 2}, {"c": 3})) is None
    assert cadeia.primeira_quebra([]) is None


def test_o_conteudo_mudado_quebra_aquele_elo() -> None:
    elos = _cadeia({"a": 1}, {"b": 2}, {"c": 3})
    elos[1] = replace(elos[1], conteudo={"b": 3})

    assert cadeia.primeira_quebra(elos) == cadeia.Quebra(2, "o resumo não bate com o conteúdo")


def test_a_cadeia_refeita_a_partir_do_meio_quebra_no_seguinte() -> None:
    # Quem muda o elo 2 e refaz o resumo dele ainda quebra a ligação com o 3.
    elos = _cadeia({"a": 1}, {"b": 2}, {"c": 3})
    resumo = cadeia.resumo_do_elo(elos[1].anterior, "evento", "2", {"b": 3})
    elos[1] = replace(elos[1], conteudo={"b": 3}, resumo=resumo)

    assert cadeia.primeira_quebra(elos) == cadeia.Quebra(3, "o resumo do anterior não bate")


def test_o_primeiro_elo_comeca_dos_zeros() -> None:
    elos = _cadeia({"a": 1})
    resumo = cadeia.resumo_do_elo("1" * 64, "evento", "1", {"a": 1})
    elos[0] = replace(elos[0], anterior="1" * 64, resumo=resumo)

    assert cadeia.primeira_quebra(elos) == cadeia.Quebra(1, "o resumo do anterior não bate")


def test_o_elo_que_falta_quebra_a_cadeia() -> None:
    elos = _cadeia({"a": 1}, {"b": 2}, {"c": 3})

    assert cadeia.primeira_quebra([elos[0], elos[2]]) == cadeia.Quebra(
        3, "falta um elo antes deste"
    )

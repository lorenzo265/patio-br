"""Ativação da caixa de borda (SDD 7.4): código de uso único, chave própria, revogação."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from nuvem.erros import NaoEncontradoError
from nuvem.frota import servico
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)


def _codigo(sessao: Session, cenario: Demonstracao, agora: datetime = AGORA) -> str:
    return servico.gerar_codigo_de_ativacao(
        sessao, cenario.site_a.id, administrador_id=cenario.administrador.id, agora=agora
    ).codigo


def test_codigo_tem_tres_grupos_de_4_letras_e_numeros(
    sessao: Session, cenario: Demonstracao
) -> None:
    assert re.fullmatch(r"[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}", _codigo(sessao, cenario))


def test_codigo_nao_tem_caracteres_que_se_confundem(sessao: Session, cenario: Demonstracao) -> None:
    # Quem digita o código na caixa não pode ficar em dúvida entre 0 e O, ou 1 e I.
    codigos = "".join(_codigo(sessao, cenario) for _ in range(20))

    assert not set(codigos) & set("0O1IL")


def test_banco_guarda_so_o_resumo_do_codigo(sessao: Session, cenario: Demonstracao) -> None:
    codigo = _codigo(sessao, cenario)

    gravados = sessao.execute(text("select codigo_resumo from codigo_ativacao")).scalars().all()
    assert all(codigo.replace("-", "") not in gravado for gravado in gravados)


def test_ativar_cria_a_caixa_no_site_do_codigo(sessao: Session, cenario: Demonstracao) -> None:
    ativada = servico.ativar(sessao, _codigo(sessao, cenario), agora=AGORA)

    caixa = servico.caixa_da_chave(sessao, ativada.chave)
    assert caixa is not None
    assert (caixa.site_id, caixa.empresa_id) == (cenario.site_a.id, cenario.empresa_a.id)
    assert caixa.caixa_id == ativada.caixa_id


def test_codigo_usado_duas_vezes_e_recusado(sessao: Session, cenario: Demonstracao) -> None:
    codigo = _codigo(sessao, cenario)
    servico.ativar(sessao, codigo, agora=AGORA)

    with pytest.raises(servico.CodigoRecusadoError):
        servico.ativar(sessao, codigo, agora=AGORA + timedelta(minutes=1))


def test_codigo_vale_24_horas(sessao: Session, cenario: Demonstracao) -> None:
    codigo = _codigo(sessao, cenario)

    assert servico.ativar(sessao, codigo, agora=AGORA + timedelta(hours=24, seconds=-1))


def test_codigo_vencido_e_recusado(sessao: Session, cenario: Demonstracao) -> None:
    codigo = _codigo(sessao, cenario)

    with pytest.raises(servico.CodigoRecusadoError):
        servico.ativar(sessao, codigo, agora=AGORA + timedelta(hours=24))


def test_codigo_inventado_e_recusado(sessao: Session, cenario: Demonstracao) -> None:
    with pytest.raises(servico.CodigoRecusadoError):
        servico.ativar(sessao, "ABCD-EFGH-JKMN", agora=AGORA)


def test_codigo_digitado_em_minusculas_e_sem_hifen_vale(
    sessao: Session, cenario: Demonstracao
) -> None:
    codigo = _codigo(sessao, cenario)

    assert servico.ativar(sessao, f" {codigo.replace('-', '').lower()} ", agora=AGORA)


def test_banco_guarda_so_o_resumo_da_chave(sessao: Session, cenario: Demonstracao) -> None:
    ativada = servico.ativar(sessao, _codigo(sessao, cenario), agora=AGORA)

    gravada = sessao.execute(text("select chave_resumo from caixa_borda")).scalar_one()
    assert ativada.chave not in gravada


def test_chave_revogada_nao_identifica_mais_a_caixa(sessao: Session, cenario: Demonstracao) -> None:
    ativada = servico.ativar(sessao, _codigo(sessao, cenario), agora=AGORA)

    servico.revogar(sessao, ativada.caixa_id, agora=AGORA)

    assert servico.caixa_da_chave(sessao, ativada.chave) is None


def test_chave_inventada_nao_identifica_nada(sessao: Session, cenario: Demonstracao) -> None:
    assert servico.caixa_da_chave(sessao, "chave-inventada") is None


def test_revogar_caixa_que_nao_existe(sessao: Session, cenario: Demonstracao) -> None:
    with pytest.raises(NaoEncontradoError):
        servico.revogar(sessao, 999_999, agora=AGORA)


def test_codigo_para_site_que_nao_existe(sessao: Session, cenario: Demonstracao) -> None:
    with pytest.raises(NaoEncontradoError):
        servico.gerar_codigo_de_ativacao(
            sessao, 999_999, administrador_id=cenario.administrador.id, agora=AGORA
        )

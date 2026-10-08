"""Regras do agendamento no banco (SDD 3.4, 5.1 e 5.5): gravar, reenviar, cancelar e separar."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nuvem.agendamento import servico
from nuvem.agendamento.conectores import Lido, Recusado, ler_dados
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento, MudancaAgendamento, Origem
from nuvem.agendamento.servico import (
    AgendamentoCanceladoError,
    Relatorio,
    SiteDoAgendamento,
)
from nuvem.banco import SQLSTATE_CHAVE_ESTRANGEIRA, SQLSTATE_UNICIDADE, sqlstate
from nuvem.cadastro.acesso import Acesso
from nuvem.erros import NaoEncontradoError
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)
INICIO = datetime(2026, 11, 5, 11, 0, tzinfo=UTC)
"""8h em São Paulo, no dia seguinte a ``AGORA``."""


def _dados(**mudancas: Any) -> DadosDoAgendamento:
    campos: dict[str, Any] = {
        "codigo_externo": "AG-1",
        "janela_inicio": INICIO,
        "janela_fim": INICIO + timedelta(hours=2),
        "tipo": "descarga",
        "placa_cavalo": "ABC1D23",
        "placas_reboques": ["DEF4G56"],
        "motorista_nome": "Motorista Inventado",
        "motorista_celular": "11987654321",
        "toneladas": "32.5",
    }
    campos.update(mudancas)
    return DadosDoAgendamento.model_validate(campos)


@pytest.fixture
def site_a(sessao: Session, cenario: Demonstracao, acesso_a: Acesso) -> SiteDoAgendamento:
    """O site_a, para o gestor A gravar agendamentos."""
    return servico.site_para_agendar(sessao, acesso_a, cenario.site_a.id)


def _gravar(
    sessao: Session, site: SiteDoAgendamento, origem: Origem = "planilha", **mudancas: Any
) -> servico.Gravado:
    return servico.gravar(sessao, site, origem, _dados(**mudancas), agora=AGORA)


def _mudancas(sessao: Session, agendamento: Agendamento) -> list[MudancaAgendamento]:
    return list(
        sessao.scalars(
            select(MudancaAgendamento)
            .where(MudancaAgendamento.agendamento_id == agendamento.id)
            .order_by(MudancaAgendamento.id)
        )
    )


# --- Gravar ----------------------------------------------------------------------------------


def test_grava_o_agendamento_com_os_dados_do_conector(
    sessao: Session, cenario: Demonstracao, site_a: SiteDoAgendamento
) -> None:
    gravado = _gravar(sessao, site_a)
    agendamento = gravado.agendamento

    assert gravado.resultado == "criado"
    assert (agendamento.empresa_id, agendamento.site_id) == (
        cenario.empresa_a.id,
        cenario.site_a.id,
    )
    assert (agendamento.origem, agendamento.codigo_externo, agendamento.situacao) == (
        "planilha",
        "AG-1",
        "ativo",
    )
    assert (agendamento.placa_cavalo, agendamento.placas_reboques) == ("ABC1D23", ["DEF4G56"])
    assert agendamento.motorista_celular == "+5511987654321"
    assert agendamento.toneladas == Decimal("32.5")
    assert agendamento.janela_inicio == INICIO
    assert agendamento.criado_em == agendamento.atualizado_em == AGORA


def test_a_criacao_fica_registrada_com_quem_gravou(
    sessao: Session, cenario: Demonstracao, site_a: SiteDoAgendamento
) -> None:
    agendamento = _gravar(sessao, site_a).agendamento

    [criacao] = _mudancas(sessao, agendamento)

    assert (criacao.tipo, criacao.via, criacao.usuario_id, criacao.momento) == (
        "criado",
        "planilha",
        cenario.gestor_a.id,
        AGORA,
    )
    assert criacao.antes is None
    assert criacao.depois["placa_cavalo"] == "ABC1D23"
    assert criacao.depois["janela_inicio"] == INICIO.isoformat()
    assert criacao.depois["toneladas"] == "32.5"


# --- Reenvio (D-33) ---------------------------------------------------------------------------


def test_reenviar_igual_nao_muda_nada(sessao: Session, site_a: SiteDoAgendamento) -> None:
    primeiro = _gravar(sessao, site_a).agendamento

    de_novo = servico.gravar(sessao, site_a, "planilha", _dados(), agora=AGORA + timedelta(hours=1))

    assert (de_novo.resultado, de_novo.agendamento.id) == ("igual", primeiro.id)
    assert de_novo.agendamento.atualizado_em == AGORA
    assert len(_mudancas(sessao, primeiro)) == 1
    assert sessao.scalar(select(Agendamento.id).where(Agendamento.id != primeiro.id)) is None


def test_reenviar_com_mudanca_atualiza_e_registra_o_que_mudou(
    sessao: Session, site_a: SiteDoAgendamento
) -> None:
    primeiro = _gravar(sessao, site_a).agendamento
    depois = AGORA + timedelta(hours=1)

    alterado = servico.gravar(
        sessao,
        site_a,
        "planilha",
        _dados(placa_cavalo="XYZ9K87", toneladas="30"),
        agora=depois,
    )

    assert (alterado.resultado, alterado.agendamento.id) == ("alterado", primeiro.id)
    assert alterado.agendamento.placa_cavalo == "XYZ9K87"
    assert alterado.agendamento.atualizado_em == depois
    mudanca = _mudancas(sessao, primeiro)[-1]
    assert (mudanca.tipo, mudanca.momento) == ("alterado", depois)
    assert mudanca.antes == {"placa_cavalo": "ABC1D23", "toneladas": "32.5"}
    assert mudanca.depois == {"placa_cavalo": "XYZ9K87", "toneladas": "30"}


def test_reenvio_que_tira_um_campo_registra_o_vazio(
    sessao: Session, site_a: SiteDoAgendamento
) -> None:
    primeiro = _gravar(sessao, site_a).agendamento

    _gravar(sessao, site_a, placas_reboques=[], motorista_nome=None)

    mudanca = _mudancas(sessao, primeiro)[-1]
    assert mudanca.antes == {
        "placas_reboques": ["DEF4G56"],
        "motorista_nome": "Motorista Inventado",
    }
    assert mudanca.depois == {"placas_reboques": [], "motorista_nome": None}


def test_mesmo_codigo_de_outra_origem_e_outro_agendamento(
    sessao: Session, site_a: SiteDoAgendamento
) -> None:
    da_planilha = _gravar(sessao, site_a, "planilha").agendamento
    do_link = _gravar(sessao, site_a, "link").agendamento

    assert da_planilha.id != do_link.id


def test_mesmo_codigo_em_outro_site_e_outro_agendamento(
    sessao: Session, cenario: Demonstracao, site_a: SiteDoAgendamento, acesso_b: Acesso
) -> None:
    site_b = servico.site_para_agendar(sessao, acesso_b, cenario.site_b.id)

    assert _gravar(sessao, site_a).agendamento.id != _gravar(sessao, site_b).agendamento.id


# --- Cancelar ---------------------------------------------------------------------------------


def test_cancelar_registra_quem_cancelou(
    sessao: Session, cenario: Demonstracao, site_a: SiteDoAgendamento, acesso_a: Acesso
) -> None:
    agendamento = _gravar(sessao, site_a).agendamento
    depois = AGORA + timedelta(hours=2)

    servico.cancelar(sessao, acesso_a, agendamento.id, agora=depois)

    assert (agendamento.situacao, agendamento.atualizado_em) == ("cancelado", depois)
    mudanca = _mudancas(sessao, agendamento)[-1]
    assert (mudanca.tipo, mudanca.via, mudanca.usuario_id) == (
        "cancelado",
        "painel",
        cenario.gestor_a.id,
    )
    assert (mudanca.antes, mudanca.depois) == ({"situacao": "ativo"}, {"situacao": "cancelado"})


def test_cancelar_de_novo_nao_registra_outra_mudanca(
    sessao: Session, site_a: SiteDoAgendamento, acesso_a: Acesso
) -> None:
    agendamento = _gravar(sessao, site_a).agendamento
    servico.cancelar(sessao, acesso_a, agendamento.id, agora=AGORA)

    servico.cancelar(sessao, acesso_a, agendamento.id, agora=AGORA + timedelta(hours=1))

    assert [m.tipo for m in _mudancas(sessao, agendamento)] == ["criado", "cancelado"]


def test_cancelado_nao_volta_pelo_reenvio(
    sessao: Session, site_a: SiteDoAgendamento, acesso_a: Acesso
) -> None:
    agendamento = _gravar(sessao, site_a).agendamento
    servico.cancelar(sessao, acesso_a, agendamento.id, agora=AGORA)

    with pytest.raises(AgendamentoCanceladoError, match="AG-1"):
        _gravar(sessao, site_a, toneladas="10")

    assert (agendamento.situacao, agendamento.toneladas) == ("cancelado", Decimal("32.5"))


def test_cancelar_agendamento_de_outra_empresa_nao_encontra(
    sessao: Session, site_a: SiteDoAgendamento, acesso_b: Acesso
) -> None:
    agendamento = _gravar(sessao, site_a).agendamento

    with pytest.raises(NaoEncontradoError):
        servico.cancelar(sessao, acesso_b, agendamento.id, agora=AGORA)

    assert agendamento.situacao == "ativo"


# --- Ler --------------------------------------------------------------------------------------


def test_obter_traz_o_agendamento_do_proprio_site(
    sessao: Session, site_a: SiteDoAgendamento, acesso_a: Acesso
) -> None:
    agendamento = _gravar(sessao, site_a).agendamento

    assert servico.obter(sessao, acesso_a, agendamento.id) == agendamento


def test_agendamento_de_outra_empresa_nao_e_encontrado(
    sessao: Session, site_a: SiteDoAgendamento, acesso_b: Acesso
) -> None:
    agendamento = _gravar(sessao, site_a).agendamento

    with pytest.raises(NaoEncontradoError):
        servico.obter(sessao, acesso_b, agendamento.id)


def test_agendamento_de_site_fora_do_alcance_nao_e_encontrado(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    # O site_a2 é da empresa A, mas o gestor A não o vê; a administração grava por lá.
    site_a2 = SiteDoAgendamento(
        empresa_id=cenario.empresa_a.id, site_id=cenario.site_a2.id, usuario_id=None
    )
    agendamento = _gravar(sessao, site_a2).agendamento

    with pytest.raises(NaoEncontradoError):
        servico.obter(sessao, acesso_a, agendamento.id)


def test_site_para_agendar_recusa_site_fora_do_alcance(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    for site in (cenario.site_a2, cenario.site_b):
        with pytest.raises(NaoEncontradoError):
            servico.site_para_agendar(sessao, acesso_a, site.id)


def test_listar_traz_as_janelas_que_tocam_o_periodo_em_ordem(
    sessao: Session, cenario: Demonstracao, site_a: SiteDoAgendamento, acesso_a: Acesso
) -> None:
    def gravar(codigo: str, inicio: datetime) -> Agendamento:
        return _gravar(
            sessao, site_a, codigo_externo=codigo, janela_inicio=inicio,
            janela_fim=inicio + timedelta(hours=2),
        ).agendamento  # fmt: skip

    tarde = gravar("tarde", INICIO + timedelta(hours=6))
    cedo = gravar("cedo", INICIO)
    gravar("ontem", INICIO - timedelta(days=1))
    madrugada = gravar("madrugada", INICIO - timedelta(hours=3))  # termina 1h depois de de
    gravar("amanha", INICIO + timedelta(days=1))
    de = INICIO - timedelta(hours=2)

    lista = servico.listar(sessao, acesso_a, cenario.site_a.id, de=de, ate=de + timedelta(days=1))

    assert [a.codigo_externo for a in lista] == [m.codigo_externo for m in (madrugada, cedo, tarde)]


def test_listar_site_de_outra_empresa_nao_encontra(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    with pytest.raises(NaoEncontradoError):
        servico.listar(sessao, acesso_a, cenario.site_b.id, de=INICIO, ate=INICIO)


def test_mudancas_trazem_o_historico_em_ordem(
    sessao: Session, site_a: SiteDoAgendamento, acesso_a: Acesso, acesso_b: Acesso
) -> None:
    agendamento = _gravar(sessao, site_a).agendamento
    _gravar(sessao, site_a, toneladas="1")
    servico.cancelar(sessao, acesso_a, agendamento.id, agora=AGORA)

    tipos = [m.tipo for m in servico.mudancas(sessao, acesso_a, agendamento.id)]

    assert tipos == ["criado", "alterado", "cancelado"]
    with pytest.raises(NaoEncontradoError):
        servico.mudancas(sessao, acesso_b, agendamento.id)


# --- O banco também separa (SDD 5.5) ----------------------------------------------------------


def test_banco_recusa_agendamento_de_uma_empresa_em_site_de_outra(
    sessao: Session, cenario: Demonstracao
) -> None:
    errado = SiteDoAgendamento(
        empresa_id=cenario.empresa_b.id, site_id=cenario.site_a.id, usuario_id=None
    )

    with pytest.raises(DBAPIError) as erro:
        _gravar(sessao, errado)

    assert sqlstate(erro.value) == SQLSTATE_CHAVE_ESTRANGEIRA


def test_banco_recusa_codigo_repetido_na_mesma_origem_e_site(
    sessao: Session, site_a: SiteDoAgendamento
) -> None:
    primeiro = _gravar(sessao, site_a).agendamento
    copia = {
        coluna.key: getattr(primeiro, coluna.key)
        for coluna in Agendamento.__table__.columns
        if coluna.key != "id"
    }
    sessao.add(Agendamento(**copia))

    with pytest.raises(DBAPIError) as erro:
        sessao.flush()

    assert sqlstate(erro.value) == SQLSTATE_UNICIDADE


# --- Importar por um conector -----------------------------------------------------------------


@dataclass
class ConectorDeLista:
    """Um conector de teste: cada item da lista é um dicionário de campos, ou já uma recusa."""

    origem: Origem = "planilha"

    def ler(self, entrada: list[dict[str, Any]]) -> Iterable[Lido | Recusado]:
        for numero, campos in enumerate(entrada, start=2):
            yield ler_dados(f"linha {numero}", campos)


def _campos(codigo: str, **mudancas: Any) -> dict[str, Any]:
    return {**_dados(codigo_externo=codigo).model_dump(), **mudancas}


def test_importar_grava_os_lidos_e_relata_os_recusados(
    sessao: Session, site_a: SiteDoAgendamento, acesso_a: Acesso
) -> None:
    _gravar(sessao, site_a, codigo_externo="ja-existia")
    _gravar(sessao, site_a, codigo_externo="igual")
    _gravar(sessao, site_a, codigo_externo="cancelado")
    cancelado = servico.obter_por_codigo(sessao, site_a, "planilha", "cancelado")
    servico.cancelar(sessao, acesso_a, cancelado.id, agora=AGORA)
    entrada = [
        _campos("novo"),
        _campos("ja-existia", toneladas="5"),
        _campos("igual"),
        _campos("placa-ruim", placa_cavalo="ABC12"),
        _campos("cancelado"),
    ]

    relatorio = servico.importar(sessao, site_a, ConectorDeLista(), entrada, agora=AGORA)

    assert relatorio == Relatorio(
        criados=1,
        alterados=1,
        iguais=1,
        recusados=[
            Recusado(
                onde="linha 5",
                motivo="placa do cavalo: placa inválida: 'ABC12' "
                "(formatos aceitos: ABC1234 e ABC1D23)",
            ),
            Recusado(onde="linha 6", motivo="o agendamento cancelado foi cancelado no painel"),
        ],
    )


def test_importar_marca_a_origem_do_conector(sessao: Session, site_a: SiteDoAgendamento) -> None:
    servico.importar(sessao, site_a, ConectorDeLista(origem="link"), [_campos("L1")], agora=AGORA)

    assert servico.obter_por_codigo(sessao, site_a, "link", "L1").origem == "link"


def test_obter_por_codigo_de_outro_site_nao_encontra(
    sessao: Session, cenario: Demonstracao, site_a: SiteDoAgendamento, acesso_b: Acesso
) -> None:
    _gravar(sessao, site_a)
    site_b = servico.site_para_agendar(sessao, acesso_b, cenario.site_b.id)

    with pytest.raises(NaoEncontradoError):
        servico.obter_por_codigo(sessao, site_b, "planilha", "AG-1")


def test_importar_recusa_o_mesmo_codigo_duas_vezes_na_mesma_entrada(
    sessao: Session, site_a: SiteDoAgendamento
) -> None:
    entrada = [_campos("AG-7"), _campos("AG-7", toneladas="1")]

    relatorio = servico.importar(sessao, site_a, ConectorDeLista(), entrada, agora=AGORA)

    assert (relatorio.criados, relatorio.recusados) == (
        1,
        [Recusado(onde="linha 3", motivo="o código AG-7 já apareceu em linha 2")],
    )
    assert servico.obter_por_codigo(sessao, site_a, "planilha", "AG-7").toneladas == Decimal("32.5")


def test_codigos_externos_so_dos_sites_de_quem_pede(
    sessao: Session, cenario: Demonstracao, site_a: SiteDoAgendamento, acesso_a: Acesso
) -> None:
    do_a = _gravar(sessao, site_a, codigo_externo="DO-A").agendamento
    site_a2 = SiteDoAgendamento(
        empresa_id=cenario.empresa_a.id, site_id=cenario.site_a2.id, usuario_id=None
    )
    do_a2 = _gravar(sessao, site_a2, codigo_externo="DO-A2").agendamento

    codigos = servico.codigos_externos(sessao, acesso_a, [do_a.id, do_a2.id])

    assert codigos == {do_a.id: "DO-A"}

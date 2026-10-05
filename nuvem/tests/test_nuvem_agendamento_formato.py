"""O formato interno do agendamento (SDD 3.4): o que todo conector entrega, já conferido."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from nuvem.agendamento.conectores import Lido, Recusado, ler_dados
from nuvem.agendamento.formato import (
    CelularInvalidoError,
    ChaveNfeInvalidaError,
    DadosDoAgendamento,
    descrever_erros,
    normalizar_celular,
    normalizar_chave_nfe,
)

INICIO = datetime(2026, 11, 5, 11, 0, tzinfo=UTC)

CHAVE_INVENTADA = "35261112345678000100550010000001231123456785"
"""Chave de NF-e inventada (CNPJ 12.345.678/0001-00), com o dígito verificador certo."""

CHAVE_INVENTADA_ALFANUMERICA = "352611DEMO0000000A00550010000001231123456783"
"""A mesma, com um CNPJ alfanumérico inventado (as letras valem o código ASCII menos 48)."""


def _dados(**mudancas: Any) -> dict[str, Any]:
    dados: dict[str, Any] = {
        "codigo_externo": "AG-1",
        "janela_inicio": INICIO,
        "janela_fim": INICIO + timedelta(hours=2),
        "tipo": "descarga",
        "placa_cavalo": "ABC1D23",
    }
    dados.update(mudancas)
    return dados


# --- Celular ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "escrito",
    [
        "11987654321",
        "(11) 98765-4321",
        "11 98765 4321",
        "+55 11 98765-4321",
        "5511987654321",
        "+5511987654321",
        "011 98765-4321",
    ],
)
def test_celular_escrito_de_varios_jeitos_vira_o_mesmo(escrito: str) -> None:
    assert normalizar_celular(escrito) == "+5511987654321"


@pytest.mark.parametrize(
    "escrito",
    [
        "1198765432",  # 10 números: falta um
        "119876543210",  # 12 números
        "10987654321",  # DDD 10 não existe
        "20987654321",  # DDD 20 não existe
        "11887654321",  # celular começa com 9
        "1133334444",  # fixo
        "+1 415 555 0100",  # outro país
        "11 9876a-4321",
        "",
    ],
)
def test_celular_fora_da_regra_e_recusado(escrito: str) -> None:
    with pytest.raises(CelularInvalidoError):
        normalizar_celular(escrito)


# --- Chave da NF-e ----------------------------------------------------------------------------


def test_chave_da_nfe_com_digito_certo_passa() -> None:
    assert normalizar_chave_nfe(CHAVE_INVENTADA) == CHAVE_INVENTADA


def test_chave_da_nfe_com_cnpj_alfanumerico_passa() -> None:
    assert normalizar_chave_nfe(CHAVE_INVENTADA_ALFANUMERICA.lower()) == (
        CHAVE_INVENTADA_ALFANUMERICA
    )


def test_chave_da_nfe_escrita_em_blocos_de_4_passa() -> None:
    em_blocos = " ".join(CHAVE_INVENTADA[i : i + 4] for i in range(0, 44, 4))

    assert normalizar_chave_nfe(em_blocos) == CHAVE_INVENTADA


@pytest.mark.parametrize(
    "chave",
    [
        CHAVE_INVENTADA[:-1] + "6",  # dígito verificador errado
        CHAVE_INVENTADA[:10] + "9" + CHAVE_INVENTADA[11:],  # um número trocado no meio
        CHAVE_INVENTADA[:-1],  # 43 caracteres
        "A" + CHAVE_INVENTADA[1:],  # letra fora do lugar do CNPJ
    ],
)
def test_chave_da_nfe_fora_da_regra_e_recusada(chave: str) -> None:
    with pytest.raises(ChaveNfeInvalidaError):
        normalizar_chave_nfe(chave)


# --- Os dados do agendamento ------------------------------------------------------------------


def test_dados_completos_ficam_no_formato_interno() -> None:
    dados = DadosDoAgendamento.model_validate(
        _dados(
            placa_cavalo="abc-1d23",
            placas_reboques=["DEF4G56", "ghi-7890"],
            motorista_nome="  Motorista Inventado  ",
            motorista_celular="(11) 98765-4321",
            toneladas="32.5",
            chave_nfe=CHAVE_INVENTADA,
        )
    )

    assert dados.placa_cavalo == "ABC1D23"
    assert dados.placas_reboques == ("DEF4G56", "GHI7890")
    assert dados.motorista_nome == "Motorista Inventado"
    assert dados.motorista_celular == "+5511987654321"
    assert dados.toneladas == Decimal("32.5")
    assert dados.chave_nfe == CHAVE_INVENTADA


def test_so_os_obrigatorios_bastam() -> None:
    dados = DadosDoAgendamento.model_validate(_dados())

    assert dados.placas_reboques == ()
    assert (dados.motorista_nome, dados.motorista_celular, dados.toneladas, dados.chave_nfe) == (
        None,
        None,
        None,
        None,
    )


def test_texto_vazio_nos_opcionais_conta_como_ausente() -> None:
    # A planilha deixa a célula vazia; vazio não é um celular inválido, é celular nenhum.
    dados = DadosDoAgendamento.model_validate(
        _dados(motorista_nome=" ", motorista_celular="", chave_nfe="", toneladas="")
    )

    assert (dados.motorista_nome, dados.motorista_celular, dados.chave_nfe, dados.toneladas) == (
        None,
        None,
        None,
        None,
    )


@pytest.mark.parametrize(
    "mudanca",
    [
        {"janela_fim": INICIO},  # janela sem duração
        {"janela_fim": INICIO - timedelta(minutes=1)},  # fim antes do início
        {"janela_inicio": datetime(2026, 11, 5, 8, 0)},  # sem fuso
        {"tipo": "transbordo"},
        {"placa_cavalo": "ABC12"},
        {"placas_reboques": ["DEF4G56", "DEF4G57", "DEF4G58", "DEF4G59"]},  # 4 reboques
        {"placas_reboques": ["ABC1D23"]},  # reboque com a placa do cavalo
        {"placas_reboques": ["DEF4G56", "def-4g56"]},  # o mesmo reboque duas vezes
        {"toneladas": "0"},
        {"toneladas": "-3"},
        {"toneladas": "12.3456"},  # mais de 3 casas (o quilo)
        {"codigo_externo": "  "},
        {"codigo_externo": "x" * 101},
        {"motorista_nome": "x" * 121},
        {"campo_que_nao_existe": 1},
    ],
)
def test_dados_fora_da_regra_sao_recusados(mudanca: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DadosDoAgendamento.model_validate(_dados(**mudanca))


def test_codigo_externo_perde_os_espacos_das_pontas() -> None:
    assert DadosDoAgendamento.model_validate(_dados(codigo_externo=" AG-1 ")).codigo_externo == (
        "AG-1"
    )


# --- Os erros em português, para o relatório da planilha e o formulário do link ---------------


def _erros(**mudancas: Any) -> list[str]:
    with pytest.raises(ValidationError) as erro:
        DadosDoAgendamento.model_validate(_dados(**mudancas))
    return descrever_erros(erro.value)


def test_erro_de_placa_diz_o_campo_e_a_placa() -> None:
    assert _erros(placa_cavalo="ABC12") == [
        "placa do cavalo: placa inválida: 'ABC12' (formatos aceitos: ABC1234 e ABC1D23)"
    ]


def test_erro_de_reboque_diz_qual_reboque() -> None:
    assert _erros(placas_reboques=["DEF4G56", "XX"]) == [
        "placa do reboque 2: placa inválida: 'XX' (formatos aceitos: ABC1234 e ABC1D23)"
    ]


def test_erros_comuns_saem_em_portugues() -> None:
    erros = _erros(
        tipo="transbordo",
        motorista_celular="1198765432",
        toneladas="0",
        janela_inicio="amanhã cedo",
        codigo_externo=None,
    )

    assert erros == [
        "código: falta",
        "início da janela: data e hora inválidas",
        "tipo: use carga ou descarga",
        "celular: celular inválido: '1198765432' (use o DDD e os 9 números do celular)",
        "toneladas: precisa ser maior que 0",
    ]


def test_erro_da_janela_vem_sem_campo() -> None:
    assert _erros(janela_fim=INICIO) == ["o fim da janela precisa ser depois do início"]


def test_data_sem_fuso_tem_mensagem_propria() -> None:
    assert _erros(janela_inicio=datetime(2026, 11, 5, 8, 0)) == [
        "início da janela: a data e hora precisam do fuso"
    ]


# --- O que os conectores usam para ler cada item ----------------------------------------------


def test_ler_dados_devolve_o_lido_com_o_lugar() -> None:
    lido = ler_dados("linha 2", _dados())

    assert isinstance(lido, Lido)
    assert (lido.onde, lido.dados.codigo_externo) == ("linha 2", "AG-1")


def test_ler_dados_devolve_a_recusa_com_os_motivos_juntos() -> None:
    recusado = ler_dados("linha 7", _dados(placa_cavalo="ABC12", toneladas="0"))

    assert recusado == Recusado(
        onde="linha 7",
        motivo="placa do cavalo: placa inválida: 'ABC12' (formatos aceitos: ABC1234 e ABC1D23); "
        "toneladas: precisa ser maior que 0",
    )


def test_reboque_com_a_placa_do_cavalo_diz_o_porque() -> None:
    assert _erros(placas_reboques=["ABC1D23"]) == ["o reboque ABC1D23 tem a placa do cavalo"]


@pytest.mark.parametrize(("escrito", "valor"), [("32,5", "32.5"), ("1.234,5", "1234.5")])
def test_toneladas_com_virgula_como_se_escreve_no_brasil(escrito: str, valor: str) -> None:
    assert DadosDoAgendamento.model_validate(_dados(toneladas=escrito)).toneladas == Decimal(valor)

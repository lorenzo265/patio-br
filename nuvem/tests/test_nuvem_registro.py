"""O registro da nuvem (SDD 8.1, D-61 e D-74): sem placa nem telefone, e uma linha por registro
na homologação e na produção. Placas e telefones daqui são inventados."""

import io
import json
import logging
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import StatementError

from nuvem import registro
from nuvem.banco import criar_motor


@pytest.mark.parametrize(
    "placa",
    ["ABC1D23", "abc1d23", "ABC1234", "ABC-1234", "XYZ9A88"],
)
def test_esconde_a_placa(placa: str) -> None:
    assert registro.mascarar(f"placa {placa} na entrada") == "placa [placa] na entrada"


@pytest.mark.parametrize(
    "telefone",
    [
        "5523999990000",
        "+55 23 99999-0000",
        "(23) 99999-0000",
        "23 9999-0000",
        "23999990000",
        "+5523999990000",
    ],
)
def test_esconde_o_telefone(telefone: str) -> None:
    assert registro.mascarar(f"para {telefone}.") == "para [telefone]."


@pytest.mark.parametrize(
    "texto",
    [
        "visita 123 da empresa 4",
        "passagem 550e8400-e29b-41d4-a716-446655440000",
        "2026-10-06T08:47:57.123+00:00",
        '172.18.0.5:43210 - "GET /saude HTTP/1.1" 200',
        "resumo 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        "id do número 123456789012345",
        "erro no laço do worker; ele segue",
    ],
)
def test_deixa_os_ids_as_horas_e_os_enderecos(texto: str) -> None:
    assert registro.mascarar(texto) == texto


def _registro(mensagem: str, *args: object, erro: BaseException | None = None) -> logging.LogRecord:
    exc_info = (type(erro), erro, erro.__traceback__) if erro else None
    return logging.LogRecord("nuvem.teste", logging.ERROR, __file__, 1, mensagem, args, exc_info)


def _erro_com(mensagem: str) -> BaseException:
    try:
        raise RuntimeError(mensagem)
    except RuntimeError as erro:
        return erro


def test_o_json_e_uma_linha_com_o_nivel_e_o_erro_sem_dado_pessoal() -> None:
    linha = registro.FormatoJson().format(
        _registro("aviso para %s falhou", "5523999990000", erro=_erro_com("placa ABC1D23"))
    )

    assert "\n" not in linha
    dados = json.loads(linha)
    assert dados["nivel"] == "ERROR"
    assert dados["origem"] == "nuvem.teste"
    assert dados["mensagem"] == "aviso para [telefone] falhou"
    assert "RuntimeError: placa [placa]" in dados["erro"]
    assert "Traceback" in dados["erro"]
    assert dados["quando"].endswith("+00:00")


def test_o_json_sem_erro_nao_tem_o_campo_do_erro() -> None:
    dados = json.loads(registro.FormatoJson().format(_registro("tudo certo")))

    assert "erro" not in dados


def test_o_texto_tambem_esconde_a_placa_e_o_telefone_no_erro() -> None:
    formato = registro.Mascarado(logging.Formatter("%(levelname)s %(message)s"))

    linha = formato.format(_registro("placa %s", "ABC1D23", erro=_erro_com("tel 23999990000")))

    assert linha.startswith("ERROR placa [placa]")
    assert "RuntimeError: tel [telefone]" in linha
    assert "ABC1D23" not in linha and "23999990000" not in linha


def test_o_texto_mascarado_nao_estraga_o_registro_para_os_outros() -> None:
    # O uvicorn monta a linha do acesso com os args: eles continuam lá para o próximo formato.
    original = _registro("placa %s", "ABC1D23")

    registro.Mascarado(logging.Formatter("%(message)s")).format(original)

    assert original.args == ("ABC1D23",)


@pytest.fixture
def raiz_limpa() -> Iterator[logging.Logger]:
    """Devolve o registro raiz e os do uvicorn como estavam antes do teste."""
    nomes = ("", "uvicorn", "uvicorn.access")
    antes = {
        nome: (logging.getLogger(nome).handlers[:], logging.getLogger(nome).level) for nome in nomes
    }
    yield logging.getLogger()
    for nome, (handlers, nivel) in antes.items():
        logger = logging.getLogger(nome)
        logger.handlers[:] = handlers
        logger.setLevel(nivel)


def _da_nuvem(logger: logging.Logger) -> list[logging.Handler]:
    return [h for h in logger.handlers if getattr(h, registro.MARCA, False)]


@pytest.mark.parametrize("ambiente", ["homologacao", "producao"])
def test_configurar_poe_um_so_registro_na_raiz_mesmo_chamado_duas_vezes(
    raiz_limpa: logging.Logger, ambiente: str
) -> None:
    registro.configurar(ambiente)
    registro.configurar(ambiente)

    [handler] = _da_nuvem(raiz_limpa)
    assert isinstance(handler.formatter, registro.FormatoJson)
    assert raiz_limpa.level == logging.INFO


def test_fora_da_homologacao_e_da_producao_o_registro_e_texto(raiz_limpa: logging.Logger) -> None:
    registro.configurar("local")

    [handler] = _da_nuvem(raiz_limpa)
    assert isinstance(handler.formatter, registro.Mascarado)


def test_configurar_troca_o_formato_dos_registros_do_uvicorn(raiz_limpa: logging.Logger) -> None:
    saida = io.StringIO()
    acesso = logging.getLogger("uvicorn.access")
    handler = logging.StreamHandler(saida)
    handler.setFormatter(logging.Formatter("%(message)s"))
    acesso.handlers[:] = [handler]

    registro.configurar("producao")
    acesso.error('%s - "%s %s HTTP/%s" %d', "1.2.3.4:5", "GET", "/prova?placa=ABC1D23", "1.1", 200)

    dados = json.loads(saida.getvalue())
    assert dados["mensagem"] == '1.2.3.4:5 - "GET /prova?placa=[placa] HTTP/1.1" 200'


def test_configurar_mascara_o_formato_de_texto_do_uvicorn_sem_perder_o_dele(
    raiz_limpa: logging.Logger,
) -> None:
    saida = io.StringIO()
    acesso = logging.getLogger("uvicorn.access")
    handler = logging.StreamHandler(saida)
    handler.setFormatter(logging.Formatter("acesso: %(message)s"))
    acesso.handlers[:] = [handler]

    registro.configurar("local")
    registro.configurar("local")  # não mascara duas vezes
    acesso.error("GET %s", "/prova?placa=ABC1D23")

    assert saida.getvalue() == "acesso: GET /prova?placa=[placa]\n"


@pytest.mark.integracao
def test_o_erro_do_banco_nao_mostra_os_valores_da_consulta(url_banco_teste: str) -> None:
    motor = criar_motor(url_banco_teste)

    with motor.connect() as conexao, pytest.raises(StatementError) as erro:
        # Dividir por zero: a mensagem do banco não repete o valor; só o SQLAlchemy o mostraria.
        conexao.execute(text("select cast(:placa as text), 1 / 0"), {"placa": "ABC1D23"})

    motor.dispose()
    assert "ABC1D23" not in str(erro.value)

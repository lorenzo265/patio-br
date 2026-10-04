"""O formato interno do agendamento (SDD 3.4): o que todo conector entrega, já conferido.

A placa segue a mesma regra do leitor (``contratos.placa``); o celular é do Brasil e fica com o
+55; a chave da NF-e tem 44 caracteres e o dígito verificador confere. Texto vazio conta como
ausente: a célula vazia da planilha não é um celular inválido, é celular nenhum.

Os erros saem em português (``descrever_erros``), para o relatório da planilha e o formulário do
link.
"""

import re
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from contratos.placa import Placa

Tipo = Literal["carga", "descarga"]

MAXIMO_DE_REBOQUES = 3
"""Até o tritrem; o casamento conta no máximo 2 (SDD 5.3), mas guarda o que vier."""

# --- Celular ----------------------------------------------------------------------------------

DDDS = frozenset(
    {
        *range(11, 20),
        21, 22, 24, 27, 28,
        31, 32, 33, 34, 35, 37, 38,
        *range(41, 50),
        51, 53, 54, 55,
        *range(61, 70),
        71, 73, 74, 75, 77, 79,
        *range(81, 90),
        *range(91, 100),
    }
)  # fmt: skip
"""Os 67 DDDs do Brasil."""

FORMATO_DO_CELULAR = r"^\+55[1-9]{2}9[0-9]{8}$"
"""Como o celular fica guardado: +55, o DDD e os 9 números (o primeiro é sempre 9)."""

_SINAIS_DO_TELEFONE = re.compile(r"[\s().-]")


class CelularInvalidoError(ValueError):
    """O texto não é um celular do Brasil."""

    def __init__(self, texto: str) -> None:
        super().__init__(f"celular inválido: {texto!r} (use o DDD e os 9 números do celular)")


def normalizar_celular(texto: str) -> str:
    """Devolve o celular como fica guardado (ex.: ``+5511987654321``).

    Aceita o celular como as pessoas escrevem: ``(11) 98765-4321``, ``+55 11 98765-4321``,
    ``011 98765-4321``.

    Raises:
        CelularInvalidoError: se não for um celular do Brasil (DDD que existe e 9 números,
            começando por 9).
    """
    numeros = _SINAIS_DO_TELEFONE.sub("", texto)
    if numeros.startswith("+"):
        numeros = numeros[1:]
        if not numeros.startswith("55"):
            raise CelularInvalidoError(texto)
    if not (numeros.isascii() and numeros.isdigit()):
        raise CelularInvalidoError(texto)
    if len(numeros) == 13 and numeros.startswith("55"):
        numeros = numeros[2:]
    elif len(numeros) == 12 and numeros.startswith("0"):
        numeros = numeros[1:]
    if len(numeros) != 11 or int(numeros[:2]) not in DDDS or numeros[2] != "9":
        raise CelularInvalidoError(texto)
    return f"+55{numeros}"


# --- Chave da NF-e ----------------------------------------------------------------------------

FORMATO_DA_CHAVE_NFE = "^[0-9]{6}[A-Z0-9]{12}[0-9]{26}$"
"""44 caracteres; as 12 primeiras posições do CNPJ podem ter letras (CNPJ alfanumérico)."""

_PADRAO_DA_CHAVE = re.compile(FORMATO_DA_CHAVE_NFE)
_PESOS_DA_CHAVE = (2, 3, 4, 5, 6, 7, 8, 9)


class ChaveNfeInvalidaError(ValueError):
    """O texto não é uma chave de NF-e (formato ou dígito verificador)."""

    def __init__(self, texto: str) -> None:
        super().__init__(
            f"chave da NF-e inválida: {texto!r} (44 caracteres, com o dígito verificador certo)"
        )


def normalizar_chave_nfe(texto: str) -> str:
    """Devolve a chave da NF-e sem espaços, em maiúsculas, com o dígito verificador conferido.

    O dígito é o módulo 11 dos 43 primeiros caracteres, com pesos de 2 a 9 da direita para a
    esquerda; cada caractere vale o código ASCII menos 48 (o número vale ele mesmo, e a letra A
    vale 17), como na Nota Técnica Conjunta 2025.001 do CNPJ alfanumérico.

    Raises:
        ChaveNfeInvalidaError: se o formato ou o dígito verificador não conferirem.
    """
    chave = "".join(texto.split()).upper()
    if not _PADRAO_DA_CHAVE.fullmatch(chave):
        raise ChaveNfeInvalidaError(texto)
    soma = sum(
        (ord(caractere) - 48) * _PESOS_DA_CHAVE[posicao % len(_PESOS_DA_CHAVE)]
        for posicao, caractere in enumerate(reversed(chave[:43]))
    )
    resto = soma % 11
    if int(chave[43]) != (0 if resto < 2 else 11 - resto):
        raise ChaveNfeInvalidaError(texto)
    return chave


# --- Os dados do agendamento ------------------------------------------------------------------


def _celular_se_texto(valor: object) -> object:
    return normalizar_celular(valor) if isinstance(valor, str) else valor


def _chave_se_texto(valor: object) -> object:
    return normalizar_chave_nfe(valor) if isinstance(valor, str) else valor


def _numero_escrito(valor: object) -> object:
    # "32,5" e "1.234,5", como se escreve no Brasil; sem vírgula, o ponto é o decimal.
    if isinstance(valor, str) and "," in valor:
        return valor.replace(".", "").replace(",", ".")
    return valor


Celular = Annotated[str, BeforeValidator(_celular_se_texto)]
ChaveNfe = Annotated[str, BeforeValidator(_chave_se_texto)]
Toneladas = Annotated[
    Decimal, Field(gt=0, max_digits=9, decimal_places=3), BeforeValidator(_numero_escrito)
]


class DadosDoAgendamento(BaseModel):
    """Um agendamento no formato interno, como todo conector entrega (SDD 3.4).

    Obrigatórios: código externo, janela, tipo e placa do cavalo. O resto pode chegar depois,
    num reenvio com o mesmo código.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    codigo_externo: Annotated[str, Field(max_length=100)]
    """O código do agendamento na origem (a linha da planilha, o pedido do link)."""
    janela_inicio: AwareDatetime
    janela_fim: AwareDatetime
    tipo: Tipo
    placa_cavalo: Placa
    placas_reboques: Annotated[tuple[Placa, ...], Field(max_length=MAXIMO_DE_REBOQUES)] = ()
    motorista_nome: Annotated[str | None, Field(max_length=120)] = None
    motorista_celular: Celular | None = None
    toneladas: Toneladas | None = None
    chave_nfe: ChaveNfe | None = None

    @model_validator(mode="before")
    @classmethod
    def _vazio_e_ausente(cls, dados: Any) -> Any:
        if not isinstance(dados, dict):
            return dados
        limpos = {
            campo: (valor.strip() or None) if isinstance(valor, str) else valor
            for campo, valor in dados.items()
        }
        if limpos.get("placas_reboques") is None:
            limpos.pop("placas_reboques", None)
        return limpos

    @model_validator(mode="after")
    def _conferir_o_conjunto(self) -> "DadosDoAgendamento":
        if self.janela_fim <= self.janela_inicio:
            raise ValueError("o fim da janela precisa ser depois do início")
        vistos = {self.placa_cavalo}
        for placa in self.placas_reboques:
            if placa == self.placa_cavalo:
                raise ValueError(f"o reboque {placa} tem a placa do cavalo")
            if placa in vistos:
                raise ValueError(f"o reboque {placa} aparece duas vezes")
            vistos.add(placa)
        return self


# --- Os erros em português --------------------------------------------------------------------

ROTULOS = {
    "codigo_externo": "código",
    "janela_inicio": "início da janela",
    "janela_fim": "fim da janela",
    "tipo": "tipo",
    "placa_cavalo": "placa do cavalo",
    "placas_reboques": "placas dos reboques",
    "motorista_nome": "motorista",
    "motorista_celular": "celular",
    "toneladas": "toneladas",
    "chave_nfe": "chave da NF-e",
}
"""Como cada campo aparece para a pessoa."""

_DATA_E_HORA = frozenset(
    {"datetime_type", "datetime_parsing", "datetime_from_date_parsing", "datetime_object_invalid"}
)
_NUMERO = frozenset({"decimal_type", "decimal_parsing", "float_parsing", "float_type"})


def descrever_erros(erro: ValidationError) -> list[str]:
    """Os erros de ``DadosDoAgendamento`` em português, um por campo (ex.: ``"tipo: ..."``)."""
    return [_descrever(detalhe) for detalhe in erro.errors()]


def _descrever(detalhe: Any) -> str:
    rotulo = _rotulo(detalhe["loc"])
    texto = _texto(detalhe)
    return f"{rotulo}: {texto}" if rotulo else texto


def _rotulo(local: tuple[int | str, ...]) -> str:
    if not local:
        return ""
    campo = str(local[0])
    if campo == "placas_reboques" and len(local) > 1 and isinstance(local[1], int):
        return f"placa do reboque {local[1] + 1}"
    return ROTULOS.get(campo, campo)


def _texto(detalhe: Any) -> str:
    tipo: str = detalhe["type"]
    contexto: dict[str, Any] = detalhe.get("ctx", {})
    if tipo == "missing" or (detalhe["loc"] and detalhe.get("input") is None):
        return "falta"
    if tipo == "value_error":
        return str(contexto["error"])
    if tipo == "literal_error":
        return "use " + str(contexto["expected"]).replace("'", "").replace(" or ", " ou ")
    if tipo in _DATA_E_HORA:
        return "data e hora inválidas"
    if tipo == "timezone_aware":
        return "a data e hora precisam do fuso"
    if tipo in _NUMERO:
        return "número inválido"
    mensagens = {
        "greater_than": "precisa ser maior que {gt}",
        "decimal_max_places": "no máximo {decimal_places} casas depois da vírgula",
        "decimal_max_digits": "número grande demais",
        "decimal_whole_digits": "número grande demais",
        "string_too_long": "no máximo {max_length} caracteres",
        "too_long": "no máximo {max_length}",
        "string_type": "precisa ser texto",
        "extra_forbidden": "campo desconhecido",
    }
    return mensagens.get(tipo, "valor inválido").format(**contexto)

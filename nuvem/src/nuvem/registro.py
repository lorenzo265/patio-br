"""O registro da nuvem (SDD 8.1, D-61 e D-74): sem placa nem telefone, e fácil de achar o erro.

Na homologação e na produção, cada registro é **uma linha JSON** (o erro, com o rastro, vai na
mesma linha): o Docker a manda ao CloudWatch, que conta os erros pelo ``nivel``. Nos outros
ambientes, texto, para ler no terminal.

O código registra só os ids. O formato é a segunda barreira: troca o que parecer placa ou
telefone por ``[placa]`` e ``[telefone]``, na mensagem e no rastro do erro. Nome não tem como
reconhecer: por isso a regra é registrar só os ids.
"""

import json
import logging
import re
from datetime import UTC, datetime

_FORA = r"(?<![0-9A-Za-z])"
_ATE = r"(?![0-9A-Za-z])"
PLACA = re.compile(_FORA + r"[A-Za-z]{3}-?[0-9][A-Za-z0-9][0-9]{2}" + _ATE)
"""A placa antiga (``ABC1234``, ``ABC-1234``) e a Mercosul (``ABC1D23``)."""
TELEFONE = re.compile(
    _FORA + r"(?:\+?55[ .-]?)?(?:\([0-9]{2}\)|[0-9]{2})[ .-]?9?[0-9]{4}[ .-]?[0-9]{4}" + _ATE
)
"""O celular e o fixo do Brasil, com ou sem o 55, o DDD entre parênteses e os separadores."""

MARCA = "_da_nuvem"
"""O atributo que marca o registro que a nuvem pôs na raiz (para não pôr dois)."""
FORMATO_DE_TEXTO = "%(asctime)s %(levelname)s %(name)s: %(message)s"
DO_UVICORN = ("uvicorn", "uvicorn.access")
"""Os registros do uvicorn, que não passam pela raiz (o ``uvicorn.error`` vai pelo ``uvicorn``)."""


def mascarar(texto: str) -> str:
    """O texto com cada placa e cada telefone trocados por ``[placa]`` e ``[telefone]``."""
    return TELEFONE.sub("[telefone]", PLACA.sub("[placa]", texto))


class FormatoJson(logging.Formatter):
    """Uma linha JSON por registro: quando, nível, origem, mensagem e, se houver, o erro."""

    def format(self, record: logging.LogRecord) -> str:
        """Monta a linha, já sem placa nem telefone."""
        dados = {
            "quando": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "nivel": record.levelname,
            "origem": record.name,
            "mensagem": mascarar(record.getMessage()),
        }
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            dados["erro"] = mascarar(record.exc_text)
        if record.stack_info:
            dados["pilha"] = mascarar(self.formatStack(record.stack_info))
        return json.dumps(dados, ensure_ascii=False)


class Mascarado(logging.Formatter):
    """Um formato de texto qualquer (o nosso ou o do uvicorn), sem placa nem telefone."""

    def __init__(self, formato: logging.Formatter) -> None:
        """Usa ``formato`` para montar a linha e esconde o que não pode sair."""
        super().__init__()
        self._formato = formato

    def format(self, record: logging.LogRecord) -> str:
        """A linha do formato de dentro, mascarada (o registro em si não muda)."""
        return mascarar(self._formato.format(record))


def configurar(ambiente: str) -> None:
    """Põe o registro da nuvem na raiz (uma vez só) e troca o formato dos do uvicorn.

    Na homologação e na produção, o formato é o JSON; nos outros ambientes, texto mascarado.
    """
    em_json = ambiente in ("homologacao", "producao")
    raiz = logging.getLogger()
    nosso = next((h for h in raiz.handlers if getattr(h, MARCA, False)), None)
    if nosso is None:
        nosso = logging.StreamHandler()
        setattr(nosso, MARCA, True)
        raiz.addHandler(nosso)
    nosso.setFormatter(FormatoJson() if em_json else Mascarado(logging.Formatter(FORMATO_DE_TEXTO)))
    raiz.setLevel(logging.INFO)
    for nome in DO_UVICORN:
        for handler in logging.getLogger(nome).handlers:
            if em_json:
                handler.setFormatter(FormatoJson())
            elif not isinstance(handler.formatter, Mascarado):
                handler.setFormatter(Mascarado(handler.formatter or logging.Formatter()))

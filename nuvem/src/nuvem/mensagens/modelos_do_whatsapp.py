"""Os modelos de mensagem do WhatsApp (SDD 7.5, D-63): um por tipo de mensagem.

A Meta só deixa a empresa começar a conversa com um **modelo aprovado**: o texto fixo, com as
variáveis numeradas (``{{1}}``, ``{{2}}``...). Os textos ficam aqui, e é este texto que se manda à
Meta para aprovar (N19). A tela da conversa mostra o mesmo texto, já preenchido.

Regras da Meta seguidas aqui: nenhum modelo começa nem termina com uma variável, as variáveis
vão numeradas a partir de 1, e o nome só tem letras minúsculas, números e ``_``. Todos são da
categoria utilidade, em português (``pt_BR``).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from nuvem.mensagens.modelos import ModeloDeMensagem

IDIOMA = "pt_BR"
_VARIAVEL = re.compile(r"\{\{(\d+)\}\}")


@dataclass(frozen=True)
class ModeloDoWhatsApp:
    """Um modelo de mensagem: o nome aprovado na Meta e o texto, com as variáveis."""

    nome: str
    corpo: str

    @property
    def variaveis(self) -> int:
        """Quantas variáveis o texto tem."""
        return len(_VARIAVEL.findall(self.corpo))


MODELOS: dict[ModeloDeMensagem, ModeloDoWhatsApp] = {
    "confirmacao": ModeloDoWhatsApp(
        "patio_confirmacao",
        "Olá! {{1}} agendada: {{2}}, {{3}}, das {{4}} às {{5}} (agendamento {{6}}). "
        "Os avisos da fila e da doca vão chegar por aqui.",
    ),
    "na_fila": ModeloDoWhatsApp(
        "patio_na_fila",
        "Chegada registrada às {{1}}. Você está na fila, posição {{2}}. "
        "Espere o aviso da doca por aqui.",
    ),
    "chamada": ModeloDoWhatsApp("patio_chamada", "Sua vez! Siga para a {{1}}."),
    "pode_sair": ModeloDoWhatsApp(
        "patio_pode_sair", "Pronto! {{1}} terminada. Pode sair pela portaria. Boa viagem!"
    ),
}
"""O modelo de cada tipo de mensagem ao motorista."""


def preencher(modelo: ModeloDeMensagem, variaveis: Sequence[str]) -> str:
    """O texto do modelo com as variáveis, como o motorista lê.

    Raises:
        ValueError: se o número de variáveis não for o do modelo.
    """
    escolhido = MODELOS[modelo]
    if len(variaveis) != escolhido.variaveis:
        raise ValueError(
            f"o modelo {escolhido.nome} tem {escolhido.variaveis} variáveis, "
            f"e vieram {len(variaveis)}"
        )
    return _VARIAVEL.sub(lambda achada: variaveis[int(achada.group(1)) - 1], escolhido.corpo)

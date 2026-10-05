"""As telas "em breve" do recebimento e do estoque em 3D (T46, D-43 e D-45).

Mostram para onde o produto vai, sem prometer o que não existe: as duas dizem "em breve", usam
dados de exemplo fixos (inventados, deste arquivo) e não gravam nada. Os módulos de verdade vêm
depois do piloto aprovado (`[ABERTO-19]` e `[ABERTO-20]`).

- **Recebimento:** a nota de um caminhão na doca, item por item, com a contagem do conferente e
  a diferença (a conta da tela também roda no navegador, ao digitar).
- **Estoque:** o armazém em 3D (three.js, em ``estatico/``); a busca acende o lugar do item.
"""

import json
from dataclasses import asdict, dataclass
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from nuvem.cadastro.acesso import Acesso, obter_acesso
from nuvem.web.rotas import tela

roteador = APIRouter(include_in_schema=False)

AcessoDoCliente = Annotated[Acesso, Depends(obter_acesso)]

Situacao = Literal["confere", "falta", "sobra", "a contar"]


@dataclass(frozen=True)
class ItemDaNota:
    """Um item da nota fiscal e a contagem do conferente (vazia = ainda não contou)."""

    codigo: str
    descricao: str
    unidade: str
    na_nota: int
    contado: int | None

    @property
    def diferenca(self) -> int | None:
        return None if self.contado is None else self.contado - self.na_nota

    @property
    def situacao(self) -> Situacao:
        if self.diferenca is None:
            return "a contar"
        if self.diferenca < 0:
            return "falta"
        return "sobra" if self.diferenca > 0 else "confere"


@dataclass(frozen=True)
class NotaDeExemplo:
    """Uma nota fiscal inventada, de um caminhão na doca."""

    numero: str
    fornecedor: str
    doca: str
    placa: str
    itens: tuple[ItemDaNota, ...]


@dataclass(frozen=True)
class ItemNoEstoque:
    """Um item guardado num lugar do armazém: rua, prédio (coluna) e nível (altura)."""

    descricao: str
    rua: str
    predio: int
    nivel: int
    saldo: int
    unidade: str


@dataclass(frozen=True)
class EstoqueDeExemplo:
    """Um armazém inventado: ruas de porta-paletes, com prédios e níveis."""

    ruas: tuple[str, ...]
    predios: int
    niveis: int
    itens: tuple[ItemNoEstoque, ...]


NOTA_DE_EXEMPLO = NotaDeExemplo(
    numero="000.123.456",
    fornecedor="Fornecedor Exemplo Alimentos Ltda.",
    doca="Doca 2",
    placa="ABC1D23",
    itens=(
        ItemDaNota("ALI-001", "Arroz tipo 1, 5 kg", "fardo", 120, 120),
        ItemDaNota("ALI-002", "Feijão carioca, 1 kg", "fardo", 80, 80),
        ItemDaNota("ALI-003", "Óleo de soja, 900 ml", "caixa", 60, 58),
        ItemDaNota("ALI-004", "Açúcar refinado, 1 kg", "fardo", 90, 90),
        ItemDaNota("ALI-005", "Café torrado e moído, 500 g", "caixa", 40, 40),
        ItemDaNota("ALI-006", "Macarrão espaguete, 500 g", "caixa", 75, 76),
        ItemDaNota("ALI-007", "Farinha de trigo, 1 kg", "fardo", 50, None),
        ItemDaNota("ALI-008", "Leite UHT integral, 1 L", "caixa", 100, None),
    ),
)
"""Inventada: o fornecedor, a nota e os códigos não existem."""

ESTOQUE_DE_EXEMPLO = EstoqueDeExemplo(
    ruas=("A", "B", "C", "D"),
    predios=8,
    niveis=4,
    itens=(
        ItemNoEstoque("Arroz tipo 1, 5 kg", "A", 2, 1, 340, "fardos"),
        ItemNoEstoque("Feijão carioca, 1 kg", "A", 5, 2, 210, "fardos"),
        ItemNoEstoque("Biscoito recheado, 140 g", "A", 8, 3, 300, "caixas"),
        ItemNoEstoque("Óleo de soja, 900 ml", "B", 3, 1, 180, "caixas"),
        ItemNoEstoque("Açúcar refinado, 1 kg", "B", 7, 3, 260, "fardos"),
        ItemNoEstoque("Papel higiênico, 12 rolos", "B", 1, 4, 90, "fardos"),
        ItemNoEstoque("Café torrado e moído, 500 g", "C", 1, 2, 95, "caixas"),
        ItemNoEstoque("Macarrão espaguete, 500 g", "C", 4, 4, 150, "caixas"),
        ItemNoEstoque("Sabão em pó, 1 kg", "C", 7, 1, 130, "caixas"),
        ItemNoEstoque("Farinha de trigo, 1 kg", "D", 6, 1, 120, "fardos"),
        ItemNoEstoque("Leite UHT integral, 1 L", "D", 2, 2, 400, "caixas"),
        ItemNoEstoque("Detergente, 500 ml", "D", 8, 3, 220, "caixas"),
    ),
)
"""Inventado: os outros lugares têm paletes "de outros itens", desenhados sem nome."""


@roteador.get("/recebimento")
def recebimento(request: Request, acesso: AcessoDoCliente) -> HTMLResponse:
    """A conferência de uma nota na doca, com dados de exemplo."""
    itens = NOTA_DE_EXEMPLO.itens
    contados = [item for item in itens if item.contado is not None]
    contexto = {
        "nota": NOTA_DE_EXEMPLO,
        "contados": len(contados),
        "divergencias": [item for item in contados if item.situacao != "confere"],
    }
    return tela(request, "recebimento.html", contexto)


@roteador.get("/estoque")
def estoque(request: Request, acesso: AcessoDoCliente) -> HTMLResponse:
    """O armazém em 3D, com a busca, e dados de exemplo."""
    dados = asdict(ESTOQUE_DE_EXEMPLO)
    # Dentro de <script>: "</" e "<!--" não podem aparecer no JSON.
    texto = json.dumps(dados, ensure_ascii=False).replace("<", "\\u003c")
    return tela(request, "estoque.html", {"estoque": ESTOQUE_DE_EXEMPLO, "dados": texto})

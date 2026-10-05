"""O vault do Obsidian em ``knowledge/``: o gerador e a conferência do vault no Git."""

from dataclasses import replace
from pathlib import Path

import pytest

from tarefas.comandos import encontrar_raiz
from tarefas.conhecimento import (
    COMANDO,
    PASTA_DO_VAULT,
    ArquivoDeCodigo,
    ArquivoDeTeste,
    Fontes,
    Indice,
    diferencas,
    escrever,
    gerar,
    ligacoes,
    ligar,
    montar,
    nome_de_nota,
)

INDICE = Indice(
    ids=frozenset({"D-05", "ABERTO-04", "T40", "N15"}),
    secoes={"5.4": "5.4 Contas do extrato", "11": "11. Registro de decisões", "6.1": "6.1 Stack"},
    documentos={"docs/SDD.md": "SDD", "CLAUDE.md": "CLAUDE - regras do repositório"},
    anexos={"docs/guias/tela.png": "tela.png"},
)

SDD = """# SDD — exemplo

Versão 9.9 · 2026-01-01

---

## 1. Visão

Texto da visão, ver seção 1.1 e D-01.

### 1.1 O problema: a fila

O problema, com o `[ABERTO-01]`.

---

## 11. Registro de decisões

| # | Decisão | Motivo | Alternativa descartada |
|---|---|---|---|
| D-01 | Fazer assim | porque sim (seção 1.1) | fazer assado |
| D-02 | Outra | outro motivo | nada |

## 12. Itens em aberto

| # | Item | Como e quando decidir |
|---|---|---|
| ABERTO-01 | O nome | numa conversa |

## Histórico de versões

| Versão | Data | Mudança |
|---|---|---|
| 9.9 | 2026-01-01 | fecha o `[ABERTO-07]` (D-02) |
"""

PLANO = """# Plano do mês 9 (setembro): exemplo

## 1. Objetivo

Fazer a T90 e a T91.

## 3. Tarefas técnicas

### Semana 1 — começo

#### T90. Primeira tarefa

Faz a primeira coisa (SDD 1.1, D-01).

#### ~~T91. Segunda tarefa~~ → próximo plano

Não cabe.

---

## 4. Trilha não técnica

| # | Tarefa | Por quê | Resolve |
|---|---|---|---|
| N1 | Falar com o advogado | prazo | `[ABERTO-01]` |
| ~~N2~~ | ~~Instalar o kit~~ (adiada) | dados | [[T90]] |

## 5. Acrescentada depois

#### T92. Terceira tarefa

Fora de qualquer semana.
"""

CODIGO_DO_PACOTE = '''"""Um pacote de exemplo, da T90."""
'''

CODIGO_DAS_ROTAS = '''"""As rotas de exemplo (D-01)."""

from fastapi import APIRouter

roteador = APIRouter(prefix="/coisas")

LIMITE = 3
"""Quantas coisas cabem."""


class Coisa(Base):
    """Uma coisa guardada."""

    __tablename__ = "coisa"

    id: Mapped[int] = mapped_column(primary_key=True)
    rotulo: ClassVar[str] = "coisa"
    nome: Mapped[str]


@roteador.get("/{coisa_id}")
def ver(coisa_id: int) -> str:
    """Mostra uma coisa.

    Mais detalhes que não entram no resumo.
    """
    return tela("coisa.html")


def _escondida() -> None:
    """Não aparece."""
'''

COMANDOS = '''"""Os comandos."""


def etapas_do_ola() -> list[str]:
    """Diz olá."""
    return []


def _interpretador() -> None:
    comandos.add_parser("ola", help="diz olá")
'''


MIGRACAO = '''"""início: a coisa

Criada em: 2026-01-01
"""
'''


def _fontes() -> Fontes:
    return Fontes(
        sdd=SDD,
        planos={"docs/planos/2026-09-plano.md": PLANO},
        documentos={
            "docs/guias/guia.md": "# Um guia\n\nVeja o [SDD](../SDD.md) e a ![tela](tela.png).\n",
            "CLAUDE.md": "# Regras\n\nSDD 1.1 e a seção 1 (não é do SDD).\n",
        },
        nomes_dos_documentos={"CLAUDE.md": "CLAUDE - regras do repositório"},
        descricoes={"exemplo": "Pacote de exemplo."},
        codigo=(
            ArquivoDeCodigo(
                "exemplo/src/exemplo/__init__.py", "exemplo", "exemplo", CODIGO_DO_PACOTE
            ),
            ArquivoDeCodigo(
                "exemplo/src/exemplo/rotas.py", "exemplo.rotas", "exemplo", CODIGO_DAS_ROTAS
            ),
            ArquivoDeCodigo(
                "ferramentas/src/tarefas/comandos.py", "tarefas.comandos", "ferramentas", COMANDOS
            ),
        ),
        testes=(
            ArquivoDeTeste(
                "exemplo/tests/test_exemplo_rotas.py", "exemplo", '"""As rotas de exemplo."""\n'
            ),
        ),
        telas={
            "coisa.html": '{% extends "base.html" %}\n{% include "parte.html" %}\n',
            "base.html": "<html></html>\n",
            "parte.html": "<p></p>\n",
        },
        migracoes={"nuvem/migracoes/versions/0001_inicio.py": MIGRACAO},
        imagens={"docs/guias/tela.png": b"PNG", "docs/guias/sobra.png": b"PNG"},
    )


def _texto(arquivos: dict[str, bytes], caminho: str) -> str:
    return arquivos[caminho].decode("utf-8")


# --- Ligações ---------------------------------------------------------------------------------


def test_decisao_item_tarefa_e_trilha_existentes_viram_ligacao() -> None:
    texto = ligar("Pela D-05, a T40 e a N15 resolvem o `[ABERTO-04]`.", INDICE)

    assert texto == "Pela [[D-05]], a [[T40]] e a [[N15]] resolvem o [[ABERTO-04]]."


def test_identificador_sem_nota_continua_texto() -> None:
    texto = ligar("A D-53 ou a próxima livre; o N150 da caixa; a T39.", INDICE)

    assert texto == "A D-53 ou a próxima livre; o N150 da caixa; a T39."


def test_ligacao_que_ja_existe_nao_e_ligada_de_novo() -> None:
    assert ligar("- [[T40]] Visual", INDICE) == "- [[T40]] Visual"


def test_a_nota_nao_liga_para_si_mesma() -> None:
    assert ligar("# T40. Visual, depois da D-05", INDICE, propria="T40") == (
        "# T40. Visual, depois da [[D-05]]"
    )


def test_referencia_ao_sdd_aponta_para_a_secao() -> None:
    assert ligar("Ver SDD 5.4.", INDICE) == "Ver [[5.4 Contas do extrato|SDD 5.4]]."
    assert ligar("(SDD 5.4, 6.1 e 7.7)", INDICE) == (
        "([[5.4 Contas do extrato|SDD 5.4]], [[6.1 Stack|6.1]] e 7.7)"
    )
    assert ligar("(SDD, seção 11)", INDICE) == "([[11. Registro de decisões|SDD, seção 11]])"
    assert ligar("o SDD 0.36 e o SDD 9.9", INDICE) == "o SDD 0.36 e o SDD 9.9"


def test_em_linha_de_tabela_o_apelido_usa_barra_escapada() -> None:
    texto = ligar("| x | SDD 5.4 e `docs/SDD.md` |", INDICE)

    assert texto == "| x | [[5.4 Contas do extrato\\|SDD 5.4]] e [[SDD\\|docs/SDD.md]] |"


def test_secao_so_vira_ligacao_dentro_do_sdd() -> None:
    texto = "Nas seções 6.1, 11 e 12."

    assert ligar(texto, INDICE) == texto
    assert ligar(texto, INDICE, secoes_do_sdd=True) == (
        "Nas seções [[6.1 Stack|6.1]], [[11. Registro de decisões|11]] e 12."
    )


def test_codigo_nao_vira_ligacao() -> None:
    texto = "Rode `D-05` assim:\n```\nT40 D-05\n```\nFim da D-05."

    assert ligar(texto, INDICE) == "Rode `D-05` assim:\n```\nT40 D-05\n```\nFim da [[D-05]]."


def test_link_relativo_para_documento_e_imagem_vira_ligacao_do_obsidian() -> None:
    texto = ligar(
        "Veja as [regras](../../CLAUDE.md), a ![tela](tela.png) e o [uv](https://exemplo.org/a).",
        INDICE,
        pasta="docs/guias",
    )

    assert texto == (
        "Veja as [[CLAUDE - regras do repositório|regras]], a ![[tela.png]] "
        "e o [uv](https://exemplo.org/a)."
    )


def test_link_com_codigo_no_rotulo_vira_uma_ligacao_so() -> None:
    texto = ligar("| [`CLAUDE.md`](CLAUDE.md) | as regras |", INDICE)

    assert texto == "| [[CLAUDE - regras do repositório\\|CLAUDE.md]] | as regras |"


def test_ligacoes_ignoram_o_codigo() -> None:
    texto = "Ver [[D-05]] e [[T40|a T40]]; `Callable[[str], int]`\n```\n[[N15]]\n```"

    assert ligacoes(texto) == ["D-05", "T40"]


def test_nome_de_nota_tira_o_que_o_obsidian_nao_aceita() -> None:
    assert nome_de_nota("3.2 O contrato: a `Passagem`?") == "3.2 O contrato - a Passagem"
    assert nome_de_nota("10. Cronograma (out/2026)") == "10. Cronograma (out-2026)"


# --- Notas geradas ----------------------------------------------------------------------------


def test_cada_secao_do_sdd_vira_uma_nota_com_titulo_e_navegacao() -> None:
    arquivos = montar(_fontes())

    secao = _texto(arquivos, "SDD/1.1 O problema - a fila.md")
    assert "# 1.1 O problema: a fila" in secao
    assert "O problema, com o [[ABERTO-01]]." in secao
    assert "[[1. Visão]]" in secao
    visao = _texto(arquivos, "SDD/1. Visão.md")
    assert "ver seção [[1.1 O problema - a fila|1.1]] e [[D-01]]" in visao
    assert "- [[1.1 O problema - a fila]]" in visao
    assert "Histórico de versões do SDD" in _texto(arquivos, "SDD/SDD.md")


def test_cada_decisao_vira_uma_nota_com_os_campos_e_onde_aparece() -> None:
    arquivos = montar(_fontes())

    decisao = _texto(arquivos, "Decisões/D-01.md")
    assert "**Decisão:** Fazer assim" in decisao
    assert "**Motivo:** porque sim (seção [[1.1 O problema - a fila|1.1]])" in decisao
    assert "**Alternativa descartada:** fazer assado" in decisao
    onde = decisao.split("## Onde aparece", 1)[1].split("\n---\n", 1)[0]
    assert "[[1. Visão]]" in onde
    assert "[[T90]]" in onde
    assert "[[exemplo.rotas]]" not in onde  # o módulo cai na nota do pacote
    assert "[[exemplo]]" in onde
    assert "[[11. Registro de decisões]]" not in onde  # a nota-mãe fica no rodapé


def test_item_em_aberto_da_tabela_e_item_ja_fechado_viram_notas() -> None:
    arquivos = montar(_fontes())

    assert "**Item:** O nome" in _texto(arquivos, "Itens em aberto/ABERTO-01.md")
    fechado = _texto(arquivos, "Itens em aberto/ABERTO-07.md")
    assert "fechado" in fechado
    assert "[[Histórico de versões do SDD]]" in fechado


def test_plano_vira_nota_com_a_lista_de_tarefas_e_uma_nota_por_tarefa() -> None:
    arquivos = montar(_fontes())

    plano = _texto(arquivos, "Planos/Plano do mês 9.md")
    assert "- [[T90]] Primeira tarefa\n- ~~[[T91]] Segunda tarefa~~ → próximo plano\n" in plano
    assert "Faz a primeira coisa" not in plano
    tarefa = _texto(arquivos, "Tarefas/T90.md")
    assert "# T90. Primeira tarefa" in tarefa
    assert "Faz a primeira coisa ([[1.1 O problema - a fila|SDD 1.1]], [[D-01]])." in tarefa
    assert "Semana 1 — começo" in tarefa
    assert "semana:" not in _texto(arquivos, "Tarefas/T92.md")
    assert "**Tarefa:** Falar com o advogado" in _texto(arquivos, "Trilha não técnica/N1.md")
    adiado = _texto(arquivos, "Trilha não técnica/N2.md")
    assert "# ~~N2~~" in adiado
    assert "**Tarefa:** ~~Instalar o kit~~ (adiada)" in adiado
    assert "| ~~[[N2]]~~ | ~~Instalar o kit~~ (adiada) |" in plano


def test_documentos_sao_copiados_com_ligacoes_e_imagens_citadas_vao_para_anexos() -> None:
    arquivos = montar(_fontes())

    guia = _texto(arquivos, "Documentos/Um guia.md")
    assert "Veja o [[SDD|SDD]] e a ![[tela.png]]." in guia
    regras = _texto(arquivos, "Documentos/CLAUDE - regras do repositório.md")
    assert "[[1.1 O problema - a fila|SDD 1.1]] e a seção 1 (não é do SDD)" in regras
    assert arquivos["Anexos/tela.png"] == b"PNG"
    assert "Anexos/sobra.png" not in arquivos


def test_codigo_vira_notas_de_pacote_rotas_tabelas_migracoes_telas_e_comandos() -> None:
    arquivos = montar(_fontes())

    pacote = _texto(arquivos, "Código/exemplo.md")
    assert "Um pacote de exemplo, da [[T90]]." in pacote
    assert "### `exemplo.rotas`" in pacote
    assert "- **`ver`**: Mostra uma coisa." in pacote
    assert "- **`Coisa`** (classe): Uma coisa guardada." in pacote
    assert "- **`LIMITE`** = `3`: Quantas coisas cabem." in pacote
    assert "_escondida" not in pacote
    assert "`exemplo/tests/test_exemplo_rotas.py`: As rotas de exemplo." in pacote
    rotas = _texto(arquivos, "Código/Rotas.md")
    assert "| `/coisas/{coisa_id}` | GET | `ver` | [[exemplo]] | Mostra uma coisa. |" in rotas
    tabelas = _texto(arquivos, "Código/Tabelas do banco.md")
    assert "| `coisa` | `Coisa` | [[exemplo]] | id, nome | Uma coisa guardada. |" in tabelas
    migracoes = _texto(arquivos, "Código/Migrações do banco.md")
    assert "| `0001` | início: a coisa | 2026-01-01 |" in migracoes
    telas = _texto(arquivos, "Código/Telas do painel.md")
    assert "| `coisa.html` | `exemplo.rotas.ver` | `base.html` | `parte.html` |" in telas
    comandos = _texto(arquivos, "Código/Comandos.md")
    assert "| `uv run tarefas ola` | diz olá | Diz olá. |" in comandos
    mapa = _texto(arquivos, "Código/Mapa do código.md")
    assert "- [[exemplo]]: Um pacote de exemplo, da [[T90]]." in mapa


def test_nota_gerada_diz_de_onde_veio_e_como_gerar_de_novo() -> None:
    texto = _texto(montar(_fontes()), "Decisões/D-01.md")

    assert texto.startswith('---\ntipo: "decisão"\n')
    assert "gerada: true" in texto
    assert COMANDO in texto


def test_dois_documentos_com_o_mesmo_nome_de_nota_param_o_gerador() -> None:
    fontes = _fontes()
    documentos = {**fontes.documentos, "docs/guias/outro.md": "# Um guia\n"}

    with pytest.raises(ValueError, match="Um guia"):
        montar(replace(fontes, documentos=documentos))


# --- O vault no disco -------------------------------------------------------------------------


@pytest.mark.integracao
def test_escrever_apaga_nota_gerada_que_sobrou_e_nao_mexe_nas_escritas_a_mao(
    tmp_path: Path,
) -> None:
    vault = tmp_path / PASTA_DO_VAULT
    (vault / "Decisões").mkdir(parents=True)
    (vault / "Decisões" / "D-99.md").write_text("velha", encoding="utf-8")
    (vault / "00 Início.md").write_text("à mão", encoding="utf-8")

    escrever(tmp_path, {"Decisões/D-01.md": b"nova"})

    assert not (vault / "Decisões" / "D-99.md").exists()
    assert (vault / "Decisões" / "D-01.md").read_bytes() == b"nova"
    assert (vault / "00 Início.md").read_text(encoding="utf-8") == "à mão"
    assert diferencas(tmp_path, {"Decisões/D-01.md": b"nova"}) == []
    assert diferencas(tmp_path, {"Decisões/D-02.md": b"x"}) == [
        "falta: Decisões/D-02.md",
        "sobra: Decisões/D-01.md",
    ]


@pytest.mark.integracao
def test_nota_com_fim_de_linha_do_windows_conta_como_igual(tmp_path: Path) -> None:
    (tmp_path / PASTA_DO_VAULT / "Decisões").mkdir(parents=True)
    (tmp_path / PASTA_DO_VAULT / "Decisões" / "D-01.md").write_bytes(b"# D-01\r\n\r\nTexto\r\n")

    assert diferencas(tmp_path, {"Decisões/D-01.md": b"# D-01\n\nTexto\n"}) == []


@pytest.mark.integracao
def test_o_vault_no_git_esta_igual_ao_que_o_gerador_produz() -> None:
    raiz = encontrar_raiz(Path(__file__).resolve())

    problemas = diferencas(raiz, gerar(raiz))

    assert not problemas, f"vault desatualizado: rode `{COMANDO}`.\n" + "\n".join(problemas[:20])


@pytest.mark.integracao
def test_toda_ligacao_do_vault_aponta_para_uma_nota_ou_anexo_que_existe() -> None:
    vault = encontrar_raiz(Path(__file__).resolve()) / PASTA_DO_VAULT
    notas = list(vault.rglob("*.md"))
    nomes = [nota.stem for nota in notas]
    anexos = {arquivo.name for arquivo in (vault / "Anexos").iterdir()}
    repetidos = {nome for nome in nomes if nomes.count(nome) > 1}
    assert not repetidos, f"notas com o mesmo nome: {sorted(repetidos)}"

    quebradas = []
    for nota in notas:
        for alvo in ligacoes(nota.read_text(encoding="utf-8")):
            if alvo not in nomes and alvo not in anexos:
                quebradas.append(f"{nota.relative_to(vault)} -> {alvo}")
    assert not quebradas, "\n".join(quebradas)

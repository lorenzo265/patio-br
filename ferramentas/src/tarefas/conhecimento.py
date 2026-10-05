"""O vault do Obsidian em ``knowledge/``: as notas geradas de ``docs/`` e do código.

``uv run tarefas conhecimento`` reescreve as pastas geradas do vault (``PASTAS_GERADAS``). As
notas escritas à mão (na raiz do vault e em ``Temas/``) ficam como estão. Um teste confere que o
vault no Git é igual ao que este gerador produz: quem muda ``docs/`` ou o código e esquece de
gerar vê o teste falhar, com o comando para corrigir.

- **Documentos:** cada seção do SDD, cada decisão (D-nn), cada item em aberto (ABERTO-nn), cada
  tarefa dos planos (Tnn) e cada item da trilha não técnica (Nnn) vira uma nota; os outros
  documentos são copiados inteiros.
- **Código:** pacotes, módulos, rotas, tabelas, migrações, telas e comandos, lidos dos arquivos
  com o ``ast`` do Python, sem importar nada; os docstrings são a descrição.
- **Ligações:** as referências viram ligações do Obsidian (``[[D-05]]``), e cada decisão, item,
  tarefa e item da trilha lista as notas que o citam ("Onde aparece").

Só usa a biblioteca padrão, como o resto do ``tarefas``.
"""

from __future__ import annotations

import argparse
import ast
import json
import posixpath
import re
import sys
import tomllib
from collections import defaultdict
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from tarefas.comandos import encontrar_raiz

PASTA_DO_VAULT = "knowledge"
"""O vault, relativo à raiz do repositório."""

PASTAS_GERADAS = (
    "SDD",
    "Decisões",
    "Itens em aberto",
    "Planos",
    "Tarefas",
    "Trilha não técnica",
    "Documentos",
    "Código",
    "Anexos",
)
"""Pastas do vault que o gerador reescreve inteiras; o resto do vault é escrito à mão."""

COMANDO = "uv run tarefas conhecimento"

ARQUIVO_DO_SDD = "docs/SDD.md"
PASTA_DOS_PLANOS = "docs/planos"
PASTA_DAS_TELAS = "nuvem/src/nuvem/web/telas"
PASTA_DAS_MIGRACOES = "nuvem/migracoes/versions"
MODULO_DOS_COMANDOS = "tarefas.comandos"
EXTENSOES_DE_IMAGEM = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

NOMES_DOS_DOCUMENTOS: dict[str, str] = {
    "README.md": "README",
    "CLAUDE.md": "CLAUDE - regras do repositório",
    "borda/AVISOS-DE-TERCEIROS.md": "Avisos de terceiros da caixa de borda",
    "nuvem/src/nuvem/web/estatico/LEIA-ME.md": "Arquivos de terceiros do painel",
    "docs/guias/demo-mes-1.md": "Guia da demonstração do mês 1",
    "docs/validacao/fatos-tecnicos-stack.md": "Validação - fatos técnicos da stack",
    "docs/validacao/fontes-de-placas.md": "Validação - fontes de placas",
    "docs/validacao/recebimento-e-estoque.md": "Validação - recebimento e estoque",
    "docs/validacao/relatorio-validacao-v3.md": "Validação - relatório da tese v3",
    "docs/prompts/identidade-visual.md": "Prompt da identidade visual",
}
"""Nome no vault dos documentos fora do SDD e dos planos.

Os de fora de ``docs/`` só entram se estiverem aqui; um documento novo em ``docs/`` sem nome aqui
entra com o próprio título.
"""

_PROIBIDOS_NO_NOME = re.compile(r'[\\*?"<>|#^\[\]`~]')
_TITULO = re.compile(r"(#{1,6}) (.+?)\s*")
_NUMERO_E_TITULO = re.compile(r"(\d+(?:\.\d+)*)\.?\s+(.+)")
_TAREFA = re.compile(r"(?P<risco>~~)?(?P<id>T\d+)\.\s*")
_DECISAO = re.compile(r"D-\d+")
_ABERTO = re.compile(r"ABERTO-\d+")
_ITEM_DA_TRILHA = re.compile(r"N\d+")
_SEPARADOR_DE_TABELA = re.compile(r":?-+:?")
_IMAGEM = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
_CRASE = re.compile(r"(`+)(.+?)\1")
_LINK = re.compile(r"(?P<imagem>!?)\[(?P<rotulo>[^\]]*)\]\((?P<alvo>[^)\s]+)\)")
_LIGAVEL = re.compile(
    r"(?P<wiki>!?\[\[[^\]]*\]\])"
    r"|\[(?P<entre_colchetes>ABERTO-\d+)\]"
    r"|\b(?P<id>ABERTO-\d+|D-\d+|T\d+|N\d+)\b"
    r"|\b(?P<sdd>SDD,? (?:[Ss]eç(?:ão|ões) )?)(?P<numeros_do_sdd>{numeros})"
    r"|\b(?P<secao>[Ss]eç(?:ão|ões) )(?P<numeros>{numeros})".format(
        numeros=r"\d+(?:\.\d+)?(?:(?:, | e )\d+(?:\.\d+)?)*\b"
    )
)
_NUMERO_DE_SECAO = re.compile(r"\d+(?:\.\d+)?")
_ALVO_DA_LIGACAO = re.compile(r"\[\[([^\]|#\\]+)")
_INCLUSAO = re.compile(r"{%-?\s*(extends|include)\s+[\"']([^\"']+)[\"']")
_METODOS_HTTP = ("get", "post", "put", "patch", "delete")


# --- Fontes -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ArquivoDeCodigo:
    """Um arquivo ``.py`` do ``src/`` de um pacote do workspace."""

    caminho: str
    """Relativo à raiz do repositório, com ``/``."""
    modulo: str
    """Nome do módulo; o ``__init__.py`` tem o nome do pacote."""
    membro: str
    """A pasta do workspace (``nuvem``, ``borda``...)."""
    texto: str

    @property
    def e_pacote(self) -> bool:
        return self.caminho.endswith("__init__.py")

    @property
    def pacote(self) -> str:
        """O pacote onde o módulo mora: cada pacote vira uma nota."""
        return self.modulo if self.e_pacote else self.modulo.rpartition(".")[0] or self.modulo


@dataclass(frozen=True)
class ArquivoDeTeste:
    """Um arquivo de teste (``tests/test_*.py``) de um pacote do workspace."""

    caminho: str
    membro: str
    texto: str


@dataclass(frozen=True)
class Fontes:
    """Tudo o que o gerador lê do repositório, já em memória (os testes montam à mão)."""

    sdd: str
    planos: dict[str, str]
    """Caminho do plano -> texto."""
    documentos: dict[str, str]
    """Caminho dos outros documentos -> texto."""
    nomes_dos_documentos: dict[str, str]
    descricoes: dict[str, str]
    """Membro do workspace -> a descrição do ``pyproject.toml`` dele."""
    codigo: tuple[ArquivoDeCodigo, ...]
    testes: tuple[ArquivoDeTeste, ...]
    telas: dict[str, str]
    """Nome do arquivo da tela -> texto."""
    migracoes: dict[str, str]
    """Caminho da migração -> texto."""
    imagens: dict[str, bytes]
    """Caminho das imagens de ``docs/`` -> conteúdo; só as citadas vão para o vault."""


def _ler(caminho: Path) -> str:
    # Sem o \r do Windows: o vault sai igual em qualquer sistema.
    return caminho.read_text(encoding="utf-8").replace("\r\n", "\n")


def ler_fontes(raiz: Path) -> Fontes:
    """Lê do repositório os documentos, o código, as telas e as migrações."""

    def relativo(caminho: Path) -> str:
        return caminho.relative_to(raiz).as_posix()

    def arquivos(pasta: Path, padrao: str) -> list[Path]:
        achados = (p for p in pasta.rglob(padrao) if "__pycache__" not in p.parts)
        return sorted(achados, key=relativo)

    planos = {relativo(p): _ler(p) for p in arquivos(raiz / PASTA_DOS_PLANOS, "*.md")}
    documentos = {
        relativo(p): _ler(p)
        for p in arquivos(raiz / "docs", "*.md")
        if relativo(p) != ARQUIVO_DO_SDD and relativo(p) not in planos
    }
    for caminho in NOMES_DOS_DOCUMENTOS:
        if not caminho.startswith("docs/"):
            documentos[caminho] = _ler(raiz / caminho)
    imagens = {
        relativo(p): p.read_bytes()
        for p in arquivos(raiz / "docs", "*")
        if p.suffix.lower() in EXTENSOES_DE_IMAGEM
    }

    membros: list[str] = tomllib.loads(_ler(raiz / "pyproject.toml"))["tool"]["uv"]["workspace"][
        "members"
    ]
    descricoes: dict[str, str] = {}
    codigo: list[ArquivoDeCodigo] = []
    testes: list[ArquivoDeTeste] = []
    for membro in membros:
        projeto = tomllib.loads(_ler(raiz / membro / "pyproject.toml"))["project"]
        descricoes[membro] = projeto.get("description", "")
        src = raiz / membro / "src"
        for arquivo in arquivos(src, "*.py"):
            partes = arquivo.relative_to(src).with_suffix("").parts
            if partes[-1] == "__init__":
                partes = partes[:-1]
            modulo = ".".join(partes)
            codigo.append(ArquivoDeCodigo(relativo(arquivo), modulo, membro, _ler(arquivo)))
        for arquivo in arquivos(raiz / membro / "tests", "test_*.py"):
            testes.append(ArquivoDeTeste(relativo(arquivo), membro, _ler(arquivo)))

    return Fontes(
        sdd=_ler(raiz / ARQUIVO_DO_SDD),
        planos=planos,
        documentos=documentos,
        nomes_dos_documentos=NOMES_DOS_DOCUMENTOS,
        descricoes=descricoes,
        codigo=tuple(codigo),
        testes=tuple(testes),
        telas={p.name: _ler(p) for p in arquivos(raiz / PASTA_DAS_TELAS, "*.html")},
        migracoes={relativo(p): _ler(p) for p in arquivos(raiz / PASTA_DAS_MIGRACOES, "*.py")},
        imagens=imagens,
    )


# --- Notas ------------------------------------------------------------------------------------


@dataclass
class Nota:
    """Uma nota do vault, antes de virar texto."""

    pasta: str
    nome: str
    tipo: str
    fonte: str
    corpo: str
    """Markdown ainda sem as ligações: o ``ligar`` passa em todas no fim."""
    pasta_da_fonte: str = ""
    """Pasta do documento de origem, para os links relativos."""
    secoes_do_sdd: bool = False
    """O texto é do SDD: "seção 5.4" aponta para a seção do próprio SDD."""
    propriedades: dict[str, str] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    citavel: bool = False
    """Recebe a lista "Onde aparece", com as notas que ligam para ela."""
    pai: str = ""
    """A nota de onde esta saiu: vai no rodapé e não conta em "Onde aparece"."""
    rodape: str = ""
    """Navegação no fim da nota, já com as ligações."""

    @property
    def caminho(self) -> str:
        return f"{self.pasta}/{self.nome}.md"


@dataclass(frozen=True)
class Indice:
    """O que pode virar ligação, e o nome da nota de cada coisa."""

    ids: frozenset[str]
    """D-nn, ABERTO-nn, Tnn e Nnn que têm nota."""
    secoes: dict[str, str]
    """Número da seção do SDD -> nome da nota."""
    documentos: dict[str, str]
    """Caminho do documento no repositório -> nome da nota."""
    anexos: dict[str, str]
    """Caminho da imagem no repositório -> nome do arquivo em ``Anexos/``."""


def nome_de_nota(titulo: str) -> str:
    """Tira do título o que o Obsidian (e o Windows) não aceita em nome de arquivo."""
    nome = titulo.replace(": ", " - ").replace(":", "-").replace("/", "-")
    nome = _PROIBIDOS_NO_NOME.sub("", nome)
    return re.sub(r"\s+", " ", nome).strip().rstrip(".").strip()


def _chave_natural(texto: str) -> list[tuple[int, int | str]]:
    # "1.2" antes de "1.10", e "T9" antes de "T10".
    return [
        (0, int(parte)) if parte.isdigit() else (1, parte.lower())
        for parte in re.split(r"(\d+)", texto)
        if parte
    ]


def _yaml(valor: str) -> str:
    return json.dumps(valor, ensure_ascii=False)


def _aparar(linhas: Sequence[str]) -> list[str]:
    """Tira as linhas vazias das pontas e os separadores (``---``) do fim."""
    inicio, fim = 0, len(linhas)
    while inicio < fim and not linhas[inicio].strip():
        inicio += 1
    while fim > inicio and linhas[fim - 1].strip() in ("", "---"):
        fim -= 1
    return list(linhas[inicio:fim])


def _resumo(docstring: str | None) -> str:
    """O primeiro parágrafo de um docstring, numa linha só."""
    if not docstring:
        return ""
    return " ".join(docstring.split("\n\n", 1)[0].split())


def _celula(texto: str) -> str:
    return texto.replace("|", "\\|")


def _texto_da_nota(nota: Nota, corpo: str, citacoes: Sequence[str]) -> str:
    linhas = ["---", f"tipo: {_yaml(nota.tipo)}"]
    linhas += [f"{chave}: {_yaml(valor)}" for chave, valor in nota.propriedades.items()]
    linhas += [f"fonte: {_yaml(nota.fonte)}", "gerada: true"]
    if nota.tags:
        linhas.append(f"tags: [{', '.join(nota.tags)}]")
    linhas += [
        "---",
        "",
        f"> [!note] Gerada de `{nota.fonte}` por `{COMANDO}`: para mudar, mude a fonte e gere "
        "de novo.",
        "",
        corpo.strip(),
    ]
    if citacoes:
        linhas += ["", "## Onde aparece", "", *(f"- [[{nome}]]" for nome in citacoes)]
    if nota.rodape:
        linhas += ["", "---", "", nota.rodape]
    return "\n".join(linhas) + "\n"


# --- Ligações ---------------------------------------------------------------------------------


def ligar(
    texto: str,
    indice: Indice,
    *,
    pasta: str = "",
    secoes_do_sdd: bool = False,
    propria: str = "",
) -> str:
    """Troca as referências do texto por ligações do Obsidian.

    Vira ligação: D-nn, ABERTO-nn, Tnn e Nnn que têm nota; "SDD 5.4"; "seção 5.4" e "seções 5.1
    e 5.2", só no SDD (fora dele, "seção" pode ser do próprio documento); os caminhos de
    documentos entre crases e os links relativos. Código (entre crases ou em bloco) fica como
    está, menos o ``[ABERTO-nn]`` e os caminhos de documentos. Em linha de tabela, o ``|`` do
    apelido vai escapado. A ``propria`` nota não liga para si mesma.
    """
    linhas = []
    em_bloco = False
    for linha in texto.split("\n"):
        if linha.lstrip().startswith("```"):
            em_bloco = not em_bloco
            linhas.append(linha)
        elif em_bloco:
            linhas.append(linha)
        else:
            linhas.append(_ligar_linha(linha, indice, pasta, secoes_do_sdd, propria))
    return "\n".join(linhas)


def _ligar_linha(linha: str, indice: Indice, pasta: str, secoes_do_sdd: bool, propria: str) -> str:
    barra = "\\|" if linha.lstrip().startswith("|") else "|"

    def fora_dos_links(trecho: str) -> str:
        partes = []
        inicio = 0
        for crase in _CRASE.finditer(trecho):
            antes = trecho[inicio : crase.start()]
            partes.append(_ligar_trecho(antes, indice, secoes_do_sdd, barra, propria))
            partes.append(_ligar_codigo(crase, indice, barra))
            inicio = crase.end()
        partes.append(_ligar_trecho(trecho[inicio:], indice, secoes_do_sdd, barra, propria))
        return "".join(partes)

    # Os links primeiro: o rótulo pode ter código (``[`CLAUDE.md`](CLAUDE.md)``).
    partes = []
    inicio = 0
    for link in _LINK.finditer(linha):
        partes.append(fora_dos_links(linha[inicio : link.start()]))
        partes.append(_ligar_link(link, indice, pasta, barra))
        inicio = link.end()
    partes.append(fora_dos_links(linha[inicio:]))
    return "".join(partes)


def _ligar_codigo(crase: re.Match[str], indice: Indice, barra: str) -> str:
    conteudo = crase.group(2)
    aberto = re.fullmatch(r"\[(ABERTO-\d+)\]", conteudo)
    if aberto and aberto.group(1) in indice.ids:
        return f"[[{aberto.group(1)}]]"
    if conteudo in indice.documentos:
        return f"[[{indice.documentos[conteudo]}{barra}{conteudo}]]"
    return crase.group(0)


def _ligar_trecho(
    trecho: str, indice: Indice, secoes_do_sdd: bool, barra: str, propria: str
) -> str:
    def secoes(antes: str, numeros: str) -> str:
        # Cada número vira uma ligação; o primeiro leva junto o que vem antes ("SDD 5.4").
        def secao(numero: re.Match[str]) -> str:
            nota = indice.secoes.get(numero.group(0))
            rotulo = antes + numero.group(0) if numero.start() == 0 else numero.group(0)
            return f"[[{nota}{barra}{rotulo}]]" if nota else rotulo

        return _NUMERO_DE_SECAO.sub(secao, numeros)

    def trocar(achado: re.Match[str]) -> str:
        if achado.group("wiki") is not None:
            return achado.group(0)
        identificador = achado.group("entre_colchetes") or achado.group("id")
        if identificador is not None:
            ligavel = identificador in indice.ids and identificador != propria
            return f"[[{identificador}]]" if ligavel else achado.group(0)
        if achado.group("sdd") is not None:
            return secoes(achado.group("sdd"), achado.group("numeros_do_sdd"))
        if secoes_do_sdd:
            return achado.group("secao") + secoes("", achado.group("numeros"))
        return achado.group(0)

    return _LIGAVEL.sub(trocar, trecho)


def _ligar_link(achado: re.Match[str], indice: Indice, pasta: str, barra: str) -> str:
    # Endereço da internet ou âncora não bate com nenhum caminho do repositório: fica como está.
    caminho = posixpath.normpath(posixpath.join(pasta, achado.group("alvo")))
    if achado.group("imagem") and caminho in indice.anexos:
        return f"![[{indice.anexos[caminho]}]]"
    if not achado.group("imagem") and caminho in indice.documentos:
        rotulo = achado.group("rotulo").replace("`", "")
        return f"[[{indice.documentos[caminho]}{barra}{rotulo}]]"
    return achado.group(0)


# --- Documentos -------------------------------------------------------------------------------


def _titulos(linhas: Sequence[str]) -> Iterator[tuple[int, int, str]]:
    """Devolve (linha, nível, texto) de cada título fora dos blocos de código."""
    em_bloco = False
    for posicao, linha in enumerate(linhas):
        if linha.lstrip().startswith("```"):
            em_bloco = not em_bloco
        elif not em_bloco and (titulo := _TITULO.fullmatch(linha)):
            yield posicao, len(titulo.group(1)), titulo.group(2)


def _celulas(linha: str) -> list[str]:
    miolo = linha.strip().removeprefix("|").removesuffix("|")
    return [celula.strip() for celula in miolo.split("|")]


def _linhas_de_tabela(linhas: Sequence[str]) -> Iterator[tuple[list[str], list[str]]]:
    """Devolve (cabeçalho, células) de cada linha de dados das tabelas do texto."""
    cabecalho: list[str] | None = None
    for linha in linhas:
        if not linha.lstrip().startswith("|"):
            cabecalho = None
            continue
        celulas = _celulas(linha)
        if cabecalho is None:
            cabecalho = celulas
        elif not all(_SEPARADOR_DE_TABELA.fullmatch(celula) for celula in celulas):
            yield cabecalho, celulas


def _campos(cabecalho: Sequence[str], celulas: Sequence[str]) -> str:
    """As colunas de uma linha de tabela, uma por parágrafo: ``**Coluna:** valor``."""
    return "\n\n".join(
        f"**{nome}:** {valor}" for nome, valor in zip(cabecalho, celulas, strict=False)
    )


@dataclass
class _Secao:
    nivel: int
    numero: str | None
    titulo: str
    nome: str
    linhas: list[str]


def _secoes_do_sdd(texto: str) -> tuple[list[str], list[_Secao]]:
    """Divide o SDD no preâmbulo e nas seções (``##``) e subseções (``###``)."""
    linhas = texto.split("\n")
    titulos = [(i, nivel, titulo) for i, nivel, titulo in _titulos(linhas) if nivel in (2, 3)]
    preambulo = _aparar(linhas[: titulos[0][0]] if titulos else linhas)
    secoes = []
    for posicao, (i, nivel, titulo) in enumerate(titulos):
        fim = titulos[posicao + 1][0] if posicao + 1 < len(titulos) else len(linhas)
        numerado = _NUMERO_E_TITULO.fullmatch(titulo)
        if numerado is None:
            numero, nome = None, f"{nome_de_nota(titulo)} do SDD"
        else:
            numero = numerado.group(1)
            separador = ". " if nivel == 2 else " "
            nome = nome_de_nota(f"{numero}{separador}{numerado.group(2)}")
        secoes.append(_Secao(nivel, numero, titulo, nome, _aparar(linhas[i + 1 : fim])))
    return preambulo, secoes


def _notas_do_sdd(preambulo: Sequence[str], secoes: Sequence[_Secao]) -> list[Nota]:
    pais: dict[str, str] = {}
    filhos: dict[str, list[str]] = defaultdict(list)
    pai_atual = "SDD"
    for secao in secoes:
        if secao.nivel == 2:
            pai_atual = secao.nome
            pais[secao.nome] = "SDD"
        else:
            pais[secao.nome] = pai_atual
            filhos[pai_atual].append(secao.nome)

    arvore = [f"{chr(9) if s.nivel == 3 else ''}- [[{s.nome}]]" for s in secoes]
    notas = [
        Nota(
            pasta="SDD",
            nome="SDD",
            tipo="índice do SDD",
            fonte=ARQUIVO_DO_SDD,
            corpo="\n".join([*preambulo, "", "## Seções", "", *arvore]),
            pasta_da_fonte="docs",
            secoes_do_sdd=True,
            tags=("sdd",),
        )
    ]
    for posicao, secao in enumerate(secoes):
        corpo = [f"# {secao.titulo}", "", *secao.linhas]
        if filhos[secao.nome]:
            corpo += ["", "**Nesta seção:**", "", *(f"- [[{f}]]" for f in filhos[secao.nome])]
        navegacao = []
        if posicao > 0:
            navegacao.append(f"Anterior: [[{secoes[posicao - 1].nome}]]")
        navegacao.append(f"Parte de: [[{pais[secao.nome]}]]")
        if posicao + 1 < len(secoes):
            navegacao.append(f"Próxima: [[{secoes[posicao + 1].nome}]]")
        notas.append(
            Nota(
                pasta="SDD",
                nome=secao.nome,
                tipo="seção do SDD",
                fonte=ARQUIVO_DO_SDD,
                corpo="\n".join(corpo),
                pasta_da_fonte="docs",
                secoes_do_sdd=True,
                propriedades={"secao": secao.numero} if secao.numero else {},
                tags=("sdd",),
                pai=pais[secao.nome],
                rodape=" · ".join(navegacao),
            )
        )
        notas += _notas_das_tabelas_do_sdd(secao)
    return notas


def _notas_das_tabelas_do_sdd(secao: _Secao) -> Iterator[Nota]:
    """As decisões (seção 11) e os itens em aberto (seção 12), uma nota por linha."""
    for cabecalho, celulas in _linhas_de_tabela(secao.linhas):
        identificador = celulas[0].strip("~")  # riscado: a linha continua no registro
        if _DECISAO.fullmatch(identificador):
            pasta, tipo, tag, corpo = "Decisões", "decisão", "decisao", ""
        elif _ABERTO.fullmatch(identificador):
            pasta, tipo, tag = "Itens em aberto", "item em aberto", "item-em-aberto"
            corpo = "**Situação:** em aberto.\n\n"
        else:
            continue
        yield Nota(
            pasta=pasta,
            nome=identificador,
            tipo=tipo,
            fonte=ARQUIVO_DO_SDD,
            corpo=f"# {identificador}\n\n{corpo}{_campos(cabecalho[1:], celulas[1:])}",
            pasta_da_fonte="docs",
            secoes_do_sdd=True,
            propriedades={"id": identificador},
            tags=(tag,),
            citavel=True,
            pai=secao.nome,
            rodape=f"Da [[{secao.nome}]], no [[SDD]].",
        )


def _nota_do_aberto_fechado(identificador: str) -> Nota:
    corpo = (
        f"# {identificador}\n\n"
        "**Situação:** fechado: não está mais na [[12. Itens em aberto]] do SDD. A decisão que o "
        'fechou e a versão do SDD em que saiu estão em "Onde aparece", abaixo (em geral, uma '
        "decisão e o [[Histórico de versões do SDD]])."
    )
    return Nota(
        pasta="Itens em aberto",
        nome=identificador,
        tipo="item em aberto (fechado)",
        fonte=ARQUIVO_DO_SDD,
        corpo=corpo,
        propriedades={"id": identificador},
        tags=("item-em-aberto", "fechado"),
        citavel=True,
    )


def _nome_do_plano(caminho: str, texto: str) -> str:
    for linha in texto.split("\n"):
        if linha.startswith("# "):
            return nome_de_nota(re.split(r" \(|:", linha[2:], maxsplit=1)[0])
    return nome_de_nota(posixpath.basename(caminho).removesuffix(".md"))


def _notas_do_plano(caminho: str, texto: str) -> list[Nota]:
    """O plano numa nota, com a lista das tarefas; cada tarefa e item da trilha numa nota."""
    plano = _nome_do_plano(caminho, texto)
    linhas = texto.split("\n")
    titulos = list(_titulos(linhas))
    tarefas: dict[int, tuple[int, str, str, str]] = {}
    semana = ""
    for posicao, (inicio, nivel, titulo) in enumerate(titulos):
        if nivel <= 3:
            semana = titulo if nivel == 3 else ""
        tarefa = _TAREFA.match(titulo) if nivel == 4 else None
        if tarefa:
            fim = next((i for i, n, _ in titulos[posicao + 1 :] if n <= 4), len(linhas))
            tarefas[inicio] = (fim, tarefa.group("id"), titulo, semana)

    notas = []
    corpo_do_plano = []
    posicao = 0
    while posicao < len(linhas):
        if posicao not in tarefas:
            corpo_do_plano.append(linhas[posicao])
            posicao += 1
            continue
        fim, identificador, titulo, semana = tarefas[posicao]
        corpo_do_plano.append(
            "- " + _TAREFA.sub(lambda t: f"{t.group('risco') or ''}[[{t.group('id')}]] ", titulo, 1)
        )
        if fim < len(linhas) and fim not in tarefas:
            corpo_do_plano.append("")
        propriedades = {"plano": plano}
        if semana:
            propriedades["semana"] = semana
        notas.append(
            Nota(
                pasta="Tarefas",
                nome=identificador,
                tipo="tarefa",
                fonte=caminho,
                corpo="\n".join([f"# {titulo}", "", *_aparar(linhas[posicao + 1 : fim])]),
                pasta_da_fonte=PASTA_DOS_PLANOS,
                propriedades=propriedades,
                tags=("tarefa",),
                citavel=True,
                pai=plano,
                rodape=f"Do [[{plano}]]" + (f", {semana}." if semana else "."),
            )
        )
        posicao = fim

    for cabecalho, celulas in _linhas_de_tabela(linhas):
        item = celulas[0].strip("~")  # riscado: adiado ou resolvido, e o texto diz qual
        if _ITEM_DA_TRILHA.fullmatch(item):
            notas.append(
                Nota(
                    pasta="Trilha não técnica",
                    nome=item,
                    tipo="item da trilha não técnica",
                    fonte=caminho,
                    corpo=f"# {celulas[0]}\n\n{_campos(cabecalho[1:], celulas[1:])}",
                    pasta_da_fonte=PASTA_DOS_PLANOS,
                    propriedades={"id": item, "plano": plano},
                    tags=("trilha",),
                    citavel=True,
                    pai=plano,
                    rodape=f"Da trilha não técnica do [[{plano}]].",
                )
            )
    notas.insert(
        0,
        Nota(
            pasta="Planos",
            nome=plano,
            tipo="plano",
            fonte=caminho,
            corpo="\n".join(_aparar(corpo_do_plano)),
            pasta_da_fonte=PASTA_DOS_PLANOS,
            tags=("plano",),
        ),
    )
    return notas


def _nome_do_documento(caminho: str, texto: str, nomes: dict[str, str]) -> str:
    if caminho in nomes:
        return nomes[caminho]
    for linha in texto.split("\n"):
        if linha.startswith("# "):
            return nome_de_nota(linha[2:])
    return nome_de_nota(posixpath.basename(caminho).removesuffix(".md"))


# --- Código -----------------------------------------------------------------------------------


def _docstring_do_atributo(corpo: Sequence[ast.stmt], posicao: int) -> str | None:
    """O texto logo depois de uma atribuição (o jeito do projeto de documentar constantes)."""
    if posicao + 1 >= len(corpo):
        return None
    seguinte = corpo[posicao + 1]
    if (
        isinstance(seguinte, ast.Expr)
        and isinstance(seguinte.value, ast.Constant)
        and isinstance(seguinte.value.value, str)
    ):
        return seguinte.value.value
    return None


def _itens_publicos(arvore: ast.Module) -> Iterator[str]:
    """Classes, funções e constantes documentadas do módulo, com o resumo de cada uma."""
    for posicao, no in enumerate(arvore.body):
        if isinstance(no, ast.ClassDef) and not no.name.startswith("_"):
            yield f"- **`{no.name}`** (classe): {_resumo(ast.get_docstring(no))}".rstrip(": ")
        elif isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef) and not no.name.startswith("_"):
            yield f"- **`{no.name}`**: {_resumo(ast.get_docstring(no))}".rstrip(": ")
        elif isinstance(no, ast.Assign | ast.AnnAssign):
            alvo = no.targets[0] if isinstance(no, ast.Assign) else no.target
            documentacao = _docstring_do_atributo(arvore.body, posicao)
            if not isinstance(alvo, ast.Name) or alvo.id.startswith("_") or documentacao is None:
                continue
            valor = ast.unparse(no.value) if no.value is not None else ""
            igual = f" = `{valor}`" if valor and len(valor) <= 40 and "`" not in valor else ""
            yield f"- **`{alvo.id}`**{igual}: {_resumo(documentacao)}"


def _nome_do_pacote_do_teste(teste: ArquivoDeTeste, pacotes: Sequence[str]) -> str | None:
    """O pacote que o teste cobre, pelo nome do arquivo (``test_nuvem_web_patio`` -> nuvem.web)."""
    nome = posixpath.basename(teste.caminho).removeprefix("test_").removesuffix(".py")
    candidatos = [
        pacote
        for pacote in pacotes
        if nome == pacote.replace(".", "_") or nome.startswith(pacote.replace(".", "_") + "_")
    ]
    return max(candidatos, key=len) if candidatos else None


def _notas_do_codigo(fontes: Fontes) -> list[Nota]:
    arvores = {arquivo.caminho: ast.parse(arquivo.texto) for arquivo in fontes.codigo}
    por_pacote: dict[str, list[ArquivoDeCodigo]] = defaultdict(list)
    for arquivo in fontes.codigo:
        por_pacote[arquivo.pacote].append(arquivo)
    pacotes = sorted(por_pacote, key=_chave_natural)
    testes: dict[str, list[ArquivoDeTeste]] = defaultdict(list)
    for teste in fontes.testes:
        pacote = _nome_do_pacote_do_teste(teste, pacotes)
        if pacote:
            testes[pacote].append(teste)

    def resumo_do_pacote(pacote: str) -> str:
        inicio = next((a for a in por_pacote[pacote] if a.e_pacote), None)
        return _resumo(ast.get_docstring(arvores[inicio.caminho])) if inicio else ""

    notas = []
    for pacote in pacotes:
        arquivos = sorted(por_pacote[pacote], key=lambda a: (not a.e_pacote, a.modulo))
        pasta = posixpath.dirname(arquivos[0].caminho)
        linhas = [f"# {pacote}", "", f"Pasta `{pasta}/`."]
        for arquivo in arquivos:
            arvore = arvores[arquivo.caminho]
            documentacao = ast.get_docstring(arvore)
            itens = list(_itens_publicos(arvore))
            if arquivo.e_pacote:
                linhas += ["", documentacao] if documentacao else []
                linhas += ["", *itens] if itens else []
                subpacotes = [p for p in pacotes if p.rpartition(".")[0] == pacote]
                if subpacotes:
                    linhas += ["", "## Subpacotes", ""]
                    linhas += [f"- [[{p}]]: {resumo_do_pacote(p)}".rstrip(": ") for p in subpacotes]
                linhas += ["", "## Módulos"]
                continue
            linhas += ["", f"### `{arquivo.modulo}`", "", f"`{arquivo.caminho}`"]
            linhas += ["", documentacao] if documentacao else []
            linhas += ["", *itens] if itens else []
        if testes[pacote]:
            linhas += ["", "## Testes", ""]
            for teste in testes[pacote]:
                resumo = _resumo(ast.get_docstring(ast.parse(teste.texto)))
                linhas.append(f"- `{teste.caminho}`: {resumo}".rstrip(": "))
        if linhas[-1] == "## Módulos":
            linhas = linhas[:-2]
        notas.append(
            Nota(
                pasta="Código",
                nome=pacote,
                tipo="pacote",
                fonte=f"{pasta}/",
                corpo="\n".join(linhas),
                pasta_da_fonte=pasta,
                tags=("codigo",),
                pai="Mapa do código",
                rodape="Do [[Mapa do código]].",
            )
        )

    notas.append(_nota_do_mapa(fontes, pacotes, resumo_do_pacote))
    notas.append(_nota_das_rotas(fontes, arvores))
    notas.append(_nota_das_tabelas(fontes, arvores))
    notas.append(_nota_das_migracoes(fontes))
    notas.append(_nota_das_telas(fontes, arvores))
    notas.append(_nota_dos_comandos(fontes, arvores))
    return notas


def _nota_de_codigo(nome: str, fonte: str, corpo: Sequence[str]) -> Nota:
    return Nota(
        pasta="Código",
        nome=nome,
        tipo="código",
        fonte=fonte,
        corpo="\n".join(corpo),
        tags=("codigo",),
        pai="Mapa do código",
        rodape="Do [[Mapa do código]].",
    )


def _nota_do_mapa(
    fontes: Fontes, pacotes: Sequence[str], resumo_do_pacote: Callable[[str], str]
) -> Nota:
    membros = sorted({arquivo.membro for arquivo in fontes.codigo})
    linhas = [
        "# Mapa do código",
        "",
        f"O repositório é um workspace do uv com {len(membros)} pacotes; cada um tem o código "
        "em `src/` e os testes em `tests/`. Cada nota abaixo é um pacote Python, com os módulos, "
        "o que cada um faz (lido dos docstrings) e os testes.",
        "",
        "Também gerado do código:",
        "",
        "- [[Rotas]]: os endereços da API e das telas",
        "- [[Tabelas do banco]]: as tabelas e as colunas",
        "- [[Migrações do banco]]: as mudanças do banco, em ordem",
        "- [[Telas do painel]]: os arquivos de tela e quem mostra cada um",
        "- [[Comandos]]: o `uv run tarefas ...`",
    ]
    for membro in membros:
        linhas += ["", f"## {membro} (`{membro}/`)", ""]
        if fontes.descricoes.get(membro):
            linhas += [fontes.descricoes[membro], ""]
        do_membro = {a.pacote for a in fontes.codigo if a.membro == membro}
        for pacote in (p for p in pacotes if p in do_membro):
            recuo = "\t" * pacote.count(".")
            linhas.append(f"{recuo}- [[{pacote}]]: {resumo_do_pacote(pacote)}".rstrip(": "))
    return Nota(
        pasta="Código",
        nome="Mapa do código",
        tipo="mapa do código",
        fonte="pyproject.toml",
        corpo="\n".join(linhas),
        tags=("codigo",),
    )


def _funcoes(arvore: ast.Module) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
            yield no


def _atribui(no: ast.Assign, nome: str) -> bool:
    return any(isinstance(alvo, ast.Name) and alvo.id == nome for alvo in no.targets)


def _texto_constante(no: ast.expr | None) -> str | None:
    if isinstance(no, ast.Constant) and isinstance(no.value, str):
        return no.value
    return None


def _nota_das_rotas(fontes: Fontes, arvores: dict[str, ast.Module]) -> Nota:
    rotas = []
    for arquivo in fontes.codigo:
        arvore = arvores[arquivo.caminho]
        prefixos: dict[str, str] = {}
        for no in ast.walk(arvore):
            if (
                isinstance(no, ast.Assign)
                and isinstance(no.value, ast.Call)
                and isinstance(no.value.func, ast.Name)
                and no.value.func.id == "APIRouter"
            ):
                prefixo = next(
                    (_texto_constante(k.value) for k in no.value.keywords if k.arg == "prefix"),
                    None,
                )
                for alvo in no.targets:
                    if isinstance(alvo, ast.Name):
                        prefixos[alvo.id] = prefixo or ""
        for funcao in _funcoes(arvore):
            for decorador in funcao.decorator_list:
                if not (
                    isinstance(decorador, ast.Call)
                    and isinstance(decorador.func, ast.Attribute)
                    and decorador.func.attr in _METODOS_HTTP
                    and isinstance(decorador.func.value, ast.Name)
                ):
                    continue
                caminho = _texto_constante(decorador.args[0]) if decorador.args else None
                if caminho is None:
                    continue
                endereco = prefixos.get(decorador.func.value.id, "") + caminho
                rotas.append(
                    (
                        endereco,
                        _METODOS_HTTP.index(decorador.func.attr),
                        f"| `{endereco}` | {decorador.func.attr.upper()} | `{funcao.name}` "
                        f"| [[{arquivo.pacote}]] | {_celula(_resumo(ast.get_docstring(funcao)))} |",
                    )
                )
    rotas.sort(key=lambda rota: (rota[0], rota[1]))
    return _nota_de_codigo(
        "Rotas",
        "nuvem/src/",
        [
            "# Rotas",
            "",
            "Os endereços da API e das telas, lidos dos decoradores (`@roteador.get(...)`) com o "
            "prefixo do `APIRouter` de cada módulo.",
            "",
            "| Endereço | Método | Função | Pacote | O que faz |",
            "|---|---|---|---|---|",
            *(rota[2] for rota in rotas),
        ],
    )


def _nota_das_tabelas(fontes: Fontes, arvores: dict[str, ast.Module]) -> Nota:
    tabelas = []
    for arquivo in fontes.codigo:
        for no in ast.walk(arvores[arquivo.caminho]):
            if not isinstance(no, ast.ClassDef):
                continue
            nome = next(
                (
                    _texto_constante(item.value)
                    for item in no.body
                    if isinstance(item, ast.Assign) and _atribui(item, "__tablename__")
                ),
                None,
            )
            if nome is None:
                continue
            colunas = [
                item.target.id
                for item in no.body
                if isinstance(item, ast.AnnAssign)
                and isinstance(item.target, ast.Name)
                and ast.unparse(item.annotation).startswith("Mapped[")
            ]
            tabelas.append(
                (
                    nome,
                    f"| `{nome}` | `{no.name}` | [[{arquivo.pacote}]] | {', '.join(colunas)} "
                    f"| {_celula(_resumo(ast.get_docstring(no)))} |",
                )
            )
    tabelas.sort()
    return _nota_de_codigo(
        "Tabelas do banco",
        "nuvem/src/",
        [
            "# Tabelas do banco",
            "",
            "As tabelas do PostgreSQL, lidas dos modelos do SQLAlchemy (`__tablename__`), com as "
            "colunas na ordem do modelo. As garantias da separação por empresa estão na "
            "[[5.5 Garantias|seção 5.5]] do SDD.",
            "",
            "| Tabela | Classe | Pacote | Colunas | O que guarda |",
            "|---|---|---|---|---|",
            *(tabela[1] for tabela in tabelas),
        ],
    )


def _nota_das_migracoes(fontes: Fontes) -> Nota:
    linhas = []
    for caminho, texto in fontes.migracoes.items():
        documentacao = ast.get_docstring(ast.parse(texto)) or ""
        criada = re.search(r"^Criada em:\s*(\S+)", documentacao, re.MULTILINE)
        revisao = posixpath.basename(caminho).split("_", 1)[0]
        primeira = documentacao.split("\n", 1)[0]
        data = criada.group(1) if criada else ""
        linhas.append(f"| `{revisao}` | {_celula(primeira)} | {data} |")
    return _nota_de_codigo(
        "Migrações do banco",
        f"{PASTA_DAS_MIGRACOES}/",
        [
            "# Migrações do banco",
            "",
            f"As migrações do Alembic, em ordem, de `{PASTA_DAS_MIGRACOES}/`. Modelo novo ou "
            "alterado pede migração nova (veja o [[CLAUDE - regras do repositório]]).",
            "",
            "| Revisão | O que muda | Criada em |",
            "|---|---|---|",
            *linhas,
        ],
    )


def _nota_das_telas(fontes: Fontes, arvores: dict[str, ast.Module]) -> Nota:
    mostradas: dict[str, set[str]] = defaultdict(set)
    for arquivo in fontes.codigo:
        arvore = arvores[arquivo.caminho]
        for funcao in (n for n in arvore.body if isinstance(n, ast.FunctionDef)):
            for no in ast.walk(funcao):
                texto = _texto_constante(no) if isinstance(no, ast.expr) else None
                if texto in fontes.telas:
                    mostradas[texto].add(f"{arquivo.modulo}.{funcao.name}")
    linhas = []
    for tela, texto in sorted(fontes.telas.items()):
        estende = [alvo for tipo, alvo in _INCLUSAO.findall(texto) if tipo == "extends"]
        inclui = sorted({alvo for tipo, alvo in _INCLUSAO.findall(texto) if tipo == "include"})
        celulas = [
            ", ".join(f"`{f}`" for f in sorted(mostradas[tela])),
            ", ".join(f"`{e}`" for e in estende),
            ", ".join(f"`{i}`" for i in inclui),
        ]
        linhas.append(f"| `{tela}` | " + " | ".join(celulas) + " |")
    return _nota_de_codigo(
        "Telas do painel",
        f"{PASTA_DAS_TELAS}/",
        [
            "# Telas do painel",
            "",
            f"Os arquivos Jinja de `{PASTA_DAS_TELAS}/`, a função que mostra cada um e de quem "
            "ele herda ou o que inclui. O que cada tela mostra está na "
            "[[6.2 Telas do MVP|seção 6.2]] do SDD.",
            "",
            "| Tela | Mostrada por | Estende | Inclui |",
            "|---|---|---|---|",
            *linhas,
        ],
    )


def _nota_dos_comandos(fontes: Fontes, arvores: dict[str, ast.Module]) -> Nota:
    linhas = []
    for arquivo in fontes.codigo:
        if arquivo.modulo != MODULO_DOS_COMANDOS:
            continue
        arvore = arvores[arquivo.caminho]
        etapas = {
            funcao.name.removeprefix("etapas_do_"): _resumo(ast.get_docstring(funcao))
            for funcao in _funcoes(arvore)
        }
        for no in ast.walk(arvore):
            if not (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and no.func.attr == "add_parser"
                and no.args
            ):
                continue
            nome = _texto_constante(no.args[0])
            ajuda = next((_texto_constante(k.value) for k in no.keywords if k.arg == "help"), "")
            if nome:
                linhas.append(
                    f"| `uv run tarefas {nome}` | {_celula(ajuda or '')} "
                    f"| {_celula(etapas.get(nome, ''))} |"
                )
    return _nota_de_codigo(
        "Comandos",
        "ferramentas/src/tarefas/comandos.py",
        [
            "# Comandos",
            "",
            "Os comandos do dia a dia, lidos de `ferramentas/src/tarefas/comandos.py`. Funcionam "
            "igual em Windows, Linux e Mac.",
            "",
            "| Comando | Para quê | O que roda |",
            "|---|---|---|",
            *linhas,
        ],
    )


# --- O vault ----------------------------------------------------------------------------------


def ligacoes(texto: str) -> list[str]:
    """As notas para onde o texto liga (``[[nota]]``), fora do código, que o Obsidian não liga."""
    linhas = []
    em_bloco = False
    for linha in texto.split("\n"):
        if linha.lstrip().startswith("```"):
            em_bloco = not em_bloco
        elif not em_bloco:
            linhas.append(_CRASE.sub("", linha))
    return _ALVO_DA_LIGACAO.findall("\n".join(linhas))


def _citacoes(notas: Sequence[Nota], ligadas: dict[str, str]) -> dict[str, list[str]]:
    citaveis = {nota.nome: nota for nota in notas if nota.citavel}
    citacoes: dict[str, set[str]] = defaultdict(set)
    for nota in notas:
        for alvo in ligacoes(ligadas[nota.nome]):
            if alvo in citaveis and alvo != nota.nome and citaveis[alvo].pai != nota.nome:
                citacoes[alvo].add(nota.nome)
    return {alvo: sorted(nomes, key=_chave_natural) for alvo, nomes in citacoes.items()}


def montar(fontes: Fontes) -> dict[str, bytes]:
    """Monta o vault: caminho de cada arquivo gerado (relativo ao vault) -> conteúdo.

    Raises:
        ValueError: se duas notas saírem com o mesmo nome (o Obsidian liga pelo nome).
    """
    preambulo, secoes = _secoes_do_sdd(fontes.sdd)
    notas = _notas_do_sdd(preambulo, secoes)
    documentos = {ARQUIVO_DO_SDD: "SDD"}
    for caminho, texto in fontes.planos.items():
        notas += _notas_do_plano(caminho, texto)
        documentos[caminho] = _nome_do_plano(caminho, texto)
    anexos: dict[str, str] = {}
    for caminho, texto in fontes.documentos.items():
        nome = _nome_do_documento(caminho, texto, fontes.nomes_dos_documentos)
        documentos[caminho] = nome
        pasta = posixpath.dirname(caminho)
        for imagem in _IMAGEM.findall(texto):
            citada = posixpath.normpath(posixpath.join(pasta, imagem))
            if citada in fontes.imagens:
                anexos[citada] = posixpath.basename(citada)
        notas.append(
            Nota(
                pasta="Documentos",
                nome=nome,
                tipo="documento",
                fonte=caminho,
                corpo=texto,
                pasta_da_fonte=pasta,
                tags=("documento",),
            )
        )
    notas += _notas_do_codigo(fontes)

    com_nota = {nota.nome for nota in notas if nota.citavel}
    citados = set(_ABERTO.findall("\n".join(nota.corpo for nota in notas)))
    for identificador in sorted(citados - com_nota, key=_chave_natural):
        notas.append(_nota_do_aberto_fechado(identificador))

    nomes = [nota.nome for nota in notas] + list(anexos.values())
    repetidos = sorted({nome for nome in nomes if nomes.count(nome) > 1})
    if repetidos:
        raise ValueError(f"notas com o mesmo nome: {', '.join(repetidos)}")

    indice = Indice(
        ids=frozenset(nota.nome for nota in notas if nota.citavel),
        secoes={s.numero: s.nome for s in secoes if s.numero},
        documentos=documentos,
        anexos=anexos,
    )
    ligadas = {
        nota.nome: ligar(
            nota.corpo,
            indice,
            pasta=nota.pasta_da_fonte,
            secoes_do_sdd=nota.secoes_do_sdd,
            propria=nota.nome,
        )
        for nota in notas
    }
    citacoes = _citacoes(notas, ligadas)
    arquivos = {
        nota.caminho: _texto_da_nota(nota, ligadas[nota.nome], citacoes.get(nota.nome, [])).encode(
            "utf-8"
        )
        for nota in notas
    }
    for caminho, nome in sorted(anexos.items()):
        arquivos[f"Anexos/{nome}"] = fontes.imagens[caminho]
    return arquivos


def gerar(raiz: Path) -> dict[str, bytes]:
    """Lê o repositório em ``raiz`` e monta o vault (sem escrever nada)."""
    return montar(ler_fontes(raiz))


def _gerados_no_disco(vault: Path) -> dict[str, Path]:
    achados = {}
    for pasta in PASTAS_GERADAS:
        if (vault / pasta).is_dir():
            for arquivo in (vault / pasta).rglob("*"):
                if arquivo.is_file():
                    achados[arquivo.relative_to(vault).as_posix()] = arquivo
    return achados


def diferencas(raiz: Path, arquivos: dict[str, bytes]) -> list[str]:
    """Compara as pastas geradas do vault em ``raiz`` com ``arquivos``.

    Returns:
        Uma linha por arquivo que falta, sobra ou está diferente; vazia se o vault está em dia.
    """
    no_disco = _gerados_no_disco(raiz / PASTA_DO_VAULT)
    problemas = []
    for caminho in sorted(arquivos.keys() - no_disco.keys()):
        problemas.append(f"falta: {caminho}")
    for caminho in sorted(no_disco.keys() - arquivos.keys()):
        problemas.append(f"sobra: {caminho}")
    for caminho in sorted(arquivos.keys() & no_disco.keys()):
        conteudo = no_disco[caminho].read_bytes()
        if caminho.endswith(".md"):
            conteudo = conteudo.replace(b"\r\n", b"\n")
        if conteudo != arquivos[caminho]:
            problemas.append(f"diferente: {caminho}")
    return problemas


def escrever(raiz: Path, arquivos: dict[str, bytes]) -> None:
    """Grava ``arquivos`` no vault e apaga das pastas geradas o que não está neles."""
    vault = raiz / PASTA_DO_VAULT
    for caminho, arquivo in _gerados_no_disco(vault).items():
        if caminho not in arquivos:
            arquivo.unlink()
    for caminho, conteudo in arquivos.items():
        destino = vault / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        if not destino.is_file() or destino.read_bytes() != conteudo:
            destino.write_bytes(conteudo)
    for pasta in PASTAS_GERADAS:
        for sub in sorted((vault / pasta).rglob("*"), reverse=True):
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()


def principal(argumentos: Sequence[str] | None = None) -> int:
    """Ponto de entrada de ``python -m tarefas.conhecimento``."""
    interpretador = argparse.ArgumentParser(
        prog="python -m tarefas.conhecimento",
        description="Gera o vault do Obsidian (knowledge/) a partir de docs/ e do código.",
    )
    interpretador.add_argument(
        "--conferir", action="store_true", help="só confere se o vault está em dia; não grava"
    )
    opcoes = interpretador.parse_args(argumentos)
    raiz = encontrar_raiz(Path.cwd())
    arquivos = gerar(raiz)
    if opcoes.conferir:
        problemas = diferencas(raiz, arquivos)
        for problema in problemas:
            print(problema)
        print(f"vault desatualizado: rode `{COMANDO}`" if problemas else "vault em dia")
        return 1 if problemas else 0
    escrever(raiz, arquivos)
    print(f"{len(arquivos)} arquivos gerados em {PASTA_DO_VAULT}/")
    return 0


if __name__ == "__main__":
    sys.exit(principal())

---
tipo: "pacote"
fonte: "ferramentas/src/tarefas/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `ferramentas/src/tarefas/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# tarefas

Pasta `ferramentas/src/tarefas/`.

Comandos do dia a dia do projeto, iguais em qualquer sistema operacional.

## Módulos

### `tarefas.__main__`

`ferramentas/src/tarefas/__main__.py`

Permite rodar também como ``python -m tarefas``.

### `tarefas.comandos`

`ferramentas/src/tarefas/comandos.py`

Comandos do dia a dia do projeto: ``uv run tarefas <comando>``.

Cada comando é uma sequência de etapas (programas externos) que roda na raiz do repositório
e para na primeira falha. As ferramentas são chamadas como ``python -m <ferramenta>`` com o
mesmo Python do ambiente, o que funciona igual em Windows, Linux e Mac.

Novos comandos entram junto com a tarefa que cria o que eles executam.

- **`MARCA_DO_WORKSPACE`** = `'[tool.uv.workspace]'`: Trecho que só aparece no pyproject.toml da raiz do repositório.
- **`ARQUIVO_COMPOSE`** = `'infra/docker-compose.yml'`: Serviços do ambiente local, relativos à raiz do repositório.
- **`ARQUIVO_ALEMBIC`** = `'nuvem/alembic.ini'`: Configuração das migrações da nuvem, relativa à raiz do repositório.
- **`CODIGO_PROGRAMA_NAO_ENCONTRADO`** = `127`: Mesmo código que o shell devolve quando o programa não existe.
- **`Executor`** = `Callable[[Sequence[str], Path], int]`: Roda um programa (argumentos) numa pasta e devolve o código de saída.
- **`RaizNaoEncontradaError`** (classe): Nenhuma pasta acima do ponto de partida é a raiz do repositório.
- **`ProgramaNaoEncontradoError`** (classe): O programa de uma etapa não está instalado (ex.: o docker).
- **`Etapa`** (classe): Um programa a rodar, com um nome curto para o relatório.
- **`etapas_do_check`**: Devolve as verificações completas: estilo, formato, tipos e testes, nessa ordem.
- **`etapas_do_up`**: Devolve a etapa que reconstrói a API, sobe os serviços locais e espera ficarem saudáveis.
- **`etapas_do_down`**: Devolve a etapa que derruba os serviços locais, mantendo os dados do banco.
- **`etapas_do_migrar`**: Devolve a etapa que aplica as migrações da nuvem no banco de ``PATIO_URL_BANCO``.
- **`etapas_do_semente`**: Devolve a etapa que grava os dados de demonstração no banco de ``PATIO_URL_BANCO``.
- **`etapas_do_demonstracao`**: Devolve a etapa que cria a empresa de demonstração no banco de desenvolvimento ([[D-49]]).
- **`etapas_do_treino`**: Monta a pasta da base de treino em ``dados/treino`` ([[D-71]]).
- **`etapas_do_conhecimento`**: Devolve a etapa que gera o vault do Obsidian (``knowledge/``) de docs/ e do código.
- **`etapas_do_modelos`**: Devolve a etapa que baixa os modelos do leitor v0 para ``modelos/v0`` (fora do Git).
- **`etapas_do_demo`**: Devolve a demonstração: sobe tudo, migra, semeia e roda o simulador.
- **`etapas_do_test`**: Devolve só a etapa de testes, repassando ``extras`` ao pytest (ex.: ``-k placa``).
- **`encontrar_raiz`**: Sobe a partir de ``partida`` até a pasta cujo pyproject.toml declara o workspace.
- **`executar_etapas`**: Roda as etapas em ordem dentro de ``raiz`` e para na primeira que falhar.
- **`executar_processo`**: Executor real: roda o programa em ``raiz`` mostrando a saída dele no terminal.
- **`principal`**: Ponto de entrada do comando ``tarefas``.

### `tarefas.conhecimento`

`ferramentas/src/tarefas/conhecimento.py`

O vault do Obsidian em ``knowledge/``: as notas geradas de ``docs/`` e do código.

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

- **`PASTA_DO_VAULT`** = `'knowledge'`: O vault, relativo à raiz do repositório.
- **`PASTAS_GERADAS`**: Pastas do vault que o gerador reescreve inteiras; o resto do vault é escrito à mão.
- **`NOMES_DOS_DOCUMENTOS`**: Nome no vault dos documentos fora do SDD e dos planos.
- **`ArquivoDeCodigo`** (classe): Um arquivo ``.py`` do ``src/`` de um pacote do workspace.
- **`ArquivoDeTeste`** (classe): Um arquivo de teste (``tests/test_*.py``) de um pacote do workspace.
- **`Fontes`** (classe): Tudo o que o gerador lê do repositório, já em memória (os testes montam à mão).
- **`ler_fontes`**: Lê do repositório os documentos, o código, as telas e as migrações.
- **`Nota`** (classe): Uma nota do vault, antes de virar texto.
- **`Indice`** (classe): O que pode virar ligação, e o nome da nota de cada coisa.
- **`nome_de_nota`**: Tira do título o que o Obsidian (e o Windows) não aceita em nome de arquivo.
- **`ligar`**: Troca as referências do texto por ligações do Obsidian.
- **`ligacoes`**: As notas para onde o texto liga (``[[nota]]``), fora do código, que o Obsidian não liga.
- **`montar`**: Monta o vault: caminho de cada arquivo gerado (relativo ao vault) -> conteúdo.
- **`gerar`**: Lê o repositório em ``raiz`` e monta o vault (sem escrever nada).
- **`diferencas`**: Compara as pastas geradas do vault em ``raiz`` com ``arquivos``.
- **`escrever`**: Grava ``arquivos`` no vault e apaga das pastas geradas o que não está neles.
- **`principal`**: Ponto de entrada de ``python -m tarefas.conhecimento``.

## Testes

- `ferramentas/tests/test_tarefas_comandos.py`: Comportamento dos comandos do projeto (`uv run tarefas ...`).
- `ferramentas/tests/test_tarefas_conhecimento.py`: O vault do Obsidian em ``knowledge/``: o gerador e a conferência do vault no Git.
- `ferramentas/tests/test_tarefas_pacote.py`: O pacote tarefas é instalado pelo workspace do projeto.

---

Do [[Mapa do código]].

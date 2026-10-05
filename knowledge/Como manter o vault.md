---
tipo: "mapa"
escrita: "à mão"
atualizada: "2026-10-05"
tags: [inicio]
---

# Como manter o vault

A verdade continua em `docs/` e no código ([[CLAUDE - regras do repositório]], "Onde está a
verdade"). O vault é a mesma documentação, dividida em notas e ligada; ele é gerado de lá.

## A regra

- **Mudou `docs/` ou o código? Rode `uv run tarefas conhecimento`** e mande as notas geradas no
  mesmo commit da mudança (a documentação no commit `docs:`, o código no dele).
- Um teste (`ferramentas/tests/test_tarefas_conhecimento.py`) confere que o vault no Git é igual
  ao que o gerador produz. Se alguém esquecer, o `uv run tarefas check` e a CI falham com o
  comando para corrigir.
- Para só conferir, sem gravar: `uv run python -m tarefas.conhecimento --conferir`.
- **Não edite as notas geradas:** a mudança some na próxima geração e o teste falha. Mude a
  fonte (o SDD, o plano, o docstring) e gere de novo.

## O que é gerado e o que é à mão

| Onde | Quem escreve | De onde vem |
|---|---|---|
| `SDD/`, `Decisões/`, `Itens em aberto/` | o gerador | `docs/SDD.md` |
| `Planos/`, `Tarefas/`, `Trilha não técnica/` | o gerador | `docs/planos/` |
| `Documentos/`, `Anexos/` | o gerador | os outros `.md` de `docs/`, o README, o CLAUDE.md e os avisos de terceiros |
| `Código/` | o gerador | os docstrings, os modelos, as rotas, as telas e as migrações |
| a raiz e `Temas/` | à mão | resumos e mapas |

O gerador está em `ferramentas/src/tarefas/conhecimento.py` (veja [[tarefas]]). Ele só usa a
biblioteca padrão do Python e lê o código sem importar nada.

## As notas à mão

- [[00 Início]], [[Estado atual]], [[Pendências do Lorenzo]] e os [[Licenças|temas]] são
  resumos: quando o projeto muda, atualize-os à mão (a data fica em `atualizada`, no topo).
- O [[Estado atual]] muda a cada PR que entra; os temas, quando entra uma decisão nova.
- Ligações para notas geradas usam o nome da nota: `[[D-45]]`, `[[T40]]`, `[[5.4 Contas do extrato]]`,
  `[[nuvem.extrato]]`. Um teste confere que toda ligação do vault aponta para uma nota que existe.

## Como as referências viram ligações

O gerador troca, nos documentos e nos docstrings:

| No texto | Vira |
|---|---|
| `D-45`, `T40`, `N16`, `[ABERTO-01]` | a nota da decisão, da tarefa, do item da trilha ou do item em aberto |
| "SDD 5.4", "SDD 5.1, 5.4 e 6.2", "SDD, seção 4" | a nota de cada seção |
| "seção 5.4" (só dentro do SDD) | a nota da seção |
| `docs/SDD.md`, `CLAUDE.md`... entre crases, e links relativos | a nota do documento |
| uma imagem citada | o arquivo em `Anexos/` |

Fora do SDD, "seção 2" fica como está: pode ser do próprio documento. Identificador sem nota
(como uma decisão que ainda não foi escrita) também fica como texto.

## Configuração do Obsidian

A pasta `.obsidian/` leva só o `app.json`: ligações no formato `[[nota]]`, ligações atualizadas
ao mudar o nome de uma nota e imagens novas em `Anexos/`. O resto (o estado da janela, o grafo,
os plugins de cada pessoa) fica fora do Git, pelo `.gitignore`.

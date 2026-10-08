---
tipo: "código"
fonte: "ferramentas/src/tarefas/comandos.py"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `ferramentas/src/tarefas/comandos.py` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Comandos

Os comandos do dia a dia, lidos de `ferramentas/src/tarefas/comandos.py`. Funcionam igual em Windows, Linux e Mac.

| Comando | Para quê | O que roda |
|---|---|---|
| `uv run tarefas check` | estilo, formato, tipos e testes | Devolve as verificações completas: estilo, formato, tipos e testes, nessa ordem. |
| `uv run tarefas test` | só os testes; o que vier depois vai para o pytest | Devolve só a etapa de testes, repassando ``extras`` ao pytest (ex.: ``-k placa``). |
| `uv run tarefas up` | sobe o ambiente local (bancos e API) e espera ficar pronto | Devolve a etapa que reconstrói a API, sobe os serviços locais e espera ficarem saudáveis. |
| `uv run tarefas down` | derruba o ambiente local, mantendo os dados | Devolve a etapa que derruba os serviços locais, mantendo os dados do banco. |
| `uv run tarefas migrar` | aplica as migrações da nuvem no banco de desenvolvimento | Devolve a etapa que aplica as migrações da nuvem no banco de ``PATIO_URL_BANCO``. |
| `uv run tarefas semente` | grava os dados de demonstração no banco de desenvolvimento | Devolve a etapa que grava os dados de demonstração no banco de ``PATIO_URL_BANCO``. |
| `uv run tarefas demonstracao` | cria a empresa de demonstração (um mês de histórico) no banco de desenvolvimento | Devolve a etapa que cria a empresa de demonstração no banco de desenvolvimento ([[D-49]]). |
| `uv run tarefas treino` | monta a pasta da base de treino (os rótulos revisados) em dados/treino | Monta a pasta da base de treino em ``dados/treino`` ([[D-71]]). |
| `uv run tarefas conhecimento` | gera as notas do vault do Obsidian (knowledge/) a partir de docs/ e do código | Devolve a etapa que gera o vault do Obsidian (``knowledge/``) de docs/ e do código. |
| `uv run tarefas modelos` | baixa os modelos do leitor v0 (conferindo o SHA-256) | Devolve a etapa que baixa os modelos do leitor v0 para ``modelos/v0`` (fora do Git). |
| `uv run tarefas demo` | demonstração: sobe tudo, semeia e manda passagens pelo simulador | Devolve a demonstração: sobe tudo, migra, semeia e roda o simulador. |

---

Do [[Mapa do código]].

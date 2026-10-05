# patio-br (nome provisório)

Sistema de pátio para sites logísticos de médio e alto volume no Brasil:

- **check-in automático por câmera**, sem aplicativo para o motorista;
- fila, chamada à doca e avisos pelo **WhatsApp**;
- **extrato mensal da economia** gerada, em R$;
- hardware barato: câmeras IP comuns e um mini PC na portaria.

## Comece por aqui

| Documento | O que tem |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | as regras que não se negociam e como uma mudança entra (vale para pessoas e para sessões com IA) |
| [`docs/SDD.md`](docs/SDD.md) | o desenho do MVP do piloto: escopo, arquitetura, leitor de placas, dados, aplicativo, infraestrutura, LGPD, testes, cronograma, decisões e itens em aberto |
| [`docs/planos/2026-10-plano-mes-1.md`](docs/planos/2026-10-plano-mes-1.md) | o plano de implementação do mês 1 (fundação), tarefa por tarefa |
| [`docs/planos/2026-11-plano-mes-2.md`](docs/planos/2026-11-plano-mes-2.md) | o plano do mês 2 (leitor próprio, agendamento e casamento) |
| [`docs/planos/2026-12-plano-mes-3.md`](docs/planos/2026-12-plano-mes-3.md) | o plano do mês 3: a demonstração comercial na internet |
| [`docs/validacao/relatorio-validacao-v3.md`](docs/validacao/relatorio-validacao-v3.md) | a validação de mercado que originou o projeto e o teste com comprador que o piloto precisa passar |
| [`docs/validacao/fatos-tecnicos-stack.md`](docs/validacao/fatos-tecnicos-stack.md) | licenças, preços e benchmarks usados nas escolhas técnicas (verificados em 2026-09-29) |
| `knowledge/` | o vault do Obsidian: toda a documentação em notas ligadas, o mapa do código, o estado atual e as pendências; abra a pasta no Obsidian e comece por `00 Início` |

## Ambiente de desenvolvimento

Precisa de **Python 3.12** e do [`uv`](https://docs.astral.sh/uv/). Funciona igual em Windows,
Linux e Mac.

O banco (PostgreSQL 16) e a API rodam no Docker: precisa também do
[Docker Desktop](https://www.docker.com/products/docker-desktop/) aberto.

Na primeira vez, copie `.env.exemplo` para `.env` (o Git ignora o `.env`; é ali que se muda
senha ou portas):

```bash
cp .env.exemplo .env         # no Windows (PowerShell): Copy-Item .env.exemplo .env
uv sync                      # cria o ambiente e instala todos os pacotes do projeto
```

No dia a dia:

```bash
uv run tarefas up            # sobe os bancos (15432 e 15433, o de testes), a API (18000) e o worker
uv run tarefas migrar        # aplica as migrações no banco de desenvolvimento
uv run tarefas semente       # grava os dados de demonstração (duas empresas inventadas)
uv run tarefas demonstracao  # a empresa de demonstração, com um mês de histórico (D-49)
uv run tarefas modelos       # baixa os modelos do leitor v0 para modelos/ (fora do Git)
uv run tarefas demo          # a demonstração do mês 1: sobe, semeia e manda passagens
uv run tarefas conhecimento  # gera o vault do Obsidian (knowledge/) de docs/ e do código
uv run tarefas check         # estilo, formato, tipos e testes (o mesmo que a CI vai rodar)
uv run tarefas test -k placa # só os testes; o que vier depois de `test` vai para o pytest
uv run tarefas down          # derruba; os dados do banco de desenvolvimento ficam guardados
```

### Windows com Controle de Aplicativo

Se o Windows bloqueia programas sem assinatura (Controle de Aplicativo), o venv precisa nascer
do Python oficial, que é assinado, e os comandos rodam pelo `python.exe` do venv:

```powershell
uv venv --python 3.12 --python-preference only-system
uv sync --frozen
Copy-Item .env.exemplo .env
.venv\Scripts\python.exe -m tarefas up
.venv\Scripts\python.exe -m tarefas check
```

- `--frozen` instala exatamente o `uv.lock`, sem reescrevê-lo (o uv da máquina pode ser de
  outra versão que a do projeto).
- Use sempre `.venv\Scripts\python.exe -m <comando>` (`tarefas`, `simulador`, `borda.caixa`): os
  executáveis `uv run tarefas` e `.venv\Scripts\tarefas.exe` também são bloqueados.
- Se a saída for longa, veja só o fim: `... -m tarefas check 2>&1 | Select-Object -Last 30`.

Os testes da nuvem usam o banco de testes: rode `tarefas up` antes do `check`. Com o ambiente
no ar, `http://localhost:18000/saude` responde `{"ok": true}` quando a API alcança o banco.

Depois do `migrar` e da `semente`, entre no painel em `http://localhost:18000/entrar` com
`gestor@empresa-a.example` e a senha `demonstracao-local` (a mesma para todas as pessoas da
demonstração; os e-mails estão em `nuvem/src/nuvem/semente.py`). A administração (nós) entra
com `admin@patio-br.example`. Com o porteiro (`porteiro@empresa-a.example`), a tela
`http://localhost:18000/portaria` mostra as passagens que chegam, atualizada a cada 2 segundos.

Para ver passagens chegando sem câmera, o simulador faz o papel da caixa de borda (ativa com a
administração da semente e manda três passagens inventadas):

```bash
uv run simulador --demonstracao --passagens amostra
```

A demonstração do mês 1 inteira, do zero, num comando só: `uv run tarefas demo` (passo a passo
em [`docs/guias/demo-mes-1.md`](docs/guias/demo-mes-1.md)).

O dia de demonstração (D-49): `uv run tarefas demonstracao` cria a "Distribuidora Exemplo
(demonstração)", com um mês de histórico (precisa da semente). Com a API e o worker rodando
(`python -m nuvem.worker`), entre como `gestor@demonstracao.example` (a senha da semente) e abra
"Dia de demonstração": a manhã aparece pronta e, nos 5 minutos seguintes, os caminhões chegam e o
líder automático trabalha.

Quando um PR acrescenta variável ao `.env.exemplo`, copie-o de novo para `.env`.

### A caixa de borda

Na caixa (o mini PC da portaria), o programa `caixa` lê as câmeras e manda as passagens:

```bash
uv run tarefas modelos                                   # os modelos do leitor v0, uma vez
uv run caixa ativar --nuvem https://<a nuvem> --codigo XXXX-XXXX-XXXX
uv run caixa rodar                                       # até Ctrl+C ou o sinal de término
```

O código de ativação é gerado pela administração para o site (vale 24 horas, uso único). A
chave fica em `dados/caixa/caixa.json` e a fila em `dados/caixa/fila.sqlite`, fora do Git.
Detalhes no SDD, seção 7.4.

A CI (`.github/workflows/ci.yml`) roda em cada PR e na `main`: o mesmo `tarefas check` (com o
banco de testes), a checagem de licenças das dependências, a de falhas de segurança conhecidas
e o `tarefas up` com a API construída, as migrações aplicadas e o `/saude` respondendo.

O repositório é um workspace `uv` com cinco pacotes: `contratos/`, `borda/`, `nuvem/`,
`ferramentas/` e `ml/` (ver `docs/SDD.md`, seção 6.3).

## Situação

SDD 0.37 aprovado como base. Mês 3 (a demonstração comercial na internet) em andamento, conforme
o plano; cada tarefa entra por um PR. O que já está pronto e o que falta:
`knowledge/Estado atual.md`.

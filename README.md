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
| [`docs/validacao/relatorio-validacao-v3.md`](docs/validacao/relatorio-validacao-v3.md) | a validação de mercado que originou o projeto e o teste com comprador que o piloto precisa passar |
| [`docs/validacao/fatos-tecnicos-stack.md`](docs/validacao/fatos-tecnicos-stack.md) | licenças, preços e benchmarks usados nas escolhas técnicas (verificados em 2026-09-29) |

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
uv run tarefas up            # sobe os bancos (15432 e 15433, o de testes) e a API (18000)
uv run tarefas migrar        # aplica as migrações no banco de desenvolvimento
uv run tarefas semente       # grava os dados de demonstração (duas empresas inventadas)
uv run tarefas check         # estilo, formato, tipos e testes (o mesmo que a CI vai rodar)
uv run tarefas test -k placa # só os testes; o que vier depois de `test` vai para o pytest
uv run tarefas down          # derruba; os dados do banco de desenvolvimento ficam guardados
```

Os testes da nuvem usam o banco de testes: rode `tarefas up` antes do `check`. Com o ambiente
no ar, `http://localhost:18000/saude` responde `{"ok": true}` quando a API alcança o banco.

Depois do `migrar` e da `semente`, entre no painel em `http://localhost:18000/entrar` com
`gestor@empresa-a.example` e a senha `demonstracao-local` (a mesma para todas as pessoas da
demonstração; os e-mails estão em `nuvem/src/nuvem/semente.py`). A administração (nós) entra
com `admin@patio-br.example`.

Quando um PR acrescenta variável ao `.env.exemplo`, copie-o de novo para `.env`.

A CI (`.github/workflows/ci.yml`) roda em cada PR e na `main`: o mesmo `tarefas check` (com o
banco de testes), a checagem de licenças das dependências, a de falhas de segurança conhecidas
e o `tarefas up` com a API construída, as migrações aplicadas e o `/saude` respondendo.

O repositório é um workspace `uv` com cinco pacotes: `contratos/`, `borda/`, `nuvem/`,
`ferramentas/` e `ml/` (ver `docs/SDD.md`, seção 6.3).

## Situação

SDD v0.5 aprovado como base. Mês 1 (fundação) em andamento, conforme o plano; cada tarefa entra por um PR.

# patio-br (nome provisório)

Sistema de pátio para sites logísticos de médio e alto volume no Brasil:

- **check-in automático por câmera**, sem aplicativo para o motorista;
- fila, chamada à doca e avisos pelo **WhatsApp**;
- **extrato mensal da economia** gerada, em R$;
- hardware barato: câmeras IP comuns e um mini PC na portaria.

## Comece por aqui

| Documento | O que tem |
|---|---|
| [`docs/SDD.md`](docs/SDD.md) | o desenho do MVP do piloto: escopo, arquitetura, leitor de placas, dados, aplicativo, infraestrutura, LGPD, testes, cronograma, decisões e itens em aberto |
| [`docs/planos/2026-10-plano-mes-1.md`](docs/planos/2026-10-plano-mes-1.md) | o plano de implementação do mês 1 (fundação), tarefa por tarefa |
| [`docs/validacao/relatorio-validacao-v3.md`](docs/validacao/relatorio-validacao-v3.md) | a validação de mercado que originou o projeto e o teste com comprador que o piloto precisa passar |
| [`docs/validacao/fatos-tecnicos-stack.md`](docs/validacao/fatos-tecnicos-stack.md) | licenças, preços e benchmarks usados nas escolhas técnicas (verificados em 2026-09-29) |

## Ambiente de desenvolvimento

Precisa de **Python 3.12** e do [`uv`](https://docs.astral.sh/uv/). Funciona igual em Windows,
Linux e Mac.

```bash
uv sync                      # cria o ambiente e instala todos os pacotes do projeto
uv run tarefas check         # estilo, formato, tipos e testes (o mesmo que a CI vai rodar)
uv run tarefas test -k placa # só os testes; o que vier depois de `test` vai para o pytest
```

O banco local (PostgreSQL 16) roda no Docker: precisa do
[Docker Desktop](https://www.docker.com/products/docker-desktop/) aberto. Para mudar senha ou
portas, copie `.env.exemplo` para `.env` (o Git ignora o `.env`).

```bash
uv run tarefas up            # sobe o banco de desenvolvimento (5432) e o de testes (5433)
uv run tarefas down          # derruba; os dados do banco de desenvolvimento ficam guardados
```

A CI (`.github/workflows/ci.yml`) roda em cada PR e na `main`: o mesmo `tarefas check`, a
checagem de licenças das dependências, a de falhas de segurança conhecidas e o `tarefas up`
com os dois bancos respondendo.

O repositório é um workspace `uv` com cinco pacotes: `contratos/`, `borda/`, `nuvem/`,
`ferramentas/` e `ml/` (ver `docs/SDD.md`, seção 6.3).

## Situação

SDD v0.2 aprovado como base. Mês 1 (fundação) em andamento, conforme o plano; cada tarefa entra por um PR.

# patio-br — orientação para quem trabalha neste repositório

Leia este arquivo antes de mudar qualquer coisa. Ele diz onde está a verdade do projeto, o que
nunca pode acontecer aqui e como uma mudança entra.

## O que é

Sistema de pátio para sites logísticos: câmera na portaria lê a placa, o caminhão entra na fila
sem aplicativo, o motorista é avisado pelo WhatsApp e o cliente recebe um extrato mensal da
economia em R$. Uma caixa de borda (mini PC) lê as placas; a nuvem decide.

## Onde está a verdade

| Arquivo | Para quê |
|---|---|
| `docs/SDD.md` | **a fonte da verdade**: o que construir, como as peças se encaixam e por quê |
| `docs/planos/` | o plano do mês em curso, tarefa por tarefa |
| `README.md` | instalação e comandos |

- Tudo o que for construído precisa caber no SDD. Se não couber, **o SDD muda primeiro**
  (seção 0), com o motivo registrado na seção 11.
- Um item marcado `[ABERTO-nn]` (seção 12) **não se resolve no código**: pergunte antes.
- Um desvio do plano fica registrado no próprio plano (riscado, com a tarefa para onde foi) e
  explicado no PR.

## Regras que não se negociam

1. **Só licença permissiva.**
   - Dependências: MIT, BSD, Apache, ISC, PSF ou PostgreSQL. MPL-2.0 só para biblioteca usada
     sem modificação. GPL, LGPL e AGPL nunca (SDD 6.1). A CI checa as dependências Python.
   - Bibliotecas nativas dentro das rodas (SDD D-27): LGPL só usada sem modificação e carregada
     dinamicamente; GPL só com a exceção de runtime do GCC; FFmpeg só sem partes GPL (o PyAV do
     PyPI não entra). A CI não as vê: ao acrescentar uma dependência, confira a roda e anote os
     créditos que a licença pedir em `borda/AVISOS-DE-TERCEIROS.md`.
   - Modelos de visão: só código Apache, MIT ou BSD e **pesos treinados por nós** (SDD 4.1).
     O YOLO da Ultralytics (AGPL) não entra. O banco RodoSol-ALPR é só acadêmico: nunca treina
     o produto (SDD 4.6). Pesos de terceiros só para comparar modelos e avaliar internamente
     (SDD D-26). A CI não vê modelos; essa checagem é sua.
   - Arquivos de terceiros do painel (ex.: o HTMX) ficam em `nuvem/src/nuvem/web/estatico/`,
     com licença e hash no `LEIA-ME.md` de lá (SDD 6.1). A CI também não os vê.
2. **LGPD** (SDD 8.3). Sem reconhecimento facial. Foto guardada é recorte de placa e de
   veículo; rostos nas fotos de contexto são borrados na própria caixa. A base de treino guarda
   só recortes de placa e a região de gravação das câmeras (abaixo do para-brisa, SDD D-39).
3. **Dado real nunca entra no Git.** Vídeos, fotos, placas, nomes e telefones reais ficam em
   `dados/`; pesos de modelos ficam em `modelos/`. As duas pastas são ignoradas. Nem em teste,
   nem em fixture, nem em mensagem de commit: os testes usam dados inventados.
4. **Nenhum segredo no repositório.** O `.env` é ignorado; o `.env.exemplo` só tem valores de
   exemplo do ambiente local.
5. **As garantias do SDD 5.5 valem para todo código da nuvem:** passagem repetida é ignorada;
   horário e foto não se editam (correção é um evento novo); nenhuma consulta sem filtro de
   empresa. Na prática: toda leitura de dado do cliente recebe o `Acesso` de quem pede
   (`nuvem.cadastro.acesso`); toda tabela de cliente tem `empresa_id`, e cada filha aponta para
   o pai pela dupla (pai, empresa); o que é de outra empresa responde "não encontrado".
   Nas rotas: `obter_acesso` (qualquer usuário do cliente) ou `exigir_papel(...)`; sem login,
   401; papel errado, 403. A administração (nós) é outra tabela e outro tipo, `AcessoAdmin`
   (`obter_acesso_admin`), e não usa as rotas do cliente (SDD D-19). A caixa de borda se
   identifica pela chave (`nuvem.frota.acesso.obter_caixa`) e só lê e grava no site dela.
6. **Senha, PIN e código de sessão só como resumo** (`nuvem.senhas`, argon2; SDD 8.2). Nunca o
   texto, nem em registro de erro.

## Como trabalhar

Python 3.12, [`uv`](https://docs.astral.sh/uv/) e Docker Desktop. Os comandos do projeto são
Python puro e funcionam igual em Windows, Linux e Mac:

```bash
uv sync                      # instala o ambiente (antes, na primeira vez: .env.exemplo → .env)
uv run tarefas up            # sobe os bancos (desenvolvimento e testes) e a API, no Docker
uv run tarefas migrar        # aplica as migrações no banco de desenvolvimento
uv run tarefas semente       # grava os dados de demonstração (duas empresas inventadas)
uv run tarefas demonstracao  # a empresa de demonstração, com um mês de histórico (D-49)
uv run tarefas modelos       # baixa os pesos do leitor v0 para modelos/ (SHA-256 conferido)
uv run tarefas demo          # a demonstração do mês 1 (docs/guias/demo-mes-1.md)
uv run tarefas check         # estilo, formato, tipos e testes (o mesmo que a CI roda)
uv run tarefas test -k placa # só os testes; o resto vai para o pytest
uv run tarefas down          # derruba, mantendo os dados
```

Os testes da nuvem usam o banco de testes do `tarefas up`, zerado e migrado do zero a cada
rodada; cada teste roda numa transação desfeita no fim (fixture `sessao`). A fixture `cenario`
grava os dados de demonstração (`nuvem.semente`): duas empresas, para testar a separação.
Nos testes de rota, a fixture `entrar` entra pela tela de login, como uma pessoa, e cada
requisição usa a própria sessão do banco: o que a rota grava sem `commit` se perde, como em
produção.
Modelo novo ou alterado pede migração nova (`alembic revision --autogenerate`, ver
`nuvem/alembic.ini`); um teste falha se faltar. Com o pg8000, violação de chave estrangeira ou
de CHECK chega como `ProgrammingError`, não `IntegrityError`: use `nuvem.banco.sqlstate`.

- **Uma tarefa = uma branch = um PR** para a `main` (ex.: `mes1/t06-contratos`). O PR só entra
  com a CI verde.
- **Teste primeiro nas regras com lógica** (formato de placa, votação, composição, separação de
  clientes, envio repetido): escreva o teste, veja-o falhar, depois escreva o código.
- **Testes:** cada pacote tem sua pasta `tests/`. O nome do arquivo é único no repositório e
  leva o pacote na frente (`test_borda_composicao.py`); o `pyproject.toml` explica por quê.
  Teste que usa banco, rede ou disco leva `@pytest.mark.integracao`.
- **Comando novo** entra em `ferramentas/src/tarefas/comandos.py`, junto com a tarefa que cria o
  que ele executa. Nada de script `.sh` ou `.ps1` para o dia a dia.
- **Dependência nova:** confira a licença antes; `uv add` no pacote que a usa; o `uv.lock` vai no
  mesmo commit.
- **Commits** curtos, em português, com prefixo (`feat:`, `fix:`, `test:`, `docs:`, `ci:`,
  `infra:`, `chore:`). Código e documentação em commits separados.
- **Linguagem simples** em código, comentários e documentos, em português. Termo técnico
  inevitável vai para o glossário do SDD (seção 13).

Antes de abrir o PR: `uv run tarefas check` passa; se mexeu em `infra/`, `tarefas up` e
`tarefas down` também.

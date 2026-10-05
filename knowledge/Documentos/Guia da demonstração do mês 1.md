---
tipo: "documento"
fonte: "docs/guias/demo-mes-1.md"
gerada: true
tags: [documento]
---

> [!note] Gerada de `docs/guias/demo-mes-1.md` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Demonstração do mês 1

O marco do mês (plano do mês 1, seção 1): uma passagem sai da caixa de borda, chega à API e
**aparece na tela da portaria** com foto, placa e confiança.

Hoje a demonstração usa o **simulador** no papel da caixa, com uma amostra de passagens
inventadas (placas inventadas e fotos de placa desenhadas). Com vídeo gravado de verdade, ela
depende de duas coisas que ainda faltam (ver o fim deste guia).

Desde o mês 2, a demonstração também **sobe agendamentos** e mostra o **casamento** ([[5.3 Casamento da chegada com o agendamento|SDD 5.3]]):
check-in automático, exceção com os candidatos e saída.

![[demo-mes-2.png]]

## O que precisa estar instalado

- Git;
- Python 3.12;
- [`uv`](https://docs.astral.sh/uv/);
- [Docker Desktop](https://www.docker.com/products/docker-desktop/), **aberto**.

## Do zero

1. **Baixe o projeto** (o repositório é privado: o Git pode abrir o navegador para você entrar no
   GitHub):

   ```bash
   git clone https://github.com/lorenzo265/patio-br.git
   cd patio-br
   ```

2. **Monte o ambiente Python.**

   - Linux e Mac: `uv sync`.
   - Windows: os mesmos passos do README, seção "Windows com Controle de Aplicativo" (o venv
     a partir do Python oficial e `uv sync --frozen`).

3. **Copie a configuração local** (o Git ignora o `.env`):

   ```bash
   cp .env.exemplo .env          # Windows (PowerShell): Copy-Item .env.exemplo .env
   ```

4. **Rode a demonstração:**

   ```bash
   uv run tarefas demo           # Windows: .venv\Scripts\python.exe -m tarefas demo
   ```

   Ela faz, em ordem:

   1. sobe o banco, a API e o worker no Docker;
   2. aplica as migrações;
   3. grava as duas empresas de demonstração;
   4. o simulador ativa uma caixa com a administração da semente, sobe quatro agendamentos como o
      gestor (pela planilha, com as janelas em volta da hora atual) e manda cinco passagens;
   5. o worker casa cada passagem com os agendamentos, em segundo plano.

   O fim da saída fica assim:

   ```text
   4 agendamentos: 4 novos, 0 alterados, 0 iguais
   5 passagens guardadas na fila da caixa
   5 enviadas; 0 recusadas pela nuvem; 0 na fila
   veja em http://localhost:18000/portaria (entre com porteiro@empresa-a.example e a senha demonstracao-local)
   e os agendamentos em http://localhost:18000/agendamentos (entre com gestor@empresa-a.example)
   ok
   ```

5. **Abra a tela da portaria:** <http://localhost:18000/portaria>, com o e-mail
   `porteiro@empresa-a.example` e a senha `demonstracao-local`. Aparecem as cinco passagens da
   amostra, cada uma com o resultado do casamento:

   - um cavalo com reboque (`ABC1D23` + `XYZ9876`): **check-in** no agendamento dele;
   - um cavalo (`BRA2E19`) com dois agendamentos perto da hora: **exceção**, com os dois
     candidatos e os pontos (80 e 70) no cartão de cima;
   - uma passagem sem placa lida: **exceção**;
   - um cavalo (`CDE3F45`) que faz **check-in** e depois **sai**: a câmera traseira da saída lê a
     placa do reboque (`FGH6I78`), que o agendamento trazia e a entrada não viu.

   A tela se atualiza sozinha a cada 2 segundos. Os agendamentos ficam em
   <http://localhost:18000/agendamentos>, com o e-mail `gestor@empresa-a.example`.

6. **Confira uma placa:** na coluna "Conferência", clique em **conferir**. A página mostra a foto
   de cada placa ao lado do que o leitor leu. **Está certa** confirma; para corrigir, digite a
   placa da foto e clique em **Corrigir**. De volta à portaria, a lista mostra "placa certa" ou
   "corrigida: ..." (SDD [[D-42]]).

## Ver passagens chegando com a tela aberta

Com a tela aberta, rode o simulador de novo noutro terminal:

```bash
uv run simulador --passagens amostra    # Windows: .venv\Scripts\python.exe -m simulador --passagens amostra
```

Em até uns 2 segundos, mais cinco passagens aparecem no topo; sem agendamentos novos, as
entradas viram exceção. Para repetir também os agendamentos (com códigos novos), use
`uv run simulador --demonstracao --agendamentos amostra --passagens amostra`. O simulador usa a
caixa que a demonstração ativou: a chave fica em `dados/simulador/caixa.json`, fora do Git.

Para mandar passagens suas, escreva um arquivo JSON no formato da amostra
(`ferramentas/src/simulador/amostra.json`) e use `--passagens meu-arquivo.json`. A faixa de
saída fica assim: `--faixa saida-1`, ou `"sentido": "saida"` na própria passagem. Os
agendamentos seguem o formato de `ferramentas/src/simulador/amostra_agendamentos.json` (janelas
em minutos a partir de agora).

## Com um vídeo gravado (leitor v0)

O leitor v0 usa pesos de terceiros: **só para avaliação interna** ([[4.1 Regra de licença|SDD 4.1]] e [[D-26]]; licenças em
[[Validação - fatos técnicos da stack|docs/validacao/fatos-tecnicos-stack.md]]). Nas conversas comerciais, use a amostra acima.

1. Baixe os modelos uma vez: `uv run tarefas modelos`. Eles ficam em `modelos/v0`, fora do Git.
2. Ponha o vídeo dentro de `dados/` (fora do Git), ex.: `dados/amostras/portaria-1.mp4`.
3. Rode o simulador sobre o vídeo:

   ```bash
   uv run simulador --video dados/amostras/portaria-1.mp4 --faixa entrada-1 --camera frente
   # Windows: .venv\Scripts\python.exe -m simulador --video dados\amostras\portaria-1.mp4 --faixa entrada-1 --camera frente
   ```

   Os quadros de um vídeo numa pasta, como imagens numeradas, também servem: `--quadros pasta`.

## Se der errado

| O que aparece | O que fazer |
|---|---|
| `o programa 'docker' não foi encontrado` | abra o Docker Desktop e rode de novo |
| porta 15432, 15433 ou 18000 em uso | troque a porta no `.env`: a 15432 em `POSTGRES_PORTA` **e** em `PATIO_URL_BANCO`; a 15433 em `POSTGRES_TESTE_PORTA` **e** em `PATIO_URL_BANCO_TESTE`; a 18000 em `API_PORTA` (o simulador também a lê dali). Depois, rode de novo e use a porta nova no endereço da tela |
| `nenhuma caixa ativada` no simulador | rode com `--demonstracao` (só no ambiente local) ou com `--codigo` |
| `a nuvem não recebeu N passagens` | a API está fora do ar: `uv run tarefas up`; as passagens ficaram na fila e vão na próxima vez |
| a tela pede para entrar de novo | a sessão vale 12 horas; entre de novo |

## O que ainda falta para o marco completo

- **Vídeos gravados** com autorização (plano, [[T19]], passo 1): de 10 a 20 passagens de caminhão,
  com aviso de gravação e sem foco em rostos, em `dados/amostras/`, com a ficha de quem
  autorizou. É uma tarefa do Lorenzo.
- **A caixa na portaria**: o programa `caixa` já ativa, lê as câmeras ao vivo (RTSP) e envia
  (README, "A caixa de borda"); falta montá-lo no mini PC N150, com câmeras de verdade.
- **Acerto do leitor**: o v0 não tem meta de acerto; ele existe para o fluxo funcionar. O
  acerto é trabalho do v1, com pesos nossos (mês 2).

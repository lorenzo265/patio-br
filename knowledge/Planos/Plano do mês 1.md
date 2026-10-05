---
tipo: "plano"
fonte: "docs/planos/2026-10-plano-mes-1.md"
gerada: true
tags: [plano]
---

> [!note] Gerada de `docs/planos/2026-10-plano-mes-1.md` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Plano do mês 1 (outubro de 2026): fundação

Plano de implementação do mês 1 do cronograma do SDD ([[SDD|docs/SDD.md]], seção 10).
Versão 1 · 2026-10-02

---

## 1. Objetivo e marco

**Objetivo:** ter a base do projeto de pé — repositório organizado, verificações automáticas,
ambiente local com Docker, o formato da passagem, o esqueleto da nuvem com cadastro e login, e
um leitor de placas inicial (v0) rodando sobre vídeo gravado.

**Marco do mês (o teste de "pronto"):**

> Com um comando (`uv run tarefas demo`), o ambiente local sobe, um vídeo gravado de uma
> portaria passa pelo leitor v0, vira **passagem**, chega à API e **aparece na tela da
> portaria** com foto, placa e confiança.

**Fora do mês 1** (para não inchar): agendamento e casamento (mês 2), worker e fila de tarefas
(mês 2), telas de pátio e exceções (mês 3), WhatsApp (mês 4), verificação em duas etapas
(mês 4, antes da produção), AWS de produção (mês 4).

---

## 2. Como trabalhar neste plano

- **Uma tarefa = uma branch = um pull request** (`mes1/t06-contratos`, por exemplo). O PR só
  entra na `main` com a CI verde.
- **Teste primeiro** nas regras com lógica (formato de placa, votação, composição, separação de
  clientes, envio repetido): escreva o teste que falha, depois o código que o faz passar.
- **Ambiente de desenvolvimento:** seu computador é Windows (pelo que o projeto da Dell usa).
  Por isso os comandos do projeto são **Python puro**, chamados por `uv run tarefas <comando>`,
  e funcionam igual em Windows, Linux e Mac. Precisa de: Python 3.12, `uv` e Docker Desktop.
- **Dados reais (vídeos, fotos, placas) nunca entram no Git.** Ficam na pasta `dados/`, que o
  Git ignora.
- Qualquer mudança de desenho passa pelo SDD primeiro (regra da seção 0 do SDD).

---

## 3. Tarefas técnicas

Ordem sugerida por semana. Estimativas para uma pessoa com IA; a semana 4 tem folga.

### Semana 1 — fundação do repositório

- [[T01]] Estrutura de pastas e espaço de trabalho Python
- [[T02]] Comandos do projeto (`tarefas`)
- [[T03]] Integração contínua (GitHub Actions)
- [[T04]] Ambiente local com Docker
- [[T05]] Arquivo de orientação para sessões com IA

### Semana 2 — contrato e esqueleto da nuvem

- [[T06]] Pacote `contratos`: a Passagem
- [[T07]] Esqueleto da nuvem
- [[T08]] Módulo `cadastro` e separação por empresa
- [[T09]] Login e papéis
- [[T10]] Caixa de borda: ativação e chave

### Semana 3 — passagens e tela crua da portaria

- [[T11]] Receber passagens e fotos
- [[T12]] Tela crua da portaria

### Semana 3–4 — leitor v0 e simulador

- [[T13]] Licenças dos pesos do leitor v0
- [[T14]] Regras puras do leitor (sem modelo)
- [[T15]] Leitor v0
- [[T16]] Captura de vídeo e rastreamento
- [[T17]] Fila de envio da borda
- [[T18]] Agente da borda e simulador de portaria

### Semana 4 — demonstração e bancada

- [[T19]] Vídeos de amostra e demonstração do marco
- [[T20]] Kit de bancada e primeira medição de desempenho

## 4. Trilha não técnica (comercial e burocracia)

Coisas que levam tempo de calendário: começar na **semana 1**.

| # | Tarefa | Por quê | Resolve |
|---|---|---|---|
| [[N1]] | Pedir a **verificação da empresa na Meta** (Business Manager) e criar o app da Cloud API do WhatsApp | a verificação demora e libera o limite de 2.000 destinatários/dia | prepara o mês 4 |
| [[N2]] | Criar a conta **AWS** com alerta de gasto | evita surpresa de custo | prepara o mês 4 |
| [[N3]] | Reunião com **advogado**: modelo de contrato, acordo de tratamento de dados (LGPD) e prazos de guarda | o jurídico do cliente vai pedir | [[ABERTO-04]], [[ABERTO-07]] |
| [[N4]] | Escolher o **nome do produto** e registrar o domínio | as conversas comerciais precisam de nome | [[ABERTO-01]] |
| [[N5]] | Escrever o **roteiro das conversas** (só fatos passados: quantos postos, quanto custam, contrato de portaria, o que o seguro exige) e começar as 15–25 conversas | é o teste com comprador do Test Card | [[ABERTO-06]] |
| [[N6]] | Achar o **site parceiro** que cede uma portaria para gravar no mês 2 | sem ele não há dados para treinar | prepara o mês 2 |
| [[N7]] | **Comprar o hardware** da bancada ([[T20]]) e o do site parceiro | prazo de entrega | prepara o mês 2 |
| [[N8]] | Começar o **guia de posicionamento das câmeras** a partir da bancada | define altura e ângulo por tipo de portaria | [[ABERTO-08]] |

---

## 5. Ajustes no SDD feitos junto com este plano

- [[ABERTO-11]] (fila de tarefas no PostgreSQL) passa para o **mês 2**: o worker só é necessário
  quando entrar o casamento com o agendamento.
- **04/10, SDD 0.15:** [[ABERTO-12]] e [[ABERTO-13]] decididos ([[D-26]] e [[D-27]]). Pesos de terceiros
  servem só para comparar e avaliar; bibliotecas nativas LGPL entram sem modificação, e o FFmpeg
  sem partes GPL. Com isso, o que esperava o [[ABERTO-13]] (vídeo e RTSP na caixa, o executável
  da caixa e o `simulador --video`) deixa de esperar e vira a próxima tarefa.
- **04/10, SDD 0.16:** a caixa lê vídeo pelo OpenCV sem interface gráfica ([[D-29]]): câmera (RTSP)
  e arquivo, e o `simulador --video`. Novo [[ABERTO-14]]: o OpenSSL 1.1.1w dentro da roda do
  OpenCV para Linux. O programa da caixa (ativação, câmeras RTSP e envio) vem na tarefa seguinte.
- **04/10, SDD 0.17:** o programa da caixa (`caixa ativar` e `caixa rodar`): ativação, câmeras
  RTSP da configuração, agente e envio ([[D-30]]). Saúde, atualização e o contêiner da caixa seguem
  no mês 3, como no cronograma.
- **04/10, SDD 0.18:** [[ABERTO-14]] decidido ([[D-31]]): o OpenSSL que vem no OpenCV para Linux é
  aceito, com o crédito em [[Avisos de terceiros da caixa de borda|borda/AVISOS-DE-TERCEIROS.md]].

---

## 6. Checklist de "mês 1 pronto"

- [ ] `uv sync` e `uv run tarefas check` passam numa máquina limpa.
- [ ] CI verde na `main`, com checagem de licenças e vulnerabilidades.
- [ ] `contratos` com a Passagem v1, JSON Schema gerado e testado.
- [ ] Nuvem com cadastro, login, papéis, separação por empresa (com o teste de vazamento) e
      ativação da caixa.
- [ ] Recebimento de passagens com reenvio seguro e fotos no armazenamento local.
- [ ] Leitor v0 com pesos de licença verificada; regras de formato, votação e composição
      testadas.
- [ ] Fila de envio da borda testada com falha de rede.
- [ ] **Marco:** `uv run tarefas demo` mostra uma passagem de vídeo gravado na tela da portaria.
- [ ] Medição do v0 no N150 registrada.
- [ ] Trilha não técnica: [[N1]]–[[N3]] iniciados; [[N4]] decidido; pelo menos 5 conversas feitas; site
      parceiro em negociação; hardware comprado.

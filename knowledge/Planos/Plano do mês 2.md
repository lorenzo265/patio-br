---
tipo: "plano"
fonte: "docs/planos/2026-11-plano-mes-2.md"
gerada: true
tags: [plano]
---

> [!note] Gerada de `docs/planos/2026-11-plano-mes-2.md` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Plano do mês 2 (novembro de 2026): leitor próprio, agendamento e casamento

Plano de implementação do mês 2 do cronograma do SDD ([[SDD|docs/SDD.md]], seção 10).
Versão 2 · 2026-10-05 · Aprovado pelo Lorenzo; o site parceiro ficou para depois (seção 2)

---

## 1. Objetivo e marco

**Objetivo:** duas frentes em paralelo.

1. **Leitor próprio:** gravar as passagens do site parceiro, rotular 3 a 5 mil placas, montar a
   régua fixa e treinar o leitor v1, com pesos nossos ([[4.1 Regra de licença|SDD 4.1]], [[4.6 Dados de treino|4.6]] e [[4.7 Metas e a régua|4.7]]).
2. **Agendamento e casamento:** o agendamento chega pelo link da transportadora ou pela planilha
   do cliente, e a chegada da caixa casa com ele: check-in automático ou exceção ([[2.2 A jornada de um caminhão (modo A)|SDD 2.2]], [[3.4 Conectores de agendamento|3.4]] e
   5.3).

~~**Marco do mês (o teste de "pronto"): o teste técnico** ([[10. Cronograma (out-2026 – mar-2027)|SDD 10]]).~~ → próximo plano: o site
parceiro foi adiado em 05/10 (seção 2). Fica como marco o fluxo do agendamento à saída na
demonstração ([[T35]]), com a conferência da placa pelo porteiro ([[T38]]).

> Na régua fixa, o leitor v1 é comparado com o leitor comercial (e com o v0): acerto por placa e
> acerto da composição casando com o agendamento. O resultado decide o caminho do piloto:
>
> | Composição casando com o agendamento | Ação |
> |---|---|
> | ≥ 95% | segue com o leitor próprio |
> | 90–95% | segue, com mais um ciclo de rotulagem e treino antes do modo sombra |
> | < 90% | o piloto começa com o leitor comercial; o próprio continua treinando com dados do piloto |

**Fora do mês 2** (para não inchar):
- **mês 3:** telas definitivas de portaria e pátio, resolver as exceções pela tela, estados
  completos da visita (fila, chamada, doca), alertas, trilha de prova completa, o conector
  `api_generica`, e na caixa a saúde, a atualização e o contêiner;
- **mês 4:** WhatsApp e extrato.

**O que fica do mês 1:** a medição no N150 ([[T20]]) entra na semana 2, já com o v1. Os vídeos da
[[T19]] passam a ser as gravações do site parceiro ([[T21]]).

---

## 2. Antes de começar: decisões do Lorenzo

Quatro decisões travam tarefas do mês. As três primeiras estão no SDD como itens em aberto.

| # | Decisão | O que trava | Recomendação |
|---|---|---|---|
| D1 | **[[ABERTO-15]]: gravar sem guardar rostos.** O detector aprende com quadros inteiros, e a base de treino só pode ter recortes de placa ([[4.6 Dados de treino\|SDD 4.6]] e [[8.3 LGPD\|8.3]]). | [[T21]] e o treino do detector ([[T24]]) | Cada câmera de placa ganha uma **região de gravação**, abaixo do para-brisa, marcada no cadastro da câmera. A caixa só guarda o que está nela. A câmera é posicionada para enquadrar o para-choque (guia de posicionamento, [[ABERTO-08]]). O detector do v1 aprende veículo e placa dentro dessa região. |
| D2 | **[[ABERTO-16]]: ambiente de treino.** O PyTorch com GPU traz bibliotecas da NVIDIA com licença proprietária. | [[T24]] e [[T25]] | O treino roda num **ambiente à parte**, fora do `uv.lock` do projeto, só na máquina de GPU alugada. Nada dele vai para a caixa nem para a nuvem. Os modelos saem em ONNX, e o código de treino segue a regra de licença (Apache, MIT ou BSD). |
| D3 | **[[ABERTO-17]]: leitor comercial no teste técnico.** Mandar as imagens da régua ao Plate Recognizer é passar dado de terceiros a outro operador, talvez fora do Brasil. | [[T36]] (o marco) | Perguntar ao advogado ([[N3]] do mês 1) e ao site parceiro. Se não puder, usar o programa local do Plate Recognizer, ou comparar o v1 só com o v0 e com o registro manual da portaria. |
| D4 | **[[ABERTO-11]]: fila de tarefas no PostgreSQL.** O casamento e o "não veio" rodam fora do pedido da caixa. | [[T33]] | **Tabela própria**, com um worker que pega a próxima tarefa por `SELECT ... FOR UPDATE SKIP LOCKED`. As bibliotecas de fila para PostgreSQL que conheço usam o psycopg (LGPL), que a [[D-18]] tirou. |

Mais uma pergunta, sem item no SDD: **quem rotula as 3 a 5 mil placas, e em quantas horas** ([[N10]]).
Com a leitura do v0 como pré-rótulo, a pessoa só confere e corrige. O ritmo real é medido na
primeira hora de rotulagem.

**Decididas em 05/10:**
- D1 a D4 pela recomendação (SDD [[D-39]], [[D-40]], [[D-41]] e [[D-38]]).
- Quem rotula: o Lorenzo. Ele pediu também que o porteiro confira a placa na plataforma,
  comparando a leitura com a foto ([[T38]], SDD [[D-42]]).
- O site parceiro fica para depois: o Lorenzo quer o produto mais completo antes de levá-lo
  ao site. As primeiras placas vêm de outra fonte ([[ABERTO-18]],
  [[Validação - fontes de placas|docs/validacao/fontes-de-placas.md]]). O que depende do site sai deste mês (riscado abaixo).

---

## 3. Como trabalhar neste plano

As mesmas regras do mês 1 ([[CLAUDE - regras do repositório|CLAUDE.md]]), com estes ajustes:

- **Numeração:** as tarefas continuam a do mês 1 ([[T21]] em diante), para "[[T13]]" nunca ser ambíguo.
  As branches levam `mes2/` (ex.: `mes2/t27-agendamentos`).
- **Ordem dos PRs:** quando um PR depende de outro, ele é aberto depois. O merge segue a ordem
  dos números dos PRs.
- **Dados do site parceiro** (vídeos, quadros, placas, rótulos) ficam em `dados/`, fora do Git.
  No repositório entram só o código, o manifesto da régua (nomes e resumos dos arquivos, sem as
  placas) e os números das medições.

---

## 4. Tarefas técnicas

Ordem sugerida por semana. A semana 4 tem folga.

### Semana 1 — gravar, rotular e a régua

- ~~[[T21]] Gravação no site parceiro~~ → [[T65]] do mês 5
- ~~[[T22]] Rotulagem no Label Studio~~ → [[T75]] do mês 5
- ~~[[T23]] Régua fixa~~ → [[T75]] do mês 5

### Semana 2 — leitor v1

- ~~[[T24]] Detector v1~~ → [[T66]] do mês 5
- ~~[[T25]] OCR v1~~ → [[T67]] do mês 5
- ~~[[T26]] Leitor v1 na caixa~~ → [[T68]] do mês 5

### Semanas 2–3 — agendamento

- [[T27]] Agendamentos no banco
- [[T28]] Link da transportadora
- [[T29]] Importar planilha
- [[T30]] Tela de agendamentos

### Semana 3 — visita e casamento

- [[T31]] Visita e eventos
- [[T32]] Casamento
- [[T33]] Fila de tarefas e worker
- [[T34]] Exceções na tela da portaria (só ver)

### Semana 4 — de ponta a ponta e o teste técnico

- [[T35]] Simulador com agendamentos
- ~~[[T36]] Teste técnico (o marco)~~ → [[T78]] do mês 5
- ~~[[T37]] Ajuste do casamento~~ → [[T77]] do mês 5

### Acrescentada em 05/10

- [[T38]] Conferência da placa pelo porteiro

## 5. Trilha não técnica (comercial e burocracia)

| # | Tarefa | Por quê | Resolve |
|---|---|---|---|
| ~~[[N9]]~~ | ~~**Instalar o kit no site parceiro**, com as câmeras posicionadas pelo guia ([[N8]]), a placa de aviso de gravação e o termo com o site~~ (adiada em 05/10, seção 2) | sem ele não há dados para treinar | [[T21]] |
| [[N10]] | ~~**Definir quem rotula**~~ resolvida em 05/10: o Lorenzo | 3 a 5 mil placas | [[T22]] |
| [[N11]] | **Abrir as contas:** GPU por hora para o treino (quando houver as primeiras placas) e, se D3 permitir, Plate Recognizer | o treino e o teste técnico | [[T24]], [[T36]] |
| [[N12]] | **Montar a oferta de piloto anual pré-pago** e levá-la às conversas | o comercial do mês 2 ([[10. Cronograma (out-2026 – mar-2027)\|SDD 10]]) | [[ABERTO-06]] |
| ~~[[N13]]~~ | ~~**Combinar com o site parceiro o registro manual** das chegadas durante a gravação (hora, placas, agendamento)~~ (adiada em 05/10) | é o gabarito da composição e do casamento | [[T36]], [[T37]] |
| [[N14]] | **Fechar o que ficou da trilha do mês 1** ([[N1]] a [[N8]]) | Meta, AWS e advogado têm prazo longo | [[ABERTO-01]], [[ABERTO-04]], [[ABERTO-07]] |
| [[N15]] | **Levar ao advogado** (acrescentada em 05/10): gravar em portões de conhecidos, fotografar placas na rua, o leitor comercial na nuvem ([[D-41]]) e a cláusula do treino no contrato ([[8.3 LGPD\|SDD 8.3]]) | a coleta própria e o uso das conferências no treino dependem do sim | [[ABERTO-18]], [[ABERTO-07]] |

---

## 6. Ajustes no SDD feitos junto com este plano

- Novos itens em aberto, para decidir antes das tarefas que travam (seção 2):
  - [[ABERTO-15]]: gravar sem guardar rostos;
  - [[ABERTO-16]]: ambiente de treino;
  - [[ABERTO-17]]: leitor comercial no teste técnico.
- Em 05/10 (SDD 0.28): os três fechados pela recomendação ([[D-39]] a [[D-41]]), a [[D-38]] confirmada, a
  conferência da placa pelo porteiro ([[D-42]]) e o novo [[ABERTO-18]] (as primeiras placas).

---

## 7. Checklist de "mês 2 pronto"

- [x] D1 a D4 decididas e registradas no SDD.
- [ ] ~~Gravações do site parceiro em `dados/`, sem rostos,~~ e 3 a 5 mil placas rotuladas
      (da fonte que o [[ABERTO-18]] escolher).
- [ ] Régua fixa separada, com o manifesto no repositório e a garantia de que não entra no
      treino.
- [ ] Detector e OCR v1 treinados, com pesos nossos; o v1 na caixa; [[ABERTO-03]] decidido.
- [ ] Medição no N150 registrada (a [[T20]] do mês 1).
- [x] Agendamento por link e por planilha, com a tela do gestor.
- [x] Casamento com check-in automático, exceção e saída, com o worker.
- [ ] Conferência da placa pelo porteiro ([[T38]]).
- [ ] ~~**Marco:** teste técnico feito e o caminho do piloto decidido.~~ → próximo plano
- [ ] ~~[[ABERTO-02]] fechado com os dados do site parceiro.~~ → próximo plano
- [ ] Trilha não técnica: ~~kit instalado no site parceiro;~~ oferta de piloto nas conversas.

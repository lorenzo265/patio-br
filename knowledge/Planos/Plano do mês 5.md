---
tipo: "plano"
fonte: "docs/planos/2027-02-plano-mes-5.md"
gerada: true
tags: [plano]
---

> [!note] Gerada de `docs/planos/2027-02-plano-mes-5.md` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Plano do mês 5: o piloto no site, em modo sombra

Plano de implementação do mês 5 do cronograma do SDD ([[SDD|docs/SDD.md]], seção 10).
Versão 1 · 2026-10-09 · **Rascunho para aprovação do Lorenzo**

---

## 1. Objetivo e marco

**Objetivo:** a caixa e as 6 câmeras no site do piloto, em **modo sombra** por 2 a 4 semanas.
Nesse tempo, o trabalho da portaria não muda ([[9. Testes e qualidade|SDD 9]], item 6). No mês:
- o leitor com pesos nossos (v1) vai para a caixa e é treinado de novo com as placas do próprio
  site;
- o acerto real é medido contra o registro manual da portaria, de dia e de noite;
- a linha de base do extrato é medida no mesmo período.

No fim do mês sai a decisão de ligar o check-in automático no mês 6.

**Marco do mês (o teste de "pronto"):**

> No site do piloto, depois de pelo menos 2 semanas de modo sombra:
> 1. A caixa e as 6 câmeras estão no ar, com a saúde na frota de borda. Uma queda da internet
>    principal passa pela internet de reserva, e nada se perde.
> 2. Nenhuma mensagem saiu para um motorista, e o trabalho da portaria seguiu como sempre.
> 3. O relatório do acerto real está pronto: por placa e por composição casando com o
>    agendamento, de dia e de noite, com a margem de erro. Ele compara o nosso leitor com o
>    comercial.
> 4. O leitor foi treinado de novo com as placas do site, sem piorar a régua fixa.
> 5. A linha de base do extrato está gravada, com a origem "modo sombra" e os parâmetros do
>    cliente.
> 6. A decisão de ligar o check-in no mês 6 está escrita, pela régua da G6.

**Antes de instalar:**
- **O contrato:** o piloto fechado ([[N24]]), com o contrato e o acordo de tratamento de dados
  assinados ([[ABERTO-07]]) e a cláusula do treino ([[8.3 LGPD|SDD 8.3]]; o sim do advogado, [[N22]]). Sem
  isso, nenhum dado do cliente entra na produção.
- **A produção:** no ar na AWS ([[N21]]), com o roteiro do piloto rodado na homologação (o marco do
  mês 4, [[T62]]).
- **O WhatsApp e o SMS não são necessários neste mês.** No modo sombra nada sai ao motorista (G4),
  e as contas da Meta e do SMS ([[N19]] e [[N20]]) ficam para o mês 6.

**O que fica do mês 4**, em paralelo com este plano:
- o visual próprio ([[T40]]), na sessão da identidade visual ([[ABERTO-01]]);
- o deploy da demonstração ([[N17]]);
- a API e os webhooks ([[T61]]), só se o cliente do piloto pedir;
- as conferências de verdade, que esperam as contas: a homologação e a produção ([[N21]]), a caixa
  num N150 ([[N23]]), a Meta ([[N19]]) e o SMS ([[N20]]).

**Fora do mês 5:**
- **O check-in automático ligado, o WhatsApp ativo e o primeiro extrato real:** são o mês 6
  ([[10. Cronograma (out-2026 – mar-2027)|SDD 10]]).
- **A foto de contexto com os rostos borrados:** espera um modelo de rostos com pesos nossos
  ([[4.1 Regra de licença|SDD 4.1]]). A caixa segue mandando só o recorte da placa.
- **O SSE ([[D-09]]):** as telas continuam perguntando ao servidor a cada 2 ou 3 segundos.
- O modo B e as fases seguintes ([[3.5 Fases futuras (já previstas)|SDD 3.5]]).

**Riscos do mês e o plano B:**

| Risco | Plano B |
|---|---|
| o piloto não fecha a tempo | a mesma sombra num portão de conhecidos (a coleta própria do [[ABERTO-18]], com o sim do advogado); mede e treina o leitor, mas não dá a linha de base |
| o v1 do começo, treinado sem placas reais, lê mal | é o esperado; a sombra não decide nada; o comercial local mede o plano B desde o primeiro dia (G1), e o retreino semanal usa as placas do site |
| a noite lê mal | ajustar o infravermelho e o obturador ([[T70]]), treinar de novo com as placas da noite e, se não bastar, levar à decisão de ligar (G6) |
| a internet do site é fraca para subir as gravações | subir com limite de banda, à noite; ou tirar as gravações da caixa pela Tailscale |
| o cliente não aceita o registro manual em planilha | conferir pela foto uma amostra maior; o que a câmera não viu fica sem medida, e o relatório diz isso |

---

## 2. Antes de começar: decisões do Lorenzo

| # | Decisão | Trava | Recomendação | Decidido em |
|---|---|---|---|---|
| G1 | **Que leitor a caixa leva para o modo sombra.** O v0 não vai para o produto ([[D-26]]), e o teste técnico (a antiga [[T36]]) não aconteceu: o nosso leitor nunca foi medido em placas reais. | [[T68]], [[T69]], [[T78]] | **Os dois na caixa:** o v1 (pesos nossos) é o leitor da caixa; o Plate Recognizer, pelo programa local (US$ 50 por mês, sem mandar imagem para fora, [[D-41]]), lê as mesmas passagens só para comparar. O que ele lê nunca vira rótulo. Assim, o teste técnico acontece no próprio site, em passagens reais. A tabela da seção 10 do SDD vale no fim: com o nosso a 95% ou mais, o mês 6 liga com o nosso; abaixo, liga com o comercial, se ele chegar à régua da G6, e o nosso segue treinando. As alternativas: **só o v1**, mais barato, mas sem plano B medido (o mês 6 poderia ter de começar com um leitor nunca visto no site); **só o comercial**, que mede o plano B, mas não deixa medir o nosso nem o retreino no lugar. | — |
| G2 | **De onde vêm as placas reais** ([[ABERTO-18]]). | [[T65]], [[T75]], [[T76]] | **Do próprio site do piloto**, com a cláusula do treino no contrato ([[D-71]]) e o sim do advogado. A caixa grava a região de gravação de cada passagem ([[D-39]]), e as gravações sobem para a base de treino. O Lorenzo rotula, e a régua fixa sai das mesmas passagens, separada antes do treino. São as placas que mais importam: as da câmera, da luz e da portaria onde o leitor vai trabalhar. Os portões de conhecidos e a frota parada ficam como plano B, se o piloto atrasar. A alternativa é começar pela frota parada e pelos portões: tem placas antes, mas de outra câmera e de outro ângulo, e pede outra autorização para cada lugar. | — |
| G3 | **Como medir o acerto real** (o gabarito). | [[T72]], [[T78]] | **O registro manual da portaria, com a conferência pela foto.** A portaria já anota quem entra (caderno, planilha ou o sistema dela); durante a sombra, esse registro vem numa planilha. O sistema compara com o que a câmera viu. O Lorenzo confere pela foto só o que diverge, mais 1 em cada 10 dos que concordam, para conferir que concordar é acertar. É o único jeito de achar o caminhão que a câmera não viu, e não pede trabalho novo ao porteiro. As alternativas: **o porteiro confere toda passagem no tablet**, com um gabarito melhor, mas é trabalho a mais no posto que o cliente quer reduzir, e muda o processo que a sombra só deveria observar; **o Lorenzo confere tudo pela foto**: são cerca de 3.600 visitas por mês, e não acha o que a câmera não viu. | — |
| G4 | **O que o sistema faz no modo sombra.** | [[T64]], [[T74]] | **Tudo roda e se grava, mas nada sai.** O casamento, o check-in que seria automático, as exceções e a saída acontecem como no mês 6. Mas nenhuma mensagem vai ao motorista, nem a confirmação nem o SMS, e nenhum alerta vai ao gestor por WhatsApp. O painel mostra tudo, com a faixa "modo sombra", e os alertas da caixa e das câmeras chegam a nós. O porteiro não usa o tablet. Os agendamentos entram pela planilha do cliente, todo dia (a importação da [[T29]]), ou pela API ([[T61]]), se o cliente pedir. Na última semana, se o cliente quiser, um ensaio: o porteiro usa o tablet ao lado do registro de sempre, para chegar treinado ao mês 6. A alternativa é já avisar o motorista na sombra: mede o WhatsApp antes, mas um aviso nascido de um check-in errado confunde o motorista e o porteiro. | — |
| G5 | **Como medir a linha de base do extrato e as horas de portaria** ([[5.4 Contas do extrato\|SDD 5.4]] e [[ABERTO-05]]). | [[T73]] | **Nas 2 últimas semanas da sombra, com o mesmo instrumento do depois:** a chegada e a saída pelas câmeras; a chamada, o início e o fim na doca marcados pelo líder de pátio na tela do pátio (a única mudança pedida ao cliente na sombra); as toneladas, dos agendamentos. **A portaria, pela escala:** postos × horas, no contrato do serviço de portaria ou na escala da equipe própria, antes (na sombra) e depois. O custo do posto vem do mesmo contrato, e o gestor informa, com o documento. Sem as marcas do líder, a linha de base fica só com o tempo no site e a espera fica sem medida; o extrato diz isso. A alternativa é tirar a linha de base do histórico do cliente (os meses de antes, no sistema dele): a amostra é maior, mas medida com outro instrumento (a hora anotada à mão contra a hora da câmera), o que pode inventar ou esconder economia. | — |
| G6 | **A régua para ligar o check-in automático no mês 6.** | [[T78]] | **Liga quando, em pelo menos 7 dias seguidos da sombra, com a mesma versão do leitor, de dia e de noite, e com pelo menos 500 composições conferidas:** (1) a composição certa casando com o agendamento fica em 95% ou mais (a meta do [[4.7 Metas e a régua\|SDD 4.7]]; com 500, a margem é de cerca de 2 pontos); (2) o check-in automático errado, no agendamento errado, fica em até 1 em 200; (3) as chegadas agendadas com check-in sem o porteiro chegam a 70% ou mais ([[1.5 O que o piloto precisa provar\|SDD 1.5]]). Liga com o leitor que cumpriu (G1). Se nenhum cumprir, mais 2 semanas de sombra, com o ajuste (câmera, retreino), e o mês 6 encurta. A alternativa é olhar só a meta de 95%: mas um check-in errado é pior que uma exceção, porque o caminhão errado vai para a doca e a prova fica errada. | — |
| G7 | **O hardware e a instalação.** | [[T70]], [[T74]] | **Nós compramos o hardware, que fica nosso, emprestado ao site pelo tempo do contrato, e entra no preço do piloto** ([[ABERTO-06]]). As peças: a caixa N150, 6 câmeras IP de 4 MP com lente varifocal, infravermelho e obturador ajustável, de uma marca com assistência no Brasil, o switch PoE, o nobreak, o roteador 4G e um tablet Android de 10" com suporte. As câmeras são conferidas antes na bancada. **Um integrador de CFTV da região** passa os cabos e fixa as câmeras, pelo nosso guia ([[T70]]); o cliente costuma ter um. Nós configuramos e conferimos o enquadramento. A alternativa é o cliente comprar pela nossa lista: não prende o nosso dinheiro, mas cada site fica diferente, e trocar uma peça demora. | — |

---

## 3. Como trabalhar neste plano

As mesmas regras dos meses anteriores ([[CLAUDE - regras do repositório|CLAUDE.md]]), com estes ajustes:

- **Numeração:** as tarefas continuam de onde pararam, a partir da [[T64]]. As tarefas do leitor que
  esperavam as placas reais ganham números novos aqui:
  - a medição no N150 ([[T20]]) vira a [[T70]];
  - a gravação ([[T21]]) vira a [[T65]];
  - a rotulagem e a régua ([[T22]] e [[T23]]) viram a [[T75]];
  - o detector, o OCR e o leitor v1 ([[T24]], [[T25]] e [[T26]]) viram a [[T66]], a [[T67]] e a [[T68]];
  - o teste técnico ([[T36]]) vira a [[T78]], e o ajuste do casamento ([[T37]]), a [[T77]].

  Os planos dos meses 1 e 2 mostram as antigas riscadas, com a tarefa para onde foram. As
  branches levam `mes5/` (ex.: `mes5/t64-modo-sombra`).
- **O primeiro dado real:** a partir da instalação, a produção guarda dados do cliente. Nada
  disso entra no Git (regra 3):
  - os relatórios no repositório só levam números;
  - as fotos e as gravações ficam no armazenamento da nuvem;
  - a máquina de GPU alugada recebe só a pasta da base de treino ([[D-71]]) e a apaga ao terminar;
  - os testes continuam com dados inventados.
- **O treino** roda no ambiente à parte ([[D-40]]), com código de licença Apache, MIT ou BSD.
  - **Os pesos de partida:** do zero, ou de um ponto de partida com licença conferida, nunca os
    pesos do v0 nem outros sem licença declarada ([[D-26]]).
  - **A régua ([[4.7 Metas e a régua|SDD 4.7]]):** cada versão nova do leitor só vai à caixa se não piorar a régua.
    O primeiro v1 é a exceção: entra na sombra sem régua, porque ali ele não decide nada.
- **Cada ida ao site e cada versão mandada à caixa** entram no PR da tarefa: o que foi feito e os
  números, sem placas nem fotos.
- **O que a execução decidir vira uma D-nn** no SDD, no mesmo PR, como nos meses anteriores.

---

## 4. Tarefas técnicas

### Semana 1 — antes de instalar

- [[T64]] O modo sombra do site
- [[T65]] A região de gravação e a gravação para treino (era a [[T21]])
- [[T66]] Detector v1 (era a [[T24]])
- [[T67]] OCR v1 (era a [[T25]])
- [[T68]] Leitor v1 na caixa, com os pesos na versão (era a [[T26]])
- [[T69]] O leitor comercial local, só para comparar
- [[T70]] A caixa do piloto na bancada: a medição no N150 e o enquadramento (era a [[T20]])

### Semana 2 — a instalação

- [[T71]] O PWA dos tablets
- [[T72]] O registro manual e a conferência das divergências
- [[T73]] Os parâmetros do extrato e a linha de base medida
- [[T74]] A instalação no site e o começo do modo sombra

### Semanas 3 e 4 — medir e treinar de novo

- [[T75]] Rotulagem e régua fixa (eram a [[T22]] e a [[T23]])
- [[T76]] O retreino com as placas do site
- [[T77]] Ajuste do casamento (era a [[T37]])
- [[T78]] O acerto real medido e a decisão de ligar (era a [[T36]]; o marco)

## 5. Trilha não técnica

| # | Tarefa | Por quê | Resolve |
|---|---|---|---|
| [[N25]] | Combinar o modo sombra com o cliente: as datas; o aviso aos porteiros e ao líder de pátio; o registro manual numa planilha (G3); as marcações do líder na tela do pátio (G5); a planilha diária dos agendamentos (G4); os parâmetros do extrato e a escala da portaria (G5, [[ABERTO-05]]); os tempos dos alertas ([[ABERTO-09]]) | o gabarito, a linha de base e os agendamentos dependem do cliente | [[T72]], [[T73]], [[T74]], [[ABERTO-05]], [[ABERTO-09]] |
| [[N26]] | Comprar o hardware do site (G7): a caixa N150, as 6 câmeras, o switch PoE, o nobreak, o rack, o roteador 4G com o chip e o tablet com suporte. Contratar o integrador de CFTV | o prazo de entrega e a instalação | [[T70]], [[T74]] |
| [[N27]] | Abrir a conta da GPU por hora ([[N11]]) e a do Plate Recognizer, com o programa local (G1, US$ 50 por mês) | o treino e a comparação | [[T66]], [[T67]], [[T69]], [[T76]] |
| [[N28]] | Fazer a placa de aviso da portaria, com o contato do encarregado e o uso para treino, e o relatório de impacto (RIPD) para o cliente ([[8.3 LGPD\|SDD 8.3]]); o advogado confere ([[N22]]) | a transparência da LGPD antes da primeira câmera | [[T65]], [[T74]] |
| [[N29]] | Visitar o site antes da instalação: as faixas e onde ficam as câmeras, a energia, a rede, o lugar da caixa e a internet de reserva. Fotos só para o guia, sem placas nem pessoas | o guia de instalação e a lista de compras | [[T70]], [[T74]], [[ABERTO-08]] |
| [[N30]] | Reservar as horas de rotular: a régua (cerca de 1.000 placas), as divergências da sombra e as caixas do detector, ao longo de 3 semanas | sem rótulo não há régua nem retreino | [[T72]], [[T75]], [[T76]] |

---

## 6. Ajustes no SDD feitos junto com este plano

- **No SDD 0.58:**
  - o cronograma do mês 5 (seção 10) com o que este plano traz: o leitor v1 e o teste técnico,
    que esperavam as placas reais desde o mês 2, vêm para o modo sombra do site do piloto, com o
    comercial local para comparar, o registro manual, a gravação para treino, os parâmetros e a
    linha de base e o PWA dos tablets;
  - as propostas para o [[ABERTO-05]] (G5) e o [[ABERTO-18]] (G2), na seção 12;
  - os novos prazos do [[ABERTO-02]], do [[ABERTO-03]], do [[ABERTO-08]] e do [[ABERTO-09]].
- **Com a aprovação:**
  - as decisões G1 a G7 viram D-nn;
  - o modo sombra entra nas seções 5.4 e 9;
  - o leitor da sombra e a comparação entram nas seções 4.5 e 4.7;
  - as placas do site entram na seção 4.6;
  - o [[ABERTO-05]] e o [[ABERTO-18]] fecham.

---

## 7. Checklist de "mês 5 pronto"

- [ ] G1 a G7 decididas e registradas no SDD.
- [ ] O modo sombra: tudo se grava, e nada sai ao motorista.
- [ ] A gravação para treino, só da região de gravação e só com a cláusula.
- [ ] O detector e o OCR v1 treinados por nós, e o [[ABERTO-03]] fechado.
- [ ] O leitor v1 na caixa, com os pesos entregues pela atualização, com volta.
- [ ] O leitor comercial local lendo as mesmas passagens, só para comparar (G1).
- [ ] A medição no N150 com 6 câmeras e o guia de instalação ([[ABERTO-08]]).
- [ ] O PWA nos tablets.
- [ ] O registro manual comparado, e as divergências conferidas.
- [ ] Os parâmetros do extrato e a linha de base medida na sombra.
- [ ] A caixa e as 6 câmeras no site, com a saúde na frota.
- [ ] A rotulagem, a régua fixa e um retreino que não piora a régua.
- [ ] O casamento ajustado com os dados do piloto ([[ABERTO-02]]).
- [ ] **Marco:** o acerto real medido, com a decisão de ligar o check-in no mês 6.

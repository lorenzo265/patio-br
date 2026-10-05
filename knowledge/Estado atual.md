---
tipo: "mapa"
escrita: "à mão"
atualizada: "2026-10-05"
tags: [estado]
---

# Estado atual

> [!info] Retrato de 05/10/2026 (SDD 0.37)
> Escrito à mão: o que entrou depois está nos PRs do GitHub e nos planos. Os checklists de "mês
> pronto" dos planos não foram marcados a cada tarefa; esta nota é a lista do que entrou.

## Em poucas linhas

- **Funciona de ponta a ponta, no ambiente local e com dados inventados:** o agendamento (link
  da transportadora e planilha), a passagem da caixa ou do simulador, o casamento com o
  agendamento, a exceção resolvida pela tela, a chegada manual, a fila, as docas, as mensagens ao
  motorista (num canal de demonstração, sem enviar nada), o painel e o extrato em R$, as telas
  "em breve" do recebimento e do estoque e o dia de demonstração.
- **Falta para a demonstração no ar (mês 3):** o visual próprio ([[T40]], depois da identidade
  visual, [[ABERTO-01]]), a demonstração na internet ([[T47]], Vercel e Supabase, [[D-51]]) e o
  link por empresa ([[T48]], [[D-52]]).
- **O leitor próprio espera as placas:** o treino ([[T22]] a [[T26]]) depende das placas reais
  do [[ABERTO-18]]; o leitor v0, com pesos de terceiros, serve só para avaliação interna
  ([[D-26]]).
- **A caixa de borda** lê vídeo gravado e câmera RTSP, monta a passagem e envia com fila e
  reenvio; a medição no mini PC N150 ([[T20]]) espera o hardware.

## Mês 1: fundação ([[Plano do mês 1]])

| Tarefa | Situação | PR |
|---|---|---|
| [[T01]] estrutura do workspace | feita | [#2](https://github.com/lorenzo265/patio-br/pull/2) |
| [[T02]] comandos `tarefas` | feita | [#3](https://github.com/lorenzo265/patio-br/pull/3) |
| [[T03]] CI (testes, licenças, vulnerabilidades) | feita | [#4](https://github.com/lorenzo265/patio-br/pull/4) |
| [[T04]] ambiente local com Docker | feita | [#5](https://github.com/lorenzo265/patio-br/pull/5) e [#10](https://github.com/lorenzo265/patio-br/pull/10) |
| [[T05]] CLAUDE.md | feita | [#6](https://github.com/lorenzo265/patio-br/pull/6) |
| [[T06]] contratos: a Passagem v1 | feita | [#7](https://github.com/lorenzo265/patio-br/pull/7) |
| [[T07]] esqueleto da nuvem | feita | [#8](https://github.com/lorenzo265/patio-br/pull/8) |
| [[T08]] cadastro e separação por empresa | feita | [#9](https://github.com/lorenzo265/patio-br/pull/9) |
| [[T09]] login e papéis | feita | [#11](https://github.com/lorenzo265/patio-br/pull/11) |
| [[T10]] ativação da caixa e chave | feita | [#12](https://github.com/lorenzo265/patio-br/pull/12) |
| [[T11]] receber passagens e fotos | feita | [#13](https://github.com/lorenzo265/patio-br/pull/13) |
| [[T12]] tela crua da portaria | feita | [#14](https://github.com/lorenzo265/patio-br/pull/14) |
| [[T13]] licenças dos pesos do leitor v0 | feita | [#17](https://github.com/lorenzo265/patio-br/pull/17) |
| [[T14]] formato de placa, votação e composição | feita | [#15](https://github.com/lorenzo265/patio-br/pull/15) |
| [[T15]] leitor v0 | feita | [#19](https://github.com/lorenzo265/patio-br/pull/19) |
| [[T16]] captura e rastreamento | feita | [#18](https://github.com/lorenzo265/patio-br/pull/18) |
| [[T17]] fila de envio da borda | feita | [#16](https://github.com/lorenzo265/patio-br/pull/16) |
| [[T18]] agente da borda e simulador | feita | [#20](https://github.com/lorenzo265/patio-br/pull/20) |
| [[T19]] demonstração do mês 1 | feita | [#21](https://github.com/lorenzo265/patio-br/pull/21) |
| [[T20]] kit de bancada e medição no N150 | **espera o hardware** ([[N7]]) | |

Além das tarefas: as decisões de 04/10 ([[D-26]] a [[D-28]],
[#22](https://github.com/lorenzo265/patio-br/pull/22)), a leitura de vídeo e RTSP na caixa
([#23](https://github.com/lorenzo265/patio-br/pull/23)), o programa da caixa
([#24](https://github.com/lorenzo265/patio-br/pull/24)) e o OpenSSL do OpenCV ([[D-31]],
[#25](https://github.com/lorenzo265/patio-br/pull/25)).

## Mês 2: agendamento e casamento ([[Plano do mês 2]])

| Tarefa | Situação | PR |
|---|---|---|
| [[T21]] gravação no site parceiro | **adiada**: o site parceiro ficou para depois | |
| [[T22]] a [[T26]] rotulagem, régua e leitor v1 | **esperam as placas** do [[ABERTO-18]] | |
| [[T27]] agendamentos e a interface de conector | feita | [#27](https://github.com/lorenzo265/patio-br/pull/27) |
| [[T28]] link da transportadora | feita | [#28](https://github.com/lorenzo265/patio-br/pull/28) |
| [[T29]] importar planilha | feita | [#29](https://github.com/lorenzo265/patio-br/pull/29) |
| [[T30]] tela de agendamentos | feita | [#30](https://github.com/lorenzo265/patio-br/pull/30) |
| [[T31]] visita e eventos | feita | [#31](https://github.com/lorenzo265/patio-br/pull/31) |
| [[T32]] casamento | feita | [#32](https://github.com/lorenzo265/patio-br/pull/32) |
| [[T33]] fila de tarefas e worker | feita | [#33](https://github.com/lorenzo265/patio-br/pull/33) |
| [[T34]] exceções na portaria (só ver) | feita | [#34](https://github.com/lorenzo265/patio-br/pull/34) |
| [[T35]] simulador com agendamentos | feita | [#35](https://github.com/lorenzo265/patio-br/pull/35) |
| [[T36]] teste técnico e [[T37]] ajuste do casamento | **passaram para depois** (precisam de placas reais) | |
| [[T38]] conferência da placa pelo porteiro | feita | [#37](https://github.com/lorenzo265/patio-br/pull/37) |

Além das tarefas: o plano ([#26](https://github.com/lorenzo265/patio-br/pull/26)), as decisões
de 05/10 ([[D-39]] a [[D-42]], com a [[D-38]] confirmada; [#36](https://github.com/lorenzo265/patio-br/pull/36)) e o
recebimento e o estoque como módulos de depois do piloto ([[D-43]], [[D-44]],
[#38](https://github.com/lorenzo265/patio-br/pull/38)).

## Mês 3: a demonstração comercial ([[Plano do mês 3]])

| Tarefa | Situação | PR |
|---|---|---|
| [[T40]] visual próprio | **espera a identidade visual** (sessão à parte, [[Prompt da identidade visual]]) | |
| [[T41]] portaria definitiva | feita | [#40](https://github.com/lorenzo265/patio-br/pull/40) |
| [[T42]] pátio e docas | feita | [#41](https://github.com/lorenzo265/patio-br/pull/41) |
| [[T43]] mensagens do motorista | feita | [#42](https://github.com/lorenzo265/patio-br/pull/42) |
| [[T44]] painel e extrato em R$ | feita | [#44](https://github.com/lorenzo265/patio-br/pull/44) |
| [[T45]] dia de demonstração | feita | [#46](https://github.com/lorenzo265/patio-br/pull/46) |
| [[T46]] recebimento e estoque "em breve" | feita | [#45](https://github.com/lorenzo265/patio-br/pull/45) |
| [[T47]] demonstração na internet | **espera as contas** da Vercel e do Supabase ([[N17]]) | |
| [[T48]] link por empresa | a fazer, depois da [[T47]] | |

Além das tarefas: o plano ([#39](https://github.com/lorenzo265/patio-br/pull/39)), o relógio dos
testes ([#43](https://github.com/lorenzo265/patio-br/pull/43)), as decisões E2 a E4 no SDD 0.36
([[D-50]] a [[D-52]]) com o prompt da identidade visual
([#47](https://github.com/lorenzo265/patio-br/pull/47)) e este vault ([[D-53]]), num PR depois
dele.

## O que existe no código hoje

- **Nuvem** ([[nuvem]]): cadastro e login ([[nuvem.cadastro]]), caixas de borda
  ([[nuvem.frota]]), passagens, visitas e casamento ([[nuvem.portaria]]), agendamentos
  ([[nuvem.agendamento]]), pátio e docas ([[nuvem.patio]]), mensagens ([[nuvem.mensagens]]),
  extrato ([[nuvem.extrato]]), demonstração ([[nuvem.demonstracao]]) e as telas
  ([[nuvem.web]]). Endereços em [[Rotas]]; banco em [[Tabelas do banco]] e
  [[Migrações do banco]].
- **Caixa de borda** ([[borda]], [[borda.leitor]]): captura, rastreamento, leitor v0, composição,
  fila de envio e o programa da caixa.
- **Contratos** ([[contratos]]): a Passagem v1, compartilhada entre a caixa e a nuvem.
- **Ferramentas** ([[tarefas]], [[simulador]]): os comandos do dia a dia, o simulador de
  portaria e o gerador deste vault.
- **Treino** ([[ml]]): baixar os pesos do v0 e o que vier do treino.

## O próximo passo

1. A sessão da identidade visual ([[Prompt da identidade visual]]): decide o nome, as cores e as
   fontes ([[ABERTO-01]]) e faz a [[T40]].
2. O Lorenzo abre as contas da Vercel e do Supabase ([[N17]]); então a [[T47]] e a [[T48]].
3. Depois da demonstração: as placas reais ([[ABERTO-18]]), o treino do leitor e o mês 4
   (WhatsApp de verdade, produção na AWS, caixa definitiva). Veja [[10. Cronograma (out-2026 – mar-2027)]].

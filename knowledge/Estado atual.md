---
tipo: "mapa"
escrita: "à mão"
atualizada: "2026-10-09"
tags: [estado]
---

# Estado atual

> [!info] Retrato de 09/10/2026 (SDD 0.58)
> Escrito à mão: o que entrou depois está nos PRs do GitHub e nos planos. Os checklists de "mês
> pronto" dos planos não foram marcados a cada tarefa; esta nota é a lista do que entrou.

## Em poucas linhas

- **Funciona de ponta a ponta, no ambiente local e com dados inventados:** o agendamento (link
  da transportadora e planilha), a passagem da caixa ou do simulador, o casamento com o
  agendamento, a exceção resolvida pela tela, a chegada manual, a fila, as docas, as mensagens ao
  motorista (num canal de demonstração, sem enviar nada), o painel e o extrato em R$, as telas
  "em breve" do recebimento e do estoque, o dia de demonstração e o link de demonstração por
  empresa, com a faixa que troca de papel ([[T48]], [[D-54]]).
- **A segurança antes da internet** está pronta ([[T47]], parte 1): código anti-CSRF
  ([[D-55]]), limite de login por endereço e o comando da administração. A verificação em duas
  etapas do gestor e da administração também ([[T51]], [[D-60]]).
- **O código da Vercel e do Supabase** está pronto ([[T47]], parte 2, [[D-56]]): o tique, as
  fotos pela API S3, o cron diário e a entrada da Vercel; o deploy segue o
  [[Guia da demonstração na internet]].
- **Falta para a demonstração no ar (mês 3):** o visual próprio ([[T40]], depois da identidade
  visual, [[ABERTO-01]]) e o deploy, que espera as contas da Vercel e do Supabase ([[N17]]).
- **O mês 4, a versão do piloto, está pronto no código** ([[Plano do mês 4]], [[D-57]] a
  [[D-75]]): a produção na AWS, o WhatsApp e o SMS, os alertas, a caixa em contêineres, a prova
  encadeada, a guarda, a base de treino e o cadastro do cliente. Subir e conferir de verdade
  espera as contas ([[N19]] a [[N21]] e [[N23]]).
- **O [[Plano do mês 5]], o piloto no site em modo sombra, espera a aprovação** do Lorenzo, com
  as decisões G1 a G7.
- **O leitor próprio vai para o site do piloto:** o treino e o teste técnico (as antigas
  [[T20]] a [[T26]], [[T36]] e [[T37]]) passam para o [[Plano do mês 5]], com as placas do
  próprio site, no modo sombra ([[ABERTO-18]]); o leitor v0, com pesos de terceiros, serve só
  para avaliação interna ([[D-26]]).
- **A caixa de borda** lê vídeo gravado e câmera RTSP, monta a passagem e envia com fila e
  reenvio, e manda a saúde a cada minuto, que aparece na frota de borda da administração
  ([[T54]], [[D-65]]); a medição no mini PC N150 ([[T70]], era a [[T20]]) espera o hardware.

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
| [[T20]] kit de bancada e medição no N150 | **passou para o mês 5** ([[T70]]); espera o hardware ([[N26]]) | |

Além das tarefas: as decisões de 04/10 ([[D-26]] a [[D-28]],
[#22](https://github.com/lorenzo265/patio-br/pull/22)), a leitura de vídeo e RTSP na caixa
([#23](https://github.com/lorenzo265/patio-br/pull/23)), o programa da caixa
([#24](https://github.com/lorenzo265/patio-br/pull/24)) e o OpenSSL do OpenCV ([[D-31]],
[#25](https://github.com/lorenzo265/patio-br/pull/25)).

## Mês 2: agendamento e casamento ([[Plano do mês 2]])

| Tarefa | Situação | PR |
|---|---|---|
| [[T21]] gravação no site parceiro | **passou para o mês 5** ([[T65]]), no site do piloto | |
| [[T22]] a [[T26]] rotulagem, régua e leitor v1 | **passaram para o mês 5** ([[T75]] e [[T66]] a [[T68]]), com as placas do site ([[ABERTO-18]]) | |
| [[T27]] agendamentos e a interface de conector | feita | [#27](https://github.com/lorenzo265/patio-br/pull/27) |
| [[T28]] link da transportadora | feita | [#28](https://github.com/lorenzo265/patio-br/pull/28) |
| [[T29]] importar planilha | feita | [#29](https://github.com/lorenzo265/patio-br/pull/29) |
| [[T30]] tela de agendamentos | feita | [#30](https://github.com/lorenzo265/patio-br/pull/30) |
| [[T31]] visita e eventos | feita | [#31](https://github.com/lorenzo265/patio-br/pull/31) |
| [[T32]] casamento | feita | [#32](https://github.com/lorenzo265/patio-br/pull/32) |
| [[T33]] fila de tarefas e worker | feita | [#33](https://github.com/lorenzo265/patio-br/pull/33) |
| [[T34]] exceções na portaria (só ver) | feita | [#34](https://github.com/lorenzo265/patio-br/pull/34) |
| [[T35]] simulador com agendamentos | feita | [#35](https://github.com/lorenzo265/patio-br/pull/35) |
| [[T36]] teste técnico e [[T37]] ajuste do casamento | **passaram para o mês 5** ([[T78]] e [[T77]]), no modo sombra | |
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
| [[T47]] demonstração na internet | o código feito (parte 1, segurança; parte 2, Vercel e Supabase); o deploy **espera as contas** ([[N17]]) | [#50](https://github.com/lorenzo265/patio-br/pull/50) e [#51](https://github.com/lorenzo265/patio-br/pull/51) |
| [[T48]] link por empresa | feita | [#49](https://github.com/lorenzo265/patio-br/pull/49) |

Além das tarefas: o plano ([#39](https://github.com/lorenzo265/patio-br/pull/39)), o relógio dos
testes ([#43](https://github.com/lorenzo265/patio-br/pull/43)), as decisões E2 a E4 no SDD 0.36
([[D-50]] a [[D-52]]) com o prompt da identidade visual
([#47](https://github.com/lorenzo265/patio-br/pull/47)) e este vault ([[D-53]]), num PR depois
dele.

## Mês 4: a versão do piloto ([[Plano do mês 4]])

O plano ([#52](https://github.com/lorenzo265/patio-br/pull/52)) foi aprovado em 06/10, com as
recomendações ([[D-57]] a [[D-62]]). As tarefas que não precisam de conta começam primeiro.

| Tarefa | Situação |
|---|---|
| [[T49]] produção e homologação na AWS | o código está pronto ([#64](https://github.com/lorenzo265/patio-br/pull/64), [[D-73]]); subir de verdade espera a conta da AWS e o domínio ([[N21]]) |
| [[T50]] cópias e alarmes | o código está pronto ([#65](https://github.com/lorenzo265/patio-br/pull/65), [[D-74]]): a cópia diária e a restauração de teste mensal pelo worker, a batida do worker no `/saude`, o registro em JSON sem placa nem telefone e os alarmes no CloudFormation; ligar de verdade espera a conta da AWS ([[N21]]) |
| [[T51]] verificação em duas etapas | feita ([#53](https://github.com/lorenzo265/patio-br/pull/53)) |
| [[T52]] WhatsApp | feita, com a Meta imitada ([#54](https://github.com/lorenzo265/patio-br/pull/54), [[D-63]]); a conferência com o número de teste espera a conta ([[N19]]) |
| [[T53]] SMS e o motorista não avisado | feita, com a Zenvia imitada ([#55](https://github.com/lorenzo265/patio-br/pull/55), [[D-64]]); a conferência de verdade espera a conta ([[N20]]) |
| [[T54]] saúde da caixa e frota de borda | feita ([#56](https://github.com/lorenzo265/patio-br/pull/56), [[D-65]]); a medição no N150 de verdade é a [[N23]] |
| [[T55]] a caixa em contêineres | feita ([#57](https://github.com/lorenzo265/patio-br/pull/57), [[D-66]]): as imagens montam na CI; a conferência num N150 de verdade é a [[N23]] |
| [[T56]] atualização da caixa | feita ([#58](https://github.com/lorenzo265/patio-br/pull/58), [[D-67]]): a primeira versão publicada espera a conta do GitHub com o registro ligado; a conferência num N150 é a [[N23]] |
| [[T57]] alertas | feita ([#59](https://github.com/lorenzo265/patio-br/pull/59), [[D-62]] e [[D-68]]): o modelo `patio_alerta` entra na lista para a Meta aprovar ([[N19]]) |
| [[T58]] prova encadeada | feita ([#60](https://github.com/lorenzo265/patio-br/pull/60), [[D-69]]): a trava de verdade das âncoras espera o balde da AWS com Object Lock ([[T49]]) |
| [[T59]] prazos de guarda e o pedido do titular | feita ([#61](https://github.com/lorenzo265/patio-br/pull/61), [[D-70]]): os prazos são parâmetros até o [[ABERTO-04]] |
| [[T60]] base de treino | feita ([#62](https://github.com/lorenzo265/patio-br/pull/62), [[D-71]]): com cliente, espera a cláusula do contrato ([[N22]]) |
| [[T39]] placas sintéticas | feita ([#63](https://github.com/lorenzo265/patio-br/pull/63), [[D-72]]): o crédito da Artificial Mercosur espera os nomes dos autores, ao baixar a base |
| [[T61]] API e webhooks | só se o cliente do piloto pedir |
| [[T62]] o roteiro do piloto em homologação (o marco) | o roteiro e o simulador como caixa estão prontos ([#66](https://github.com/lorenzo265/patio-br/pull/66)); rodar espera a homologação ([[N21]]) e a [[T63]] |
| [[T63]] o cadastro do cliente pela administração | feita ([#67](https://github.com/lorenzo265/patio-br/pull/67), [[D-75]]): tarefa nova, vinda da preparação da T62; a empresa, os sites, as portarias, as faixas, as câmeras, as docas e as pessoas, com o link de senha de uso único |

## Mês 5: o piloto no site, em modo sombra ([[Plano do mês 5]])

O plano espera a aprovação do Lorenzo, com as decisões G1 a G7:
- o leitor da sombra: o v1 e o comercial local para comparar;
- as placas reais do próprio site ([[ABERTO-18]]);
- o registro manual da portaria como gabarito;
- o que o sistema faz na sombra: tudo se grava, e nada sai ao motorista;
- a linha de base e as horas de portaria ([[ABERTO-05]]);
- a régua para ligar o check-in no mês 6;
- o hardware e a instalação.

As tarefas vão da [[T64]] à [[T78]]; nenhuma começa antes da aprovação.

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

1. O Lorenzo aprova o [[Plano do mês 5]] (G1 a G7). Depois, as tarefas que não precisam do
   site: o modo sombra ([[T64]]), a gravação ([[T65]]), o leitor v1 ([[T66]] a [[T68]], com a
   conta da GPU, [[N27]]), o comercial local ([[T69]]), o PWA ([[T71]]), o registro manual
   ([[T72]]) e a linha de base ([[T73]]).
2. As contas e o contrato: a AWS e o domínio ([[N21]]), o advogado ([[N22]]) e o piloto fechado
   ([[N24]]). Com eles, o roteiro do piloto na homologação ([[T62]]) e a instalação ([[T74]]).
3. A sessão da identidade visual ([[Prompt da identidade visual]]): decide o nome, as cores e as
   fontes ([[ABERTO-01]]) e faz a [[T40]].
4. O Lorenzo abre as contas da Vercel e do Supabase ([[N17]]); então o deploy da demonstração,
   pelo [[Guia da demonstração na internet]]. Veja [[10. Cronograma (out-2026 – mar-2027)]].

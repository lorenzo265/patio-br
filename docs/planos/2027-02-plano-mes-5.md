# Plano do mês 5: o piloto no site, em modo sombra

Plano de implementação do mês 5 do cronograma do SDD (`docs/SDD.md`, seção 10).
Versão 1 · 2026-10-09 · **Rascunho para aprovação do Lorenzo**

---

## 1. Objetivo e marco

**Objetivo:** a caixa e as 6 câmeras no site do piloto, em **modo sombra** por 2 a 4 semanas.
Nesse tempo, o trabalho da portaria não muda (SDD 9, item 6). No mês:
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
- **O contrato:** o piloto fechado (N24), com o contrato e o acordo de tratamento de dados
  assinados (`[ABERTO-07]`) e a cláusula do treino (SDD 8.3; o sim do advogado, N22). Sem
  isso, nenhum dado do cliente entra na produção.
- **A produção:** no ar na AWS (N21), com o roteiro do piloto rodado na homologação (o marco do
  mês 4, T62).
- **O WhatsApp e o SMS não são necessários neste mês.** No modo sombra nada sai ao motorista (G4),
  e as contas da Meta e do SMS (N19 e N20) ficam para o mês 6.

**O que fica do mês 4**, em paralelo com este plano:
- o visual próprio (T40), na sessão da identidade visual (`[ABERTO-01]`);
- o deploy da demonstração (N17);
- a API e os webhooks (T61), só se o cliente do piloto pedir;
- as conferências de verdade, que esperam as contas: a homologação e a produção (N21), a caixa
  num N150 (N23), a Meta (N19) e o SMS (N20).

**Fora do mês 5:**
- **O check-in automático ligado, o WhatsApp ativo e o primeiro extrato real:** são o mês 6
  (SDD 10).
- **A foto de contexto com os rostos borrados:** espera um modelo de rostos com pesos nossos
  (SDD 4.1). A caixa segue mandando só o recorte da placa.
- **O SSE (D-09):** as telas continuam perguntando ao servidor a cada 2 ou 3 segundos.
- O modo B e as fases seguintes (SDD 3.5).

**Riscos do mês e o plano B:**

| Risco | Plano B |
|---|---|
| o piloto não fecha a tempo | a mesma sombra num portão de conhecidos (a coleta própria do `[ABERTO-18]`, com o sim do advogado); mede e treina o leitor, mas não dá a linha de base |
| o v1 do começo, treinado sem placas reais, lê mal | é o esperado; a sombra não decide nada; o comercial local mede o plano B desde o primeiro dia (G1), e o retreino semanal usa as placas do site |
| a noite lê mal | ajustar o infravermelho e o obturador (T70), treinar de novo com as placas da noite e, se não bastar, levar à decisão de ligar (G6) |
| a internet do site é fraca para subir as gravações | subir com limite de banda, à noite; ou tirar as gravações da caixa pela Tailscale |
| o cliente não aceita o registro manual em planilha | conferir pela foto uma amostra maior; o que a câmera não viu fica sem medida, e o relatório diz isso |

---

## 2. Antes de começar: decisões do Lorenzo

| # | Decisão | Trava | Recomendação | Decidido em |
|---|---|---|---|---|
| G1 | **Que leitor a caixa leva para o modo sombra.** O v0 não vai para o produto (D-26), e o teste técnico (a antiga T36) não aconteceu: o nosso leitor nunca foi medido em placas reais. | T68, T69, T78 | **Os dois na caixa:** o v1 (pesos nossos) é o leitor da caixa; o Plate Recognizer, pelo programa local (US$ 50 por mês, sem mandar imagem para fora, D-41), lê as mesmas passagens só para comparar. O que ele lê nunca vira rótulo. Assim, o teste técnico acontece no próprio site, em passagens reais. A tabela da seção 10 do SDD vale no fim: com o nosso a 95% ou mais, o mês 6 liga com o nosso; abaixo, liga com o comercial, se ele chegar à régua da G6, e o nosso segue treinando. As alternativas: **só o v1**, mais barato, mas sem plano B medido (o mês 6 poderia ter de começar com um leitor nunca visto no site); **só o comercial**, que mede o plano B, mas não deixa medir o nosso nem o retreino no lugar. | — |
| G2 | **De onde vêm as placas reais** (`[ABERTO-18]`). | T65, T75, T76 | **Do próprio site do piloto**, com a cláusula do treino no contrato (D-71) e o sim do advogado. A caixa grava a região de gravação de cada passagem (D-39), e as gravações sobem para a base de treino. O Lorenzo rotula, e a régua fixa sai das mesmas passagens, separada antes do treino. São as placas que mais importam: as da câmera, da luz e da portaria onde o leitor vai trabalhar. Os portões de conhecidos e a frota parada ficam como plano B, se o piloto atrasar. A alternativa é começar pela frota parada e pelos portões: tem placas antes, mas de outra câmera e de outro ângulo, e pede outra autorização para cada lugar. | — |
| G3 | **Como medir o acerto real** (o gabarito). | T72, T78 | **O registro manual da portaria, com a conferência pela foto.** A portaria já anota quem entra (caderno, planilha ou o sistema dela); durante a sombra, esse registro vem numa planilha. O sistema compara com o que a câmera viu. O Lorenzo confere pela foto só o que diverge, mais 1 em cada 10 dos que concordam, para conferir que concordar é acertar. É o único jeito de achar o caminhão que a câmera não viu, e não pede trabalho novo ao porteiro. As alternativas: **o porteiro confere toda passagem no tablet**, com um gabarito melhor, mas é trabalho a mais no posto que o cliente quer reduzir, e muda o processo que a sombra só deveria observar; **o Lorenzo confere tudo pela foto**: são cerca de 3.600 visitas por mês, e não acha o que a câmera não viu. | — |
| G4 | **O que o sistema faz no modo sombra.** | T64, T74 | **Tudo roda e se grava, mas nada sai.** O casamento, o check-in que seria automático, as exceções e a saída acontecem como no mês 6. Mas nenhuma mensagem vai ao motorista, nem a confirmação nem o SMS, e nenhum alerta vai ao gestor por WhatsApp. O painel mostra tudo, com a faixa "modo sombra", e os alertas da caixa e das câmeras chegam a nós. O porteiro não usa o tablet. Os agendamentos entram pela planilha do cliente, todo dia (a importação da T29), ou pela API (T61), se o cliente pedir. Na última semana, se o cliente quiser, um ensaio: o porteiro usa o tablet ao lado do registro de sempre, para chegar treinado ao mês 6. A alternativa é já avisar o motorista na sombra: mede o WhatsApp antes, mas um aviso nascido de um check-in errado confunde o motorista e o porteiro. | — |
| G5 | **Como medir a linha de base do extrato e as horas de portaria** (SDD 5.4 e `[ABERTO-05]`). | T73 | **Nas 2 últimas semanas da sombra, com o mesmo instrumento do depois:** a chegada e a saída pelas câmeras; a chamada, o início e o fim na doca marcados pelo líder de pátio na tela do pátio (a única mudança pedida ao cliente na sombra); as toneladas, dos agendamentos. **A portaria, pela escala:** postos × horas, no contrato do serviço de portaria ou na escala da equipe própria, antes (na sombra) e depois. O custo do posto vem do mesmo contrato, e o gestor informa, com o documento. Sem as marcas do líder, a linha de base fica só com o tempo no site e a espera fica sem medida; o extrato diz isso. A alternativa é tirar a linha de base do histórico do cliente (os meses de antes, no sistema dele): a amostra é maior, mas medida com outro instrumento (a hora anotada à mão contra a hora da câmera), o que pode inventar ou esconder economia. | — |
| G6 | **A régua para ligar o check-in automático no mês 6.** | T78 | **Liga quando, em pelo menos 7 dias seguidos da sombra, com a mesma versão do leitor, de dia e de noite, e com pelo menos 500 composições conferidas:** (1) a composição certa casando com o agendamento fica em 95% ou mais (a meta do SDD 4.7; com 500, a margem é de cerca de 2 pontos); (2) o check-in automático errado, no agendamento errado, fica em até 1 em 200; (3) as chegadas agendadas com check-in sem o porteiro chegam a 70% ou mais (SDD 1.5). Liga com o leitor que cumpriu (G1). Se nenhum cumprir, mais 2 semanas de sombra, com o ajuste (câmera, retreino), e o mês 6 encurta. A alternativa é olhar só a meta de 95%: mas um check-in errado é pior que uma exceção, porque o caminhão errado vai para a doca e a prova fica errada. | — |
| G7 | **O hardware e a instalação.** | T70, T74 | **Nós compramos o hardware, que fica nosso, emprestado ao site pelo tempo do contrato, e entra no preço do piloto** (`[ABERTO-06]`). As peças: a caixa N150, 6 câmeras IP de 4 MP com lente varifocal, infravermelho e obturador ajustável, de uma marca com assistência no Brasil, o switch PoE, o nobreak, o roteador 4G e um tablet Android de 10" com suporte. As câmeras são conferidas antes na bancada. **Um integrador de CFTV da região** passa os cabos e fixa as câmeras, pelo nosso guia (T70); o cliente costuma ter um. Nós configuramos e conferimos o enquadramento. A alternativa é o cliente comprar pela nossa lista: não prende o nosso dinheiro, mas cada site fica diferente, e trocar uma peça demora. | — |

---

## 3. Como trabalhar neste plano

As mesmas regras dos meses anteriores (`CLAUDE.md`), com estes ajustes:

- **Numeração:** as tarefas continuam de onde pararam, a partir da T64. As tarefas do leitor que
  esperavam as placas reais ganham números novos aqui:
  - a medição no N150 (T20) vira a T70;
  - a gravação (T21) vira a T65;
  - a rotulagem e a régua (T22 e T23) viram a T75;
  - o detector, o OCR e o leitor v1 (T24, T25 e T26) viram a T66, a T67 e a T68;
  - o teste técnico (T36) vira a T78, e o ajuste do casamento (T37), a T77.

  Os planos dos meses 1 e 2 mostram as antigas riscadas, com a tarefa para onde foram. As
  branches levam `mes5/` (ex.: `mes5/t64-modo-sombra`).
- **O primeiro dado real:** a partir da instalação, a produção guarda dados do cliente. Nada
  disso entra no Git (regra 3):
  - os relatórios no repositório só levam números;
  - as fotos e as gravações ficam no armazenamento da nuvem;
  - a máquina de GPU alugada recebe só a pasta da base de treino (D-71) e a apaga ao terminar;
  - os testes continuam com dados inventados.
- **O treino** roda no ambiente à parte (D-40), com código de licença Apache, MIT ou BSD.
  - **Os pesos de partida:** do zero, ou de um ponto de partida com licença conferida, nunca os
    pesos do v0 nem outros sem licença declarada (D-26).
  - **A régua (SDD 4.7):** cada versão nova do leitor só vai à caixa se não piorar a régua.
    O primeiro v1 é a exceção: entra na sombra sem régua, porque ali ele não decide nada.
- **Cada ida ao site e cada versão mandada à caixa** entram no PR da tarefa: o que foi feito e os
  números, sem placas nem fotos.
- **O que a execução decidir vira uma D-nn** no SDD, no mesmo PR, como nos meses anteriores.

---

## 4. Tarefas técnicas

### Semana 1 — antes de instalar

#### T64. O modo sombra do site

**Objetivo:** o site roda inteiro sem mudar o trabalho de ninguém e sem falar com ninguém de
fora (G4).

**Depende de:** G4.

**Arquivos:**
- `nuvem/src/nuvem/cadastro/` (o modo do site, com a migração);
- `nuvem/src/nuvem/mensagens/` e `nuvem/src/nuvem/alertas/` (o que não sai na sombra);
- `nuvem/src/nuvem/web/` (a faixa nas telas e a troca de modo na administração);
- testes.

**Regras (teste primeiro):**
- **O modo:** cada site tem um, `sombra` ou `ligado`.
  - O site cadastrado pela administração (T63) nasce em sombra; os da semente e da
    demonstração nascem ligados.
  - Só a administração muda o modo, com o motivo.
  - Cada mudança fica registrada (quem, quando, de qual para qual) e não se apaga.
- **Na sombra, a nuvem faz tudo igual:** recebe as passagens, casa, cria a visita (check-in pelo
  sistema ou exceção) e fecha na saída. O pátio e o painel funcionam.
- **Na sombra, nada sai para fora:**
  - nenhuma mensagem ao motorista (nem a confirmação, nem por SMS);
  - nenhum alerta ao gestor por WhatsApp;
  - os alertas da caixa e das câmeras para a administração continuam.
- **O que deixou de sair não sai depois** (D-47: aviso velho não sai). Ao ligar, só os eventos
  novos geram mensagens.
- **As telas do cliente** mostram a faixa "Modo sombra: o registro oficial continua o de
  sempre".
- **Separação de clientes:** o modo é do site; a troca é da administração, pelo `AcessoAdmin`.

**Verificar:** com o simulador, um site em sombra faz o check-in e não grava nenhuma mensagem
para mandar; ligado, manda.

**Commit:** `feat(cadastro): o modo sombra do site`

#### T65. A região de gravação e a gravação para treino (era a T21)

**Objetivo:** com a cláusula do treino, a caixa grava a região de gravação de cada passagem e a
manda para a base de treino (G2).

**Depende de:** G2 e a cláusula registrada (D-71).

**Arquivos:**
- o campo da região de gravação no cadastro da câmera (nuvem, na tela da T63, com a
  migração) e na configuração da caixa;
- `borda/src/borda/gravacao.py`;
- a rota que recebe as gravações (`nuvem/src/nuvem/treino/`);
- testes.

**Regras (teste primeiro):**
- **A região de gravação** é um retângulo no quadro da câmera, abaixo do para-brisa (D-39).
  - A administração a marca no cadastro, em frações da largura e da altura, para não mudar com
    a resolução.
  - Câmera sem região marcada não grava.
- **Só o que está dentro da região** vai para o disco.
- **Grava por passagem:**
  - os quadros amostrados de cada veículo, em JPEG, com a leitura do v1 ao lado (o
    pré-rótulo);
  - começa quando o detector vê o veículo ou quando há movimento na faixa, o que vier antes:
    o v1 do começo pode não ver o veículo.
- **Só grava com a autorização da empresa registrada** (D-71); a caixa sabe pela configuração.
  Revogar para a gravação, e a nuvem apaga o que veio daquela empresa.
- **Sobe sozinha para a base de treino** (a pasta à parte, D-71), depois de a fila das passagens
  esvaziar e com limite de banda. Isso muda a regra da antiga T21 ("nada sobe sozinho"), escrita
  para um site sem contrato; aqui a cláusula autoriza.
- **O disco tem limite:** acima dele, as gravações já enviadas se apagam primeiro; depois, as
  mais antigas, com registro.
- **Na nuvem,** as gravações seguem a guarda da base de treino (D-71), não a das fotos.

**Verificar:** com um vídeo inventado, só a região chega à pasta e à nuvem; sem a autorização,
nada se grava.

**Commit:** `feat(borda): gravação para treino, só da região de gravação`

#### T66. Detector v1 (era a T24)

**Objetivo:** o detector de veículo e de placa com pesos nossos, e a escolha do `[ABERTO-03]`.

**Depende de:** N27 (a conta da GPU).

**Arquivos:**
- `ml/treino/` (o ambiente à parte, D-40: os requisitos, o treino e a exportação);
- `ml/src/ml/bases_abertas.py` (baixar e converter as bases abertas da D-44);
- `docs/validacao/detector-v1.md` (só números);
- testes.

**Regras:**
- **O primeiro treino** usa as bases abertas: Open Images (anotações CC BY 4.0) e CCPD (MIT),
  guardando só a região da placa (D-44). Os seguintes acrescentam as gravações do site (T76).
  Os créditos que as licenças pedem vão para `ml/CREDITOS.md`.
- **Os dois modelos:** treinar o D-FINE-N e o YOLOX-Tiny (código Apache-2.0) na GPU alugada,
  com os pesos de partida da seção 3.
- **A exportação e a medição:** exportar em ONNX e medir os dois na régua (T75) e no N150 (T70).
- **A escolha:** fica o de melhor acerto que der pelo menos 5 quadros por segundo por câmera no
  N150, com as 6 câmeras ligadas. Isso fecha o `[ABERTO-03]`.
- **O teste:** um treino curto, em CPU e com imagens inventadas, que sai em ONNX.

**Commit:** `feat(ml): treino do detector v1`

#### T67. OCR v1 (era a T25)

**Objetivo:** a leitura da placa com pesos nossos.

**Depende de:** N27.

**Arquivos:** `ml/treino/`, `docs/validacao/ocr-v1.md` (só números), testes.

**Regras:**
- **O modelo:** no estilo do fast-plate-ocr (código MIT), com os pesos de partida da seção 3.
- **O treino:** com as placas sintéticas (T39) e a Artificial Mercosur (CC BY 4.0); depois,
  com as placas do site (T76).
- **As placas:** antiga e Mercosul. Exportação em ONNX.
- **A medição:** na régua, por caractere e por placa, de dia e de noite.

**Commit:** `feat(ml): treino do OCR v1`

#### T68. Leitor v1 na caixa, com os pesos na versão (era a T26)

**Objetivo:** a caixa lê com o v1, e os pesos novos chegam à caixa pela atualização, com volta.

**Depende de:** T66 e T67.

**Arquivos:**
- `borda/src/borda/leitor/v1.py`;
- `borda/atualizador.py` e a versão da caixa na nuvem (`nuvem/src/nuvem/frota/`, com a
  migração);
- `docs/SDD.md` (seção 7.4, o SDD primeiro);
- testes.

**Regras (teste primeiro):**
- **A interface:** a mesma do v0 (`LeitorDePlacas` e `DetectorDeVeiculos`).
- **O motor:** roda no OpenVINO (Apache-2.0, SDD 4.4), com o ONNX Runtime de reserva. Antes,
  conferir as bibliotecas nativas da roda (D-27) e anotar os créditos em
  `borda/AVISOS-DE-TERCEIROS.md`.
- **A passagem** leva `versao_leitor="v1"` e a versão dos pesos.
- **Os pesos vão na versão da caixa** (D-67):
  - a versão ganha o pacote de pesos: o endereço no nosso armazenamento e o resumo SHA-256;
  - o atualizador baixa e confere os pesos antes de trocar o agente;
  - a volta devolve a imagem e os pesos anteriores.

**Verificar:** uma versão com pesos novos chega à caixa de teste; com pesos de resumo errado,
a caixa não troca.

**Commit:** `feat(borda): leitor v1 com pesos nossos, entregues pela atualização`

#### T69. O leitor comercial local, só para comparar

**Objetivo:** o Plate Recognizer, pelo programa local, lê as mesmas passagens que o v1, para o
teste técnico no site, e fica pronto como plano B (D-07, G1).

**Depende de:** G1 e N27 (a conta do Plate Recognizer).

**Arquivos:**
- `borda/src/borda/leitor/comercial.py` (o motor atrás da `LeitorDePlacas`);
- o serviço no compose da caixa (`infra/caixa/`);
- o envio da leitura de comparação à nuvem;
- testes, com o serviço imitado.

**Regras (teste primeiro):**
- **O programa local** roda na caixa, num contêiner, e não manda imagem para fora (D-41). É um
  serviço pago à parte, como o WhatsApp, e não uma dependência do nosso código (SDD 4.5).
- **Na comparação:**
  - lê o melhor recorte de cada veículo, e não cada quadro: cerca de 11 mil leituras por mês,
    dentro do plano de 50 mil (SDD 7.6);
  - a leitura vai à nuvem marcada como de comparação; não entra na composição nem no
    casamento;
  - segue a guarda das fotos;
  - nunca vira rótulo nem entra no treino (D-41; os termos de uso dele, item 1.7).
- **Como plano B:** a configuração da caixa escolhe o leitor principal (o v1 ou o comercial).
  Trocar não muda nada fora da caixa (SDD 4.5).
- **O formato:** se o contrato da passagem ganhar um campo, ele é opcional, e o SDD 3.2 muda
  primeiro. Detalhar na execução.

**Commit:** `feat(borda): leitor comercial local, para comparar`

#### T70. A caixa do piloto na bancada: a medição no N150 e o enquadramento (era a T20)

**Objetivo:** medir o v1 no N150 com 6 câmeras e escrever o guia de instalação (`[ABERTO-08]`),
com um comando que confere o enquadramento de cada câmera.

**Depende de:** N26 (o hardware), T68 e N29 (a visita ao site).

**Arquivos:**
- `borda/src/borda/enquadramento.py` (o comando `caixa enquadrar`);
- `docs/guias/instalar-no-site.md`;
- `docs/validacao/fatos-tecnicos-stack.md` (as medições próprias);
- testes.

**Regras:**
- **A medição:** com o v1 no OpenVINO e no ONNX Runtime, com 6 câmeras ao mesmo tempo:
  - os quadros por segundo por câmera (pelo menos 3, SDD 4.4);
  - a CPU e a temperatura.
- **`caixa enquadrar --camera <id>`:**
  - pega um quadro, roda o detector e grava uma imagem com a região de gravação desenhada e a
    largura da placa em pixels;
  - a largura mínima sai da régua do v1 por tamanho de placa;
  - a imagem fica só na caixa (pode ter pessoas) e não sobe para a nuvem.
- **O guia:**
  - altura, ângulo, distância, lente, infravermelho e obturador de cada câmera;
  - a região de gravação e a ordem da instalação;
  - os números saem da bancada.
  - Ele fecha o `[ABERTO-08]` para a portaria do piloto.

**Verificar:** o comando com quadros inventados mede a placa e desenha a região.

**Commit:** `feat(borda): conferir o enquadramento da câmera`, e
`docs: medição no N150 e o guia de instalação`

### Semana 2 — a instalação

#### T71. O PWA dos tablets

**Objetivo:** a portaria e o pátio abrem no tablet como um aplicativo, em tela cheia e com a tela
sempre acesa (D-09), antes de os tablets chegarem ao site.

**Arquivos:**
- `nuvem/src/nuvem/web/estatico/` (o manifesto, os ícones e o service worker);
- `nuvem/src/nuvem/web/telas/` (o modelo das telas);
- testes.

**Regras (teste primeiro):**
- **O manifesto:** abre em tela cheia, com o nome e os ícones do produto. Os ícones são feitos
  por nós, ou vêm com o visual (T40).
- **O service worker:**
  - guarda só os arquivos estáticos;
  - sem internet, mostra "sem conexão" no lugar da tela;
  - nunca guarda uma página com dados do cliente nem a sessão.
- **A tela da portaria e a do pátio** pedem ao navegador para ficarem acesas.
- **Funcionar sem internet** fica de fora: toda ação precisa da nuvem. O SSE continua de fora.

**Verificar:** no Chrome do Android, "Adicionar à tela inicial" abre em tela cheia; sem
internet, aparece o aviso.

**Commit:** `feat(web): o painel instalável nos tablets`

#### T72. O registro manual e a conferência das divergências

**Objetivo:** comparar o que a câmera viu com o registro da portaria e conferir pela foto o que
diverge (G3).

**Depende de:** G3 e N25 (o registro combinado com o cliente).

**Arquivos:**
- `nuvem/src/nuvem/sombra/` (módulo novo: o registro manual, a comparação e a conferência, com a
  migração);
- `nuvem/src/nuvem/web/` (a tela do gestor para mandar a planilha e a tela da administração
  para conferir);
- testes.

**Regras (teste primeiro):**
- **O registro manual** entra por planilha (CSV ou XLSX, como a T29), só enquanto o site está em
  sombra.
  - As colunas: o dia, a hora de entrada, as placas (cavalo e reboques, se houver) e a hora de
    saída (se houver).
  - Linha com erro volta com o motivo.
- **A comparação:** cada linha do registro procura a passagem de entrada do site numa janela de
  tempo (padrão: 10 minutos para cada lado), pela placa igual ou parecida (a distância da seção
  5.3). Há quatro resultados:
  - **concorda:** a placa lida é a anotada;
  - **diverge:** há passagem na janela, com a placa diferente;
  - **a câmera não viu:** nenhuma passagem na janela;
  - **o registro não tem:** a câmera viu, e o registro não.
- **A conferência** é da administração.
  - **A tela:** cada divergência mostra o recorte, a leitura do comercial, se houver (G1), a
    placa anotada e a lida.
  - **As respostas:** "a câmera leu certo", "o registro está certo", "placa ilegível na foto"
    ou a placa certa, digitada.
  - **A amostra:** entra também 1 em cada 10 concordâncias, sorteadas pelo resumo, como na régua
    da D-71.
- **A conferência é um registro novo:** o registro manual e a leitura não mudam (SDD 5.5). Com a
  cláusula do treino (D-71), a placa conferida vira um rótulo a revisar, como a do porteiro.
- **A guarda:** o registro manual segue a das fotos (90 dias, D-70).
- **Separação de clientes:** tudo com `empresa_id` e a dupla (pai, empresa). O gestor só manda
  a planilha do próprio site. A administração lê pelo `AcessoAdmin`.

**Verificar:** com um registro inventado e o simulador, os quatro resultados aparecem, e a
conferência muda o acerto.

**Commit:** `feat(sombra): o registro manual e a conferência das divergências`

#### T73. Os parâmetros do extrato e a linha de base medida

**Objetivo:** o gestor informa os parâmetros do site, e a administração grava a linha de base
medida na sombra (G5). A D-75 deixou isto para o mês 5.

**Depende de:** G5 e T64.

**Arquivos:**
- `nuvem/src/nuvem/extrato/` (gravar os parâmetros e medir a linha de base, com a migração, se
  precisar);
- `nuvem/src/nuvem/web/` (a tela dos parâmetros do gestor e a da linha de base na
  administração);
- testes.

**Regras (teste primeiro):**
- **Os parâmetros do site** são do gestor (SDD 2.1): o valor da estadia (R$ por t·h), os postos
  de portaria antes e depois, o custo mensal do posto e o custo da hora-doca.
  - Cada mudança fica registrada (quem, quando, o valor de antes e o novo).
  - O mês fechado guarda os parâmetros que usou (D-48) e não muda.
- **A linha de base:**
  - a administração escolhe o período, dentro da sombra (o padrão é as 2 últimas semanas);
  - vê as medidas e quantas visitas entraram em cada uma (quantas foram liberadas, quantas
    tinham toneladas) antes de gravar;
  - grava com a origem "modo sombra".
- **Uma linha de base nova não apaga a anterior:** o extrato fechado guarda a que usou (D-48).
- **Pouca visita:** com menos de 100 visitas liberadas no período, a tela avisa que a medida é
  fraca.
- **Separação de clientes:** o gestor só vê e muda o próprio site.

**Verificar:** com o histórico inventado da demonstração, a linha de base medida bate com a
conta feita à mão (SDD 9, item 1).

**Commit:** `feat(extrato): os parâmetros do site e a linha de base medida`

#### T74. A instalação no site e o começo do modo sombra

**Objetivo:** a caixa e as 6 câmeras no ar no site do piloto, em sombra (G4 e G7).

**Depende de:** o contrato (seção 1), N21, N26, N28, T64, T68, T70 e, se G1, T69.

**Arquivos:** `docs/guias/instalar-no-site.md` (o que a instalação ensinar) e
`docs/validacao/instalacao-piloto.md` (o que deu certo e os números, sem placas nem fotos de
pessoas).

**Passos:**
1. A caixa preparada (`infra/caixa/autoinstall.yaml`), ativada na produção com o código do site,
   e o site em sombra.
2. As câmeras fixadas pelo integrador; a região de gravação e o enquadramento conferidos com o
   `caixa enquadrar`, de dia e de noite.
3. A placa de aviso na portaria (N28). A gravação para treino só liga depois da cláusula
   registrada (D-71).
4. O tablet com o PWA (T71), para o ensaio da última semana (G4) e para o mês 6.

**Verificar:**
- as 6 câmeras no ar na frota, de dia e de noite;
- um veículo de teste passa nas duas faixas de entrada e numa de saída, e as passagens
  aparecem;
- tirar a internet principal: a caixa segue pela de reserva;
- tirar as duas por 10 minutos: nada se perde;
- tirar a energia: o nobreak segura e, quando a energia volta, a caixa volta sozinha (o TPM,
  D-66).

**Commit:** `docs: a instalação no site do piloto`

### Semanas 3 e 4 — medir e treinar de novo

#### T75. Rotulagem e régua fixa (eram a T22 e a T23)

**Objetivo:** rotular rápido as gravações do site e separar a régua, que nunca entra no treino
(SDD 4.7).

**Depende de:** G2, T65 e as primeiras gravações.

**Arquivos:**
- o Label Studio no `infra/docker-compose.yml` (fora do `tarefas up` comum) e o comando
  `tarefas rotulagem`;
- `ml/src/ml/rotulagem.py`, `ml/src/ml/regua.py` e `ml/src/ml/avaliar.py`;
- `docs/validacao/regua.md` (o manifesto, sem placas);
- testes.

**Regras (teste primeiro):**
- **As caixas do detector:** o Label Studio (edição comunitária, Apache-2.0) roda na máquina do
  Lorenzo, com os dados em `dados/`.
- **O texto das placas:** a tela de rotulagem da nuvem, que já existe (T60).
- **O pré-rótulo** vem do v1, nunca do comercial (D-41).
- **A régua:**
  - segue a da D-71: pelo resumo, estável;
  - uma passagem vai inteira para a régua ou inteira para o treino (as conferências e as
    gravações dela);
  - a exportação de treino recusa qualquer arquivo da régua (o manifesto tem o resumo de cada
    um);
  - meta de 1.000 placas na régua, de dia e de noite: com 1.000, a margem do acerto de 97% é de
    cerca de 1 ponto.
- **`avaliar.py`** mede um leitor na régua: por placa, por caractere e por composição; de dia e
  de noite.

**Verificar:** com rótulos inventados, a separação não muda entre rodadas, e um arquivo da régua
no treino dá erro.

**Commit:** `feat(ml): rotulagem e régua fixa com as placas do site`

#### T76. O retreino com as placas do site

**Objetivo:** a cada semana da sombra, treinar de novo com as placas novas e mandar à caixa só
o que não piora a régua.

**Depende de:** T66, T67, T68 e T75.

**Arquivos:** `ml/treino/` e `docs/validacao/retreino-piloto.md` (só números).

**Regras:**
- **Os dados:** a pasta do `tarefas treino` (D-71) mais as gravações rotuladas (T65 e T75),
  menos a régua.
- **A régua decide:** a versão nova só vai à caixa se não piorar o acerto por placa nem o por
  composição (SDD 4.7).
- **A entrega:** pela versão da caixa com os pesos novos (T68).
- **Cada versão** guarda o resumo do conjunto de treino que usou, para poder ser refeita.

**Commit:** `feat(ml): retreino com as placas do site`

#### T77. Ajuste do casamento (era a T37)

**Objetivo:** fechar o `[ABERTO-02]`: os pesos e o limite do casamento, com os dados da sombra.

**Depende de:** T72 (as composições conferidas).

**Arquivos:**
- `docs/SDD.md` (seção 5.3, o SDD primeiro);
- `nuvem/src/nuvem/portaria/casamento.py`;
- `docs/validacao/casamento-piloto.md` (só números);
- testes.

**Regras (teste primeiro):**
- **A escolha:** os pesos que deixam o check-in errado dentro da régua da G6 e dão mais
  check-ins automáticos.
- **A conta:** refeita sobre as composições conferidas da sombra; só os números entram no
  repositório.
- **Os testes** do casamento ganham os casos que a sombra mostrar, com placas inventadas.

**Commit:** `feat(portaria): pesos do casamento ajustados com os dados do piloto`

#### T78. O acerto real medido e a decisão de ligar (era a T36; o marco)

**Objetivo:** o relatório do acerto real e a decisão do mês 6, pela régua da G6.

**Depende de:** G1, G3, G6, T72, T75 e pelo menos 2 semanas de sombra.

**Arquivos:**
- o relatório na administração (`nuvem/src/nuvem/sombra/`);
- `docs/validacao/teste-tecnico-piloto.md` (só números);
- `docs/SDD.md` (a decisão, numa D-nn).

**Regras (teste primeiro, nas contas):**
- **Por versão do leitor e pelo comercial (G1), de dia e de noite**, com a margem de erro de 95%:
  - o acerto por placa visível (meta: 97% ou mais);
  - a composição certa casando com o agendamento (meta: 95% ou mais);
  - o check-in automático errado (G6);
  - as chegadas agendadas com check-in sem o porteiro (meta: 70% ou mais);
  - os caminhões que a câmera não viu;
  - os quadros por segundo e a CPU da caixa, pela saúde.
- **A decisão** sai pela régua da G6: ligar com o nosso leitor, ligar com o comercial, ou mais 2
  semanas de sombra.
  - Ela vai para o SDD e para o plano do mês 6.
  - Ela também diz se a meta de 70% muda (SDD 1.5: "revisável após o modo sombra").

**Commit:** `docs: o acerto real medido no piloto e a decisão de ligar`

---

## 5. Trilha não técnica

| # | Tarefa | Por quê | Resolve |
|---|---|---|---|
| N25 | Combinar o modo sombra com o cliente: as datas; o aviso aos porteiros e ao líder de pátio; o registro manual numa planilha (G3); as marcações do líder na tela do pátio (G5); a planilha diária dos agendamentos (G4); os parâmetros do extrato e a escala da portaria (G5, `[ABERTO-05]`); os tempos dos alertas (`[ABERTO-09]`) | o gabarito, a linha de base e os agendamentos dependem do cliente | T72, T73, T74, `[ABERTO-05]`, `[ABERTO-09]` |
| N26 | Comprar o hardware do site (G7): a caixa N150, as 6 câmeras, o switch PoE, o nobreak, o rack, o roteador 4G com o chip e o tablet com suporte. Contratar o integrador de CFTV | o prazo de entrega e a instalação | T70, T74 |
| N27 | Abrir a conta da GPU por hora (N11) e a do Plate Recognizer, com o programa local (G1, US$ 50 por mês) | o treino e a comparação | T66, T67, T69, T76 |
| N28 | Fazer a placa de aviso da portaria, com o contato do encarregado e o uso para treino, e o relatório de impacto (RIPD) para o cliente (SDD 8.3); o advogado confere (N22) | a transparência da LGPD antes da primeira câmera | T65, T74 |
| N29 | Visitar o site antes da instalação: as faixas e onde ficam as câmeras, a energia, a rede, o lugar da caixa e a internet de reserva. Fotos só para o guia, sem placas nem pessoas | o guia de instalação e a lista de compras | T70, T74, `[ABERTO-08]` |
| N30 | Reservar as horas de rotular: a régua (cerca de 1.000 placas), as divergências da sombra e as caixas do detector, ao longo de 3 semanas | sem rótulo não há régua nem retreino | T72, T75, T76 |

---

## 6. Ajustes no SDD feitos junto com este plano

- **No SDD 0.58:**
  - o cronograma do mês 5 (seção 10) com o que este plano traz: o leitor v1 e o teste técnico,
    que esperavam as placas reais desde o mês 2, vêm para o modo sombra do site do piloto, com o
    comercial local para comparar, o registro manual, a gravação para treino, os parâmetros e a
    linha de base e o PWA dos tablets;
  - as propostas para o `[ABERTO-05]` (G5) e o `[ABERTO-18]` (G2), na seção 12;
  - os novos prazos do `[ABERTO-02]`, do `[ABERTO-03]`, do `[ABERTO-08]` e do `[ABERTO-09]`.
- **Com a aprovação:**
  - as decisões G1 a G7 viram D-nn;
  - o modo sombra entra nas seções 5.4 e 9;
  - o leitor da sombra e a comparação entram nas seções 4.5 e 4.7;
  - as placas do site entram na seção 4.6;
  - o `[ABERTO-05]` e o `[ABERTO-18]` fecham.

---

## 7. Checklist de "mês 5 pronto"

- [ ] G1 a G7 decididas e registradas no SDD.
- [ ] O modo sombra: tudo se grava, e nada sai ao motorista.
- [ ] A gravação para treino, só da região de gravação e só com a cláusula.
- [ ] O detector e o OCR v1 treinados por nós, e o `[ABERTO-03]` fechado.
- [ ] O leitor v1 na caixa, com os pesos entregues pela atualização, com volta.
- [ ] O leitor comercial local lendo as mesmas passagens, só para comparar (G1).
- [ ] A medição no N150 com 6 câmeras e o guia de instalação (`[ABERTO-08]`).
- [ ] O PWA nos tablets.
- [ ] O registro manual comparado, e as divergências conferidas.
- [ ] Os parâmetros do extrato e a linha de base medida na sombra.
- [ ] A caixa e as 6 câmeras no site, com a saúde na frota.
- [ ] A rotulagem, a régua fixa e um retreino que não piora a régua.
- [ ] O casamento ajustado com os dados do piloto (`[ABERTO-02]`).
- [ ] **Marco:** o acerto real medido, com a decisão de ligar o check-in no mês 6.

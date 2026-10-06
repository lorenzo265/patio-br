---
tipo: "plano"
fonte: "docs/planos/2027-01-plano-mes-4.md"
gerada: true
tags: [plano]
---

> [!note] Gerada de `docs/planos/2027-01-plano-mes-4.md` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Plano do mês 4: a versão do piloto

Plano de implementação do mês 4 do cronograma do SDD ([[SDD|docs/SDD.md]], seção 10).
Versão 1 · 2026-10-06 · **Rascunho para aprovação do Lorenzo**

---

## 1. Objetivo e marco

**Objetivo:** a versão que vai para o piloto, pronta e testada na homologação. O que ela faz:
- avisa o motorista de verdade, pelo WhatsApp, com o SMS de reserva;
- manda os alertas para quem precisa agir;
- prepara a caixa de borda para o site: em contêiner, mandando a saúde e se atualizando sozinha;
- guarda a prova de cada visita de um jeito que se pode conferir;
- roda a nuvem de produção na AWS, com cópias e alarmes;
- protege a produção com a verificação em duas etapas.

O prazo é de cerca de um mês. Na trilha comercial, a meta é fechar o piloto pago.

**Marco do mês (o teste de "pronto"):**

> Na homologação, com o simulador no lugar da caixa:
> 1. Um agendamento chega pela planilha e o celular de teste recebe o primeiro aviso.
> 2. O motorista autoriza o WhatsApp.
> 3. A passagem faz o check-in.
> 4. O motorista recebe no WhatsApp "na fila", "vá para a doca" e "pode sair".
> 5. Desligar a caixa dispara o alerta. Ao religar, nada se perdeu.
> 6. A prova da visita mostra tudo, com a cadeia conferida.
> 7. A cópia do banco volta numa restauração de teste.
> 8. Uma tag leva a mesma versão à produção, pronta para o piloto.

**Nenhum dado de cliente antes do contrato.** A homologação só tem dados inventados. A produção
fica vazia até o contrato e o acordo de tratamento de dados do piloto estarem assinados
([[ABERTO-07]]). Os testes continuam com dados inventados (regra 3 do [[CLAUDE - regras do repositório|CLAUDE.md]]).

**O que fica do mês 3**, em paralelo com este plano:
- o visual próprio ([[T40]]), na sessão da identidade visual ([[ABERTO-01]]);
- o deploy da demonstração, que espera as contas da Vercel e do Supabase ([[N17]]).

**O que continua esperando:**
- **A medição no N150 ([[T20]]):** espera o hardware ([[N7]]).
- **O leitor v1 e o teste técnico ([[T22]] a [[T26]], [[T36]] e [[T37]]):** esperam as placas reais
  ([[ABERTO-18]]).
  - Com o gerador de placas sintéticas ([[T39]], neste mês) e a conta de GPU ([[N11]]), o treino do OCR
    pode começar antes.
  - Nenhum modelo vai para a caixa sem a régua fixa ([[4.7 Metas e a régua|SDD 4.7]]).
- **A caixa do piloto:** não leva os pesos do v0, que são só para avaliação interna ([[D-26]]). Ela
  espera o v1 ou o leitor comercial de reserva ([[D-07]], pelo resultado do teste técnico).

**Fora do mês 4:**
- **A foto de contexto com os rostos borrados:** pela regra da seção 4.1, o modelo que acha
  rostos também precisa de pesos nossos. Até lá, a caixa só manda o recorte da placa, como hoje.
- **O SSE e o PWA ([[D-09]]):** as telas perguntam ao servidor a cada 2 ou 3 segundos (HTMX), o que
  basta para um site. O PWA entra com o visual ([[T40]]) ou antes dos tablets do piloto (mês 5).
- O modo B e as fases seguintes ([[3.5 Fases futuras (já previstas)|SDD 3.5]]).

---

## 2. Antes de começar: decisões do Lorenzo

| # | Decisão | Trava | Recomendação |
|---|---|---|---|
| F1 | **Onde roda a produção.** O SDD escolheu a AWS ([[D-11]]). A demonstração foi para a Vercel e o Supabase ([[D-51]]), mas o piloto é diferente. | [[T49]] e [[T50]] | **Manter a AWS da [[D-11]]**, em São Paulo: Lightsail 4 GB (API, worker e Caddy), RDS PostgreSQL e S3 para as fotos. A homologação fica numa Lightsail 2 GB, com o PostgreSQL num contêiner e um balde S3 próprio. Os preços estão no [[Validação - fatos técnicos da stack\|docs/validacao/fatos-tecnicos-stack.md]]. O motivo: o piloto precisa do worker rodando sempre (o check-in e o aviso ao motorista na hora, sem esperar alguém abrir uma tela), da API da caixa ligada e de voltar o banco a qualquer minuto dos últimos 7 dias. A alternativa é o Supabase Pro para o banco e as fotos, mais uma máquina para a API e o worker: uma conta a menos, mas voltar a qualquer minuto é um adicional pago. |
| F2 | **Como o motorista autoriza o WhatsApp** ([[ABERTO-22]]). A política da Meta só deixa a empresa começar a conversa com quem autorizou receber as mensagens dela. O número do motorista vem da transportadora ou da planilha, e o [[2.2 A jornada de um caminhão (modo A)\|SDD 2.2]] manda o primeiro WhatsApp antes dessa autorização. | [[T52]] e [[T53]] | **O motorista começa a conversa.** O primeiro aviso vai por SMS, com um link que abre o WhatsApp com a mensagem pronta. Quando o motorista manda, isso é a autorização, e a conversa no WhatsApp fica aberta. Um QR na placa de aviso da portaria faz o mesmo para quem chega sem ter autorizado. "SAIR" cancela na hora. Quem não autoriza recebe os avisos por SMS. A alternativa: a transportadora declara, no link e na planilha, que o motorista autorizou, e o primeiro WhatsApp vai direto. É mais simples e mais barato, mas a autorização vem de outra pessoa, e uma denúncia de "spam" baixa a qualidade do número na Meta e o limite de envio. Levar ao advogado ([[N22]]). |
| F3 | **Qual fornecedor de SMS** (o [[7.5 WhatsApp e SMS\|SDD 7.5]] deixa a Zenvia ou a Twilio). | [[T53]] | **Pedir o orçamento da Zenvia** e comparar com a Twilio (US$ 0,0599 por SMS ao Brasil). Ficar com a Zenvia se o preço em reais for menor: ela cobra em reais, com nota, e tem suporte no Brasil. As duas entram pela mesma interface, então trocar depois é escrever outra classe. |
| F4 | **Como funciona a verificação em duas etapas** ([[8.2 Segurança\|SDD 8.2]], para o gestor e a administração). | [[T51]] | **App autenticador** (Google Authenticator, Microsoft Authenticator e outros): o código de 6 números que muda a cada 30 segundos, mais 10 códigos de recuperação. Não depende de serviço de fora e funciona sem sinal de celular. As alternativas: código por e-mail, que precisa de um serviço de e-mail, ou por SMS, que custa e cai com a troca de chip. O porteiro e o líder de pátio continuam sem ela: usam o tablet da portaria, com o PIN. |
| F5 | **Como os erros e as quedas chegam até nós** ([[8.1 Falhas\|SDD 8.1]]: "erro no código: sempre registrado e alertado"). | [[T50]] | **Tudo dentro da AWS:** o registro de erros no CloudWatch, um alarme para cada erro e a verificação do `/saude` a cada minuto pelo Route 53, com aviso por e-mail. Custa menos de US$ 5 por mês, e nenhum dado sai da nossa nuvem. A alternativa é o Sentry: lê melhor os erros, mas é mais um fornecedor recebendo dados, o que pede um acordo LGPD com ele. |
| F6 | **Para quem vão os alertas, e por onde.** | [[T57]] | **No painel, sempre:** um sino com os alertas abertos do site, em todas as telas. **Por WhatsApp ao gestor que autorizar, só os graves:** a caixa ou uma câmera fora do ar, e a estadia que passou das 5 horas. **Para a administração (nós):** a caixa e a câmera fora do ar, e os erros. A alternativa é o e-mail, que precisa de um serviço de e-mail e é lido mais tarde. |

---

## 3. Como trabalhar neste plano

As mesmas regras dos meses anteriores ([[CLAUDE - regras do repositório|CLAUDE.md]]), com estes ajustes:

- **Numeração:** as tarefas continuam de onde pararam, a partir da [[T49]]. A [[T39]], das placas
  sintéticas, guardada desde o mês 3, entra aqui. As branches levam `mes4/` (ex.:
  `mes4/t49-producao`).
- **Contas e segredos:** cada conta nova (AWS, Meta, SMS) é aberta pelo Lorenzo. Os segredos
  ficam só nas variáveis de ambiente das máquinas e nos *secrets* do GitHub, passados pelo cofre
  de segredos do ambiente, nunca no repositório (regra 4).
- **Os serviços de fora são imitados nos testes:** a Meta, o SMS e o S3 (como no mês 3, com o
  moto). Nenhum teste usa a rede, e nenhum usa um número de telefone de verdade.
- **Cada integração é conferida de verdade na homologação**, com o número de teste da Meta e o
  celular do Lorenzo. A conferência entra no PR.
- **O que a execução decidir vira uma D-nn** no SDD, no mesmo PR, como nos meses anteriores.

---

## 4. Tarefas técnicas

### Semana 1 — a casa do piloto

- [[T49]] Produção e homologação na AWS
- [[T50]] Cópias, restauração testada e alarmes
- [[T51]] Verificação em duas etapas

### Semana 2 — o motorista avisado de verdade

- [[T52]] Canais de mensagem e o WhatsApp
- [[T53]] SMS de reserva e o "motorista não avisado"

### Semana 3 — a caixa no site e os alertas

- [[T54]] Saúde da caixa e a frota de borda
- [[T55]] A caixa em contêineres, pronta para o site
- [[T56]] Atualização da caixa
- [[T57]] Alertas

### Semana 4 — prova, dados e integração

- [[T58]] Trilha de prova completa
- [[T59]] Prazos de guarda e o pedido do titular
- [[T60]] Base de treino
- [[T39]] Gerador de placas sintéticas
- [[T61]] Agendamentos por API e webhooks
- [[T62]] A versão do piloto em homologação

## 5. Trilha não técnica

| # | Tarefa | Por quê | Resolve |
|---|---|---|---|
| [[N19]] | Com a verificação da empresa na Meta ([[N1]]): registrar o número do WhatsApp do produto (um chip só para isso) e mandar os modelos de mensagem da [[T52]] para aprovação | o WhatsApp de verdade | [[T52]] |
| [[N20]] | Pedir o orçamento da Zenvia (F3) e abrir a conta de SMS | o SMS de reserva | [[T53]] |
| [[N21]] | Abrir a conta da AWS com alerta de gasto ([[N2]]). Separar o domínio de produção: é o da marca ([[ABERTO-01]]); até lá, a homologação usa um endereço provisório. Passar os acessos do deploy pelo cofre de segredos | a produção e a homologação | [[T49]], [[T50]] |
| [[N22]] | Levar ao advogado (junto com a [[N3]] e a [[N15]]): a autorização do motorista (F2, [[ABERTO-22]]), o SMS ao motorista, os prazos de guarda ([[ABERTO-04]]), a cláusula do treino e o modelo de contrato do piloto ([[ABERTO-07]]) | nada de dado de cliente sem isso | [[T52]], [[T53]], [[T59]], [[T60]] |
| [[N23]] | Abrir a conta do Tailscale ([[D-13]]) e comprar uma caixa ([[N7]]) para conferir o contêiner e a atualização num N150 de verdade | a caixa pronta para o site | [[T49]], [[T55]], [[T56]] |
| [[N24]] | Fechar o piloto pago: o cliente, o site, o preço ([[ABERTO-06]]) e a data da instalação (mês 5); com ele, como medir as horas de portaria ([[ABERTO-05]]) e os tempos dos alertas ([[ABERTO-09]]) | o marco comercial do mês | [[ABERTO-05]], [[ABERTO-06]], [[ABERTO-09]] |

---

## 6. Ajustes no SDD feitos junto com este plano

- O cronograma do mês 4 (seção 10) com o que este plano traz:
  - a verificação em duas etapas, que a seção 8.2 já deixava para o mês 4;
  - a API e os webhooks, que estão no MVP (seção 2.3);
  - os prazos de guarda (seção 8.3);
  - as placas sintéticas ([[D-44]]).
- O novo [[ABERTO-22]], sobre a autorização do motorista para o WhatsApp, e a nota dele nas
  seções 2.2 e 7.5.
- Os fatos do WhatsApp e do SMS conferidos em 06/10, com as fontes, em
  [[Validação - fatos técnicos da stack|docs/validacao/fatos-tecnicos-stack.md]].

---

## 7. Checklist de "mês 4 pronto"

- [ ] F1 a F6 decididas e registradas no SDD.
- [ ] Produção e homologação na AWS, com o deploy pela `main` e pela tag.
- [ ] Cópias diárias, restauração testada e alarmes funcionando.
- [ ] Verificação em duas etapas para o gestor e a administração.
- [ ] WhatsApp de verdade, com a autorização do motorista, e o SMS de reserva.
- [ ] Saúde da caixa, tela da frota, caixa em contêineres e atualização com volta.
- [ ] Alertas no painel e por mensagem.
- [ ] Prova da visita encadeada, com a âncora do dia.
- [ ] Prazos de guarda e o pedido do titular.
- [ ] Base de treino e gerador de placas sintéticas.
- [ ] **Marco:** o roteiro do piloto rodado na homologação, e a mesma versão na produção.

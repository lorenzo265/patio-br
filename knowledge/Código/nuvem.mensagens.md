---
tipo: "pacote"
fonte: "nuvem/src/nuvem/mensagens/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/mensagens/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.mensagens

Pasta `nuvem/src/nuvem/mensagens/`.

Mensagens ao motorista ([[2.2 A jornada de um caminhão (modo A)|SDD 2.2]], [[7.5 WhatsApp e SMS|7.5]] e [[D-47]]): a confirmação e os avisos da fila e da doca.

## Módulos

### `nuvem.mensagens.canais`

`nuvem/src/nuvem/mensagens/canais.py`

Os canais de envio das mensagens ao motorista ([[7.5 WhatsApp e SMS|SDD 7.5]], [[D-63]]).

Cada canal (o WhatsApp, o SMS) manda uma mensagem e devolve o id dela no canal. O erro diz se
vale tentar de novo: o **passageiro** (a rede, o limite de envio) faz a tarefa da fila tentar
mais tarde; o **definitivo** (o número sem WhatsApp, o modelo recusado) deixa a mensagem como
falhou. O canal de demonstração não manda nada, e não é um canal de envio.

- **`EnvioFalhouError`** (classe): O envio falhou por um motivo passageiro: a tarefa tenta de novo, mais tarde.
- **`EnvioRecusadoError`** (classe): O canal recusou a mensagem de vez: tentar de novo não muda nada.
- **`Situacao`** (classe): A situação de uma mensagem nossa, como o canal avisou depois do envio.
- **`Envio`** (classe): A mensagem aceita pelo canal.
- **`CanalDeEnvio`** (classe): Um canal que manda as mensagens ao motorista.
- **`CanalDoWhatsApp`** (classe): O WhatsApp: além de mandar o modelo, responde ao motorista e tem o número dos links.
- **`Canais`** (classe): Os canais configurados. Sem o WhatsApp, as mensagens ficam no canal de demonstração.

### `nuvem.mensagens.modelos`

`nuvem/src/nuvem/mensagens/modelos.py`

Tabelas das mensagens ao motorista ([[5.1 Entidades|SDD 5.1]], [[D-47]], [[D-58]] e [[D-63]]).

A mensagem aponta para o agendamento, para o evento que a gerou e para o site pela dupla (pai,
empresa) ([[5.5 Garantias|SDD 5.5]]). O texto fica pronto: é o que o motorista leu.

A autorização do WhatsApp é do celular, numa empresa ([[D-58]]). A mensagem recebida é da
plataforma, como a fila de tarefas: o número do WhatsApp é um só para todos os clientes, e a
empresa só se sabe pelo que o texto diz.

- **`ModeloDeMensagem`**: A confirmação do agendamento e os avisos do check-in, da chamada e do fim na doca.
- **`Canal`**: Por onde a mensagem vai. O de demonstração só guarda ([[D-45]] e [[D-63]]).
- **`SituacaoDaMensagem`**: Guardada é a que ainda não saiu (no canal de demonstração, nunca sai).
- **`Mensagem`** (classe): Uma mensagem ao motorista de um agendamento.
- **`AutorizacaoWhatsApp`** (classe): O celular que autorizou receber os avisos de uma empresa pelo WhatsApp ([[D-58]]).
- **`MensagemRecebida`** (classe): Uma mensagem que alguém mandou ao número do produto ([[D-63]]).

### `nuvem.mensagens.modelos_do_whatsapp`

`nuvem/src/nuvem/mensagens/modelos_do_whatsapp.py`

Os modelos de mensagem do WhatsApp ([[7.5 WhatsApp e SMS|SDD 7.5]], [[D-63]]): um por tipo de mensagem.

A Meta só deixa a empresa começar a conversa com um **modelo aprovado**: o texto fixo, com as
variáveis numeradas (``{{1}}``, ``{{2}}``...). Os textos ficam aqui, e é este texto que se manda à
Meta para aprovar ([[N19]]). A tela da conversa mostra o mesmo texto, já preenchido.

Regras da Meta seguidas aqui: nenhum modelo começa nem termina com uma variável, as variáveis
vão numeradas a partir de 1, e o nome só tem letras minúsculas, números e ``_``. Todos são da
categoria utilidade, em português (``pt_BR``).

- **`ModeloDoWhatsApp`** (classe): Um modelo de mensagem: o nome aprovado na Meta e o texto, com as variáveis.
- **`MODELOS`**: O modelo de cada tipo de mensagem ao motorista.
- **`preencher`**: O texto do modelo com as variáveis, como o motorista lê.

### `nuvem.mensagens.rotas`

`nuvem/src/nuvem/mensagens/rotas.py`

Os avisos dos canais ([[7.5 WhatsApp e SMS|SDD 7.5]]): o webhook do WhatsApp ([[D-63]]) e o retorno do SMS ([[D-64]]).

``/api/whatsapp``:

- ``GET``: a Meta confere o webhook ao cadastrá-lo, com o código que escolhemos; a resposta é o
  desafio que ela mandou.
- ``POST``: o aviso da Meta (a situação das mensagens, as mensagens recebidas). Só passa com a
  assinatura do segredo do app (``X-Hub-Signature-256``); o aviso vira a tarefa "aviso do
  WhatsApp", e o worker faz o resto. O mesmo aviso duas vezes vira uma tarefa só.

``/api/sms/<segredo>``: o retorno da entrega do SMS. A Zenvia não assina os avisos, então o
segredo vai no endereço, que só ela conhece (e some do registro de acesso).

Sem o canal configurado, as rotas respondem 404. O cookie não decide quem pede, então elas ficam
fora do código anti-CSRF ([[D-55]]).

- **`corpo_do_pedido`**: O corpo cru, como a Meta assinou (a assinatura é dos bytes, não do JSON lido).
- **`conferir_o_webhook`**: A conferência da Meta: devolve o desafio se o código for o nosso.
- **`receber_o_aviso`**: Guarda o aviso assinado numa tarefa e responde logo (a Meta repete o que demora).
- **`receber_o_retorno_do_sms`**: O retorno da Zenvia ([[D-64]]): só com o segredo do endereço, e vira a tarefa "aviso do SMS".

### `nuvem.mensagens.servico`

`nuvem/src/nuvem/mensagens/servico.py`

Mensagens ao motorista ([[2.2 A jornada de um caminhão (modo A)|SDD 2.2]], [[D-47]], [[D-58]] e [[D-63]]): nascem dos eventos, pelo worker.

- **Confirmação:** o agendamento ativo com celular, que ainda não terminou, recebe uma para cada
  celular que teve (o celular novo ainda não sabe de nada).
- **Avisos:** o check-in avisa a posição na fila; a chamada, a doca; o fim na doca, que pode
  sair. Cada evento avisa uma vez só, no celular que o agendamento tem na hora.
- **Só o recente:** o worker olha os eventos dos últimos 30 minutos (aviso mais velho chegaria
  tarde) e os agendamentos criados ou mudados no último dia.
- **O canal** ([[D-63]]): sem o WhatsApp e sem o SMS configurados, o de demonstração, que só guarda;
  com eles, o WhatsApp para o celular que autorizou a empresa, e o SMS para os outros, com o
  texto curto do SMS ([[D-64]]). A mensagem que sai vira a tarefa "enviar mensagem".
- **A reserva** ([[D-64]]): a mensagem do WhatsApp que falha de vez ganha uma cópia pelo SMS.
- **O aviso da Meta** (``tratar_aviso``): a situação de cada mensagem (enviada, entregue, lida,
  falhou) e as mensagens que o motorista mandou: a autorização ("AVISOS ...") e o "SAIR".

O texto fica pronto na mensagem, sem o nome do motorista. O módulo lê a portaria, o pátio e o
agendamento só pelas funções de serviço deles ([[3.3 Módulos da nuvem no MVP|SDD 3.3]]). As funções gravam sem ``commit``; quem
lê passa o ``Acesso``.

- **`AVISOS_OLHADOS`** = `timedelta(minutes=30)`: O evento mais velho que isso não avisa mais: o aviso chegaria tarde (ex.: a doca já mudou).
- **`AGENDAMENTOS_OLHADOS`** = `timedelta(days=1)`: A confirmação olha os agendamentos criados ou mudados no último dia (cobre o worker parado).
- **`SEM_ENVIO`** = `'demonstracao'`: O canal sem o WhatsApp configurado: só guarda ([[D-45]]).
- **`ORDEM_DA_SITUACAO`**: O aviso da Meta chega fora de ordem: a situação só anda para a frente (falhar, só antes de entregar).
- **`AVISO_DO_EVENTO`**: Os eventos da visita que avisam o motorista, e o modelo de cada aviso.
- **`ULTIMAS_CONVERSAS`** = `50`: Quantas conversas a lista de um site mostra.
- **`Conversa`** (classe): As mensagens de um agendamento, pela última.
- **`preparar`**: Grava as mensagens que faltam, de todos os sites (sem ``commit``).
- **`enviar`**: Manda uma mensagem guardada pelo canal dela (a tarefa "enviar mensagem"; sem ``commit``).
- **`tratar_aviso`**: Trata um aviso do webhook do WhatsApp (a tarefa "aviso do WhatsApp"; sem ``commit``).
- **`tratar_aviso_do_sms`**: Trata um retorno da Zenvia (a tarefa "aviso do SMS"; sem ``commit``): a entrega do SMS.
- **`conversa`**: As mensagens de um agendamento que o usuário vê, na ordem em que foram feitas.
- **`conversas`**: As conversas de um site que o usuário vê, da última mensagem para a primeira.
- **`nao_avisados`**: Os agendamentos, entre estes, cujo motorista não recebeu o último aviso ([[D-64]]).

### `nuvem.mensagens.sms`

`nuvem/src/nuvem/mensagens/sms.py`

O SMS de reserva pela Zenvia, direto e sem biblioteca dela ([[7.5 WhatsApp e SMS|SDD 7.5]], [[D-59]] e [[D-64]]).

- **Mandar:** ``POST https://api.zenvia.com/v2/channels/sms/messages``, com o token no cabeçalho
  ``X-API-TOKEN`` e o texto pronto da mensagem.
- **O texto:** curto e só com os caracteres do GSM-7, sem acento, para caber num pedaço de 160
  (com um acento do português, o pedaço cai para 70 e o SMS custa o dobro). O da confirmação
  leva o link que abre o WhatsApp com "AVISOS A<agendamento>" ([[D-58]]).
- **O retorno:** a Zenvia avisa a entrega com um evento ``MESSAGE_STATUS``.

- **`TAMANHO_DO_PEDACO`** = `160`: Um pedaço de SMS, só com os caracteres do GSM-7.
- **`ASSINATURA`** = `'patio-br'`: Quem manda, no começo do texto; muda com o nome do produto ([[ABERTO-01]]).
- **`MENOR_PEDACO_DE_NOME`** = `8`: O nome do site (ou da doca) é cortado para caber, mas não fica menor que isto.
- **`SITUACOES`**: A situação que a Zenvia avisa, no nome daqui.
- **`CanalSMS`** (classe): O canal de SMS: manda o texto pronto da mensagem pela Zenvia.
- **`para_gsm7`**: O texto sem acento e só com os caracteres da tabela básica do GSM-7.
- **`texto_do_sms`**: O texto do SMS de uma mensagem: curto, sem acento e de no máximo 160 caracteres.
- **`ler_aviso_do_sms`**: A situação de uma mensagem nossa, de um evento da Zenvia; ``None`` se não é uma.
- **`canal_da_configuracao`**: O canal de SMS da configuração, ou ``None`` se ele não está configurado.

### `nuvem.mensagens.whatsapp`

`nuvem/src/nuvem/mensagens/whatsapp.py`

O WhatsApp pela Cloud API da Meta, direto e sem biblioteca dela ([[7.5 WhatsApp e SMS|SDD 7.5]], [[D-12]] e [[D-63]]).

- **Mandar:** o modelo aprovado, com as variáveis, por ``POST /<versão>/<número>/messages``; e a
  resposta curta, em texto livre, a quem acabou de mandar uma mensagem.
- **O webhook:** a Meta assina o corpo com o segredo do app (``X-Hub-Signature-256``); aqui se
  confere a assinatura e se lê o aviso (as situações das mensagens e as recebidas).
- **O motorista:** o link ``wa.me`` abre o WhatsApp com a mensagem pronta ([[D-58]]), e o texto que
  ele manda diz o que pediu ("AVISOS A<agendamento>", "AVISOS S<site>" ou "SAIR").

- **`VERSAO_PADRAO`** = `'v25.0'`: A versão da API da Meta (de 02/2026); configurável, porque cada versão vale cerca de 2 anos.
- **`ERROS_PASSAGEIROS`**: Os códigos de erro da Meta que passam: o limite de envio, o serviço fora, o token vencido (até alguém trocar). Os outros (o número sem WhatsApp, o modelo recusado) são definitivos.
- **`SITUACOES`**: A situação que a Meta avisa, no nome daqui.
- **`Recebida`** (classe): Uma mensagem que alguém mandou ao número do produto.
- **`CanalWhatsApp`** (classe): O canal do WhatsApp: manda os modelos e as respostas pela Cloud API.
- **`assinatura_confere`**: Se o ``X-Hub-Signature-256`` é o HMAC-SHA256 do corpo com o segredo do app.
- **`celular_do_whatsapp`**: O celular do Brasil como o agendamento guarda (``+55``, o DDD e os 9 números).
- **`link_para_autorizar`**: O link que abre o WhatsApp no número do produto, com o texto já escrito ([[D-58]]).
- **`pedido_do_agendamento`**: O texto pronto do link do SMS: autoriza a empresa do agendamento.
- **`pedido_do_site`**: O texto pronto do QR da portaria: autoriza a empresa do site.
- **`o_que_pediu`**: O que o motorista pediu na mensagem, ou ``None`` se não é um pedido.
- **`ler_aviso`**: As situações e as mensagens recebidas de um aviso do webhook.
- **`canal_da_configuracao`**: O canal do WhatsApp da configuração, ou ``None`` se ele não está configurado.

## Testes

- `nuvem/tests/test_nuvem_mensagens.py`: Mensagens do motorista ([[T43]], [[2.2 A jornada de um caminhão (modo A)|SDD 2.2]] e [[D-47]]): nascem dos eventos, no canal de demonstração.
- `nuvem/tests/test_nuvem_mensagens_envio.py`: O envio das mensagens ao motorista ([[7.5 WhatsApp e SMS|SDD 7.5]], [[D-58]] e [[D-63]]): o canal de cada uma, a fila, as situações que a Meta avisa, a autorização do motorista e o "SAIR". A Meta é imitada.
- `nuvem/tests/test_nuvem_mensagens_reserva.py`: O SMS de reserva e o motorista não avisado ([[7.5 WhatsApp e SMS|SDD 7.5]], [[D-58]] e [[D-64]]), com o banco: a Meta e a Zenvia imitadas.
- `nuvem/tests/test_nuvem_mensagens_sms.py`: O canal de SMS ([[7.5 WhatsApp e SMS|SDD 7.5]], [[D-59]] e [[D-64]]), sem banco: a Zenvia imitada e os textos curtos.
- `nuvem/tests/test_nuvem_mensagens_whatsapp.py`: O canal do WhatsApp ([[7.5 WhatsApp e SMS|SDD 7.5]], [[D-12]] e [[D-63]]), sem banco: a Cloud API da Meta imitada.

---

Do [[Mapa do código]].

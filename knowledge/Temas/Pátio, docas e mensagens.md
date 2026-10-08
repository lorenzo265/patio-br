---
tipo: "tema"
escrita: "à mão"
atualizada: "2026-10-06"
tags: [tema]
---

# Pátio, docas e mensagens

Depois do check-in: a fila, a chamada para a doca, a carga ou descarga e os avisos ao motorista.

## O essencial

- **O líder de pátio** vê a fila, chama para a doca e marca início e fim com um toque
  ([[2.1 Quem usa e o que pode fazer]], [[2.2 A jornada de um caminhão (modo A)]]). Uma doca por
  caminhão; quem passou pela doca é liberado para sair; alerta das 4 horas ([[T42]]).
- **As mensagens ao motorista nascem dos eventos, pelo worker** ([[D-47]]): a confirmação do
  agendamento, "na fila, posição X", "vá para a doca" e "pode sair". Cada evento gera uma
  mensagem só, e o texto não leva o nome do motorista.
- **Sem o WhatsApp configurado (local e demonstração), o canal é o de demonstração**, que só
  guarda: a tela em forma de celular mostra as mensagens, sem enviar nada ([[T43]]).
- **Com o WhatsApp configurado** ([[T52]], [[D-63]]): cada mensagem escolhe o canal ao ser
  gravada (WhatsApp para o celular que autorizou a empresa, SMS para os outros) e sai por uma
  tarefa da fila; o webhook da Meta (`/api/whatsapp`) confere a assinatura e guarda o aviso
  numa tarefa, e o worker atualiza a situação (enviada, entregue, lida, falhou) e trata as
  mensagens do motorista ([[7.5 WhatsApp e SMS]], [[N1]], [[N19]]).
- **O SMS** ([[T53]], [[D-64]]): pela Zenvia ([[D-59]]), com um texto curto, sem acento e de no
  máximo 160 caracteres; o da confirmação leva o link do WhatsApp. A mensagem do WhatsApp que
  falha de vez ganha uma cópia pelo SMS. O retorno da Zenvia chega em `/api/sms/<segredo>`.
- **Motorista não avisado:** quando o último aviso falhou em todas as tentativas, o quadro do
  pátio mostra "motorista não avisado" no caminhão ([[D-64]]).
- **O motorista começa a conversa** ([[D-58]], que fechou o [[ABERTO-22]]): a política da Meta
  pede a autorização de quem recebe, e o número vem da transportadora. O primeiro aviso vai por
  SMS (Zenvia, [[D-59]]), com um link que abre o WhatsApp com a mensagem pronta; a mensagem do
  motorista é a autorização. Um QR na portaria faz o mesmo (o gestor imprime a placa em
  `/mensagens/qr`), e "SAIR" cancela em todas as empresas.
- **Os alertas** (a estadia, a caixa e a câmera fora do ar, o motorista não avisado) vão para o
  painel e, os graves, por WhatsApp ao gestor ([[D-62]], [[T57]]).

## Onde ler

- SDD: [[2.2 A jornada de um caminhão (modo A)]], [[5.2 Estados da visita]],
  [[7.5 WhatsApp e SMS]].
- Decisões: [[D-12]], [[D-47]], [[D-58]], [[D-59]], [[D-62]], [[D-63]], [[D-64]].
- Código: [[nuvem.patio]], [[nuvem.mensagens]], [[nuvem.web]].
- Tarefas: [[T42]], [[T43]], [[T52]], [[T53]], [[T57]].

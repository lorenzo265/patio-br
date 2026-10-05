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

### `nuvem.mensagens.modelos`

`nuvem/src/nuvem/mensagens/modelos.py`

Tabela das mensagens ao motorista ([[5.1 Entidades|SDD 5.1]] e [[D-47]]).

A mensagem aponta para o agendamento, para o evento que a gerou e para o site pela dupla (pai,
empresa) ([[5.5 Garantias|SDD 5.5]]). O texto fica pronto: é o que o motorista leu.

- **`ModeloDeMensagem`**: A confirmação do agendamento e os avisos do check-in, da chamada e do fim na doca.
- **`Canal`** = `Literal['demonstracao']`: Por onde a mensagem vai. O de demonstração só guarda; WhatsApp e SMS entram no mês 4.
- **`SituacaoDaMensagem`** = `Literal['guardada']`: No canal de demonstração, a mensagem só fica guardada (no mês 4: enviada, entregue...).
- **`Mensagem`** (classe): Uma mensagem ao motorista de um agendamento.

### `nuvem.mensagens.servico`

`nuvem/src/nuvem/mensagens/servico.py`

Mensagens ao motorista ([[2.2 A jornada de um caminhão (modo A)|SDD 2.2]] e [[D-47]]): nascem dos eventos, pelo worker.

- **Confirmação:** o agendamento ativo com celular, que ainda não terminou, recebe uma para cada
  celular que teve (o celular novo ainda não sabe de nada).
- **Avisos:** o check-in avisa a posição na fila; a chamada, a doca; o fim na doca, que pode
  sair. Cada evento avisa uma vez só, no celular que o agendamento tem na hora.
- **Só o recente:** o worker olha os eventos dos últimos 30 minutos (aviso mais velho chegaria
  tarde) e os agendamentos criados ou mudados no último dia.
- **Canal de demonstração:** a mensagem só fica guardada; o WhatsApp entra no mês 4, aqui.

O texto fica pronto na mensagem, sem o nome do motorista. O módulo lê a portaria, o pátio e o
agendamento só pelas funções de serviço deles ([[3.3 Módulos da nuvem no MVP|SDD 3.3]]). ``preparar`` grava sem ``commit``; quem
lê passa o ``Acesso``.

- **`AVISOS_OLHADOS`** = `timedelta(minutes=30)`: O evento mais velho que isso não avisa mais: o aviso chegaria tarde (ex.: a doca já mudou).
- **`AGENDAMENTOS_OLHADOS`** = `timedelta(days=1)`: A confirmação olha os agendamentos criados ou mudados no último dia (cobre o worker parado).
- **`CANAL`** = `'demonstracao'`: O canal do mês 3: só guarda.
- **`AVISO_DO_EVENTO`**: Os eventos da visita que avisam o motorista, e o modelo de cada aviso.
- **`ULTIMAS_CONVERSAS`** = `50`: Quantas conversas a lista de um site mostra.
- **`Conversa`** (classe): As mensagens de um agendamento, pela última.
- **`preparar`**: Grava as mensagens que faltam, de todos os sites (sem ``commit``).
- **`conversa`**: As mensagens de um agendamento que o usuário vê, na ordem em que foram feitas.
- **`conversas`**: As conversas de um site que o usuário vê, da última mensagem para a primeira.

## Testes

- `nuvem/tests/test_nuvem_mensagens.py`: Mensagens do motorista ([[T43]], [[2.2 A jornada de um caminhão (modo A)|SDD 2.2]] e [[D-47]]): nascem dos eventos, no canal de demonstração.

---

Do [[Mapa do código]].

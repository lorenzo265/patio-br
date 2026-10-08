---
tipo: "pacote"
fonte: "nuvem/src/nuvem/alertas/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/alertas/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.alertas

Pasta `nuvem/src/nuvem/alertas/`.

Os alertas ([[8.1 Falhas|SDD 8.1]], [[D-62]] e [[D-68]]): abrem uma vez, fecham sozinhos e avisam quem autorizou.

## Módulos

### `nuvem.alertas.modelos`

`nuvem/src/nuvem/alertas/modelos.py`

Tabelas dos alertas ([[5.1 Entidades|SDD 5.1]] e [[8.1 Falhas|8.1]], [[D-68]]).

O alerta e o aviso dele são da empresa do site; os da plataforma (a tarefa que falhou) não têm
empresa nem site. A autorização do WhatsApp é de uma pessoa: um usuário do cliente (com a empresa
dele) ou alguém da administração.

- **`SituacaoDoAviso`** = `Literal['guardado', 'enviado', 'falhou']`: Guardado (ainda não foi, ou não há WhatsApp), enviado, ou recusado de vez.
- **`Alerta`** (classe): Um alerta: abre uma vez e fecha sozinho quando a situação passa.
- **`AlertasNoWhatsApp`** (classe): O pedido de uma pessoa para receber os alertas graves pelo WhatsApp e, depois de ela mandar o código, a autorização daquele celular ([[D-68]]).
- **`AvisoDeAlerta`** (classe): Um alerta grave mandado pelo WhatsApp a quem autorizou ([[D-68]]).

### `nuvem.alertas.servico`

`nuvem/src/nuvem/alertas/servico.py`

Os alertas ([[8.1 Falhas|SDD 8.1]], [[D-62]] e [[D-68]]).

- **Conferir:** a cada minuto, o worker (um de cada vez) levanta as situações de agora; o alerta
  de uma situação nova abre, e o da situação que passou fecha. Um alerta aberto não se repete.
- **Quem vê:** quem é do cliente vê os alertas dos sites dele (o sino e a tela ``/alertas``); a
  administração vê a caixa, a câmera e as tarefas de todas as empresas.
- **O WhatsApp:** os graves vão a quem autorizou, por um código de uso único que a tela mostra
  ("ALERTAS <código>", 10 minutos). O aviso sai por uma tarefa da fila.

Os tempos ficam no código até o [[ABERTO-09]] e o cliente do piloto.

- **`DIFERENCA_DO_RELOGIO`** = `2.0`: Segundos: acima disso, o relógio da caixa está errado.
- **`GRAVES`**: Os que vão pelo WhatsApp ([[D-62]]).
- **`DA_ADMINISTRACAO`**: Os que a administração vê; dos graves, a caixa e a câmera vão também pelo WhatsApp a ela.
- **`NO_SITE`**: A visita que chegou e ainda não saiu.
- **`ALFABETO_DO_CODIGO`** = `'23456789ABCDEFGHJKMNPQRSTUVWXYZ'`: Letras e números sem os que se confundem (0 e O, 1, I e L).
- **`Situacao`** (classe): O que está acontecendo agora e pede um alerta.
- **`Lugar`** (classe): A empresa e o site de um alerta, para a tela da administração.
- **`Conferencia`** (classe): Quantos alertas abriram e quantos fecharam numa conferência.
- **`conferir`**: Abre os alertas das situações novas e fecha os das que passaram (com ``flush``).
- **`abertos`**: Os alertas abertos dos sites que o usuário vê, dos mais novos para os mais antigos.
- **`recentes`**: Os abertos e os fechados nas últimas 24 horas, dos sites que o usuário vê.
- **`abertos_da_administracao`**: Os alertas abertos da caixa, da câmera e das tarefas, de todas as empresas.
- **`lugares_da_administracao`**: A empresa e o site de cada alerta que tem site (os das tarefas não têm).
- **`pedir_codigo`**: Um código de uso único, de 10 minutos, para a pessoa ligar o celular aos alertas.
- **`celular_autorizado`**: O celular que recebe os alertas graves desta pessoa, ou ``None``.
- **`autorizar_pelo_codigo`**: Liga o celular de quem mandou o código à pessoa que o pediu.
- **`revogar_do_celular`**: Cancela os alertas pelo WhatsApp deste celular ("SAIR"); devolve quantas autorizações.
- **`avisar`**: Manda o aviso de um alerta pelo WhatsApp (a tarefa "avisar alerta").

## Testes

- `nuvem/tests/test_nuvem_alertas.py`: Os alertas ([[8.1 Falhas|SDD 8.1]], [[D-62]] e [[D-68]]): abrem uma vez, fecham sozinhos e avisam quem autorizou.

---

Do [[Mapa do código]].

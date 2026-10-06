---
tipo: "pacote"
fonte: "nuvem/src/nuvem/guarda/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/guarda/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.guarda

Pasta `nuvem/src/nuvem/guarda/`.

A guarda dos dados ([[8.3 LGPD|SDD 8.3]], [[D-70]]): os prazos, a disputa e o pedido do titular.

## Módulos

### `nuvem.guarda.modelos`

`nuvem/src/nuvem/guarda/modelos.py`

Tabelas da guarda ([[5.1 Entidades|SDD 5.1]] e [[8.3 LGPD|8.3]], [[D-70]]).

A foto apagada e a marca de disputa só se acrescentam: um gatilho no banco recusa alterar ou
apagar (migração 0025), como nos eventos da visita.

- **`FotoApagada`** (classe): Uma foto da passagem que saiu do armazenamento pelo prazo de guarda.
- **`MarcaDeDisputa`** (classe): O gestor marca ou desmarca a visita "em disputa"; vale a última marca.

### `nuvem.guarda.servico`

`nuvem/src/nuvem/guarda/servico.py`

A guarda das fotos e a disputa ([[8.3 LGPD|SDD 8.3]], [[D-70]]).

- **A foto vencida:** a cada hora, o worker apaga o arquivo das fotos das passagens que chegaram
  há mais que o prazo (``PATIO_GUARDA_FOTOS_DIAS``, 90 dias), menos as de uma visita com exceção
  aberta ou em disputa. Cada foto vira uma ``FotoApagada``, que diz se o arquivo estava lá e
  entra na cadeia da prova; o resumo dela continua lá.
- **A disputa:** o gestor marca e desmarca a visita, com o motivo; a marca só se acrescenta, e
  vale a última. Marcar o que já está marcado não grava nada.

- **`PASSAGENS_POR_VEZ`** = `200`: O worker apaga as fotos de no máximo estas passagens a cada volta (o resto, na seguinte).
- **`marcar_disputa`**: Marca a visita "em disputa" (sem ``commit``); ``None`` se ela já estava.
- **`desmarcar_disputa`**: Tira a visita da disputa (sem ``commit``); ``None`` se ela não estava.
- **`em_disputa`**: Se a última marca da visita é "marcar".
- **`ultima_marca`**: A marca que pôs a visita em disputa, se ela está em disputa (``None`` se não está).
- **`apagar_fotos_vencidas`**: Apaga as fotos das passagens vencidas que nada segura (sem ``commit``).

### `nuvem.guarda.titular`

`nuvem/src/nuvem/guarda/titular.py`

O pedido do titular ([[8.3 LGPD|SDD 8.3]], [[D-70]]): tudo o que existe de uma placa ou de um celular.

O cliente é o controlador e responde ao titular; nós (a administração) levantamos, numa empresa,
o que existe: pela placa, as visitas, as passagens (com as fotos guardadas e apagadas), as
conferências, os agendamentos e as mensagens deles; pelo celular, os agendamentos, as visitas
deles, as mensagens, as autorizações do WhatsApp e as mensagens recebidas. Uma coisa de cada vez:
a placa ou o celular.

- **`Levantamento`** (classe): O que existe de uma placa ou de um celular numa empresa.
- **`levantar`**: Levanta, numa empresa, tudo o que existe de uma placa ou de um celular.

## Testes

- `nuvem/tests/test_nuvem_guarda.py`: A guarda das fotos e a disputa ([[8.3 LGPD|SDD 8.3]], [[D-70]]): a foto vencida se apaga e a prova fica.
- `nuvem/tests/test_nuvem_guarda_titular.py`: O pedido do titular ([[8.3 LGPD|SDD 8.3]], [[D-70]]): tudo o que existe de uma placa ou de um celular.

---

Do [[Mapa do código]].

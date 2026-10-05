---
tipo: "pacote"
fonte: "nuvem/src/nuvem/patio/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/patio/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.patio

Pasta `nuvem/src/nuvem/patio/`.

Pátio e docas ([[2.2 A jornada de um caminhão (modo A)|SDD 2.2]], passos 4 e 5): a fila, a chamada para a doca, o início e o fim.

## Módulos

### `nuvem.patio.servico`

`nuvem/src/nuvem/patio/servico.py`

O pátio do site: a fila, as docas e os caminhões liberados ([[2.2 A jornada de um caminhão (modo A)|SDD 2.2]] e [[5.2 Estados da visita|5.2]]).

- **Fila:** as visitas em ``NA_FILA``, da chegada mais antiga para a mais nova, com o tempo desde
  a chegada e o alerta perto das 5 horas (a lei conta a estadia desde a chegada).
- **Chamar:** a visita da fila vai para uma doca livre do mesmo site (``CHAMADA``). Uma doca tem no
  máximo um caminhão chamado ou carregando; o banco também confere.
- **Começar e terminar:** ``NA_DOCA`` e ``LIBERADA``; liberada, a doca fica livre. A saída fecha a
  visita (no casamento).
- **Cancelar a chamada:** o caminhão não veio à doca; volta para a fila e a doca fica livre.

Cada mudança é um evento, com quem fez. As funções gravam com ``flush``; o ``commit`` é de quem
chama.

- **`ALERTA_DE_ESTADIA`** = `timedelta(hours=4)`: Quanto depois da chegada o pátio avisa que as 5 horas estão perto ([[ABERTO-09]]).
- **`ESTADIA_DA_LEI`** = `timedelta(hours=5)`: Depois de 5 horas da chegada, a estadia é devida (Lei 11.442, [[5.4 Contas do extrato|SDD 5.4]]).
- **`DocaOcupadaError`** (classe): A doca já tem um caminhão chamado ou carregando.
- **`CaminhaoNoPatio`** (classe): Uma visita no pátio, como o líder a vê.
- **`DocaDoPatio`** (classe): Uma doca, livre (sem caminhão) ou ocupada.
- **`Quadro`** (classe): O pátio de um site agora.
- **`quadro`**: A fila, as docas e os liberados de um site que o usuário vê.
- **`docas_livres`**: As docas de um site sem caminhão chamado ou carregando, pelo nome.
- **`obter_caminhao`**: Uma visita de um site que o usuário vê, como o líder a vê.
- **`posicao_na_fila`**: A posição do caminhão na fila do site: 1 mais quantos chegaram antes e ainda esperam.
- **`chamar`**: Chama o caminhão da fila para uma doca livre do mesmo site.
- **`cancelar_chamada`**: O caminhão chamado não veio à doca: volta para a fila, e a doca fica livre.
- **`iniciar`**: O caminhão chegou à doca: começa a carga ou a descarga.
- **`finalizar`**: Terminou a carga ou a descarga: o caminhão está liberado, e a doca fica livre.

## Testes

- `nuvem/tests/test_nuvem_patio.py`: Pátio e docas ([[T42]], [[2.2 A jornada de um caminhão (modo A)|SDD 2.2]] e [[5.2 Estados da visita|5.2]]): a fila, a chamada para a doca, o início e o fim.

---

Do [[Mapa do código]].

---
tipo: "pacote"
fonte: "ferramentas/src/simulador/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `ferramentas/src/simulador/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# simulador

Pasta `ferramentas/src/simulador/`.

Simulador de portaria ([[6.4 Simulador de portaria|SDD 6.4]]): faz o papel de uma caixa de borda, sem câmera.

## Módulos

### `simulador.__main__`

`ferramentas/src/simulador/__main__.py`

Simulador de portaria ([[6.4 Simulador de portaria|SDD 6.4]]): manda passagens à nuvem como uma caixa de borda.

Exemplos (com o ambiente local no ar, ``uv run tarefas up``)::

    uv run simulador --demonstracao --passagens amostra
    uv run simulador --demonstracao --agendamentos amostra --passagens amostra
    uv run simulador --codigo XXXX-XXXX-XXXX --passagens minhas-passagens.json
    uv run simulador --quadros dados/amostras/portaria-1 --faixa entrada-1 --camera frente
    uv run simulador --video dados/amostras/portaria-1.mp4 --faixa entrada-1 --camera frente

- **Ativação:** ``--codigo`` usa um código gerado pela administração; ``--demonstracao`` (só no
  ambiente local) entra como a administração da semente e gera o código sozinho. A chave fica
  em ``dados/simulador/caixa.json`` (fora do Git) e é usada de novo nas próximas vezes.
- **Passagens prontas** (``--passagens``): um arquivo JSON com uma lista de passagens (ou
  ``amostra``, a do simulador). O que faltar (id, caixa, site, faixa, sentido, horários,
  câmeras) é completado pela ativação e pela hora atual; cada placa leva uma foto desenhada.
  Uma passagem que diz só o sentido (``"sentido": "saida"``) vai pela primeira faixa dele.
- **Agendamentos** (``--agendamentos``, só com ``--demonstracao``): um arquivo JSON (ou
  ``amostra``) com as janelas em minutos a partir de agora; o simulador entra como o gestor da
  semente e os sobe pela planilha, com códigos novos a cada rodada. A amostra de agendamentos
  combina com a de passagens: duas chegadas casam, uma vira exceção com dois candidatos, uma
  não tem placa e uma sai.
- **Quadros** (``--quadros``): as imagens de uma pasta passam pelo agente da caixa com o leitor
  v0 (``uv run tarefas modelos`` antes), como se fossem uma câmera.
- **Vídeo** (``--video``): o mesmo, sobre um arquivo de vídeo (ex.: uma gravação da portaria).

As passagens passam pela mesma fila da caixa (``dados/simulador/fila.sqlite``): o que a nuvem
não recebeu fica guardado para a próxima vez.

- **`SITE_DA_DEMONSTRACAO`** = `'CD Exemplo'`: Os mesmos da semente da nuvem (``nuvem/src/nuvem/semente.py``); um teste confere.
- **`ESPERA_MAXIMA_PADRAO`** = `60.0`: Quanto o simulador espera a nuvem, somando as tentativas, antes de desistir por ora.
- **`PORTA_PADRAO_DA_API`** = `'18000'`: A mesma do ``.env.exemplo`` e do docker compose.
- **`SimuladorError`** (classe): Algo que quem roda o simulador precisa resolver (a mensagem diz o quê).
- **`principal`**: Ponto de entrada do comando ``simulador``.
- **`cliente_para`**: O cliente HTTP para falar com a nuvem.
- **`COLUNAS_DA_PLANILHA`**: As colunas do modelo da planilha da nuvem (``nuvem.agendamento.planilha``); um teste confere.

## Testes

- `ferramentas/tests/test_simulador.py`: Simulador de portaria ([[6.4 Simulador de portaria|SDD 6.4]]): manda passagens à nuvem como uma caixa de borda.

---

Do [[Mapa do código]].

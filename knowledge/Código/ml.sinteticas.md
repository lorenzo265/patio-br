---
tipo: "pacote"
fonte: "ml/src/ml/sinteticas/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `ml/src/ml/sinteticas/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# ml.sinteticas

Pasta `ml/src/ml/sinteticas/`.

Placas sintéticas para começar o treino da leitura sem placas reais ([[4.6 Dados de treino|SDD 4.6]], [[D-44]] e [[D-72]]).

## Módulos

### `ml.sinteticas.__main__`

`ml/src/ml/sinteticas/__main__.py`

``python -m ml.sinteticas``: um lote de placas sintéticas (``uv run tarefas sinteticas``).

### `ml.sinteticas.fonte`

`ml/src/ml/sinteticas/fonte.py`

A fonte de traços das placas sintéticas, desenhada por nós ([[D-72]]).

Cada caractere são linhas numa grade de 4 de largura por 8 de altura, como as letras estreitas e
de cantos chanfrados das placas. A fonte oficial da placa Mercosul e a Mandatory, da placa cinza,
não têm licença que sirva; o leitor aprende o formato com as variações, e não com o desenho exato
de cada letra.

- **`TRACOS`**: Os traços de cada caractere, na grade de ``LARGURA`` por ``ALTURA``.
- **`ESPESSURA`** = `0.11`: A grossura do traço, em partes da altura da letra.
- **`largura_de`**: A largura de uma letra desta altura (com a meia grossura de cada lado).
- **`desenhar`**: Desenha um caractere com o canto de cima à esquerda em ``canto``.

### `ml.sinteticas.gerar`

`ml/src/ml/sinteticas/gerar.py`

O lote de placas sintéticas: ``uv run tarefas sinteticas`` ([[D-72]]).

Grava ``imagens/000001.jpg`` em diante e ``rotulos.csv`` (``arquivo,placa,tipo,categoria``) na
pasta de destino (``dados/sinteticas``, que o Git ignora). Cada imagem tem a própria semente,
tirada da semente do lote e do número dela: o mesmo lote sai igual, imagem por imagem.

- **`gerar`**: Gera o lote; devolve quantas placas gravou.
- **`principal`**: Lê os argumentos, gera o lote e diz quantas placas foram.

### `ml.sinteticas.placa`

`ml/src/ml/sinteticas/placa.py`

As placas de carro e caminhão (400 por 130 mm): a Mercosul e a antiga ([[D-72]]).

- **Mercosul:** fundo branco, a faixa azul no alto com "BRASIL", e a cor dos caracteres pela
  categoria (particular preto, comercial vermelho, oficial azul, especial verde, colecionador
  cinza e diplomática dourado). O texto: três letras, um número, uma letra e dois números.
- **Antiga:** fundo cinza (particular), vermelho (comercial) ou branco (oficial), a faixa da
  cidade no alto e o texto com o hífen: três letras e quatro números.

O texto sai sempre no formato válido ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]]). A placa de moto fica de fora: o pátio é de
caminhões.

- **`MARGEM_DO_TEXTO`** = `0.9`: O texto ocupa no máximo 90% da largura da placa.
- **`CATEGORIAS`**: De cada tipo, as categorias: a cor do fundo e a dos caracteres.
- **`CIDADES`**: A faixa da placa antiga (cidades de verdade, sem nenhum dado de pessoa).
- **`Placa`** (classe): O que vai numa placa sintética.
- **`sortear_texto`**: Um texto de placa no formato do tipo (sem o hífen).
- **`sortear`**: Uma placa: o tipo (metade de cada), a categoria (a particular é a mais comum) e o texto.
- **`desenhar`**: A placa de frente, em RGB, com 2 pixels por milímetro.

### `ml.sinteticas.variacoes`

`ml/src/ml/sinteticas/variacoes.py`

As variações que imitam o recorte da câmera ([[D-72]]).

A perspectiva (a câmera nunca está de frente), o borrão (o movimento e o foco), a luz (o sol, a
sombra e a noite), a sujeira, um pedaço coberto (o engate, o para-choque), o ruído e o tamanho
(o recorte da caixa tem de 60 a 240 pixels de largura). A compressão do JPEG fica para a hora de
gravar. Tudo sai do gerador que se passa: a mesma semente dá a mesma imagem.

- **`FOLGA`** = `0.12`: Quanto da imagem em volta da placa entra no recorte (o para-choque), de cada lado.
- **`variar`**: A placa como a câmera a recortaria.

## Testes

- `ml/tests/test_ml_sinteticas.py`: O gerador de placas sintéticas ([[4.6 Dados de treino|SDD 4.6]], [[D-44]] e [[D-72]]).

---

Do [[Mapa do código]].

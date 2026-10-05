---
tipo: "pacote"
fonte: "borda/src/borda/leitor/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `borda/src/borda/leitor/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# borda.leitor

Pasta `borda/src/borda/leitor/`.

Leitor de placas da caixa ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]]): a interface, o formato e a votação entre quadros.

## Módulos

### `borda.leitor.formato`

`borda/src/borda/leitor/formato.py`

O formato da placa lida ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]]): valida e corrige pela posição de cada caractere.

Placa antiga ``LLLNNNN`` e Mercosul ``LLLNLNN``: as três primeiras posições são letras, a 4ª,
a 6ª e a 7ª são números, e a 5ª aceita os dois. Onde só cabe letra, um número parecido vira
letra (``0→O``, ``1→I``, ``8→B``, ``5→S``); onde só cabe número, o contrário. A 5ª posição
nunca é corrigida, porque os dois formatos são válidos.

O leitor nunca inventa nem apaga caractere: só os separadores saem, e o que não fica com 7
caracteres, ou tem um caractere sem correção possível na posição, é descartado.

- **`PENALIDADE_POR_CORRECAO`** = `0.9`: Cada caractere corrigido multiplica a confiança por este valor.
- **`PlacaFormatada`** (classe): Uma placa no formato canônico, com a confiança já reduzida pelas correções.
- **`formatar`**: Põe o texto lido no formato da placa, corrigindo pela posição.

### `borda.leitor.interface`

`borda/src/borda/leitor/interface.py`

A interface única do leitor de placas ([[4.5 Interface única e dois motores|SDD 4.5]]): entra uma imagem, saem os textos lidos.

Qualquer motor (o v0 com modelos pré-treinados, o v1 com pesos nossos, o comercial) fica atrás
desta interface: trocar de motor não muda nada fora da caixa (SDD [[D-07]]).

- **`Quadro`** = `npt.NDArray[np.uint8]`: Uma imagem colorida, em BGR, com forma (altura, largura, 3): o que a captura entrega.
- **`Regiao`** (classe): Um retângulo na imagem, em pixels: canto de cima à esquerda, largura e altura.
- **`LeituraBruta`** (classe): Um texto que o motor achou na imagem, ainda sem a regra de formato da placa.
- **`LeitorDePlacas`** (classe): Um motor de leitura de placas.

### `borda.leitor.v0`

`borda/src/borda/leitor/v0.py`

Leitor v0 ([[T15]]): modelos pré-treinados de terceiros, só para avaliação interna ([[4.1 Regra de licença|SDD 4.1]]).

- **Veículos:** YOLOX-Tiny (ONNX publicado pelo projeto; pesos sem licença declarada).
- **Texto:** PP-OCRv5 mobile do PaddleOCR (Apache-2.0): um modelo acha as linhas de texto, outro
  lê cada linha. A regra de formato da placa (``formato``) vem depois, no rastreador.

Tudo roda no ONNX Runtime, com NumPy e Pillow, sem OpenCV. Os pesos de terceiros servem só
para avaliação interna (SDD [[D-26]]) e ficam em ``modelos/v0`` (``uv run tarefas modelos``).

Não há meta de acerto no v0: ele existe para o fluxo funcionar; o acerto é trabalho do v1, com
pesos nossos (mês 2).

- **`CLASSES_DE_VEICULO`**: As classes do COCO que contam como veículo.
- **`LADO_MAIOR_DO_TEXTO`** = `960`: O modelo de texto trabalha com o lado maior da imagem neste tamanho (múltiplo de 32).
- **`preparar_yolox`**: Põe o quadro no tamanho do YOLOX sem distorcer (o resto fica cinza).
- **`decodificar_yolox`**: Transforma a saída crua do YOLOX em veículos, na escala do quadro.
- **`nms`**: Supressão de não máximos: das caixas que se sobrepõem demais, fica a de nota maior.
- **`DetectorYolox`** (classe): Acha os veículos de um quadro com o YOLOX-Tiny (só avaliação interna).
- **`caixas_de_texto`**: Acha as linhas de texto no mapa de probabilidade do detector de texto.
- **`expandir`**: Alarga a caixa como o PaddleOCR, sem sair da imagem.
- **`decodificar_ctc`**: Lê a saída do modelo de leitura: junta repetidos seguidos e tira os brancos (CTC).
- **`LeitorPaddle`** (classe): Lê os textos de uma imagem com os modelos do PaddleOCR (PP-OCRv5 mobile).
- **`carregar_v0`**: Carrega o detector e o leitor do v0 da pasta dos modelos.

### `borda.leitor.votacao`

`borda/src/borda/leitor/votacao.py`

Votação entre os quadros do mesmo veículo ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]]).

O veículo aparece em vários quadros do vídeo, e o leitor pode errar em alguns. Fica a placa
lida em mais quadros; no empate, a de maior confiança média; no empate total, a primeira em
ordem alfabética (para o resultado não depender da ordem dos quadros).

A confiança final é a média das confianças dos quadros vencedores vezes a fração dos quadros
que concordam: discordância entre quadros é sinal de leitura duvidosa.

- **`LeituraDoQuadro`** (classe): A placa (já formatada) lida num quadro, com a confiança.
- **`ResultadoDaVotacao`** (classe): A placa escolhida para o veículo.
- **`votar`**: Escolhe a placa do veículo entre as leituras dos quadros.

## Testes

- `borda/tests/test_borda_leitor_v0.py`: Leitor v0 ([[T15]]): preparo e decodificação dos modelos, sem OpenCV.

---

Do [[Mapa do código]].

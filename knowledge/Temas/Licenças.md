---
tipo: "tema"
escrita: "à mão"
atualizada: "2026-10-05"
tags: [tema]
---

# Licenças

O produto é fechado: tudo o que entra nele precisa de licença que permita isso.

## O essencial

- **Dependências:** só MIT, BSD, Apache, ISC, PSF ou PostgreSQL. MPL-2.0 só para biblioteca
  usada sem modificação. **GPL, LGPL e AGPL nunca** ([[6.1 Stack]]). A CI confere as
  dependências Python a cada envio.
- **O driver do banco é o pg8000** (BSD-3), e não o psycopg (LGPL) ([[D-18]]); por isso a fila de
  tarefas é uma tabela nossa, e não uma biblioteca sobre o psycopg ([[D-38]]).
- **Bibliotecas nativas dentro das rodas:** LGPL só usada sem modificação e carregada
  dinamicamente; GPL só com a exceção de runtime do GCC; FFmpeg só sem partes GPL, e o PyAV do
  PyPI não entra ([[D-27]]). O vídeo da caixa usa o `opencv-python-headless` ([[D-29]]), com o
  OpenSSL 1.1.1w aceito e creditado ([[D-31]]). A CI não vê essas bibliotecas: os créditos ficam
  em [[Avisos de terceiros da caixa de borda]].
- **Modelos de visão:** só código Apache, MIT ou BSD e **pesos treinados por nós** ([[D-05]],
  [[4.1 Regra de licença]]). O YOLO da Ultralytics (AGPL) não entra. Pesos de terceiros só para
  comparar modelos e avaliar internamente, como o leitor v0 ([[D-26]], [[T13]]).
- **Bases de placas:** RodoSol-ALPR e UFPR-ALPR são só acadêmicas e nunca treinam o produto
  ([[4.6 Dados de treino]], [[Validação - fontes de placas]]). O treino começa com placas
  sintéticas e bases abertas ([[D-44]]) e roda num ambiente à parte, porque o PyTorch com GPU
  traz bibliotecas da NVIDIA com licença proprietária ([[D-40]]).
- **Arquivos de terceiros do painel** (o HTMX, o three.js) ficam em
  `nuvem/src/nuvem/web/estatico/`, com a licença e o hash no LEIA-ME de lá; um teste confere os
  hashes ([[Arquivos de terceiros do painel]]). **Fontes com a licença SIL OFL 1.1** entram do
  mesmo jeito, usadas sem modificação ([[D-50]]).

## Onde ler

- Regras: [[CLAUDE - regras do repositório]] (regra 1), [[4.1 Regra de licença]], [[6.1 Stack]].
- Fatos verificados (licenças, versões, preços): [[Validação - fatos técnicos da stack]].
- Decisões: [[D-05]], [[D-10]], [[D-18]], [[D-26]], [[D-27]], [[D-29]], [[D-31]], [[D-40]],
  [[D-44]], [[D-50]].
- Itens já fechados: [[ABERTO-13]], [[ABERTO-14]], [[ABERTO-16]], [[ABERTO-21]].

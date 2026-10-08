---
tipo: "pacote"
fonte: "ml/src/ml/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `ml/src/ml/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# ml

Pasta `ml/src/ml/`.

Treino, avaliação e exportação dos modelos do leitor de placas ([[4.6 Dados de treino|SDD, seção 4.6]]).

## Subpacotes

- [[ml.sinteticas]]: Placas sintéticas para começar o treino da leitura sem placas reais ([[4.6 Dados de treino|SDD 4.6]], [[D-44]] e [[D-72]]).

## Módulos

### `ml.baixar_modelos`

`ml/src/ml/baixar_modelos.py`

Baixa os modelos do leitor v0 para ``modelos/v0`` (fora do Git): ``uv run tarefas modelos``.

Cada arquivo tem endereço com versão fixa e resumo SHA-256 conferido depois do download: o que
chega é exatamente o que foi conferido na [[T13]]. A licença e o uso permitido de cada um estão em
[[Validação - fatos técnicos da stack|docs/validacao/fatos-tecnicos-stack.md]]. O detector (YOLOX) não tem licença declarada para os
pesos: só avaliação interna e a demonstração do mês 1 ([[4.1 Regra de licença|SDD 4.1]]).

- **`PASTA_PADRAO`** = `Path('modelos') / 'v0'`: Relativa à raiz do repositório (``modelos/`` fica fora do Git).
- **`ArquivoDeModelo`** (classe): Um arquivo de modelo: onde baixar, como conferir e o que a licença deixa fazer.
- **`DICIONARIO`** = `'texto_leitura_dicionario.txt'`: Os caracteres que o modelo de leitura conhece, um por linha (tirados do ``.yml``).
- **`ResumoErradoError`** (classe): O arquivo baixado não tem o resumo SHA-256 esperado (foi trocado ou veio pela metade).
- **`baixar`**: Baixa os modelos que faltam (ou estão estragados) e confere o resumo de cada um.
- **`extrair_dicionario`**: Grava os caracteres do modelo de leitura (``PostProcess.character_dict``), um por linha.
- **`principal`**: Baixa os modelos do v0 e prepara o dicionário; devolve o código de saída.

## Testes

- `ml/tests/test_ml_baixar_modelos.py`: Download dos modelos do leitor v0 ([[T15]]): só com o resumo SHA-256 conferido, fora do Git.
- `ml/tests/test_ml_pacote.py`: O pacote ml é instalado pelo workspace do projeto.

---

Do [[Mapa do código]].

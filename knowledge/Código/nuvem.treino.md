---
tipo: "pacote"
fonte: "nuvem/src/nuvem/treino/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/treino/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.treino

Pasta `nuvem/src/nuvem/treino/`.

A base de treino ([[4.6 Dados de treino|SDD 4.6]] e [[8.3 LGPD|8.3]], [[D-71]]): a conferência do porteiro vira rótulo, com o contrato.

## Módulos

### `nuvem.treino.__main__`

`nuvem/src/nuvem/treino/__main__.py`

``python -m nuvem.treino``: a pasta da base de treino (``uv run tarefas treino``, [[D-71]]).

Monta, em ``dados/treino`` (ou em ``--destino``), os recortes aceitos e corrigidos, separados
entre o treino e a régua, com um CSV de cada, para o ambiente de treino ([[D-40]]). Lê a configuração
do ambiente (``PATIO_URL_BANCO`` e o armazenamento), como a API.

### `nuvem.treino.exportacao`

`nuvem/src/nuvem/treino/exportacao.py`

A exportação da base de treino pela linha de comando (``uv run tarefas treino``, [[D-71]]).

- **`DESTINO_PADRAO`** = `Path('dados/treino')`: Dentro de ``dados/``, que o Git ignora: os recortes são de placas reais.
- **`exportar_da_configuracao`**: Monta a pasta com o banco e o armazenamento da configuração.
- **`principal`**: Lê os argumentos e a configuração, monta a pasta e diz quantos recortes foram.

### `nuvem.treino.guarda`

`nuvem/src/nuvem/treino/guarda.py`

Onde ficam as cópias dos recortes da base de treino ([[D-71]]).

Uma pasta à parte (``treino/``) no mesmo armazenamento das fotos: no disco, ou no S3. Fora da
guarda das fotos (90 dias): a cópia vale enquanto valer a autorização do contrato. Cada empresa
tem a sua pasta, que se apaga inteira quando ela revoga.

- **`GuardaDoTreino`** (classe): Grava, lê e apaga as cópias dos recortes.
- **`guarda_do_treino_da_configuracao`**: O S3 das fotos, se configurado; senão, a pasta das fotos.
- **`TreinoNoDisco`** (classe): As cópias numa pasta (``<pasta das fotos>/treino``).
- **`TreinoNoS3`** (classe): As cópias no balde das fotos, em ``treino/``.

### `nuvem.treino.modelos`

`nuvem/src/nuvem/treino/modelos.py`

Tabelas da base de treino ([[5.1 Entidades|SDD 5.1]], [[D-71]]).

O rótulo não é prova: ele se apaga quando a empresa revoga a autorização do treino.

- **`OrigemDoRotulo`** = `Literal['conferencia', 'rotulagem']`: A conferência do porteiro ou a rotulagem no Label Studio ([[ABERTO-18]]).
- **`AutorizacaoDeTreino`** (classe): A cláusula do contrato que autoriza o uso das conferências da empresa no treino.
- **`Rotulo`** (classe): Um recorte de placa com a placa certa, para o treino ou para a régua.

### `nuvem.treino.servico`

`nuvem/src/nuvem/treino/servico.py`

A base de treino ([[4.6 Dados de treino|SDD 4.6]] e [[8.3 LGPD|8.3]], [[D-71]]).

- **A autorização:** a administração registra a data da cláusula do contrato de cada empresa (a
  de demonstração não entra). Revogar apaga os rótulos e as cópias dos recortes da empresa.
- **Rotular:** a cada hora, o worker transforma a última conferência de cada recorte, feita desde
  a data da cláusula, num rótulo a revisar, e copia o recorte para a base de treino (a foto se
  apaga aos 90 dias; a cópia, não). Sem o recorte (a foto já saiu), o rótulo nasce descartado.
- **A régua:** 1 em cada 10 rótulos, pelo resumo da passagem e da foto (``conjunto_de``): a mesma
  conferência cai sempre no mesmo conjunto, e o conjunto fica gravado.
- **A rotulagem:** aceitar, corrigir ou descartar. Só os aceitos e os corrigidos vão para o treino.
- **A exportação:** a pasta que o ambiente de treino lê ([[D-40]]): os recortes e um CSV por conjunto.

- **`ROTULOS_POR_VEZ`** = `500`: O worker rotula no máximo estes recortes a cada volta (o resto, na seguinte).
- **`UM_EM`** = `10`: A régua recebe 1 em cada 10 rótulos.
- **`Exportacao`** (classe): Quantos recortes foram para cada conjunto.
- **`autorizar`**: Registra a cláusula do contrato da empresa (a anterior deixa de valer; sem ``commit``).
- **`revogar`**: Revoga a autorização e apaga os rótulos e as cópias da empresa (sem ``commit``).
- **`autorizacoes`**: As empresas (menos as de demonstração), cada uma com a autorização ativa, se tiver.
- **`conjunto_de`**: Treino ou régua, pelo resumo da passagem e da foto: sempre o mesmo para o mesmo recorte.
- **`rotular`**: Transforma as conferências autorizadas que ainda não são rótulos (sem ``commit``).
- **`pendentes`**: Os rótulos a revisar, dos mais antigos.
- **`contagem`**: Quantos rótulos há em cada situação, e quantos na régua.
- **`obter_rotulo`**: Um rótulo.
- **`revisar`**: Aceita, corrige (com a placa certa) ou descarta um rótulo (sem ``commit``).
- **`exportar`**: Monta a pasta do treino: ``treino/`` e ``regua/`` com os recortes, e um CSV de cada.

## Testes

- `nuvem/tests/test_nuvem_treino.py`: A base de treino ([[4.6 Dados de treino|SDD 4.6]] e [[8.3 LGPD|8.3]], [[D-71]]): a conferência do porteiro vira rótulo, com o contrato.

---

Do [[Mapa do código]].

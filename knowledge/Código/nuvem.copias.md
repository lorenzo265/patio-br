---
tipo: "pacote"
fonte: "nuvem/src/nuvem/copias/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/copias/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.copias

Pasta `nuvem/src/nuvem/copias/`.

As cópias do banco e a restauração de teste ([[7.2 Nuvem (AWS, sa-east-1)|SDD 7.2]], [[D-74]]).

Uma vez por dia, depois das 3h de Brasília, o worker faz a cópia do banco (``pg_dump``) direto
para o balde das cópias; uma vez por mês, volta a última num banco temporário e confere.

## Módulos

### `nuvem.copias.guarda`

`nuvem/src/nuvem/copias/guarda.py`

Onde as cópias do banco ficam ([[D-74]]): o balde das cópias, no mesmo S3 das fotos.

O arquivo vai do ``pg_dump`` para o balde enquanto é lido, sem passar pelo disco; o resumo e o
tamanho saem no caminho.

- **`Legivel`** (classe): Qualquer coisa de onde se leem bytes (o ``pg_dump``, o arquivo no balde).
- **`LeitorComResumo`** (classe): Lê de outro leitor e conta o tamanho e o resumo (SHA-256) do que passou.
- **`Gravada`** (classe): O tamanho e o resumo da cópia gravada.
- **`GuardaDasCopias`** (classe): Grava, abre e apaga os arquivos das cópias.
- **`CopiasNoS3`** (classe): As cópias no balde das cópias (privado e cifrado; o guia da produção diz como criar).
- **`guarda_das_copias_da_configuracao`**: O balde das cópias, se configurado (``PATIO_COPIAS_S3_BALDE``); senão, nenhum.

### `nuvem.copias.modelos`

`nuvem/src/nuvem/copias/modelos.py`

As cópias do banco e as restaurações de teste ([[D-74]]): da plataforma, fora das empresas.

- **`CopiaDoBanco`** (classe): Uma cópia do banco no balde das cópias, com o que ela precisa ter (o manifesto).
- **`RestauracaoDeTeste`** (classe): Uma volta de cópia num banco temporário, para conferir que ela serve.

### `nuvem.copias.postgres`

`nuvem/src/nuvem/copias/postgres.py`

O banco de verdade da cópia e da restauração de teste: o ``pg_dump`` e o ``pg_restore`` ([[D-74]]).

Os dois são do cliente do PostgreSQL da mesma versão do servidor (16), que vem na imagem da
nuvem. A conexão vai pelas variáveis do próprio PostgreSQL (``PGHOST``, ``PGPASSWORD`` ...),
montadas da ``PATIO_URL_BANCO``: a senha não aparece na lista de processos.

A restauração de teste cria um banco temporário no mesmo servidor (``patio_restauracao_...``),
volta a cópia nele e o apaga no fim, dê certo ou não. Nada é apagado fora dele.

- **`ERRO_MAXIMO`** = `500`: Quantos caracteres do fim do erro do ``pg_dump`` ou do ``pg_restore`` entram na mensagem.
- **`ProgramaFalhouError`** (classe): O ``pg_dump`` ou o ``pg_restore`` terminou com erro.
- **`BancoPostgres`** (classe): O servidor do banco da nuvem, para copiar e para a restauração de teste.

### `nuvem.copias.servico`

`nuvem/src/nuvem/copias/servico.py`

A cópia diária, a restauração de teste e a guarda das cópias ([[7.2 Nuvem (AWS, sa-east-1)|SDD 7.2]], [[D-74]]).

O worker chama ``cuidar`` de tempos em tempos; o que está pendente roda na hora:

- **a cópia:** uma por dia, a partir das 3h de Brasília. Antes de começar, anota o manifesto
  (a migração, as contagens das tabelas só de acréscimo e o último evento); ao terminar, o
  resumo e o tamanho;
- **a guarda:** apaga as cópias de mais de 30 dias, menos a mais nova;
- **a restauração de teste:** uma por mês, a partir do dia 1º às 4h. Volta a última cópia num
  banco temporário e confere o resumo, a migração e se as contagens e o último evento são pelo
  menos os anotados (a nuvem continua gravando enquanto a cópia é feita). Se falhar, tenta de
  novo no dia seguinte.

Cada parte que falha vira um erro registrado (e um alarme, [[D-61]]) e não impede as outras.

- **`NOVA_TENTATIVA`** = `timedelta(hours=20)`: Depois de uma restauração de teste que falhou, quanto esperar para tentar de novo.
- **`Banco`** (classe): O servidor do banco: de onde sai a cópia e onde ela volta para o teste.
- **`Copias`** (classe): O que o worker precisa para as cópias: onde guardar e de onde copiar.
- **`copias_da_configuracao`**: As cópias, se há o balde delas (``PATIO_COPIAS_S3_BALDE``); senão, nenhuma.
- **`Manifesto`** (classe): O que a cópia precisa ter, anotado antes de ela começar.
- **`tabelas_so_de_acrescimo`**: As tabelas com o gatilho ``so_acrescenta`` ([[5.5 Garantias|SDD 5.5]]): só crescem, então dá para contar.
- **`manifesto`**: A migração, as contagens das tabelas só de acréscimo e o último evento, agora.
- **`marco_da_copia`**: As últimas 3h de Brasília até ``agora``: a cópia do dia é a feita depois delas.
- **`marco_da_restauracao`**: O último dia 1º às 4h de Brasília até ``agora``: a restauração do mês vem depois dele.
- **`copia_pendente`**: Se ainda não há cópia desde as últimas 3h.
- **`restauracao_pendente`**: Se o mês ainda não tem restauração de teste que passou, e a última tentativa já esfriou.
- **`nome_da_copia`**: O nome do arquivo no balde, pela hora em UTC (ex.: ``copia-20261006-060000.dump``).
- **`fazer_copia`**: Anota o manifesto, copia o banco para o balde e registra a cópia.
- **`apagar_vencidas`**: Apaga as cópias de mais de 30 dias, menos a mais nova; devolve quantas.
- **`conferir`**: O que não confere entre o banco restaurado e o manifesto da cópia (vazio: tudo certo).
- **`testar_restauracao`**: Volta a última cópia num banco temporário, confere e registra o resultado.
- **`cuidar`**: Faz o que estiver pendente: a cópia, a guarda e a restauração de teste, nesta ordem.

## Testes

- `nuvem/tests/test_nuvem_copias.py`: As cópias do banco e a restauração de teste ([[7.2 Nuvem (AWS, sa-east-1)|SDD 7.2]], [[D-74]]), com um balde na memória e um servidor de mentira: o banco "restaurado" é o próprio banco do teste.
- `nuvem/tests/test_nuvem_copias_postgres.py`: O ``pg_dump`` e o ``pg_restore`` de verdade, no banco de teste ([[D-74]]).
- `nuvem/tests/test_nuvem_copias_s3.py`: O balde das cópias ([[D-74]]): a cópia vai ao S3 enquanto é lida, com o resumo e o tamanho.

---

Do [[Mapa do código]].

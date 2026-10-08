---
tipo: "pacote"
fonte: "nuvem/src/nuvem/prova/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/prova/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.prova

Pasta `nuvem/src/nuvem/prova/`.

A prova da visita ([[5.5 Garantias|SDD 5.5]], [[D-69]]): a cadeia de resumos, a âncora do dia e a conferência.

## Módulos

### `nuvem.prova.ancoras`

`nuvem/src/nuvem/prova/ancoras.py`

Onde a âncora do dia fica guardada ([[D-69]]).

- **No balde das âncoras** (``PATIO_ANCORAS_S3_BALDE``, a produção): cada arquivo vai com o Object
  Lock no modo de conformidade por 5 anos (a guarda da trilha de prova, [[8.3 LGPD|SDD 8.3]]). Nem o dono da
  conta apaga ou troca o arquivo antes disso. O balde precisa ter sido criado com a trava ligada.
- **No S3 das fotos, sem trava** (a demonstração, no Supabase, que não tem a trava).
- **Na pasta das fotos**, sem trava (o ambiente local).

Em todos, o arquivo gravado não se troca: gravar o mesmo de novo não faz nada, e gravar outro
conteúdo com o mesmo nome é erro.

- **`TRAVA`** = `timedelta(days=round(365.25 * 5))`: 5 anos: a guarda da trilha de prova ([[8.3 LGPD|SDD 8.3]]).
- **`AncoraDiferenteError`** (classe): Já existe outra âncora com este nome: a gravada não se troca.
- **`Gravada`** (classe): Onde a âncora ficou, e se está travada contra apagar e trocar.
- **`GuardaDasAncoras`** (classe): Grava e lê os arquivos das âncoras.
- **`guarda_da_configuracao`**: O balde das âncoras, se configurado; senão, o S3 das fotos; senão, a pasta das fotos.
- **`AncorasNoS3`** (classe): As âncoras num balde S3, em ``ancoras/``; travadas no balde das âncoras.
- **`AncorasNoDisco`** (classe): As âncoras numa pasta (``<pasta das fotos>/ancoras``), sem trava.

### `nuvem.prova.cadeia`

`nuvem/src/nuvem/prova/cadeia.py`

A regra do resumo da cadeia de prova ([[D-69]]), sem banco: a mesma que o arquivo da prova explica.

O resumo de um elo é o SHA-256, em hexadecimal, do texto: o resumo do elo anterior (64 zeros no
primeiro), uma quebra de linha e o JSON de ``{"tipo", "referencia", "conteudo"}``, com as chaves
em ordem, sem espaços e em UTF-8. Mudar qualquer coisa num elo muda o resumo dele; e, como o
seguinte guarda esse resumo, quebra a ligação dali em diante.

- **`INICIO`** = `'0' * 64`: O "anterior" do primeiro elo de cada visita.
- **`REGRA`**: A regra, escrita no arquivo da prova para quem quiser conferir sem nós.
- **`Elo`** (classe): Um elo da cadeia, como está guardado.
- **`Quebra`** (classe): O primeiro elo que não confere, e por quê.
- **`json_canonico`**: O JSON com as chaves em ordem e sem espaços: o mesmo valor dá sempre o mesmo texto.
- **`resumo_do_elo`**: O resumo de um elo, pela regra (``REGRA``).
- **`primeira_quebra`**: Refaz a cadeia na ordem e devolve o primeiro elo que não confere (``None``: íntegra).

### `nuvem.prova.modelos`

`nuvem/src/nuvem/prova/modelos.py`

Tabelas da prova ([[5.1 Entidades|SDD 5.1]] e [[5.5 Garantias|5.5]], [[D-69]]).

A foto resumida e o elo só se acrescentam: um gatilho no banco recusa alterar ou apagar
(migração 0024), como nos eventos da visita. A âncora do dia é da plataforma, uma por dia; o
arquivo dela é que fica travado, fora do banco.

- **`FotoRecebida`** (classe): O resumo de uma foto da passagem, feito pela nuvem logo que a passagem chegou.
- **`EloDaProva`** (classe): Um elo da cadeia de uma visita: o retrato de um registro e o resumo (``prova.cadeia``).
- **`AncoraDoDia`** (classe): A âncora de um dia (UTC): o último resumo de cada visita que mudou, num arquivo travado.

### `nuvem.prova.servico`

`nuvem/src/nuvem/prova/servico.py`

A prova da visita ([[5.5 Garantias|SDD 5.5]], [[D-69]]).

- **O resumo das fotos:** logo que a passagem chega (as fotos chegam antes dela), a tarefa
  "resumir as fotos" lê cada foto do armazenamento e guarda o SHA-256 (``FotoRecebida``).
- **Selar:** cada registro da visita (a passagem, cada foto, cada evento, cada conferência da
  placa, cada situação das mensagens ao motorista, cada marca de disputa e cada foto apagada
  pela guarda, [[D-70]]) vira um elo da cadeia (``prova.cadeia``),
  com o retrato do registro. O worker sela a cada minuto o que chegou nos últimos 7 dias; a
  página da prova sela a visita que abre. Os novos de uma vez entram na ordem em que chegaram.
- **Conferir:** refaz a cadeia, compara cada elo com o registro de origem, relê as fotos e
  confere as âncoras; aponta o primeiro elo quebrado.
- **A âncora do dia:** uma vez por dia (UTC), o último resumo de cada visita que mudou no dia vai
  para um arquivo travado (``prova.ancoras``), fora do banco.

- **`JANELA_DE_SELAR`** = `timedelta(days=7)`: O worker procura, a cada minuto, só o que chegou nesta janela (a página sela o resto).
- **`MARGEM_DA_ANCORA`** = `timedelta(minutes=10)`: A âncora de um dia só é gravada 10 minutos depois de ele acabar: quem selava, já gravou.
- **`TRAVA_DA_PROVA`** = `7304`: A trava do PostgreSQL de cada visita (com o id dela): dois selando a mesma não se cruzam.
- **`ORDEM_DOS_TIPOS`**: Os que chegaram na mesma hora entram nesta ordem.
- **`SITUACOES_DA_MENSAGEM`**: Cada horário preenchido da mensagem é um elo (ela anda; o horário de cada situação, não).
- **`Registro`** (classe): Um registro da visita, com o retrato que vai no elo.
- **`AncoraConferida`** (classe): O que a conferência achou na âncora de um dia.
- **`Conferencia`** (classe): O resultado da conferência da prova de uma visita.
- **`resumir_fotos`**: Guarda o SHA-256 de cada foto da passagem que está no armazenamento; devolve quantas novas.
- **`selar`**: Sela as visitas com registro novo nos últimos 7 dias (com ``flush``); devolve os elos.
- **`selar_a_visita`**: Sela o que falta de uma visita que o usuário vê; devolve quantos elos novos.
- **`elos_da_visita`**: Os elos de uma visita que o usuário vê, na ordem.
- **`visitas_para_a_prova`**: As últimas visitas dos sites que o usuário vê, das mais novas; com ``placa``, só as dela.
- **`nomes_das_pessoas`**: Os nomes das pessoas da empresa do usuário, por id (quem registrou cada coisa).
- **`conferir`**: Confere a prova de uma visita que o usuário vê: a cadeia, a origem, as fotos e as âncoras.
- **`gravar_ancoras`**: Grava a âncora de cada dia (UTC) já terminado que tem elos e ainda não tem âncora.

## Testes

- `nuvem/tests/test_nuvem_prova.py`: A prova da visita ([[5.5 Garantias|SDD 5.5]], [[D-69]]): o resumo das fotos, a cadeia, a conferência e a âncora.
- `nuvem/tests/test_nuvem_prova_ancoras.py`: Onde a âncora do dia fica guardada ([[D-69]]): no disco, ou num balde S3 travado (Object Lock).
- `nuvem/tests/test_nuvem_prova_cadeia.py`: A regra do resumo da cadeia de prova ([[D-69]]), sem banco.

---

Do [[Mapa do código]].

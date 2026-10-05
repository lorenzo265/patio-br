# Plano do mês 2 (novembro de 2026): leitor próprio, agendamento e casamento

Plano de implementação do mês 2 do cronograma do SDD (`docs/SDD.md`, seção 10).
Versão 2 · 2026-10-05 · Aprovado pelo Lorenzo; o site parceiro ficou para depois (seção 2)

---

## 1. Objetivo e marco

**Objetivo:** duas frentes em paralelo.

1. **Leitor próprio:** gravar as passagens do site parceiro, rotular 3 a 5 mil placas, montar a
   régua fixa e treinar o leitor v1, com pesos nossos (SDD 4.1, 4.6 e 4.7).
2. **Agendamento e casamento:** o agendamento chega pelo link da transportadora ou pela planilha
   do cliente, e a chegada da caixa casa com ele: check-in automático ou exceção (SDD 2.2, 3.4 e
   5.3).

~~**Marco do mês (o teste de "pronto"): o teste técnico** (SDD 10).~~ → próximo plano: o site
parceiro foi adiado em 05/10 (seção 2). Fica como marco o fluxo do agendamento à saída na
demonstração (T35), com a conferência da placa pelo porteiro (T38).

> Na régua fixa, o leitor v1 é comparado com o leitor comercial (e com o v0): acerto por placa e
> acerto da composição casando com o agendamento. O resultado decide o caminho do piloto:
>
> | Composição casando com o agendamento | Ação |
> |---|---|
> | ≥ 95% | segue com o leitor próprio |
> | 90–95% | segue, com mais um ciclo de rotulagem e treino antes do modo sombra |
> | < 90% | o piloto começa com o leitor comercial; o próprio continua treinando com dados do piloto |

**Fora do mês 2** (para não inchar):
- **mês 3:** telas definitivas de portaria e pátio, resolver as exceções pela tela, estados
  completos da visita (fila, chamada, doca), alertas, trilha de prova completa, o conector
  `api_generica`, e na caixa a saúde, a atualização e o contêiner;
- **mês 4:** WhatsApp e extrato.

**O que fica do mês 1:** a medição no N150 (T20) entra na semana 2, já com o v1. Os vídeos da
T19 passam a ser as gravações do site parceiro (T21).

---

## 2. Antes de começar: decisões do Lorenzo

Quatro decisões travam tarefas do mês. As três primeiras estão no SDD como itens em aberto.

| # | Decisão | O que trava | Recomendação |
|---|---|---|---|
| D1 | **`[ABERTO-15]`: gravar sem guardar rostos.** O detector aprende com quadros inteiros, e a base de treino só pode ter recortes de placa (SDD 4.6 e 8.3). | T21 e o treino do detector (T24) | Cada câmera de placa ganha uma **região de gravação**, abaixo do para-brisa, marcada no cadastro da câmera. A caixa só guarda o que está nela. A câmera é posicionada para enquadrar o para-choque (guia de posicionamento, `[ABERTO-08]`). O detector do v1 aprende veículo e placa dentro dessa região. |
| D2 | **`[ABERTO-16]`: ambiente de treino.** O PyTorch com GPU traz bibliotecas da NVIDIA com licença proprietária. | T24 e T25 | O treino roda num **ambiente à parte**, fora do `uv.lock` do projeto, só na máquina de GPU alugada. Nada dele vai para a caixa nem para a nuvem. Os modelos saem em ONNX, e o código de treino segue a regra de licença (Apache, MIT ou BSD). |
| D3 | **`[ABERTO-17]`: leitor comercial no teste técnico.** Mandar as imagens da régua ao Plate Recognizer é passar dado de terceiros a outro operador, talvez fora do Brasil. | T36 (o marco) | Perguntar ao advogado (N3 do mês 1) e ao site parceiro. Se não puder, usar o programa local do Plate Recognizer, ou comparar o v1 só com o v0 e com o registro manual da portaria. |
| D4 | **`[ABERTO-11]`: fila de tarefas no PostgreSQL.** O casamento e o "não veio" rodam fora do pedido da caixa. | T33 | **Tabela própria**, com um worker que pega a próxima tarefa por `SELECT ... FOR UPDATE SKIP LOCKED`. As bibliotecas de fila para PostgreSQL que conheço usam o psycopg (LGPL), que a D-18 tirou. |

Mais uma pergunta, sem item no SDD: **quem rotula as 3 a 5 mil placas, e em quantas horas** (N10).
Com a leitura do v0 como pré-rótulo, a pessoa só confere e corrige. O ritmo real é medido na
primeira hora de rotulagem.

**Decididas em 05/10:**
- D1 a D4 pela recomendação (SDD D-39, D-40, D-41 e D-38).
- Quem rotula: o Lorenzo. Ele pediu também que o porteiro confira a placa na plataforma,
  comparando a leitura com a foto (T38, SDD D-42).
- O site parceiro fica para depois: o Lorenzo quer o produto mais completo antes de levá-lo
  ao site. As primeiras placas vêm de outra fonte (`[ABERTO-18]`,
  `docs/validacao/fontes-de-placas.md`). O que depende do site sai deste mês (riscado abaixo).

---

## 3. Como trabalhar neste plano

As mesmas regras do mês 1 (`CLAUDE.md`), com estes ajustes:

- **Numeração:** as tarefas continuam a do mês 1 (T21 em diante), para "T13" nunca ser ambíguo.
  As branches levam `mes2/` (ex.: `mes2/t27-agendamentos`).
- **Ordem dos PRs:** quando um PR depende de outro, ele é aberto depois. O merge segue a ordem
  dos números dos PRs.
- **Dados do site parceiro** (vídeos, quadros, placas, rótulos) ficam em `dados/`, fora do Git.
  No repositório entram só o código, o manifesto da régua (nomes e resumos dos arquivos, sem as
  placas) e os números das medições.

---

## 4. Tarefas técnicas

Ordem sugerida por semana. A semana 4 tem folga.

### Semana 1 — gravar, rotular e a régua

#### T21. Gravação no site parceiro

**Objetivo:** a caixa grava, sem operar, as passagens do site parceiro para rotular.

**Depende de:** D1 decidida (D-39) e um lugar para gravar, com o aviso de gravação: o site
parceiro (adiado em 05/10) ou os portões do `[ABERTO-18]`.

**Arquivos:** `borda/src/borda/gravacao.py`, o comando `caixa gravar`, o campo da região de
gravação no cadastro da câmera (nuvem), testes.

**Regras (teste primeiro):**
- Grava só a região de gravação da câmera (D1); fora dela, nada vai para o disco.
- Grava por passagem: os quadros amostrados (5 por segundo) em JPEG, em
  `dados/gravacoes/<data>/<passagem>/`, com a leitura do v0 ao lado (o pré-rótulo).
- Tem limite de disco: acima do limite, apaga as passagens mais antigas.
- Nada sobe para a nuvem sozinho; as gravações saem da caixa à mão, por um caminho definido
  com o site.

**Verificar:** com um vídeo inventado, as passagens aparecem na pasta, só com a região.

**Commit:** `feat(borda): gravação das passagens para rotular`

#### T22. Rotulagem no Label Studio

**Objetivo:** rotular rápido, conferindo o pré-rótulo. Quem rotula: o Lorenzo (05/10).

**Arquivos:** o serviço `label-studio` no `infra/docker-compose.yml` (fora do `tarefas up` comum),
o comando `tarefas rotulagem`, `ml/src/ml/rotulagem.py`, testes.

**Regras:**
- O Label Studio (edição comunitária, Apache-2.0) roda no Docker, com os dados em `dados/`.
- A importação leva as gravações e o pré-rótulo do v0. A exportação gera o formato de treino:
  caixas do veículo e da placa (detector), e o texto da placa (OCR).
- Uma placa rotulada guarda quem rotulou e quando (vai para a entidade `Rotulo`, SDD 5.1, no
  mês 3).

**Verificar:** importar e exportar 10 passagens inventadas, ida e volta.

**Commit:** `feat(ml): rotulagem no Label Studio com o pré-rótulo do v0`

#### T23. Régua fixa

**Objetivo:** um conjunto de imagens rotuladas que **nunca** entra no treino (SDD 4.7).

**Depende de:** as primeiras placas reais (`[ABERTO-18]`).

**Arquivos:** `ml/src/ml/regua.py`, `ml/src/ml/avaliar.py`, `docs/validacao/regua.md` (o
manifesto, sem placas), testes.

**Regras (teste primeiro):**
- **Separação:** por dia de gravação (ex.: 1 dia em cada 5 vai para a régua), estável. Rodar de
  novo dá a mesma separação.
- **Garantia:** a exportação de treino recusa qualquer arquivo da régua (o manifesto tem o
  resumo de cada um).
- **Medição:** `avaliar.py` mede um leitor na régua, com o acerto por placa (meta ≥ 97%) e, depois
  da T32, o acerto da composição casando com o agendamento (meta ≥ 95%).

**Verificar:** com rótulos inventados, a separação não muda entre rodadas, e um arquivo da régua
no treino dá erro.

**Commit:** `feat(ml): régua fixa e medição do leitor`

### Semana 2 — leitor v1

#### T24. Detector v1

**Objetivo:** detector de veículo e placa com pesos nossos, e a decisão do `[ABERTO-03]`.

**Depende de:** D2 decidida (D-40), T22, T23 e as primeiras placas (`[ABERTO-18]`).

**Arquivos:** `ml/treino/` (ambiente à parte, D2), `docs/validacao/detector-v1.md` (só números).

**Regras:**
- Treinar o D-FINE-N e o YOLOX-Tiny (código Apache-2.0) com os nossos rótulos, na GPU alugada.
- Exportar em ONNX e medir os dois na régua e no N150 (a T20 do mês 1), em quadros por segundo.
- Fica o que tiver melhor acerto e der pelo menos 5 quadros por segundo por câmera no N150.

**Commit:** `feat(ml): treino do detector v1`

#### T25. OCR v1

**Objetivo:** leitura da placa com pesos nossos.

**Arquivos:** `ml/treino/`, `docs/validacao/ocr-v1.md`.

**Regras:**
- Um modelo no estilo do fast-plate-ocr (código MIT), treinado nos nossos recortes.
- Placa antiga e Mercosul. Exportação em ONNX.
- Medição na régua, por caractere e por placa.

**Commit:** `feat(ml): treino do OCR v1`

#### T26. Leitor v1 na caixa

**Objetivo:** a caixa usa o v1, e a troca não piora a régua.

**Arquivos:** `borda/src/borda/leitor/v1.py`, `ml/src/ml/baixar_modelos.py` (os pesos v1, do
nosso armazenamento), testes.

**Regras:**
- Mesma interface do v0 (`LeitorDePlacas` e `DetectorDeVeiculos`), rodando no OpenVINO
  (Apache-2.0, SDD 4.4), com o ONNX Runtime de reserva.
- A passagem leva `versao_leitor="v1"`.
- O v1 só entra no lugar do v0 se não piorar a régua (SDD 4.7).

**Commit:** `feat(borda): leitor v1 com pesos nossos`

### Semanas 2–3 — agendamento

#### T27. Agendamentos no banco

**Objetivo:** guardar o agendamento, venha de onde vier (SDD 3.4 e 5.1).

**Arquivos:** módulo `nuvem/src/nuvem/agendamento/` (modelos, serviço, conectores), migração,
testes.

**Regras (teste primeiro):**
- Os campos da SDD 5.1, com `origem` e `codigo_externo`.
- A interface de conector: recebe os dados de fora e devolve agendamentos no formato interno.
- O mesmo `codigo_externo` da mesma origem não duplica: atualiza, e a mudança fica registrada.
- As placas esperadas passam pela mesma regra de formato do leitor.
- **Separação por empresa:** chave estrangeira composta, e o teste que tenta ler o agendamento de
  outra empresa e recebe 404.

**Commit:** `feat(agendamento): agendamentos e a interface de conector`

#### T28. Link da transportadora

**Objetivo:** a transportadora agenda pelo celular, sem conta (SDD 6.2).

**Arquivos:** `nuvem/src/nuvem/agendamento/link.py`, telas, testes.

**Regras (teste primeiro):**
- **O link:** código aleatório, revogável, com limite de envios (SDD 8.2); só o resumo do
  código fica no banco.
- **O formulário** é curto, para celular: placas, motorista, celular, janela, toneladas e NF-e
  opcional. Ele valida a placa (formato), o celular (DDD + número) e a janela (dentro do horário
  do site).
- **Erros:** link vencido ou revogado dá 404; passou do limite dá 429.
- Cria o agendamento com `origem=link`.

**Commit:** `feat(agendamento): link da transportadora`

#### T29. Importar planilha

**Objetivo:** o cliente sobe a planilha que já usa.

**Arquivos:** `nuvem/src/nuvem/agendamento/planilha.py`, testes. Dependência nova: `openpyxl`
(MIT), para XLSX.

**Regras (teste primeiro):**
- CSV e XLSX, com um modelo para baixar.
- Relatório de erros por linha (ex.: "linha 7: placa ABC12 não tem 7 caracteres"). As linhas
  certas entram, e as erradas voltam no relatório.
- Reimportar a mesma linha (mesmo `codigo_externo`) não duplica.
- Cria os agendamentos com `origem=planilha`.

**Commit:** `feat(agendamento): importação de planilha com relatório por linha`

#### T30. Tela de agendamentos

**Objetivo:** o gestor vê e alimenta os agendamentos (SDD 6.2).

**Arquivos:** `nuvem/src/nuvem/web/agendamentos.py`, telas, testes.

**Conteúdo:**
- Lista do dia e da semana, por site.
- Importar a planilha.
- Gerar e revogar links.
- Só o gestor vê a tela, e só dos sites dele.

**Commit:** `feat(web): tela de agendamentos`

### Semana 3 — visita e casamento

#### T31. Visita e eventos

**Objetivo:** a chegada vira uma visita, com eventos que não se editam (SDD 5.1, 5.2 e 5.5).

**Arquivos:** módulo `nuvem/src/nuvem/visita/` (ou dentro de `portaria`), migração, testes.

**Regras (teste primeiro):**
- **Entidades:** `Visita`, `Evento` (só se acrescenta: o banco recusa a alteração e a exclusão)
  e `Excecao`.
- **Estados deste mês:** `AGENDADA`, `NA_FILA`, `EXCECAO`, `NAO_VEIO` e `SAIU`. Os outros entram
  no mês 3.
- **Transições:** uma transição fora do diagrama é recusada.
- **Composição:** cada placa da composição confirmada é marcada como lida ou inferida (D-17).

**Commit:** `feat(portaria): visita, eventos e exceções`

#### T32. Casamento

**Objetivo:** a chegada casa com o agendamento (SDD 5.3).

**Arquivos:** `nuvem/src/nuvem/portaria/casamento.py`, testes.

**Regras (teste primeiro), com os pesos iniciais da SDD 5.3 (`[ABERTO-02]`):**
- **Candidatos:** agendamentos do site em `AGENDADA`, com janela no dia (± tolerância).
- **Pontos:**
  - cavalo idêntico: 60;
  - cavalo com uma troca fácil (O/0, I/1, B/8, S/5): 40;
  - cada reboque idêntico: 20, até 2;
  - chegada dentro da janela: 20; dentro da tolerância: 10.
- **Check-in automático:** um candidato com ≥ 80 pontos e 20 à frente do segundo. Senão, exceção,
  com os candidatos.
- **Saída:** a placa do cavalo fecha a visita aberta do mesmo site (`SAIU`).
- **Casos de borda:** dois agendamentos da mesma placa no dia; reboque trocado; placa só da
  traseira (D-23); passagem sem placa.

**Commit:** `feat(portaria): casamento da chegada com o agendamento`

#### T33. Fila de tarefas e worker

**Objetivo:** o casamento e o "não veio" rodam fora do pedido da caixa (D4).

**Arquivos:** `nuvem/src/nuvem/tarefas_de_fundo.py`, o serviço `worker` no compose, migração,
testes.

**Regras (teste primeiro):**
- **O caminho:** a passagem recebida vira uma tarefa "casar". O worker a executa uma vez, e
  dois workers não pegam a mesma tarefa.
- **Falhas:** uma tarefa com erro volta para a fila, esperando mais a cada vez, até um limite.
- **"Não veio":** fim da janela mais a tolerância, sem chegada, leva a visita a `NAO_VEIO`.

**Commit:** `feat(nuvem): fila de tarefas no PostgreSQL e worker`

#### T34. Exceções na tela da portaria (só ver)

**Objetivo:** o porteiro vê as exceções com a foto e os candidatos. Resolver pela tela fica no
mês 3.

**Arquivos:** `nuvem/src/nuvem/web/portaria.py`, telas, testes.

**Commit:** `feat(web): exceções na tela da portaria`

### Semana 4 — de ponta a ponta e o teste técnico

#### T35. Simulador com agendamentos

**Objetivo:** o fluxo agendado → chegada → check-in (ou exceção) → saída roda no simulador.

**Arquivos:** `ferramentas/src/simulador/`, a amostra de agendamentos, testes.

**Regras:** `simulador --agendamentos amostra` cria os agendamentos da demonstração, e a amostra
de passagens tem casos que casam, que viram exceção e que saem.

**Verificar:** `tarefas demo` mostra um check-in automático e uma exceção na tela.

**Commit:** `feat(ferramentas): simulador com agendamentos`

#### ~~T36. Teste técnico (o marco)~~ → próximo plano

Adiada em 05/10: precisa das gravações de um site, com o registro manual das chegadas (N13).

**Objetivo:** decidir o caminho do piloto (seção 1).

**Depende de:** D3 decidida, T23 a T26 e T32.

**Arquivos:** `docs/validacao/teste-tecnico-mes-2.md`, só com números, sem placas.

**Regras:**
- **Leitores:** v1, v0 e o comercial (se D3 permitir), na mesma régua.
- **Medidas:** acerto por placa; acerto da composição casando com o agendamento, com os
  agendamentos do registro manual da portaria (N13); quadros por segundo no N150.
- **Decisão:** pela tabela da seção 1.

**Commit:** `docs: teste técnico do mês 2`

#### ~~T37. Ajuste do casamento~~ → próximo plano

Adiada em 05/10: precisa dos dados do site parceiro.

**Objetivo:** fechar o `[ABERTO-02]`, os pesos e o limite do casamento, com os dados do site
parceiro.

**Arquivos:** `docs/SDD.md` (seção 5.3, o SDD primeiro), `nuvem/src/nuvem/portaria/casamento.py`.

**Commit:** `feat(portaria): pesos do casamento ajustados com os dados do site parceiro`

### Acrescentada em 05/10

#### T38. Conferência da placa pelo porteiro

**Objetivo:** o porteiro compara a leitura com a placa da foto e confirma ou corrige (SDD
D-42). Cada conferência é a placa certa de um recorte: vira rótulo para o treino quando o
contrato do cliente autorizar (SDD 4.6 e 8.3).

**Arquivos:** `nuvem/src/nuvem/portaria/conferencia.py`, o modelo e a migração,
`nuvem/src/nuvem/web/portaria.py`, telas, testes.

**Regras (teste primeiro):**
- Porteiro e gestor conferem o recorte de placa de qualquer passagem do site; a placa digitada
  passa pelo formato da placa (antiga ou Mercosul).
- A conferência é um registro novo, que o banco não deixa alterar nem apagar; conferir de novo
  cria outro, e o último vale.
- A leitura comparada é a placa lida pela mesma câmera do recorte; sem leitura, a placa
  digitada é a correção.
- A passagem de outra empresa, ou de um site que o usuário não vê, responde "não encontrado".
- Não muda a visita nem o casamento: isso vem com a resolução das exceções, no mês 3.
- A conferência abre numa página própria, fora da lista que se atualiza a cada 2 segundos,
  para a atualização não apagar o que o porteiro digita.

**Commit:** `feat(portaria): conferência da placa pelo porteiro`

---

## 5. Trilha não técnica (comercial e burocracia)

| # | Tarefa | Por quê | Resolve |
|---|---|---|---|
| ~~N9~~ | ~~**Instalar o kit no site parceiro**, com as câmeras posicionadas pelo guia (N8), a placa de aviso de gravação e o termo com o site~~ (adiada em 05/10, seção 2) | sem ele não há dados para treinar | T21 |
| N10 | ~~**Definir quem rotula**~~ resolvida em 05/10: o Lorenzo | 3 a 5 mil placas | T22 |
| N11 | **Abrir as contas:** GPU por hora para o treino (quando houver as primeiras placas) e, se D3 permitir, Plate Recognizer | o treino e o teste técnico | T24, T36 |
| N12 | **Montar a oferta de piloto anual pré-pago** e levá-la às conversas | o comercial do mês 2 (SDD 10) | `[ABERTO-06]` |
| ~~N13~~ | ~~**Combinar com o site parceiro o registro manual** das chegadas durante a gravação (hora, placas, agendamento)~~ (adiada em 05/10) | é o gabarito da composição e do casamento | T36, T37 |
| N14 | **Fechar o que ficou da trilha do mês 1** (N1 a N8) | Meta, AWS e advogado têm prazo longo | `[ABERTO-01]`, `[ABERTO-04]`, `[ABERTO-07]` |
| N15 | **Levar ao advogado** (acrescentada em 05/10): gravar em portões de conhecidos, fotografar placas na rua, o leitor comercial na nuvem (D-41) e a cláusula do treino no contrato (SDD 8.3) | a coleta própria e o uso das conferências no treino dependem do sim | `[ABERTO-18]`, `[ABERTO-07]` |

---

## 6. Ajustes no SDD feitos junto com este plano

- Novos itens em aberto, para decidir antes das tarefas que travam (seção 2):
  - `[ABERTO-15]`: gravar sem guardar rostos;
  - `[ABERTO-16]`: ambiente de treino;
  - `[ABERTO-17]`: leitor comercial no teste técnico.
- Em 05/10 (SDD 0.28): os três fechados pela recomendação (D-39 a D-41), a D-38 confirmada, a
  conferência da placa pelo porteiro (D-42) e o novo `[ABERTO-18]` (as primeiras placas).

---

## 7. Checklist de "mês 2 pronto"

- [x] D1 a D4 decididas e registradas no SDD.
- [ ] ~~Gravações do site parceiro em `dados/`, sem rostos,~~ e 3 a 5 mil placas rotuladas
      (da fonte que o `[ABERTO-18]` escolher).
- [ ] Régua fixa separada, com o manifesto no repositório e a garantia de que não entra no
      treino.
- [ ] Detector e OCR v1 treinados, com pesos nossos; o v1 na caixa; `[ABERTO-03]` decidido.
- [ ] Medição no N150 registrada (a T20 do mês 1).
- [x] Agendamento por link e por planilha, com a tela do gestor.
- [x] Casamento com check-in automático, exceção e saída, com o worker.
- [ ] Conferência da placa pelo porteiro (T38).
- [ ] ~~**Marco:** teste técnico feito e o caminho do piloto decidido.~~ → próximo plano
- [ ] ~~`[ABERTO-02]` fechado com os dados do site parceiro.~~ → próximo plano
- [ ] Trilha não técnica: ~~kit instalado no site parceiro;~~ oferta de piloto nas conversas.

---
tipo: "pacote"
fonte: "nuvem/src/nuvem/portaria/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/portaria/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.portaria

Pasta `nuvem/src/nuvem/portaria/`.

Portaria ([[3.3 Módulos da nuvem no MVP|SDD 3.3]]): recebe as passagens da borda; no mês 2, casa com o agendamento.

## Módulos

### `nuvem.portaria.casamento`

`nuvem/src/nuvem/portaria/casamento.py`

Casamento da chegada com o agendamento, e a saída ([[5.3 Casamento da chegada com o agendamento|SDD 5.3]], [[D-17]], [[D-23]], [[D-36]] e [[D-37]]).

As regras puras (``pontuar``, ``decidir``, ``compor``, ``escolher_saida``) não usam o banco.
``processar_passagem`` junta tudo: lê a passagem, procura os candidatos, decide e grava a visita
(check-in ou exceção) ou fecha a visita na saída.

Os pesos são os iniciais da [[5.3 Casamento da chegada com o agendamento|SDD 5.3]] (``PESOS_INICIAIS``); os definitivos saem dos dados do site
parceiro ([[ABERTO-02]], [[T37]]). A tolerância padrão é a de [[ABERTO-09]] (4h).

- **`Pesos`** (classe): Os pontos de cada critério e o limite do check-in automático ([[5.3 Casamento da chegada com o agendamento|SDD 5.3]]).
- **`PESOS_INICIAIS`** = `Pesos()`: Os pesos iniciais da [[5.3 Casamento da chegada com o agendamento|SDD 5.3]], até o [[ABERTO-02]] ser fechado com os dados do mês 2.
- **`TOLERANCIA_PADRAO`** = `timedelta(hours=4)`: A tolerância da janela, para antes e para depois (padrão do [[ABERTO-09]]).
- **`CANDIDATOS_NA_EXCECAO`** = `5`: Quantos candidatos a exceção mostra ao porteiro, do maior para o menor.
- **`TROCAS_FACEIS`**: Os pares que o leitor confunde ([[5.3 Casamento da chegada com o agendamento|SDD 5.3]]).
- **`forma_mercosul`**: A placa na forma Mercosul (a antiga ``ABC1234`` vira ``ABC1C34``; a Mercosul fica igual).
- **`mesma_placa`**: Diz se as duas placas são a do mesmo veículo (a antiga e a Mercosul contam juntas).
- **`troca_facil`**: Diz se as placas diferem num caractere só, e esse é uma troca fácil (O/0, I/1, B/8, S/5).
- **`Esperado`** (classe): O que o casamento usa de um agendamento.
- **`Pontuado`** (classe): Um candidato com os pontos (e quantos deles vieram das placas).
- **`CheckIn`** (classe): O candidato que casou, e o segundo colocado (se houve).
- **`ParaExcecao`** (classe): A chegada não casou com segurança: o porteiro resolve.
- **`pontuar`**: Os pontos de um agendamento para uma chegada ([[5.3 Casamento da chegada com o agendamento|SDD 5.3]]).
- **`decidir`**: Check-in automático ou exceção, com o motivo e os candidatos ([[5.3 Casamento da chegada com o agendamento|SDD 5.3]]).
- **`compor`**: A composição confirmada no check-in: cada placa, lida ou inferida ([[D-17]]).
- **`lidas_na_visita`**: As placas da passagem como vieram (a composição da exceção), sem repetir nem dois cavalos.
- **`Aberta`** = `tuple[int, Sequence[str], datetime]`: Uma visita aberta: o id, as placas da composição e a hora da chegada.
- **`escolher_saida`**: A visita que a saída fecha: a de chegada mais recente com uma placa lida ([[D-37]]).
- **`Processada`** (classe): O que a passagem fez: o resultado e a visita (se houve).
- **`processar_passagem`**: Casa a passagem de entrada (check-in ou exceção), ou fecha a visita na saída.
- **`agendamentos_sem_visita`**: Os candidatos: agendamentos ativos perto da chegada que ainda não têm visita ([[D-35]]).
- **`esperado_de`**: O que o casamento usa de um agendamento.

### `nuvem.portaria.conferencia`

`nuvem/src/nuvem/portaria/conferencia.py`

Conferência da placa pelo porteiro (SDD [[D-42]]).

A tela mostra cada recorte de placa de uma passagem ao lado do que o leitor leu pela mesma
câmera, e o porteiro confirma ou digita a placa certa. A conferência é um registro novo, que o
banco não deixa alterar nem apagar; conferir de novo cria outro, e o último vale. Ela não muda
a visita nem o casamento: o "corrigir" da fila de exceções vem no mês 3.

Cada conferência é a placa certa de um recorte: vira rótulo para o treino quando o contrato do
cliente autorizar ([[4.6 Dados de treino|SDD 4.6]] e [[8.3 LGPD|8.3]]).

- **`Recorte`** (classe): Um recorte de placa de uma passagem, com a leitura e a última conferência.
- **`recortes`**: Os recortes de placa de uma passagem que o usuário vê, na ordem das fotos.
- **`conferir`**: Grava a placa certa de um recorte, conferida por quem pede (sem ``commit``).
- **`ultimas_por_passagem`**: A última conferência de cada recorte, por passagem (na ordem das fotos).

### `nuvem.portaria.modelos`

`nuvem/src/nuvem/portaria/modelos.py`

Tabelas da portaria ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]], [[5.1 Entidades|5.1]] e [[5.2 Estados da visita|5.2]]): passagens, visitas, eventos, exceções e conferências.

A passagem é prova da chegada ([[5.5 Garantias|SDD 5.5]]): fica guardada exatamente como veio (``como_veio``),
e não se edita. As colunas ao lado repetem o que as consultas usam (site, faixa, horários).

A visita nasce na chegada ([[D-35]]). O evento e a conferência da placa só se acrescentam: um gatilho
no banco recusa alterar ou apagar (migrações 0008 e 0011).

- **`PassagemRecebida`** (classe): Uma passagem que uma caixa de borda mandou.
- **`EstadoDaVisita`**: Os estados da visita ([[5.2 Estados da visita|SDD 5.2]]).
- **`TipoDeEvento`**: O que aconteceu com a visita; cada tipo leva a um estado (``visitas.TRANSICOES``).
- **`MotivoDaExcecao`**: Por que a chegada não casou ([[5.3 Casamento da chegada com o agendamento|SDD 5.3]]).
- **`Visita`** (classe): A estadia de um caminhão no site, da chegada à saída (ou o "não veio").
- **`Evento`** (classe): Algo que aconteceu com uma visita. Só se acrescenta ([[5.5 Garantias|SDD 5.5]]).
- **`Excecao`** (classe): Uma chegada que o sistema não casou com segurança: o porteiro resolve ([[5.2 Estados da visita|SDD 5.2]]).
- **`ConferenciaPlaca`** (classe): A placa certa de um recorte, segundo quem conferiu ([[D-42]]). Só se acrescenta ([[5.5 Garantias|SDD 5.5]]).

### `nuvem.portaria.resolucao`

`nuvem/src/nuvem/portaria/resolucao.py`

O porteiro resolve a exceção, corrige a placa e registra a chegada à mão ([[5.2 Estados da visita|SDD 5.2]] e [[D-46]]).

- **Resolver a exceção:** "é este" liga a visita a um agendamento perto da chegada e ainda sem
  visita; "sem agendamento" aceita; "recusar" leva a ``RECUSADA``. Cada um é um evento, com quem
  fez, e a exceção fica resolvida por essa pessoa.
- **Corrigir a placa numa exceção casa de novo:** a placa conferida na foto ([[D-42]]) ou digitada
  entra no lugar da que o leitor leu, e o casamento roda com ela. Casou com segurança, a visita vai
  para a fila; senão, a exceção fica com o motivo e os candidatos novos.
- **Chegada manual** (a câmera falhou): o porteiro digita as placas e escolhe o agendamento entre
  as sugestões, ou nenhum. Não abre exceção: quem escolhe é ele, na hora.

Quem chama é a tela da portaria (porteiro ou gestor). As funções gravam com ``flush``; o
``commit`` é de quem chama.

- **`ExcecaoJaResolvidaError`** (classe): A exceção já foi resolvida (por outra pessoa, ou pelo sistema quando o caminhão saiu).
- **`AgendamentoIndisponivelError`** (classe): O agendamento não serve: já tem visita, foi cancelado, é de outro site ou está longe.
- **`Opcao`** (classe): Um agendamento que o porteiro pode escolher, com os pontos para as placas da chegada.
- **`obter_excecao`**: Uma exceção (aberta ou não) de um site que o usuário vê, com a visita dela.
- **`opcoes`**: Os agendamentos perto da chegada e sem visita, dos mais pontos para os menos.
- **`ligar_ao_agendamento`**: "É este": liga a visita ao agendamento e a leva para a fila.
- **`aceitar_sem_agendamento`**: Aceita a chegada sem agendamento: a visita vai para a fila.
- **`recusar`**: Recusa a entrada: a visita vai para ``RECUSADA``.
- **`conferir_placa`**: Confere a placa de um recorte ([[D-42]]); numa exceção aberta, casa de novo com a placa certa.
- **`digitar_cavalo`**: A placa do cavalo digitada (quando não há foto para conferir); casa de novo.
- **`sugestoes`**: Os agendamentos perto de agora e sem visita, pelos pontos das placas digitadas.
- **`registrar_chegada_manual`**: Abre a visita de uma chegada que a câmera não registrou, com as placas digitadas.

### `nuvem.portaria.rotas`

`nuvem/src/nuvem/portaria/rotas.py`

Rotas da borda para passagens e fotos ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]], [[D-22]]).

As respostas são as que a fila da caixa precisa entender: 201 (nova), 200 (já tinha chegado),
401 (chave), 403 (outro site), 409 (id de outra caixa) e 422 (campo que não confere).

- **`PassagemAceita`** (classe): A resposta a uma passagem aceita (nova ou repetida).
- **`PedidoDeEndereco`** (classe): O ``ref`` da foto que a caixa vai enviar (o mesmo que irá na passagem).
- **`EnderecoDeEnvio`** (classe): Para onde enviar a foto (com ``PUT``), até quando.
- **`receber_passagem`**: Recebe uma passagem da caixa: 201 se nova, 200 se repetida.
- **`endereco_de_foto`**: Devolve o endereço temporário para a caixa enviar uma foto.
- **`receber_foto`**: Recebe a foto no armazenamento local (o endereço já autoriza; não leva a chave).

### `nuvem.portaria.servico`

`nuvem/src/nuvem/portaria/servico.py`

Regras da portaria: receber as passagens da borda e mostrá-las ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]] e [[5.5 Garantias|5.5]]).

- Reenvio seguro: o mesmo ``id`` de novo, da mesma caixa, não cria outra passagem.
- A caixa só manda passagens do site dela, com faixas e câmeras desse site.
- A passagem fica guardada como veio; nada aqui a altera depois.
- Quem lê (a tela da portaria) passa o ``Acesso``: só vê os sites dele, da empresa dele.
- A passagem nova vira a tarefa "casar", que o worker executa (``tarefas_de_fundo``).

As funções gravam com ``flush``; o ``commit`` é de quem chama.

- **`LIMITE_DA_TELA`** = `50`: Quantas passagens a tela da portaria mostra (as últimas).
- **`Local`** = `tuple[str | int, ...]`: Onde está o campo recusado dentro da passagem (ex.: ``("placas", 0, "camera_id")``).
- **`PassagemDeOutroSiteError`** (classe): A passagem diz ser de outro site ou de outra caixa que não a dona da chave.
- **`IdDeOutraCaixaError`** (classe): O ``id`` da passagem já foi usado por outra caixa.
- **`PassagemInvalidaError`** (classe): Um campo da passagem não confere com o cadastro do site (``loc`` diz qual).
- **`receber_passagem`**: Guarda uma passagem mandada pela caixa.
- **`ultimas_passagens`**: As últimas passagens de um site que o usuário vê, das mais novas para as mais antigas.
- **`resultados`**: O que o casamento fez com cada passagem, em poucas palavras, para a tela da portaria.
- **`obter_passagem`**: Uma passagem de um site que o usuário vê.
- **`foto_da_passagem`**: A foto número ``indice`` de uma passagem que o usuário vê.

### `nuvem.portaria.visitas`

`nuvem/src/nuvem/portaria/visitas.py`

Regras da visita ([[5.1 Entidades|SDD 5.1]], [[5.2 Estados da visita|5.2]], [[5.5 Garantias|5.5]] e [[D-35]]): a chegada vira visita, com eventos que ficam.

- **A visita nasce na chegada:** casou, ``NA_FILA``; não casou, ``EXCECAO`` (com a ``Excecao``);
  no prazo do "não veio", ``NAO_VEIO``. Antes disso, o agendamento ativo sem visita é o
  ``AGENDADA`` do diagrama.
- **Cada evento leva a um estado** (``ABRE`` e ``TRANSICOES``); um evento fora do diagrama é
  recusado (``TransicaoInvalidaError``) e nada muda.
- **O evento só se acrescenta:** o banco recusa alterar ou apagar.
- **A composição** diz, de cada placa, se foi lida pela câmera ou inferida do agendamento ([[D-17]]).
- **Quem grava** é a nuvem, a partir da passagem (o casamento) ou do porteiro (a resolução da
  exceção e a chegada manual, em ``resolucao``): ``SiteDaVisita`` diz onde. **Quem lê** passa o
  ``Acesso``.

As funções gravam com ``flush``; o ``commit`` é de quem chama.

- **`ABRE`**: Os eventos que abrem uma visita, e o estado em que ela nasce (a chegada manual abre com ``check_in`` ou ``aceita_sem_agendamento``, [[D-46]]).
- **`TRANSICOES`**: De um estado, cada evento permitido e o estado seguinte.
- **`ABERTOS`**: Os estados de quem ainda está no site (a saída fecha a visita aberta da placa).
- **`TransicaoInvalidaError`** (classe): O evento não cabe no estado atual da visita ([[5.2 Estados da visita|SDD 5.2]]).
- **`PlacaNaVisita`** (classe): Uma placa da composição confirmada: o papel e se foi lida ou inferida ([[D-17]]).
- **`Candidato`** (classe): Um agendamento que chegou perto no casamento, com os pontos ([[5.3 Casamento da chegada com o agendamento|SDD 5.3]]).
- **`SiteDaVisita`** (classe): O site da visita; quem grava já sabe qual é (pela passagem da caixa ou pelo agendamento).
- **`abrir_visita`**: Abre uma visita com o primeiro evento (check-in, exceção ou "não veio").
- **`abrir_excecao`**: Abre a visita de uma chegada que não casou, com a exceção para o porteiro resolver.
- **`registrar`**: Registra um evento numa visita aberta e a leva ao estado seguinte.
- **`mudar_composicao`**: Troca as placas da visita (ex.: o porteiro corrigiu a placa numa exceção).
- **`composicao_da_visita`**: As placas da visita, como ``PlacaNaVisita``.
- **`VisitaInventada`** (classe): Uma visita inventada para a demonstração ([[D-49]]), até onde ela chegou: só chegou, foi chamada, está na doca, foi liberada ou saiu.
- **`gravar_inventadas`**: Grava de uma vez as visitas inventadas da demonstração, com os eventos de cada etapa (o check-in do sistema ou do porteiro; a chamada, o início e o fim pelo líder; a saída pelo sistema). Só para a demonstração.
- **`abertas_do_site`**: As visitas ainda abertas de um site (quem ainda está nele), da chegada mais antiga.
- **`obter_visita`**: Uma visita de um site que o usuário vê.
- **`eventos_da_visita`**: Os eventos de uma visita que o usuário vê, na ordem em que foram registrados.
- **`eventos_recentes`**: Os eventos destes tipos registrados desde ``desde``, de todos os sites, com a visita, na ordem em que foram registrados; só os das visitas com agendamento.
- **`para_o_extrato`**: As visitas de um site que chegaram em ``[de, ate)`` ou usaram uma doca nele, cada uma com se o check-in foi automático (feito pelo sistema, sem pessoa; [[D-46]]). O "não veio" fica fora.
- **`excecoes_abertas`**: As exceções abertas de um site, da chegada mais antiga para a mais nova.

## Testes

- `nuvem/tests/test_nuvem_portaria_casamento.py`: As regras puras do casamento ([[5.3 Casamento da chegada com o agendamento|SDD 5.3]], [[D-17]], [[D-23]], [[D-36]] e [[D-37]]), sem banco.
- `nuvem/tests/test_nuvem_portaria_casar.py`: O casamento no banco ([[5.3 Casamento da chegada com o agendamento|SDD 5.3]]): a passagem que chega vira check-in ou exceção; a saída fecha.
- `nuvem/tests/test_nuvem_portaria_conferencia.py`: Conferência da placa pelo porteiro (SDD [[D-42]]): a placa certa de cada recorte, com prova.
- `nuvem/tests/test_nuvem_portaria_passagens.py`: Recebimento de passagens ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]] e [[5.5 Garantias|5.5]]): reenvio seguro, só do site da caixa, como veio.
- `nuvem/tests/test_nuvem_portaria_resolucao.py`: O porteiro resolve a exceção, corrige a placa e registra a chegada à mão ([[T41]], [[D-46]]).
- `nuvem/tests/test_nuvem_portaria_rotas.py`: Rotas da borda para passagens e fotos: respostas que a fila da caixa entende.
- `nuvem/tests/test_nuvem_portaria_visitas.py`: Visita, eventos e exceções ([[5.1 Entidades|SDD 5.1]], [[5.2 Estados da visita|5.2]], [[5.5 Garantias|5.5]] e [[D-35]]): a chegada vira visita, com prova.

---

Do [[Mapa do código]].

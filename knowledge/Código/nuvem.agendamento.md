---
tipo: "pacote"
fonte: "nuvem/src/nuvem/agendamento/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/agendamento/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.agendamento

Pasta `nuvem/src/nuvem/agendamento/`.

Agendamento ([[3.3 Módulos da nuvem no MVP|SDD 3.3]] e [[3.4 Conectores de agendamento|3.4]]): os agendamentos de cada site e os conectores que os trazem.

## Módulos

### `nuvem.agendamento.conectores`

`nuvem/src/nuvem/agendamento/conectores.py`

A interface dos conectores de agendamento ([[3.4 Conectores de agendamento|SDD 3.4]]).

Cada origem (o link da transportadora, a planilha do cliente, a API genérica e, depois, os ERPs)
é um conector: recebe os dados de fora e devolve, item a item, o agendamento no formato interno
(``Lido``) ou o motivo da recusa (``Recusado``), sempre dizendo onde estava o item (ex.:
``"linha 7"``). Quem grava é o serviço (``servico.importar``), igual para todos.

- **`Lido`** (classe): Um agendamento que o conector entendeu, já no formato interno.
- **`Recusado`** (classe): Um item que não entrou, com o motivo em português.
- **`Conector`** (classe): O que todo conector faz: transformar a entrada de fora em agendamentos.
- **`ler_dados`**: Confere os campos de um item contra o formato interno.

### `nuvem.agendamento.formato`

`nuvem/src/nuvem/agendamento/formato.py`

O formato interno do agendamento ([[3.4 Conectores de agendamento|SDD 3.4]]): o que todo conector entrega, já conferido.

A placa segue a mesma regra do leitor (``contratos.placa``); o celular é do Brasil e fica com o
+55; a chave da NF-e tem 44 caracteres e o dígito verificador confere. Texto vazio conta como
ausente: a célula vazia da planilha não é um celular inválido, é celular nenhum.

Os erros saem em português (``descrever_erros``), para o relatório da planilha e o formulário do
link.

- **`MAXIMO_DE_REBOQUES`** = `3`: Até o tritrem; o casamento conta no máximo 2 ([[5.3 Casamento da chegada com o agendamento|SDD 5.3]]), mas guarda o que vier.
- **`DDDS`**: Os 67 DDDs do Brasil.
- **`FORMATO_DO_CELULAR`** = `'^\\+55[1-9]{2}9[0-9]{8}$'`: Como o celular fica guardado: +55, o DDD e os 9 números (o primeiro é sempre 9).
- **`CelularInvalidoError`** (classe): O texto não é um celular do Brasil.
- **`normalizar_celular`**: Devolve o celular como fica guardado (ex.: ``+5511987654321``).
- **`FORMATO_DA_CHAVE_NFE`** = `'^[0-9]{6}[A-Z0-9]{12}[0-9]{26}$'`: 44 caracteres; as 12 primeiras posições do CNPJ podem ter letras (CNPJ alfanumérico).
- **`ChaveNfeInvalidaError`** (classe): O texto não é uma chave de NF-e (formato ou dígito verificador).
- **`normalizar_chave_nfe`**: Devolve a chave da NF-e sem espaços, em maiúsculas, com o dígito verificador conferido.
- **`DadosDoAgendamento`** (classe): Um agendamento no formato interno, como todo conector entrega ([[3.4 Conectores de agendamento|SDD 3.4]]).
- **`ROTULOS`**: Como cada campo aparece para a pessoa.
- **`descrever_erros`**: Os erros de ``DadosDoAgendamento`` em português, um por campo (ex.: ``"tipo: ..."``).

### `nuvem.agendamento.link`

`nuvem/src/nuvem/agendamento/link.py`

Link da transportadora ([[3.4 Conectores de agendamento|SDD 3.4]], [[6.2 Telas do MVP|6.2]], [[8.2 Segurança|8.2]] e [[D-34]]): agendar pelo celular, sem conta.

- **O link:** o gestor gera; o código é aleatório e longo, vai no endereço e aparece uma vez só,
  para quem gerou. O banco guarda só o resumo. O link vence, pode ser revogado e tem um limite de
  agendamentos.
- **Vencido, revogado ou inventado** dá ``NaoEncontradoError`` (404, sem dizer qual); **no
  limite**, ``LinkEsgotadoError`` (429).
- **O formulário** pede tudo (placas, motorista, celular, janela, tipo, toneladas; a NF-e é
  opcional). A janela é escolhida no fuso do site, num dia só, dentro do horário de operação,
  começando no futuro e no máximo 60 dias à frente.
- **Cada envio** é um agendamento novo, com o código externo ``<link>-<número do envio>``. O envio
  recusado não gasta o limite.

As funções gravam com ``flush``; o ``commit`` é de quem chama.

- **`ANTECEDENCIA_MAXIMA`** = `timedelta(days=60)`: Até quantos dias à frente a transportadora marca pelo link.
- **`LinkEsgotadoError`** (classe): O link chegou ao limite de agendamentos: a API responde 429.
- **`LinkGerado`** (classe): O link novo e o código dele (que só aparece agora, para o gestor mandar).
- **`LinkAberto`** (classe): O que o formulário mostra: para quem é o link e o site onde se agenda.
- **`FormularioDoLink`** (classe): Os campos do formulário, como o navegador manda (texto; vazio = não preenchido).
- **`gerar_link`**: Gera um link de agendamento para uma transportadora, num site do gestor.
- **`revogar_link`**: Revoga um link: deixa de valer na hora. Revogar de novo não muda nada.
- **`listar_links`**: Os links de um site, do mais novo ao mais velho.
- **`situacao_do_link`**: Como o link está agora, para a tela do gestor (o primeiro motivo que o impede de valer).
- **`abrir_link`**: O que o formulário do link mostra.
- **`agendar_pelo_link`**: Cria o agendamento que a transportadora mandou pelo link.
- **`agendamento_do_link`**: Um agendamento feito por este link (a confirmação que a transportadora vê).
- **`horario_do_link`**: O site do link (para mostrar a confirmação no fuso dele), mesmo com o link no limite.
- **`ConectorDoLink`** (classe): O conector do link ([[3.4 Conectores de agendamento|SDD 3.4]]): o formulário vira um agendamento no formato interno.

### `nuvem.agendamento.modelos`

`nuvem/src/nuvem/agendamento/modelos.py`

Tabelas do agendamento ([[5.1 Entidades|SDD 5.1]]): os agendamentos de cada site e as mudanças de cada um.

O agendamento aponta para o site pela dupla (site, empresa), e a mudança aponta para o
agendamento do mesmo jeito ([[5.5 Garantias|SDD 5.5]]). A situação é só ativo ou cancelado: o andamento da
chegada é da visita ([[D-32]]).

- **`Origem`**: Os conectores do MVP ([[3.4 Conectores de agendamento|SDD 3.4]]); cada conector novo entra aqui.
- **`Via`**: Por onde veio a mudança: por um conector ou pelo painel (ex.: o gestor cancelou).
- **`Agendamento`** (classe): Um caminhão esperado no site, numa janela de horário.
- **`MudancaAgendamento`** (classe): Uma mudança num agendamento: a criação, cada alteração e o cancelamento.
- **`LinkTransportadora`** (classe): Um link de agendamento que o gestor manda a uma transportadora ([[8.2 Segurança|SDD 8.2]] e [[D-34]]).

### `nuvem.agendamento.planilha`

`nuvem/src/nuvem/agendamento/planilha.py`

Importação de planilha ([[3.4 Conectores de agendamento|SDD 3.4]]): o gestor sobe a agenda em CSV ou XLSX.

- **Colunas** do modelo, em qualquer ordem, sem ligar para maiúsculas e acentos; colunas a mais
  são ignoradas, e alguns nomes comuns valem pelo do modelo ("data" por "dia").
- **Valores:** dia em ``dd/mm/aaaa`` (ou a data do próprio XLSX) e horas em ``hh:mm``, no fuso
  do site. A planilha não confere o horário de operação nem se a janela passou: é o dado do
  próprio cliente, corrigido e reimportado ao longo do dia.
- **Arquivo:** CSV em UTF-8 ou Windows-1252 (o Excel no Brasil), separado por ``;``, ``,`` ou
  tabulação; ou a primeira aba do XLSX. Até 5 MB e 5.000 linhas. O XLSX é lido com o defusedxml
  (contra XML feito para atacar o leitor) e só se o conteúdo descompactado couber em 20 MB.
- **Relatório por linha:** cada linha certa vira ``Lido``; cada errada, ``Recusado`` com o número
  da linha. Problema no arquivo inteiro levanta ``PlanilhaInvalidaError`` antes de gravar nada.

- **`MAXIMO_DESCOMPACTADO`** = `20 * 1024 * 1024`: O XLSX é um zip: um arquivo pequeno pode esconder um conteúdo enorme.
- **`Coluna`** (classe): Uma coluna do modelo: o nome que aparece e os nomes que valem por ele.
- **`COLUNAS`**: As colunas do modelo, na ordem em que ele as traz.
- **`EXEMPLO`**: Uma linha inventada, na aba de exemplo do modelo XLSX.
- **`PlanilhaInvalidaError`** (classe): O arquivo inteiro não serve (formato, tamanho, colunas): nada é gravado.
- **`Planilha`** (classe): O arquivo que o gestor subiu.
- **`ConectorDaPlanilha`** (classe): O conector da planilha ([[3.4 Conectores de agendamento|SDD 3.4]]): cada linha vira um agendamento no formato interno.
- **`importar_planilha`**: Importa a planilha num site do gestor e devolve o relatório por linha.
- **`modelo_csv`**: O modelo em CSV, só com o cabeçalho, como o Excel no Brasil abre (``;`` e BOM).
- **`modelo_xlsx`**: O modelo em XLSX: a aba da agenda, só com o cabeçalho, e uma aba com um exemplo.

### `nuvem.agendamento.rotas`

`nuvem/src/nuvem/agendamento/rotas.py`

Rotas dos agendamentos: ler (qualquer usuário do cliente) e subir a planilha (o gestor).

Sem login, 401; a administração, 403 (ela tem rotas próprias, [[D-19]]); o papel errado, 403; o que
é de outra empresa ou de um site que o usuário não vê, 404. Planilha que não serve, 422.

- **`MAIOR_PERIODO`** = `timedelta(days=31)`: O maior período que a lista aceita de uma vez.
- **`AgendamentoPublico`** (classe): Um agendamento como a API o mostra.
- **`RelatorioPublico`** (classe): O resultado da importação, como a API o mostra.
- **`subir_planilha`**: Importa a planilha (CSV ou XLSX) num site do gestor; devolve o relatório por linha.
- **`listar`**: Os agendamentos de um site cuja janela toca o período ``[de, ate)`` (até 31 dias).
- **`obter`**: Um agendamento de um site que o usuário vê (404 para qualquer outro).

### `nuvem.agendamento.servico`

`nuvem/src/nuvem/agendamento/servico.py`

Regras do agendamento ([[3.4 Conectores de agendamento|SDD 3.4]], [[5.1 Entidades|5.1]] e [[5.5 Garantias|5.5]]).

- **Quem grava** é um conector, para um site: ``SiteDoAgendamento`` diz qual (e quem, se for uma
  pessoa do cliente). Para o usuário do cliente, ele nasce de ``site_para_agendar``, que confere
  o ``Acesso``; o link da transportadora tem o seu.
- **Reenvio atualiza** ([[D-33]]): o mesmo código externo, pela mesma origem, no mesmo site, muda o
  agendamento que já existe; reenviar igual não muda nada.
- **Cada mudança fica registrada** (``MudancaAgendamento``), inclusive a criação e o
  cancelamento. Trocar o celular apaga a autorização de WhatsApp, que é do número.
- **Cancelado não volta** pelo reenvio: o conector recebe a recusa.
- **Quem lê** passa o ``Acesso``: só vê os sites dele, da empresa dele; o resto "não existe".

As funções gravam com ``flush``; o ``commit`` é de quem chama.

- **`CAMPOS`**: Os campos que um reenvio pode mudar (o código externo é o que identifica o agendamento).
- **`SiteDoAgendamento`** (classe): O site onde o conector grava, e quem está gravando: uma pessoa do cliente ou um link.
- **`Gravado`** (classe): O agendamento depois de gravado, e o que aconteceu com ele.
- **`Relatorio`** (classe): O resultado de uma importação: quantos entraram, mudaram ou já estavam iguais, e as recusas, cada uma com o lugar e o motivo.
- **`AgendamentoCanceladoError`** (classe): O reenvio é de um agendamento que foi cancelado no painel: ele não volta assim.
- **`site_para_agendar`**: O site onde o usuário vai gravar agendamentos (ex.: a planilha que o gestor sobe).
- **`gravar`**: Cria o agendamento ou, se o código externo já existe nesta origem e site, atualiza.
- **`AgendamentoInventado`** (classe): Um agendamento inventado para a demonstração ([[D-49]]): sem motorista, com o celular de um DDD que não existe (por isso não passa pelo ``DadosDoAgendamento``, que recusa o DDD).
- **`gravar_inventados`**: Grava de uma vez os agendamentos inventados da demonstração, cada um com a mudança "criado" (pela planilha, um dia antes da janela). Só para a demonstração.
- **`importar`**: Grava cada agendamento que o conector entendeu e junta as recusas no relatório.
- **`cancelar`**: Cancela um agendamento pelo painel; cancelar de novo não muda nada.
- **`obter`**: Um agendamento de um site que o usuário vê.
- **`obter_por_codigo`**: O agendamento de um conector, pelo código externo, no site dele.
- **`ativos_perto`**: Os agendamentos ativos de um site cuja janela, alargada pela folga, contém o momento.
- **`ativos_que_terminaram`**: Os agendamentos ativos, de todos os sites, cuja janela terminou em ``[de, ate)``.
- **`para_confirmar`**: Os agendamentos ativos com celular, de todos os sites, criados ou mudados desde ``mudados_desde`` e cuja janela ainda não terminou.
- **`empresa_do_agendamento`**: A empresa de um agendamento de qualquer site, ou ``None`` se ele não existe.
- **`com_celular`**: Os agendamentos com celular entre estes, de todos os sites, por id.
- **`listar`**: Os agendamentos de um site cuja janela toca o período ``[de, ate)``, pelo início.
- **`dias_com_agendamento`**: Os dias, no fuso do site, em que começa algum agendamento do site em ``[de, ate)``.
- **`codigos_externos`**: O código externo de cada agendamento (dos sites que o usuário vê), por id.
- **`Resumo`** (classe): O que as telas mostram de um agendamento ao lado de uma visita.
- **`resumos`**: O código, o tipo e as toneladas de cada agendamento (dos sites que o usuário vê), por id.
- **`mudancas`**: O histórico de um agendamento que o usuário vê, da criação até agora.

## Testes

- `nuvem/tests/test_nuvem_agendamento_formato.py`: O formato interno do agendamento ([[3.4 Conectores de agendamento|SDD 3.4]]): o que todo conector entrega, já conferido.
- `nuvem/tests/test_nuvem_agendamento_importar.py`: Importar a planilha no banco e pela API ([[3.4 Conectores de agendamento|SDD 3.4]]): só o gestor, só nos sites dele.
- `nuvem/tests/test_nuvem_agendamento_link.py`: Link da transportadora ([[3.4 Conectores de agendamento|SDD 3.4]], [[8.2 Segurança|8.2]] e [[D-34]]): gerar, abrir, agendar, vencer, revogar, limitar.
- `nuvem/tests/test_nuvem_agendamento_planilha.py`: Importação de planilha ([[3.4 Conectores de agendamento|SDD 3.4]]): CSV e XLSX, o modelo, e o relatório por linha.
- `nuvem/tests/test_nuvem_agendamento_rotas.py`: Rotas de leitura dos agendamentos: só dentro da empresa, só nos sites de quem pede.
- `nuvem/tests/test_nuvem_agendamento_servico.py`: Regras do agendamento no banco ([[3.4 Conectores de agendamento|SDD 3.4]], [[5.1 Entidades|5.1]] e [[5.5 Garantias|5.5]]): gravar, reenviar, cancelar e separar.

---

Do [[Mapa do código]].

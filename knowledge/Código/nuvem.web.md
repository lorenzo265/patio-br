---
tipo: "pacote"
fonte: "nuvem/src/nuvem/web/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/web/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.web

Pasta `nuvem/src/nuvem/web/`.

Telas do painel ([[6.2 Telas do MVP|SDD 6.2]]): páginas feitas no servidor, com Jinja.

## Módulos

### `nuvem.web.agendamentos`

`nuvem/src/nuvem/web/agendamentos.py`

Tela de agendamentos ([[6.2 Telas do MVP|SDD 6.2]]): o gestor vê e alimenta os agendamentos dos sites dele.

- A lista do dia (ou da semana), no fuso do site, com o cancelamento.
- Importar a planilha, com o relatório por linha, e baixar os modelos.
- Gerar e revogar os links das transportadoras. O endereço de um link novo aparece uma vez só,
  na resposta do pedido que o gerou (a página não vai para o cache).

Só o gestor, e só nos sites dele: outro papel recebe 403; site ou agendamento de outra empresa,
404.

- **`DIAS_DA_LISTA`** = `(1, 7)`: A lista mostra um dia ou uma semana.
- **`Avisos`** (classe): O que a tela mostra além da lista, depois de um pedido do gestor.
- **`tela_de_agendamentos`**: A lista do dia (ou da semana) de um site do gestor, com a planilha e os links.
- **`subir_planilha`**: Importa a planilha no site e mostra o relatório por linha.
- **`baixar_modelo_csv`**: O modelo da planilha em CSV (só o cabeçalho).
- **`baixar_modelo_xlsx`**: O modelo da planilha em XLSX (a agenda vazia e uma aba de exemplo).
- **`gerar_link`**: Gera um link para uma transportadora e mostra o endereço, uma vez só.
- **`revogar_link`**: Revoga um link: ele deixa de valer na hora.
- **`cancelar`**: Cancela um agendamento e volta à lista do dia dele.

### `nuvem.web.agendar`

`nuvem/src/nuvem/web/agendar.py`

Telas do link da transportadora ([[6.2 Telas do MVP|SDD 6.2]], [[8.2 Segurança|8.2]] e [[D-34]]): agendar pelo celular, sem conta.

- ``GET /agendar/<código>``: o formulário.
- ``POST /agendar/<código>``: cria o agendamento e leva à confirmação (assim, recarregar a página
  não agenda de novo); com erro, volta o formulário com os motivos e o que já estava preenchido.
- ``GET /agendar/<código>/feito/<número>``: a confirmação.

Link vencido, revogado ou inventado: 404, sem dizer qual. No limite: 429. As páginas não vão para
o cache, não mandam o endereço a outros sites e pedem para não ser indexadas. O registro de
acesso troca o código por ``***`` (``EsconderCodigoDoLink``).

- **`CABECALHOS`**: O endereço tem o código: ele não vai para outro site, para o cache nem para buscadores.
- **`TAMANHO_DO_CAMPO`** = `200`: O que passar disto em um campo é cortado (nenhum campo de verdade chega perto).
- **`formulario`**: O formulário do link, vazio.
- **`agendar`**: Cria o agendamento e leva à confirmação; com erro, volta o formulário com os motivos.
- **`feito`**: A confirmação de um agendamento feito por este link.
- **`EsconderCodigoDoLink`** (classe): Troca o código do link por ``***`` no registro de acesso do uvicorn.
- **`esconder_codigo_no_registro_de_acesso`**: Liga o filtro no registro de acesso do uvicorn (uma vez só, mesmo se chamada de novo).

### `nuvem.web.csrf`

`nuvem/src/nuvem/web/csrf.py`

O código anti-CSRF ([[8.2 Segurança|SDD 8.2]], [[D-55]]).

Outro site pode fazer o navegador de alguém mandar um formulário para cá, com o cookie da sessão.
Para isso não valer, todo pedido que muda alguma coisa, de quem tem a sessão aberta, leva um
código que outro site não tem como saber: o HMAC do código da sessão com um segredo só da nuvem
(tirado da chave da cifra). Ele muda a cada login, e nada novo se grava no banco.

- **No formulário:** o campo escondido ``_csrf`` (as telas recebem ``csrf`` no contexto).
- **No HTMX:** o cabeçalho ``X-CSRF-Token`` (o ``hx-headers`` do ``<body>``).
- **Ficam de fora** só as rotas em que o cookie não decide quem pede (``ISENTAS``): o login
  (que recusa o envio vindo de outro site), o link da transportadora, o link de demonstração e
  a API da caixa (pela chave).

- **`ISENTAS`**: O login, exato; os outros, pelo começo do caminho.
- **`CodigoCsrfRecusadoError`** (classe): O pedido muda alguma coisa, tem a sessão, e não trouxe o código certo (403).
- **`segredo`**: O segredo do código, tirado da chave da cifra (só a nuvem tem).
- **`codigo`**: O código anti-CSRF de uma sessão.
- **`isenta`**: Se a rota fica de fora da conferência (o cookie não decide quem pede nela).
- **`codigo_do_pedido`**: O código das telas desta sessão, ou ``None`` sem sessão.
- **`conferir`**: Dependência da aplicação: recusa o pedido que muda alguma coisa sem o código certo.

### `nuvem.web.demonstracao`

`nuvem/src/nuvem/web/demonstracao.py`

As telas da demonstração: o dia ([[T45]], [[D-49]]) e o link por empresa ([[T48]], [[D-52]] e [[D-54]]).

Só existem nos ambientes ``local`` e ``demonstracao`` (fora deles, 404).

- **O dia:** só o gestor começa e acompanha; a tela se atualiza sozinha e leva às telas onde o
  dia acontece: portaria, pátio, mensagens e painel.
- **O link:** a página (``GET``) só mostra para quem é e o botão "Entrar"; o botão (``POST``)
  cria a empresa, na primeira vez, e entra como gestor. O pré-visualizador do WhatsApp abre a
  página e não cria nada.
- **A faixa de papel:** quem é do cliente troca de papel sem senha (gestor, porteiro, líder de
  pátio); o motorista é a tela das mensagens.
- **A administração** gera e revoga os links; o endereço aparece uma vez só.

- **`so_com_demonstracao`**: Fora dos ambientes da demonstração, as rotas não existem (404).
- **`DESTINO_DO_PAPEL`**: Para onde a faixa leva depois de trocar de papel.
- **`andamento`**: O dia de demonstração de um site do gestor: o botão de começar ou o andamento.
- **`comecar`**: Começa o dia de demonstração do site.
- **`pagina_do_link`**: Para quem é a demonstração e o botão de entrar; não cria nada.
- **`entrar_pelo_link`**: Entra na empresa de demonstração do link como gestor (cria a empresa na primeira vez).
- **`trocar_de_papel`**: A faixa da demonstração: passa a sessão para a pessoa do papel, na mesma empresa.
- **`lista_de_links`**: Os links de demonstração e o formulário de gerar um novo.
- **`gerar_link`**: Gera um link para uma empresa visitada e mostra o endereço, uma vez só.
- **`revogar_link`**: Revoga o link: ele deixa de valer, e as pessoas da empresa dele saem na hora.

### `nuvem.web.em_breve`

`nuvem/src/nuvem/web/em_breve.py`

As telas "em breve" do recebimento e do estoque em 3D ([[T46]], [[D-43]] e [[D-45]]).

Mostram para onde o produto vai, sem prometer o que não existe: as duas dizem "em breve", usam
dados de exemplo fixos (inventados, deste arquivo) e não gravam nada. Os módulos de verdade vêm
depois do piloto aprovado ([[ABERTO-19]] e [[ABERTO-20]]).

- **Recebimento:** a nota de um caminhão na doca, item por item, com a contagem do conferente e
  a diferença (a conta da tela também roda no navegador, ao digitar).
- **Estoque:** o armazém em 3D (three.js, em ``estatico/``); a busca acende o lugar do item.

- **`ItemDaNota`** (classe): Um item da nota fiscal e a contagem do conferente (vazia = ainda não contou).
- **`NotaDeExemplo`** (classe): Uma nota fiscal inventada, de um caminhão na doca.
- **`ItemNoEstoque`** (classe): Um item guardado num lugar do armazém: rua, prédio (coluna) e nível (altura).
- **`EstoqueDeExemplo`** (classe): Um armazém inventado: ruas de porta-paletes, com prédios e níveis.
- **`NOTA_DE_EXEMPLO`**: Inventada: o fornecedor, a nota e os códigos não existem.
- **`ESTOQUE_DE_EXEMPLO`**: Inventado: os outros lugares têm paletes "de outros itens", desenhados sem nome.
- **`recebimento`**: A conferência de uma nota na doca, com dados de exemplo.
- **`estoque`**: O armazém em 3D, com a busca, e dados de exemplo.

### `nuvem.web.extrato`

`nuvem/src/nuvem/web/extrato.py`

O painel do gestor e o extrato do mês ([[T44]], [[6.2 Telas do MVP|SDD 6.2]] e [[D-48]]).

- ``/painel``: o dia, o mês até agora contra a linha de base e um gráfico de barras por dia.
- ``/extrato?mes=aaaa-mm``: o extrato em R$, para ler, imprimir ou salvar em PDF.
- ``/extrato.csv?mes=aaaa-mm``: o mesmo extrato em planilha (``;`` e vírgula decimal, como o
  Excel em português abre).

Só o gestor vê. A linha de base de exemplo (a da demonstração) aparece marcada assim.

- **`painel`**: O dia, o mês até agora e cada dia do mês de um site do gestor.
- **`extrato_do_mes`**: O extrato em R$ de um mês (o atual, se nenhum for pedido).
- **`planilha`**: O extrato de um mês em planilha.

### `nuvem.web.mensagens`

`nuvem/src/nuvem/web/mensagens.py`

O celular do motorista ([[T43]], [[6.2 Telas do MVP|SDD 6.2]] e [[D-47]]): as mensagens que ele receberia.

A lista mostra as últimas conversas de um site; cada uma abre numa tela em forma de celular, que
busca a conversa (``/mensagens/agendamentos/{id}/conversa``) ao abrir e a cada 3 segundos. O
canal de demonstração não envia nada; a tela diz isso. O número aparece escondido, só com o DDD
e o fim.

- **`conversas`**: As últimas conversas de um site do usuário (o primeiro, se nenhum for pedido).
- **`celular`**: A tela em forma de celular, com a conversa de um agendamento.
- **`conversa`**: As mensagens de um agendamento (o pedaço da tela que o HTMX troca), com o dia de cada uma.

### `nuvem.web.patio`

`nuvem/src/nuvem/web/patio.py`

A tela do pátio e das docas ([[T42]], [[6.2 Telas do MVP|SDD 6.2]]): o líder vê a fila e as docas e move os caminhões.

A página traz o HTMX, que busca o quadro (``/patio/quadro``) ao abrir e a cada 3 segundos. Chamar
para a doca tem página própria (as docas livres como botões), e começar, terminar e cancelar a
chamada são botões no próprio quadro.

- **`tela_do_patio`**: O pátio de um site do usuário (o primeiro, se nenhum for pedido).
- **`quadro`**: A fila, as docas e os liberados (o pedaço da tela que o HTMX troca).
- **`tela_de_chamar`**: As docas livres do site, para chamar o caminhão.
- **`chamar`**: Chama o caminhão para a doca escolhida.
- **`comecar`**: O caminhão chegou à doca.
- **`terminar`**: Terminou a carga ou a descarga.
- **`cancelar_chamada`**: O caminhão chamado não veio: volta para a fila.

### `nuvem.web.portaria`

`nuvem/src/nuvem/web/portaria.py`

Tela crua da portaria ([[T12]], [[T34]] e [[T38]]): as últimas passagens e as exceções abertas do site.

A página traz o HTMX, que busca as listas (``/portaria/passagens`` e ``/portaria/excecoes``) ao
abrir e a cada 2 segundos. A atualização empurrada pelo servidor (SSE) e a resolução das
exceções vêm com a tela definitiva, no mês 3.

A conferência da placa ([[D-42]]) tem página própria (``/portaria/conferir/<passagem>``), fora das
listas que se atualizam: a atualização não apaga o que o porteiro digita.

- **`CACHE_DA_FOTO`** = `'private, max-age=86400, immutable'`: A foto de uma passagem nunca muda ([[5.5 Garantias|SDD 5.5]]): o navegador pode guardá-la.
- **`tela_da_portaria`**: A tela da portaria de um site do usuário (o primeiro, se nenhum for pedido).
- **`lista_de_passagens`**: A lista das últimas passagens (o pedaço da tela que o HTMX troca).
- **`tela_de_conferir`**: Os recortes de placa de uma passagem, para o porteiro confirmar ou corrigir ([[D-42]]).
- **`conferir`**: Grava a placa certa de um recorte e volta para a página da conferência.
- **`lista_de_excecoes`**: As exceções abertas do site, da chegada mais antiga para a mais nova (só ver).
- **`foto`**: Uma foto de uma passagem que o usuário vê (404 para qualquer outra).

### `nuvem.web.resolucao`

`nuvem/src/nuvem/web/resolucao.py`

O porteiro resolve a exceção e registra a chegada à mão ([[T41]], [[5.2 Estados da visita|SDD 5.2]] e [[D-46]]).

Cada exceção tem página própria (``/portaria/excecoes/<id>``), fora da lista que se atualiza a
cada 2 segundos: a foto, as placas, os agendamentos possíveis pelos pontos e as ações ("é este",
"sem agendamento", "recusar" e corrigir a placa). A chegada manual (``/portaria/chegada-manual``)
pede as placas, sugere os agendamentos e registra com o que o porteiro escolher.

- **`tela_da_excecao`**: A exceção, com a foto, as placas, os agendamentos possíveis e as ações.
- **`e_este`**: "É este": liga a chegada ao agendamento escolhido.
- **`sem_agendamento`**: Aceita a chegada sem agendamento.
- **`recusar`**: Recusa a entrada.
- **`corrigir_na_foto`**: Confere a placa de uma foto da exceção; se ela muda, o casamento roda de novo.
- **`digitar_cavalo`**: A placa do cavalo digitada, quando não há foto; o casamento roda de novo.
- **`tela_da_chegada_manual`**: As placas; com elas, os agendamentos sugeridos pelos pontos.
- **`registrar_chegada_manual`**: Registra a chegada com o agendamento escolhido (ou nenhum).

### `nuvem.web.rotas`

`nuvem/src/nuvem/web/rotas.py`

Telas de entrar, sair, início e troca de porteiro ([[8.2 Segurança|SDD 8.2]]).

O login abre uma sessão no banco e põe o código dela num cookie ``HttpOnly`` e
``SameSite=Lax`` (``Secure`` fora do ambiente local). O ``SameSite=Lax`` também impede que
outro site faça o navegador postar formulários aqui com o cookie. O login, que não usa o
cookie, recusa o envio que o navegador marca como vindo de outro site (``Sec-Fetch-Site``).

- **`tela`**: Desenha uma tela do painel.
- **`endereco_de`**: O endereço IP de quem pede: do cabeçalho de confiança, se configurado ([[D-55]]).
- **`tela_de_entrar`**: O formulário de e-mail e senha.
- **`entrar`**: Confere e-mail e senha; se baterem, abre a sessão e leva ao início.
- **`sair`**: Fecha a sessão no servidor e apaga o cookie.
- **`inicio`**: A tela inicial de quem entrou.
- **`tela_de_trocar_porteiro`**: Os porteiros que podem assumir o tablet, e o campo do PIN.
- **`trocar_porteiro`**: Passa a sessão para o porteiro escolhido, se o PIN dele conferir.
- **`ir_com_a_sessao`**: Leva a ``destino`` com o cookie da sessão aberta (o código só vai no cookie).

## Testes

- `nuvem/tests/test_nuvem_web_agendamentos.py`: Tela de agendamentos ([[6.2 Telas do MVP|SDD 6.2]]): o gestor vê e alimenta os agendamentos dos sites dele.
- `nuvem/tests/test_nuvem_web_agendar.py`: Telas do link da transportadora ([[6.2 Telas do MVP|SDD 6.2]] e [[8.2 Segurança|8.2]]): o formulário, a confirmação e os avisos.
- `nuvem/tests/test_nuvem_web_csrf.py`: O código anti-CSRF ([[8.2 Segurança|SDD 8.2]], [[D-55]]): todo pedido que muda alguma coisa, de quem tem a sessão aberta, leva o código tirado da sessão.
- `nuvem/tests/test_nuvem_web_demonstracao.py`: A tela do dia de demonstração ([[T45]], [[D-49]]): começar o dia e acompanhar.
- `nuvem/tests/test_nuvem_web_demonstracao_link.py`: As telas do link de demonstração ([[T48]], [[D-52]] e [[D-54]]): a administração, a página do link e a faixa que troca de papel.
- `nuvem/tests/test_nuvem_web_em_breve.py`: As telas "em breve" do recebimento e do estoque em 3D ([[T46]], [[D-43]] e [[D-45]]), e os arquivos de terceiros que o painel serve.
- `nuvem/tests/test_nuvem_web_extrato.py`: O painel do gestor e o extrato na tela ([[T44]], [[6.2 Telas do MVP|SDD 6.2]] e [[D-48]]).
- `nuvem/tests/test_nuvem_web_login.py`: Telas de entrar, sair e trocar de porteiro: cookie seguro e respostas certas.
- `nuvem/tests/test_nuvem_web_mensagens.py`: A tela do celular do motorista ([[T43]], [[6.2 Telas do MVP|SDD 6.2]] e [[D-47]]): as mensagens que ele receberia.
- `nuvem/tests/test_nuvem_web_patio.py`: A tela do pátio e das docas ([[T42]], [[6.2 Telas do MVP|SDD 6.2]]): o líder vê a fila e as docas e move os caminhões.
- `nuvem/tests/test_nuvem_web_portaria.py`: Tela crua da portaria ([[T12]]): as últimas passagens do site, atualizadas a cada 2 segundos.
- `nuvem/tests/test_nuvem_web_portaria_conferencia.py`: A conferência da placa na tela da portaria ([[T38]], SDD [[D-42]]).
- `nuvem/tests/test_nuvem_web_portaria_excecoes.py`: Exceções na tela da portaria ([[T34]]): o porteiro vê, com a foto e os candidatos; resolver é no mês 3.
- `nuvem/tests/test_nuvem_web_portaria_resolucao.py`: Resolver a exceção e registrar a chegada à mão pela tela da portaria ([[T41]], [[5.2 Estados da visita|SDD 5.2]] e [[D-46]]).
- `nuvem/tests/test_nuvem_web_portaria_resultado.py`: O resultado do casamento na lista de passagens da portaria ([[T35]], [[6.2 Telas do MVP|SDD 6.2]]).

---

Do [[Mapa do código]].

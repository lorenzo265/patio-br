---
tipo: "pacote"
fonte: "nuvem/src/nuvem/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem

Pasta `nuvem/src/nuvem/`.

Aplicação da nuvem: API, painel e módulos do produto ([[3.3 Módulos da nuvem no MVP|SDD, seção 3.3]]).

## Subpacotes

- [[nuvem.agendamento]]: Agendamento ([[3.3 Módulos da nuvem no MVP|SDD 3.3]] e [[3.4 Conectores de agendamento|3.4]]): os agendamentos de cada site e os conectores que os trazem.
- [[nuvem.cadastro]]: Módulo cadastro ([[3.3 Módulos da nuvem no MVP|SDD 3.3]]): empresas, sites, portarias, faixas, câmeras, docas e usuários.
- [[nuvem.demonstracao]]: A demonstração comercial ([[D-45]] e [[D-49]]): empresas inventadas, o mês de histórico e o dia ao vivo.
- [[nuvem.extrato]]: Indicadores e extrato do mês em R$ ([[5.4 Contas do extrato|SDD 5.4]] e [[D-48]]).
- [[nuvem.frota]]: Frota de borda ([[3.3 Módulos da nuvem no MVP|SDD 3.3]] e [[7.4 A caixa de borda|7.4]]): as caixas de cada site, a ativação e a chave de cada uma.
- [[nuvem.mensagens]]: Mensagens ao motorista ([[2.2 A jornada de um caminhão (modo A)|SDD 2.2]], [[7.5 WhatsApp e SMS|7.5]] e [[D-47]]): a confirmação e os avisos da fila e da doca.
- [[nuvem.patio]]: Pátio e docas ([[2.2 A jornada de um caminhão (modo A)|SDD 2.2]], passos 4 e 5): a fila, a chamada para a doca, o início e o fim.
- [[nuvem.portaria]]: Portaria ([[3.3 Módulos da nuvem no MVP|SDD 3.3]]): recebe as passagens da borda; no mês 2, casa com o agendamento.
- [[nuvem.web]]: Telas do painel ([[6.2 Telas do MVP|SDD 6.2]]): páginas feitas no servidor, com Jinja.

## Módulos

### `nuvem.administracao`

`nuvem/src/nuvem/administracao.py`

O comando da administração no servidor ([[8.2 Segurança|SDD 8.2]]): ``python -m nuvem.administracao``.

- ``uv run python -m nuvem.administracao --nome "Fulano" --email fulano@exemplo.com`` pede a
  senha duas vezes, sem mostrar, e cria a conta no banco de ``PATIO_URL_BANCO``. É assim que a
  administração nasce fora do ambiente local, onde a semente não roda.
- ``uv run python -m nuvem.administracao --zerar-duas-etapas --email fulano@exemplo.com`` zera a
  verificação em duas etapas de quem perdeu o celular e fecha as sessões dele ([[D-60]]). Na
  próxima entrada, ele liga a verificação de novo. Serve para a administração, que não tem
  quem a zere pelo painel (o usuário do cliente, a administração zera pelo painel).

- **`principal`**: Cria a conta, ou zera a verificação em duas etapas; devolve 0 se deu certo, 1 se não.

### `nuvem.armazenamento`

`nuvem/src/nuvem/armazenamento.py`

Armazenamento das fotos das passagens ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]], [[D-22]]).

A caixa pede um endereço de envio para cada foto e manda a foto direto para ele. O endereço é
temporário (15 minutos) e já autoriza o envio, sem a chave da caixa: é assim que o S3 funciona
(endereço assinado), e é assim que o armazenamento local imita, com um código cifrado no
endereço. A caixa só aprende uma regra: "peça o endereço e envie".

Implementações:

- ``ArmazenamentoLocal``: uma pasta no disco (o ambiente local);
- ``ArmazenamentoS3``: um balde S3, pelo boto3 ([[D-56]]): o Supabase Storage na demonstração e a
  AWS no mês 4. O endereço de envio é o endereço assinado do próprio S3.

Cada caixa tem a sua pasta: o ``ref`` que a caixa escolhe nunca alcança a foto de outra.

- **`TAMANHO_MAXIMO_DA_FOTO`** = `2 * 1024 * 1024`: 2 MB: um recorte de placa tem dezenas de KB; uma foto de contexto, algumas centenas.
- **`CAMINHO_DO_ENVIO`** = `'/api/borda/fotos/envio/'`: Onde o armazenamento local recebe as fotos (o código cifrado vem depois).
- **`RefInvalidoError`** (classe): O ``ref`` da foto foge da regra (letras, números, ``.``, ``_``, ``-``, ``/``).
- **`EnderecoRecusadoError`** (classe): O endereço de envio foi alterado, é de outra chave ou venceu.
- **`FotoInvalidaError`** (classe): A foto não serve (a mensagem diz por quê).
- **`FotoNaoJpegError`** (classe): A foto não é JPEG.
- **`FotoGrandeDemaisError`** (classe): A foto passa de 2 MB.
- **`FotoDiferenteError`** (classe): Já existe outra foto neste ``ref``: a foto guardada não se troca ([[5.5 Garantias|SDD 5.5]]).
- **`validar_ref`**: Confere se o ``ref`` da foto segue a regra (e não sairia da pasta da caixa).
- **`Armazenamento`** (classe): O que a nuvem faz com as fotos, seja qual for o armazenamento.
- **`armazenamento_da_configuracao`**: O S3, se a configuração tem o endereço dele; senão, a pasta do disco.
- **`ArmazenamentoS3`** (classe): Fotos num balde S3 ([[D-56]]), cada caixa na sua pasta (``caixa-<id>/``), como no disco.
- **`ArmazenamentoLocal`** (classe): Fotos numa pasta do disco; o endereço de envio aponta para a própria API.
- **`obter_armazenamento`**: Dependência do FastAPI: o armazenamento de fotos da aplicação.

### `nuvem.banco`

`nuvem/src/nuvem/banco.py`

Conexão com o PostgreSQL (SQLAlchemy 2, driver pg8000) e a base dos modelos da nuvem.

- **`CONVENCAO_DE_NOMES`**: Nomes previsíveis para índices e restrições: as migrações conseguem achá-los depois.
- **`Base`** (classe): Base de todas as tabelas da nuvem; as migrações (Alembic) partem deste metadata.
- **`texto_de_lista`**: Coluna de texto que só aceita os valores de um ``Literal`` (ex.: ``Sentido``).
- **`do_pai_na_mesma_empresa`**: Chave estrangeira composta (pai, empresa) de uma tabela filha de cliente ([[5.5 Garantias|SDD 5.5]]).
- **`pode_ser_pai`**: A dupla (id, empresa) única, que a chave estrangeira composta dos filhos exige no pai.
- **`SQLSTATE_SO_ACRESCENTA`** = `'23001'`: O gatilho ``so_acrescenta`` recusou alterar ou apagar uma linha de prova ([[5.5 Garantias|SDD 5.5]]).
- **`sqlstate`**: Devolve o código SQLSTATE do PostgreSQL que causou o erro (ex.: ``"23503"``).
- **`criar_motor`**: Cria o motor de conexões; ``pool_pre_ping`` descarta conexões que o banco já fechou.
- **`contexto_ssl`**: O SSL da conexão com o banco, se a configuração pede (conferindo o certificado).
- **`motor_da_configuracao`**: O motor do banco como a configuração pede (pool e SSL).
- **`obter_sessao`**: Dependência do FastAPI: uma sessão por requisição, fechada ao final dela.

### `nuvem.cifra`

`nuvem/src/nuvem/cifra.py`

Cifra dos segredos que a nuvem precisa guardar e depois ler de volta (ex.: senha da câmera).

Usa Fernet (biblioteca ``cryptography``): AES-128 em modo CBC com HMAC-SHA256, que também
detecta texto alterado. A chave vem da configuração (``PATIO_CHAVE_CIFRA``) e nunca do banco:
quem copia o banco sem a chave não lê os segredos.

- **`SegredoIlegivelError`** (classe): O texto cifrado não abre com esta chave (chave trocada ou texto alterado).
- **`Cifra`** (classe): Cifra e decifra textos com a chave da configuração.
- **`obter_cifra`**: Dependência do FastAPI: a cifra da aplicação, com a chave da configuração.

### `nuvem.config`

`nuvem/src/nuvem/config.py`

Configuração da nuvem, lida do ambiente.

Cada valor vem de uma variável ``PATIO_<NOME>`` ou, no desenvolvimento, do ``.env`` da pasta
atual (o mesmo que o docker compose lê; as variáveis dele, sem o prefixo, são ignoradas aqui).
Valor obrigatório ausente impede a nuvem de iniciar: melhor parar na hora do que rodar errado.

- **`TAMANHO_DO_SEGREDO`** = `32`: O menor segredo de webhook que vai no endereço (ex.: ``secrets.token_urlsafe(32)``).
- **`Configuracao`** (classe): Os valores que mudam entre ambientes (local, homologação, produção).
- **`ConfiguracaoInvalidaError`** (classe): Falta um valor obrigatório no ambiente, ou um valor não é válido.
- **`ler_configuracao`**: Lê a configuração do ambiente e do ``.env`` da pasta atual.

### `nuvem.cron`

`nuvem/src/nuvem/cron.py`

O cron diário ([[D-56]]): ``GET /api/cron/diaria``, chamado pela Vercel uma vez por dia.

Apaga as empresas dos links de demonstração vencidos ou revogados ([[D-54]]) e confere o "não
veio" ([[5.2 Estados da visita|SDD 5.2]]), o que o worker faria. Só com o segredo do cron (o ``CRON_SECRET`` da Vercel,
que ela manda em ``Authorization: Bearer ...``); sem o segredo configurado, a rota não existe.
Rodar duas vezes não faz mal: o que já foi feito não se faz de novo.

- **`diaria`**: Apaga as empresas de demonstração vencidas e confere o "não veio".

### `nuvem.erros`

`nuvem/src/nuvem/erros.py`

Erros de regra da nuvem, comuns a todos os módulos.

- **`NaoEncontradoError`** (classe): O registro não existe ou não pertence a quem pediu: para quem pediu, dá no mesmo.
- **`DadoInvalidoError`** (classe): Um dado recebido não segue a regra do cadastro (a mensagem diz qual).
- **`NaoIdentificadoError`** (classe): Ninguém entrou no sistema (sem sessão, ou sessão vencida): a API responde 401.
- **`SemPermissaoError`** (classe): Quem pede entrou, mas o papel dele não permite isto: a API responde 403.
- **`CaixaNaoIdentificadaError`** (classe): A chamada da borda veio sem chave, com chave inventada ou revogada: a API responde 401.

### `nuvem.principal`

`nuvem/src/nuvem/principal.py`

A aplicação da nuvem ([[3.3 Módulos da nuvem no MVP|SDD 3.3]]).

Para rodar: ``uvicorn nuvem.principal:criar_app --factory``. Cada módulo do produto registra
aqui as suas rotas.

- **`PASTA_ESTATICA`** = `Path(web.__file__).parent / 'estatico'`: Arquivos de terceiros servidos como estão (o HTMX e o three.js), em ``/estatico``.
- **`criar_app`**: Monta a aplicação.
- **`saude`**: Responde se a API está no ar e alcança o banco (503 quando não alcança).

### `nuvem.relogio`

`nuvem/src/nuvem/relogio.py`

A hora de agora, num lugar só: as regras recebem a hora, e os testes escolhem qual é.

- **`agora`**: Dependência do FastAPI: a hora atual, com fuso (UTC).

### `nuvem.semente`

`nuvem/src/nuvem/semente.py`

Dados de demonstração: ``uv run tarefas semente``.

Duas empresas inventadas, para ver a separação na prática:

- **Empresa A**: o site "CD Exemplo" (aberto das 6h às 22h; uma portaria com uma faixa de
  entrada e uma de saída, três câmeras e duas docas), mais o site "CD Exemplo 2", que ninguém da
  A vê; no CD Exemplo, um gestor, um líder de pátio e dois porteiros (dia e noite), e os
  parâmetros do extrato com uma linha de base **de exemplo** ([[D-48]]), marcada assim na tela;
- **Empresa B**: o site "CD Outra Empresa", com uma câmera, um gestor e um porteiro;
- **Administração** (nós): uma pessoa, fora das duas empresas.

Todos entram com a senha ``SENHA_DA_DEMONSTRACAO``; os porteiros têm o PIN
``PIN_DA_DEMONSTRACAO``. Os e-mails estão abaixo, em ``semear``.

Os mesmos dados servem de cenário aos testes da nuvem. Roda uma vez: se já existem, não faz
nada. Só para desenvolvimento e demonstração; nunca em produção.

- **`CNPJ_B`** = `'DEMO0000000B00'`: CNPJs que não existem: as letras DEMO marcam os dados como de demonstração.
- **`SENHA_DAS_CAMERAS`** = `'camera-local'`: Senha inventada das câmeras de demonstração (gravada cifrada, como qualquer outra).
- **`SENHA_DA_DEMONSTRACAO`** = `'demonstracao-local'`: Senha inventada de todas as pessoas da demonstração (gravada só como resumo).
- **`PIN_DA_DEMONSTRACAO`** = `'135790'`: PIN inventado dos porteiros da demonstração.
- **`PARAMETROS_DE_EXEMPLO`**: Três pontos de portaria 24 horas, um a menos depois, pelo menor custo da seção 1.1 do SDD.
- **`LINHA_DE_BASE_DE_EXEMPLO`**: Números inventados de um mês antes do sistema, para a demonstração ter com o que comparar.
- **`Demonstracao`** (classe): O que a semente gravou, para os testes e para quem quiser olhar.
- **`semear`**: Grava os dados de demonstração (sem commit).
- **`principal`**: Grava os dados de demonstração no banco de desenvolvimento (``PATIO_URL_BANCO``).

### `nuvem.senhas`

`nuvem/src/nuvem/senhas.py`

Resumo de senhas e PINs com argon2id ([[8.2 Segurança|SDD 8.2]]).

Guarda-se só o resumo: dá para conferir se uma senha bate, nunca para recuperá-la. O argon2 é
lento de propósito (e gasta memória), o que torna caro adivinhar senhas a partir de um banco
copiado. O resumo leva junto o sal e o custo usado, então mudar o custo não invalida os resumos
antigos: eles são refeitos quando a pessoa entra.

- **`RESUMOS_AO_MESMO_TEMPO`** = `4`: Quantos resumos o processo faz ao mesmo tempo; os outros esperam a vez ([[8.2 Segurança|SDD 8.2]]).
- **`Senhas`** (classe): Faz e confere resumos de senhas e PINs.
- **`resumo_rapido`**: Resumo SHA-256 (64 caracteres), para códigos aleatórios e longos que a nuvem só confere.
- **`obter_senhas`**: Dependência do FastAPI: o resumidor de senhas da aplicação.

### `nuvem.tarefas_de_fundo`

`nuvem/src/nuvem/tarefas_de_fundo.py`

Fila de tarefas no PostgreSQL e o laço do worker ([[6.1 Stack|SDD 6.1]], [[D-16]] e [[D-38]]).

- **Enfileirar:** a passagem recebida vira a tarefa "casar" (uma só por passagem: a chave), na
  mesma transação que a grava.
- **Pegar:** ``SELECT ... FOR UPDATE SKIP LOCKED``: a tarefa fica travada até o fim da
  transação, e dois workers nunca pegam a mesma.
- **Falhar:** o que a tarefa gravou é desfeito; ela volta para a fila esperando cada vez mais
  (``espera``), até ``MAXIMO_DE_TENTATIVAS``; depois, fica como falhou, com o erro.
- **"Não veio"** ([[5.2 Estados da visita|SDD 5.2]]): a cada 5 minutos, o agendamento ativo sem visita, com a janela
  vencida há mais que a tolerância, ganha a visita em ``NAO_VEIO``. Um worker de cada vez (trava
  do PostgreSQL).
- **Mensagens ao motorista** ([[D-47]]): a cada volta, as que faltam (``mensagens.preparar``); a
  que sai por um canal de verdade vira a tarefa "enviar mensagem", e o aviso do webhook do
  WhatsApp e o do SMS, as tarefas "aviso do WhatsApp" e "aviso do SMS" ([[D-63]] e [[D-64]]). Elas usam
  os canais do ``Contexto``.
- **Dia de demonstração** ([[D-49]]): a cada volta, se o ambiente tiver, as chegadas e o líder
  automático.

O worker roda em outro processo (``python -m nuvem.worker``).

- **`TAMANHO_DO_ERRO`** = `500`: O texto do erro guardado na tarefa é cortado aqui.
- **`TOLERANCIA_DO_NAO_VEIO`** = `TOLERANCIA_PADRAO`: Quanto depois do fim da janela o agendamento sem chegada vira "não veio" ([[ABERTO-09]]).
- **`JANELAS_OLHADAS`** = `timedelta(days=7)`: O "não veio" olha as janelas que terminaram nos últimos 7 dias (cobre o worker parado).
- **`TRAVA_DO_NAO_VEIO`** = `7301`: Número da trava do PostgreSQL que deixa um worker de cada vez conferir o "não veio".
- **`PAUSA`** = `1.0`: Segundos de espera quando a fila está vazia.
- **`TarefaDeFundo`** (classe): Uma tarefa para o worker. É da plataforma, não de um cliente: os dados dizem o que fazer.
- **`Contexto`** (classe): O que as tarefas usam além do banco: os canais das mensagens ([[D-63]]).
- **`EXECUTORES`**: O que cada tipo de tarefa faz.
- **`enfileirar`**: Põe uma tarefa na fila, para já; a mesma chave do mesmo tipo de novo não muda nada.
- **`pegar_proxima`**: A tarefa pendente mais antiga que já pode rodar, travada até o fim da transação.
- **`situacao_das_tarefas`**: A situação da tarefa de cada chave (ex.: o "casar" de cada passagem), por chave.
- **`espera`**: Quanto esperar depois da falha número ``tentativas``: 10 s, 20 s, 40 s ... até 10 min.
- **`executar_uma`**: Executa a próxima tarefa e grava o resultado (com ``commit``).
- **`executar_pendentes`**: Executa as tarefas que já podem rodar, até ``limite``; devolve quantas executou.
- **`conferir_nao_veio`**: Abre a visita "não veio" de cada agendamento vencido sem chegada (sem ``commit``).
- **`rodar`**: Executa as tarefas, confere o "não veio" e prepara as mensagens até ``parar`` ser ligado.

### `nuvem.tique`

`nuvem/src/nuvem/tique.py`

O tique ([[D-51]] e [[D-56]]): o trabalho do worker, um pouco de cada vez, quando uma tela se atualiza.

A Vercel não tem processo que fica rodando. Com ``PATIO_TIQUE``, as telas que se atualizam
sozinhas (``TELAS``) rodam antes uma volta do que o worker faria: o dia de demonstração, as
tarefas da fila (o casamento) e as mensagens. Um tique de cada vez (trava do PostgreSQL): o
pedido que chega com outro tique rodando segue sem esperar. Um erro no tique fica registrado, e
a tela abre do mesmo jeito.

O "não veio" e a faxina das empresas de demonstração ficam para o cron diário (``nuvem.cron``).

- **`TELAS`**: As telas que se atualizam sozinhas (HTMX ou o refresh da página).
- **`TAREFAS_POR_TIQUE`** = `20`: O tique não segura a tela: no máximo estas tarefas da fila de cada vez.
- **`avancar`**: Uma volta do trabalho do worker (com ``commit``).
- **`na_tela`**: Dependência da aplicação: o tique antes das telas que se atualizam, se ligado.

### `nuvem.worker`

`nuvem/src/nuvem/worker.py`

O worker da nuvem ([[6.1 Stack|SDD 6.1]] e [[D-38]]): ``python -m nuvem.worker``.

Executa as tarefas da fila (o casamento das passagens; o envio das mensagens e o aviso do
WhatsApp, [[D-63]]), confere o "não veio", prepara as mensagens e, nos ambientes que têm, avança o
dia de demonstração ([[D-49]]) e apaga as empresas dos links de demonstração vencidos ([[D-54]]), até
receber o sinal de parar (SIGTERM do Docker, ou Ctrl+C). Lê a configuração do ambiente, como a
API.

- **`main`**: Sobe o worker e roda até o sinal de parar.

## Testes

- `nuvem/tests/test_nuvem_administracao.py`: O comando que cria a administração ([[8.2 Segurança|SDD 8.2]]): ``python -m nuvem.administracao``.
- `nuvem/tests/test_nuvem_armazenamento.py`: Armazenamento local das fotos ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]], [[D-22]]): endereço temporário, foto que não se edita.
- `nuvem/tests/test_nuvem_armazenamento_s3.py`: As fotos num armazenamento S3 ([[D-56]]): o Supabase Storage na demonstração e a AWS no mês 4.
- `nuvem/tests/test_nuvem_banco.py`: O banco de teste: migrado do zero no início e limpo a cada teste.
- `nuvem/tests/test_nuvem_banco_conexao.py`: Como a nuvem se liga ao banco ([[D-56]]): sem pool na função da Vercel e com SSL no Supabase.
- `nuvem/tests/test_nuvem_cifra.py`: Cifra dos segredos guardados no banco (ex.: senha da câmera).
- `nuvem/tests/test_nuvem_config.py`: Configuração da nuvem: lida do ambiente (variáveis PATIO_*) ou do .env da pasta atual.
- `nuvem/tests/test_nuvem_pacote.py`: O pacote nuvem usa o mesmo contrato de passagem que o resto do sistema ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]]).
- `nuvem/tests/test_nuvem_saude.py`: GET /saude: a API está no ar e alcança o banco.
- `nuvem/tests/test_nuvem_semente.py`: Dados de demonstração (`uv run tarefas semente`).
- `nuvem/tests/test_nuvem_senhas.py`: Resumo de senhas e PINs com argon2 ([[8.2 Segurança|SDD 8.2]]): guarda-se o resumo, nunca o texto.
- `nuvem/tests/test_nuvem_tarefas_de_fundo.py`: Fila de tarefas e worker ([[6.1 Stack|SDD 6.1]] e [[D-38]]): o casamento e o "não veio" fora do pedido da caixa.
- `nuvem/tests/test_nuvem_vercel.py`: A entrada da Vercel ([[D-51]] e [[D-56]]): o `app`, o `vercel.json` e o `pyproject.toml` combinam.

---

Do [[Mapa do código]].

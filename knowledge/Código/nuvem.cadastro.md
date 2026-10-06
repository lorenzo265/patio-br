---
tipo: "pacote"
fonte: "nuvem/src/nuvem/cadastro/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/cadastro/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.cadastro

Pasta `nuvem/src/nuvem/cadastro/`.

Módulo cadastro ([[3.3 Módulos da nuvem no MVP|SDD 3.3]]): empresas, sites, portarias, faixas, câmeras, docas e usuários.

## Módulos

### `nuvem.cadastro.acesso`

`nuvem/src/nuvem/cadastro/acesso.py`

Quem está pedindo: o usuário do cliente (com empresa, papel e sites) ou a administração.

Toda leitura de dado do cliente recebe um ``Acesso`` ([[5.5 Garantias|SDD 5.5]]). Ele nasce da sessão de login
([[D-20]]): o cookie traz o código, e o banco diz de quem é. A administração (nós) recebe um
``AcessoAdmin``, de outro tipo, que nunca serve onde se pede um ``Acesso`` ([[D-19]]).

As dependências do FastAPI daqui respondem 401 sem login e 403 com o papel errado.

- **`Acesso`** (classe): O que um usuário do cliente pode ver: só a empresa dele e, nela, só os sites dele.
- **`AcessoAdmin`** (classe): Alguém da administração da plataforma (nós), que atravessa empresas pelas rotas dela.
- **`acesso_do_usuario`**: Monta o acesso de um usuário a partir do cadastro.
- **`obter_quem`**: Dependência do FastAPI: quem está na sessão do cookie.
- **`obter_acesso`**: Dependência do FastAPI: o acesso do usuário do cliente que fez a requisição.
- **`exigir_papel`**: Cria a dependência que só deixa passar os papéis dados (os outros recebem 403).
- **`obter_acesso_admin`**: Dependência do FastAPI: só a administração passa (o usuário do cliente recebe 403).

### `nuvem.cadastro.login`

`nuvem/src/nuvem/cadastro/login.py`

Login ([[8.2 Segurança|SDD 8.2]]): senha, sessão no banco ([[D-20]]), limite de tentativas e troca de porteiro.

Quem entra é uma **conta**: um usuário do cliente ou alguém da administração ([[D-19]]). As duas
entram pela mesma tela, com e-mail e senha; o e-mail é único entre as duas tabelas.

As funções gravam com ``flush``; o ``commit`` é de quem chama. Atenção: uma recusa também grava
o erro (para o limite de tentativas), então quem chama faz ``commit`` mesmo quando recebe
``LoginRecusadoError``.

As tentativas de um mesmo alvo passam uma de cada vez: a trava no banco vale até o ``commit``
(ou o ``rollback``) de quem chama.

- **`VALIDADE_DA_SESSAO`** = `timedelta(hours=12)`: Um turno de portaria; depois disso, entra de novo.
- **`MAXIMO_DE_ERROS`** = `5`: No máximo 5 erros por alvo (e-mail ou porteiro) a cada 15 minutos.
- **`MAXIMO_DE_ERROS_POR_ENDERECO`** = `20`: E no máximo 20 por endereço IP ([[D-55]]): uma rede pode ter várias pessoas.
- **`LoginRecusadoError`** (classe): E-mail, senha ou PIN não conferem (de propósito, sem dizer qual).
- **`MuitasTentativasError`** (classe): Erros demais para o mesmo alvo nos últimos 15 minutos: espere e tente de novo.
- **`normalizar_email`**: O e-mail como é guardado e comparado: sem espaços nas pontas, em minúsculas.
- **`conta_por_email`**: Devolve o usuário ou o administrador com este e-mail, se houver.
- **`entrar`**: Confere e-mail e senha e abre uma sessão.
- **`sair`**: Fecha a sessão do código (se ela existir).
- **`conta_da_sessao`**: Devolve quem está na sessão do código, ou ``None`` se ela não vale.
- **`porteiros_da_troca`**: Os porteiros que podem assumir o tablet deste usuário, por nome.
- **`trocar_porteiro`**: Passa a sessão aberta no tablet para o porteiro do turno, que confirma com o PIN.
- **`abrir_sessao`**: Abre uma sessão para a conta, sem conferir nada: quem chama já sabe quem é.

### `nuvem.cadastro.modelos`

`nuvem/src/nuvem/cadastro/modelos.py`

Tabelas do cadastro ([[5.1 Entidades|SDD 5.1]]): a estrutura física do cliente, os usuários e o login.

Toda tabela de dados do cliente tem ``empresa_id``. Cada tabela filha aponta para o pai por
uma chave estrangeira composta, (pai, empresa): o banco recusa, por exemplo, uma portaria da
empresa B num site da empresa A, mesmo que o código erre ([[5.5 Garantias|SDD 5.5]]).

A administração (nós) fica fora das empresas, numa tabela própria (SDD [[D-19]]).

- **`Papel`** = `Literal['porteiro', 'patio', 'gestor']`: Papéis dos usuários do cliente. A administração (nós) não é usuário de cliente ([[D-19]]).
- **`FORMATO_CNPJ`** = `'^[0-9A-Z]{12}[0-9]{2}$'`: 14 caracteres: 12 letras ou números (CNPJ alfanumérico, desde julho de 2026) e 2 dígitos.
- **`Empresa`** (classe): Um cliente.
- **`Site`** (classe): Um local do cliente com portaria e pátio (ex.: um centro de distribuição).
- **`Portaria`** (classe): Uma portaria do site; tem uma ou mais faixas.
- **`Faixa`** (classe): Uma faixa da portaria, de entrada ou de saída.
- **`Camera`** (classe): Uma câmera IP da faixa. A senha fica cifrada (ver ``nuvem.cifra``).
- **`Doca`** (classe): Uma doca de carga e descarga do site.
- **`Usuario`** (classe): Uma pessoa do cliente que usa o painel.
- **`UsuarioSite`** (classe): Os sites que um usuário vê; sempre da mesma empresa do usuário.
- **`Administrador`** (classe): Uma pessoa da administração da plataforma (nós), fora de qualquer empresa ([[D-19]]).
- **`SessaoLogin`** (classe): Uma sessão aberta no painel ([[D-20]]): de um usuário do cliente ou da administração.
- **`TentativaLogin`** (classe): Um erro de senha ou de PIN, para o limite de tentativas ([[8.2 Segurança|SDD 8.2]]).

### `nuvem.cadastro.rotas`

`nuvem/src/nuvem/cadastro/rotas.py`

Rotas do cadastro: o cliente consulta os sites e as câmeras que vê; a administração, as
empresas.

Sem login, 401; com o papel errado, 403; o que é de outra empresa, 404. Câmera sai sem login
nem senha.

- **`SitePublico`** (classe): Um site como a API o mostra.
- **`EmpresaPublica`** (classe): Uma empresa como a API da administração a mostra.
- **`SiteParaAdministracao`** (classe): Um site como a administração o vê: com a empresa.
- **`CameraPublica`** (classe): Uma câmera como a API a mostra: sem login nem senha.
- **`listar_sites`**: Os sites que o usuário vê.
- **`obter_site`**: Um site que o usuário vê (404 para qualquer outro).
- **`listar_cameras`**: As câmeras de um site que o gestor vê (404 para qualquer outro site).
- **`listar_empresas`**: Todas as empresas (só a administração).
- **`listar_sites_para_administracao`**: Todos os sites, de todas as empresas (só a administração).

### `nuvem.cadastro.servico`

`nuvem/src/nuvem/cadastro/servico.py`

Regras do cadastro.

Três portas de entrada:

- **Leitura pelo cliente:** toda função recebe o ``Acesso`` de quem pede e só enxerga a empresa
  e os sites dele ([[5.5 Garantias|SDD 5.5]]). O que é de outro "não existe" (``NaoEncontradoError``), sem dizer
  que existe.
- **Leitura pela borda:** a caixa de borda, já identificada pela chave, lê a estrutura do
  próprio site; a função recebe a empresa e o site da caixa e filtra pelos dois.
- **Administração (nós):** criar a estrutura de um cliente e as pessoas que usam o painel.
  Cada filho herda a empresa do pai recebido, então não há como passar a empresa errada.

As funções gravam com ``flush`` (o registro ganha id); o ``commit`` é de quem chama.

- **`TAMANHO_DA_SENHA`** = `range(10, 129)`: De 10 a 128 caracteres: longa o bastante, sem deixar o resumo virar um peso para o servidor.
- **`FORMATO_DO_PIN`** = `re.compile('[0-9]{6}')`: Exatamente 6 números de 0 a 9.
- **`listar_sites`**: Devolve os sites que o usuário vê, por nome.
- **`obter_site`**: Devolve um site que o usuário vê.
- **`listar_docas`**: As docas de um site que o usuário vê, pelo nome.
- **`pessoas_do_site`**: As pessoas ativas de um papel ligadas a um site que o usuário vê, da mais antiga.
- **`nomes_das_faixas`**: Os nomes das faixas de um site que o usuário vê, por id.
- **`listar_cameras`**: Devolve as câmeras de um site que o usuário vê.
- **`CameraDaBorda`** (classe): O que a caixa precisa para ler o vídeo de uma câmera, com a senha decifrada.
- **`FaixaDaBorda`** (classe): Uma faixa do site, com as câmeras dela.
- **`faixas_para_a_borda`**: As faixas e câmeras de um site, para a caixa de borda dele ([[7.4 A caixa de borda|SDD 7.4]]).
- **`FaixaDoSite`** (classe): Uma faixa do site e os ids das câmeras dela, para conferir o que a caixa manda.
- **`estrutura_do_site`**: As faixas de um site (por id), com as câmeras de cada uma, sem senhas.
- **`HorarioDoSite`** (classe): O nome, o fuso e o horário de operação de um site (vazio = 24 horas).
- **`horario_do_site`**: O horário de um site, para o formulário do link da transportadora.
- **`obter_site_para_administracao`**: Um site de qualquer empresa. Só para a administração (as rotas dela conferem).
- **`criar_empresa`**: Cadastra um cliente. O CNPJ vai sem pontuação (14 caracteres).
- **`criar_site`**: Cadastra um site do cliente; sem ``abre`` nem ``fecha``, ele funciona 24 horas.
- **`criar_portaria`**: Cadastra uma portaria no site.
- **`criar_faixa`**: Cadastra uma faixa na portaria, de entrada ou de saída.
- **`criar_camera`**: Cadastra uma câmera na faixa, guardando a senha cifrada.
- **`criar_doca`**: Cadastra uma doca no site.
- **`criar_usuario`**: Cadastra um usuário do cliente e liga-o aos sites que ele vai ver.
- **`criar_administrador`**: Cadastra alguém da administração da plataforma (nós; SDD [[D-19]]).
- **`definir_senha`**: Troca a senha de um usuário ou administrador (guarda só o resumo).
- **`definir_pin`**: Define o PIN de um porteiro, usado na troca de porteiro no tablet (guarda só o resumo).
- **`listar_sites_para_administracao`**: Todos os sites, por empresa e nome. Só para a administração (as rotas dela conferem).
- **`listar_empresas`**: Todas as empresas, por nome. Só para a administração (as rotas dela conferem).

## Testes

- `nuvem/tests/test_nuvem_cadastro_camera.py`: Câmeras: a senha fica cifrada no banco; o endereço não leva usuário nem senha.
- `nuvem/tests/test_nuvem_cadastro_login.py`: Login ([[8.2 Segurança|SDD 8.2]], [[D-20]]): senha, sessão no banco, limite de tentativas e troca de porteiro.
- `nuvem/tests/test_nuvem_cadastro_rotas.py`: Rotas do cadastro com login de verdade: só dentro da empresa, só com o papel certo.
- `nuvem/tests/test_nuvem_cadastro_separacao.py`: Separação por empresa ([[5.5 Garantias|SDD 5.5]]): um cliente nunca vê dado de outro.
- `nuvem/tests/test_nuvem_cadastro_usuarios.py`: Usuários e administração: senha e PIN só como resumo, regras de tamanho e e-mail único.

---

Do [[Mapa do código]].

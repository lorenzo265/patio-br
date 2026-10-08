---
tipo: "tema"
escrita: "à mão"
atualizada: "2026-10-06"
tags: [tema]
---

# Separação de clientes e segurança

Uma empresa nunca vê o que é de outra, e quem não tem o papel certo não entra.

## O essencial

- **As garantias de [[5.5 Garantias]] valem para todo código da nuvem:** passagem repetida é
  ignorada; horário e foto não se editam (correção é um evento novo); nenhuma consulta sem
  filtro de empresa.
- **Na prática:** toda leitura de dado do cliente recebe o `Acesso` de quem pede
  ([[nuvem.cadastro]]); toda tabela de cliente tem `empresa_id`, e cada filha aponta para o pai
  pela dupla (pai, empresa), então o banco recusa misturar empresas. O que é de outra empresa
  responde "não encontrado".
- **Nas rotas:** `obter_acesso` (qualquer usuário do cliente) ou `exigir_papel(...)`; sem login,
  401; papel errado, 403 ([[2.1 Quem usa e o que pode fazer]]).
- **A administração (nós)** é outra tabela e outro tipo de acesso, e não usa as rotas do cliente
  ([[D-19]]). **A caixa de borda** se identifica pela chave e só lê e grava no site dela
  ([[nuvem.frota]]).
- **Senha, PIN, código de sessão e código de recuperação só como resumo** (argon2 para senha,
  PIN e código de recuperação), nunca o texto, nem em registro de erro ([[8.2 Segurança]]). A sessão fica no banco; o cookie leva só um código
  aleatório ([[D-20]]). Limite de 5 erros por e-mail a cada 15 minutos.
- **Links sem login** guardam só o resumo do código: o da transportadora ([[D-34]]) e o de
  demonstração por empresa, válido por 7 dias ([[D-52]]). A troca de papel sem senha do link de
  demonstração só existe nos ambientes da demonstração, dentro da mesma empresa ([[D-54]]).
- **A prova só se apaga na demonstração:** o banco deixa apagar evento, mudança de agendamento,
  conferência e extrato só de uma empresa que nasceu de um link de demonstração, e só quando a
  transação avisa qual empresa está apagando ([[D-54]], [[5.5 Garantias]]).
- **Antes da internet** (feito no mês 3, [[T47]] parte 1, [[8.2 Segurança]]):
  - **código anti-CSRF** tirado da sessão ([[D-55]]): todo formulário que muda alguma coisa leva
    o campo `_csrf`, o HTMX leva o cabeçalho `X-CSRF-Token`, e a nuvem recusa o pedido sem ele
    (403); só ficam de fora o login, o link da transportadora, o link de demonstração e a API da
    caixa;
  - **limite de login por endereço:** 20 erros a cada 15 minutos por endereço IP, além dos 5 por
    e-mail; atrás de proxy, o endereço vem só do cabeçalho configurado (`PATIO_CABECALHO_DO_IP`);
  - **o comando da administração:** `uv run python -m nuvem.administracao --nome ... --email ...`.
- **Verificação em duas etapas** ([[T51]], [[D-60]], [[8.2 Segurança]]): na homologação e na
  produção, o gestor e a administração entram com a senha e o código do app autenticador.
  - A senha certa abre uma sessão pela metade (10 minutos), que só serve para a tela do código.
  - Na primeira vez, a tela mostra o QR e, depois do primeiro código, 10 códigos de recuperação,
    uma vez só (guardados só como resumo argon2); o segredo do app fica cifrado.
  - Perdeu o celular: um código de recuperação; a administração zera a do gestor pela rota
    dela, e a própria pelo comando, com `--zerar-duas-etapas`.
- **Nenhum segredo no repositório:** o `.env` é ignorado; o `.env.exemplo` só tem valores de
  exemplo do ambiente local.

## Onde ler

- Regras: [[CLAUDE - regras do repositório]] (regras 4, 5 e 6), [[5.5 Garantias]],
  [[8.2 Segurança]].
- Decisões: [[D-19]], [[D-20]], [[D-21]], [[D-22]], [[D-28]], [[D-34]], [[D-52]], [[D-54]],
  [[D-55]], [[D-60]].
- Código: [[nuvem.cadastro]] (acesso, papéis, sessões), [[nuvem.frota]] (chave da caixa),
  [[Tabelas do banco]].
- Tarefas: [[T08]], [[T09]], [[T10]], [[T28]], [[T47]], [[T48]], [[T51]].

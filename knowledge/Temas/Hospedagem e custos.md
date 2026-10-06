---
tipo: "tema"
escrita: "à mão"
atualizada: "2026-10-06"
tags: [tema]
---

# Hospedagem e custos

Onde cada ambiente roda e quanto custa ([[7.1 Ambientes]]).

## O essencial

| Ambiente | Onde | Situação |
|---|---|---|
| Local | `uv run tarefas up` (Docker) ou PostgreSQL local | pronto |
| Demonstração | a API como função da Vercel; o banco e as fotos no Supabase, em São Paulo ([[D-51]]) | espera as contas ([[N17]], [[T47]]) |
| Homologação e produção | AWS São Paulo: Lightsail, RDS e S3 ([[D-11]], [[7.2 Nuvem (AWS, sa-east-1)]]) | mês 4 ([[T49]] e [[T50]]); confirmada pelo Lorenzo em 06/10 ([[D-57]]) |

- **Na Vercel não há processo que fica rodando:** o worker vira um **tique**; as telas que se
  atualizam sozinhas (portaria, pátio, mensagens e o dia de demonstração) rodam antes o que
  estiver pendente, um tique de cada vez, com a trava do PostgreSQL ([[D-51]], [[D-56]]).
- **O código está pronto** ([[T47]], parte 2, [[D-56]]):
  - as fotos vão para o Supabase Storage pela API S3 (o boto3, o mesmo que serve à AWS no mês 4);
  - o cron diário (`/api/cron/diaria`) apaga as empresas vencidas e confere o "não veio";
  - a API da caixa não existe no ambiente `demonstracao`;
  - o banco vai pelo pooler em modo sessão, sem pool na função e com SSL.
- **O passo a passo do deploy**, com todas as variáveis de ambiente e o que conferir no primeiro:
  [[Guia da demonstração na internet]]. Segredos só nas variáveis de ambiente da Vercel.
- **Planos (conferidos em 10/2026, decisão do Lorenzo ao abrir as contas):** a Vercel Hobby é só
  para uso pessoal, não comercial, e o Pro custa US$ 20 por mês por pessoa; o Supabase Free pausa
  o projeto depois de uma semana sem uso, e o Pro custa a partir de US$ 25 por mês.
- **A produção no mês 4** ([[Plano do mês 4]]): a `main` vai sozinha para a homologação e uma
  tag vai para a produção, com a aprovação do Lorenzo; cópia diária do banco, restauração de
  teste todo mês dentro da AWS e alarmes por e-mail ([[T49]], [[T50]]).
- **Custos do piloto** (1 site, preços de 2026-09-29): nuvem de US$ 60 a 80 por mês, Tailscale
  US$ 8, WhatsApp cerca de R$ 380 por site e hardware de R$ 15 a 22 mil por site, uma vez
  ([[7.6 Custos de operação (piloto, 1 site; preços de 2026-09-29)]]).

## Onde ler

- SDD: [[7.1 Ambientes]], [[7.2 Nuvem (AWS, sa-east-1)]], [[7.3 Do código à produção]],
  [[7.6 Custos de operação (piloto, 1 site; preços de 2026-09-29)]].
- Decisões: [[D-11]], [[D-13]], [[D-51]], [[D-56]], [[D-57]], [[D-61]].
- Tarefas: [[T04]], [[T47]], [[T49]], [[T50]]; contas: [[N2]], [[N17]], [[N21]].
- Fatos de preço e licença: [[Validação - fatos técnicos da stack]].

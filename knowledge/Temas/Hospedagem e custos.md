---
tipo: "tema"
escrita: "à mão"
atualizada: "2026-10-05"
tags: [tema]
---

# Hospedagem e custos

Onde cada ambiente roda e quanto custa ([[7.1 Ambientes]]).

## O essencial

| Ambiente | Onde | Situação |
|---|---|---|
| Local | `uv run tarefas up` (Docker) ou PostgreSQL local | pronto |
| Demonstração | a API como função da Vercel; o banco e as fotos no Supabase, em São Paulo ([[D-51]]) | espera as contas ([[N17]], [[T47]]) |
| Homologação e produção | AWS São Paulo: Lightsail, RDS e S3 ([[D-11]], [[7.2 Nuvem (AWS, sa-east-1)]]) | mês 4 |

- **Na Vercel não há processo que fica rodando:** o worker vira um **tique**; as telas, ao se
  atualizar, fazem a nuvem avançar o que estiver pendente, um tique de cada vez, com a trava do
  PostgreSQL ([[D-51]]). As fotos vão para o Supabase Storage, porque o disco da Vercel não fica.
- **Cuidados da [[T47]]:** o pooler do Supabase em modo transação não aceita prepared
  statements (conferir o pg8000 nele, ou usar o modo sessão); as empresas de demonstração
  vencidas são apagadas uma vez por dia (o cron da Vercel); segredos só nas variáveis de ambiente
  da Vercel.
- **Planos (conferidos em 10/2026, decisão do Lorenzo ao abrir as contas):** a Vercel Hobby é só
  para uso pessoal, não comercial, e o Pro custa US$ 20 por mês por pessoa; o Supabase Free pausa
  o projeto depois de uma semana sem uso, e o Pro custa a partir de US$ 25 por mês.
- **Custos do piloto** (1 site, preços de 2026-09-29): nuvem de US$ 60 a 80 por mês, Tailscale
  US$ 8, WhatsApp cerca de R$ 380 por site e hardware de R$ 15 a 22 mil por site, uma vez
  ([[7.6 Custos de operação (piloto, 1 site; preços de 2026-09-29)]]).

## Onde ler

- SDD: [[7.1 Ambientes]], [[7.2 Nuvem (AWS, sa-east-1)]], [[7.3 Do código à produção]],
  [[7.6 Custos de operação (piloto, 1 site; preços de 2026-09-29)]].
- Decisões: [[D-11]], [[D-13]], [[D-51]].
- Tarefas: [[T04]], [[T47]]; contas: [[N2]], [[N17]].
- Fatos de preço e licença: [[Validação - fatos técnicos da stack]].

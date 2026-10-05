---
tipo: "mapa"
escrita: "à mão"
atualizada: "2026-10-05"
tags: [pendencias]
---

# Pendências do Lorenzo

O que só o Lorenzo pode fazer ou decidir. O código não resolve nenhum item em aberto sem passar
por ele ([[0. Como usar este documento|SDD, seção 0]]).

> [!info] Retrato de 05/10/2026
> A situação dos itens da trilha não técnica não fica registrada no repositório: confira e
> atualize esta nota quando algum andar.

## Para a demonstração no ar (mês 3)

- [ ] **Abrir a sessão da identidade visual** ([[ABERTO-01]], E1): uma sessão nova do Claude
  Code neste repositório, com o texto do [[Prompt da identidade visual]]. Ela decide o nome, as
  cores e as fontes com você e já faz a [[T40]].
- [ ] **Consultar a marca no INPI e o domínio `.com.br`** antes de fechar o nome ([[N16]]).
- [ ] **Abrir as contas da Vercel e do Supabase** e escolher os planos ([[N17]], [[D-51]]):
  - a Vercel Hobby é só para uso pessoal, não comercial; para apresentar a empresas, o **Pro
    (US$ 20 por mês, por pessoa)**;
  - o Supabase Free pausa o projeto depois de uma semana sem uso; o **Pro (a partir de US$ 25
    por mês)** não pausa;
  - o acesso passa pelo cofre de segredos do ambiente, nunca pelo repositório.
- [ ] **Listar as empresas para apresentar** e marcar as conversas ([[N18]]).
- [ ] **Juntar os PRs abertos:** o [#47](https://github.com/lorenzo265/patio-br/pull/47) (decisões
  e prompt) e, depois dele, o deste vault.

## Com o advogado

- [ ] Modelo de contrato e acordo de tratamento de dados ([[ABERTO-07]]) e os prazos de guarda
  ([[ABERTO-04]]): [[N3]].
- [ ] As placas reais para a régua e o treino ([[ABERTO-18]]): gravar em portões de conhecidos,
  **fotografar placas na rua só com o sim dele**, o leitor comercial na nuvem ([[D-41]]) e a
  cláusula do treino no contrato ([[8.3 LGPD|SDD 8.3]]): [[N15]].

## Comercial e contas (da trilha dos meses 1 e 2)

- [ ] Verificação da empresa na Meta e o app da Cloud API do WhatsApp ([[N1]]), para o mês 4.
- [ ] Conta da AWS com alerta de gasto ([[N2]]), para a produção do piloto ([[D-11]]).
- [ ] Roteiro e as 15 a 25 conversas ([[N5]]); a oferta de piloto anual pré-pago ([[N12]]); o
  preço do piloto ([[ABERTO-06]]).
- [ ] Hardware da bancada ([[N7]]) para medir o leitor no mini PC N150 ([[T20]]).
- [ ] O site parceiro ([[N6]]) e o guia de posicionamento das câmeras ([[N8]], [[ABERTO-08]]),
  que ficaram para depois; a instalação ([[N9]]) e o registro manual ([[N13]]) foram adiados em
  05/10.
- [ ] As contas de GPU para o treino e, se o advogado permitir, do leitor comercial ([[N11]]).
- [x] Quem rotula as placas: o Lorenzo ([[N10]]).

## Decisões que esperam dados ou o cliente

| Item | Espera |
|---|---|
| [[ABERTO-02]] pesos e limite do casamento | os dados rotulados |
| [[ABERTO-03]] o detector (D-FINE-N ou YOLOX-Tiny) | o teste técnico no N150 |
| [[ABERTO-05]] como medir as horas de portaria | o cliente do piloto |
| [[ABERTO-09]] tolerância de janela e momento do alerta | o cliente do piloto |
| [[ABERTO-10]] dados do modo B | a Fase 2 |
| [[ABERTO-19]] e [[ABERTO-20]] recebimento e estoque | o piloto aprovado ([[D-43]]) |

A lista completa, com como e quando decidir: [[12. Itens em aberto]].

---
tipo: "documento"
fonte: "docs/validacao/relatorio-validacao-v3.md"
gerada: true
tags: [documento]
---

> [!note] Gerada de `docs/validacao/relatorio-validacao-v3.md` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# VALIDAÇÃO — Tese v3: pátio com check-in automático, extrato de economia e hardware barato · 2026-09-29

**Pergunta neutralizada:** existe demanda paga sustentável, no Brasil, por um sistema de pátio com
check-in sem aplicativo, extrato de economia realizada e captura sobre hardware barato, para sites
de médio e alto volume, nos dois modos de operação (motorista espera com o caminhão; carreta
solta no pátio)?

**Base rate declarada:** prior de 20-30% para tese de mesa deste tipo. A v3 foi montada com os
sobreviventes de dois kill baratos, o que reduz o risco de premissa já testada, mas não o das novas.

**Kill barato v3:** V1 meia queda (reusar o CFTV existente não foi demonstrado; câmera IP comum de
~R$ 881 + modelo próprio sobrevive); V2 não caiu (compatível sem biometria facial; portos e
recintos exigem integração ao credenciamento; NF-e com certificado do cliente); V3 não caiu
(WhatsApp ~86% em 2018; R$ 0,035 por mensagem utility).

**Dossiês:** C1-C3, D1-D3, KA-KC, V1-V3, M, A (15 dossiês, 79 fatos em fatos.json).
**Memorandos:** a favor e contra, escritos isolados, sem acesso a julgamentos anteriores.

**Citações críticas conferidas pelo juiz:**
- ABESE: mais de 14 mil condomínios com portaria remota, custo 40-60% menor (confirmado; associação interessada).
- RodoSol: "academic research only ... non-commercial purposes"; sem categoria de reboque (confirmado).
- Opendock BR: câmera no gate, ativos em tempo real, layout de pátio, comunicação bidirecional com motorista; nenhum cliente BR (confirmado).
- TOTVS YMS: self check-in em totem ou tablet sem pessoa na portaria, com agendamento, e aviso por SMS ou WhatsApp (confirmado em páginas da TOTVS via busca).
- Laroca et al. 2026 existe e declara superar sistemas comerciais; os números por tipo de placa vêm da extração do PDF pelo pesquisador (não reconferidos pelo juiz).
- Fonte oHub (portaria remota até ~80 caminhões/dia): usada pelos dois lados em sentidos opostos, Tier 3 e declarada gerada por IA → descartada por falta de diagnosticidade.
- Acórdão TJSP (estadia improcedente por falta de prova): não reconferido; é de duplo sentido, pois hoje a falta de registro beneficia o recebedor.

**Observação do juiz sobre a conta de acerto:** o memorando contra calcula 85,7-91,3% de
composições certas como leitura aberta (0,95³). Com o agendamento do dia como lista de
candidatos, a identificação vira casamento com poucas placas esperadas, e o acerto efetivo tende a
ser maior. As exceções vão para uma fila humana, não quebram o sistema. O acerto decide quantas
horas-posto somem, não se o produto funciona. Não há medição brasileira (V1-44): é teste, não fato.

## Veredito por dimensão

```
DIMENSÃO: 1 Problema
NÍVEL: PROVÁVEL (65–90%) · pontual ~70%
CONFIANÇA NA EVIDÊNCIA: MÉDIA
A FAVOR: C2-15/16/17, M-19..22 (T2, espera 5h09 e 11h40 em CD); D1-01..03, D1-11/12 (T1, portaria
         24x7 R$ 21,5-36,9 mil/mês; tarefa = ler DANFE e triagem); KB-10..24 (T1, fricção do motorista
         com apps); f-NOVO-A3-01 (T2, comprador BR já troca porteiro por tecnologia em condomínios)
CONTRA: C2-05/10/13/14 (o custo da espera fica com o transportador); C2 N3 (nenhuma cifra do custo
        do site além da portaria); M-26/27 (modo carreta solta sem cifra no Brasil)
POR MODO: A (espera) tem cifra na portaria e métricas de espera; B (carreta solta) tem existência
        documentada (M-05..17) e nenhuma cifra.
MUDARIA O NÍVEL: ↑ se entrevistas trouxerem R$ de doca ociosa e horas extras; ↓ se o site não
        reconhecer a espera como custo próprio
```

```
DIMENSÃO: 2 Comprador e orçamento   [dimensão-trava]
NÍVEL: INCERTO (35–65%) · pontual ~42% — por evidência conflitante
CONFIANÇA NA EVIDÊNCIA: BAIXA
A FAVOR: D1-01..03, D1-11/12 (T1, a linha de portaria é paga e tem preço); f-NOVO-A3-01 (T2,
         substituição de porteiro por tecnologia é comportamento revelado no Brasil); KB-26
         (agendamento "maduro, falta adoção": há não-consumo)
CONTRA: C2-05 (a estadia raramente vira caixa: 3 das 4 linhas do extrato não são dinheiro do site);
        TOTVS self check-in + WhatsApp, Senior LPR + dashboards, Loadsmart gate CV + ativos + layout
        (confirmados): incumbentes cobrem 2 dos 3 pilares; KA-17 (CV é licenciável: EAIGLE para
        C3/FourKites); KB-29 (integração é o obstáculo nº 1, favorece quem já tem o agendamento)
FEATURE-VS-EMPRESA: (a) orçamento próprio: sim, na linha de portaria; (b) quem compra sofre: sim na
        portaria, não na espera; (c) se o incumbente lançar como aba: resposta parcialmente
        específica — identificação automática de composições brasileiras (motores genéricos 48-69%,
        modelo treinado 94-97%, sem dataset comercial disponível) e extrato de economia (ninguém
        oferece); ambas copiáveis em 12-24 meses; (d) adjacências: existem, com donos.
MUDARIA O NÍVEL: ↑ se ≥3 pilotos pagos anuais a ≥R$ 8 mil/site; ↓ para IMPROVÁVEL (trava) se o teto
        de preço aceito for ≤R$ 4 mil/site
```

```
DIMENSÃO: 3 Solução vs alternativas
NÍVEL: INCERTO (35–65%) · pontual ~50% — por ausência de evidência
CONFIANÇA NA EVIDÊNCIA: BAIXA
A FAVOR: KC-48, A-40/41 (nenhum fornecedor mede economia realizada no produto); C1-N01/N03/N04,
         KC-49 (nenhuma CV de pátio com cliente BR); V1-21..23 (motores genéricos falham na placa
         brasileira); V2-39 (nenhuma norma obriga consulta de motorista na portaria de CD privado)
CONTRA: TOTVS totem sem portaria e Loadsmart SmartGate (confirmados): o "sem app" já existe como
        totem/QR; V1-06/07/08 (câmera de monitoramento não serve para LPR: hardware novo, embora
        barato); RodoSol não comercial (confirmado): modelo exige dataset próprio; V1-29/30, V1-44
        (placa traseira de reboque, acerto não medido no BR); modo B: abordagem dos EUA lê número de
        trailer, no BR só há placa traseira (f-NOVO-C3-06)
MUDARIA O NÍVEL: ↑ se o bake-off medir ≥95% de composições certas casando com o agendamento;
        ↓ se ficar <90%
```

```
DIMENSÃO: 4 Economia unitária   [dimensão-trava]
NÍVEL: INCERTO (35–65%) · pontual ~50% — era IMPROVÁVEL (~30%) no v-2026-0001; trava removida
CONFIANÇA NA EVIDÊNCIA: BAIXA
A FAVOR: capex do modo A de R$ 10-50 mil por site (V1-33/34, D1-04, A-30/31), 3 a 15 vezes abaixo dos
         R$ 157-237 mil anteriores; os dois memorandos convergem em margem bruta de 56-76% a
         R$ 8 mil/mês; edge amortizado (~R$ 250/mês) contra nuvem GPU em SP (~R$ 3,5 mil/mês, A-27);
         WhatsApp ~R$ 0,10 por visita (V3-23/29); conectividade R$ 150-250/mês (A-33/34)
CONTRA: preço de R$ 8 mil não tem âncora; as âncoras observáveis estão em R$ 2,7-4,9 mil (D3-07 T3,
        C3-17, D1-23), e a R$ 3 mil a margem vai a 36% ou negativa; implantação de R$ 36-68 mil
        por site (integração ERP/NF-e); equipe fixa de R$ 2,3-3,4 mi/ano → break-even de 36-64 sites
        a R$ 8 mil; modo B soma R$ 12-28 mil por veículo de manobra e não tem linha de valor com cifra
SENSIBILIDADE: entre R$ 3 e 8 mil por site/mês, a margem vai de -17% a 76%. A dimensão depende de
        uma coisa: o cliente reduz horas-posto de portaria o bastante para aceitar R$ 8 mil?
MUDARIA O NÍVEL: ↑ para PROVÁVEL se ≥2 sites reduzirem ≥1 ponto 24x7 (ou ≥40% das horas-posto) em
        90 dias; ↓ para IMPROVÁVEL se o preço aceito ficar ≤R$ 4 mil
```

```
DIMENSÃO: 5 Distribuição
NÍVEL: INCERTO (35–65%) · pontual ~40% — por ausência de evidência
CONFIANÇA NA EVIDÊNCIA: BAIXA
A FAVOR: D2-02..18 (T1, contas com endereço e muitos sites por conta); D2-43 (nenhum dono de
         condomínio oferece tecnologia de pátio: canal livre); D2-36 (seniorX, ISV TOTVS);
         D3-04 (o comparável planeja por conversão de base)
CONTRA: K1 exige ~174 sites a R$ 8 mil (os dois memorandos concordam), 8-15% de 1.200-2.200 sites
        qualificados (premissa; D2-40 não permite filtrar por volume); comparáveis dos EUA com
        US$ 12-17 mi chegaram a ~30 sites ou clientes (KA-01, KA-12/13, V1-15/16); Loblaw: 1 site ao
        vivo de 26 (KA-16); taxas de funil sem comparável brasileiro
MUDARIA O NÍVEL: ↑ se uma conta multi-site assinar expansão após o piloto; ↓ se o ciclo do piloto
        passar de 6 meses
```

```
DIMENSÃO: 6 Moat e timing
NÍVEL: IMPROVÁVEL (10–35%) · pontual ~30% (era ~25%)
CONFIANÇA NA EVIDÊNCIA: MÉDIA
A FAVOR: dataset próprio de composições brasileiras (RodoSol não comercial, sem reboque; V1-44 sem
         medição pública) como recurso acumulado; extrato de economia sem equivalente (KC-48); desenho
         sem biometria é o de menor risco enquanto a ANPD não regulamenta (D3-31..36)
CONTRA: TOTVS, Senior, Loadsmart e nstech cobrem 2 de 3 pilares (confirmados); CV licenciável
        (KA-17); DT-e adiado, sem gatilho regulatório (D3-23..26); 2026 trouxe concorrentes
        (Loadsmart, Kaleris CV)
MUDARIA O NÍVEL: ↑ se o dataset próprio sustentar vantagem de acerto medida contra um motor genérico
        em bake-off; ↓ se um incumbente anunciar reconhecimento de composição + relatório de economia
```

**4 de 6 dimensões saíram INCERTO (67%).** Pela régua da skill, é sinal de análise prematura: a
pesquisa de mesa se esgotou nesta tese. As incertezas restantes (preço aceito, redução de posto,
acerto em composições brasileiras) só se resolvem com comprador e com piloto.

## Travas ativas

Nenhuma formal: Economia saiu de IMPROVÁVEL para INCERTO (~50%), e Comprador está em INCERTO
(~42%). As duas continuam no limite, e as condições de volta à trava estão escritas acima
(preço ≤R$ 4 mil; nenhum piloto pago).

## O que a evidência sustenta / derruba / deixa em aberto

**Sustenta**
- O custo de hardware deixou de ser trava: R$ 10-50 mil por site no modo espera.
- A fricção do motorista com apps é real e documentada em lojas de apps (T1).
- Ninguém mede economia realizada dentro do produto, em logística, no Brasil ou fora.
- O desenho sem biometria é compatível com a LGPD, e nenhuma norma obriga consulta de motorista na
  portaria de CD privado.
- Os dois modos de operação existem no Brasil.

**Derruba**
- "Sem aplicativo" como novidade: a TOTVS já faz check-in por totem sem pessoa na portaria, com
  SMS/WhatsApp. O que resta de novo é a identificação sem nenhuma ação do motorista.
- Reusar o CFTV existente como regra: câmera de monitoramento não serve para leitura de placa.
- Usar dataset público brasileiro em produto comercial: o RodoSol é só acadêmico.
- Transferir direto o modo "carreta solta" dos EUA: lá se lê o número do trailer; aqui só há placa
  traseira.

**Em aberto**
- Preço aceito (R$ 3 mil ou R$ 8 mil muda tudo).
- Se o site reduz horas-posto de portaria, e quanto.
- Acerto de composições brasileiras casando com o agendamento.
- Se o extrato de economia retém cliente no Brasil.
- Participação de cada modo por contratante.

## Hipóteses rivais

| id | Hipótese | p (v-0001) | p (v3) |
|---|---|---|---|
| H1 | Tese válida: empresa nova independente | 15% | 20% |
| H2 | Ganho vem de software sem CV; diferencial não pago | 25% | 20% |
| H3 | Vira módulo de incumbente (saída por aquisição no máximo) | 25% | 25% |
| H4 | Só fecha em nichos 24x7 de alto volume; abaixo do K1 ou modelo de serviço | 25% | 25% |
| H5 | Tese certa, timing cedo | 10% | 10% |

H1 subiu porque a trava de hardware caiu e as lacunas (extrato, CV de pátio no BR, fricção do
motorista) foram verificadas. H3 e H4 continuam empatadas com H1 ou acima.

## Cenários

- **Bull (20%)**: bake-off ≥95%; 3+ contas pagam ≥R$ 8 mil/site; horas-posto caem; K1 em ~4 anos
  ou aquisição por nstech/TOTVS/Loadsmart com dataset e base como ativo.
- **Base (45%)**: preço aceito em R$ 4-6 mil; negócio de R$ 5-10 mi de ARR em portarias de alto
  volume (modo A), com o modo B em poucas contas dedicadas; saída por aquisição.
- **Bear (35%)**: o incumbente do ERP entrega "bom o suficiente" (totem + LPR + dashboard); pilotos
  não convertem.

## Recomendação sobre os dois modos

A arquitetura deve nascer pronta para os dois modos: o mesmo modelo de eventos (chegada,
identificação, posição, doca, saída) com captura diferente (câmeras fixas na portaria e nas docas
no modo A; câmera em veículo de manobra + posicionamento no modo B). O produto a construir e vender
primeiro é o modo A, porque é o que tem cifra (portaria) e métrica (espera). O modo B entra quando
um contratante com operação de carreta solta pagar pelo piloto, porque hoje não há cifra
brasileira que o sustente e ele pede hardware por veículo.

## Gatilhos de reversão

- Até 31/03/2027: bake-off com ≥1.000 composições acerta ≥95% casando com o agendamento → Solução
  sobe para PROVÁVEL.
- Até 31/03/2027: ≥3 pilotos pagos (≥2 anuais pré-pagos) a ≥R$ 8 mil/site → Comprador e Economia
  sobem para PROVÁVEL.
- A qualquer momento: teto de preço aceito ≤R$ 4 mil em ≥5 conversas qualificadas → Economia volta a
  IMPROVÁVEL (trava).
- Até 30/06/2027: TOTVS, Senior, nstech ou Loadsmart anunciam reconhecimento automático de
  composição + relatório de economia realizada → Moat cai; H3 sobe.

## Sensibilidade

As três evidências que mais pesam:
1. Preço aceito por site. Se R$ 8 mil estiver errado para baixo, Economia volta a trava.
2. Redução de horas-posto. É a única linha de caixa T1; sem ela o extrato mede dinheiro que o site
   não gasta.
3. Acerto de composições brasileiras. Define quantas exceções sobram para um humano.

## Pre-mortem (execução)

Em 12 meses falhou porque:
- o time tentou os dois modos ao mesmo tempo e não terminou nenhum;
- a coleta de dados para treinar o modelo foi lenta, porque cada site exigiu aviso LGPD e acordo
  de dados;
- o piloto provou acerto, mas o contrato de portaria terceirizada tinha multa de rescisão e o
  cliente não cortou horas-posto no primeiro ano;
- a TOTVS acrescentou LPR ao totem e o cliente "já tinha isso no ERP".

## Pre-parade (upside)

Em 3-5 anos deu certo porque:
- o dataset de composições brasileiras (cavalo, reboques, placa antiga e Mercosul, placa suja) virou
  o melhor do país e foi licenciado para YMS e gerenciadoras;
- o extrato de economia virou o documento que o CFO leva à renovação do contrato de portaria;
- a empresa começou pelo modo A em 3 contas multi-site e abriu o modo B com uma operação dedicada
  (bebidas ou varejo alimentar), onde manobristas e cavalos de manobra já existem;
- foi comprada por um consolidador com o dataset e a base como ativo.

## Próximo teste (Test Card v3)

- **Hipótese:** operadores de sites com ≥80 caminhões/dia e portaria 24x7 aceitam ≥R$ 8 mil/mês por
  site, em piloto anual pré-pago, por check-in automático + extrato mensal de economia; e o sistema
  acerta ≥95% das composições casando com o agendamento, reduzindo ≥1 ponto 24x7 (ou ≥40% das
  horas-posto) em 90 dias.
- **Experimento (em paralelo):**
  1. **Bake-off técnico barato:** 6 câmeras IP comuns (~R$ 5 mil) + 1 edge numa portaria cedida,
     2 semanas, ≥1.000 composições, conferidas contra NF-e/CT-e e agendamento; aviso LGPD, sem
     biometria facial, guarda curta. Mede acerto aberto e acerto casando com o agendamento.
  2. **Conversas Mom Test:** 15-25 com gerentes de operação, de segurança e controladoria de CDs
     multi-site; só fatos passados (quantos postos, quanto custam, contrato de portaria, multas);
     toda conversa termina com oferta real de piloto anual pré-pago a preço de lista.
  3. **Modo B (descoberta):** 3-5 conversas com operações de carreta solta (bebidas, varejo
     alimentar, refrigerados; ver M-05..13) para saber quantas carretas, quantos manobristas e
     quanto tempo se perde procurando carreta.
  4. **Seguro:** 3 seguradoras ou gerenciadoras respondem se reduzir o posto noturno mantém prêmio e
     cobertura.
- **Thresholds (fixados antes dos dados):**
  - GO: ≥3 pilotos pagos a ≥R$ 8 mil (≥2 anuais pré-pagos) e acerto ≥95% e ≥1 site reduzindo posto
    em 90 dias.
  - ITERAR 1x: preço aceito entre R$ 4 e 8 mil, ou acerto entre 90 e 95%.
  - KILL: 0 pilotos pagos em 25 conversas qualificadas; ou acerto <90% mesmo casando com o
    agendamento; ou teto de preço ≤R$ 4 mil.
- **Escada de evidência:** mínimo de 2 degraus com dinheiro (depósito, pedido pago) antes de
  construir o produto completo; anual pré-pago vale mais que mensal.

## Registrado em vereditos.json: v-2026-0003

---
tipo: "documento"
fonte: "docs/validacao/recebimento-e-estoque.md"
gerada: true
tags: [documento]
---

> [!note] Gerada de `docs/validacao/recebimento-e-estoque.md` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Recebimento e estoque: evidências (pesquisa de 2026-10-05)

Pergunta: vale levar o produto do "quem chega" para o "o que chega" e para o estoque (SDD
[[D-43]], [[ABERTO-19]] e [[ABERTO-20]])? Só pesquisa na web. "Conferido" marca o que foi relido na
fonte em 05/10; "[inferência]" marca uma conta nossa; "não confirmado", o que ficou sem fonte
primária.

## A dor, com números

- **Tempo de descarga na Grande SP em 2025:** 5h09 em média (4h08 em 2024). Supermercados
  3h05, atacadistas 5h56, CDs 11h40. Só 13% dos locais têm vaga de carga e descarga. Causas
  citadas: poucas docas, janelas de agenda, falta de conferentes e burocracia.
  https://setcesp.org.br/noticias/a-demora-que-compromete-a-eficiencia/
- **Perdas dos supermercados em 2023:** 1,87% do faturamento (cerca de R$ 14 bi). O desvio
  operacional é 28% das perdas, e o fornecedor responde por 16% dele. Erros de inventário são
  51% das perdas administrativas, e 41% das empresas fazem inventário uma vez por ano (ABRAS e
  APRAS). [inferência] A parte do fornecedor dá cerca de 0,08% do faturamento, perto de
  R$ 0,6 bi por ano.
  https://static.abras.com.br/pdf/eficiencia-operacional-abras-em-acao-apras-13072024.pdf
- **Conferente de mercadoria:** salário médio de R$ 2.158; custo para a empresa perto de
  R$ 3.669 por mês.
  https://www.salario.com.br/profissao/conferente-de-mercadoria-cbo-414105/
- **Ruptura de gôndola:** 11,2% em novembro de 2025 (índice Neogrid).
- **Divergência de quantidade:** quem recebe menos do que a NF diz lança o que recebeu e avisa
  o fornecedor por escrito (SEFAZ-SP, Resposta à Consulta 21673/2020).
  https://legislacao.fazenda.sp.gov.br/Paginas/RC21673_2020.aspx
- Não achamos o percentual de entregas com divergência no Brasil.

## Supermercados que conferem a NF no agendamento

- **Muffato** (conferido): com o sistema de pátio da Tempo Certo, passou de 80 para 120
  entregas por dia, e o tempo médio por veículo caiu de 5 para 2 horas. "Ao agendar, o
  fornecedor já envia antecipadamente a nota fiscal do produto, que pode ser conferida
  previamente." https://mundologistica.com.br/noticias/muffatto-aumenta-em-50-volume-diario-de-entrega
- **Koch** (Tempo Certo): o CD recebe 80% do volume, com 160 veículos por dia; a agenda antes
  era planilha. https://portalerp.com/br/noticia/grupo-koch-implanta-solucao-da-tempo-certo-para-automatizar-gestao-de-patio
- **Bistek** (TOTVS Fluig e RMS, 2016): 676 fornecedores, cerca de 2.000 agendamentos por mês,
  capacidade 10% maior.

## Quem já faz

| Fornecedor | O que tem | Preço |
|---|---|---|
| TOTVS (com Consinco e Linx) | WMS com conferência de recebimento; YMS "Porteiro" com agenda, check-in e documentos. Leitura de placa: não confirmado | não publica |
| Senior | WMS e YMS; o YMS confere a NF contra a ordem de recebimento e pode barrar o caminhão | não publica |
| Neogrid e eSales | agendamento de docas, portaria e pátio para o varejo (desde 2024) | não publica |
| Tempo Certo (NGTechno) | sistema de pátio com a NF mandada antes da entrega | não confirmado |
| Trackage | sistema de pátio **com leitura de placa** (caso Braskem) | não publica |
| Alterdata | "conferência cega de entrada", com a NF pelo XML ou pela chave | não publica |
| Qive, nsdocs | captura do XML na SEFAZ com o certificado do cliente | a partir de R$ 30 a R$ 153 por mês |

Nenhum WMS por assinatura brasileiro com preço publicado foi encontrado.

## Os itens da NF-e

- **Só a chave:** a consulta pública confirma a nota, mas não traz os itens, e tem captcha
  (robôs são barrados desde 2019).
- **Certificado digital do destinatário (A1 ou A3) e Distribuição DF-e:** antes da
  manifestação vem só um resumo; depois da "Ciência da Operação" vem o XML completo. Vale para
  notas de até 90 dias. O certificado precisa ser da mesma raiz de CNPJ (NT 2014.002 v1.40).
  Guardar o certificado do cliente é um peso de segurança.
- **Transportador ou CNPJ autorizado na nota (tag `autXML`):** XML completo, sem manifestação.
- **O fornecedor:** é obrigado a mandar ou disponibilizar o XML ao destinatário (Ajuste SINIEF
  07/05). É o caminho de Muffato e Bistek: o XML vem com o agendamento.
- **Bibliotecas Python:** `nfelib` (MIT, conferido) e `erpbrasil.edoc` (MIT, conferido;
  Distribuição DF-e e manifestação). As dependências de cada uma ainda precisam de conferência.
  Ficam de fora pela regra de licença: PyNFe (LGPL), PyTrustNFe (LGPL) e BrazilFiscalReport
  (LGPL e AGPL).
- **Certificado e-CNPJ A1 de 1 ano:** cerca de R$ 220 a R$ 235.

## Quem compra e onde

- Nos casos de supermercado, quem compra é o gerente ou executivo de suprimentos, ou a
  diretoria de TI. Todos os casos estão integrados ao ERP ou ao WMS.
- **As grandes redes recebem no CD, não na loja:** a Havan abastece cerca de 200 lojas a partir
  de um CD, e o Koch passa 80% do volume pelo CD. [inferência] O recebimento cabe primeiro nos
  CDs, que já são o alvo do pátio ([[1.3 Para quem|SDD 1.3]]); as lojas vêm depois.

## Onde cabemos e os riscos

- **Onde cabemos** [inferência]: entre a portaria e o ERP. Conferir a NF antes de o caminhão
  chegar, contar às cegas no tablet contra o XML, mandar o aviso de divergência ao fornecedor e
  exportar o resultado para o ERP, sem lançar a nota.
- **Riscos:**
  - TOTVS, Senior, Neogrid e Tempo Certo já fazem agenda com conferência;
  - comparar a NF com o pedido exige o pedido e o cadastro de produtos do ERP do cliente;
  - a loja é diferente do CD;
  - guardar o certificado do cliente é um peso de segurança.

## Três caminhos, do menor para o maior

1. **A NF no agendamento:** o fornecedor manda o XML ao agendar (pelo link ou pela planilha), e
   a portaria vê os problemas antes de o caminhão chegar. Aproveita o agendamento que já
   existe. A obrigação legal de mandar o XML é do fornecedor.
2. **Conferência cega no tablet e aviso de divergência ao fornecedor:** a nota diz o que deveria
   vir, e o conferente conta sem ver a nota. O fornecedor responde por 16% do desvio
   operacional; mas os WMS já têm conferência cega, e não há taxa pública de divergência para
   provar o retorno.
3. **Estoque e endereços, com busca e visão 3D:** território dos WMS (TOTVS, Senior, SAP), com
   integração pesada. As grandes redes já automatizam o CD.

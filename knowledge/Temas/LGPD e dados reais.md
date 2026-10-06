---
tipo: "tema"
escrita: "à mão"
atualizada: "2026-10-05"
tags: [tema]
---

# LGPD e dados reais

O cliente é o controlador dos dados; nós somos o operador ([[8.3 LGPD]]).

## O essencial

- **Sem reconhecimento facial**, em nenhuma fase ([[D-15]]). Foto guardada é recorte de placa e
  de veículo; rostos nas fotos de contexto são borrados na própria caixa.
- **A base de treino guarda só recortes de placa e a região de gravação** das câmeras, abaixo do
  para-brisa ([[D-39]]), nunca rostos. A conferência do porteiro só vira rótulo se o contrato do
  cliente autorizar ([[D-42]], [[8.3 LGPD]]): a administração registra a data da cláusula, e
  revogar apaga os rótulos e os recortes daquela empresa ([[D-71]], [[T60]]).
- **O que um leitor comercial lê nunca vira rótulo**, e mandar imagens à nuvem dele só com o sim
  do advogado e do site ([[D-41]]).
- **Base legal:** câmera e placa por legítimo interesse; WhatsApp só com a autorização do
  motorista ([[8.3 LGPD]], [[D-47]]).
- **Guarda** (a validar com o advogado, [[ABERTO-04]]): fotos 90 dias, visitas e trilha de prova
  5 anos. Contrato e acordo de tratamento de dados: [[ABERTO-07]]. Os prazos são parâmetros
  ([[D-70]], [[T59]]): o worker apaga a foto vencida, menos a de visita com exceção aberta ou em
  disputa, e a prova guarda o resumo dela; a disputa é marcada pelo gestor na página da prova.
- **O pedido do titular** ([[D-70]]): a administração levanta tudo o que existe de uma placa ou
  de um celular numa empresa, e o cliente (o controlador) responde ao titular.
- **Dado real nunca entra no Git:** vídeos, fotos, placas, nomes e telefones reais ficam em
  `dados/`; pesos em `modelos/`; as duas pastas são ignoradas. Testes e demonstração usam dados
  inventados; os celulares da demonstração usam o DDD 23, que não existe ([[D-49]]).
- **As placas reais** para a régua e o treino ainda não têm fonte ([[ABERTO-18]]): portões de
  conhecidos ou fotos na rua, só com o sim do advogado ([[N15]]).

## Onde ler

- Regras: [[CLAUDE - regras do repositório]] (regras 2 e 3), [[8.3 LGPD]], [[4.6 Dados de treino]].
- Pesquisa das fontes de placas: [[Validação - fontes de placas]].
- Decisões: [[D-15]], [[D-39]], [[D-41]], [[D-42]], [[D-44]], [[D-47]], [[D-49]].
- Itens: [[ABERTO-04]], [[ABERTO-07]], [[ABERTO-18]]; já fechado: [[ABERTO-15]].
- Com o advogado: [[N3]] e [[N15]].

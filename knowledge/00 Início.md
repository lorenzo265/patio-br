---
tipo: "mapa"
escrita: "à mão"
atualizada: "2026-10-05"
tags: [inicio]
---

# patio-br: o mapa do projeto

Este vault do Obsidian junta **toda a documentação do patio-br** num lugar só, com ligações
entre as partes: o SDD dividido em seções, cada decisão, cada item em aberto, cada tarefa dos
planos, os outros documentos e um mapa do código.

> [!tip] Como abrir
> No Obsidian, "Abrir pasta como vault" e escolha a pasta `knowledge/` do repositório. Fora do
> Obsidian, as notas são Markdown comum: dá para ler no GitHub ou em qualquer editor.

## O projeto em um minuto

- **O quê:** sistema de pátio para centros de distribuição, indústrias e terminais. A câmera da
  portaria lê a placa, o caminhão entra na fila sem aplicativo, o motorista é avisado pelo
  WhatsApp e o gestor recebe um extrato mensal da economia em R$ ([[1.2 A proposta]]).
- **O problema:** o caminhão espera horas para carregar ou descarregar, a portaria custa de
  R$ 21,5 mil a R$ 36,9 mil por mês por ponto 24 horas, e ninguém entrega ao cliente a economia
  medida dentro do produto ([[1.1 O problema]]).
- **Para quem:** sites com portaria 24 horas e cerca de 80 caminhões por dia ou mais
  ([[1.3 Para quem]]).
- **Como:** uma caixa de borda (mini PC na portaria) lê as placas; a nuvem decide ([[D-03]],
  [[3.1 Visão geral]]).
- **O que o piloto precisa provar:** 95% das composições certas, 70% das chegadas sem o
  porteiro, menos horas de portaria e R$ 8 mil por mês por site
  ([[1.5 O que o piloto precisa provar]]).
- **Agora:** o mês 3 é a demonstração comercial na internet ([[D-45]], [[Plano do mês 3]]). O
  que já está pronto e o que falta: [[Estado atual]].

## Por onde começar

| Se você quer... | Leia |
|---|---|
| as regras que não se negociam | [[CLAUDE - regras do repositório]] |
| o que construir e por quê (a fonte da verdade) | [[SDD]] |
| o que já foi feito e o que falta | [[Estado atual]] |
| o que depende do Lorenzo | [[Pendências do Lorenzo]] |
| o plano do mês | [[Plano do mês 3]] (os anteriores: [[Plano do mês 1]] e [[Plano do mês 2]]) |
| todas as decisões, com o motivo | [[11. Registro de decisões]] |
| o que ainda não foi decidido | [[12. Itens em aberto]] |
| os termos do projeto | [[13. Glossário]] |
| onde está cada coisa no código | [[Mapa do código]] |
| instalar e rodar | [[README]] e [[Comandos]] |
| a identidade visual (sessão à parte) | [[Prompt da identidade visual]] |

## Os temas

Cada tema junta o essencial e liga às seções do SDD, às decisões, às tarefas e ao código.

- [[Licenças]]: o que pode entrar no produto, e o que nunca entra.
- [[LGPD e dados reais]]: rostos, placas, guarda e o que nunca vai para o Git.
- [[Separação de clientes e segurança]]: empresa, papéis, sessões e links.
- [[Leitor de placas e caixa de borda]]: a câmera, a caixa, os modelos e o treino.
- [[Agendamento, portaria e casamento]]: do agendamento à chegada, com as exceções.
- [[Pátio, docas e mensagens]]: fila, chamada, doca e os avisos ao motorista.
- [[Extrato e números]]: as contas do extrato em R$ e os indicadores.
- [[Demonstração comercial]]: a empresa de demonstração, o dia ao vivo e o link.
- [[Hospedagem e custos]]: onde cada ambiente roda e quanto custa.
- [[Identidade visual]]: o nome, as cores e as fontes, ainda por decidir.
- [[Depois do piloto]]: recebimento, estoque e o que vem nas próximas fases.

## As pastas

| Pasta | O que tem | Quem escreve |
|---|---|---|
| `SDD/` | o SDD, uma nota por seção; [[SDD]] é o índice | o gerador |
| `Decisões/` | uma nota por decisão (D-nn), com o motivo e a alternativa descartada | o gerador |
| `Itens em aberto/` | uma nota por item (ABERTO-nn), aberto ou já fechado | o gerador |
| `Planos/` | o plano de cada mês, com a lista das tarefas | o gerador |
| `Tarefas/` | uma nota por tarefa dos planos (Tnn) | o gerador |
| `Trilha não técnica/` | o comercial e a burocracia (Nnn) | o gerador |
| `Documentos/` | README, CLAUDE.md, guias, validações, o prompt e os avisos de terceiros | o gerador |
| `Código/` | pacotes, rotas, tabelas, migrações, telas e comandos | o gerador |
| `Anexos/` | as imagens citadas nos documentos | o gerador |
| `Temas/` e a raiz | os mapas e os resumos, como esta nota | à mão |

As notas geradas dizem de onde vieram e listam "Onde aparece": cada decisão, item e tarefa mostra
as notas que o citam. Como o vault fica em dia: [[Como manter o vault]].

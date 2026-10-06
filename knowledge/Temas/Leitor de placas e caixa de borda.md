---
tipo: "tema"
escrita: "à mão"
atualizada: "2026-10-06"
tags: [tema]
---

# Leitor de placas e caixa de borda

A borda lê, a nuvem decide ([[D-03]]): a caixa na portaria transforma vídeo em passagens, e a
nuvem casa cada passagem com o agendamento.

## O essencial

- **A caixa:** um mini PC Intel N150 com OpenVINO (cerca de R$ 3,5 mil, [[D-06]]), câmeras IP
  comuns, acesso remoto pelo Tailscale ([[D-13]]) e atualizador próprio ([[D-14]])
  ([[7.4 A caixa de borda]]).
- **O caminho de cada câmera** ([[4.2 O caminho de cada câmera, dentro da caixa]]): captura
  (OpenCV, [[D-29]]; uma linha de execução por câmera, [[D-30]]), detecção, rastreamento
  (próprio, por sobreposição, [[D-25]]), leitura, votação entre quadros e composição (cavalo e
  reboques, [[4.3 Composições e o que a câmera não vê]]).
- **A Passagem** é o contrato entre a caixa e a nuvem ([[3.2 O contrato entre borda e nuvem - a Passagem]],
  [[contratos]]): traz só o que a caixa viu ([[D-17]]); a placa só da traseira vai com papel
  `desconhecido` ([[D-23]]). A caixa envia com fila e reenvio; o que a nuvem recusa de vez fica
  guardado à parte ([[D-24]]).
- **A saúde da caixa** vai a cada minuto, fora da fila: as versões, a máquina, cada câmera e a
  fila ([[D-65]]). A administração vê a **frota de borda**, com o histórico de 7 dias; a
  portaria mostra "site sem conexão desde HH:MM" depois de 3 minutos sem saúde.
- **O leitor fica atrás de uma interface única**, com um motor comercial de reserva ([[D-07]],
  [[4.5 Interface única e dois motores]]). O **v0** usa pesos de terceiros e serve só para
  avaliação interna ([[D-26]]); o produto usará pesos treinados por nós ([[D-05]]).
- **Metas:** leitura por placa visível de 97% e composição de 95%; abaixo da confiança, vira
  exceção, nunca entra errada. A **régua fixa** nunca entra no treino ([[4.7 Metas e a régua]]).
- **O treino** começa com placas sintéticas e bases abertas ([[D-44]]), num ambiente à parte
  ([[D-40]]), e espera as placas reais ([[ABERTO-18]]). O detector (D-FINE-N ou YOLOX-Tiny) se
  decide no teste técnico ([[ABERTO-03]]).

## Onde ler

- SDD: [[3.1 Visão geral]], [[3.2 O contrato entre borda e nuvem - a Passagem]],
  [[4. Leitor de placas]] e subseções, [[7.4 A caixa de borda]], [[6.4 Simulador de portaria]].
- Decisões: [[D-03]], [[D-05]], [[D-06]], [[D-07]], [[D-13]], [[D-14]], [[D-17]], [[D-21]],
  [[D-23]], [[D-24]], [[D-25]], [[D-26]], [[D-29]], [[D-30]], [[D-39]], [[D-40]], [[D-44]],
  [[D-65]].
- Código: [[borda]], [[borda.leitor]], [[contratos]], [[ml]], [[simulador]].
- Tarefas: [[T13]] a [[T20]] (mês 1); [[T21]] a [[T26]] (mês 2, esperam as placas); [[T54]] a
  [[T56]] (mês 4).
- Documentos: [[Guia da demonstração do mês 1]], [[Validação - fatos técnicos da stack]],
  [[Avisos de terceiros da caixa de borda]].

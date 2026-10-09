---
tipo: "tema"
escrita: "à mão"
atualizada: "2026-10-09"
tags: [tema]
---

# Agendamento, portaria e casamento

Do agendamento à chegada: a câmera lê a placa e a nuvem descobre de qual agendamento é o
caminhão.

## O essencial

- **Agendamento próprio simples, com conectores** ([[D-04]], [[3.4 Conectores de agendamento]]):
  pelo link da transportadora, sem login ([[D-34]]), pela planilha CSV ou XLSX, ou pela API. O
  agendamento só é ativo ou cancelado ([[D-32]]); o mesmo código externo atualiza, e a mudança
  fica registrada ([[D-33]]).
- **A visita nasce na chegada** (ou no prazo do "não veio"), e não com o agendamento ([[D-35]]).
  Os estados estão em [[5.2 Estados da visita]].
- **O casamento** ([[5.3 Casamento da chegada com o agendamento]]) compara as placas lidas com as
  esperadas, por pontos; a placa antiga e a Mercosul contam como a mesma ([[D-36]]); na saída,
  qualquer placa da composição fecha a visita ([[D-37]]). Os pesos e o limite esperam os dados
  do modo sombra ([[ABERTO-02]], [[T77]]); a tolerância de janela, o cliente ([[ABERTO-09]]).
- **Roda no worker**, pela fila de tarefas no PostgreSQL ([[D-38]]): a passagem chega, a tarefa
  de casar entra na fila.
- **O porteiro confere a placa** de qualquer passagem ([[D-42]]); corrigir a placa numa exceção
  casa de novo, e a chegada manual não abre exceção ([[D-46]]).

## Onde ler

- SDD: [[2.2 A jornada de um caminhão (modo A)]], [[3.3 Módulos da nuvem no MVP]],
  [[3.4 Conectores de agendamento]], [[5.2 Estados da visita]],
  [[5.3 Casamento da chegada com o agendamento]].
- Decisões: [[D-04]], [[D-32]] a [[D-38]], [[D-42]], [[D-46]].
- Código: [[nuvem.agendamento]], [[nuvem.portaria]], [[nuvem.web]] (telas da portaria e dos
  agendamentos), [[Rotas]].
- Tarefas: [[T11]], [[T12]], [[T27]] a [[T35]], [[T38]], [[T41]]; o ajuste com dados reais:
  [[T77]] (era a [[T37]]); o modo sombra e o registro manual: [[T64]] e [[T72]].

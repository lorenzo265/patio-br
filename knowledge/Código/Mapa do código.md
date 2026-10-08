---
tipo: "mapa do código"
fonte: "pyproject.toml"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `pyproject.toml` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Mapa do código

O repositório é um workspace do uv com 5 pacotes; cada um tem o código em `src/` e os testes em `tests/`. Cada nota abaixo é um pacote Python, com os módulos, o que cada um faz (lido dos docstrings) e os testes.

Também gerado do código:

- [[Rotas]]: os endereços da API e das telas
- [[Tabelas do banco]]: as tabelas e as colunas
- [[Migrações do banco]]: as mudanças do banco, em ordem
- [[Telas do painel]]: os arquivos de tela e quem mostra cada um
- [[Comandos]]: o `uv run tarefas ...`

## borda (`borda/`)

Agente da caixa de borda: captura, leitor de placas, composição e envio.

- [[borda]]: Agente da caixa de borda: captura, leitor de placas, composição e envio ([[4. Leitor de placas|SDD, seção 4]]).
	- [[borda.leitor]]: Leitor de placas da caixa ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]]): a interface, o formato e a votação entre quadros.

## contratos (`contratos/`)

Formatos compartilhados entre a borda e a nuvem.

- [[contratos]]: Formatos compartilhados entre a borda e a nuvem ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD, seção 3.2]]).

## ferramentas (`ferramentas/`)

Ferramentas do projeto: comandos do dia a dia e simulador.

- [[simulador]]: Simulador de portaria ([[6.4 Simulador de portaria|SDD 6.4]]): faz o papel de uma caixa de borda, sem câmera.
- [[tarefas]]: Comandos do dia a dia do projeto, iguais em qualquer sistema operacional.

## ml (`ml/`)

Treino, avaliação e exportação dos modelos do leitor de placas.

- [[ml]]: Treino, avaliação e exportação dos modelos do leitor de placas ([[4.6 Dados de treino|SDD, seção 4.6]]).

## nuvem (`nuvem/`)

Aplicação da nuvem: API, painel e módulos do produto.

- [[nuvem]]: Aplicação da nuvem: API, painel e módulos do produto ([[3.3 Módulos da nuvem no MVP|SDD, seção 3.3]]).
	- [[nuvem.agendamento]]: Agendamento ([[3.3 Módulos da nuvem no MVP|SDD 3.3]] e [[3.4 Conectores de agendamento|3.4]]): os agendamentos de cada site e os conectores que os trazem.
	- [[nuvem.alertas]]: Os alertas ([[8.1 Falhas|SDD 8.1]], [[D-62]] e [[D-68]]): abrem uma vez, fecham sozinhos e avisam quem autorizou.
	- [[nuvem.cadastro]]: Módulo cadastro ([[3.3 Módulos da nuvem no MVP|SDD 3.3]]): empresas, sites, portarias, faixas, câmeras, docas e usuários.
	- [[nuvem.demonstracao]]: A demonstração comercial ([[D-45]] e [[D-49]]): empresas inventadas, o mês de histórico e o dia ao vivo.
	- [[nuvem.extrato]]: Indicadores e extrato do mês em R$ ([[5.4 Contas do extrato|SDD 5.4]] e [[D-48]]).
	- [[nuvem.frota]]: Frota de borda ([[3.3 Módulos da nuvem no MVP|SDD 3.3]] e [[7.4 A caixa de borda|7.4]]): as caixas de cada site, a ativação e a chave de cada uma.
	- [[nuvem.guarda]]: A guarda dos dados ([[8.3 LGPD|SDD 8.3]], [[D-70]]): os prazos, a disputa e o pedido do titular.
	- [[nuvem.mensagens]]: Mensagens ao motorista ([[2.2 A jornada de um caminhão (modo A)|SDD 2.2]], [[7.5 WhatsApp e SMS|7.5]] e [[D-47]]): a confirmação e os avisos da fila e da doca.
	- [[nuvem.patio]]: Pátio e docas ([[2.2 A jornada de um caminhão (modo A)|SDD 2.2]], passos 4 e 5): a fila, a chamada para a doca, o início e o fim.
	- [[nuvem.portaria]]: Portaria ([[3.3 Módulos da nuvem no MVP|SDD 3.3]]): recebe as passagens da borda; no mês 2, casa com o agendamento.
	- [[nuvem.prova]]: A prova da visita ([[5.5 Garantias|SDD 5.5]], [[D-69]]): a cadeia de resumos, a âncora do dia e a conferência.
	- [[nuvem.web]]: Telas do painel ([[6.2 Telas do MVP|SDD 6.2]]): páginas feitas no servidor, com Jinja.

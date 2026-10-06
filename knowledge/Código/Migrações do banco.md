---
tipo: "código"
fonte: "nuvem/migracoes/versions/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/migracoes/versions/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Migrações do banco

As migrações do Alembic, em ordem, de `nuvem/migracoes/versions/`. Modelo novo ou alterado pede migração nova (veja o [[CLAUDE - regras do repositório]]).

| Revisão | O que muda | Criada em |
|---|---|---|
| `0001` | Início: o banco passa a ser controlado pelas migrações; ainda sem tabelas. | 2026-10-02 |
| `0002` | cadastro: estrutura física, usuários e separação por empresa | 2026-10-03 |
| `0003` | login: senha e PIN dos usuários, administração, sessões e tentativas | 2026-10-03 |
| `0004` | frota: códigos de ativação e caixas de borda | 2026-10-03 |
| `0005` | portaria: passagens recebidas da borda | 2026-10-03 |
| `0006` | agendamento: agendamentos e as mudanças de cada um | 2026-10-04 |
| `0007` | agendamento: link da transportadora e horário de operação do site | 2026-10-04 |
| `0008` | portaria: visitas, eventos e exceções | 2026-10-04 |
| `0009` | portaria: o casamento (a passagem única por visita e o motivo pontos_baixos) | 2026-10-04 |
| `0010` | fila de tarefas do worker ([[D-38]]) | 2026-10-04 |
| `0011` | portaria: conferência da placa pelo porteiro ([[D-42]]) | 2026-10-05 |
| `0012` | portaria: a exceção resolvida pelo porteiro (RECUSADA e os eventos novos) | 2026-10-05 |
| `0013` | pátio: a doca na visita, os estados e os eventos do pátio | 2026-10-05 |
| `0014` | mensagens: as mensagens ao motorista ([[D-47]]) | 2026-10-05 |
| `0015` | extrato: parâmetros do site, linha de base e o extrato guardado ([[D-48]]) | 2026-10-05 |
| `0016` | demonstração: o dia de demonstração ([[D-49]]) | 2026-10-05 |
| `0017` | demonstração: o link de demonstração por empresa ([[D-52]] e [[D-54]]) | 2026-10-05 |

---

Do [[Mapa do código]].

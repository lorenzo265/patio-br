---
tipo: "tema"
escrita: "à mão"
atualizada: "2026-10-05"
tags: [tema]
---

# Demonstração comercial

O mês 3 virou a demonstração do produto na internet, para o Lorenzo apresentar às empresas
([[D-45]], [[Plano do mês 3]]).

## O essencial

- **O marco:** o Lorenzo manda um link a uma empresa; quem abre entra numa empresa de
  demonstração só dela, com um mês de histórico, e aperta "começar o dia": em cerca de 5
  minutos os caminhões chegam, fazem check-in, vão para a doca e saem, com uma exceção para
  resolver. Funciona no notebook e no celular, com a marca escolhida.
- **Só dados inventados**, sempre: placas, nomes e celulares (DDD 23, que não existe) vêm da
  semente.
- **O dia de demonstração roda no worker, no relógio de verdade** ([[D-49]]): grava a manhã como
  se já tivesse acontecido e manda as chegadas pelo caminho da caixa, com fotos de placa
  desenhadas; o líder automático chama, começa e termina. Só existe nos ambientes `local` e
  `demonstracao` ([[7.1 Ambientes]]).
- **Um link por empresa visitada**, gerado pela administração e válido por 7 dias; a empresa de
  demonstração é apagada depois; sem cadastro aberto ao público ([[D-52]], [[T48]]).
- **Na internet:** Vercel e Supabase ([[D-51]], [[T47]]); veja [[Hospedagem e custos]].
- **"Em breve":** as telas do recebimento e do estoque em 3D mostram a ideia de depois do piloto,
  com dados de exemplo fixos ([[T46]], [[D-43]]).

## Para ver no computador

```bash
uv run tarefas up            # ou PostgreSQL local, sem Docker
uv run tarefas migrar
uv run tarefas semente
uv run tarefas demonstracao  # a empresa de demonstração, com um mês de histórico
PATIO_AMBIENTE=local uv run uvicorn nuvem.principal:criar_app --factory --port 8000
PATIO_AMBIENTE=local uv run python -m nuvem.worker
```

Entre como `gestor@demonstracao.example` (senha `demonstracao-local`, só no ambiente local),
abra "Dia de demonstração" e clique "Começar o dia".

## Onde ler

- Plano: [[Plano do mês 3]] e as tarefas [[T40]] a [[T48]].
- SDD: [[7.1 Ambientes]], [[8.2 Segurança]], [[10. Cronograma (out-2026 – mar-2027)]].
- Decisões: [[D-43]], [[D-45]], [[D-49]], [[D-51]], [[D-52]].
- Código: [[nuvem.demonstracao]], [[nuvem.web]], [[simulador]].
- A demonstração do mês 1 (caixa e simulador): [[Guia da demonstração do mês 1]].

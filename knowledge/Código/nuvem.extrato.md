---
tipo: "pacote"
fonte: "nuvem/src/nuvem/extrato/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/extrato/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.extrato

Pasta `nuvem/src/nuvem/extrato/`.

Indicadores e extrato do mês em R$ ([[5.4 Contas do extrato|SDD 5.4]] e [[D-48]]).

## Módulos

### `nuvem.extrato.contas`

`nuvem/src/nuvem/extrato/contas.py`

As contas do extrato, sem banco ([[5.4 Contas do extrato|SDD 5.4]], versão 1 da regra, [[D-48]]).

- **Quem entra:** as visitas que chegaram no período ``[de, ate)``.
- **Espera:** da chegada à (última) chamada. **Estadia:** da chegada à liberação na doca; quem saiu
  sem passar pela doca não tem estadia.
- **Exposição a estadia:** os minutos acima da franquia vezes as toneladas e o valor; sem
  toneladas, a visita fica fora da soma e é contada.
- **Uso das docas:** do início ao fim na doca (ou à saída, ou ao fim do período), dentro do
  período, dividido pelas horas disponíveis (as docas vezes as horas de operação).
- **Economia:** a estadia por visita liberada contra a linha de base, a portaria pelos postos e,
  com o custo hora-doca, as horas de doca a mais.

Dinheiro em centavos e porcentagens com uma casa, arredondados para cima a partir da metade.

- **`VERSAO_DA_REGRA`** = `1`: Muda quando uma conta muda: o extrato guardado diz com qual foi feito.
- **`VALOR_DA_ESTADIA`** = `Decimal('2.50')`: R$ por tonelada e hora acima da franquia, em 2026 ([[5.4 Contas do extrato|SDD 5.4]]).
- **`FRANQUIA`** = `timedelta(hours=5)`: Lei 11.442: a estadia conta o que passa de 5 horas desde a chegada.
- **`VisitaMedida`** (classe): O que as contas precisam de uma visita.
- **`Parametros`** (classe): Os números do site para o extrato (``ParametrosSite``).
- **`Medidas`** (classe): As medidas de um período (do mês ou da linha de base), em totais; as médias saem deles.
- **`Economia`** (classe): O que o mês poupou contra a linha de base; vazio = não dá para calcular.
- **`medir`**: As medidas do período ``[de, ate)``.
- **`horas_disponiveis`**: As docas vezes as horas de operação do site em ``[de, ate)``; sem horário, 24 horas.
- **`economizar`**: A economia do mês contra a linha de base.

### `nuvem.extrato.modelos`

`nuvem/src/nuvem/extrato/modelos.py`

Tabelas do extrato ([[5.1 Entidades|SDD 5.1]], [[5.4 Contas do extrato|5.4]] e [[D-48]]): os parâmetros do site, a linha de base e o extrato.

As três apontam para o site pela dupla (site, empresa) ([[5.5 Garantias|SDD 5.5]]). O extrato guardado só se
acrescenta: os gatilhos da função so_acrescenta (migração 0008) recusam mudar ou apagar.

- **`OrigemDaLinhaDeBase`** = `Literal['exemplo', 'modo_sombra']`: Exemplo: gravada pela semente da demonstração. Modo sombra: medida no site (seção 9).
- **`ParametrosSite`** (classe): Os números do site para o extrato; sem linha aqui, valem os da lei e nada da portaria.
- **`LinhaDeBase`** (classe): As medidas do site antes do sistema, para comparar cada mês ([[5.4 Contas do extrato|SDD 5.4]]).
- **`Extrato`** (classe): O extrato de um mês fechado, como foi calculado na primeira vez. Só se acrescenta.

### `nuvem.extrato.servico`

`nuvem/src/nuvem/extrato/servico.py`

O extrato e o painel de um site ([[5.4 Contas do extrato|SDD 5.4]], [[6.2 Telas do MVP|6.2]] e [[D-48]]).

- **Mês fechado:** calculado na primeira vez que é pedido e guardado com a versão da regra, os
  parâmetros e a linha de base usados; depois, vem do que foi guardado.
- **Mês em curso:** parcial, até agora, e a portaria proporcional; não se guarda.
- **Painel:** o dia, o mês até agora e cada dia do mês, de uma leitura só das visitas.

O módulo lê as visitas, os agendamentos e o cadastro pelas funções de serviço deles ([[3.3 Módulos da nuvem no MVP|SDD 3.3]]).
Quem lê passa o ``Acesso``; a semente grava pelos ``gravar_*``.

- **`MesFuturoError`** (classe): O mês ainda não começou no site.
- **`LinhaDeBaseLida`** (classe): A linha de base de um site, com a origem (exemplo ou modo sombra).
- **`ExtratoDoMes`** (classe): O extrato de um mês: fechado (guardado) ou parcial (até agora).
- **`Dia`** (classe): As medidas de um dia (no fuso do site).
- **`Painel`** (classe): O dia, o mês até agora e cada dia do mês.
- **`parametros`**: Os parâmetros do extrato de um site que o usuário vê (sem eles, os da lei).
- **`do_mes`**: O extrato de um mês de um site que o usuário vê (``mes``: qualquer dia dele).
- **`painel`**: O painel de um site que o usuário vê: hoje, o mês até agora e cada dia do mês.
- **`gravar_parametros`**: Grava (ou troca) os parâmetros do extrato de um site.
- **`gravar_linha_de_base`**: Grava (ou troca) a linha de base de um site.

## Testes

- `nuvem/tests/test_nuvem_extrato.py`: O extrato com o banco ([[T44]], [[5.4 Contas do extrato|SDD 5.4]] e [[D-48]]): as visitas do site, o mês guardado e o parcial.
- `nuvem/tests/test_nuvem_extrato_contas.py`: As contas do extrato ([[5.4 Contas do extrato|SDD 5.4]] e [[D-48]]), sem banco: quem entra, as medidas e a economia em R$.

---

Do [[Mapa do código]].

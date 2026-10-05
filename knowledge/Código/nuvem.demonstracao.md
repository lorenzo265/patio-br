---
tipo: "pacote"
fonte: "nuvem/src/nuvem/demonstracao/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/demonstracao/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.demonstracao

Pasta `nuvem/src/nuvem/demonstracao/`.

A demonstração comercial ([[D-45]] e [[D-49]]): empresas inventadas, o mês de histórico e o dia ao vivo.

Só existe nos ambientes ``local`` e ``demonstracao``; tudo aqui é inventado.

## Módulos

### `nuvem.demonstracao.__main__`

`nuvem/src/nuvem/demonstracao/__main__.py`

``python -m nuvem.demonstracao``: a empresa de demonstração local (ver ``local``).

### `nuvem.demonstracao.dia`

`nuvem/src/nuvem/demonstracao/dia.py`

O dia de demonstração ([[D-49]]): a manhã pronta e o resto ao vivo, com o líder automático.

- **Começar:** fecha o que ficou aberto de antes; grava os agendamentos do dia e a manhã até
  agora (quem saiu, quem está na doca e quem espera na fila há horas); e monta o roteiro das
  chegadas ao vivo, uma a cada 10 segundos, cada uma com o seu agendamento. A quarta vem com a
  placa lida errada: vira exceção para a pessoa resolver (a foto mostra a placa certa).
- **Avançar** (o worker, a cada volta): manda as chegadas da hora, pelo caminho da caixa
  (receber e casar), com a foto desenhada; e o líder automático faz uma coisa a cada 6 segundos:
  manda à saída quem foi liberado, começa quem foi chamado, chama o mais antigo da fila para a
  doca livre ou termina quem está na doca há mais tempo. Depois de 5 minutos, o dia acaba e o
  pátio fica como está.

O relógio é o de verdade: as esperas e os alertas são os de um dia real.

- **`AO_VIVO`** = `24`: Quantas chegadas o roteiro manda depois de começar.
- **`CHEGADA_ERRADA`** = `3`: A quarta chegada vem com a placa lida errada (vira exceção).
- **`LIBERADO_HA`** = `timedelta(seconds=15)`: O líder manda à saída quem foi liberado há pelo menos isso.
- **`NA_FILA_HA`** = `timedelta(seconds=12)`: Quem acabou de chegar fica um pouco na fila, para aparecer na tela.
- **`DiaJaComecouError`** (classe): O site já tem um dia de demonstração rodando.
- **`SiteSemCaixaError`** (classe): O site não tem caixa de borda: as passagens não têm em nome de quem chegar.
- **`Andamento`** (classe): O dia de um site, como a tela mostra.
- **`comecar`**: Começa o dia de demonstração de um site do usuário (sem ``commit``).
- **`andamento`**: O último dia de demonstração de um site do usuário, ou ``None`` se nunca começou.
- **`avancar`**: Avança os dias de demonstração que estão rodando, de todos os sites (sem ``commit``).

### `nuvem.demonstracao.empresa`

`nuvem/src/nuvem/demonstracao/empresa.py`

A empresa de demonstração ([[D-49]]): um site completo, inventado, com um mês de histórico.

- **Cadastro:** a empresa, o "CD Demonstração" (das 6h às 22h, 6 docas), a portaria com uma faixa
  de entrada e uma de saída, as câmeras (endereços que não existem), o gestor, o porteiro e o
  líder de pátio, e uma caixa de borda ativada, que o dia de demonstração usa para mandar as
  passagens.
- **Histórico:** os dias passados, já fechados (todos saíram), gravados de uma vez.
- **Linha de base de exemplo:** um mês inventado "antes do sistema" (o ritmo ``ANTES``), medido
  pelas contas do extrato; fica marcada como exemplo ([[D-48]]).
- **Celulares:** do DDD 23, que não existe; nenhum número pode ser de alguém.

As funções gravam com ``flush``; o ``commit`` é de quem chama.

- **`CAMINHOES_POR_DIA`** = `55`: Em média; cada dia varia até 8 para mais ou para menos.
- **`PARAMETROS`**: Três pontos de portaria 24 horas, um a menos depois, pelo menor custo da seção 1.1 do SDD.
- **`EmpresaDeDemonstracao`** (classe): O que foi criado: quem entra e a caixa que manda as passagens.
- **`Lugar`** (classe): O site e quem faz cada coisa, para gravar as jornadas.
- **`criar`**: Cria uma empresa de demonstração inteira, com os ``dias`` passados de histórico.
- **`dia_inventado`**: Os caminhões de um dia do CD Demonstração, com o sistema.
- **`gravar_jornadas`**: Grava o agendamento de cada jornada e, das que já chegaram até ``agora``, a visita, até onde ela foi (a etapa que ainda não aconteceu fica de fora).
- **`celular_inventado`**: Um celular do DDD 23, que não existe (o Rio usa 21, 22 e 24).

### `nuvem.demonstracao.fotos`

`nuvem/src/nuvem/demonstracao/fotos.py`

As fotos de placa desenhadas da demonstração ([[D-49]]): parecem um recorte de placa Mercosul.

São inventadas: nenhuma câmera as tirou. Ficam no armazenamento como as fotos da caixa, e a
portaria as mostra do mesmo jeito (a conferência da placa, [[D-42]]).

- **`placa_desenhada`**: O JPEG de uma placa: fundo branco, a faixa azul com "BRASIL" e os caracteres pretos.

### `nuvem.demonstracao.historico`

`nuvem/src/nuvem/demonstracao/historico.py`

Os dias inventados da demonstração ([[D-49]]): chegadas, chamadas, docas e saídas, sem banco.

Um dia é uma pequena simulação: os caminhões chegam das 6h às 19h (mais de manhã cedo e no começo
da tarde); cada um fica pronto para ser chamado depois da reação do site (o check-in, a conferência)
e vai para a primeira doca que ficar livre. A espera sai da fila de verdade: quando as docas
lotam, ela cresce. O ritmo "antes do sistema" reage mais devagar e não tem check-in automático:
é dele que sai a linha de base de exemplo.

Tudo vem de um ``random.Random``: a mesma semente dá o mesmo dia.

- **`PESO_DAS_HORAS`**: Quantos caminhões chegam em cada hora, em proporção.
- **`Ritmo`** (classe): Como o site trabalha, da chegada à doca.
- **`ANTES`**: Check-in no papel, chamada pelo rádio e doca parada esperando: a linha de base.
- **`Jornada`** (classe): Um caminhão num dia inventado, da chegada à saída.
- **`jornadas_do_dia`**: Os caminhões de um dia, pela ordem de chegada.
- **`placa_inventada`**: Uma placa Mercosul (ABC1D23) que ainda não foi usada; ela entra em ``usadas``.
- **`toneladas_inventadas`**: De 8 a 32 toneladas; de vez em quando, sem (o extrato conta quantas ficaram sem).

### `nuvem.demonstracao.local`

`nuvem/src/nuvem/demonstracao/local.py`

A empresa de demonstração do ambiente local: ``uv run tarefas demonstracao``.

Cria a "Distribuidora Exemplo (demonstração)" no banco de desenvolvimento, com o mês de
histórico, para ver o dia de demonstração ([[D-49]]) na própria máquina. Precisa da semente (a
administração dela gera o código da caixa). Roda uma vez: se a empresa já existe, não faz nada.

- **`CNPJ_LOCAL`** = `'DEMO0000000D00'`: Um CNPJ que não existe: as letras DEMO marcam os dados como de demonstração.
- **`EMAIL_DA_ADMINISTRACAO`** = `'admin@patio-br.example'`: A administração da semente.
- **`SemSementeError`** (classe): A semente ainda não foi gravada: falta a administração que gera o código da caixa.
- **`criar_a_local`**: Cria a empresa de demonstração local (sem ``commit``); ``None`` se ela já existe.
- **`principal`**: Cria a empresa de demonstração no banco de desenvolvimento (``PATIO_URL_BANCO``).

### `nuvem.demonstracao.modelos`

`nuvem/src/nuvem/demonstracao/modelos.py`

A tabela do dia de demonstração ([[D-49]]): o roteiro das chegadas ao vivo e onde ele está.

- **`DiaDeDemonstracao`** (classe): Um "começar o dia" de um site de demonstração.

## Testes

- `nuvem/tests/test_nuvem_demonstracao.py`: A empresa e o dia de demonstração com o banco ([[T45]], [[D-49]]).
- `nuvem/tests/test_nuvem_demonstracao_historico.py`: Os dias inventados da demonstração ([[T45]], [[D-49]]), sem banco: chegadas, docas e ritmos.

---

Do [[Mapa do código]].

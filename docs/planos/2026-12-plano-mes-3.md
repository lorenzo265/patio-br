# Plano do mês 3: a demonstração comercial na internet

Plano de implementação do mês 3 do cronograma do SDD (`docs/SDD.md`, seção 10), refeito em
05/10 (D-45).
Versão 1 · 2026-10-05 · **Rascunho para aprovação do Lorenzo**

---

## 1. Objetivo e marco

**Objetivo:** um sistema funcionando e bonito, num endereço na internet, para o Lorenzo
apresentar às empresas e mostrar que o produto é sério. Prazo: cerca de um mês.

**O que a demonstração mostra** (escolhido pelo Lorenzo em 05/10):

1. **A jornada do caminhão:** agendamento, a câmera lê a placa, check-in sozinho, fila, chamada
   para a doca, carga ou descarga e saída, com a exceção e a conferência da placa.
2. **O painel do gestor e o extrato em R$:** espera média, check-in automático, docas e a
   economia do mês.
3. **O celular do motorista:** as mensagens que ele receberia no WhatsApp, mostradas na tela
   (simuladas, sem enviar nada).
4. **A visão do recebimento e do estoque:** telas de exemplo da ideia de depois do piloto
   (D-43), sem funcionar de verdade e marcadas como "em breve".

**Marco do mês (o teste de "pronto"):**

> O Lorenzo manda um link a uma empresa. Quem abre entra numa empresa de demonstração só dela,
> já com um mês de histórico, e aperta **"começar o dia"**: em cerca de 5 minutos os
> caminhões chegam, fazem check-in, vão para a doca e saem, com uma exceção para resolver. A
> pessoa troca de papel (gestor, porteiro, pátio, motorista) e vê o extrato em R$. Tudo
> funciona no notebook e no celular, com a marca escolhida.

**Só dados inventados.** A demonstração nunca recebe dado de cliente: as placas, os nomes e os
números são gerados pela semente (regra 3 do `CLAUDE.md`).

**O que sai do mês 3 original e para onde vai:**
- a caixa de borda com fila offline, saúde, atualização e contêiner → mês 4;
- a trilha de prova completa → mês 4 (a demonstração usa os eventos que já existem);
- os alertas por mensagem → mês 4, com o WhatsApp de verdade;
- o gerador de placas sintéticas (T39) → depois da demonstração; ele não aparece nela.

**O que vem do mês 4 para cá:** os indicadores e o extrato, o ambiente na internet (só para a
demonstração, com dados inventados) e a segurança mínima para a internet (anti-CSRF e limite
de login por endereço).

---

## 2. Antes de começar: decisões do Lorenzo

| # | Decisão | Trava | Recomendação |
|---|---|---|---|
| E1 | **Nome e cores** (`[ABERTO-01]`). Três caminhos estão na página "Marca do patio-br". | o visual (T40) e o domínio (T47) | escolher um; depois, consultar a marca no INPI e o domínio .com.br |
| E2 | **Onde hospedar a demonstração.** É preciso uma conta e um domínio. | a demonstração na internet (T47) | **AWS Lightsail em São Paulo**, o mesmo que o SDD 7.2 prevê para a produção, numa máquina de 2 GB (US$ 12/mês), e o domínio no registro.br (cerca de R$ 40/ano). A conta é do Lorenzo; eu preparo tudo e passo os passos |
| E3 | **Como a pessoa entra.** | T48 | **um link por empresa visitada**, gerado pela administração e válido por 7 dias. Quem abre ganha uma empresa de demonstração só dela, apagada depois. Sem cadastro aberto ao público |
| E4 | **Fontes tipográficas no painel.** As boas fontes livres usam a licença SIL OFL 1.1, que a regra de licenças ainda não cita (`[ABERTO-21]`). | o visual (T40) | aceitar a OFL 1.1 para fontes usadas sem modificação, como o MPL-2.0; os arquivos ficam em `nuvem/src/nuvem/web/estatico/`, com licença e resumo no `LEIA-ME.md` |

---

## 3. Como trabalhar neste plano

As mesmas regras dos meses 1 e 2 (`CLAUDE.md`), com estes ajustes:

- **Numeração:** as tarefas continuam de onde parou (T40 em diante; a T39, das placas
  sintéticas, fica para depois). As branches levam `mes3/` (ex.: `mes3/t40-visual`).
- **Telas de verdade, não maquetes:** tudo o que a demonstração mostra roda no código do
  produto, com testes, exceto a visão do recebimento e do estoque (T46), que é declarada
  "em breve".
- **Cada tela nova tem captura** no PR (computador e celular), feita com o navegador da sessão.
- **A marca fica num lugar só** (as cores e fontes num arquivo de estilos): trocar o nome ou as
  cores depois é mudar um arquivo.

---

## 4. Tarefas técnicas

### Semana 1 — o visual e a portaria

#### T40. Visual próprio

**Objetivo:** as telas com a marca escolhida (E1), bonitas no computador, no tablet e no celular.

**Depende de:** E1 e E4.

**Arquivos:** `nuvem/src/nuvem/web/estatico/` (estilos, fontes, ícones), `telas/base.html` e
todas as telas que já existem (entrar, início, portaria, agendamentos, link da transportadora).

**Regras:**
- Um arquivo de estilos com as cores, as fontes e os tamanhos da marca; as telas só usam esses
  nomes.
- Menu com os papéis da pessoa; cabeçalho com a empresa e o site.
- Peças repetidas iguais em toda tela: botão, estado (pílula), placa, tabela, cartão, aviso.
- Tema claro (o escuro fica para depois).
- Sem arquivo de outro site (o painel não depende de CDN, SDD 6.1).

**Verificar:** captura de cada tela no computador e no celular; nenhuma rola para o lado.

**Commit:** `feat(web): visual próprio do painel`

#### T41. Portaria definitiva

**Objetivo:** o porteiro resolve tudo pela tela (SDD 5.2 e 6.2).

**Arquivos:** `nuvem/src/nuvem/portaria/`, `nuvem/src/nuvem/web/portaria.py`, telas, migração,
testes.

**Regras (teste primeiro):**
- **Resolver a exceção:** "é este" liga a um candidato; "sem agendamento" aceita; "recusar" leva
  a `RECUSADA`. Cada um é um evento, com quem fez.
- **Corrigir a placa numa exceção** casa de novo com a placa certa (o que a D-42 deixou para o
  mês 3).
- **Registro manual de chegada**, quando a câmera falha.
- A lista se atualiza sozinha sem apagar o que o porteiro está digitando.

**Commit:** `feat(portaria): exceções resolvidas pela tela e registro manual`

### Semana 2 — pátio, docas e o celular do motorista

#### T42. Pátio e docas

**Objetivo:** o líder vê a fila e as docas e move os caminhões (SDD 2.2, passos 4 e 5).

**Arquivos:** módulo `patio` (novo), telas, migração, testes.

**Regras (teste primeiro):**
- Estados `CHAMADA`, `NA_DOCA` e `LIBERADA` (SDD 5.2), cada mudança com um evento.
- Fila pela ordem de chegada, com o tempo de espera de cada um; aviso perto das 5 horas.
- Docas livres e ocupadas; chamar para uma doca livre, começar, terminar.

**Commit:** `feat(patio): fila, chamada e docas`

#### T43. Celular do motorista (simulado)

**Objetivo:** mostrar as mensagens que o motorista receberia, sem enviar nada.

**Arquivos:** módulo `mensagens` (novo, só o canal de demonstração), tela, testes.

**Regras:**
- Cada evento da visita gera a mensagem do modelo: confirmação do agendamento, "você está na
  fila, posição X", "vá para a doca 7", "pode sair".
- O canal de demonstração só guarda; o WhatsApp de verdade entra no mês 4, no mesmo lugar.
- Uma tela em forma de celular mostra a conversa de uma visita.

**Commit:** `feat(mensagens): mensagens do motorista no canal de demonstração`

### Semana 3 — os números

#### T44. Painel do gestor e extrato em R$

**Objetivo:** os indicadores e o extrato do mês (SDD 5.4 e 6.2).

**Arquivos:** módulo `extrato` (novo), telas, testes.

**Regras (teste primeiro):**
- Espera média, estadia, visitas acima de 5 horas, % de check-in automático e uso das docas,
  pelas contas da seção 5.4, com a versão da regra guardada.
- A economia em R$ compara o mês com a linha de base; na demonstração, a linha de base vem da
  semente e está marcada como exemplo.
- Gráficos simples, no próprio painel.

**Commit:** `feat(extrato): indicadores e extrato do mês`

#### T45. O dia de demonstração

**Objetivo:** ~~um dia inteiro de caminhões em cerca de 5 minutos~~ a manhã já pronta e o resto
do dia ao vivo em cerca de 5 minutos, mais um mês de histórico. *Mudou na execução (D-49): no
relógio de verdade, as esperas e os alertas aparecem como num dia real; com o relógio acelerado,
seriam de segundos.*

**Arquivos:** `nuvem/src/nuvem/demonstracao/` (novo), ~~o simulador~~ o worker (D-49), testes.

**Regras:**
- A semente da demonstração grava um mês de visitas passadas (para o painel e o extrato ter
  números) e os agendamentos do dia.
- "Começar o dia" grava a manhã e manda as passagens ~~no tempo acelerado~~ a cada poucos
  segundos, com fotos de placa desenhadas; um "líder automático" chama para as docas e termina
  as cargas, e deixa uma exceção para a pessoa resolver.
- Só dados inventados; nada disso existe fora do ambiente de demonstração.

**Commit:** `feat(demonstracao): dia acelerado e histórico do mês`

### Semana 4 — a visão e a internet

#### T46. Visão do recebimento e do estoque ("em breve")

**Objetivo:** mostrar para onde o produto vai (D-43), sem prometer o que não existe.

**Arquivos:** duas telas e os dados de exemplo.

**Regras:**
- **Recebimento:** a nota de um caminhão na doca, item por item, com a contagem do conferente e
  a divergência.
- **Estoque em 3D:** o armazém em três dimensões; a busca acende o lugar do item. A biblioteca
  de 3D tem licença MIT e fica em `estatico/`, com licença e resumo.
- As duas telas dizem "em breve" e usam dados de exemplo fixos.

**Commit:** `feat(web): visão do recebimento e do estoque`

#### T47. Demonstração na internet

**Objetivo:** o endereço público, seguro e barato.

**Depende de:** E1 (o domínio) e E2 (a conta).

**Arquivos:** `infra/demonstracao/` (o compose da máquina e o Caddy), um comando para publicar,
`docs/guias/demonstracao-na-internet.md`.

**Regras:**
- **Antes de abrir para a internet** (vem do mês 4, SDD 8.2): código anti-CSRF nos formulários,
  limite de login também por endereço e o comando para criar a administração.
- HTTPS pelo Caddy; segredos só na máquina, nunca no repositório.
- O ambiente de demonstração recusa passagem de caixa de verdade e só tem dados da semente.
- As empresas de demonstração vencidas são apagadas toda noite.

**Commit:** `infra: demonstração na internet`

#### T48. Link de demonstração por empresa

**Objetivo:** o Lorenzo gera um link para cada empresa visitada (E3).

**Arquivos:** a administração, o módulo `demonstracao`, testes.

**Regras (teste primeiro):**
- A administração gera o link (código guardado só como resumo, como o link da transportadora,
  D-34), válido por 7 dias.
- Quem abre ganha uma empresa de demonstração só dela, com a semente, e entra como gestor; um
  seletor troca o papel (gestor, porteiro, pátio, motorista).
- Uma empresa de demonstração nunca vê outra (as regras de separação de sempre).

**Commit:** `feat(demonstracao): link de demonstração por empresa`

---

## 5. Trilha não técnica

| # | Tarefa | Por quê | Resolve |
|---|---|---|---|
| N16 | Escolher o nome e as cores (E1), consultar o INPI e registrar o domínio | a marca e o endereço da demonstração | E1, T40, T47 |
| N17 | Abrir a conta da AWS (E2) e passar o acesso pelo cofre de segredos do ambiente | publicar a demonstração | T47 |
| N18 | Listar as empresas para apresentar e marcar as conversas | o motivo da demonstração | o comercial |

---

## 6. Ajustes no SDD feitos junto com este plano

- D-45 (o mês 3 vira a demonstração comercial), o ambiente de demonstração (seção 7.1), a
  segurança antes da internet (seção 8.2), o cronograma (seção 10) e o `[ABERTO-21]` (fontes
  OFL).

---

## 7. Checklist de "mês 3 pronto"

- [ ] E1 a E4 decididas e registradas no SDD.
- [ ] Visual próprio em todas as telas, no computador e no celular.
- [ ] Exceção resolvida pela tela; registro manual.
- [ ] Pátio e docas com chamada, início e fim.
- [ ] Mensagens do motorista no canal de demonstração.
- [ ] Painel do gestor e extrato em R$.
- [ ] Dia de demonstração em cerca de 5 minutos, com um mês de histórico.
- [ ] Telas "em breve" do recebimento e do estoque.
- [ ] **Marco:** a demonstração no ar, aberta por um link de empresa, no computador e no
      celular.

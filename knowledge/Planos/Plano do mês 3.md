---
tipo: "plano"
fonte: "docs/planos/2026-12-plano-mes-3.md"
gerada: true
tags: [plano]
---

> [!note] Gerada de `docs/planos/2026-12-plano-mes-3.md` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Plano do mês 3: a demonstração comercial na internet

Plano de implementação do mês 3 do cronograma do SDD ([[SDD|docs/SDD.md]], seção 10), refeito em
05/10 ([[D-45]]).
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
   ([[D-43]]), sem funcionar de verdade e marcadas como "em breve".

**Marco do mês (o teste de "pronto"):**

> O Lorenzo manda um link a uma empresa. Quem abre entra numa empresa de demonstração só dela,
> já com um mês de histórico, e aperta **"começar o dia"**: em cerca de 5 minutos os
> caminhões chegam, fazem check-in, vão para a doca e saem, com uma exceção para resolver. A
> pessoa troca de papel (gestor, porteiro, pátio, motorista) e vê o extrato em R$. Tudo
> funciona no notebook e no celular, com a marca escolhida.

**Só dados inventados.** A demonstração nunca recebe dado de cliente: as placas, os nomes e os
números são gerados pela semente (regra 3 do [[CLAUDE - regras do repositório|CLAUDE.md]]).

**O que sai do mês 3 original e para onde vai:**
- a caixa de borda com fila offline, saúde, atualização e contêiner → mês 4;
- a trilha de prova completa → mês 4 (a demonstração usa os eventos que já existem);
- os alertas por mensagem → mês 4, com o WhatsApp de verdade;
- o gerador de placas sintéticas ([[T39]]) → depois da demonstração; ele não aparece nela.

**O que vem do mês 4 para cá:** os indicadores e o extrato, o ambiente na internet (só para a
demonstração, com dados inventados) e a segurança mínima para a internet (anti-CSRF e limite
de login por endereço).

---

## 2. Antes de começar: decisões do Lorenzo

| # | Decisão | Trava | Recomendação | Decidido em 05/10 |
|---|---|---|---|---|
| E1 | **Nome e cores** ([[ABERTO-01]]). Três caminhos estão na página "Marca do patio-br". | o visual ([[T40]]) e o domínio ([[T47]]) | escolher um; depois, consultar a marca no INPI e o domínio .com.br | **numa sessão à parte**, que decide a identidade visual inteira com as skills de design e já faz a [[T40]] (prompt em [[Prompt da identidade visual\|docs/prompts/identidade-visual.md]]) |
| E2 | **Onde hospedar a demonstração.** É preciso uma conta e um domínio. | a demonstração na internet ([[T47]]) | ~~**AWS Lightsail em São Paulo**, o mesmo que o [[7.2 Nuvem (AWS, sa-east-1)\|SDD 7.2]] prevê para a produção, numa máquina de 2 GB (US$ 12/mês), e o domínio no registro.br (cerca de R$ 40/ano)~~ | **Vercel e Supabase** ([[D-51]]): um primeiro deploy simples, sem máquina para cuidar. A [[T47]] muda (ver abaixo) |
| E3 | **Como a pessoa entra.** | [[T48]] | **um link por empresa visitada**, gerado pela administração e válido por 7 dias. Quem abre ganha uma empresa de demonstração só dela, apagada depois. Sem cadastro aberto ao público | **aprovado** ([[D-52]]) |
| E4 | **Fontes tipográficas no painel.** As boas fontes livres usam a licença SIL OFL 1.1, que a regra de licenças ainda não cita ([[ABERTO-21]]). | o visual ([[T40]]) | aceitar a OFL 1.1 para fontes usadas sem modificação, como o MPL-2.0; os arquivos ficam em `nuvem/src/nuvem/web/estatico/`, com licença e resumo no `LEIA-ME.md` | **aprovado** ([[D-50]]) |

---

## 3. Como trabalhar neste plano

As mesmas regras dos meses 1 e 2 ([[CLAUDE - regras do repositório|CLAUDE.md]]), com estes ajustes:

- **Numeração:** as tarefas continuam de onde parou ([[T40]] em diante; a [[T39]], das placas
  sintéticas, fica para depois). As branches levam `mes3/` (ex.: `mes3/t40-visual`).
- **Telas de verdade, não maquetes:** tudo o que a demonstração mostra roda no código do
  produto, com testes, exceto a visão do recebimento e do estoque ([[T46]]), que é declarada
  "em breve".
- **Cada tela nova tem captura** no PR (computador e celular), feita com o navegador da sessão.
- **A marca fica num lugar só** (as cores e fontes num arquivo de estilos): trocar o nome ou as
  cores depois é mudar um arquivo.

---

## 4. Tarefas técnicas

### Semana 1 — o visual e a portaria

- [[T40]] Visual próprio
- [[T41]] Portaria definitiva

### Semana 2 — pátio, docas e o celular do motorista

- [[T42]] Pátio e docas
- [[T43]] Celular do motorista (simulado)

### Semana 3 — os números

- [[T44]] Painel do gestor e extrato em R$
- [[T45]] O dia de demonstração

### Semana 4 — a visão e a internet

- [[T46]] Visão do recebimento e do estoque ("em breve")
- [[T47]] Demonstração na internet
- [[T48]] Link de demonstração por empresa

## 5. Trilha não técnica

| # | Tarefa | Por quê | Resolve |
|---|---|---|---|
| [[N16]] | Escolher o nome e as cores (E1), consultar o INPI e registrar o domínio | a marca e o endereço da demonstração | E1, [[T40]], [[T47]] |
| [[N17]] | ~~Abrir a conta da AWS (E2)~~ Abrir as contas da Vercel e do Supabase ([[D-51]]), escolher os planos e passar o acesso pelo cofre de segredos do ambiente | publicar a demonstração | [[T47]] |
| [[N18]] | Listar as empresas para apresentar e marcar as conversas | o motivo da demonstração | o comercial |

---

## 6. Ajustes no SDD feitos junto com este plano

- [[D-45]] (o mês 3 vira a demonstração comercial), o ambiente de demonstração (seção 7.1), a
  segurança antes da internet (seção 8.2), o cronograma (seção 10) e o [[ABERTO-21]] (fontes
  OFL).

---

## 7. Checklist de "mês 3 pronto"

- [x] E2 a E4 decididas e registradas no SDD ([[D-50]] a [[D-52]]); E1 numa sessão à parte.
- [ ] Visual próprio em todas as telas, no computador e no celular.
- [ ] Exceção resolvida pela tela; registro manual.
- [ ] Pátio e docas com chamada, início e fim.
- [ ] Mensagens do motorista no canal de demonstração.
- [ ] Painel do gestor e extrato em R$.
- [ ] Dia de demonstração em cerca de 5 minutos, com um mês de histórico.
- [ ] Telas "em breve" do recebimento e do estoque.
- [ ] **Marco:** a demonstração no ar, aberta por um link de empresa, no computador e no
      celular.

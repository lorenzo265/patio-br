# Prompt: a identidade visual do patio-br (E1 e T40)

Para abrir uma sessão nova do Claude Code neste repositório. Copie tudo abaixo da linha e cole
como a primeira mensagem.

---

Você vai cuidar da **identidade visual do patio-br**: escolher, junto com o Lorenzo, o nome, as
cores, as fontes e a marca, e depois aplicar tudo nas telas do painel. Trabalhe em português,
com linguagem simples, como o resto do repositório.

## Antes de tudo, leia

Se a pasta `knowledge/` existir, ela é o vault do Obsidian com o mapa do projeto: comece pela
nota `knowledge/00 Início.md`. Ela leva a todo o resto.

1. `CLAUDE.md`: as regras do repositório. Valem todas, em especial licenças (regra 1), dado real
   (regra 3) e "uma tarefa = uma branch = um PR".
2. `docs/SDD.md`: a fonte da verdade. Leia pelo menos:
   - 1 (o problema e para quem);
   - 2.1 (os papéis);
   - 6.1 (a stack e a regra dos arquivos de terceiros);
   - 6.2 (as telas);
   - as decisões D-43, D-45, D-49, D-50 e D-51, e o `[ABERTO-01]`.
3. `docs/planos/2026-12-plano-mes-3.md`: a tabela de decisões (E1 a E4) e a tarefa **T40**.
4. A página "Marca do patio-br" (https://claude.ai/artifact/2dCtjesCoqJdfskRTGySV9), que mostra
   os três caminhos já propostos. Leia com a ferramenta Artifact (`action: "read"`).

   | Caminho | Nome | Frase | Cores | Fontes |
   |---|---|---|---|---|
   | 1 | **cais** | "onde a carga chega" | petróleo #0F3B4C, sinalização #E8662A, concreto #E9EEF0 e aço #5B6B73 | Archivo larga e Public Sans |
   | 2 | **giro** | "pátio andando, estoque girando" | mata #14432F, lâmpada de sódio #F2B705, papel #F1F2EC e musgo #4F6158 | Bricolage Grotesque e Red Hat Text |
   | 3 | **Placar** | "a placa na entrada, o resultado no fim do mês" | grafite #1E2328, azul da placa #003399, economia #1F9D55 e placa #F4F5F2 | Barlow e Barlow Condensed |

   Os caminhos são ponto de partida, não limite: pode propor outro nome ou misturar.

## O produto, em poucas linhas

Sistema de pátio para centros de distribuição no Brasil:
- a câmera da portaria lê a placa e o caminhão entra na fila sem aplicativo;
- o líder de pátio chama para as docas;
- o motorista recebe os avisos no celular;
- o gestor vê o painel e um extrato mensal da economia em R$.

Quem usa:
- **Porteiro:** tablet na portaria, muitas vezes ao sol e com pressa. A placa, a foto e "é este /
  corrigir" precisam saltar aos olhos.
- **Líder de pátio:** computador ou tablet: a fila, as docas e os alertas de 4 e 5 horas.
- **Gestor:** computador: o painel, o extrato em R$ e os agendamentos.
- **Motorista:** só recebe mensagens. A tela em forma de celular é da demonstração.
- **Transportadora:** um formulário no celular, sem conta (o link de agendamento).

O momento: o Lorenzo vai apresentar o produto a empresas por um link na internet (D-45). A
identidade precisa passar seriedade: um produto pronto, de empresa, e não um protótipo.

## O que fazer

### Parte 1: decidir a identidade (E1, `[ABERTO-01]`)

1. Use a skill **brainstorming** antes de qualquer criação: entenda o que o Lorenzo quer
   transmitir (perguntas curtas, uma de cada vez, com opções).
2. Monte de 2 a 3 direções completas numa página (Artifact). Use as skills **artifact-design** e,
   para os gráficos do painel, **dataviz**. Cada direção traz:
   - o nome e a marca escrita (wordmark);
   - a paleta com papéis, cada cor com contraste conferido (AA): fundo, superfície, texto,
     primária, destaque, sucesso, alerta e erro;
   - as fontes (só OFL 1.1, D-50, ou outra licença permissiva);
   - os ícones;
   - um pedaço de **três telas reais** pintado com ela: a portaria (a placa e a exceção), o pátio
     (as docas e o alerta) e o extrato (o R$ em destaque).
3. O Lorenzo escolhe. Antes de fechar o nome, lembre a ele dois passos que são dele (N16): a
   consulta da marca no INPI e se o domínio .com.br está livre.
4. **Registre no SDD, antes do código:**
   - uma decisão nova (a próxima livre na seção 11): o nome, as cores, as fontes e o porquê;
   - o fim do `[ABERTO-01]` (a linha sai da tabela da seção 12);
   - a versão nova e a linha no "Histórico de versões", no fim do SDD;
   - a E1 no plano do mês 3;
   - o vault: `uv run tarefas conhecimento` gera as notas de novo, e a nota à mão
     `knowledge/Temas/Identidade visual.md` passa a dizer o que foi escolhido.

### Parte 2: aplicar nas telas (T40)

Siga as regras da T40 no plano:
- **Um arquivo de estilos** com as cores, as fontes e os tamanhos da marca, como variáveis CSS;
  as telas só usam esses nomes, sem cor solta no HTML.
- **Menu** com os papéis da pessoa; **cabeçalho** com a empresa e o site.
- **Peças repetidas iguais** em toda tela: botão, pílula de estado, placa (o desenho da placa
  Mercosul), tabela, cartão, aviso, campo de formulário, barra de gráfico.
- **Tema claro** (o escuro fica para depois).
- **Responsivo:** computador, tablet e celular. Nenhuma tela rola para o lado.
- **Sem CDN:** as fontes e os ícones ficam em `nuvem/src/nuvem/web/estatico/`, com a versão no
  nome, a licença e o SHA-256 no `LEIA-ME.md` de lá (SDD 6.1, D-50).
  - O teste `nuvem/tests/test_nuvem_web_em_breve.py` confere os hashes e exige que todo `.js`
    servido esteja listado; estenda-o para as fontes (`.woff2`).
- **Sem framework de JavaScript nem etapa de build:** o painel é Jinja + HTMX (D-09). CSS puro
  basta; JavaScript só onde já existe (a conta do recebimento, o 3D do estoque, o HTMX).
- **Acessibilidade:** contraste AA, foco visível no teclado, alvos de toque de 44 px no tablet
  da portaria, textos e rótulos em português simples.

**As telas** (todas em `nuvem/src/nuvem/web/telas/`, herdando de `base.html`):

| Grupo | Telas |
|---|---|
| Acesso | entrar, início, trocar porteiro, aviso |
| Portaria | `portaria`, com as listas `portaria_passagens` e `portaria_excecoes`; conferir a placa; resolver a exceção; chegada manual |
| Pátio | `patio`, com o quadro `patio_quadro`; chamar para a doca |
| Gestor | agendamentos (com a planilha e os links); painel; extrato |
| Transportadora | o link de agendamento (`agendar`, `agendar_aviso`, `agendar_feito`), no celular |
| Motorista (demonstração) | `mensagens`, com a tela em forma de celular `mensagens_celular` e a conversa `mensagens_conversa` |
| "Em breve" | recebimento; estoque em 3D (as cores do three.js também vêm da marca) |
| Demonstração | dia de demonstração |

Não mude regra de negócio, rota nem o que cada tela mostra: só a aparência. Se algum teste de
tela procurar um texto que você quiser mudar, mude o texto com cuidado e explique no PR.

### Como ver as telas com dados

```bash
uv sync
uv run tarefas up            # ou PostgreSQL local, se o Docker não estiver disponível
uv run tarefas migrar
uv run tarefas semente
uv run tarefas demonstracao  # a empresa de demonstração, com um mês de histórico
# a API e o worker, cada um num terminal (o worker faz o dia de demonstração andar):
PATIO_AMBIENTE=local uv run uvicorn nuvem.principal:criar_app --factory --port 8000
PATIO_AMBIENTE=local uv run python -m nuvem.worker
```

- **Os logins:**
  - `gestor@demonstracao.example` (a empresa de demonstração);
  - `gestor@empresa-a.example`, `patio@empresa-a.example` e `porteiro@empresa-a.example` (a
    semente).

  Todos com a senha `demonstracao-local`.
- **Para ver o pátio e a portaria cheios**, entre como o gestor da demonstração, abra "Dia de
  demonstração" e clique "Começar o dia".
- **Para as capturas:** `uv run --with playwright python script.py`. O Chromium já está
  instalado; não rode `playwright install`.

### Entrega

- **Branch e PR:** `mes3/t40-visual-proprio`, um PR para a `main`.
- **Commits:** o SDD primeiro (`docs:`); depois o código (`feat(web): visual próprio do
  painel`). Código e documentação em commits separados.
- **Teste:** `uv run tarefas check` passa.
- **No PR:**
  - capturas de cada tela no computador (1280 px) e no celular (390 px);
  - a lista das fontes e dos ícones, com as licenças;
  - qualquer texto de tela que mudou.
- **Ao Lorenzo**, no fim: um resumo curto do que decidiu, do que fez e do que ficou para ele (o
  INPI e o domínio).

## O que não fazer

- Não use dado real: as telas de exemplo usam placas, nomes e números inventados.
- Não ponha segredo no repositório.
- Não resolva no código outro `[ABERTO-nn]` além do 01.
- Não sirva nada de CDN.
- Não traga fonte ou ícone sem conferir a licença.

# Plano do mês 1 (outubro de 2026): fundação

Plano de implementação do mês 1 do cronograma do SDD (`docs/SDD.md`, seção 10).
Versão 1 · 2026-10-02

---

## 1. Objetivo e marco

**Objetivo:** ter a base do projeto de pé — repositório organizado, verificações automáticas,
ambiente local com Docker, o formato da passagem, o esqueleto da nuvem com cadastro e login, e
um leitor de placas inicial (v0) rodando sobre vídeo gravado.

**Marco do mês (o teste de "pronto"):**

> Com um comando (`uv run tarefas demo`), o ambiente local sobe, um vídeo gravado de uma
> portaria passa pelo leitor v0, vira **passagem**, chega à API e **aparece na tela da
> portaria** com foto, placa e confiança.

**Fora do mês 1** (para não inchar): agendamento e casamento (mês 2), worker e fila de tarefas
(mês 2), telas de pátio e exceções (mês 3), WhatsApp (mês 4), verificação em duas etapas
(mês 4, antes da produção), AWS de produção (mês 4).

---

## 2. Como trabalhar neste plano

- **Uma tarefa = uma branch = um pull request** (`mes1/t06-contratos`, por exemplo). O PR só
  entra na `main` com a CI verde.
- **Teste primeiro** nas regras com lógica (formato de placa, votação, composição, separação de
  clientes, envio repetido): escreva o teste que falha, depois o código que o faz passar.
- **Ambiente de desenvolvimento:** seu computador é Windows (pelo que o projeto da Dell usa).
  Por isso os comandos do projeto são **Python puro**, chamados por `uv run tarefas <comando>`,
  e funcionam igual em Windows, Linux e Mac. Precisa de: Python 3.12, `uv` e Docker Desktop.
- **Dados reais (vídeos, fotos, placas) nunca entram no Git.** Ficam na pasta `dados/`, que o
  Git ignora.
- Qualquer mudança de desenho passa pelo SDD primeiro (regra da seção 0 do SDD).

---

## 3. Tarefas técnicas

Ordem sugerida por semana. Estimativas para uma pessoa com IA; a semana 4 tem folga.

### Semana 1 — fundação do repositório

#### T01. Estrutura de pastas e espaço de trabalho Python

**Objetivo:** criar as pastas do SDD (seção 6.3) e um "workspace" do `uv` com um pacote por
pasta.

**Arquivos:**
- `pyproject.toml` (raiz): workspace `uv` com os membros `contratos`, `borda`, `nuvem`,
  `ferramentas`, `ml`; Python 3.12; configuração do ruff, mypy e pytest.
- `contratos/pyproject.toml`, `borda/pyproject.toml`, `nuvem/pyproject.toml`,
  `ferramentas/pyproject.toml`, `ml/pyproject.toml`: cada um com seu `src/` e `tests/`.
- `.gitignore`: `dados/`, `modelos/`, `.env`, `__pycache__/`, `.venv/`.
- `.python-version`: `3.12`.

**Verificar:** `uv sync` instala tudo sem erro; `uv run python -c "import contratos, borda, nuvem"`
não falha.

**Commit:** `chore: estrutura do monorepo com workspace uv`

#### T02. Comandos do projeto (`tarefas`)

**Objetivo:** um único ponto de entrada para os comandos do dia a dia, igual em qualquer
sistema operacional.

**Arquivos:** `ferramentas/src/tarefas/__main__.py` (registrado como script `tarefas`).

**Comandos:**

| Comando | O que faz | Entra na |
|---|---|---|
| `check` | ruff (estilo), ruff format --check, mypy (tipos), pytest | T02 |
| `test` | só os testes; o que vier depois vai para o pytest (ex.: `-k placa`) | T02 |
| `up` / `down` | sobe e derruba o Docker Compose local | T04 |
| `migrar` | aplica as migrações do banco | T07 |
| `semente` | cria empresa, site, portaria, faixas, câmeras e uma caixa de demonstração | T08 |
| `demo` | `up` + `migrar` + `semente` + roda o simulador com o vídeo de amostra | T19 |

Cada comando entra junto com a tarefa que cria o que ele executa: assim nenhum comando existe
sem ter o que rodar.

**Verificar:** `uv run tarefas check` roda e passa (mesmo com pouco código).

**Commit:** `chore: comandos do projeto em python (tarefas)`

#### T03. Integração contínua (GitHub Actions)

**Objetivo:** cada push e cada PR rodam as verificações.

**Arquivo:** `.github/workflows/ci.yml`.

**Passos da CI:**
1. Instala `uv` e Python 3.12.
2. ~~Sobe um PostgreSQL 16 como serviço~~ → entra na **T07**, junto com os primeiros testes que usam banco.
3. `uv sync --frozen`.
4. `uv run tarefas check`.
5. **Licenças:** `pip-licenses` com lista de licenças permitidas (MIT, BSD, Apache-2.0,
   PostgreSQL, ISC, PSF, MPL-2.0 apenas como biblioteca). Falha se aparecer GPL/AGPL/LGPL ou
   licença desconhecida.
6. **Vulnerabilidades:** `pip-audit`.

**Verificar:** abrir um PR de teste e ver a CI verde; adicionar de propósito um pacote AGPL numa
branch descartável e ver a CI falhar.

**Commit:** `ci: verificações, licenças e vulnerabilidades`

#### T04. Ambiente local com Docker

**Objetivo:** `uv run tarefas up` sobe o banco ~~e a API~~ (a API entra na **T07**: antes dela
não há aplicação para pôr no contêiner).

**Arquivos:**
- `infra/docker-compose.yml`: serviços `postgres` (16, com volume) e `postgres-teste` (porta
  separada, em memória, começa vazio a cada `up`), ambos só em `127.0.0.1`.
  ~~`api` (build de `nuvem/`)~~ → **T07**.
- ~~`nuvem/Dockerfile`~~ → **T07**.
- `.env.exemplo`: variáveis com valores de exemplo (nunca segredos reais).
- `tarefas up` / `tarefas down`; sem o Docker instalado, o comando diz o que falta.
- CI: um job sobe o ambiente com `tarefas up`, consulta os dois bancos e derruba com
  `tarefas down`.

**Verificar:** `uv run tarefas up` termina com os dois bancos saudáveis; `select 1` responde em
`patio` e em `patio_teste`; depois de `tarefas down` e `up`, o que estava em `patio` continua
lá. ~~`GET /saude`~~ → **T07**.

**Commit:** `infra: ambiente local com docker compose`

#### T05. Arquivo de orientação para sessões com IA

**Objetivo:** um `CLAUDE.md` curto na raiz para que qualquer sessão de IA siga as regras do
projeto.

**Conteúdo:** o SDD é a fonte da verdade; regra de licença (seção 4.1); LGPD (sem
reconhecimento facial, dados reais fora do Git); teste primeiro nas regras; comandos
`uv run tarefas ...`; uma tarefa por PR.

**Commit:** `docs: orientações do projeto para sessões com IA`

### Semana 2 — contrato e esqueleto da nuvem

#### T06. Pacote `contratos`: a Passagem

**Objetivo:** o formato único entre borda e nuvem (SDD 3.2), validado.

**Arquivos:** `contratos/src/contratos/passagem.py`, `contratos/src/contratos/placa.py`,
`contratos/schema/passagem.v1.json`, `contratos/tests/`.

**Regras (teste primeiro):**
- `Placa`: aceita `ABC1234` e `ABC1D23`; recusa o resto; sempre em maiúsculas, sem hífen.
- `PlacaLida`: placa, papel (`cavalo` | `reboque` | `desconhecido`), confiança entre 0 e 1,
  câmera, quadros ≥ 1. ~~`inferida`~~ → saiu do contrato: quem infere é a nuvem, e a placa
  inferida fica na visita (SDD D-17).
- `Passagem`: todos os campos do SDD 3.2; `sentido` é `entrada` ou `saida`; `fim` ≥ `inicio`;
  horários com fuso; `versao_contrato = 1`.
- O arquivo `passagem.v1.json` (JSON Schema) é gerado a partir do modelo; **um teste falha se o
  arquivo estiver desatualizado**.

**Verificar:** `uv run tarefas test` passa; pelo menos um teste para cada regra acima.

**Commit:** `feat(contratos): passagem v1 e validação de placa`

#### T07. Esqueleto da nuvem

**Objetivo:** aplicação FastAPI organizada por módulos (SDD 3.3), com banco e migrações.

**Arquivos:**
- `nuvem/src/nuvem/principal.py`: cria a aplicação e registra as rotas dos módulos.
- `nuvem/src/nuvem/config.py`: configurações lidas do ambiente (pydantic-settings).
- `nuvem/src/nuvem/banco.py`: conexão SQLAlchemy 2 com PostgreSQL (~~psycopg 3~~ → **pg8000**:
  o psycopg é LGPL, que a regra de licença não aceita; SDD D-18).
- `nuvem/migracoes/`: Alembic configurado.
- Rota `GET /saude`.
- `nuvem/tests/conftest.py`: banco de teste limpo a cada teste.
- `.github/workflows/ci.yml`: PostgreSQL 16 como serviço no job de testes (adiado da T03).
- `nuvem/Dockerfile` e o serviço `api` em `infra/docker-compose.yml` (adiados da T04).

**Verificar:** `uv run tarefas migrar` roda; o teste de `/saude` passa; com `uv run tarefas up`,
`GET http://localhost:8000/saude` responde `{"ok": true}` (e 503 `{"ok": false}` com o banco fora
do ar).

**Commit:** `feat(nuvem): esqueleto fastapi, banco e migrações`

#### T08. Módulo `cadastro` e separação por empresa

**Objetivo:** as tabelas da estrutura física e dos usuários (SDD 5.1) e a garantia de que um
cliente nunca vê dado de outro.

**Arquivos:** `nuvem/src/nuvem/cadastro/{modelos.py,servico.py,rotas.py}`, migração, testes.

**Tabelas:** `empresa`, `site`, `portaria`, `faixa` (com sentido), `camera` (posição, endereço,
senha cifrada), `doca`, `usuario` (papel, ~~PIN opcional~~ → **T09**, junto com a senha, já com o
resumo argon2), `usuario_site`. O papel da administração (nós) também fica para a T09.

**Regras (teste primeiro):**
- Todo acesso aos dados passa por uma função que **exige** a empresa do usuário logado.
- **Teste obrigatório:** um usuário da empresa A tenta ler um site da empresa B e recebe
  "não encontrado".
- A senha da câmera é guardada cifrada (chave vinda da configuração) e nunca aparece em
  resposta da API.
- As rotas do cadastro existem, mas respondem 401 até o login (T09): sem usuário identificado
  não há empresa para filtrar. Os testes trocam a dependência `obter_acesso` por um usuário de
  exemplo.

**Verificar:** testes passam; `uv run tarefas semente` cria os dados de demonstração.

**Commit:** `feat(cadastro): estrutura física, usuários e separação por empresa`

#### T09. Login e papéis

**Objetivo:** entrar no painel com e-mail e senha; cada tela exige um papel.

**Arquivos:** `nuvem/src/nuvem/cadastro/acesso.py`, telas `entrar` e `sair`, testes. Entraram
também `cadastro/login.py` (as regras do login), `nuvem/senhas.py` (argon2) e o começo do módulo
`nuvem/web/` (Jinja), que a T12 continua.

**Regras:**
- Senha guardada com argon2; nunca em texto.
- Sessão por cookie seguro (`HttpOnly`, `SameSite=Lax`, `Secure` fora do local). A sessão fica
  no banco (SDD D-20); o ambiente vem da variável nova `PATIO_AMBIENTE`.
- Papéis: `porteiro`, `patio`, `gestor`, ~~`admin`~~. Rota sem o papel certo devolve 403.
  ~~`admin`~~ → a administração (nós) é uma tabela própria, `administrador`, fora das empresas
  (SDD D-19), com rotas próprias (`/api/admin/...`).
- Limite de tentativas de login por e-mail (contra adivinhação).
- PIN do porteiro (adiado da T08), com argon2, e a troca de porteiro no tablet.
- A verificação em duas etapas fica para o mês 4 (antes da produção), como previsto.

**Verificar:** testes de login certo, senha errada, papel errado e limite de tentativas.

**Commit:** `feat(acesso): login por sessão e papéis`

#### T10. Caixa de borda: ativação e chave

**Objetivo:** a caixa (ou o simulador) se identifica para mandar passagens.

**Arquivos:** `nuvem/src/nuvem/frota/{modelos.py,servico.py,rotas.py}`, testes. Entrou também
`frota/acesso.py` (a dependência que identifica a caixa pela chave).

**Fluxo:**
1. O admin gera um **código de ativação** de uso único para um site (expira em 24h):
   `POST /api/admin/sites/{id}/codigos-de-ativacao`, com 12 letras e números em três grupos.
2. A caixa chama `POST /api/borda/ativar` com o código e recebe uma **chave** própria. A nuvem
   guarda só o resumo (hash) da chave.
3. Toda chamada da caixa usa `Authorization: Bearer <chave>`. Chave revogada → 401
   (`POST /api/admin/caixas/{id}/revogar`; a lista em `GET /api/admin/caixas`).
4. A mais: com a chave, a caixa baixa a configuração do site (`GET /api/borda/configuracao`:
   faixas e câmeras, com a senha da câmera), como diz o SDD 7.4. Os ids são os da nuvem, em
   texto (SDD D-21).

**Verificar:** testes de código usado duas vezes, código vencido, chave revogada.

**Commit:** `feat(frota): ativação da caixa de borda e chave de acesso`

### Semana 3 — passagens e tela crua da portaria

#### T11. Receber passagens e fotos

**Objetivo:** a nuvem aceita passagens da caixa, sem duplicar, e guarda as fotos.

**Arquivos:** `nuvem/src/nuvem/portaria/{modelos.py,servico.py,rotas.py}`,
`nuvem/src/nuvem/armazenamento.py`, migração, testes.

**Regras (teste primeiro):**
- `POST /api/borda/passagens` valida com o pacote `contratos`. Passagem nova → 201. Mesmo `id`
  de novo → 200 sem criar outra (**reenvio seguro**). Passagem de outro site que não o da caixa
  → 403. A mais (SDD 3.2): `id` que já é de outra caixa → 409; faixa ou câmera de fora do site,
  ou sentido diferente do da faixa → 422, com o campo.
- Fotos: a API devolve um endereço de envio para cada `ref` (`POST /api/borda/fotos/endereco`).
  O envio vai para a interface `Armazenamento`, com duas implementações: `ArmazenamentoLocal`
  (pasta no disco, usada agora) e `ArmazenamentoS3` (mês 4, mesma interface). No local, o
  endereço leva um código cifrado que vale 15 minutos e a foto vai com `PUT`, sem a chave
  (SDD D-22); só JPEG, até 2 MB; a pasta vem da variável nova `PATIO_PASTA_FOTOS`.

**Verificar:** testes passam, incluindo o de envio repetido.

**Commit:** `feat(portaria): recebimento de passagens com reenvio seguro e fotos`

#### T12. Tela crua da portaria

**Objetivo:** ver as passagens chegando.

**Arquivos:** `nuvem/src/nuvem/web/` (Jinja + HTMX), tela `/portaria`. Entraram
`web/portaria.py`, as telas `portaria.html` e `portaria_passagens.html`, e o HTMX 2.0.11 em
`web/estatico/` (Zero-Clause BSD, com o hash; SDD 6.1). Dependência nova: `tzdata` (Apache-2.0),
para o fuso do site funcionar também no Windows, que não traz a base de fusos.

**Conteúdo:** lista das últimas passagens do site do usuário: horário, faixa, sentido, placas
com confiança e a foto da placa. Atualiza sozinha a cada 2 segundos (HTMX). A atualização por
SSE, prevista no SDD, entra no mês 3 junto com a tela definitiva. Detalhes: as últimas 50
passagens; o horário no fuso do site; a foto sai por `/portaria/fotos/{passagem}/{n}`, só para
quem vê o site; porteiro e gestor veem a tela; com a sessão vencida, o HTMX leva à tela de
entrar.

**Verificar:** logado como porteiro, ver uma passagem enviada à mão (`curl` ou teste) aparecer
em até 2 segundos.

**Commit:** `feat(web): tela crua da portaria com atualização automática`

### Semana 3–4 — leitor v0 e simulador

#### T13. Licenças dos pesos do leitor v0

**Objetivo:** cumprir a regra de licença antes de baixar qualquer modelo (SDD 4.1 e
`[ABERTO-12]`).

**O que verificar e registrar** em `docs/validacao/fatos-tecnicos-stack.md`:
- pesos pré-treinados do **D-FINE** (COCO) — licença dos arquivos de pesos, não só do código;
- modelos do **PaddleOCR** (detecção e reconhecimento de texto) e o pacote **RapidOCR**, que os
  distribui já em ONNX — licença dos pesos.

**Regra:** se algum peso não tiver licença clara permitindo uso comercial, ele só pode ser usado
em avaliação interna, e isso fica escrito. O leitor v1 (mês 2) usa pesos treinados por nós.

**Feito (2026-10-03):** D-FINE, YOLOX e fast-plate-ocr sem licença declarada dos pesos (só
avaliação interna); PaddleOCR e RapidOCR com Apache-2.0 declarada. A mais: a conferência das
rodas achou bibliotecas nativas GPL e LGPL (PyAV com x264/x265, OpenCV com FFmpeg, NumPy com
libquadmath), registradas como `[ABERTO-13]` no SDD; até a decisão, a caixa não lê vídeo.

**Commit:** `docs: licenças dos pesos do leitor v0`

#### T14. Regras puras do leitor (sem modelo)

**Objetivo:** as partes do leitor que são lógica, testadas sem câmera nem modelo.

**Arquivos:** `borda/src/borda/leitor/{interface.py,formato.py,votacao.py}`,
`borda/src/borda/composicao.py`, testes.

**Regras (teste primeiro):**
- `interface.py`: `LeitorDePlacas` (entra imagem, sai lista de `(texto, confiança, caixa)`).
  A "caixa" (o retângulo da placa na imagem) virou `Regiao`, porque "caixa" já é a caixa de
  borda. Dependência nova na borda: `numpy` (BSD), o tipo do quadro.
- `formato.py`: valida e corrige por posição (`0↔O`, `1↔I`, `8↔B`, `5↔S`); toda correção
  reduz a confiança (×0,9 por caractere); nunca inventa caractere (SDD 4.2).
- `votacao.py`: junta as leituras de vários quadros do mesmo veículo e escolhe a mais
  frequente, desempatando pela confiança. A confiança final é a média dos vencedores vezes a
  fração dos quadros que concordam (SDD 4.2).
- `composicao.py`: na mesma faixa, junta a placa lida pela câmera da frente (cavalo) com a lida
  pela câmera de trás (reboque) dentro de uma janela de tempo configurável (padrão 30 s).
  Regras completas no SDD 4.3. Desvio: o "reboque sem cavalo" sai com papel ~~`reboque`~~
  `desconhecido`, porque sem a frente a placa traseira pode ser do próprio cavalo (SDD D-23).

**Verificar:** `uv run tarefas test` com casos de borda (placa com troca, empate, reboque sem
cavalo, cavalo sem reboque).

**Commit:** `feat(borda): formato de placa, votação e composição`

#### T15. Leitor v0

**Objetivo:** um primeiro leitor que funcione sem treino próprio, só com pesos de licença
verificada na T13.

**Caminho:**
1. Detector de veículos ~~D-FINE-N~~ → **YOLOX-Tiny** pré-treinado (classes carro, moto,
   caminhão, ônibus) em ONNX Runtime. Desvio: o YOLOX publica o ONNX pronto; o D-FINE só tem
   `.pth` e pediria o PyTorch para exportar. Os dois têm pesos sem licença declarada (T13): só
   avaliação interna. A escolha do detector do v1 continua no `[ABERTO-03]`.
2. Recorte do veículo → detecção e leitura de texto (PaddleOCR ~~/RapidOCR~~ em ONNX).
   Desvio: o RapidOCR exige o OpenCV (`[ABERTO-13]`); o v0 usa os ONNX oficiais do PaddleOCR
   (PP-OCRv5 mobile, Apache-2.0) direto no ONNX Runtime, com o pré e o pós-processamento em
   NumPy e Pillow.
3. Filtro pelo formato de placa (T14), no rastreador (T16).
4. A mais: `uv run tarefas modelos` baixa os pesos para `modelos/v0` com o SHA-256 conferido.
   Dependências novas: `onnxruntime` (MIT) na borda; `httpx` (BSD) e `pyyaml` (MIT) no `ml`.

**Arquivos:** `borda/src/borda/leitor/v0.py`, `ml/src/ml/baixar_modelos.py` (baixa os pesos
para `modelos/`, confere o checksum; nada de pesos no Git).

**Verificar:** num punhado de imagens de teste rotuladas à mão (em `dados/`, fora do Git), o v0
lê a placa na maioria. **Não há meta de acerto no v0**: ele existe para o fluxo funcionar; o
acerto é trabalho do v1 no mês 2. Sem imagens reais ainda: a conferência com as fotos do
Lorenzo fica pendente; por enquanto, o v0 lê uma placa inventada, desenhada no teste.

**Commit:** `feat(borda): leitor v0 com modelos pré-treinados`

#### T16. Captura de vídeo e rastreamento

**Objetivo:** ler um vídeo (arquivo agora, câmera RTSP depois) e transformar a passagem de um
veículo numa leitura única.

**Arquivos:** `borda/src/borda/captura.py`, `borda/src/borda/rastreio.py`, testes.

**Regras:**
- `captura.py`: lê de arquivo ou RTSP com ~~PyAV~~, a uma taxa configurável (padrão 5
  quadros/s). Desvio: a roda do PyAV traz partes GPL (x264/x265) e o OpenCV traz o FFmpeg LGPL
  (SDD `[ABERTO-13]`, achado na T13). A captura ficou atrás de uma interface (`FonteDeQuadros`),
  com a amostragem e duas fontes: em memória e uma pasta de imagens (os quadros de um vídeo,
  tirados fora da caixa), que basta para a demonstração. Arquivo de vídeo e RTSP → depois da
  decisão do `[ABERTO-13]`. Dependência nova: `pillow` (MIT-CMU), que lê as imagens e grava o
  JPEG das fotos.
- `rastreio.py`: ~~ByteTrack (biblioteca supervision)~~ → rastreador nosso, por sobreposição,
  no estilo do ByteTrack (SDD D-25), porque o supervision exige o PyAV; segue cada veículo;
  quando o veículo sai da imagem, junta as leituras (votação) e gera uma placa lida, com o
  recorte para a foto. Veículo sem placa legível gera leitura sem placa (passagem vazia).

**Verificar:** um teste com um vídeo curto sintético (gerado no próprio teste, sem dado real)
produz exatamente uma leitura por veículo. O "vídeo" são quadros desenhados em memória: sem
decodificador de vídeo até o `[ABERTO-13]`.

**Commit:** `feat(borda): captura de vídeo e rastreamento`

#### T17. Fila de envio da borda

**Objetivo:** nenhuma passagem se perde se a internet cair.

**Arquivos:** `borda/src/borda/envio.py`, testes.

**Regras (teste primeiro):**
- Toda passagem é gravada primeiro num SQLite local, depois enviada. As fotos vão junto na
  fila e sobem antes da passagem (pelo endereço temporário da T11).
- Envio com tentativas e espera crescente (1 s, 2 s, 4 s… até 5 min).
- Só sai da fila quando a nuvem responde 201 ou 200. Desvio: a recusa definitiva (403, 409,
  422) também tira da fila, mas a passagem fica guardada à parte na caixa, com o motivo; senão,
  uma passagem errada travaria a portaria para sempre (SDD D-24).
- Envia na ordem em que as passagens aconteceram.
- Dependência nova na borda: `httpx` (BSD), o cliente HTTP previsto no SDD 6.1.

**Verificar:** teste com uma nuvem falsa que falha 3 vezes e depois aceita: a passagem chega uma
vez só.

**Commit:** `feat(borda): fila de envio com reenvio`

#### T18. Agente da borda e simulador de portaria

**Objetivo:** juntar captura → leitor → composição → fila num processo só, e usá-lo com vídeo
gravado como se fosse a caixa.

**Arquivos:**
- `borda/src/borda/agente.py`: o processo principal da caixa (configuração: faixas, câmeras,
  endereço da nuvem, chave). Entrou o `Agente` (rastreador por câmera de placa, composição por
  faixa, passagem com `id` novo e foto da placa em JPEG na fila) e `rodar`, que junta as
  câmeras na ordem do tempo. Falta o executável da caixa de verdade, que lê as câmeras (RTSP):
  espera o `[ABERTO-13]`.
- `ferramentas/src/simulador/__main__.py`: `uv run simulador ~~--video <arquivo>~~ --faixa
  entrada-1 --camera frente` roda o agente sobre o arquivo; também aceita
  `--passagens <arquivo.json>` para mandar passagens prontas, sem visão computacional.
  Desvio: o vídeo espera o `[ABERTO-13]`; no lugar, `--quadros <pasta>` roda o agente sobre as
  imagens de uma pasta. A mais: `--codigo` e `--demonstracao` (ativação, só local), `amostra`
  (três passagens inventadas, com uma foto de placa desenhada), a chave e a fila em
  `dados/simulador/`. Na nuvem, a mais: `GET /api/admin/sites`, para a demonstração achar o
  site sozinha.

**Verificar:** com o ambiente local no ar, o simulador manda passagens que aparecem na tela da
portaria. Feito em 2026-10-03 com `--demonstracao --passagens amostra`.

**Commit:** `feat(ferramentas): agente da borda e simulador de portaria`

### Semana 4 — demonstração e bancada

#### T19. Vídeos de amostra e demonstração do marco

**Objetivo:** cumprir o marco do mês.

**Passos:**
1. Gravar de 10 a 20 passagens de caminhão **com autorização** (por exemplo, no pátio de uma
   transportadora conhecida), com aviso de gravação, sem foco em rostos. Guardar em
   `dados/amostras/` (fora do Git), com uma ficha simples de quem autorizou e quando.
2. `uv run tarefas demo`: sobe tudo, cria os dados de demonstração e roda o simulador com uma
   amostra.
3. Escrever `docs/guias/demo-mes-1.md` com o passo a passo e uma captura da tela.

**Verificar:** o marco da seção 1, executado do zero numa máquina limpa seguindo só o guia.

**Situação (2026-10-03):**
- passo 1 (gravar os vídeos com autorização) é do Lorenzo, e falta;
- passo 2: `uv run tarefas demo` sobe tudo, migra, semeia e roda o simulador com a **amostra de
  passagens inventadas** (fotos de placa desenhadas). Com vídeo, depois do `[ABERTO-13]`; até
  lá, o simulador lê os quadros de uma pasta (`--quadros`);
- passo 3: `docs/guias/demo-mes-1.md` escrito, com a captura da tela;
- o marco com vídeo gravado depende do passo 1 e do `[ABERTO-13]`.

**Commit:** `docs: guia da demonstração do mês 1`

#### T20. Kit de bancada e primeira medição de desempenho

**Objetivo:** medir o leitor v0 no hardware real (insumo para `[ABERTO-03]` no mês 2).

**Kit:** mini PC Intel N150 16 GB, 2 câmeras IP 4 MP, switch PoE, cabos.

**Passos:**
1. Ubuntu Server 24.04 + Docker no mini PC; instalar o agente.
2. Medir com o OpenVINO e com o ONNX Runtime: quadros por segundo por câmera, uso de CPU,
   temperatura.
3. Registrar em `docs/validacao/fatos-tecnicos-stack.md` (seção "medições próprias").

**Commit:** `docs: primeira medição do leitor v0 no N150`

---

## 4. Trilha não técnica (comercial e burocracia)

Coisas que levam tempo de calendário: começar na **semana 1**.

| # | Tarefa | Por quê | Resolve |
|---|---|---|---|
| N1 | Pedir a **verificação da empresa na Meta** (Business Manager) e criar o app da Cloud API do WhatsApp | a verificação demora e libera o limite de 2.000 destinatários/dia | prepara o mês 4 |
| N2 | Criar a conta **AWS** com alerta de gasto | evita surpresa de custo | prepara o mês 4 |
| N3 | Reunião com **advogado**: modelo de contrato, acordo de tratamento de dados (LGPD) e prazos de guarda | o jurídico do cliente vai pedir | `[ABERTO-04]`, `[ABERTO-07]` |
| N4 | Escolher o **nome do produto** e registrar o domínio | as conversas comerciais precisam de nome | `[ABERTO-01]` |
| N5 | Escrever o **roteiro das conversas** (só fatos passados: quantos postos, quanto custam, contrato de portaria, o que o seguro exige) e começar as 15–25 conversas | é o teste com comprador do Test Card | `[ABERTO-06]` |
| N6 | Achar o **site parceiro** que cede uma portaria para gravar no mês 2 | sem ele não há dados para treinar | prepara o mês 2 |
| N7 | **Comprar o hardware** da bancada (T20) e o do site parceiro | prazo de entrega | prepara o mês 2 |
| N8 | Começar o **guia de posicionamento das câmeras** a partir da bancada | define altura e ângulo por tipo de portaria | `[ABERTO-08]` |

---

## 5. Ajustes no SDD feitos junto com este plano

- `[ABERTO-11]` (fila de tarefas no PostgreSQL) passa para o **mês 2**: o worker só é necessário
  quando entrar o casamento com o agendamento.
- **04/10, SDD 0.15:** `[ABERTO-12]` e `[ABERTO-13]` decididos (D-26 e D-27). Pesos de terceiros
  servem só para comparar e avaliar; bibliotecas nativas LGPL entram sem modificação, e o FFmpeg
  sem partes GPL. Com isso, o que esperava o `[ABERTO-13]` (vídeo e RTSP na caixa, o executável
  da caixa e o `simulador --video`) deixa de esperar e vira a próxima tarefa.
- **04/10, SDD 0.16:** a caixa lê vídeo pelo OpenCV sem interface gráfica (D-29): câmera (RTSP)
  e arquivo, e o `simulador --video`. Novo `[ABERTO-14]`: o OpenSSL 1.1.1w dentro da roda do
  OpenCV para Linux. O programa da caixa (ativação, câmeras RTSP e envio) vem na tarefa seguinte.
- **04/10, SDD 0.17:** o programa da caixa (`caixa ativar` e `caixa rodar`): ativação, câmeras
  RTSP da configuração, agente e envio (D-30). Saúde, atualização e o contêiner da caixa seguem
  no mês 3, como no cronograma.
- **04/10, SDD 0.18:** `[ABERTO-14]` decidido (D-31): o OpenSSL que vem no OpenCV para Linux é
  aceito, com o crédito em `borda/AVISOS-DE-TERCEIROS.md`.

---

## 6. Checklist de "mês 1 pronto"

- [ ] `uv sync` e `uv run tarefas check` passam numa máquina limpa.
- [ ] CI verde na `main`, com checagem de licenças e vulnerabilidades.
- [ ] `contratos` com a Passagem v1, JSON Schema gerado e testado.
- [ ] Nuvem com cadastro, login, papéis, separação por empresa (com o teste de vazamento) e
      ativação da caixa.
- [ ] Recebimento de passagens com reenvio seguro e fotos no armazenamento local.
- [ ] Leitor v0 com pesos de licença verificada; regras de formato, votação e composição
      testadas.
- [ ] Fila de envio da borda testada com falha de rede.
- [ ] **Marco:** `uv run tarefas demo` mostra uma passagem de vídeo gravado na tela da portaria.
- [ ] Medição do v0 no N150 registrada.
- [ ] Trilha não técnica: N1–N3 iniciados; N4 decidido; pelo menos 5 conversas feitas; site
      parceiro em negociação; hardware comprado.

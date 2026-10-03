# SDD — patio-br (nome provisório)

**Documento de desenho do software (SDD) do MVP do piloto**
Versão 0.11 · 2026-10-03 · Situação: aprovado como base; itens em aberto na seção 12

---

## 0. Como usar este documento

Este é o documento-base do projeto. Ele diz **o que** vamos construir, **como** as peças se
encaixam e **por que** cada escolha foi feita. Tudo o que for construído deve caber aqui; se
não couber, o documento muda primeiro.

Regras para completar e manter:

1. **Linguagem simples.** Se um termo técnico for inevitável, ele está no glossário (seção 13).
2. **Toda decisão tem motivo.** Decisões ficam registradas na seção 11, com a alternativa
   descartada. Mudar uma decisão = nova linha no registro, nunca apagar a antiga.
3. **O que ainda não foi decidido fica marcado como `[ABERTO-nn]`** e listado na seção 12,
   com quando e como será decidido. Nenhum item aberto é resolvido "no código" sem passar por
   aqui.
4. **Números vêm com fonte e data.** Os números de mercado e de preço vêm da validação
   (`docs/validacao/`), verificados em 2026-09-29.
5. Cada mudança relevante entra no histórico de versões (fim do documento).

---

## 1. Visão do produto

### 1.1 O problema

Em centros de distribuição (CDs), indústrias e terminais, o caminhão espera muito para
carregar ou descarregar, e quase ninguém mede quanto isso custa para o dono do site:

- Na Grande São Paulo, o tempo médio de descarga foi de **5h09 em 2025**, e de **11h40 em CDs**
  (SETCESP/IPTC).
- A portaria é feita por pessoas: um ponto de portaria 24 horas custa de **R$ 21,5 mil a
  R$ 36,9 mil por mês** (contrato da CEAGESP e tabela CADTERC de SP). O porteiro lê documento,
  digita placa e faz triagem visual.
- Os aplicativos que pedem ao motorista para fazer check-in têm reclamações repetidas
  (cadastro que trava, SMS que não chega, placa Mercosul não aceita).
- **Nenhum** sistema de pátio, no Brasil ou fora, entrega ao cliente a **economia realizada**
  medida dentro do produto; só existem calculadoras de venda.

### 1.2 A proposta

Um sistema de pátio com três pilares:

1. **Check-in automático, sem aplicativo.** A câmera lê as placas do caminhão (cavalo e
   reboques), o sistema casa com o agendamento do dia e registra a chegada sozinho. O motorista
   só recebe mensagens no WhatsApp.
2. **Extrato mensal de economia em R$.** Todo mês o gestor recebe quanto tempo de espera caiu,
   quanto da exposição a estadia foi evitada, quantas horas de portaria foram poupadas e como
   as docas foram usadas, comparando com a linha de base medida antes.
3. **Hardware barato.** Câmeras IP comuns (~R$ 881 cada) e um mini PC na portaria (~R$ 3,5 mil),
   com modelos de leitura de placa treinados por nós em placas brasileiras.

### 1.3 Para quem

Sites com **portaria 24 horas e cerca de 80 caminhões por dia ou mais**: CDs de varejo e
atacado, indústrias, operadores logísticos e terminais. Operações pequenas não são o alvo
(a validação mostrou que o hardware e a instalação não se pagam nelas).

### 1.4 Os dois modos de operação

| Modo | Como funciona | No MVP? |
|---|---|---|
| **A — motorista espera** | o motorista fica com o caminhão na fila até carregar/descarregar | **sim, é o foco** |
| **B — carreta solta** | a carreta é deixada no pátio sem o cavalo e um manobrista a leva à doca | não; a arquitetura e os dados já preveem (Fase 2) |

O modo usado varia de cliente para cliente; o sistema deve atender os dois no futuro.

### 1.5 O que o piloto precisa provar

Os critérios vêm do "Test Card" da validação (`docs/validacao/relatorio-validacao-v3.md`):

- **≥ 95%** das composições (cavalo + reboques) identificadas corretamente, casando com o
  agendamento;
- **≥ 70% das chegadas agendadas** fazem check-in **sem ação do porteiro** (meta inicial,
  revisável após o modo sombra);
- o cliente **reduz horas de posto de portaria** (meta: ≥ 1 ponto 24x7 ou ≥ 40% das
  horas-posto em 90 dias);
- o cliente aceita pagar **≥ R$ 8 mil por mês por site** (piloto anual pré-pago).

---

## 2. Escopo do MVP do piloto

### 2.1 Quem usa e o que pode fazer

| Papel | Onde usa | O que pode fazer |
|---|---|---|
| **Porteiro** | tablet na portaria | ver chegadas e saídas ao vivo; resolver a fila de exceções; registrar chegada manual quando uma câmera falha |
| **Líder de pátio** | tablet ou PC | ver a fila; chamar caminhão para a doca; marcar início e fim de carga/descarga |
| **Gestor do site** | PC | tudo do porteiro e do líder no seu site; agendamentos; importar planilha; gerar link da transportadora; indicadores; extrato; parâmetros do site |
| **Transportadora** | celular, sem login | agendar pelo link recebido |
| **Motorista** | WhatsApp (ou SMS) | confirmar o agendamento e receber avisos de fila e doca. Não instala nada |
| **Administração (nós)** | PC | empresas, sites, câmeras, caixas de borda, usuários, rotulagem da base de treino |

### 2.2 A jornada de um caminhão (modo A)

1. **Agendamento.** Vem pelo link da transportadora ou pela planilha do cliente. Contém: data e
   janela, placas esperadas (cavalo e reboques), motorista e celular, tipo (carga ou descarga),
   toneladas e, se houver, a chave da NF-e.
2. **Confirmação.** O motorista recebe um WhatsApp para confirmar; ao responder, autoriza
   receber as próximas mensagens.
3. **Chegada.** A câmera lê as placas; a caixa de borda monta a composição; a nuvem casa com o
   agendamento. Se casar, o **check-in é automático**: a hora de chegada fica registrada como
   prova e o motorista recebe "você está na fila, posição X". Se ficar em dúvida ou não houver
   agendamento, vira **exceção** para o porteiro resolver com um toque.
4. **Chamada.** O líder chama; o motorista recebe "vá para a doca 7".
5. **Doca.** Início e fim marcados com um toque no painel.
6. **Saída.** A câmera da saída lê a placa e fecha a visita.
7. **Mês.** O extrato é gerado sozinho.

### 2.3 Dentro e fora do MVP

**Dentro:** agendamento (link + planilha + API genérica), check-in automático, fila de
exceções, fila e docas (marcação manual), WhatsApp com SMS de reserva, alertas, indicadores,
extrato mensal, trilha de prova, frota de borda, base de treino, API e webhooks.

**Fora (com o terreno preparado):**

| Item | Por que fica fora | Quando |
|---|---|---|
| Modo B (mapa do pátio, missões de manobra) | exige câmera nos veículos de manobra e não tem cifra brasileira que o sustente ainda | Fase 2 |
| Câmeras nas docas e sugestão automática de doca | hardware extra por site | Fase 2 |
| Conferência de carga e lacre por câmera | outro problema de visão computacional | Fase 3 |
| Segurança (perímetro, identidade do motorista, risco da transportadora) | escopo grande | Fase 3 |
| Conectores TOTVS, SAP, Senior | variam por cliente | sob demanda |
| Leitura de CNH e CRLV | não é exigida por norma em CD privado | Fase 2+ |
| Reconhecimento facial | risco LGPD (dado biométrico) | não por padrão, em nenhuma fase |
| App nativo e cobrança automática | o PWA resolve; poucos clientes no início | depois do piloto |

### 2.4 O MVP está pronto quando

- O fluxo completo (agendado → saiu) roda no simulador e no site piloto.
- O leitor atinge as metas da seção 4.7 na régua fixa e no modo sombra.
- A internet pode cair sem perda de eventos.
- O primeiro extrato mensal real é entregue ao gestor.

---

## 3. Arquitetura

### 3.1 Visão geral

```
PORTARIA DO CLIENTE                              NUVEM (AWS, São Paulo)
┌────────────────────────────┐                   ┌──────────────────────────────┐
│ Câmeras IP comuns (RTSP)   │                   │ API (Python/FastAPI)         │
│  entrada: frente + traseira│                   │  recebe passagens da borda   │
│  saída: traseira           │   passagens +     │  serve o painel e os links   │
│            │               │   fotos recortadas│  recebe respostas do WhatsApp│
│            ▼               │   (HTTPS, saída)  │                              │
│ Caixa de borda (mini PC)   │ ────────────────▶ │ Worker (tarefas de fundo)    │
│  1 captura o vídeo         │                   │  casamento, mensagens,       │
│  2 lê as placas            │                   │  planilhas, extrato, alertas │
│  3 monta a composição      │                   │                              │
│  4 guarda e envia (fila)   │                   │ PostgreSQL + fotos (S3)      │
└────────────────────────────┘                   └──────────────────────────────┘
        ▲ acesso remoto (Tailscale)                ▲            ▲           ▲
                                          Painel web (PWA)   WhatsApp    Link da
                                          porteiro, pátio,   (Meta)      transportadora
                                          gestor, admin
```

**Princípio central:** a **borda lê**, a **nuvem decide**. A caixa de borda processa o vídeo
no local e manda para a nuvem apenas a **passagem** (alguns KB por caminhão). Vídeo nunca sai
do site. Isso economiza banda, dispensa GPU na nuvem e mantém a portaria funcionando com a
internet instável.

### 3.2 O contrato entre borda e nuvem: a Passagem

A passagem é o único formato que a borda envia. Ela fica no pacote `contratos/`, usado pelos
dois lados. Mudou o formato → muda a versão do contrato.

```json
{
  "versao_contrato": 1,
  "id": "6f1c2c9e-8a0b-4c55-9b1e-2f0a3d4e5b6c",
  "caixa_id": "cx-0001",
  "site_id": "site-0001",
  "faixa_id": "entrada-1",
  "sentido": "entrada",
  "inicio": "2026-11-03T14:02:11.120-03:00",
  "fim": "2026-11-03T14:02:19.480-03:00",
  "placas": [
    {"placa": "ABC1D23", "papel": "cavalo",  "confianca": 0.98, "camera_id": "cam-frente-1", "quadros": 7},
    {"placa": "XYZ9876", "papel": "reboque", "confianca": 0.91, "camera_id": "cam-tras-1",   "quadros": 5}
  ],
  "fotos": [
    {"tipo": "placa",    "camera_id": "cam-frente-1", "ref": "fotos/2026/11/03/6f1c...-1.jpg"},
    {"tipo": "contexto", "camera_id": "cam-tras-1",   "ref": "fotos/2026/11/03/6f1c...-2.jpg"}
  ],
  "versao_leitor": "1.0.0"
}
```

- `id` é gerado na caixa. A nuvem ignora um `id` já recebido, então a caixa pode reenviar
  sem duplicar.
- **Recebimento** (`POST /api/borda/passagens`, com a chave da caixa):
  - passagem nova → **201**; o mesmo `id` de novo, da mesma caixa → **200**, sem criar outra;
  - `caixa_id` ou `site_id` que não são os da chave → **403**;
  - `id` que já é de outra caixa → **409**;
  - faixa ou câmera que não são do site, ou sentido diferente do da faixa → **422**, dizendo
    qual campo.
- `caixa_id`, `site_id`, `faixa_id` e `camera_id` são os identificadores da nuvem, em texto
  (ex.: `"12"`), que a caixa recebe na ativação e na configuração (D-21). Os nomes do exemplo
  acima são só ilustração.
- Os horários são da caixa (sincronizada por NTP) e são a prova da chegada.
- As fotos sobem direto para o armazenamento com um endereço temporário fornecido pela API; a
  passagem só referencia (D-22):
  - a caixa pede o endereço para cada `ref` (`POST /api/borda/fotos/endereco`) e envia a foto
    com `PUT` nesse endereço, que vale 15 minutos e não precisa da chave (como no S3);
  - o `ref` é escolhido pela caixa (letras, números, `.`, `_`, `-` e `/`, sem `..`), e a foto
    fica guardada dentro da pasta da própria caixa: uma caixa nunca alcança a foto de outra;
  - só JPEG, até 2 MB;
  - a foto não se edita: reenviar a mesma foto responde 200; uma foto diferente no mesmo `ref`
    responde 409;
  - a nuvem não confere, ao receber a passagem, se as fotos já chegaram: a tela mostra a foto
    quando ela existir.
- Rostos nas fotos de contexto são borrados na caixa, antes de enviar.
- A passagem traz **só o que a caixa viu**. A placa que nenhuma câmera viu (o reboque do meio
  de um bitrem) é completada pela nuvem e fica na visita (seção 4.3).

### 3.3 Módulos da nuvem no MVP

A nuvem é um **monólito modular**: um só sistema, dividido em módulos com uma função cada.
Um módulo só usa outro pelas funções de serviço dele, nunca acessando as tabelas alheias.

| Módulo | O que faz | Equivalente na Terminal Industries |
|---|---|---|
| `cadastro` | empresas, sites, portarias, faixas, câmeras, docas, usuários, permissões | base do sistema |
| `agendamento` | agendamentos e **conectores**: link próprio, planilha, API genérica | (usa o do cliente) |
| `portaria` | recebe passagens, casa com agendamento, check-in, exceções, saída | Gate Management |
| `patio` | fila, chamada, docas, início e fim | Dispatch / Dock (manual) |
| `mensagens` | WhatsApp oficial (Meta) e SMS de reserva | Driver communication |
| `alertas` | perto de 5h, chegada sem agendamento, câmera ou caixa fora do ar | parte do YOS |
| `extrato` | indicadores e extrato mensal em R$ | Analytics / ROI |
| `prova` | trilha de eventos que não se edita | Chain of custody |
| `frota` | saúde e versão das caixas de borda e câmeras | gestão de dispositivos |
| `treino` | correções do porteiro viram imagens rotuladas | (interno) |
| `api_publica` | API e webhooks para integrações | integrações WMS/TMS |

### 3.4 Conectores de agendamento

Cada origem de agendamento é um **conector** com a mesma interface: recebe dados de fora e
entrega agendamentos no formato interno, com `origem` e `codigo_externo` preenchidos. No MVP:
`link`, `planilha`, `api_generica`. Depois: `totvs`, `sap`, `senior`, `fleetbase` (previsão de
chegada), cada um um conector novo, sem mudar o resto.

### 3.5 Fases futuras (já previstas)

| Fase | Módulos |
|---|---|
| Fase 2 | mapa do pátio e missões de manobra (modo B); câmeras nas docas e sugestão de doca; leitura de CNH/CRLV |
| Fase 3 | conferência de carga e lacre; segurança (perímetro, identidade, risco) |
| Sob demanda | conectores de ERP |

Cada módulo futuro "escuta" os mesmos eventos de passagem e visita. A borda e o contrato não
mudam.

---

## 4. Leitor de placas

### 4.1 Regra de licença

Em produção, só entram **código e modelos com licença Apache-2.0, MIT ou BSD, com pesos
treinados por nós**. O YOLO da Ultralytics (AGPL-3.0) fica de fora: usá-lo num produto fechado
exige licença Enterprise, sem preço publicado. Pesos de terceiros com licença incerta podem ser
usados só em avaliação interna, nunca no produto.

### 4.2 O caminho de cada câmera, dentro da caixa

| Passo | O que faz | Ferramenta (licença) |
|---|---|---|
| 1. Captura | puxa o vídeo (RTSP) e só processa quando há veículo na faixa | FFmpeg/PyAV + go2rtc (MIT) |
| 2. Detecção | acha o veículo e a placa no quadro | D-FINE-N ou YOLOX-Tiny (Apache-2.0) — `[ABERTO-03]` |
| 3. Rastreamento | segue o mesmo veículo entre quadros | ByteTrack + supervision (MIT) |
| 4. Leitura (OCR) | lê os caracteres da placa | modelo leve no estilo do fast-plate-ocr (código MIT), com pesos nossos |
| 5. Votação | junta as leituras de vários quadros e fica com a mais confiável | código nosso |
| 6. Formato | valida e corrige pela posição dos caracteres | código nosso |
| 7. Composição | junta cavalo (câmera da frente) e reboque (câmera de trás) numa passagem | código nosso |

**Formatos de placa aceitos:**

- antiga: três letras e quatro números (`ABC1234`);
- Mercosul: três letras, um número, uma letra, dois números (`ABC1D23`).

Correções por posição: onde só cabe letra, `0→O`, `1→I`, `8→B`, `5→S`; onde só cabe número, o
inverso. A correção é registrada na passagem (confiança menor).

- **Formato:** só os separadores (espaço, `-`, `.`, `·`) são retirados. Texto que não fica com 7
  caracteres, ou com um caractere que não cabe na posição e não tem correção, é descartado: o
  leitor nunca inventa nem apaga caractere. Cada caractere corrigido multiplica a confiança por
  0,9. A 5ª posição aceita letra e número (antiga e Mercosul) e nunca é corrigida.
- **Votação:** fica a placa lida em mais quadros; no empate, a de maior confiança média. A
  confiança final é a média das confianças dos quadros vencedores vezes a fração dos quadros
  que concordam (ex.: 4 de 5 quadros a 0,95 → 0,95 × 0,8 = 0,76). `quadros` na passagem é o
  número de quadros vencedores.

### 4.3 Composições e o que a câmera não vê

- Pela regra do CONTRAN, reboques só têm placa traseira. A câmera da frente lê o cavalo; a de
  trás lê o último reboque.
- No bitrem, a placa do reboque do meio quase nunca aparece. Se cavalo e último reboque batem
  com um agendamento do dia, a nuvem, no casamento, completa o meio a partir dele e registra na
  composição da visita que essa placa foi **inferida**, e não lida. A passagem não muda: a caixa
  não conhece os agendamentos e só envia o que viu.
- **Composição na caixa**, por faixa, com uma janela de tempo (padrão 30 s):
  - a leitura da câmera da frente é o **cavalo**, e espera a de trás até o fim da janela;
  - a leitura de trás, com placa **diferente** da frente, é o **reboque** da composição mais
    recente da faixa, que se fecha ali. As mais antigas que ainda esperavam saem sozinhas;
  - a leitura de trás **igual** à da frente é a placa traseira do mesmo veículo, sem reboque: a
    composição se fecha só com o cavalo;
  - a leitura de trás **sem** nenhuma da frente na janela sai com papel **desconhecido**: sem a
    frente, não dá para saber se é um reboque ou o próprio cavalo (D-23);
  - a leitura da frente que chega ao fim da janela sem a de trás sai sozinha, como cavalo.

### 4.4 Onde roda

- **Mini PC Intel N150, 16 GB de RAM, 512 GB de disco** (~R$ 3,5 mil), com **OpenVINO**
  (Apache-2.0) usando a GPU integrada.
- Referência publicada (documentação do Frigate): detectores leves do mesmo porte (YOLOv9 t/s a
  320 px) levam 16–30 ms por quadro no N150/N100. D-FINE-N e YOLOX-Tiny ainda precisam ser
  medidos no N150 (`[ABERTO-03]`).
- Caminhão na portaria anda devagar: **3 a 5 quadros por segundo por câmera** durante a
  passagem bastam.
- Se faltar velocidade: subir para um mini PC Core i5 com GPU integrada mais forte (~R$ 4,1 mil
  em loja brasileira, 2026-09-29) ou usar um acelerador Hailo em formato M.2. Atenção: a versão
  M.2 do Hailo não foi encontrada à venda no Brasil; só a versão para Raspberry Pi (~R$ 855).
- Modelos são exportados para **ONNX**; rodam igual no PC de desenvolvimento e na borda.

### 4.5 Interface única e dois motores

O leitor fica atrás da interface `LeitorDePlacas` (entra imagem, sai lista de placas com
confiança). Motores:

| Motor | Papel | Custo |
|---|---|---|
| **Próprio** (seções 4.2–4.4) | principal | hardware + treino |
| **Comercial** (Plate Recognizer) | régua no teste técnico; segunda opinião para leitura de baixa confiança quando houver internet; plano B do piloto | US$ 50/mês por 50 mil leituras (preço de 2026-09-29) |

Trocar de motor não muda nada fora da caixa.

### 4.6 Dados de treino

O banco público brasileiro (RodoSol-ALPR) só permite uso acadêmico. Por isso:

1. **Semanas 1–4 do site parceiro:** as câmeras gravam (com aviso LGPD, sem operar). Rotulamos
   3 a 5 mil placas no Label Studio.
2. **Depois:** cada correção do porteiro na fila de exceções vira um rótulo novo (módulo
   `treino`), após revisão na tela de rotulagem.
3. **Treino:** PyTorch em GPU alugada por hora, só quando há dados novos. Exporta ONNX →
   OpenVINO.
4. A base de treino guarda **só recortes de placa**, nunca rostos.

### 4.7 Metas e a régua

- **Leitura por placa visível:** ≥ 97% correta.
- **Composição casando com o agendamento:** ≥ 95% correta.
- Abaixo do limite de confiança, a passagem **vira exceção**, nunca entra errada.
- **Régua fixa:** um conjunto de imagens rotuladas que **nunca** entra no treino. Um modelo novo
  só vai para produção se **não piorar** nem o acerto por placa nem o por composição nessa régua.

---

## 5. Dados

### 5.1 Entidades

| Entidade | Campos principais |
|---|---|
| `Empresa` | nome, CNPJ |
| `Site` | empresa, nome, endereço, fuso, horário de operação |
| `Portaria` / `Faixa` / `Camera` | site; faixa tem sentido (entrada/saída); câmera tem posição (frente/trás/contexto), endereço RTSP, senha cifrada |
| `Doca` | site, nome, situação |
| `Usuario` | empresa, nome, e-mail, papel (porteiro, pátio ou gestor), sites com acesso, senha, PIN (porteiro), ativo, verificação em duas etapas (gestor) |
| `Administrador` | nome, e-mail, senha, ativo, verificação em duas etapas; é a administração (nós), fora de qualquer empresa (D-19) |
| `Agendamento` | site, janela início/fim, tipo (carga/descarga), placas esperadas (cavalo, reboques), motorista (nome, celular), autorização de WhatsApp, toneladas, chave NF-e (opcional), `origem`, `codigo_externo`, situação |
| `Veiculo` | placa, tipo (cavalo, reboque, caminhão simples); campo de posição no pátio reservado para o modo B |
| `Passagem` | formato da seção 3.2 |
| `Visita` | site, agendamento (opcional), composição confirmada (cada placa marcada como lida ou inferida), estado, horários de cada etapa, doca |
| `Evento` | visita, tipo, horário, autor (sistema ou usuário), dados, foto — **só se acrescenta** |
| `Excecao` | passagem, motivo, candidatos, situação, resolução, quem resolveu |
| `Mensagem` | visita, canal, modelo, situação (enviada, entregue, lida, falhou), custo |
| `ParametrosSite` | custo mensal de um ponto de portaria, postos antes/depois, valor da estadia (R$/t·h), franquia (h), tolerância de janela, horas para alerta, custo hora-doca (opcional) |
| `Extrato` | site, mês, números calculados, versão da regra de cálculo |
| `CaixaBorda` | site, versão instalada, último contato, saúde, chave de acesso (só o resumo), ativada em, revogada em |
| `CodigoAtivacao` | site, resumo do código, criado por (administração), vence em, usado em |
| `Rotulo` | recorte, placa correta, origem (correção ou rotulagem), revisado |

Toda tabela de dados do cliente tem `empresa_id`. Toda consulta filtra por empresa.

### 5.2 Estados da visita

```
AGENDADA ──entrada casou──▶ NA_FILA ──chamada──▶ CHAMADA ──▶ NA_DOCA ──fim──▶ LIBERADA ──saída──▶ SAIU
   │                           ▲
   └─ janela + tolerância ─▶ NAO_VEIO
passagem sem casamento ─▶ EXCECAO ─porteiro resolve─┘   (ou RECUSADA)
```

- `NAO_VEIO`: fim da janela + tolerância (padrão 4h, parâmetro do site) sem chegada.
- Visita sem agendamento (o porteiro aceita uma exceção sem agendamento) é criada já em
  `NA_FILA`, com `agendamento = vazio`.
- Saída sem passar pela doca é registrada como `SAIU` com o evento "saiu sem atendimento".

### 5.3 Casamento da chegada com o agendamento

Candidatos: agendamentos do site em `AGENDADA` com janela no dia (± tolerância).

Pontuação inicial (os pesos e o limite são ajustados com os dados do mês 2 — `[ABERTO-02]`):

| Critério | Pontos |
|---|---|
| placa do cavalo idêntica | 60 |
| placa do cavalo com 1 caractere de troca fácil (O/0, I/1, B/8, S/5) | 40 |
| cada placa de reboque idêntica (máximo 2) | 20 |
| chegada dentro da janela | 20 |
| chegada dentro da tolerância | 10 |

- **Check-in automático:** um candidato com ≥ 80 pontos e pelo menos 20 pontos à frente do
  segundo.
- **Exceção:** nenhum candidato acima de 80, ou dois candidatos próximos.
- **Saída:** a placa do cavalo fecha a visita aberta do mesmo site.

### 5.4 Contas do extrato

- **Espera** = hora da chamada − hora da chegada.
- **Tempo de estadia** = hora de liberação − hora da chegada (a lei conta as 5h desde a chegada).
- **Exposição a estadia (R$)** = horas acima da franquia × toneladas × valor (R$ 2,50/t·h em
  2026, parâmetro do site).
- **Uso das docas** = horas ocupadas ÷ horas de operação; em R$ só se o cliente informar o custo
  hora-doca.
- **Portaria** = (horas-posto antes − horas-posto depois) × custo da hora-posto
  (método de medição em `[ABERTO-05]`).
- **Linha de base:** as mesmas medidas, colhidas no **modo sombra** (seção 9), antes de o sistema
  substituir o processo manual. O extrato compara o mês com a linha de base.
- Cada extrato guarda a **versão da regra de cálculo**, para ser refeito igual depois.

### 5.5 Garantias

- **Reenvio seguro:** passagem com `id` repetido é ignorada.
- **Prova:** horários e fotos não se editam. Correção = evento novo; a leitura original fica.
- **Separação de clientes:** nenhuma consulta sem filtro de empresa; testes tentam furar isso.
  O banco também garante: cada tabela filha aponta para o pai pela dupla (pai, empresa), então
  não aceita, por exemplo, uma portaria de uma empresa num site de outra.

---

## 6. Aplicativo e código

### 6.1 Stack

| Camada | Escolha |
|---|---|
| Linguagem | **Python 3.12** em tudo (borda, nuvem, treino) |
| Backend | FastAPI, SQLAlchemy 2 com o driver pg8000, Alembic (migrações), Pydantic 2 |
| Banco | PostgreSQL 16; fila de tarefas no próprio PostgreSQL (`[ABERTO-11]`) |
| Painel | páginas no servidor (Jinja) + **HTMX**; atualização ao vivo por SSE; instalável como **PWA** |
| Gráficos | biblioteca JavaScript pequena, só onde houver gráfico |
| Borda | PyAV/FFmpeg, go2rtc, OpenVINO, supervision/ByteTrack, SQLite (fila local), httpx |
| Treino | PyTorch, Label Studio, exportação ONNX → OpenVINO |
| Qualidade | ruff, mypy, pytest; checagem de licenças e vulnerabilidades das dependências |

Toda dependência precisa de licença permissiva (MIT, BSD, Apache, PostgreSQL, ISC, PSF). MPL-2.0 só é aceita para biblioteca usada sem modificação (ex.: `certifi`). GPL, LGPL e AGPL ficam de fora. A CI checa.

Arquivos de terceiros que o painel serve (o HTMX, licença Zero-Clause BSD) ficam no repositório,
em `nuvem/src/nuvem/web/estatico/`, com a versão no nome, a licença e o hash conferido, e não
num CDN: o tablet da portaria não depende de outro servidor. A CI não vê esses arquivos; a
licença deles é conferida à mão, como a dos modelos.

### 6.2 Telas do MVP

| Tela | Quem | Conteúdo |
|---|---|---|
| Portaria | porteiro | chegadas ao vivo com foto; **fila de exceções** em cartões (foto, candidatos, "é este" / "corrigir"); saídas; registro manual |
| Pátio e docas | líder | fila por tempo de espera; docas livres/ocupadas; chamar / iniciar / finalizar; alerta perto de 5h |
| Gestor | gestor | indicadores (espera média, visitas acima de 5h, % de check-in automático, uso de docas); extrato do mês (PDF e planilha) |
| Agendamentos | gestor | lista; importar planilha com modelo e relatório de erros por linha; gerar link da transportadora |
| Link da transportadora | transportadora | formulário curto para celular: placas, motorista, celular, janela, toneladas, NF-e opcional |
| Administração | nós | empresas, sites, câmeras, caixas (saúde), usuários, parâmetros, rotulagem |

### 6.3 Repositório

```
patio-br/
  docs/          SDD, decisões, guias de operação, validação
  contratos/     formatos compartilhados (Passagem, eventos) — pacote Python
  borda/         agente da caixa: captura, leitor, composicao, envio, saude, atualizacao
  nuvem/
    app/         cadastro, agendamento, portaria, patio, mensagens, alertas, extrato,
                 prova, frota, treino, api_publica, web (telas)
    migracoes/   Alembic
  ml/            treino, avaliação (régua e teste técnico), exportação de modelos
  infra/         docker-compose, deploy, preparação da caixa de borda
  ferramentas/   simulador de portaria, planilhas de exemplo
```

Cada módulo da nuvem tem a mesma forma: `modelos.py` (tabelas), `servico.py` (regras),
`rotas.py` (API e telas), `tests/`.

### 6.4 Simulador de portaria

Ferramenta que reproduz vídeos e passagens gravados e os envia à nuvem como uma caixa real.
Serve para desenvolver sem câmera, para os testes de ponta a ponta e para simular falhas
(internet caindo, envio duplicado, câmera parada).

---

## 7. Infraestrutura

### 7.1 Ambientes

| Ambiente | Onde | Para quê |
|---|---|---|
| Local | `docker compose up` | PostgreSQL, API, worker, simulador |
| Homologação | nuvem, máquina pequena | testar cada versão antes do cliente |
| Produção | AWS São Paulo | o piloto |

### 7.2 Nuvem (AWS, sa-east-1)

- **Lightsail 4 GB** (US$ 24/mês) com Docker Compose: API, worker e **Caddy** (HTTPS automático).
- **RDS PostgreSQL** (~US$ 25/mês na menor instância, mais o disco): backups automáticos e volta a qualquer
  minuto dos últimos 7 dias. Cópia diária extra no S3, guardada 30 dias. Restauração testada
  todo mês.
- **S3** para fotos (US$ 0,04/GB-mês), com expiração automática conforme a seção 8.3.
- Motivo da AWS: mais documentação. O código não depende dela (Magalu Cloud é alternativa
  mais barata, em reais).

### 7.3 Do código à produção

1. Cada envio ao GitHub roda ruff, mypy, pytest e checagem de licenças.
2. Imagens Docker vão para o registro privado do GitHub.
3. `main` → homologação automaticamente. Tag de versão → produção.
4. Segredos ficam nos "secrets" do GitHub e do servidor. Nunca no repositório.

### 7.4 A caixa de borda

- **Equipamento por portaria:** mini PC N150 16 GB, nobreak, switch PoE, câmeras IP 4 MP e
  roteador 4G/5G de reserva. Site-tipo com 2 faixas de entrada e 2 de saída = **6 câmeras**:
  frente + traseira em cada entrada (4) e traseira em cada saída (2).
- **Software:** Ubuntu Server 24.04, Docker, contêineres `go2rtc` e `agente`.
- **Ativação:** a administração gera, para um site, um código de uso único (12 letras e
  números, em três grupos de 4) que vale 24 horas. A caixa troca o código por uma **chave
  própria**; a nuvem guarda só o resumo da chave. Toda chamada da caixa leva
  `Authorization: Bearer <chave>`; chave revogada recebe 401.
- **Configuração:** com a chave, a caixa baixa da nuvem as faixas (com sentido) e as câmeras
  (posição, endereço, login e senha) do site dela. A senha da câmera sai decifrada só nessa
  resposta, só para a caixa do próprio site, porque a caixa precisa dela para ler o vídeo.
- **Saúde:** a cada minuto envia CPU, temperatura, disco, câmeras no ar, quadros por segundo e
  passagens pendentes → tela "Frota de borda" e alertas.
- **Atualização:** a caixa pergunta à nuvem qual versão rodar, baixa e reinicia; se o teste de
  saúde falhar, volta para a anterior. (Atualizador próprio: o Watchtower não é mais mantido.)
- **Acesso remoto:** Tailscale Standard (US$ 8/mês; o plano gratuito é só para uso não comercial).
- **Rede:** a caixa **só faz conexões de saída**. Nenhuma porta aberta na rede do cliente.
  Câmeras num switch separado.
- **Disco local:** fila de passagens (SQLite) e cache de recortes por até 30 dias para treino.
- **Fila de envio** (SQLite, no disco da caixa):
  - toda passagem é gravada primeiro na fila, com as fotos, e só depois enviada;
  - envia na ordem em que as passagens aconteceram: primeiro as fotos, depois a passagem;
  - erro de rede, 5xx, 401, 408 ou 429: tenta de novo, esperando 1 s, 2 s, 4 s... até 5 min
    entre as tentativas, sem passar à frente;
  - 201 ou 200: a passagem sai da fila;
  - recusa definitiva (403, 409 ou 422): a passagem sai da fila e fica guardada à parte na
    caixa, com o motivo, para não travar as seguintes (D-24). Foto recusada de vez (409, 413 ou
    415) fica de fora, e a passagem segue sem ela.

### 7.5 WhatsApp e SMS

- **WhatsApp:** Cloud API oficial da Meta, ligada direto (sem intermediário). Exige verificação
  da empresa e modelos de mensagem aprovados. Respostas chegam por webhook na nossa API.
  Bibliotecas não oficiais (Baileys, whatsapp-web.js) **não** são usadas: violam os termos do
  WhatsApp.
- **Limite inicial da Meta:** 250 destinatários únicos por 24h; sobe para 2.000 após
  verificação.
- **SMS de reserva:** Zenvia ou Twilio.

### 7.6 Custos de operação (piloto, 1 site; preços de 2026-09-29)

| Item | Custo |
|---|---|
| Nuvem (produção + homologação) | ~US$ 60–80/mês |
| Tailscale | US$ 8/mês |
| WhatsApp (~3.600 visitas × 3 mensagens × R$ 0,035) | ~R$ 380/mês por site |
| Internet de reserva | ~R$ 130–250/mês por site |
| Leitor comercial (opcional, teste técnico) | US$ 50/mês |
| **Hardware por site (uma vez)** | **~R$ 15–22 mil** |

---

## 8. Falhas, segurança e LGPD

### 8.1 Falhas

| Falha | Reação |
|---|---|
| Internet do site cai | o 4G assume; se tudo cair, a caixa grava com a hora dela e reenvia em ordem; o painel mostra "site sem conexão desde HH:MM" |
| Câmera para | alerta em 60 s; a faixa passa a modo manual (porteiro registra a chegada) |
| Leitura duvidosa / sem agendamento | fila de exceções; nunca entra errada |
| Caixa queima | nobreak; alerta; troca por caixa reserva já preparada |
| Nuvem fora | a caixa acumula; banco volta a qualquer minuto dos últimos 7 dias |
| WhatsApp não chega | SMS; se falhar, o painel mostra "motorista não avisado" |
| Relógio da caixa errado | NTP; diferença acima de 2 s gera alerta |
| Erro no código | sempre registrado e alertado; nunca ignorado |

### 8.2 Segurança

- Login individual por e-mail e senha; verificação em duas etapas para gestor e administração
  (mês 4); troca de porteiro por PIN no tablet.
- Senha e PIN são guardados só como **resumo argon2**, nunca o texto. A senha tem de 10 a 128
  caracteres; o PIN, 6 números.
- **Sessão no servidor** (D-20): ao entrar, o navegador recebe um cookie com um código aleatório
  (`HttpOnly`, `SameSite=Lax` e, fora do ambiente local, `Secure`); o banco guarda só o resumo
  do código. A sessão vale 12 horas (um turno); sair a apaga na hora.
- **Limite de tentativas:** no máximo 5 erros de senha por e-mail a cada 15 minutos. No 5º, o
  e-mail fica bloqueado, mesmo com a senha certa, até o erro mais antigo completar 15 minutos.
  E-mail que não existe conta igual, para não revelar quem existe. O PIN de cada porteiro tem o
  mesmo limite.
- **Troca de porteiro:** no tablet já aberto num site, o porteiro do turno escolhe o nome dele e
  digita o PIN; a sessão passa a ser dele. Só vale para porteiros da mesma empresa e de um site
  em comum.
- Permissões por papel e por site; filtro obrigatório por empresa em toda consulta. Sem login, a
  rota responde 401; com o papel errado, 403. O gestor pode tudo o que o porteiro e o líder de
  pátio podem nos sites dele. A administração (nós) tem rotas próprias e não usa as do cliente
  (D-19).
- Caixa com chave própria, revogável.
- Link da transportadora com código aleatório, revogável, com limite de envios.
- HTTPS em tudo; banco e fotos cifrados; senhas de câmera cifradas.
- Dependências checadas a cada build.

### 8.3 LGPD

- **Papéis:** o cliente é o **controlador**; nós somos o **operador**. Cada contrato tem acordo
  de tratamento de dados (`[ABERTO-07]`).
- **Base legal:** câmera e placa por **legítimo interesse** (controle de acesso e segurança);
  WhatsApp só com autorização do motorista.
- **Minimização:** sem reconhecimento facial; fotos guardadas são recortes de placa e veículo;
  rostos borrados na caixa nas fotos de contexto.
- **Guarda** (padrão a validar com advogado — `[ABERTO-04]`): fotos 90 dias (exceto as ligadas a
  exceção ou disputa); visitas e trilha de prova 5 anos.
- **Transparência:** placa de aviso na portaria com o contato do encarregado; modelo de relatório
  de impacto (RIPD) entregue ao cliente.
- **Base de treino:** só recortes de placa; cláusula contratual autorizando o uso para melhorar
  o serviço.
- **Portos e recintos alfandegados** (fora do foco do MVP): exigem credenciamento prévio do
  motorista; nesses casos o sistema se integra ao credenciamento, não o substitui.

---

## 9. Testes e qualidade

1. **Regras críticas** com casos de borda (pytest): casamento, estados da visita, validação de
   placa, cálculo do extrato (valores conferidos à mão).
2. **Contrato da passagem:** borda e nuvem testam contra o mesmo pacote `contratos/`.
3. **Ponta a ponta com o simulador:** fluxo completo e falhas (internet caindo, duplicata,
   câmera parada).
4. **Separação de clientes:** testes que tentam ler dados de outra empresa e precisam falhar.
5. **Régua do leitor:** modelo novo só entra se não piorar (seção 4.7).
6. **Modo sombra no piloto:** 2 a 4 semanas rodando sem substituir o porteiro, comparando com o
   registro manual. Mede o acerto real e produz a **linha de base** do extrato.

---

## 10. Cronograma (out/2026 – mar/2027)

Duas trilhas em paralelo: **construção** e **comercial**. Cada mês tem cerca de uma semana de
folga.

| Mês | Construção | Comercial e burocracia | Marco |
|---|---|---|---|
| 1. Out | repositório, CI, Docker local, `contratos/`, esqueleto da nuvem (cadastro, login, empresas), simulador básico; kit de bancada com leitor v0 em vídeo gravado | pedir verificação da empresa na Meta; conta AWS; modelo de contrato e acordo LGPD; começar 15–25 conversas; achar o site parceiro; comprar hardware | vídeo gravado → passagem → aparece no painel |
| 2. Nov | kit gravando no site parceiro; rotular 3–5 mil placas; treinar detector e OCR v1; régua fixa; agendamento (link + planilha) e casamento | conversas; oferta de piloto anual pré-pago | **teste técnico: nosso leitor × comercial** |
| 3. Dez | telas de portaria e pátio; estados da visita; trilha de prova; alertas; borda com fila offline, saúde, atualização, ativação | — | fluxo completo no simulador, com falhas |
| 4. Jan | WhatsApp e SMS; indicadores e extrato; base de treino; frota de borda; produção na AWS com backups e monitoramento | fechar o piloto pago | versão do piloto em homologação |
| 5. Fev | 6 câmeras e caixa definitiva no site; modo sombra 2–4 semanas; ajustes e retreino | linha de base do extrato | acerto real medido |
| 6. Mar | check-in automático ligado; WhatsApp ativo; primeiro extrato real | apresentar o extrato | **decisão seguir / iterar / parar** (até 31/03/2027) |

**Decisão do teste técnico (mês 2):**

| Resultado (composição casando com agendamento) | Ação |
|---|---|
| ≥ 95% | segue com o leitor próprio |
| 90–95% | segue, com mais um ciclo de rotulagem e treino antes do modo sombra |
| < 90% | o piloto começa com o leitor comercial; o próprio continua treinando com dados do piloto |

**Riscos de prazo:**

| Risco | Plano B |
|---|---|
| site parceiro demora | gravar numa portaria de condomínio logístico ou transportadora conhecida |
| verificação da Meta demora | começar só com SMS |
| jurídico do cliente trava o acordo LGPD | modelo de acordo pronto no mês 1 |
| hardware demora | comprar no mês 1 |

---

## 11. Registro de decisões

| # | Decisão | Motivo | Alternativa descartada |
|---|---|---|---|
| D-01 | Projeto em repositório próprio, privado (`patio-br`) | o repositório INVOICE_DELL é restrito à Dell | usar um repositório existente |
| D-02 | MVP do piloto completo no modo A | é o modo com cifra (portaria) e métrica (espera) | começar pelo kit de teste técnico isolado; construir os dois modos juntos |
| D-03 | A borda lê, a nuvem decide | pouca banda, sem GPU na nuvem, resiste a internet ruim | tudo na nuvem (12–24 Mbps por site; GPU ~R$ 3,5 mil/mês); tudo no cliente (inviável para 1 pessoa) |
| D-04 | Agendamento próprio simples + planilha, com conectores | o piloto não pode depender do ERP do cliente; integrações futuras sem refazer | integrar com ERP no MVP; não ter agendamento |
| D-05 | Só modelos Apache/MIT/BSD com pesos próprios | produto fechado | YOLO Ultralytics (AGPL ou licença paga sem preço) |
| D-06 | Mini PC Intel N150 + OpenVINO | preço (~R$ 3,5 mil), disponibilidade, desempenho esperado suficiente (a confirmar no teste técnico) | Jetson (esgotado ou R$ 9–15 mil) |
| D-07 | Leitor atrás de interface única, com motor comercial de reserva | o piloto não depende do acerto do modelo próprio | depender de um único motor |
| D-08 | Python em tudo; monólito modular | uma pessoa com IA; menos peças | microsserviços; React + TypeScript |
| D-09 | Painel com HTMX + SSE, instalável como PWA | sem segunda stack; tempo real suficiente | SPA em React; app nativo |
| D-10 | Fleetbase só como conector futuro e referência | resolve frota em movimento, não pátio; PHP/Ember; AGPL | usar o Fleetbase como base |
| D-11 | AWS São Paulo (Lightsail + RDS + S3) | documentação e serviços gerenciados | Magalu Cloud (mais barata; fica como alternativa) |
| D-12 | WhatsApp pela Cloud API oficial, direto | custo por mensagem baixo; bibliotecas não oficiais violam os termos | Baileys / whatsapp-web.js; intermediário (BSP) |
| D-13 | Tailscale Standard para acesso remoto | simples; plano gratuito proíbe uso comercial | WireGuard próprio (mais trabalho); balena (mais caro) |
| D-14 | Atualizador próprio na caixa | Watchtower não é mantido | Watchtower |
| D-15 | Sem reconhecimento facial; rostos borrados | LGPD (biometria é dado sensível) | identificar motorista pelo rosto |
| D-16 | Fila de tarefas no PostgreSQL | uma peça a menos (sem Redis) | Redis + Celery |
| D-17 | A passagem traz só o que a caixa viu; a placa inferida fica na visita | quem infere é o casamento com o agendamento, na nuvem; uma placa inferida não tem câmera nem quadros | campo `inferida` em cada placa lida da passagem |
| D-18 | Driver do PostgreSQL: pg8000 (BSD-3) | psycopg 2 e 3 são LGPL, que a regra de licença (seção 6.1) não aceita; pg8000 é síncrono como o resto da nuvem, Python puro (igual em Windows e Linux) e é o driver síncrono de PostgreSQL do conector oficial do Cloud SQL, do Google | psycopg 3 (LGPL-3.0); asyncpg (Apache-2.0, mas obrigaria a nuvem inteira a ser assíncrona) |
| D-19 | A administração (nós) fica numa tabela própria, `administrador`, fora das empresas; o login dela gera um acesso de outro tipo, que nunca vira o `Acesso` de um cliente | toda tabela de cliente tem empresa e toda leitura de cliente filtra por ela (seção 5.5); com tipos separados, uma rota de cliente não atende a administração por engano, e vice-versa | papel `admin` na tabela `usuario`, com empresa vazia (abre exceção na regra da empresa); uma "empresa da plataforma" com permissão de ver as outras (um furo na separação) |
| D-20 | Sessão de login guardada no banco; o cookie leva só um código aleatório | sair e desligar um usuário valem na hora; o banco guarda só o resumo do código; não precisa de outra chave secreta | cookie assinado com os dados do usuário, ou token JWT (não dá para revogar antes de vencer) |
| D-21 | Na passagem e na configuração da caixa, os identificadores (caixa, site, faixa, câmera) são os ids da nuvem em texto | a caixa os recebe prontos na ativação e na configuração; a nuvem confere cada um contra o cadastro sem tabela de tradução | um código próprio para cada coisa (ex.: `entrada-1`), que precisaria ser único, editável e traduzido em toda passagem |
| D-22 | Fotos enviadas pela caixa a um endereço temporário; no armazenamento local, o endereço leva um código cifrado (Fernet, com a chave da cifra) que diz a caixa, o `ref` e quando vence | a mesma forma do endereço assinado do S3 (mês 4): a caixa só aprende "peça o endereço e envie"; não precisa de outro segredo | foto dentro da passagem (passagem pesada, reenvio caro); envio pela API com a chave da caixa (no S3 seria outro caminho) |
| D-23 | A placa lida só pela câmera de trás, sem a da frente, vai com papel `desconhecido` | sem a frente, a placa traseira pode ser de um reboque ou do próprio cavalo sem reboque; a caixa só diz o que viu, e o casamento (mês 2) testa a placa em qualquer papel | papel `reboque` sempre que a leitura vem da traseira (erra no cavalo sem reboque com a frente ilegível e na saída, que só tem câmera traseira) |
| D-24 | Passagem que a nuvem recusa de vez (403, 409, 422) sai da fila e fica guardada à parte na caixa | reenviar não muda a resposta, e a fila em ordem ficaria travada para sempre atrás dela; guardada à parte, nada se perde e o suporte vê o motivo | só tirar da fila com 201 ou 200 (trava a portaria inteira por uma passagem errada); apagar a recusada (perde a prova) |

---

## 12. Itens em aberto

| # | Item | Como e quando decidir |
|---|---|---|
| ABERTO-01 | Nome do produto | antes das primeiras conversas comerciais (mês 1) |
| ABERTO-02 | Pesos e limite do casamento (seção 5.3) | com os dados rotulados do mês 2 |
| ABERTO-03 | Detector: D-FINE-N ou YOLOX-Tiny | no teste técnico: acerto e quadros por segundo no N150 |
| ABERTO-04 | Prazos de guarda de dados | com advogado, no mês 1 |
| ABERTO-05 | Método de medir horas-posto de portaria antes e depois | com o cliente do piloto, antes do modo sombra |
| ABERTO-06 | Preço e forma de cobrança do piloto (assinatura, implantação, hardware) | nas conversas dos meses 1–2 |
| ABERTO-07 | Modelo de contrato e acordo de tratamento de dados | com advogado, no mês 1 |
| ABERTO-08 | Guia de posicionamento das câmeras por tipo de portaria | no kit de bancada e no site parceiro (meses 1–2) |
| ABERTO-09 | Tolerância de janela (padrão 4h após o fim da janela, usada também para "não veio") e momento do alerta de estadia (padrão: 4h depois da chegada) | com o cliente do piloto |
| ABERTO-10 | Modelo de dados detalhado do modo B | no início da Fase 2 |
| ABERTO-11 | Implementação da fila de tarefas no PostgreSQL (biblioteca ou tabela própria) | no mês 2, quando o worker entrar com o casamento |
| ABERTO-12 | Licença dos pesos de terceiros usados em avaliação (ex.: fast-plate-ocr) | antes de usá-los, mesmo internamente |

---

## 13. Glossário

| Termo | Significado |
|---|---|
| **Cavalo** | a parte do caminhão com motor e cabine (caminhão-trator) |
| **Reboque / semirreboque** | a carreta puxada pelo cavalo; só tem placa traseira |
| **Composição** | o conjunto cavalo + reboques que passa junto |
| **Bitrem / rodotrem** | composições com dois ou mais reboques |
| **Borda / caixa de borda** | o mini PC na portaria do cliente que processa o vídeo |
| **Passagem** | o registro que a borda envia quando um veículo passa por uma faixa |
| **Visita** | a estadia de um caminhão no site, da chegada à saída |
| **Exceção** | uma passagem que o sistema não conseguiu casar com segurança; o porteiro resolve |
| **Casamento** | ligar uma passagem a um agendamento do dia |
| **Estadia** | valor devido ao transportador quando carga/descarga passa de 5h (Lei 11.442) |
| **Linha de base** | as medidas do site antes de o sistema operar, usadas para calcular a economia |
| **Modo sombra** | período em que o sistema roda sem substituir o processo manual, só medindo |
| **Régua fixa** | conjunto de imagens rotuladas, fora do treino, usado para aprovar modelos novos |
| **Conector** | peça que traz agendamentos de uma origem (link, planilha, ERP) para o formato interno |
| **PWA** | site que se instala no tablet como se fosse um aplicativo |
| **SSE** | forma de o servidor empurrar novidades para a tela sem recarregar |
| **RTSP** | protocolo pelo qual a câmera IP envia o vídeo |
| **OCR** | leitura dos caracteres numa imagem |
| **Resumo (hash)** | transformação de mão única: dá para conferir se uma senha ou código bate, mas não para recuperá-lo. Senhas e PINs usam o argon2, feito para ser lento de adivinhar |
| **Cookie** | pequeno dado que o site guarda no navegador e que volta a cada pedido; aqui, só o código da sessão de login |

---

## Histórico de versões

| Versão | Data | Mudança |
|---|---|---|
| 0.1 | 2026-10-02 | primeira versão, a partir das 8 seções aprovadas na sessão de desenho |
| 0.2 | 2026-10-02 | plano do mês 1 criado (`docs/planos/2026-10-plano-mes-1.md`); `[ABERTO-11]` passa para o mês 2; regra de licença inclui ISC/PSF e MPL-2.0 só sem modificação |
| 0.3 | 2026-10-02 | campo `inferida` sai da Passagem v1, antes de qualquer caixa usá-la; a placa inferida fica na visita (D-17; seções 3.2, 4.3 e 5.1) |
| 0.4 | 2026-10-02 | driver do PostgreSQL: pg8000 no lugar do psycopg, por licença (D-18; seção 6.1) |
| 0.5 | 2026-10-03 | separação de clientes garantida também no banco, por chave estrangeira composta (seção 5.5) |
| 0.6 | 2026-10-03 | login e papéis (T09): administração em tabela própria (D-19), sessão no banco (D-20), senha e PIN com argon2, limite de tentativas e troca de porteiro por PIN (seções 5.1 e 8.2) |
| 0.7 | 2026-10-03 | ativação da caixa (T10): código de uso único por site, chave própria com `Bearer`, configuração baixada pela caixa; ids da nuvem em texto na passagem (D-21; seções 3.2, 5.1 e 7.4) |
| 0.8 | 2026-10-03 | recebimento de passagens e fotos (T11): respostas 201/200/403/409/422 e envio de fotos por endereço temporário (D-22; seção 3.2) |
| 0.9 | 2026-10-03 | tela crua da portaria (T12): arquivos de terceiros do painel (HTMX) no repositório, com licença e hash (seção 6.1) |
| 0.10 | 2026-10-03 | regras puras do leitor (T14): formato, votação e composição na caixa; leitura só da traseira com papel desconhecido (D-23; seções 4.2 e 4.3) |
| 0.11 | 2026-10-03 | fila de envio da caixa (T17): ordem, espera crescente e recusa definitiva guardada à parte (D-24; seção 7.4) |

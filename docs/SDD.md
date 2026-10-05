# SDD — patio-br (nome provisório)

**Documento de desenho do software (SDD) do MVP do piloto**
Versão 0.30 · 2026-10-05 · Situação: aprovado como base; itens em aberto na seção 12

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

**Depois do piloto aprovado** (D-43), o recebimento e o estoque (seção 3.5) abrem o produto
para qualquer empresa que recebe mercadoria, como supermercados e lojas grandes. Esses módulos
funcionam só com o sistema, sem câmera; onde houver câmera, ela liga a mercadoria ao caminhão
que a trouxe.

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
| Recebimento: conferir na doca o que chegou contra a NF-e (falta, sobra, avaria) e mandar o relatório ao fornecedor | o pátio precisa ser aprovado antes (D-43) | depois do piloto aprovado |
| Estoque: onde cada mercadoria está, com busca e visão 3D do armazém | o pátio precisa ser aprovado antes (D-43) | depois do piloto aprovado |
| Cuidado de cargas e controle de entregas | escopo a definir (`[ABERTO-20]`) | depois do piloto aprovado |
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
  - o endereço parte do endereço público da API (`PATIO_URL_PUBLICA`, D-28) ou, sem ele, do
    endereço do pedido, o que basta no ambiente local;
  - o `ref` é escolhido pela caixa (letras, números, `.`, `_`, `-` e `/`; nenhuma parte termina
    em `.` nem é nome reservado do Windows, como `CON` ou `NUL`), e a foto fica guardada dentro
    da pasta da própria caixa: uma caixa nunca alcança a foto de outra;
  - só JPEG, até 2 MB;
  - a foto não se edita: reenviar a mesma foto responde 200; uma foto diferente no mesmo `ref`,
    ou um `ref` que esbarra na pasta de outro (`a` e `a/b`), responde 409;
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

Regras comuns a todos os conectores:

- **Formato interno:** as placas passam pela mesma regra de formato do leitor (seção 4.2); o
  celular é do Brasil (DDD e os 9 números do celular) e fica guardado com o +55; a chave da NF-e
  tem 44 caracteres e o dígito verificador confere, já com o CNPJ alfanumérico.
- **Obrigatórios:** janela, tipo, placa do cavalo e `codigo_externo`. Motorista, celular e
  toneladas podem chegar depois, por um reenvio (a planilha do cliente nem sempre os tem); o link
  da transportadora pede todos.
- **Reenvio atualiza** (D-33): o mesmo `codigo_externo` da mesma origem, no mesmo site, muda o
  agendamento que já existe em vez de criar outro. Reenviar igual não muda nada.
- **Cada mudança fica registrada** (o que era, o que ficou, quando, por qual origem e por quem),
  inclusive a criação e o cancelamento. Trocar o celular apaga a autorização de WhatsApp: ela é do
  número, não do agendamento.
- **Cancelado não volta pelo reenvio:** o conector recebe a recusa, com o motivo.

O **link da transportadora** (`link`) é um formulário curto para o celular, sem conta. Cada envio
cria um agendamento novo, com o código externo `<link>-<número do envio>` (ex.: `12-3`), que a
transportadora vê na confirmação. A janela é escolhida no fuso do site, num dia só, dentro do
horário de operação, começando no futuro e no máximo 60 dias à frente. O código, o limite e a
validade do link estão na seção 8.2.

A **planilha** (`planilha`) é a que o gestor sobe, em CSV ou XLSX, a partir do modelo que o
painel oferece:

- **Colunas do modelo:** código, dia, início, fim, tipo, placa do cavalo, reboque 1 a 3,
  motorista, celular, toneladas e chave da NF-e. As seis primeiras são obrigatórias; a ordem não
  importa, maiúsculas e acentos também não, e colunas a mais são ignoradas. Alguns nomes comuns
  valem pelo do modelo (ex.: "data" por "dia", "placa" por "placa do cavalo").
- **Valores:** dia em `dd/mm/aaaa` (ou a data do próprio XLSX), horas em `hh:mm`, no fuso do
  site. Diferente do link, a planilha não confere o horário de operação nem se a janela já
  passou: é o dado do próprio cliente, e a planilha do dia é corrigida e reimportada ao longo
  dele.
- **Arquivo:** CSV em UTF-8 ou no padrão do Excel no Brasil (Windows-1252, separado por `;`), ou
  a primeira aba do XLSX; até 5 MB e 5.000 linhas. O XLSX é lido com proteção contra arquivos
  feitos para atacar o leitor (XML malicioso e compactação que explode de tamanho).
- **Relatório por linha:** as linhas certas entram, e as erradas voltam com o número da linha e
  o motivo (ex.: "linha 7: placa do cavalo: placa inválida: 'ABC12'"). Um problema no arquivo
  inteiro (formato, tamanho, colunas obrigatórias) recusa tudo, sem gravar nada.

### 3.5 Fases futuras (já previstas)

| Fase | Módulos |
|---|---|
| Fase 2 | mapa do pátio e missões de manobra (modo B); câmeras nas docas e sugestão de doca; leitura de CNH/CRLV |
| Fase 3 | conferência de carga e lacre; segurança (perímetro, identidade, risco) |
| Depois do piloto aprovado (D-43) | **recebimento** pela NF-e, na doca; **estoque** com endereços, busca e visão 3D do armazém; **cuidado de cargas e controle de entregas** |
| Sob demanda | conectores de ERP |

Cada módulo futuro "escuta" os mesmos eventos de passagem e visita. A borda e o contrato não
mudam. O recebimento e o estoque também funcionam sem câmera: partem do agendamento e da NF-e,
e a visita, quando existe, diz qual caminhão trouxe a mercadoria.

---

## 4. Leitor de placas

### 4.1 Regra de licença

Em produção, só entram **código e modelos com licença Apache-2.0, MIT ou BSD, com pesos
treinados por nós**. O YOLO da Ultralytics (AGPL-3.0) fica de fora: usá-lo num produto fechado
exige licença Enterprise, sem preço publicado. Pesos de terceiros com licença incerta podem ser
usados só em avaliação interna, nunca no produto (D-26): para comparar modelos entre si e
escolher o que treinar, e no leitor v0 da demonstração interna. Nas conversas comerciais, a
demonstração usa o simulador com a amostra, não o v0.

### 4.2 O caminho de cada câmera, dentro da caixa

| Passo | O que faz | Ferramenta (licença) |
|---|---|---|
| 1. Captura | puxa o vídeo (RTSP) e só processa quando há veículo na faixa | OpenCV sem interface gráfica, com o FFmpeg LGPL da roda (D-29) + go2rtc (MIT); o PyAV do PyPI traz x264 e x265 (GPL) e fica de fora (D-27) |
| 2. Detecção | acha o veículo e a placa no quadro | D-FINE-N ou YOLOX-Tiny (Apache-2.0) — `[ABERTO-03]` |
| 3. Rastreamento | segue o mesmo veículo entre quadros | rastreador nosso por sobreposição, no estilo do ByteTrack (D-25); o supervision exige o PyAV (D-27) |
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
- **Rastreamento** (D-25): cada câmera tem um rastreador. O detector acha os veículos no quadro;
  cada veículo segue a caixa do quadro anterior que mais se sobrepõe a ele (primeiro as
  detecções de confiança alta, depois as de baixa, como no ByteTrack). Quando o veículo some por
  alguns quadros, as leituras dele passam pela votação e viram uma leitura do veículo, com o
  recorte da placa mais confiável para a foto. Veículo sem placa legível também gera leitura
  (sem placa), e a passagem sai sem placas: a nuvem trata como exceção (seção 3.2).
- **Captura:** os quadros chegam por uma fonte, a uma taxa configurável (padrão 5 por segundo).
  O vídeo é lido pelo OpenCV (D-29). As fontes:
  - **câmera** (RTSP): a hora de cada quadro é a do relógio da caixa. Se a câmera cai ou não
    abre, a fonte tenta de novo, esperando 1 s, 2 s, 4 s... até 30 s, e o registro mostra o
    endereço sem o login e a senha;
  - **arquivo de vídeo** (ex.: uma gravação da portaria): a hora conta a partir de um início
    dado, pelo número do quadro e pela taxa do vídeo;
  - **pasta de imagens** (os quadros de um vídeo, um arquivo por quadro), para testes.
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
  - a leitura da frente que chega ao fim da janela sem a de trás sai sozinha, como cavalo;
  - leitura sem placa legível entra nas mesmas regras, mas não vira placa: a frente ilegível com
    a traseira lida deixa a traseira com papel desconhecido; sem placa nenhuma, a passagem sai
    vazia.

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
| **Comercial** (Plate Recognizer) | régua no teste técnico; segunda opinião para leitura de baixa confiança quando houver internet; plano B do piloto. Mandar imagens à nuvem dele pede o sim do advogado, e o que ele lê nunca vira rótulo (D-41) | US$ 50/mês por 50 mil leituras (preço de 2026-09-29) |

Trocar de motor não muda nada fora da caixa.

### 4.6 Dados de treino

Os bancos públicos brasileiros com placas reais (RodoSol-ALPR e UFPR-ALPR) só permitem uso
acadêmico (`docs/validacao/fontes-de-placas.md`). Por isso:

1. **Primeiras placas:** o treino começa com placas sintéticas e bases abertas (D-44). As placas
   reais (cerca de 1.000 para a régua e as de treino) vêm do `[ABERTO-18]` e são rotuladas no
   Label Studio, pelo Lorenzo. A gravação no site parceiro ficou para depois (decisão de 05/10).
   Onde houver gravação, as câmeras gravam só a região de gravação (D-39), com aviso LGPD, sem
   operar.
2. **Depois:** cada conferência do porteiro (D-42) vira um rótulo novo (módulo `treino`), após
   revisão na tela de rotulagem, se o contrato do cliente autorizar (seção 8.3).
3. **Treino:** PyTorch em GPU alugada por hora, num ambiente à parte (D-40), só quando há dados
   novos. Exporta ONNX → OpenVINO.
4. A base de treino guarda **só recortes de placa e a região de gravação** (D-39), nunca rostos.
5. O que um leitor comercial lê nunca vira rótulo (D-41).

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
| `Site` | empresa, nome, endereço, fuso, horário de operação (abre e fecha, na hora do site; vazio = 24 horas) |
| `Portaria` / `Faixa` / `Camera` | site; faixa tem sentido (entrada/saída); câmera tem posição (frente/trás/contexto), endereço RTSP, senha cifrada, região de gravação (D-39) |
| `Doca` | site, nome, situação |
| `Usuario` | empresa, nome, e-mail, papel (porteiro, pátio ou gestor), sites com acesso, senha, PIN (porteiro), ativo, verificação em duas etapas (gestor) |
| `Administrador` | nome, e-mail, senha, ativo, verificação em duas etapas; é a administração (nós), fora de qualquer empresa (D-19) |
| `Agendamento` | site, janela início/fim, tipo (carga/descarga), placas esperadas (cavalo, reboques), motorista (nome, celular), autorização de WhatsApp, toneladas, chave NF-e (opcional), `origem`, `codigo_externo`, situação (ativo ou cancelado; o andamento da chegada é da visita, D-32) |
| `MudancaAgendamento` | agendamento, quando, tipo (criado, alterado, cancelado), por onde (a origem do conector ou o painel), quem (usuário, se houver), o que era e o que ficou — **só se acrescenta** |
| `Veiculo` | placa, tipo (cavalo, reboque, caminhão simples); campo de posição no pátio reservado para o modo B |
| `Passagem` | formato da seção 3.2 |
| `Visita` | site, agendamento (opcional; no máximo uma visita por agendamento), passagens de entrada e de saída, composição confirmada (cada placa marcada como lida ou inferida), estado, horários de cada etapa, doca |
| `Evento` | visita, tipo, horário, autor (sistema ou usuário), dados, foto (pela passagem) — **só se acrescenta**: o banco recusa alterar ou apagar |
| `Excecao` | visita, passagem, motivo, candidatos (agendamento e pontos), situação (aberta ou resolvida), resolução, quem resolveu |
| `ConferenciaPlaca` | passagem, foto (o recorte da placa), placa lida, placa conferida, quem, quando — **só se acrescenta**: conferir de novo é outro registro, e o último vale (D-42) |
| `Mensagem` | visita, canal, modelo, situação (enviada, entregue, lida, falhou), custo |
| `ParametrosSite` | custo mensal de um ponto de portaria, postos antes/depois, valor da estadia (R$/t·h), franquia (h), tolerância de janela, horas para alerta, custo hora-doca (opcional) |
| `Extrato` | site, mês, números calculados, versão da regra de cálculo |
| `CaixaBorda` | site, versão instalada, último contato, saúde, chave de acesso (só o resumo), ativada em, revogada em |
| `CodigoAtivacao` | site, resumo do código, criado por (administração), vence em, usado em |
| `LinkTransportadora` | site, nome (a transportadora), resumo do código, criado por (gestor), criado em, vence em, revogado em, limite de envios, envios feitos; o agendamento feito pelo link aponta para ele |
| `Rotulo` | recorte, placa correta, origem (conferência do porteiro ou rotulagem), revisado |

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
- **A visita nasce na chegada** (D-35): a entrada que casou cria a visita em `NA_FILA`; a que
  não casou, em `EXCECAO`, junto com a `Excecao` (motivo e candidatos). No prazo do "não veio",
  o agendamento sem visita ganha uma, em `NAO_VEIO`. Antes disso, o `AGENDADA` do diagrama é o
  agendamento ativo que ainda não tem visita.
- O porteiro resolve a exceção na própria visita (mês 3): liga a um agendamento, ou aceita sem
  agendamento, e ela vai para `NA_FILA`; ou recusa, e ela vai para `RECUSADA`. Se o caminhão
  sai antes, a visita vai para `SAIU` e a exceção fica resolvida pelo sistema ("saiu").
- Toda mudança de estado vem com um evento; uma mudança fora do diagrama é recusada.

### 5.3 Casamento da chegada com o agendamento

Candidatos: agendamentos do site em `AGENDADA` (ativos e ainda sem visita, D-35) cuja janela,
alargada pela tolerância para antes e para depois (padrão 4h, `[ABERTO-09]`), contém a hora da
chegada.

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
- **Exceção:** nenhum candidato acima de 80, ou dois candidatos próximos. O motivo vai junto:
  passagem sem placa; sem candidato (nenhuma placa bate); pontos baixos (o melhor fica abaixo
  de 80); candidatos próximos (menos de 20 pontos à frente). Os candidatos da exceção são os que
  bateram alguma placa, com os pontos.
- **Saída:** uma placa da composição fecha a visita aberta do mesmo site (D-37); havendo mais de
  uma visita aberta com a placa, fecha a de chegada mais recente. Saída sem visita aberta fica só
  como passagem.
- **Placa antiga e Mercosul** (D-36): a placa antiga e a Mercosul que a substituiu (o 5º
  caractere, de número, vira letra: 0→A, 1→B ... 9→J; `ABC1234` = `ABC1C34`) contam como a mesma
  placa.
- **Placa lida só pela traseira** (papel desconhecido, D-23) é testada como cavalo e como
  reboque.
- **Composição da visita** (D-17): o cavalo é o do agendamento; cada reboque do agendamento
  entra como lido, se a câmera o viu, ou inferido, se não viu. Se a câmera viu um reboque que
  não está no agendamento (reboque trocado), ele entra como lido, e os do agendamento não são
  inferidos.
- **A mesma passagem duas vezes** (o trabalho repetido depois de uma falha) não cria outra
  visita: a passagem de entrada e a de saída são únicas entre as visitas.

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
  O banco recusa alterar ou apagar um evento da visita ou uma mudança de agendamento.
- **Separação de clientes:** nenhuma consulta sem filtro de empresa; testes tentam furar isso.
  O banco também garante: cada tabela filha aponta para o pai pela dupla (pai, empresa), então
  não aceita, por exemplo, uma portaria de uma empresa num site de outra.

---

## 6. Aplicativo e código

### 6.1 Stack

| Camada | Escolha |
|---|---|
| Linguagem | **Python 3.12** em tudo (borda, nuvem, treino) |
| Backend | FastAPI, SQLAlchemy 2 com o driver pg8000, Alembic (migrações), Pydantic 2; openpyxl (MIT) com defusedxml (PSF) para a planilha |
| Banco | PostgreSQL 16; fila de tarefas no próprio PostgreSQL, numa tabela nossa (D-38) |
| Painel | páginas no servidor (Jinja) + **HTMX**; atualização ao vivo por SSE; instalável como **PWA** |
| Gráficos | biblioteca JavaScript pequena, só onde houver gráfico |
| Borda | OpenCV sem interface gráfica, com FFmpeg LGPL (D-27 e D-29), go2rtc, OpenVINO, rastreador próprio (D-25), SQLite (fila local), httpx |
| Treino | PyTorch, Label Studio, exportação ONNX → OpenVINO |
| Qualidade | ruff, mypy, pytest; checagem de licenças e vulnerabilidades das dependências |

**Fila de tarefas e worker** (D-16 e D-38): o que não precisa acontecer dentro do pedido da
caixa vira uma tarefa numa tabela do PostgreSQL, e o **worker**, um processo à parte da API, a
executa. A passagem recebida vira a tarefa "casar" (uma só por passagem), gravada junto com a
passagem. O worker pega a próxima com `SELECT ... FOR UPDATE SKIP LOCKED`: dois workers nunca
pegam a mesma. Tarefa com erro volta para a fila esperando cada vez mais (10 s, 20 s, 40 s ...
até 10 min), até 8 tentativas; depois, fica como falhou, com o erro, para o suporte. A cada 5
minutos, o worker confere o "não veio" (seção 5.2), um worker de cada vez.

Toda dependência precisa de licença permissiva (MIT, BSD, Apache, PostgreSQL, ISC, PSF). MPL-2.0 só é aceita para biblioteca usada sem modificação (ex.: `certifi`). GPL, LGPL e AGPL ficam de fora. A CI checa.

Bibliotecas nativas que vêm dentro das rodas (D-27): LGPL é aceita quando usada sem modificação
e carregada dinamicamente (ex.: a `libquadmath` da NumPy); GPL só com a exceção de runtime do
GCC (ex.: a `libgfortran`); o FFmpeg só montado sem partes GPL (sem x264 e x265; por isso o
PyAV do PyPI fica de fora). A CI não vê bibliotecas nativas: quem acrescenta uma dependência
confere a roda. Os créditos que essas licenças pedem ficam em `borda/AVISOS-DE-TERCEIROS.md`
(ex.: o do OpenSSL que vem no OpenCV, D-31).

Arquivos de terceiros que o painel serve (o HTMX, licença Zero-Clause BSD) ficam no repositório,
em `nuvem/src/nuvem/web/estatico/`, com a versão no nome, a licença e o hash conferido, e não
num CDN: o tablet da portaria não depende de outro servidor. A CI não vê esses arquivos; a
licença deles é conferida à mão, como a dos modelos.

### 6.2 Telas do MVP

| Tela | Quem | Conteúdo |
|---|---|---|
| Portaria | porteiro | chegadas ao vivo com foto e o resultado do casamento (check-in, exceção, saída); **conferência da placa**: o recorte ao lado da leitura, para confirmar ou corrigir (D-42); **fila de exceções** em cartões (foto, candidatos, "é este" / "corrigir"); saídas; registro manual |
| Pátio e docas | líder | fila por tempo de espera; docas livres/ocupadas; chamar / iniciar / finalizar; alerta perto de 5h |
| Gestor | gestor | indicadores (espera média, visitas acima de 5h, % de check-in automático, uso de docas); extrato do mês (PDF e planilha) |
| Agendamentos | gestor | lista do dia ou da semana, no fuso do site, com o cancelamento; importar planilha com modelo e relatório de erros por linha; gerar e revogar links da transportadora (o endereço aparece uma vez só, ao gerar) |
| Link da transportadora | transportadora | formulário curto para celular: placas, motorista, celular, janela, toneladas, NF-e opcional |
| Celular do motorista | demonstração | as mensagens que o motorista receberia, numa tela em forma de celular; o canal de demonstração não envia nada (D-45) |
| Recebimento e estoque | demonstração | telas "em breve", com dados de exemplo, para mostrar a visão (D-43 e D-45) |
| Administração | nós | empresas, sites, câmeras, caixas (saúde), usuários, parâmetros, rotulagem, links de demonstração |

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

- Usa o mesmo agente da caixa (captura → leitor → rastreamento → composição → fila) e a mesma
  ativação: código de uso único, chave guardada em `dados/` (fora do Git).
- **Passagens prontas** (`--passagens arquivo.json`): manda passagens escritas à mão, sem visão
  computacional; caixa, site, faixa e horários vêm da ativação e da hora atual quando faltam. Uma
  passagem pode dizer só o sentido (`"sentido": "saida"`), e vai pela primeira faixa dele.
- **Agendamentos** (`--agendamentos arquivo.json` ou `amostra`, só com `--demonstracao`): entra
  como o gestor da semente e sobe os agendamentos pela planilha, com as janelas relativas à hora
  atual e códigos novos a cada rodada. A amostra de agendamentos e a de passagens vêm juntas: há
  chegadas que casam, uma que vira exceção por ter dois candidatos, uma sem placa e uma saída.
  A amostra não traz celular: mesmo inventado, um número pode ser de alguém.
- **Quadros** (`--quadros pasta`): roda o leitor v0 sobre as imagens de uma pasta, como se fossem
  uma câmera.
- **Vídeo** (`--video arquivo`): o mesmo, sobre um arquivo de vídeo (ex.: uma gravação da
  portaria, guardada em `dados/`).
- **Demonstração** (`--demonstracao`): só no ambiente local, entra como a administração da
  semente, gera o código e ativa a caixa sozinho. Se já há uma caixa ativada e a chave dela
  ainda vale, usa a mesma: o que ficou na fila de uma rodada anterior é dela.
- Com a nuvem local, o simulador não usa o proxy do sistema (numa rede de empresa, ele não
  alcançaria o `localhost`).

---

## 7. Infraestrutura

### 7.1 Ambientes

| Ambiente | Onde | Para quê |
|---|---|---|
| Local | `docker compose up` | PostgreSQL, API, worker, simulador |
| Homologação | nuvem, máquina pequena | testar cada versão antes do cliente |
| Produção | AWS São Paulo | o piloto |
| Demonstração | nuvem, máquina pequena (Lightsail em São Paulo) | apresentar o produto às empresas, só com dados inventados; cada empresa visitada ganha uma empresa de demonstração, apagada depois (D-45) |

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
- **Agente:** um processo junta, para cada câmera, captura → rastreamento com leitura → e, por
  faixa, a composição; cada composição vira uma passagem com a hora da caixa e um `id` novo, e
  vai para a fila com a foto de cada placa (o recorte, em JPEG). Por enquanto a caixa só manda
  fotos de placa; a foto de contexto entra com o borrão de rostos (seção 8.3).
- **Programa da caixa** (`caixa`):
  - `caixa ativar --nuvem <endereço> --codigo <código>` troca o código pela chave e a guarda em
    `dados/caixa/caixa.json`, que só o dono do arquivo lê;
  - `caixa rodar` baixa a configuração (se a nuvem não responde, tenta de novo, esperando 1 s,
    2 s, 4 s... até 5 min), abre as câmeras de placa por RTSP (por TCP, com o login e a senha da
    configuração), roda o agente e o remetente da fila até ser desligado (sinal de término ou
    Ctrl+C) e, ao desligar, encerra o que estava em aberto, que fica na fila para a próxima vez;
  - cada câmera é lida na própria linha de execução, e os quadros são processados na ordem em
    que chegam (D-30): uma câmera caída não segura as outras. Se o agente não dá conta, os
    quadros que não cabem na espera são descartados, com registro;
  - a configuração vale até o programa reiniciar. Por enquanto, sem a nuvem no ar a caixa não
    começa: a configuração não fica no disco, porque traz as senhas das câmeras.
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
  mesmo limite. As tentativas de um mesmo e-mail (ou PIN) passam **uma de cada vez**, por uma
  trava no banco: pedidos ao mesmo tempo não escapam da contagem.
- O resumo argon2 gasta 64 MiB de memória: cada processo da API faz **no máximo 4 ao mesmo
  tempo**, e os outros esperam a vez. Assim, uma enxurrada de logins com e-mails diferentes
  deixa a API lenta, mas não esgota a memória.
- O formulário de login **recusa envio vindo de outro site** (cabeçalho `Sec-Fetch-Site` do
  navegador): outro site não consegue fazer o tablet entrar na conta de outra pessoa.
- Os dados de demonstração (`tarefas semente`) têm senha pública: só são gravados no ambiente
  local (`PATIO_AMBIENTE=local`).
- **Troca de porteiro:** no tablet já aberto num site, o porteiro do turno escolhe o nome dele e
  digita o PIN; a sessão passa a ser dele. Só vale para porteiros da mesma empresa e de um site
  em comum.
- Permissões por papel e por site; filtro obrigatório por empresa em toda consulta. Sem login, a
  rota responde 401; com o papel errado, 403. O gestor pode tudo o que o porteiro e o líder de
  pátio podem nos sites dele. A administração (nós) tem rotas próprias e não usa as do cliente
  (D-19).
- Caixa com chave própria, revogável.
- **Link da transportadora** (D-34): código aleatório e longo no endereço (`/agendar/<código>`);
  o banco guarda só o resumo (SHA-256, como o código da sessão), e o registro de acesso da API
  troca o código por `***`. O gestor dá um nome ao link (a transportadora), a validade (padrão 30
  dias, no máximo 180) e o limite de agendamentos (padrão 50, no máximo 1.000), e pode revogá-lo.
  Link vencido, revogado ou inventado responde 404, sem dizer qual; link que chegou ao limite
  responde 429. As páginas do link não vão para o cache nem mandam o endereço a outro site
  (`Referrer-Policy: no-referrer`).
- HTTPS em tudo; banco e fotos cifrados; senhas de câmera cifradas.
- Dependências checadas a cada build.
- **Antes de abrir para a internet**, decidido em 04/10 (vem para o mês 3, com a demonstração,
  D-45):
  - limite de login também por endereço IP, junto com a hospedagem (atrás de um proxy, o IP
    real vem de um cabeçalho que precisa ser de confiança);
  - código anti-CSRF nos formulários do painel (hoje, o `SameSite=Lax` do cookie e a recusa
    do login vindo de outro site);
  - um comando para criar a administração, junto com a verificação em duas etapas (hoje, só a
    semente cria, e só no ambiente local).

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
- **Base de treino:** só recortes de placa e a região de gravação (D-39), nunca rostos;
  cláusula contratual autorizando o uso para melhorar o serviço. Sem ela, a conferência do
  porteiro (D-42) não vira rótulo.
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
| 3. Dez | **demonstração comercial na internet** (D-45): visual próprio; portaria e pátio definitivos; painel e extrato em R$; mensagens do motorista simuladas; visão do recebimento e do estoque; link de demonstração por empresa | apresentar às empresas | **demonstração no ar** |
| 4. Jan | WhatsApp e SMS; trilha de prova completa; alertas; base de treino; caixa de borda com saúde, atualização e contêiner; frota de borda; produção na AWS com backups e monitoramento | fechar o piloto pago | versão do piloto em homologação |
| 5. Fev | 6 câmeras e caixa definitiva no site; modo sombra 2–4 semanas; ajustes e retreino | linha de base do extrato | acerto real medido |
| 6. Mar | check-in automático ligado; WhatsApp ativo; primeiro extrato real | apresentar o extrato | **decisão seguir / iterar / parar** (até 31/03/2027) |

**Mudança de 05/10:** o site parceiro ficou para depois. O Lorenzo quer o produto mais
completo antes de levá-lo ao site. A gravação e o teste técnico saem do mês 2, e as primeiras
placas vêm de outra fonte (`[ABERTO-18]`). Na mesma data, o mês 3 virou a demonstração
comercial na internet (D-45, `docs/planos/2026-12-plano-mes-3.md`).

**Depois de março:** se a decisão for seguir, começa o desenho do recebimento, do estoque e
do cuidado de cargas (D-43).

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
| D-25 | Rastreador nosso, por sobreposição de caixas (no estilo do ByteTrack, sem o filtro de Kalman) | o supervision, que traz o ByteTrack, exige o PyAV, cuja roda traz partes GPL (D-27); na portaria o caminhão anda devagar e, a 5 quadros por segundo, a caixa de um quadro cobre a do seguinte | ByteTrack do supervision (preso ao PyAV); filtro de Kalman (sem ganho a esta velocidade) |
| D-26 | Pesos de terceiros servem só para comparar modelos e para avaliação interna (o leitor v0); o produto usa pesos treinados por nós | decisão de 04/10, que fecha o `[ABERTO-12]`: D-FINE, YOLOX e fast-plate-ocr não declaram licença dos pesos, e PaddleOCR e RapidOCR declaram Apache-2.0 (`docs/validacao/fatos-tecnicos-stack.md`); comparar os de terceiros mostra qual modelo se sai melhor antes de treinar os nossos | usar pesos de terceiros no produto (licença incerta); não usá-los nem para comparar (escolher o modelo às cegas) |
| D-27 | Bibliotecas nativas dentro das rodas: LGPL aceita quando usada sem modificação e carregada dinamicamente; GPL só com a exceção de runtime do GCC; FFmpeg só montado sem partes GPL | decisão de 04/10, que fecha o `[ABERTO-13]`: é a mesma lógica do MPL-2.0 (biblioteca usada sem modificação); proibir toda LGPL nativa derrubaria a NumPy (`libquadmath`), de que o ONNX Runtime precisa; o PyAV do PyPI traz x264 e x265 (GPL, sem exceção) e continua de fora, e com ele o supervision | proibir toda biblioteca nativa GPL e LGPL (sem NumPy e sem vídeo); aceitar qualquer GPL nativa (contaminaria o programa da caixa) |
| D-28 | Endereço público da API configurável (`PATIO_URL_PUBLICA`): os endereços que a API devolve à caixa partem dele | atrás de um proxy HTTPS, o pedido chega como `http://`, e a caixa receberia um endereço de envio de foto errado, tentando para sempre; sem a variável (ambiente local), vale o endereço do pedido; fora do ambiente local, só `https://` | confiar nos cabeçalhos do proxy (`--forwarded-allow-ips`), o que depende de como a hospedagem for montada (mês 4) |
| D-29 | Decodificador de vídeo da caixa: OpenCV sem interface gráfica (`opencv-python-headless`, Apache-2.0) | a roda traz o FFmpeg montado como LGPL 2.1, sem x264 nem x265 (conferido no Linux e no Windows; `docs/validacao/fatos-tecnicos-stack.md`), o que a D-27 aceita; lê arquivo e RTSP e já entrega os quadros em BGR, como a caixa usa | PyAV (a roda traz x264 e x265, GPL); o programa `ffmpeg` à parte (as montagens comuns são GPL; teríamos de montar o nosso); GStreamer (mais peças, e cada plugin com a sua licença) |
| D-30 | Na caixa, cada câmera ao vivo é lida na própria linha de execução, e o agente processa os quadros na ordem em que chegam | ao vivo, os quadros já chegam na ordem do tempo; esperar a câmera mais lenta (como na leitura de arquivos) faria uma câmera caída, que espera até 30 s para reabrir, segurar todas as outras, e o vídeo delas atrasaria e se perderia | juntar as câmeras pela hora dos quadros (certo para arquivos, onde nada chega atrasado); um processo por câmera (mais memória, e a composição junta câmeras da mesma faixa) |
| D-31 | O OpenSSL 1.1.1w que vem na roda do OpenCV para Linux é aceito, com o crédito que a licença pede em `borda/AVISOS-DE-TERCEIROS.md` | decisão de 04/10, que fecha o `[ABERTO-14]`: a licença OpenSSL/SSLeay é no estilo BSD, sem cópia obrigatória; a caixa não usa TLS pelo FFmpeg (RTSP sem TLS, na rede local), e o HTTPS dela vai pelo Python, com o OpenSSL do sistema; quando o OpenCV passar ao OpenSSL 3 (Apache-2.0), a roda nova entra no lugar | montar o nosso FFmpeg e o nosso OpenCV sem OpenSSL (trabalho grande para pouco ganho agora) |
| D-32 | O agendamento tem situação própria, só ativo ou cancelado; o andamento da chegada (`AGENDADA`, `NA_FILA`, `NAO_VEIO`...) é da visita (seção 5.2) | o agendamento muda pela origem (a planilha reimportada, o link) até o caminhão chegar; se carregasse os estados da chegada, um reenvio da planilha poderia mexer num check-in já feito | o agendamento com os estados da visita |
| D-33 | O mesmo `codigo_externo` da mesma origem, no mesmo site, atualiza o agendamento, e a mudança fica registrada | o gestor reimporta a planilha do dia várias vezes, com correções; recusar a repetida o obrigaria a apagar e criar de novo, e duplicar deixaria dois candidatos iguais no casamento | recusar o código repetido; criar outro agendamento |
| D-34 | O código do link da transportadora vai no endereço, e não num campo para digitar; o banco guarda só o resumo, e o registro de acesso o esconde | a transportadora abre o link no celular, direto da mensagem, sem copiar nada; o código é longo (sorteado pela nuvem) e o resumo basta para conferir | um código curto para digitar numa página fixa (mais um passo, e curto é fácil de adivinhar) |
| D-35 | A visita nasce na chegada (ou no prazo do "não veio"), e não junto com o agendamento; o `AGENDADA` é o agendamento ativo sem visita | o módulo de agendamento não precisa conhecer a portaria (seção 3.3); mudar ou cancelar um agendamento antes da chegada não mexe em visita nenhuma; toda entrada vira visita na hora, e a exceção já tem onde guardar os eventos e a foto | criar a visita em `AGENDADA` junto com o agendamento (o agendamento cria e cancela visitas, e o cancelamento precisaria de um estado fora do diagrama) |
| D-36 | No casamento, a placa antiga e a Mercosul que a substituiu contam como a mesma | a troca para a Mercosul manteve a placa de cada veículo, trocando só o 5º caractere por uma letra; a agenda do cliente e o cadastro da transportadora ainda trazem muita placa antiga, e a câmera lê a nova | contar como troca fácil (40 pontos; o check-in automático dependeria da janela) |
| D-37 | Na saída, qualquer placa da composição fecha a visita, e não só a do cavalo | a câmera da saída é traseira e, num caminhão com reboque, vê a placa do último reboque, não a do cavalo | só a placa do cavalo (a saída quase nunca fecharia a visita de uma carreta) |
| D-38 | Fila de tarefas numa tabela nossa, com `SELECT ... FOR UPDATE SKIP LOCKED`, e não numa biblioteca | decisão pela recomendação do plano do mês 2 (D4), que fecha o `[ABERTO-11]`, confirmada pelo Lorenzo em 05/10: as bibliotecas de fila para PostgreSQL que conhecemos usam o psycopg (LGPL), que a D-18 tirou; a fila do MVP é pequena (uma tarefa por passagem e o "não veio") | uma biblioteca de fila sobre o psycopg (licença); Redis + Celery (D-16) |
| D-39 | Cada câmera de placa tem uma **região de gravação**, abaixo do para-brisa, marcada no cadastro da câmera; ao gravar para treinar, a caixa só guarda o que está nela | decisão de 05/10, que fecha o `[ABERTO-15]`: o detector aprende com o quadro, mas a base de treino não pode ter rostos (seções 4.6 e 8.3); com a câmera enquadrando o para-choque (`[ABERTO-08]`), a região tem o veículo e a placa, sem o motorista | gravar o quadro inteiro e borrar os rostos depois (o rosto que o borrão perde fica guardado) |
| D-40 | O treino roda num **ambiente à parte**, fora do `uv.lock` do projeto, só na máquina de GPU alugada; os modelos saem em ONNX, e o código de treino segue a regra de licença | decisão de 05/10, que fecha o `[ABERTO-16]`: o PyTorch com GPU traz bibliotecas da NVIDIA com licença proprietária, que a seção 6.1 não aceita; nada delas vai para a caixa nem para a nuvem | treinar no ambiente do projeto (a checagem de licenças da CI recusaria) |
| D-41 | Leitor comercial: mandar imagens à nuvem dele só com o sim do advogado e do site; sem esse sim, o programa local dele ou a comparação só com o v0 e o registro manual. O que ele lê nunca vira rótulo nem entra no treino | decisão de 05/10, que fecha o `[ABERTO-17]`: as imagens são dados do site, e a nuvem dele pode ficar fora do Brasil; os termos de uso do Plate Recognizer (03/02/2025, item 1.7) proíbem usar o serviço para treinar modelos ou criar dados rotulados (`docs/validacao/fontes-de-placas.md`) | usá-lo para pré-rotular as placas (proibido pelos termos) |
| D-42 | O porteiro **confere a placa** de qualquer passagem, e não só a das exceções: a tela mostra o recorte ao lado da leitura, e ele confirma ou digita a placa certa. A conferência é um registro novo (a leitura e a foto não mudam, seção 5.5), e a última vale. Ela não muda a visita: o "corrigir" da fila de exceções, que casa de novo, vem com a resolução das exceções (mês 3) | pedido do Lorenzo em 05/10: compara a leitura com a placa certa no dia a dia e gera rótulos para o treino (seção 4.6), inclusive dos acertos | conferir só nas exceções (poucos rótulos, e só dos erros) |
| D-43 | Recebimento, estoque (com busca e visão 3D do armazém) e cuidado de cargas e controle de entregas **entram no projeto como módulos para depois do piloto aprovado**, e não agora. Funcionam só com o sistema, sem câmera; onde houver câmera, ela ajuda | decisão do Lorenzo em 05/10: o recebimento é a ponte natural entre quem chega e o que chega, e liga o cliente aos fornecedores que já agendam pela nossa ferramenta; no estoque, a aposta é que muitas empresas estão insatisfeitas com o sistema que usam, e um produto muito fácil de usar abre espaço (a validar); esperar o pátio aprovado mantém o foco do piloto | começar já (tira o foco do piloto); deixar de fora (perde a ponte com os fornecedores) |
| D-44 | O treino do leitor começa com **placas sintéticas e bases abertas**: placas Mercosul geradas por programa, a base Artificial Mercosur (CC BY 4.0) e, para o detector, bases abertas de fora (Open Images, CCPD), guardando só a região da placa (D-39) | decisão do Lorenzo em 05/10, pela opção 1 do `[ABERTO-18]`: não usa dado pessoal e começa já; um estudo de 2025 com placas brasileiras acertou 94,5% com só 10% das placas reais e muitas sintéticas, contra 18% sem as sintéticas | esperar as placas reais (o treino parado até o site parceiro) |
| D-45 | O mês 3 vira a **demonstração comercial na internet**: o produto funcionando e com marca própria, num endereço público, só com dados inventados; cada empresa visitada recebe um link e ganha uma empresa de demonstração só dela. Os indicadores, o extrato e a segurança para a internet vêm do mês 4; a caixa de borda com saúde e atualização, a trilha de prova completa e os alertas vão para o mês 4 | pedido do Lorenzo em 05/10: para apresentar a ideia às empresas, o sistema precisa estar funcionando e bonito, para impressionar e mostrar que somos sérios; o site parceiro foi adiado, e as conversas vêm antes dele | apresentar com as telas cruas; uma maquete só de imagens (não mostra o produto funcionando) |

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
| ABERTO-18 | Placas reais para o leitor, com o site parceiro adiado (seção 4.6). O treino começa com placas sintéticas e bases abertas (D-44). Falta decidir: a régua fixa com cerca de 1.000 placas reais (proposta: fotografar a frota própria parada de transportadoras e locadoras, com carta de autorização) e a coleta própria para treinar (proposta: gravar em 1 a 3 portões de conhecidos, com o sim do advogado) (`docs/validacao/fontes-de-placas.md`) | com o Lorenzo e o advogado, antes da régua e do treino com placas reais |
| ABERTO-19 | Recebimento: de onde vêm os itens da NF-e (o XML que o fornecedor manda, o certificado digital do cliente ou outro caminho) e como o resultado volta ao sistema do cliente (`docs/validacao/recebimento-e-estoque.md`) | no desenho do módulo, depois do piloto aprovado |
| ABERTO-20 | Estoque e cuidado de cargas: estoque próprio (endereços, saldo, busca, visão 3D) ou ligado ao sistema do cliente; o que entra em "cuidado de cargas e controle de entregas" e se inclui a conferência de carga e lacre da Fase 3 | no desenho dos módulos, depois do piloto aprovado |
| ABERTO-21 | Fontes tipográficas no painel: as boas fontes livres usam a licença SIL OFL 1.1, que a regra da seção 6.1 não cita. Proposta: aceitar a OFL 1.1 para fontes usadas sem modificação (como o MPL-2.0), com os arquivos em `nuvem/src/nuvem/web/estatico/` e licença e resumo no `LEIA-ME.md` | com o Lorenzo, antes do visual próprio (mês 3, E4) |

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
| **Rótulo** | a resposta certa de uma imagem (a placa e onde ela está), usada para treinar e medir o leitor |
| **Placa sintética** | imagem de placa gerada por programa, com letras sorteadas, para treinar a leitura |
| **Conector** | peça que traz agendamentos de uma origem (link, planilha, ERP) para o formato interno |
| **PWA** | site que se instala no tablet como se fosse um aplicativo |
| **SSE** | forma de o servidor empurrar novidades para a tela sem recarregar |
| **RTSP** | protocolo pelo qual a câmera IP envia o vídeo |
| **OCR** | leitura dos caracteres numa imagem |
| **NF-e** | nota fiscal eletrônica; a chave de 44 números identifica cada nota |
| **Recebimento** | conferir o que chegou contra o que foi pedido ou faturado, item por item |
| **WMS** | sistema de gestão de armazém: onde cada mercadoria está e o que entra e sai |
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
| 0.12 | 2026-10-03 | licenças dos pesos do leitor v0 (T13): situação do `[ABERTO-12]`; novo `[ABERTO-13]`, bibliotecas nativas GPL e LGPL dentro das rodas (seções 4.2 e 12) |
| 0.13 | 2026-10-03 | captura e rastreamento (T16): rastreador nosso (D-25), captura por fonte de quadros, leitura sem placa legível (seções 4.2 e 4.3) |
| 0.14 | 2026-10-03 | agente da caixa e simulador (T18): o que o agente junta, só fotos de placa por enquanto, modos do simulador (seções 6.4 e 7.4) |
| 0.15 | 2026-10-04 | decisões de 04/10: pesos de terceiros só para comparar e avaliar (D-26, fecha o `[ABERTO-12]`); bibliotecas nativas dentro das rodas (D-27, fecha o `[ABERTO-13]`); endereço público da API (D-28); limite por IP, anti-CSRF e comando da administração antes da produção (seções 3.2, 4.1, 4.2, 6.1, 6.4, 8.2, 11 e 12) |
| 0.16 | 2026-10-04 | leitura de vídeo na caixa: OpenCV sem interface gráfica (D-29), fontes de câmera e de arquivo, `simulador --video`; novo `[ABERTO-14]`, o OpenSSL dentro da roda do OpenCV (seções 4.2, 6.1, 6.4, 11 e 12) |
| 0.17 | 2026-10-04 | programa da caixa: ativação, configuração, câmeras RTSP, agente e remetente; câmeras ao vivo lidas em paralelo (D-30; seções 7.4 e 11) |
| 0.18 | 2026-10-04 | decisão de 04/10 sobre o OpenSSL dentro do OpenCV (D-31, fecha o `[ABERTO-14]`); créditos de terceiros da caixa em `borda/AVISOS-DE-TERCEIROS.md` (seções 6.1, 11 e 12) |
| 0.19 | 2026-10-04 | plano do mês 2 criado (`docs/planos/2026-11-plano-mes-2.md`); novos `[ABERTO-15]` (gravar sem rostos), `[ABERTO-16]` (ambiente de treino) e `[ABERTO-17]` (leitor comercial no teste técnico) (seção 12) |
| 0.20 | 2026-10-04 | agendamentos (T27): regras comuns aos conectores, situação própria do agendamento (D-32), reenvio que atualiza (D-33) e o registro das mudanças (seções 3.4, 5.1 e 11) |
| 0.21 | 2026-10-04 | link da transportadora (T28): o código no endereço (D-34), validade, limite, horário de operação do site e as regras da janela pelo link (seções 3.4, 5.1, 8.2 e 11) |
| 0.22 | 2026-10-04 | importação de planilha (T29): colunas do modelo, valores, arquivo e relatório por linha; openpyxl e defusedxml na stack (seções 3.4 e 6.1) |
| 0.23 | 2026-10-04 | tela de agendamentos (T30): lista do dia ou da semana, cancelamento e revogação de links (seção 6.2) |
| 0.24 | 2026-10-04 | visita, eventos e exceções (T31): a visita nasce na chegada (D-35), exceção na própria visita, eventos que o banco não deixa alterar (seções 5.1, 5.2, 5.5 e 11) |
| 0.25 | 2026-10-04 | casamento (T32): candidatos com a tolerância, motivos da exceção, placa antiga e Mercosul (D-36), saída por qualquer placa da composição (D-37), composição lida ou inferida, passagem repetida (seções 5.3 e 11) |
| 0.26 | 2026-10-04 | fila de tarefas e worker (T33): tabela nossa com `SKIP LOCKED` (D-38, fecha o `[ABERTO-11]` pela recomendação do plano), espera crescente, "não veio" a cada 5 minutos (seções 6.1, 11 e 12) |
| 0.27 | 2026-10-04 | simulador com agendamentos (T35): `--agendamentos`, passagem pelo sentido, resultado do casamento na tela da portaria (seções 6.2 e 6.4) |
| 0.28 | 2026-10-05 | decisões de 05/10: região de gravação (D-39), ambiente de treino (D-40) e leitor comercial (D-41), que fecham os `[ABERTO-15]` a `[ABERTO-17]`; D-38 confirmada; conferência da placa pelo porteiro (D-42); site parceiro adiado e as primeiras placas em aberto (`[ABERTO-18]`) (seções 4.5, 4.6, 5.1, 6.2, 8.3, 10, 11, 12 e 13) |
| 0.29 | 2026-10-05 | recebimento, estoque e cuidado de cargas como módulos para depois do piloto aprovado, sem exigir câmera (D-43); novos `[ABERTO-19]` e `[ABERTO-20]`; o treino começa com placas sintéticas (D-44), e as placas reais para testar entram no `[ABERTO-18]` (seções 1.3, 2.3, 3.5, 10, 11, 12 e 13) |
| 0.30 | 2026-10-05 | plano do mês 3 refeito como a demonstração comercial na internet (D-45; `docs/planos/2026-12-plano-mes-3.md`): ambiente de demonstração, telas do celular do motorista e da visão do recebimento e do estoque, segurança antes da internet, cronograma; novo `[ABERTO-21]` (fontes OFL) (seções 6.2, 7.1, 8.2, 10, 11 e 12) |

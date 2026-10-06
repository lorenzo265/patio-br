# SDD — patio-br (nome provisório)

**Documento de desenho do software (SDD) do MVP do piloto**
Versão 0.49 · 2026-10-06 · Situação: aprovado como base; itens em aberto na seção 12

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
2. **Confirmação.** O motorista recebe um SMS com o agendamento e um link que abre o WhatsApp
   com a mensagem pronta. Ao mandá-la, ele autoriza receber as próximas mensagens pelo
   WhatsApp; sem isso, os avisos seguem por SMS (D-58).
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

A passagem é o formato principal que a borda envia; o outro é a saúde da caixa (no fim desta
seção). Os dois ficam no pacote `contratos/`, usado pelos dois lados. Mudou o formato → muda a
versão do contrato.

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

**A saúde da caixa** (D-65): a cada minuto, a caixa manda `POST /api/borda/saude`, com a chave
dela e o formato `Saude` (versão 1) do pacote `contratos/`:

- a caixa e o site (os mesmos ids da passagem) e a hora da caixa;
- a versão do programa e a do leitor;
- o uso da CPU, da memória e do disco (em %) e a temperatura (em °C, quando a máquina diz);
- cada câmera de placa aberta: se está no ar (mandou quadro nos últimos 10 s), os quadros por
  segundo (dos últimos 10 s) e a hora do último quadro;
- a fila: as passagens e as fotos esperando o envio, e as passagens recusadas de vez.

A nuvem responde **204**; `caixa_id` ou `site_id` que não são os da chave → **403**; campo
desconhecido ou fora do formato → **422**. A saúde **não entra na fila**: sem internet, a caixa
não guarda saúde velha, e quando a conexão volta, o tamanho da fila mostra o atraso.

### 3.3 Módulos da nuvem no MVP

A nuvem é um **monólito modular**: um só sistema, dividido em módulos com uma função cada.
Um módulo só usa outro pelas funções de serviço dele, nunca acessando as tabelas alheias.

| Módulo | O que faz | Equivalente na Terminal Industries |
|---|---|---|
| `cadastro` | empresas, sites, portarias, faixas, câmeras, docas, usuários, permissões | base do sistema |
| `agendamento` | agendamentos e **conectores**: link próprio, planilha, API genérica | (usa o do cliente) |
| `portaria` | recebe passagens, casa com agendamento, check-in, exceções, saída | Gate Management |
| `patio` | fila, chamada, docas, início e fim | Dispatch / Dock (manual) |
| `mensagens` | mensagens ao motorista: canal de demonstração (mês 3), WhatsApp oficial (Meta) e SMS de reserva (mês 4) | Driver communication |
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
  inclusive a criação e o cancelamento. A autorização de WhatsApp é do número, numa empresa, e
  não do agendamento (D-58): o celular novo ainda não autorizou nada.
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
| `CodigoRecuperacao` | o usuário ou a administração, o resumo argon2 do código, usado em: 10 por pessoa, mostrados uma vez ao ligar a verificação em duas etapas; cada um vale uma vez (D-60) |
| `Agendamento` | site, janela início/fim, tipo (carga/descarga), placas esperadas (cavalo, reboques), motorista (nome, celular), toneladas, chave NF-e (opcional), `origem`, `codigo_externo`, situação (ativo ou cancelado; o andamento da chegada é da visita, D-32) |
| `MudancaAgendamento` | agendamento, quando, tipo (criado, alterado, cancelado), por onde (a origem do conector ou o painel), quem (usuário, se houver), o que era e o que ficou — **só se acrescenta** |
| `Veiculo` | placa, tipo (cavalo, reboque, caminhão simples); campo de posição no pátio reservado para o modo B |
| `Passagem` | formato da seção 3.2 |
| `Visita` | site, agendamento (opcional; no máximo uma visita por agendamento), passagens de entrada e de saída, composição confirmada (cada placa marcada como lida, inferida ou digitada pelo porteiro), estado, horários de cada etapa, doca |
| `Evento` | visita, tipo, horário, autor (sistema ou usuário), dados, foto (pela passagem) — **só se acrescenta**: o banco recusa alterar ou apagar |
| `Excecao` | visita, passagem, motivo, candidatos (agendamento e pontos), situação (aberta ou resolvida), resolução, quem resolveu |
| `ConferenciaPlaca` | passagem, foto (o recorte da placa), placa lida, placa conferida, quem, quando — **só se acrescenta**: conferir de novo é outro registro, e o último vale (D-42) |
| `Mensagem` | agendamento, evento que a gerou (vazio na confirmação), modelo (confirmação, na fila, chamada, pode sair), para (o celular), texto pronto, as variáveis do modelo de mensagem do WhatsApp, canal (demonstração, WhatsApp ou SMS), situação (guardada, enviada, entregue, lida ou falhou), o id no canal, os horários de cada situação, o erro, a categoria de cobrança da Meta — uma por evento e canal, e uma confirmação por celular do agendamento e canal (D-47 e D-64) |
| `AutorizacaoWhatsApp` | empresa, celular, quando autorizou, o texto que o motorista mandou (a prova), revogada em — uma ativa por empresa e celular (D-58 e D-63) |
| `Alerta` | tipo, empresa e site (vazios nos da plataforma), sobre o quê (a chave: visita, caixa, câmera, agendamento ou tarefa), o texto, aberto em, fechado em — um aberto por tipo e chave (D-68) |
| `AvisoDeAlerta` | o alerta, para quem (usuário ou administração), o celular, a situação (guardado, enviado ou falhou), o id no WhatsApp, o erro, quando (D-68) |
| `AlertasNoWhatsApp` | quem (usuário ou administração), o resumo do código de uso único, pedido em, vence em, o celular e quando autorizou, o texto (a prova), revogada em — uma ativa por pessoa (D-68) |
| `MensagemRecebida` | de (o celular), texto, id no WhatsApp, recebida em, a empresa (quando o texto diz), o que se fez (autorizou, saiu ou ignorada) — da plataforma, como a fila de tarefas (D-63) |
| `ParametrosSite` | custo mensal de um ponto de portaria, postos antes/depois, valor da estadia (R$/t·h), franquia (h), custo hora-doca (opcional); a tolerância de janela e as horas para o alerta continuam fixas no código até o `[ABERTO-09]` |
| `LinhaDeBase` | site, origem (exemplo, na demonstração; modo sombra, no piloto), período, as mesmas medidas do extrato (D-48) |
| `Extrato` | site, mês, números calculados (as medidas, a economia, os parâmetros e a linha de base usados), versão da regra de cálculo, quando foi gerado |
| `CaixaBorda` | site, versão do programa e do leitor, último contato (quando chegou a última saúde), a última saúde, a diferença do relógio, chave de acesso (só o resumo), ativada em, revogada em (D-65) |
| `SaudeCaixa` | caixa, recebida em, a hora da caixa, a diferença do relógio, CPU, temperatura, memória, disco, câmeras no ar e câmeras abertas, passagens na fila, a saúde como chegou — o histórico curto: a nuvem apaga o que passa de 7 dias (D-65) |
| `CodigoAtivacao` | site, resumo do código, criado por (administração), vence em, usado em |
| `VersaoCaixa` | nome (ex.: `0.2.0`), a imagem do agente pelo resumo, cadastrada em, por (administração) — da plataforma, fora das empresas (D-67) |
| `EscolhaDeVersao` | a versão, o alcance (todas as caixas, um site ou uma caixa), escolhida em, por (administração) — **só se acrescenta**: em cada alcance vale a última (D-67) |
| `AtualizacaoCaixa` | caixa, de qual versão, para qual, começou em, terminou em, o resultado (deu certo, voltou ou falhou), o motivo — contada pela caixa (D-67) |
| `LinkTransportadora` | site, nome (a transportadora), resumo do código, criado por (gestor), criado em, vence em, revogado em, limite de envios, envios feitos; o agendamento feito pelo link aponta para ele |
| `LinkDemonstracao` | nome (a empresa visitada), resumo do código, criado por (administração), criado em, vence em (7 dias), revogado em, a empresa de demonstração (nasce na primeira entrada), última entrada, apagada em; fica fora das empresas, como a administração (D-52 e D-54) |
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
- **Corrigir a placa numa exceção aberta** (conferindo a foto, D-42, ou digitando a do cavalo,
  quando não há foto) roda o casamento de novo: casou com segurança, a visita vai para
  `NA_FILA`, e a exceção fica resolvida por quem corrigiu; senão, a exceção fica com o motivo e
  os candidatos novos (D-46).
- **Chegada manual** (a câmera não registrou): o porteiro digita as placas, vê os agendamentos
  sugeridos pelos pontos (seção 5.3) e escolhe um, ou nenhum. Não abre exceção: a visita nasce
  em `NA_FILA`, sem passagem, com o porteiro como autor (D-46).
- **Pátio:** o líder chama o caminhão da fila para uma doca livre do site (`CHAMADA`), marca o
  início (`NA_DOCA`) e o fim (`LIBERADA`); a visita guarda a doca e as três horas. Uma doca tem no
  máximo um caminhão chamado ou na doca, e o banco também confere. Se o chamado não vem, o líder
  cancela a chamada: o caminhão volta para a fila e a doca fica livre.
- **Saída:** quem passou pela doca (liberado, ou ainda marcado na doca) sai com o evento "saiu";
  quem não chegou a ela, com "saiu sem atendimento".
- **Alerta de estadia:** o pátio avisa quando a visita passa de 4 horas desde a chegada ("perto
  das 5 horas", `[ABERTO-09]`) e, depois das 5 horas da lei, que a estadia passou.
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

Como cada conta é feita (versão 1 da regra, D-48):

- **Quem entra no mês:** as visitas que chegaram nele (no fuso do site). O "não veio" fica fora.
- **Check-in automático** = visitas com check-in feito pelo sistema ÷ visitas do mês. O check-in
  feito por uma pessoa (exceção resolvida, chegada manual) não conta (D-46).
- **Espera média:** das visitas chamadas; vale a última chamada (a cancelada não conta).
- **Estadia média e acima de 5 horas:** das visitas liberadas na doca. Quem saiu sem passar pela
  doca não tem estadia.
- **Exposição a estadia:** das liberadas acima da franquia, contada por minuto; a visita sem
  toneladas fica fora da soma, e o extrato diz quantas ficaram.
- **Uso das docas:** do início ao fim na doca (ou à saída), dentro do período, ÷ (docas × horas de
  operação do site; sem horário, 24 horas).
- **Economia em R$:**
  - estadia evitada = (exposição por visita liberada na linha de base − no mês) × liberadas do mês;
  - portaria = (postos antes − postos depois) × custo mensal de um ponto;
  - docas, só com o custo hora-doca = (uso do mês − uso da linha de base) × horas disponíveis do
    mês × custo hora-doca;
  - as horas de espera poupadas aparecem em horas, sem valor em R$.
- **Mês em curso:** é parcial (até agora, e a portaria proporcional aos dias) e não se guarda. O
  **mês fechado** é calculado na primeira vez que é pedido e guardado com a versão da regra, os
  parâmetros e a linha de base usados; depois, é sempre o mesmo.

### 5.5 Garantias

- **Reenvio seguro:** passagem com `id` repetido é ignorada.
- **Prova:** horários e fotos não se editam. Correção = evento novo; a leitura original fica.
  O banco recusa alterar ou apagar um evento da visita ou uma mudança de agendamento. A única
  exceção é a empresa de demonstração vencida, apagada inteira (D-54): o banco só deixa apagar
  linha de prova de uma empresa que nasceu de um link de demonstração, e só quando a transação
  avisa qual empresa está apagando.
- **Separação de clientes:** nenhuma consulta sem filtro de empresa; testes tentam furar isso.
  O banco também garante: cada tabela filha aponta para o pai pela dupla (pai, empresa), então
  não aceita, por exemplo, uma portaria de uma empresa num site de outra.

---

## 6. Aplicativo e código

### 6.1 Stack

| Camada | Escolha |
|---|---|
| Linguagem | **Python 3.12** em tudo (borda, nuvem, treino) |
| Backend | FastAPI, SQLAlchemy 2 com o driver pg8000, Alembic (migrações), Pydantic 2; openpyxl (MIT) com defusedxml (PSF) para a planilha; boto3 (Apache-2.0) para as fotos num armazenamento S3 (D-56); segno (BSD-3) para o QR da verificação em duas etapas (D-60) |
| Banco | PostgreSQL 16; fila de tarefas no próprio PostgreSQL, numa tabela nossa (D-38) |
| Painel | páginas no servidor (Jinja) + **HTMX**; atualização ao vivo por SSE; instalável como **PWA** |
| Gráficos | biblioteca JavaScript pequena, só onde houver gráfico |
| Borda | OpenCV sem interface gráfica, com FFmpeg LGPL (D-27 e D-29), go2rtc (MIT, montado por nós sem FFmpeg, D-66), ONNX Runtime para o leitor v0 (o OpenVINO entra com o leitor próprio), rastreador próprio (D-25), SQLite (fila local), httpx; psutil (BSD-3) para a saúde da máquina (D-65); Docker na caixa (D-66) |
| Treino | PyTorch, Label Studio, exportação ONNX → OpenVINO |
| Qualidade | ruff, mypy, pytest; checagem de licenças e vulnerabilidades das dependências |

**Fila de tarefas e worker** (D-16 e D-38): o que não precisa acontecer dentro do pedido da
caixa vira uma tarefa numa tabela do PostgreSQL, e o **worker**, um processo à parte da API, a
executa. A passagem recebida vira a tarefa "casar" (uma só por passagem), gravada junto com a
passagem; a mensagem ao motorista, a tarefa "enviar mensagem"; o aviso do WhatsApp e o do SMS,
as tarefas "aviso do WhatsApp" e "aviso do SMS" (D-63 e D-64). O worker pega a próxima com `SELECT ... FOR UPDATE SKIP LOCKED`: dois workers nunca
pegam a mesma. Tarefa com erro volta para a fila esperando cada vez mais (10 s, 20 s, 40 s ...
até 10 min), até 8 tentativas; depois, fica como falhou, com o erro, para o suporte. A cada 5
minutos, o worker confere o "não veio" (seção 5.2), um worker de cada vez; a cada minuto, os
alertas (seção 8.1, D-68).

**Sem worker, na demonstração na Vercel** (D-51 e D-56): com `PATIO_TIQUE`, cada tela que se
atualiza sozinha (portaria, pátio, mensagens e o dia de demonstração) roda antes um
**tique**: o dia de demonstração, as tarefas da fila e as mensagens, um tique de cada vez (trava
do PostgreSQL); um erro no tique fica registrado e a tela abre do mesmo jeito. Uma vez por dia,
o cron da Vercel chama `/api/cron/diaria`, com o segredo dele: apaga as empresas dos links
vencidos (D-54) e confere o "não veio".

Toda dependência precisa de licença permissiva (MIT, BSD, Apache, PostgreSQL, ISC, PSF). MPL-2.0 só é aceita para biblioteca usada sem modificação (ex.: `certifi`). GPL, LGPL e AGPL ficam de fora. A CI checa.

Bibliotecas nativas que vêm dentro das rodas (D-27): LGPL é aceita quando usada sem modificação
e carregada dinamicamente (ex.: a `libquadmath` da NumPy); GPL só com a exceção de runtime do
GCC (ex.: a `libgfortran`); o FFmpeg só montado sem partes GPL (sem x264 e x265; por isso o
PyAV do PyPI fica de fora). A CI não vê bibliotecas nativas: quem acrescenta uma dependência
confere a roda. Os créditos que essas licenças pedem ficam em `borda/AVISOS-DE-TERCEIROS.md`
(ex.: o do OpenSSL que vem no OpenCV, D-31).

Arquivos de terceiros que o painel serve (o HTMX, licença Zero-Clause BSD; o three.js, MIT)
ficam no repositório, em `nuvem/src/nuvem/web/estatico/`, com a versão no nome, a licença e o
hash conferido, e não num CDN: o tablet da portaria não depende de outro servidor. Um teste
confere o hash de cada arquivo listado no `LEIA-ME.md` de lá; a licença é conferida à mão, como
a dos modelos. **Fontes tipográficas** com a licença SIL OFL 1.1 são aceitas quando usadas sem
modificação (D-50), do mesmo jeito: os arquivos em `estatico/`, com a licença e o resumo.

### 6.2 Telas do MVP

| Tela | Quem | Conteúdo |
|---|---|---|
| Portaria | porteiro | chegadas ao vivo com foto e o resultado do casamento (check-in, exceção, saída); **conferência da placa**: o recorte ao lado da leitura, para confirmar ou corrigir (D-42); **fila de exceções** em cartões (foto, candidatos, "é este" / "corrigir"); saídas; registro manual; "site sem conexão desde HH:MM" quando a caixa some (D-65) |
| Pátio e docas | líder | fila por tempo de espera; docas livres/ocupadas; chamar / iniciar / finalizar; alerta perto de 5h; "motorista não avisado" (D-64) |
| Gestor | gestor | painel: o dia e o mês até agora (espera média, visitas acima de 5h, % de check-in automático, uso de docas), comparados com a linha de base, com gráficos simples; extrato do mês em R$ (na tela, para imprimir ou salvar em PDF, e em planilha) |
| Agendamentos | gestor | lista do dia ou da semana, no fuso do site, com o cancelamento; importar planilha com modelo e relatório de erros por linha; gerar e revogar links da transportadora (o endereço aparece uma vez só, ao gerar) |
| Alertas | quem é do cliente | o sino em todas as telas, com os alertas abertos dos sites; a tela `/alertas` com os abertos e os das últimas 24 horas; o link para receber os graves pelo WhatsApp (só o gestor, D-68) |
| Link da transportadora | transportadora | formulário curto para celular: placas, motorista, celular, janela, toneladas, NF-e opcional |
| Link de demonstração | quem visita | a página do link (para quem é e o botão "Entrar na demonstração"); dentro, uma faixa no topo troca o papel: gestor, porteiro, líder de pátio ou motorista (D-54) |
| Celular do motorista | demonstração | as mensagens que o motorista receberia, numa tela em forma de celular; o canal de demonstração não envia nada (D-45) |
| Recebimento e estoque | demonstração | telas "em breve", com dados de exemplo, para mostrar a visão (D-43 e D-45) |
| Administração | nós | empresas, sites, câmeras, usuários, parâmetros, rotulagem, links de demonstração; **frota de borda**: cada caixa com o site, as versões, o último contato, as câmeras, a fila, a máquina e o relógio, e o histórico dos últimos 7 dias, hora a hora (D-65); **versões da caixa**: cadastrar, escolher para todas, um site ou uma caixa, e as atualizações de cada caixa (D-67); **alertas da frota e da fila**, com o sino (D-68) |

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
  ferramentas/   simulador de portaria, planilhas de exemplo, comandos (tarefas)
  knowledge/     vault do Obsidian: a documentação em notas ligadas, gerada de docs/
                 e do código (D-53)
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
| Homologação | AWS São Paulo: Lightsail 2 GB, com o PostgreSQL num contêiner e um balde S3 próprio (D-57) | testar cada versão antes do cliente, só com dados inventados |
| Produção | AWS São Paulo (D-11 e D-57) | o piloto |
| Demonstração | a API como função da Vercel e o banco e as fotos no Supabase, os dois em São Paulo (D-51) | apresentar o produto às empresas, só com dados inventados; cada empresa visitada ganha uma empresa de demonstração, apagada depois (D-45); a nuvem roda com `PATIO_AMBIENTE=demonstracao`, e só nele (e no local) existe o dia de demonstração (D-49) |

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
- **Software:** Ubuntu Server 24.04 com o disco cifrado, Docker, contêineres `go2rtc` e
  `agente` (D-66).
- **Contêineres** (D-66), no compose de `infra/caixa/`, que sobem com a máquina:
  - `agente`: a nossa imagem (`borda/Dockerfile`), com Python 3.12 e o programa da caixa, sem
    root e com o sistema de arquivos só de leitura; os pesos do leitor vêm de `modelos/` por um
    volume só de leitura, e não ficam na imagem; a chave, a configuração e a fila ficam num
    volume próprio;
  - `go2rtc` (MIT): montado por nós a partir do código, pelo proxy de módulos do Go, que confere
    o resumo de cada módulo; sem FFmpeg (a imagem oficial traz um FFmpeg com partes GPL, que a
    D-27 não deixa). Ele recebe cada câmera uma vez só e a repassa ao agente;
  - o agente cadastra cada câmera de placa no go2rtc pela API dele (`PATCH /api/streams`, que
    não grava a senha em arquivo) e lê o vídeo de `rtsp://go2rtc:8554/camera-<id>`; a cada vez
    que reabre a câmera, cadastra de novo (o go2rtc que reinicia esquece as câmeras);
  - a tela do go2rtc (ver a câmera na instalação) só responde na própria máquina; de fora, pelo
    Tailscale.
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
  - a configuração baixada fica guardada no disco (`dados/caixa/configuracao.json`), como a
    chave, num arquivo que só o dono lê; se a nuvem não responde ao começar, a caixa começa com
    a última configuração guardada, sem esperar (D-66). Sem configuração guardada, espera a
    nuvem como antes. A chave recusada apaga a configuração guardada, e ativar de novo também;
  - a configuração vale até o programa reiniciar;
- **Saúde** (D-65): a cada minuto, e logo ao começar, a caixa manda a saúde (seção 3.2): as
  versões, a máquina, cada câmera de placa e a fila. Por dentro:
  - a CPU é a média desde a saúde anterior; a temperatura é a do sensor mais quente (sem
    sensor, vai vazia); o disco é o da pasta da fila;
  - cada câmera de placa conta os quadros que chegam ao agente (depois da amostragem): está no
    ar se mandou quadro nos últimos 10 s, e os quadros por segundo são os dos últimos 10 s;
  - a saúde que não chega não é guardada nem reenviada: a próxima vai daqui a um minuto;
  - na nuvem, a `CaixaBorda` guarda o último contato (a hora da nuvem em que a saúde chegou), as
    versões, a última saúde e a **diferença do relógio** (a hora da caixa menos a da nuvem, em
    segundos; o atraso da rede entra na conta, e é pequeno);
  - cada saúde entra também no histórico (`SaudeCaixa`); ao receber, a nuvem apaga a saúde da
    mesma caixa com mais de 7 dias;
  - a caixa está **sem contato** quando a última saúde chegou há 3 minutos ou mais (o mesmo
    tempo do alerta, `[ABERTO-09]`); a caixa que nunca mandou saúde não conta como sem contato;
  - telas: a "Frota de borda" da administração (seção 6.2) e, na portaria, "site sem conexão
    desde HH:MM" (com o dia, se não for hoje; seção 8.1); os alertas vêm com a T57.
- **Atualização** (atualizador próprio, porque o Watchtower não é mais mantido: D-14 e D-67):
  - **as versões:** a administração cadastra cada versão: o nome (ex.: `0.2.0`) e a imagem do
    agente pelo resumo (`ghcr.io/<conta>/patio-caixa@sha256:…`). Depois escolhe qual vale: para
    todas as caixas, para um site ou para uma caixa. A escolha mais específica vence (a da caixa,
    depois a do site, depois a de todas), e em cada alcance vale a última;
  - **a ordem:** uma versão só pode ser escolhida para um site ou para todas depois de dar certo
    numa caixa;
  - **o atualizador** é um programa à parte do agente (`borda/atualizador.py`, só com a biblioteca
    padrão do Python). Roda no próprio Ubuntu da caixa, a cada 5 minutos (um timer do systemd),
    com a chave da caixa:
    1. pergunta à nuvem a versão da caixa (`GET /api/borda/versao`); se é a que já roda, ou uma
       que já falhou nesta caixa, não faz nada;
    2. baixa a imagem pelo resumo (`docker compose pull`; o Docker confere o resumo), com a
       credencial do registro, guardada na preparação, que só baixa imagens;
    3. troca o agente: grava a imagem e o nome da versão no `.env` do compose e sobe o agente de
       novo (`docker compose up -d agente`). A chave, a configuração e a fila ficam no volume e
       não se perdem;
    4. espera a saúde por até 5 minutos. O agente novo tem de estar no ar, com todas as câmeras
       de placa no ar, e a nuvem tem de aceitar a saúde dele. Para isso, o agente grava a última
       saúde, e se a nuvem a aceitou, em `dados/caixa/saude.json`;
    5. se a saúde não vem, volta para a imagem anterior;
    6. conta o resultado à nuvem (`POST /api/borda/atualizacoes`): de qual versão, para qual,
       quando começou e terminou, o resultado (deu certo, voltou ou falhou) e o motivo. A frota
       mostra;
  - **a versão que roda:** o agente conta a versão em cada saúde. Ela é o nome que o compose
    passa ao agente (`PATIO_VERSAO`) ou, fora dos contêineres, a versão do pacote;
  - **o registro privado** é o do GitHub (`ghcr.io`), com uma credencial que só baixa imagens.
- **Acesso remoto:** Tailscale Standard (US$ 8/mês; o plano gratuito é só para uso não comercial).
- **Rede:** a caixa **só faz conexões de saída**. Nenhuma porta aberta na rede do cliente.
  Câmeras num switch separado.
- **Preparação** (D-66): um arquivo de instalação automática do Ubuntu Server 24.04
  (`infra/caixa/autoinstall.yaml`) instala o Docker, o Tailscale e o firewall, fecha a entrada
  (só o Tailscale entra), acerta o relógio pelos servidores do NTP.br (o relógio da passagem é a
  prova) e cifra o disco (LUKS). Depois da instalação, o disco é ligado ao TPM da máquina, que o
  destrava sozinho ao ligar; a senha de recuperação do disco é única por caixa e fica guardada
  por nós, fora do repositório. O guia `docs/guias/preparar-a-caixa.md` diz o resto.
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
- **Autorização:** a política da Meta só deixa a empresa começar a conversa com quem deu o
  número **e** autorizou receber as mensagens dela (conferida em 2026-10-06, em
  `docs/validacao/fatos-tecnicos-stack.md`). Por isso, **o motorista começa a conversa**
  (D-58): o primeiro aviso vai por SMS, com um link que abre o WhatsApp com a mensagem pronta,
  e a mensagem dele é a autorização, guardada com o texto e o horário; um QR na placa de aviso
  da portaria faz o mesmo; "SAIR" cancela na hora. Quem não autoriza recebe os avisos por SMS.
- **Limite inicial da Meta:** 250 destinatários únicos por 24h; sobe para 2.000 após
  verificação. O limite é do portfólio da empresa na Meta, dividido entre os números dele.
- **Por dentro** (D-63):
  - **o canal de cada mensagem** é escolhido ao gravá-la: WhatsApp se o celular autorizou
    aquela empresa; senão, SMS; no ambiente sem WhatsApp configurado (local e demonstração), o
    de demonstração, que só guarda;
  - **o envio é uma tarefa da fila** ("enviar mensagem"), com a espera crescente de sempre: o
    erro passageiro (rede, 5xx, limite de envio) tenta de novo; o definitivo (número sem
    WhatsApp, modelo recusado) deixa a mensagem como falhou, com o código;
  - **modelos de utilidade**, um por tipo de mensagem, em português (`pt_BR`), com as variáveis
    (site, janela, posição, doca); o texto de cada modelo fica no código, e nenhum começa nem
    termina com uma variável (a Meta recusa). Os alertas têm o modelo deles, `patio_alerta`, com
    o site e o texto do alerta (D-68);
  - **o webhook** (`/api/whatsapp`) confere a assinatura (`X-Hub-Signature-256`, com o segredo do
    app) e só guarda o aviso numa tarefa ("aviso do WhatsApp"): o worker atualiza a situação das
    mensagens e trata as recebidas. O mesmo aviso duas vezes não muda nada;
  - **a autorização:** o link e o QR abrem o WhatsApp com "AVISOS A<agendamento>" ou "AVISOS
    S<site>"; a mensagem diz a empresa, e a autorização vale para o celular de quem mandou, só
    naquela empresa. "SAIR" (ou "PARAR") cancela a autorização do número em todas as empresas.
    As duas recebem uma resposta curta; o resto é ignorado, sem resposta;
  - **o celular do WhatsApp:** número do Brasil que o WhatsApp manda sem o 9 (12 números) ganha o
    9 de volta, para bater com o celular do agendamento;
  - os segredos (o token, o segredo do app e o código de verificação do webhook) ficam só nas
    variáveis de ambiente; a versão da API da Meta é configurável (`v25.0`, de 02/2026).
- **SMS de reserva:** Zenvia, confirmada pelo orçamento contra a Twilio (D-59); as duas
  entram pela mesma interface de canal. O texto usa só os caracteres do GSM-7, para caber em
  um pedaço de 160. Por dentro (D-64):
  - **o texto do SMS** é outro, curto e sem acento, e cabe sempre em 160 (o nome do site é
    cortado se precisar); o da confirmação leva o link que abre o WhatsApp com "AVISOS
    A<agendamento>", quando o WhatsApp está configurado;
  - **a reserva:** a mensagem do WhatsApp que falha de vez (recusada no envio, ou avisada como
    falhou pela Meta) ganha uma cópia pelo SMS, no mesmo aviso;
  - **o retorno da Zenvia** (entregue ou não entregue) chega em `/api/sms/<segredo>`: a Zenvia
    não assina os avisos, então o segredo vai no endereço, que só ela conhece, e some do
    registro de acesso. O aviso vira a tarefa "aviso do SMS";
  - **motorista não avisado:** quando todas as tentativas do último aviso de um agendamento
    falharam, o quadro do pátio mostra "motorista não avisado" no caminhão, e o líder avisa de
    outro jeito (o alto-falante, o rádio).

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
| Internet do site cai | o 4G assume; se tudo cair, a caixa grava com a hora dela e reenvia em ordem; a portaria mostra "site sem conexão desde HH:MM" quando a saúde da caixa não chega há 3 minutos (D-65) |
| Câmera para | alerta em 60 s; a faixa passa a modo manual (porteiro registra a chegada) |
| Leitura duvidosa / sem agendamento | fila de exceções; nunca entra errada |
| Caixa queima | nobreak; alerta; troca por caixa reserva já preparada |
| Nuvem fora | a caixa acumula; banco volta a qualquer minuto dos últimos 7 dias |
| WhatsApp não chega | SMS; se falhar, o painel mostra "motorista não avisado" |
| Relógio da caixa errado | NTP; diferença acima de 2 s gera alerta |
| Erro no código | sempre registrado e alertado; nunca ignorado (pela própria AWS, D-61) |

**Os alertas** (D-62 e D-68):

- **Cada alerta** guarda o tipo, a empresa e o site (vazios nos da plataforma), sobre o quê (a
  visita, a caixa, a câmera, o agendamento ou a tarefa), o texto que aparece na tela, quando
  abriu e quando fechou. **Abre uma vez e fecha sozinho** quando a situação passa: há no máximo
  um alerta aberto do mesmo tipo sobre a mesma coisa, e ele não se repete a cada minuto.
- **Os tipos** (os tempos ficam no código até o `[ABERTO-09]` e o cliente do piloto):

  | Tipo | Abre | Fecha | Por WhatsApp | Administração |
  |---|---|---|---|---|
  | estadia perto das 5 horas | a visita está no site há 4 horas | a visita sai, ou passa das 5 horas | não | não |
  | estadia passou das 5 horas | a visita está no site há 5 horas | a visita sai | sim | não |
  | chegada sem agendamento | a exceção "sem candidato" está aberta | a exceção é resolvida | não | não |
  | caixa sem contato | a última saúde chegou há 3 minutos (D-65) | a saúde volta | sim | sim |
  | câmera parada | fora do ar nas duas últimas saúdes da caixa (cerca de 1 minuto sem quadro) | os quadros voltam | sim | sim |
  | relógio da caixa errado | a diferença do relógio passa de 2 segundos | a diferença volta | não | não |
  | motorista não avisado | o último aviso do agendamento falhou em tudo (D-64), com a visita no site | um aviso chega, ou a visita sai | não | não |
  | tarefa que falhou de vez | uma tarefa da fila ficou como falhou | a tarefa sai dessa situação | — | só ela |

  A câmera parada e o relógio só contam com a caixa em contato: sem contato, vale o alerta da
  caixa. A câmera conta pelas duas últimas saúdes, e não por uma só: logo depois de a caixa
  ligar (ou de trocar de versão), a primeira saúde ainda não tem quadro.
- **Quem confere:** o worker, a cada minuto, um de cada vez (trava do PostgreSQL), como o "não
  veio". Na demonstração da Vercel, o tique confere também, no máximo uma vez por minuto.
- **No painel, sempre:** um sino em todas as telas de quem é do cliente, com o número de alertas
  abertos dos sites dele, e a tela `/alertas` com os abertos e os fechados das últimas 24 horas.
  A administração tem o sino dela, com a caixa, a câmera e as tarefas de todas as empresas.
- **Por WhatsApp, só os graves**, a quem autorizou: o gestor dos sites do alerta, e a
  administração nos dela. A autorização é como a do motorista (D-58), mas com um **código de uso
  único**: a tela `/alertas` mostra um link (e o QR) que abre o WhatsApp com "ALERTAS
  <código>"; o código vale 10 minutos, o banco guarda só o resumo, e quem manda a mensagem
  liga aquele celular àquela pessoa (sem o código, ninguém se liga a outra pessoa). "SAIR"
  cancela, como para o motorista. A mensagem é o modelo `patio_alerta` ("Alerta do pátio em
  {{1}}: {{2}}."), mandado por uma tarefa da fila, com as mesmas tentativas das outras; sem o
  WhatsApp configurado, o aviso fica guardado e a tela mostra.

### 8.2 Segurança

- Login individual por e-mail e senha; verificação em duas etapas para gestor e administração
  (mês 4), pelo app autenticador do celular, com 10 códigos de recuperação (D-60); troca de
  porteiro por PIN no tablet.
- **Verificação em duas etapas** (D-60), como funciona:
  - é obrigatória para o gestor e a administração na homologação e na produção; quem já a
    ligou responde ao código em qualquer ambiente;
  - a senha certa abre uma **sessão pela metade**, que vale 10 minutos e só serve para a tela do
    código (ou, na primeira vez, para ligar a verificação); as outras telas a tratam como quem
    não entrou;
  - o código certo fecha a sessão pela metade e abre a de sempre, com um código novo no cookie;
  - vale o código do intervalo de 30 segundos de agora, o do anterior e o do seguinte (o relógio
    do celular pode estar um pouco errado); um código já usado não vale de novo;
  - o limite de erros é o mesmo da senha: 5 a cada 15 minutos por pessoa;
  - **ligar:** a tela mostra o QR para o app e o segredo em texto, e um código do app confirma;
    então aparecem os 10 códigos de recuperação, uma vez só;
  - o segredo do app fica cifrado com a chave da cifra (a nuvem precisa dele para conferir); os
    códigos de recuperação ficam só como resumo argon2;
  - **perdeu o celular:** um código de recuperação entra no lugar do código do app; a
    administração zera a verificação de um usuário, com a hora e quem zerou, e as sessões dele
    se fecham; a da administração se zera pelo comando
    `python -m nuvem.administracao --zerar-duas-etapas --email ...`, no servidor;
  - o cálculo do código é o da RFC 6238 (TOTP com HMAC-SHA1, 6 números, 30 segundos), feito por
    nós e conferido com os exemplos da própria RFC.
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
- Caixa com chave própria, revogável. O disco da caixa é cifrado, porque a configuração guardada
  traz as senhas das câmeras (D-66).
- **Link da transportadora** (D-34): código aleatório e longo no endereço (`/agendar/<código>`);
  o banco guarda só o resumo (SHA-256, como o código da sessão), e o registro de acesso da API
  troca o código por `***`. O gestor dá um nome ao link (a transportadora), a validade (padrão 30
  dias, no máximo 180) e o limite de agendamentos (padrão 50, no máximo 1.000), e pode revogá-lo.
  Link vencido, revogado ou inventado responde 404, sem dizer qual; link que chegou ao limite
  responde 429. As páginas do link não vão para o cache nem mandam o endereço a outro site
  (`Referrer-Policy: no-referrer`).
- **Link de demonstração** (D-52 e D-54): a administração gera, com o nome da empresa visitada;
  código aleatório e longo no endereço (`/demonstracao/link/<código>`), só o resumo no banco, o
  código escondido no registro de acesso e o endereço mostrado uma vez só. Vale 7 dias; vencido,
  revogado ou inventado responde 404, sem dizer qual. Abrir a página não cria nada; só o botão
  "Entrar" cria a empresa e a sessão. Revogar desliga na hora as pessoas da empresa. A troca de
  papel sem senha só existe nos ambientes da demonstração (fora deles, 404) e só leva a outra
  pessoa da mesma empresa, com um site em comum.
- HTTPS em tudo; banco e fotos cifrados; senhas de câmera cifradas.
- Dependências checadas a cada build.
- **Antes de abrir para a internet**, decidido em 04/10 e feito no mês 3, com a demonstração
  (D-45 e D-55):
  - **limite de login também por endereço IP:** no máximo 20 erros a cada 15 minutos por
    endereço, além dos 5 por e-mail. Atrás de um proxy, o endereço vem só do cabeçalho que a
    configuração indica (`PATIO_CABECALHO_DO_IP`; na Vercel, `x-real-ip`, que ela mesma
    escreve); sem ele, vale o endereço da conexão;
  - **código anti-CSRF** (D-55): todo pedido que muda alguma coisa, de quem tem a sessão aberta,
    leva um código tirado da sessão (no formulário, o campo `_csrf`; no HTMX, o cabeçalho
    `X-CSRF-Token`); sem ele, 403. Ficam de fora só as rotas em que o cookie não decide quem
    pede: o login (que recusa o envio vindo de outro site), o link da transportadora, o link de
    demonstração, a API da caixa (pela chave), o webhook do WhatsApp (pela assinatura, D-63) e o
    do SMS (pelo segredo no endereço, D-64). O `SameSite=Lax` do cookie continua;
  - **um comando para criar a administração** (`python -m nuvem.administracao`), que pede a
    senha duas vezes e nunca a mostra; a verificação em duas etapas fica para o mês 4, com a do
    gestor.

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
| 4. Jan | produção na AWS com backups e monitoramento; verificação em duas etapas; WhatsApp e SMS; alertas; caixa de borda com saúde, atualização e contêiner; frota de borda; trilha de prova completa; prazos de guarda; base de treino e placas sintéticas; API e webhooks (se o cliente pedir) | fechar o piloto pago; contas da Meta, do SMS e da AWS; advogado | versão do piloto em homologação |
| 5. Fev | 6 câmeras e caixa definitiva no site; modo sombra 2–4 semanas; ajustes e retreino | linha de base do extrato | acerto real medido |
| 6. Mar | check-in automático ligado; WhatsApp ativo; primeiro extrato real | apresentar o extrato | **decisão seguir / iterar / parar** (até 31/03/2027) |

**Mudança de 05/10:** o site parceiro ficou para depois. O Lorenzo quer o produto mais
completo antes de levá-lo ao site. A gravação e o teste técnico saem do mês 2, e as primeiras
placas vêm de outra fonte (`[ABERTO-18]`). Na mesma data, o mês 3 virou a demonstração
comercial na internet (D-45, `docs/planos/2026-12-plano-mes-3.md`).

**Plano do mês 4 (06/10):** a versão do piloto, em `docs/planos/2027-01-plano-mes-4.md`,
aprovado pelo Lorenzo no mesmo dia, com as decisões D-57 a D-62. Além do que o cronograma já previa, o mês traz a
verificação em duas etapas (seção 8.2), os prazos de guarda (seção 8.3), as placas sintéticas
(D-44) e a API com os webhooks do MVP (seção 2.3).

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
| D-46 | A **chegada manual não abre exceção**: o porteiro escolhe o agendamento entre as sugestões (pelos pontos das placas que digitou) ou nenhum, e a visita nasce na fila. **Corrigir a placa numa exceção aberta casa de novo** (o que a D-42 deixou para o mês 3). A placa que o porteiro escreveu fica marcada como "digitada" na composição | o porteiro está ali e decide na hora; uma exceção para ele mesmo resolver seria um passo a mais. Casar de novo com a placa certa poupa a busca do agendamento à mão. "Digitada" separa o que a câmera leu do que a pessoa escreveu, e o check-in feito por uma pessoa (o evento tem autor) não conta como automático no extrato | a chegada manual virar exceção; a placa corrigida valer só como rótulo (D-42), com o porteiro procurando o agendamento |
| D-47 | As **mensagens ao motorista nascem dos eventos, pelo worker**: a confirmação, de cada agendamento ativo com celular que ainda não terminou; "na fila, posição X", do check-in; "vá para a doca", da chamada; "pode sair", do fim na doca. O worker olha os eventos dos últimos 30 minutos e os agendamentos criados ou mudados no último dia; cada evento gera uma mensagem só, e cada celular de um agendamento, uma confirmação (o banco confere). O texto fica pronto na mensagem, sem o nome do motorista. No mês 3 o canal é o de demonstração, que só guarda; no mês 4 o canal do WhatsApp manda a mesma mensagem, só com a autorização do motorista (seção 8.3), e anota a situação | o módulo `mensagens` fica fora da portaria e do pátio e usa só as funções de serviço deles (seção 3.3); aviso velho não sai ("vá para a doca 7" uma hora depois atrapalha); o texto guardado é o que o motorista leu, e o nome dele não se repete em outra tabela | gravar a mensagem na mesma transação do evento (exata na hora, mas a portaria e o pátio passariam a depender das mensagens); montar o texto só na hora de mostrar (a tela mudaria o que já foi mandado) |
| D-48 | O **extrato** segue a versão 1 da regra (seção 5.4): o mês são as visitas que chegaram nele; a estadia é de quem foi liberado na doca; a exposição sem toneladas fica fora e é contada; a economia soma a estadia evitada (por visita, contra a linha de base), a portaria (postos × custo mensal) e, com o custo hora-doca, as horas de doca a mais. O mês fechado é guardado na primeira vez que é pedido; o mês em curso é parcial. A **linha de base** é uma tabela por site, com a origem: na demonstração, "exemplo", gravada pela semente e marcada assim na tela | a seção 5.4 dizia o que medir, mas não de quais visitas nem como comparar meses de tamanhos diferentes; por visita, a comparação vale para qualquer movimento. Guardar na primeira vez dispensa outra tarefa no worker e deixa o extrato igual depois, mesmo que os parâmetros mudem | contar a estadia de todas as visitas (quem saiu sem doca não tem fim de estadia); comparar totais do mês (mês fraco pareceria economia); gerar o extrato por uma tarefa no virar do mês |
| D-49 | O **dia de demonstração roda dentro da nuvem, no worker**, e no relógio de verdade. A empresa de demonstração tem tudo de uma empresa (site, portaria, faixas, câmeras, docas, pessoas) e uma caixa de borda de mentira, e ganha um mês de visitas passadas e uma linha de base de exemplo coerente com elas. "Começar o dia" fecha o que ficou aberto, grava a manhã como se já tivesse acontecido (caminhões que saíram, que estão na doca e que esperam na fila há horas) e, nos 5 minutos seguintes, manda as chegadas a cada poucos segundos pelo caminho da caixa (receber e casar), com fotos de placa desenhadas; o líder automático chama, começa, termina e manda os liberados à saída. Uma das chegadas tem a placa lida errada e vira exceção para a pessoa resolver. Os celulares usam o DDD 23, que não existe: nenhum número pode ser de alguém | um relógio acelerado mostraria esperas de segundos, ou exigiria um relógio falso em toda a nuvem (o login inclusive); um simulador por visitante pesaria na máquina pequena da demonstração; a manhã pronta mostra esperas, alertas e números de um dia real | o dia inteiro em 5 minutos, com o relógio acelerado; o simulador como um processo à parte para cada visitante |
| D-50 | **Fontes com a licença SIL OFL 1.1** entram no painel quando usadas sem modificação, como o MPL-2.0: os arquivos ficam em `nuvem/src/nuvem/web/estatico/`, com a licença e o hash no `LEIA-ME.md`. Fecha o `[ABERTO-21]` | decisão do Lorenzo em 05/10; as boas fontes livres (as do Google Fonts) usam a OFL, que deixa usar, embutir e distribuir, e só pede que a fonte modificada mude de nome | só fontes do sistema (sem identidade); servir de um CDN (o painel não depende de outro servidor, seção 6.1) |
| D-51 | **A demonstração na internet roda na Vercel e no Supabase**, e não numa máquina na Lightsail: a API como função da Vercel (o runtime Python roda o FastAPI) e o PostgreSQL e as fotos no Supabase, os dois em São Paulo. Sem processo que fica rodando, o worker vira um **tique**: as telas, ao se atualizar, fazem a nuvem avançar o que estiver pendente (o casamento e o dia de demonstração), um tique de cada vez (trava do PostgreSQL). As fotos vão para o Supabase Storage, porque o disco da Vercel não fica. A produção do piloto (seção 7.2) não muda agora; volta a ser vista no mês 4 | decisão do Lorenzo em 05/10: um primeiro deploy simples, sem máquina para cuidar (os dois serviços cuidam do servidor, do HTTPS e dos backups). Regras dos planos em 10/2026: a Vercel Hobby é só para uso pessoal, não comercial (Pro: US$ 20 por pessoa/mês), e o cron dela roda no máximo uma vez por dia (no Pro, uma por minuto); o Supabase Free pausa o projeto depois de uma semana sem uso (Pro: a partir de US$ 25/mês, sem pausa); o pooler do Supabase em modo transação não aceita prepared statements | a máquina na Lightsail (US$ 12/mês, mas com servidor, HTTPS e backups por nossa conta); o worker num serviço à parte (mais uma conta e mais um custo) |
| D-52 | **Um link de demonstração por empresa visitada**, gerado pela administração e válido por 7 dias (o código guardado só como resumo, como o link da transportadora, D-34). Quem abre ganha uma empresa de demonstração só dela (a da T45, D-49) e entra como gestor; ela é apagada depois. Sem cadastro aberto ao público | decisão do Lorenzo em 05/10: cada conversa comercial ganha a sua demonstração, sem uma empresa ver o que outra fez | uma demonstração única para todos (uma empresa veria o que a outra mexeu); cadastro aberto (expõe a demonstração a qualquer um) |
| D-53 | **A documentação também fica num vault do Obsidian** em `knowledge/`: o SDD dividido em seções, uma nota por decisão, item em aberto, tarefa e item da trilha, os outros documentos e um mapa do código, tudo ligado entre si. As notas são **geradas** de `docs/` e do código (`uv run tarefas conhecimento`), e um teste confere que o vault no Git está em dia; só os resumos (a nota de início, o estado atual, as pendências e os temas) são escritos à mão. `docs/` continua a fonte da verdade | pedido do Lorenzo em 05/10: achar qualquer decisão, tarefa ou parte do código em poucos cliques, e dar às sessões novas um ponto de partida; gerado, o vault não se desatualiza sem a CI avisar | mudar a documentação para o vault e apagar `docs/` (o SDD deixaria de ser um arquivo só, e cada nota teria de ser mantida à mão); copiar à mão (desatualiza na primeira mudança) |
| D-54 | **O link de demonstração por dentro** (T48): a página do link só mostra para quem é e o botão "Entrar"; quem aperta cria a empresa de demonstração, na primeira vez, e entra como gestor. **Uma empresa por link**: quem abre o mesmo link entra na mesma. **A cada entrada, os dias que faltam até ontem entram no histórico.** **Uma faixa no topo troca de papel sem senha** (gestor, porteiro, líder de pátio; o motorista é a tela do celular), só nos ambientes da demonstração e só dentro da mesma empresa; as pessoas da empresa do link têm senha sorteada, que ninguém sabe, e entram só pelo link. **A empresa vencida ou revogada é apagada inteira**, com as fotos e as linhas de prova: o gatilho `so_acrescenta` deixa apagar só linha de uma empresa que nasceu de um link de demonstração, e só quando a própria transação avisa qual empresa está apagando (`patio.apagar_empresa`) | o pré-visualizador do WhatsApp e do e-mail abre o link sozinho, e não pode criar empresa nem sessão; criar a empresa leva cerca de 15 segundos, e quem volta entra na hora; sem completar o histórico, o painel teria buraco nos dias entre as visitas; a garantia de prova (seção 5.5) protege dado de cliente, e a empresa de demonstração só tem dado inventado; o Supabase Free tem 500 MB | criar a empresa ao gerar o link (o histórico pararia no dia em que o link foi gerado); uma empresa por pessoa que abre (o link passado adiante viraria várias empresas); desligar os gatilhos para apagar (o banco deixaria de garantir que só a demonstração se apaga); só desativar a empresa vencida (o banco cresceria sem parar) |
| D-55 | **O código anti-CSRF sai da própria sessão**: é o HMAC do código da sessão com um segredo só da nuvem (tirado da chave da cifra), e muda a cada login; nada novo se grava no banco. Ele vai num campo escondido de cada formulário e no cabeçalho dos pedidos do HTMX, e a nuvem confere em todo pedido que muda alguma coisa de quem tem o cookie da sessão; um teste passa por todas as rotas e confere que cada uma confere o código ou está na lista curta das que não usam o cookie | sem tabela e sem estado; o código da sessão já é secreto e longo, e outro site não sabe o segredo para calcular; a conferência num lugar só não depende de cada rota lembrar | guardar um código à parte na sessão do banco (mais uma coluna e uma escrita); o cookie duplo (*double submit*: um subdomínio poderia escrever o cookie); só os cabeçalhos `Sec-Fetch-Site` (navegador antigo não manda, e o SDD pede o código) |
| D-56 | **A demonstração na Vercel, por dentro** (T47, parte 2): as fotos vão para o Supabase Storage pela **API S3**, com o boto3; o mesmo código serve à AWS no mês 4. Sem worker, um **tique** roda antes das telas que se atualizam sozinhas (com `PATIO_TIQUE`), e um **cron diário** (`/api/cron/diaria`, com o `CRON_SECRET` da Vercel) apaga as empresas vencidas e confere o "não veio". No ambiente `demonstracao`, a API da caixa não existe (as passagens só vêm do dia de demonstração). O banco vai pelo pooler do Supabase em **modo sessão**, sem pool na função (`PATIO_BANCO_SEM_POOL`) e com SSL (`PATIO_BANCO_SSL`, e o certificado do Supabase em `PATIO_BANCO_CA`) | uma só implementação de armazenamento para a demonstração e a produção; o tique só trabalha quando alguém olha, e a trava evita dois ao mesmo tempo; o modo sessão aceita tudo o que o pg8000 faz, e a demonstração tem pouco tráfego; caixa de verdade não tem o que fazer num ambiente de dados inventados | a API própria do Supabase Storage (só serviria à demonstração); um worker em outra hospedagem (mais uma conta e uma máquina); o pooler em modo transação (não aceita *prepared statements*; fica para conferir com o pg8000 quando houver a conta); deixar a API da caixa aberta (uma porta a mais na internet) |
| D-57 | **A produção e a homologação ficam na AWS de São Paulo**, como na D-11: a produção numa Lightsail 4 GB (API, worker e Caddy), com o RDS PostgreSQL e as fotos no S3; a homologação numa Lightsail 2 GB, com o PostgreSQL num contêiner e um balde S3 próprio, só com dados inventados. A demonstração continua na Vercel e no Supabase (D-51) | decisão do Lorenzo em 06/10 (plano do mês 4, F1): o piloto precisa do worker rodando sempre (o check-in e o aviso ao motorista na hora, sem esperar alguém abrir uma tela), da API da caixa ligada e de voltar o banco a qualquer minuto dos últimos 7 dias | o Supabase Pro para o banco e as fotos, com uma máquina para a API e o worker (voltar a qualquer minuto é um adicional pago); a produção na Vercel (sem worker) |
| D-58 | **O motorista começa a conversa no WhatsApp.** O primeiro aviso do agendamento vai por SMS, com um link que abre o WhatsApp com a mensagem pronta; a mensagem que o motorista manda é a autorização, guardada com o texto e o horário, por número e por empresa. Um QR na placa de aviso da portaria faz o mesmo para quem chega sem ter autorizado. "SAIR" cancela na hora. Quem não autoriza recebe os avisos por SMS. Fecha o `[ABERTO-22]`; o advogado confere o caminho antes do primeiro motorista de verdade (N22) | decisão do Lorenzo em 06/10 (plano do mês 4, F2): a política da Meta só deixa a empresa começar a conversa com quem autorizou receber as mensagens dela, e o número vem da transportadora ou da planilha; a autorização dada pelo próprio motorista não depende de terceiro, e menos denúncias mantêm a qualidade do número e o limite de envio | a transportadora declarar, no link e na planilha, que o motorista autorizou, e o primeiro WhatsApp ir direto (mais simples e barato, mas a autorização vem de outra pessoa) |
| D-59 | **O SMS de reserva é pela Zenvia**, confirmada pelo orçamento contra a Twilio; o código só conhece a interface de canal, e trocar de fornecedor é escrever outra classe | decisão do Lorenzo em 06/10 (plano do mês 4, F3): a Zenvia cobra em reais, com nota, e tem suporte no Brasil; a Twilio cobra US$ 0,0599 por SMS ao Brasil (`docs/validacao/fatos-tecnicos-stack.md`) | a Twilio |
| D-60 | **A verificação em duas etapas é pelo app autenticador do celular**: o código de 6 números que muda a cada 30 segundos, mais 10 códigos de recuperação, mostrados uma vez e guardados só como resumo. Obrigatória para o gestor e a administração na homologação e na produção; o porteiro e o líder de pátio continuam com a senha e o PIN | decisão do Lorenzo em 06/10 (plano do mês 4, F4): não depende de serviço de fora, funciona sem sinal de celular e não cai com a troca de chip | código por e-mail (precisa de um serviço de e-mail); código por SMS (custa e cai com a troca de chip) |
| D-61 | **Os erros e as quedas chegam até nós pela própria AWS**: o registro de erros no CloudWatch (sem placa, telefone nem nome, só os ids), um alarme para cada erro, a verificação do `/saude` a cada minuto pelo Route 53 (o `/saude` confere também o worker) e o aviso por e-mail | decisão do Lorenzo em 06/10 (plano do mês 4, F5): custa menos de US$ 5 por mês, e nenhum dado sai da nossa nuvem | o Sentry (lê melhor os erros, mas é mais um fornecedor recebendo dados, com acordo LGPD) |
| D-62 | **Os alertas aparecem sempre no painel**, num sino com os alertas abertos do site, em todas as telas dele. **Por WhatsApp, ao gestor que autorizar, só os graves:** a caixa ou uma câmera fora do ar e a estadia que passou das 5 horas. **Para a administração:** a caixa e a câmera fora do ar e os erros | decisão do Lorenzo em 06/10 (plano do mês 4, F6): quem está no painel vê na hora, e a mensagem fica para o que não pode esperar alguém olhar a tela | o e-mail (precisa de um serviço de e-mail e é lido mais tarde) |
| D-63 | **O WhatsApp por dentro** (T52): o canal de cada mensagem é escolhido ao gravá-la (WhatsApp se o celular autorizou a empresa, senão SMS); o envio é uma tarefa da fila, e o erro passageiro tenta de novo, o definitivo deixa a mensagem como falhou; o webhook só confere a assinatura e guarda o aviso numa tarefa; a autorização vem da mensagem "AVISOS A<agendamento>" ou "AVISOS S<site>", vale para o celular de quem mandou naquela empresa, e "SAIR" a cancela em todas; o celular do Brasil sem o 9 ganha o 9 | o webhook responde na hora (a Meta repete o aviso que demora) e o worker, que já sabe tentar de novo, faz o trabalho; a mensagem do motorista diz de qual empresa é a autorização, já que o número do WhatsApp é um só para todos os clientes; quem pede para sair não quer aviso de ninguém | tratar o aviso dentro do pedido do webhook; uma autorização que valesse para todas as empresas; "SAIR" só na empresa da última conversa |
| D-64 | **O SMS por dentro** (T53): o texto do SMS é outro, curto, sem acento e de no máximo 160 caracteres, e o da confirmação leva o link do WhatsApp; a mensagem do WhatsApp que falha de vez ganha uma cópia pelo SMS; o retorno da Zenvia chega num endereço com um segredo (`/api/sms/<segredo>`), escondido no registro de acesso; o "motorista não avisado" é o agendamento cujo último aviso falhou em todas as tentativas, e aparece no quadro do pátio. A mensagem passa a ser única por aviso e canal (o WhatsApp e a reserva pelo SMS) | o SMS com acento cai para 70 caracteres por pedaço e custa o dobro; a Zenvia não assina os avisos dela, e o segredo no endereço é o que ela aceita; quem chama o caminhão para a doca precisa saber que o motorista não recebeu o aviso | o mesmo texto do WhatsApp no SMS; conferir o aviso da Zenvia pelo endereço de origem; mostrar o "não avisado" só na tela de mensagens |
| D-65 | **A saúde da caixa por dentro** (T54): o formato `Saude` no pacote `contratos/`, como a passagem, mandado a cada minuto e fora da fila; o último contato é a hora da nuvem em que a última saúde chegou; o histórico de 7 dias fica numa tabela à parte e se apaga ao receber; a caixa está sem contato depois de 3 minutos sem saúde, e a que nunca mandou saúde não conta; a portaria mostra "site sem conexão desde HH:MM"; a máquina é medida com o psutil (BSD-3) | a saúde velha não ajuda ninguém, e guardá-la na fila atrasaria as passagens; com o último contato pela hora da nuvem, um relógio errado na caixa não esconde a queda; o site da demonstração tem caixa sem programa rodando, e não pode aparecer como fora do ar; 7 dias bastam para ver o que aconteceu, e o histórico pequeno não pesa no banco | a saúde na fila da caixa; o último contato pela hora da caixa ou por qualquer chamada dela; ler a máquina direto do `/proc`, que só serve no Linux |
| D-66 | **A caixa em contêineres por dentro** (T55): a imagem do agente é nossa, sem root, e os pesos vêm por volume só de leitura; o go2rtc é montado por nós a partir do código (v1.9.14), sem FFmpeg; o agente cadastra as câmeras no go2rtc pela API e lê o vídeo de lá; a configuração fica guardada no disco, e a caixa começa com ela quando a nuvem não responde; o disco é cifrado na preparação e destravado pelo TPM, com a senha de recuperação guardada por nós; o relógio vem do NTP.br; o OpenVINO entra com o leitor próprio, e o v0 roda no ONNX Runtime | a imagem oficial do go2rtc traz um FFmpeg do Alpine montado com partes GPL (x264 e x265), e a D-27 não deixa; o proxy de módulos do Go confere o resumo de cada módulo, e não é preciso copiar um resumo à mão; a caixa precisa trabalhar sem a nuvem desde o começo, e as senhas das câmeras no disco pedem o disco cifrado; sem o TPM, a caixa pediria a senha ao ligar e não voltaria sozinha depois de uma queda de energia | a imagem oficial do go2rtc; o binário do go2rtc baixado do GitHub com o resumo copiado à mão; a configuração só na memória (a caixa parada sem a nuvem); o disco cifrado com senha digitada ao ligar |
| D-67 | **A atualização da caixa por dentro** (T56): a administração cadastra cada versão pelo resumo da imagem e a escolhe para todas as caixas, um site ou uma caixa (vence a escolha mais específica); a versão só vai para um site ou para todas depois de dar certo numa caixa; o atualizador é um programa à parte, só com a biblioteca padrão do Python, que roda no Ubuntu da caixa a cada 5 minutos e troca o agente pelo compose; a saúde do agente novo é a gravada por ele no volume, com as câmeras no ar e aceita pela nuvem, em até 5 minutos; senão, volta para a anterior; a versão que falhou não é tentada de novo na mesma caixa; o registro é o do GitHub, com uma credencial que só baixa | fora dos contêineres, uma imagem ruim do agente não leva junto o atualizador, que é quem volta atrás; pelo compose, a caixa continua sendo descrita por um arquivo só; a saúde que a nuvem aceitou prova a caixa inteira (o agente, as câmeras e a internet); o registro do GitHub já está na conta do projeto e não pede um token novo a cada 12 horas, como o da AWS | o atualizador num contêiner com o socket do Docker; trocar o agente pela API do Docker, fora do compose; o registro da AWS (ECR) |
| D-68 | **Os alertas por dentro** (T57): cada alerta abre uma vez e fecha sozinho quando a situação passa (um aberto por tipo e coisa); o worker confere a cada minuto, e o tique da demonstração também; a câmera parada e o relógio só contam com a caixa em contato; a autorização do WhatsApp para os alertas é por um código de uso único, de 10 minutos, que a tela do gestor e a da administração mostram; a mensagem é um modelo novo, `patio_alerta`, mandado pela fila de tarefas | o alerta que se repete a cada minuto é ignorado; com o código, ninguém liga o próprio celular aos alertas de outra pessoa (o número do usuário não está no cadastro); a Meta só deixa a empresa começar a conversa com um modelo aprovado; sem a caixa em contato, a câmera e o relógio dela não dizem nada de novo | um alerta novo a cada conferência; a autorização pelo id do usuário na mensagem ("ALERTAS U<id>"), que qualquer um poderia mandar; o celular no cadastro do usuário |

---

## 12. Itens em aberto

| # | Item | Como e quando decidir |
|---|---|---|
| ABERTO-01 | Nome do produto (e a identidade visual: cores, fontes, marca) | numa sessão à parte, com o prompt de `docs/prompts/identidade-visual.md`, antes do visual próprio (T40) |
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
| **Líder automático** | no dia de demonstração, o programa que faz o papel do líder de pátio: chama para as docas, começa, termina e manda à saída |
| **Franquia** | as horas que o caminhão espera sem gerar estadia (5 horas, pela lei); a estadia conta o que passa dela |
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
| **Vault (Obsidian)** | uma pasta de notas em Markdown ligadas entre si, que o programa Obsidian abre como um caderno; o nosso é `knowledge/`, e começa na nota `00 Início` |
| **Contêiner (Docker)** | um programa empacotado com tudo de que precisa para rodar (a **imagem**), isolado do resto da máquina; o **compose** é o arquivo que diz quais contêineres sobem juntos |
| **TPM** | um chip de segurança da placa-mãe que guarda a chave do disco cifrado e só a entrega à própria máquina, sem ninguém digitar senha |
| **Disco cifrado (LUKS)** | o disco gravado embaralhado: quem tira o disco da caixa não consegue ler nada sem a chave |
| **Registro de imagens** | o lugar na internet de onde a caixa baixa as imagens dos contêineres; cada imagem tem um resumo, que o Docker confere ao baixar |

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
| 0.31 | 2026-10-05 | portaria definitiva (T41): a placa corrigida numa exceção casa de novo e a chegada manual sem exceção (D-46); placa "digitada" na composição (seções 5.1, 5.2 e 11) |
| 0.32 | 2026-10-05 | pátio e docas (T42): chamada, início, fim e cancelamento da chamada, uma doca por caminhão, a saída de quem passou pela doca e o alerta das 4 horas (seção 5.2) |
| 0.33 | 2026-10-05 | mensagens do motorista (T43): nascem dos eventos pelo worker, no canal de demonstração (D-47); a entidade `Mensagem` e o módulo `mensagens` (seções 3.3, 5.1 e 11) |
| 0.34 | 2026-10-05 | painel e extrato (T44): como cada conta é feita, a economia em R$, o mês fechado guardado e a linha de base por site (D-48); entidades `ParametrosSite`, `LinhaDeBase` e `Extrato`; "franquia" no glossário (seções 5.1, 5.4, 6.2, 11 e 13) |
| 0.35 | 2026-10-05 | o dia de demonstração (T45): no worker e no relógio de verdade, com a manhã pronta, o líder automático, uma exceção para resolver e celulares de DDD que não existe (D-49); o ambiente `demonstracao` (seções 7.1, 11 e 13) |
| 0.36 | 2026-10-05 | decisões de 05/10 à noite: fontes OFL (D-50, fecha o `[ABERTO-21]`), a demonstração na Vercel e no Supabase (D-51) e o link de 7 dias por empresa (D-52); o nome e a identidade visual vão para uma sessão à parte (`[ABERTO-01]`) (seções 6.1, 7.1, 11 e 12) |
| 0.37 | 2026-10-05 | o vault do Obsidian em `knowledge/`, gerado de `docs/` e do código, com o comando `tarefas conhecimento` e o teste que o mantém em dia (D-53); "vault" no glossário (seções 6.3, 11 e 13) |
| 0.38 | 2026-10-05 | link de demonstração por empresa (T48): a entidade `LinkDemonstracao`, a página do link, a faixa que troca de papel, o histórico completado a cada entrada e a empresa vencida apagada inteira, com a exceção da prova só para ela (D-54) (seções 5.1, 5.5, 6.2, 8.2 e 11) |
| 0.39 | 2026-10-05 | segurança antes da internet (T47, parte 1): limite de login por endereço IP, código anti-CSRF tirado da sessão (D-55) e o comando para criar a administração (seções 8.2 e 11) |
| 0.40 | 2026-10-05 | a demonstração na Vercel, por dentro (T47, parte 2): fotos pela API S3 com o boto3, o tique, o cron diário, a API da caixa fechada no ambiente `demonstracao` e o banco pelo pooler do Supabase com SSL (D-56) (seções 6.1 e 11) |
| 0.41 | 2026-10-06 | plano do mês 4 criado, a versão do piloto (`docs/planos/2027-01-plano-mes-4.md`): o cronograma do mês 4 com a verificação em duas etapas, os prazos de guarda, as placas sintéticas e a API com os webhooks; novo `[ABERTO-22]`, a autorização do motorista para o WhatsApp antes da primeira mensagem (seções 2.2, 7.5, 10 e 12); os fatos do WhatsApp e do SMS conferidos em 06/10 |
| 0.42 | 2026-10-06 | plano do mês 4 aprovado pelo Lorenzo com as recomendações: a produção e a homologação na AWS (D-57), o motorista começa a conversa no WhatsApp, com o primeiro aviso por SMS (D-58, fecha o `[ABERTO-22]`), o SMS pela Zenvia (D-59), a verificação em duas etapas pelo app autenticador (D-60), os erros avisados pela AWS (D-61) e para quem vão os alertas (D-62) (seções 2.2, 7.1, 7.5, 8.1, 8.2, 11 e 12) |
| 0.43 | 2026-10-06 | verificação em duas etapas (T51): a sessão pela metade, a tolerância de um intervalo, o código que não vale duas vezes, ligar com o QR, os códigos de recuperação e como zerar; a entidade `CodigoRecuperacao`; o segno na stack (seções 5.1, 6.1 e 8.2) |
| 0.44 | 2026-10-06 | o WhatsApp por dentro (T52): o canal escolhido ao gravar a mensagem, o envio pela fila, o webhook com a assinatura, a autorização por empresa e o "SAIR" (D-63); as entidades `AutorizacaoWhatsApp` e `MensagemRecebida` e a `Mensagem` com a situação do envio (seções 5.1, 6.1, 7.5, 8.2 e 11) |
| 0.45 | 2026-10-06 | o SMS por dentro (T53): o texto curto e sem acento, com o link do WhatsApp na confirmação, a reserva pelo SMS quando o WhatsApp falha, o retorno da Zenvia num endereço com segredo e o "motorista não avisado" no pátio (D-64; seções 5.1, 6.1, 6.2, 7.5, 8.2 e 11) |
| 0.46 | 2026-10-06 | a saúde da caixa por dentro (T54): o formato `Saude` no contrato, o último contato, a diferença do relógio, o histórico de 7 dias, a frota de borda na administração e o "site sem conexão" na portaria (D-65); a entidade `SaudeCaixa`; o psutil na stack (seções 3.2, 5.1, 6.1, 6.2, 7.4, 8.1 e 11) |
| 0.47 | 2026-10-06 | a caixa em contêineres (T55): o agente e o go2rtc no compose, o go2rtc montado sem FFmpeg, a configuração guardada no disco, o disco cifrado com o TPM e a preparação do Ubuntu (D-66; seções 6.1, 7.4, 8.2, 11 e 13) |
| 0.48 | 2026-10-06 | a atualização da caixa por dentro (T56): as versões pelo resumo da imagem, a escolha por alcance, a ordem (uma caixa antes das outras), o atualizador à parte com a volta automática e as atualizações na frota (D-67); as entidades `VersaoCaixa`, `EscolhaDeVersao` e `AtualizacaoCaixa` (seções 5.1, 6.2, 7.4, 11 e 13) |
| 0.49 | 2026-10-06 | os alertas por dentro (T57): abre uma vez e fecha sozinho, os tipos e os tempos, o worker a cada minuto, o sino em todas as telas, o WhatsApp dos graves com o código de uso único e a administração (D-68); as entidades `Alerta`, `AvisoDeAlerta` e `AlertasNoWhatsApp` (seções 5.1, 6.1, 6.2, 7.5, 8.1 e 11) |

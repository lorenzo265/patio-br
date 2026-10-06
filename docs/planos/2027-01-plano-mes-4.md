# Plano do mês 4: a versão do piloto

Plano de implementação do mês 4 do cronograma do SDD (`docs/SDD.md`, seção 10).
Versão 2 · 2026-10-06 · **Aprovado pelo Lorenzo em 06/10, com as recomendações**

---

## 1. Objetivo e marco

**Objetivo:** a versão que vai para o piloto, pronta e testada na homologação. O que ela faz:
- avisa o motorista de verdade, pelo WhatsApp, com o SMS de reserva;
- manda os alertas para quem precisa agir;
- prepara a caixa de borda para o site: em contêiner, mandando a saúde e se atualizando sozinha;
- guarda a prova de cada visita de um jeito que se pode conferir;
- roda a nuvem de produção na AWS, com cópias e alarmes;
- protege a produção com a verificação em duas etapas.

O prazo é de cerca de um mês. Na trilha comercial, a meta é fechar o piloto pago.

**Marco do mês (o teste de "pronto"):**

> Na homologação, com o simulador no lugar da caixa:
> 1. Um agendamento chega pela planilha e o celular de teste recebe o primeiro aviso.
> 2. O motorista autoriza o WhatsApp.
> 3. A passagem faz o check-in.
> 4. O motorista recebe no WhatsApp "na fila", "vá para a doca" e "pode sair".
> 5. Desligar a caixa dispara o alerta. Ao religar, nada se perdeu.
> 6. A prova da visita mostra tudo, com a cadeia conferida.
> 7. A cópia do banco volta numa restauração de teste.
> 8. Uma tag leva a mesma versão à produção, pronta para o piloto.

**Nenhum dado de cliente antes do contrato.** A homologação só tem dados inventados. A produção
fica vazia até o contrato e o acordo de tratamento de dados do piloto estarem assinados
(`[ABERTO-07]`). Os testes continuam com dados inventados (regra 3 do `CLAUDE.md`).

**O que fica do mês 3**, em paralelo com este plano:
- o visual próprio (T40), na sessão da identidade visual (`[ABERTO-01]`);
- o deploy da demonstração, que espera as contas da Vercel e do Supabase (N17).

**O que continua esperando:**
- **A medição no N150 (T20):** espera o hardware (N7).
- **O leitor v1 e o teste técnico (T22 a T26, T36 e T37):** esperam as placas reais
  (`[ABERTO-18]`).
  - Com o gerador de placas sintéticas (T39, neste mês) e a conta de GPU (N11), o treino do OCR
    pode começar antes.
  - Nenhum modelo vai para a caixa sem a régua fixa (SDD 4.7).
- **A caixa do piloto:** não leva os pesos do v0, que são só para avaliação interna (D-26). Ela
  espera o v1 ou o leitor comercial de reserva (D-07, pelo resultado do teste técnico).

**Fora do mês 4:**
- **A foto de contexto com os rostos borrados:** pela regra da seção 4.1, o modelo que acha
  rostos também precisa de pesos nossos. Até lá, a caixa só manda o recorte da placa, como hoje.
- **O SSE e o PWA (D-09):** as telas perguntam ao servidor a cada 2 ou 3 segundos (HTMX), o que
  basta para um site. O PWA entra com o visual (T40) ou antes dos tablets do piloto (mês 5).
- O modo B e as fases seguintes (SDD 3.5).

---

## 2. Antes de começar: decisões do Lorenzo

| # | Decisão | Trava | Recomendação | Decidido em 06/10 |
|---|---|---|---|---|
| F1 | **Onde roda a produção.** O SDD escolheu a AWS (D-11). A demonstração foi para a Vercel e o Supabase (D-51), mas o piloto é diferente. | T49 e T50 | **Manter a AWS da D-11**, em São Paulo: Lightsail 4 GB (API, worker e Caddy), RDS PostgreSQL e S3 para as fotos. A homologação fica numa Lightsail 2 GB, com o PostgreSQL num contêiner e um balde S3 próprio. Os preços estão no `docs/validacao/fatos-tecnicos-stack.md`. O motivo: o piloto precisa do worker rodando sempre (o check-in e o aviso ao motorista na hora, sem esperar alguém abrir uma tela), da API da caixa ligada e de voltar o banco a qualquer minuto dos últimos 7 dias. A alternativa é o Supabase Pro para o banco e as fotos, mais uma máquina para a API e o worker: uma conta a menos, mas voltar a qualquer minuto é um adicional pago. | **a recomendação** (D-57) |
| F2 | **Como o motorista autoriza o WhatsApp** (`[ABERTO-22]`). A política da Meta só deixa a empresa começar a conversa com quem autorizou receber as mensagens dela. O número do motorista vem da transportadora ou da planilha, e o SDD 2.2 manda o primeiro WhatsApp antes dessa autorização. | T52 e T53 | **O motorista começa a conversa.** O primeiro aviso vai por SMS, com um link que abre o WhatsApp com a mensagem pronta. Quando o motorista manda, isso é a autorização, e a conversa no WhatsApp fica aberta. Um QR na placa de aviso da portaria faz o mesmo para quem chega sem ter autorizado. "SAIR" cancela na hora. Quem não autoriza recebe os avisos por SMS. A alternativa: a transportadora declara, no link e na planilha, que o motorista autorizou, e o primeiro WhatsApp vai direto. É mais simples e mais barato, mas a autorização vem de outra pessoa, e uma denúncia de "spam" baixa a qualidade do número na Meta e o limite de envio. Levar ao advogado (N22). | **a recomendação** (D-58, fecha o `[ABERTO-22]`; o advogado confere antes do primeiro motorista de verdade) |
| F3 | **Qual fornecedor de SMS** (o SDD 7.5 deixa a Zenvia ou a Twilio). | T53 | **Pedir o orçamento da Zenvia** e comparar com a Twilio (US$ 0,0599 por SMS ao Brasil). Ficar com a Zenvia se o preço em reais for menor: ela cobra em reais, com nota, e tem suporte no Brasil. As duas entram pela mesma interface, então trocar depois é escrever outra classe. | **a recomendação** (D-59) |
| F4 | **Como funciona a verificação em duas etapas** (SDD 8.2, para o gestor e a administração). | T51 | **App autenticador** (Google Authenticator, Microsoft Authenticator e outros): o código de 6 números que muda a cada 30 segundos, mais 10 códigos de recuperação. Não depende de serviço de fora e funciona sem sinal de celular. As alternativas: código por e-mail, que precisa de um serviço de e-mail, ou por SMS, que custa e cai com a troca de chip. O porteiro e o líder de pátio continuam sem ela: usam o tablet da portaria, com o PIN. | **a recomendação** (D-60) |
| F5 | **Como os erros e as quedas chegam até nós** (SDD 8.1: "erro no código: sempre registrado e alertado"). | T50 | **Tudo dentro da AWS:** o registro de erros no CloudWatch, um alarme para cada erro e a verificação do `/saude` a cada minuto pelo Route 53, com aviso por e-mail. Custa menos de US$ 5 por mês, e nenhum dado sai da nossa nuvem. A alternativa é o Sentry: lê melhor os erros, mas é mais um fornecedor recebendo dados, o que pede um acordo LGPD com ele. | **a recomendação** (D-61) |
| F6 | **Para quem vão os alertas, e por onde.** | T57 | **No painel, sempre:** um sino com os alertas abertos do site, em todas as telas. **Por WhatsApp ao gestor que autorizar, só os graves:** a caixa ou uma câmera fora do ar, e a estadia que passou das 5 horas. **Para a administração (nós):** a caixa e a câmera fora do ar, e os erros. A alternativa é o e-mail, que precisa de um serviço de e-mail e é lido mais tarde. | **a recomendação** (D-62) |

---

## 3. Como trabalhar neste plano

As mesmas regras dos meses anteriores (`CLAUDE.md`), com estes ajustes:

- **Numeração:** as tarefas continuam de onde pararam, a partir da T49. A T39, das placas
  sintéticas, guardada desde o mês 3, entra aqui. As branches levam `mes4/` (ex.:
  `mes4/t49-producao`).
- **Contas e segredos:** cada conta nova (AWS, Meta, SMS) é aberta pelo Lorenzo. Os segredos
  ficam só nas variáveis de ambiente das máquinas e nos *secrets* do GitHub, passados pelo cofre
  de segredos do ambiente, nunca no repositório (regra 4).
- **Os serviços de fora são imitados nos testes:** a Meta, o SMS e o S3 (como no mês 3, com o
  moto). Nenhum teste usa a rede, e nenhum usa um número de telefone de verdade.
- **Cada integração é conferida de verdade na homologação**, com o número de teste da Meta e o
  celular do Lorenzo. A conferência entra no PR.
- **O que a execução decidir vira uma D-nn** no SDD, no mesmo PR, como nos meses anteriores.

---

## 4. Tarefas técnicas

### Semana 1 — a casa do piloto

#### T49. Produção e homologação na AWS

**Objetivo:** a nuvem do piloto no ar, em São Paulo, como dizem as seções 7.2 e 7.3 do SDD.

**Depende de:** F1 e N21 (a conta da AWS e o domínio).

**Arquivos:**
- `infra/producao/` (o compose da máquina: API, worker e Caddy);
- `.github/workflows/` (publicar a imagem e fazer o deploy);
- `nuvem/Dockerfile`;
- `docs/guias/producao.md`.

**Regras:**
- **As peças:**
  - produção: Lightsail 4 GB com Docker Compose (API, worker e Caddy, com o HTTPS automático);
  - o banco: RDS PostgreSQL 16, cifrado e sem acesso público (só a máquina o alcança);
  - as fotos: S3 privado e cifrado, com o endereço de envio assinado do próprio S3 (D-22; o
    código é o da D-56).
- **A homologação** é igual, menor (F1), e só tem dados inventados.
- **O caminho do código:**
  - a imagem vai para o registro privado do GitHub;
  - a `main` vai sozinha para a homologação;
  - uma tag de versão vai para a produção só com a aprovação do Lorenzo no GitHub.
- **O deploy:**
  - roda as migrações antes de a API nova subir;
  - uma parada de segundos é aceitável, porque a caixa guarda as passagens na fila;
  - as máquinas não abrem a porta do SSH na internet: o deploy entra pelo Tailscale (D-13).
- **Os segredos:**
  - a chave da cifra da produção é nova, gerada uma vez e guardada no gerenciador de senhas;
  - na máquina, os segredos ficam num `.env` que só o dono lê.

**Verificar:**
- um commit na `main` chega sozinho à homologação;
- o `/saude` responde pelo domínio, com HTTPS;
- o simulador manda passagens à homologação, e a foto chega ao S3;
- a tag chega à produção só depois da aprovação.

**Commit:** `infra: produção e homologação na AWS`

#### T50. Cópias, restauração testada e alarmes

**Objetivo:** nada se perde, e nenhum erro passa calado (SDD 7.2 e 8.1).

**Depende de:** T49 e F5.

**Arquivos:** `infra/producao/`, `ferramentas/src/tarefas/comandos.py`, `nuvem/src/nuvem/`
(registro e saúde), `docs/guias/producao.md`.

**Regras:**
- **As cópias do banco:**
  - os backups automáticos do RDS voltam a qualquer minuto dos últimos 7 dias;
  - uma cópia diária extra vai para um balde S3 cifrado e fica 30 dias;
  - a homologação também faz a cópia diária.
- **A restauração de teste:**
  - volta a última cópia num banco temporário e confere as migrações, as contagens e o último
    evento;
  - roda todo mês, sozinha, **dentro da AWS**: a cópia tem dado de cliente e nunca vai para o
    GitHub nem para um computador.
- **O `/saude`** passa a conferir também o worker: o worker marca a hora a cada volta, e se a
  marca passar de 2 minutos, o `/saude` falha.
- **Os erros:**
  - o registro de erros não leva placa, telefone nem nome, só os ids;
  - cada erro dispara um aviso (F5);
  - o `/saude` é verificado de fora a cada minuto: se a máquina cair, o alarme toca do mesmo
    jeito.
- **O gasto:** um alerta da AWS acima do valor combinado (N2).

**Verificar:**
- derrubar o worker na homologação dispara o alarme em até 5 minutos;
- um erro de propósito chega por e-mail;
- a restauração de teste passa.

**Commit:** `infra: cópias, restauração testada e alarmes`

#### T51. Verificação em duas etapas

**Objetivo:** o gestor e a administração entram com a senha e um código do celular (SDD 8.2).

**Depende de:** F4.

**Arquivos:** `nuvem/src/nuvem/cadastro/`, telas, migração, `nuvem/src/nuvem/administracao.py`,
testes.

**Regras (teste primeiro):**
- **Quem usa:**
  - é obrigatória para o gestor e a administração, na homologação e na produção;
  - o porteiro e o líder de pátio continuam só com a senha e o PIN;
  - nos ambientes local e de demonstração não é exigida (quem entra pelo link de demonstração
    nem tem senha, D-54).
- **O código:**
  - de 6 números, que muda a cada 30 segundos;
  - vale o do intervalo de 30 segundos anterior e o do seguinte;
  - um código já usado não vale de novo.
- **Ligar a verificação:**
  - no primeiro login, a tela mostra o QR para o app e pede um código para confirmar;
  - depois, mostra 10 códigos de recuperação, uma vez só.
- **Como fica guardado:**
  - o segredo do app fica cifrado (a chave da cifra), porque a nuvem precisa dele para conferir;
  - os códigos de recuperação ficam só como resumo (regra 6).
- **Entrar:**
  - a senha certa abre uma sessão que só serve para a tela do código;
  - o código certo abre a sessão de sempre;
  - o limite de erros é o mesmo da senha: 5 a cada 15 minutos.
- **Perdeu o celular:**
  - o gestor usa um código de recuperação;
  - a administração zera a verificação do gestor, com um registro de quem zerou;
  - a da própria administração se zera pelo comando `python -m nuvem.administracao`.
- **Bibliotecas:** só com licença permissiva, conferida antes (ex.: pyotp, MIT; segno, BSD-3,
  para o QR).

*Detalhado na execução (SDD 8.2):*
- o cálculo do código é nosso (a RFC 6238, conferida com os exemplos dela), sem o pyotp; o QR
  sai do segno (BSD-3);
- a sessão pela metade vale 10 minutos, e o código certo abre a de sempre com um código novo no
  cookie;
- quem já ligou a verificação responde ao código em qualquer ambiente;
- a administração zera a do usuário pela rota `POST /api/admin/usuarios/<id>/duas-etapas/zerar`
  (com a hora e quem zerou) e a dela pelo comando, com `--zerar-duas-etapas`.

**Commit:** `feat(cadastro): verificação em duas etapas para gestor e administração`

### Semana 2 — o motorista avisado de verdade

#### T52. Canais de mensagem e o WhatsApp

**Objetivo:** as mensagens da T43 saem de verdade, pelo WhatsApp (SDD 7.5, D-12).

**Depende de:**
- **para o código:** o app da Meta com o número de teste;
- **para o primeiro aviso:** F2;
- **para o número de verdade e os modelos aprovados:** N19.

**Arquivos:** `nuvem/src/nuvem/mensagens/` (canais, envio, webhook), migração, testes.

**Regras (teste primeiro):**
- **Uma interface de canal:** envia uma mensagem e devolve o id dela no canal, ou o erro.
  - O canal de demonstração continua igual: só guarda.
  - O ambiente de demonstração só usa ele.
- **O envio:**
  - é pelo worker: cada mensagem guardada vira uma tarefa "enviar", com a espera crescente da
    fila (D-38);
  - a situação vai de guardada para enviada, entregue, lida ou falhou, cada mudança com o
    horário.
- **A Cloud API da Meta**, direto e por `httpx`, sem biblioteca da Meta:
  - um modelo aprovado por tipo de mensagem, da categoria utilidade, com as variáveis (site,
    janela, posição, doca);
  - os textos dos modelos ficam no código.
- **O webhook da Meta:**
  - confere a assinatura (`X-Hub-Signature-256`, com o segredo do app) e recusa o pedido sem
    ela;
  - o mesmo aviso duas vezes não muda nada;
  - responde na hora e deixa o trabalho para o worker.
- **Mensagem do motorista:**
  - a autorização, pelo caminho que a F2 escolher;
  - "SAIR", que cancela a autorização na hora: nada mais vai por WhatsApp para aquele número
    daquela empresa.
- **A autorização** guarda o texto e o horário, como prova. Ela é do número, não do
  agendamento: trocar o celular a apaga (SDD 3.4).
- **Os erros da Meta** (limite de envio, número sem WhatsApp, modelo pausado) deixam a mensagem
  como falhou, com o código. A reserva por SMS é a T53.
- **O custo:** a categoria e o preço da tabela da Meta ficam em cada mensagem.
- **Os segredos** (o token, o segredo do app e o código de verificação do webhook) ficam só nas
  variáveis de ambiente.

**Verificar:** com o número de teste da Meta, as quatro mensagens chegam ao celular do Lorenzo, e
"SAIR" para o envio.

*Detalhado na execução (D-63):*
- o canal é escolhido ao gravar a mensagem: WhatsApp se o celular autorizou a empresa, senão SMS
  (que a T53 manda); sem o WhatsApp configurado, o de demonstração;
- a autorização vem da mensagem "AVISOS A<agendamento>" (o link do SMS) ou "AVISOS S<site>" (o QR
  da portaria, numa tela para o gestor imprimir); "SAIR" cancela em todas as empresas;
- o webhook só confere a assinatura e guarda o aviso numa tarefa; o worker faz o resto;
- o texto do "pode sair" ganhou "Pronto!" na frente: a Meta recusa modelo que começa com uma
  variável.

**Commit:** `feat(mensagens): WhatsApp pela Cloud API`

#### T53. SMS de reserva e o "motorista não avisado"

**Objetivo:** o motorista sempre fica sabendo, e, quando não fica, a portaria sabe (SDD 8.1).

**Depende de:** F2, F3, N20 e T52.

**Arquivos:** `nuvem/src/nuvem/mensagens/`, telas da portaria e do pátio, testes.

**Regras (teste primeiro):**
- **O canal de SMS** entra pela mesma interface de canal, por `httpx`.
- **Quando o aviso vai por SMS:**
  - no primeiro aviso, se a F2 for pelo SMS;
  - quando o número não tem autorização de WhatsApp;
  - quando o WhatsApp falhou de vez.
- **O texto do SMS** usa só os caracteres do GSM-7 (sem os acentos do português que ficam de
  fora dele) e tem até 160 caracteres: um pedaço só, o mais barato. Um teste confere cada
  modelo.
- **A situação da entrega** vem pelo retorno do fornecedor, com a conferência que ele oferecer.
- **Se o SMS também falha:**
  - a visita mostra "motorista não avisado" na portaria e no pátio;
  - o alerta da T57 dispara.

*Detalhado na execução (D-64):* o texto do SMS é outro, curto e sem acento, e o da confirmação
leva o link do WhatsApp; o retorno da Zenvia chega em `/api/sms/<segredo>` (ela não assina os
avisos); o "motorista não avisado" aparece no quadro do pátio, onde o líder chama o caminhão. Na
portaria, a tela mostra as passagens, e não o contato com o motorista: o aviso fica no pátio e
nos alertas (T57).

**Commit:** `feat(mensagens): SMS de reserva e o motorista não avisado`

### Semana 3 — a caixa no site e os alertas

#### T54. Saúde da caixa e a frota de borda

**Objetivo:** saber, de longe, se cada caixa e cada câmera estão bem (SDD 7.4 e 6.2).

**Arquivos:** `contratos/` (o formato da saúde), `borda/`, `nuvem/src/nuvem/frota/`, telas,
migração, testes.

**Regras (teste primeiro):**
- **A cada minuto, a caixa manda** (`POST /api/borda/saude`, com a chave dela):
  - a versão do programa e a do leitor;
  - CPU, temperatura, memória e disco;
  - cada câmera: se está no ar, os quadros por segundo e a hora do último quadro;
  - as passagens e as fotos na fila, e as recusadas;
  - a hora da caixa, para a nuvem medir a diferença do relógio.
- **O formato da saúde** fica no pacote `contratos/`, com a versão dele, como a passagem.
- **A saúde não entra na fila:** sem internet, a caixa não guarda saúde velha. Quando a conexão
  volta, o tamanho da fila mostra o atraso.
- **Na nuvem:**
  - a `CaixaBorda` guarda o último contato, a versão e a última saúde (SDD 5.1);
  - um histórico curto (7 dias) serve para ver o que aconteceu.
- **As telas:**
  - **"Frota de borda" da administração:** cada caixa, o site, a versão, o último contato, as
    câmeras e a fila;
  - **a portaria:** mostra "site sem conexão desde HH:MM" quando a caixa some (SDD 8.1).
- **Bibliotecas:** só com licença permissiva, conferida antes (ex.: psutil, BSD-3).

*Detalhado na execução (D-65):* o último contato é a hora da nuvem em que a última saúde
chegou (um relógio errado na caixa não esconde a queda); a caixa fica sem contato depois de 3
minutos, e a que nunca mandou saúde não conta (o site da demonstração tem caixa sem programa
rodando); o histórico de 7 dias se apaga ao receber, sem tarefa nova; a frota mostra o
histórico hora a hora. A roda do psutil 7.2.2 só traz o código dele (BSD-3), sem biblioteca de
terceiros dentro.

**Commit:** `feat(frota): saúde da caixa e a tela da frota`

#### T55. A caixa em contêineres, pronta para o site

**Objetivo:** a caixa sobe sozinha, num Ubuntu preparado, e trabalha mesmo sem a nuvem (SDD
7.4).

**Depende de:** N23, para conferir num N150 de verdade. Antes dele, confere num computador.

**Arquivos:**
- `borda/Dockerfile`;
- `infra/caixa/` (o compose do agente e do go2rtc e o arquivo de instalação do Ubuntu);
- `docs/guias/preparar-a-caixa.md`.

**Regras:**
- **A imagem do agente:**
  - Python 3.12, OpenCV sem interface (D-29), OpenVINO e o leitor, sem root;
  - os pesos vêm por volume, de `modelos/`, e não ficam na imagem.
- **O go2rtc** (MIT) recebe cada câmera uma vez só e a repassa ao agente. Ele também permite ver
  a câmera pelo Tailscale na instalação.
- **A caixa começa sem a nuvem:**
  - a configuração fica guardada no disco, como a chave, que só o dono lê;
  - se a nuvem não responde, a caixa começa com a última configuração que recebeu;
  - o disco da caixa é cifrado na preparação, porque a configuração traz as senhas das câmeras.
    Isso muda o SDD 7.4 e vira uma D-nn.
- **A rede:** a caixa só faz conexões de saída; a entrada fica fechada, e o acesso remoto é só
  pelo Tailscale (D-13).
- **A preparação:** um arquivo de instalação do Ubuntu Server 24.04 instala o Docker, o
  Tailscale, o NTP (o relógio da passagem é a prova) e o disco cifrado. O guia diz o resto.
- **Os créditos de terceiros** da imagem vão para `borda/AVISOS-DE-TERCEIROS.md`.

**Commit:** `infra(borda): a caixa em contêineres`

#### T56. Atualização da caixa

**Objetivo:** a caixa troca de versão sozinha e volta para a anterior se der errado (SDD 7.4).

**Depende de:** T54 e T55.

**Arquivos:** `borda/` (o atualizador), `nuvem/src/nuvem/frota/`, telas, migração, testes.

**Regras (teste primeiro):**
- **Qual versão cada caixa roda:**
  - a administração escolhe, para todas as caixas, para um site ou para uma caixa;
  - a caixa pergunta à nuvem e recebe a imagem pelo resumo dela (o *digest*).
- **O atualizador:**
  - é um serviço pequeno da caixa, fora do agente;
  - baixa a imagem do registro privado com uma credencial só de leitura e confere o resumo;
  - troca o agente e espera a saúde.
- **Se a saúde falha** (o agente não sobe, as câmeras não abrem em 5 minutos ou a saúde não
  chega), a caixa volta para a versão anterior e avisa.
- **A fila** (SQLite) fica num volume: nada se perde na troca.
- **A ordem:** a versão nova vai primeiro para uma caixa só e, depois, para as outras.
- **Cada atualização** (de qual versão, para qual, o resultado) aparece na frota.

**Commit:** `feat(borda): atualização com volta automática`

#### T57. Alertas

**Objetivo:** quem precisa agir fica sabendo na hora (SDD 3.3 e 8.1).

**Depende de:** F6, T52 e T54.

**Arquivos:** módulo `alertas` (novo), telas, migração, testes.

**Regras (teste primeiro):**
- **Cada alerta guarda:** o tipo, o site, sobre o quê (visita, caixa ou câmera), quando abriu,
  quando fechou e quem foi avisado, por onde.
- **Os tipos:**
  - a estadia perto das 5 horas (4 horas desde a chegada) e a estadia que passou das 5 horas;
  - a chegada sem agendamento;
  - a caixa sem contato há 3 minutos;
  - a câmera parada há 60 segundos;
  - o relógio da caixa com mais de 2 segundos de diferença;
  - o motorista não avisado;
  - a tarefa do worker que falhou de vez (para a administração).
- **Sem repetição:** um alerta abre uma vez e fecha sozinho quando a situação passa. Ele não se
  repete a cada minuto.
- **Quem confere:** o worker, a cada minuto, um de cada vez, como o "não veio".
- **Por onde vai:** o painel e as mensagens, como a F6 escolher.
- **Os tempos** (4 horas, 60 segundos, 3 minutos e 2 segundos) ficam no código até o
  `[ABERTO-09]` e o cliente do piloto.

**Commit:** `feat(alertas): alertas no painel e por mensagem`

### Semana 4 — prova, dados e integração

#### T58. Trilha de prova completa

**Objetivo:** a prova de cada visita, completa e conferível, para uma disputa de estadia (SDD
5.5; módulo `prova`, seção 3.3).

**Arquivos:** módulo `prova` (novo), telas, migração, testes.

**Regras (teste primeiro):**
- **A prova da visita** é uma página para imprimir ou salvar em PDF, como o extrato, mais um
  arquivo para baixar. Ela traz:
  - cada passagem: a hora da caixa, a faixa, a câmera, as placas lidas, a confiança e o recorte;
  - cada evento: quem, quando e o quê;
  - as conferências da placa;
  - as mensagens ao motorista: enviada, entregue e lida;
  - a saúde da caixa naquela hora, com o relógio conferido.
- **A cadeia:**
  - cada registro de prova ganha um resumo (SHA-256) que inclui o resumo do anterior da mesma
    visita;
  - cada foto ganha o resumo dela ao chegar;
  - uma conferência refaz a cadeia e aponta o primeiro elo quebrado.
- **A âncora do dia:**
  - o último resumo de cada visita que mudou no dia vai para um arquivo no S3, com trava contra
    apagar e mudar (*Object Lock*);
  - assim, nem quem mexer no banco consegue reescrever a prova sem deixar rastro;
  - o arquivo só tem resumos, nenhum dado pessoal.
- **Nada se edita:** a correção continua sendo um evento novo.
- **Quem vê:** só o gestor do site, com as regras de separação de sempre.
- **No SDD:** a cadeia e a âncora viram uma D-nn.

**Commit:** `feat(prova): a prova da visita, encadeada e conferível`

#### T59. Prazos de guarda e o pedido do titular

**Objetivo:** guardar só pelo tempo combinado e ajudar o cliente a responder ao titular dos
dados (SDD 8.3).

**Depende de:** `[ABERTO-04]`, para os prazos de verdade. Até lá, valem os padrões do SDD 8.3,
como parâmetros.

**Arquivos:** `nuvem/src/nuvem/` (a guarda), a administração, testes.

**Regras (teste primeiro):**
- **As fotos:**
  - ficam 90 dias (o padrão), menos as da visita com exceção aberta ou marcada "em disputa"
    pelo gestor; marcar a disputa é um evento;
  - o worker apaga a foto vencida;
  - a prova guarda o resumo da foto e diz "foto apagada pelo prazo de guarda em DD/MM";
  - apagar pelo prazo é uma exceção ao "foto não se edita" (SDD 5.5) e vira uma D-nn.
- **As visitas e a trilha de prova** ficam 5 anos (o padrão). O apagar delas entra antes do
  primeiro dado completar 5 anos.
- **O registro de erros** fica 30 dias.
- **O pedido do titular:** um comando da administração lista tudo o que existe de uma placa ou
  de um celular numa empresa. Com isso, o cliente (o controlador) responde ao titular.

**Commit:** `feat(guarda): prazos de guarda e o pedido do titular`

#### T60. Base de treino

**Objetivo:** a conferência do porteiro vira rótulo, só com a autorização do cliente (SDD 4.6,
item 2, e 8.3).

**Depende de:** a cláusula do contrato (N22), para valer com cliente. O código anda com dados
inventados.

**Arquivos:** módulo `treino` (novo), telas da administração, migração, testes.

**Regras (teste primeiro):**
- **O `Rotulo`** guarda o recorte, a placa certa, a origem (a conferência do porteiro ou a
  rotulagem) e se foi revisado (SDD 5.1).
- **Só com o contrato:**
  - só vira rótulo a conferência de uma empresa cujo contrato autoriza o treino;
  - a administração marca a data da cláusula;
  - sem ela, nada vira rótulo.
- **A tela de rotulagem da administração** (SDD 2.1): aceitar, corrigir ou descartar. Só os
  revisados vão para o treino.
- **A régua fixa:** os rótulos dela nunca entram no treino (SDD 4.7). A divisão fica gravada e
  não muda.
- **A exportação:** um comando monta a pasta no formato do treino, para o ambiente de treino
  (D-40).
- **Se o cliente revoga ou o contrato acaba**, os rótulos dele se apagam.
- **Só recortes de placa** (D-39). A gravação da região inteira, para treinar o detector, fica
  para quando houver um site (T21).

**Commit:** `feat(treino): a conferência vira rótulo`

#### T39. Gerador de placas sintéticas

**Objetivo:** placas geradas por programa, para começar o treino do OCR sem placas reais (D-44).

**Arquivos:** `ml/` (o gerador), testes.

**Regras (teste primeiro):**
- **Os formatos:** as placas Mercosul e as antigas, com as cores e as proporções de cada tipo,
  e o texto sempre no formato válido (a mesma regra de formato da seção 4.2).
- **A fonte das letras:** só com licença permissiva ou OFL (D-50), ou desenhada por nós. A
  fonte oficial das placas não entra sem licença que permita.
- **As variações**, imitando o recorte da câmera: perspectiva, borrão, luz, sujeira, um pedaço
  coberto, a compressão do JPEG e o tamanho.
- **Repetível:** a mesma semente gera as mesmas placas.
- **As imagens não vão para o Git:** ficam em `dados/`, e só o código entra.
- **A base Artificial Mercosur** (CC BY 4.0) entra com o crédito que a licença pede.

**Commit:** `feat(ml): gerador de placas sintéticas`

#### T61. Agendamentos por API e webhooks

**Objetivo:** o sistema do cliente manda os agendamentos e recebe os eventos da visita, sem
planilha (SDD 2.3, 3.3 e 3.4).

**Depende de:** o cliente do piloto pedir. Se não pedir, passa para o mês 5.

**Arquivos:** módulo `api_publica` (novo), o conector `api_generica`, telas do gestor, testes.

**Regras (teste primeiro):**
- **A chave de API** é por empresa e site. Como o link da transportadora:
  - o gestor a gera, e ela aparece uma vez só;
  - o banco guarda só o resumo;
  - o gestor pode revogá-la.
- **`POST /api/v1/agendamentos`** usa o conector `api_generica`, com as regras comuns da seção
  3.4. A resposta vem item por item.
- **Os webhooks:**
  - o gestor cadastra um endereço HTTPS;
  - a nuvem manda os eventos da visita (chegou, na fila, chamada, na doca, liberada, saiu, não
    veio);
  - cada envio é assinado com HMAC-SHA256 e leva o id do evento, para o cliente não contar duas
    vezes;
  - quando o envio falha, a nuvem tenta de novo pela fila de tarefas.
- **Sem o código anti-CSRF:** a rota com chave não usa o cookie, então entra nas isentas, com o
  teste.
- **Limite de pedidos** por chave.
- **A documentação** dessas rotas sai do próprio FastAPI, para o cliente.

**Commit:** `feat(api): agendamentos por API e webhooks`

#### T62. A versão do piloto em homologação

**Objetivo:** o marco do mês, rodado de ponta a ponta na homologação (SDD 9, itens 3 e 6).

**Depende de:** todas as anteriores; a T61, só se o cliente pedir.

**Arquivos:** `docs/guias/roteiro-do-piloto.md`, o simulador num contêiner, como uma caixa.

**Regras:**
- **O roteiro do marco**, passo a passo, com o que conferir em cada passo:
  1. o agendamento pela planilha (e pela API, se houver);
  2. o aviso ao motorista e a autorização do WhatsApp;
  3. o check-in, a exceção resolvida, a fila, a doca e a saída;
  4. os alertas;
  5. a prova da visita;
  6. o extrato.
- **As falhas do SDD 9:**
  - a internet da caixa cai e volta, sem perder nada;
  - a passagem chega duas vezes;
  - a câmera para;
  - a nuvem reinicia;
  - uma atualização da caixa dá errado e volta para a anterior.
- **A restauração da cópia do banco** passa.
- **A tag da versão** vai para a produção, que fica vazia e pronta para o piloto.

**Commit:** `docs: roteiro do piloto em homologação`

---

## 5. Trilha não técnica

| # | Tarefa | Por quê | Resolve |
|---|---|---|---|
| N19 | Com a verificação da empresa na Meta (N1): registrar o número do WhatsApp do produto (um chip só para isso) e mandar os modelos de mensagem da T52 para aprovação | o WhatsApp de verdade | T52 |
| N20 | Pedir o orçamento da Zenvia (F3) e abrir a conta de SMS | o SMS de reserva | T53 |
| N21 | Abrir a conta da AWS com alerta de gasto (N2). Separar o domínio de produção: é o da marca (`[ABERTO-01]`); até lá, a homologação usa um endereço provisório. Passar os acessos do deploy pelo cofre de segredos | a produção e a homologação | T49, T50 |
| N22 | Levar ao advogado (junto com a N3 e a N15): a autorização do motorista (F2, `[ABERTO-22]`), o SMS ao motorista, os prazos de guarda (`[ABERTO-04]`), a cláusula do treino e o modelo de contrato do piloto (`[ABERTO-07]`) | nada de dado de cliente sem isso | T52, T53, T59, T60 |
| N23 | Abrir a conta do Tailscale (D-13) e comprar uma caixa (N7) para conferir o contêiner e a atualização num N150 de verdade | a caixa pronta para o site | T49, T55, T56 |
| N24 | Fechar o piloto pago: o cliente, o site, o preço (`[ABERTO-06]`) e a data da instalação (mês 5); com ele, como medir as horas de portaria (`[ABERTO-05]`) e os tempos dos alertas (`[ABERTO-09]`) | o marco comercial do mês | `[ABERTO-05]`, `[ABERTO-06]`, `[ABERTO-09]` |

---

## 6. Ajustes no SDD feitos junto com este plano

- O cronograma do mês 4 (seção 10) com o que este plano traz:
  - a verificação em duas etapas, que a seção 8.2 já deixava para o mês 4;
  - a API e os webhooks, que estão no MVP (seção 2.3);
  - os prazos de guarda (seção 8.3);
  - as placas sintéticas (D-44).
- O novo `[ABERTO-22]`, sobre a autorização do motorista para o WhatsApp, e a nota dele nas
  seções 2.2 e 7.5 (SDD 0.41).
- Com a aprovação, as decisões D-57 a D-62 e a jornada do motorista nas seções 2.2 e 7.5; o
  `[ABERTO-22]` fecha pela D-58 (SDD 0.42).
- Os fatos do WhatsApp e do SMS conferidos em 06/10, com as fontes, em
  `docs/validacao/fatos-tecnicos-stack.md`.

---

## 7. Checklist de "mês 4 pronto"

- [x] F1 a F6 decididas e registradas no SDD (D-57 a D-62).
- [ ] Produção e homologação na AWS, com o deploy pela `main` e pela tag.
- [ ] Cópias diárias, restauração testada e alarmes funcionando.
- [ ] Verificação em duas etapas para o gestor e a administração.
- [ ] WhatsApp de verdade, com a autorização do motorista, e o SMS de reserva.
- [ ] Saúde da caixa, tela da frota, caixa em contêineres e atualização com volta.
- [ ] Alertas no painel e por mensagem.
- [ ] Prova da visita encadeada, com a âncora do dia.
- [ ] Prazos de guarda e o pedido do titular.
- [ ] Base de treino e gerador de placas sintéticas.
- [ ] **Marco:** o roteiro do piloto rodado na homologação, e a mesma versão na produção.

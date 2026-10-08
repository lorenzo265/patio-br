---
tipo: "pacote"
fonte: "borda/src/borda/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `borda/src/borda/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# borda

Pasta `borda/src/borda/`.

Agente da caixa de borda: captura, leitor de placas, composição e envio ([[4. Leitor de placas|SDD, seção 4]]).

## Subpacotes

- [[borda.leitor]]: Leitor de placas da caixa ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]]): a interface, o formato e a votação entre quadros.

## Módulos

### `borda.agente`

`borda/src/borda/agente.py`

O agente da caixa ([[7.4 A caixa de borda|SDD 7.4]]): junta captura, leitura, rastreamento, composição e fila.

Para cada câmera de placa (frente ou trás) há um rastreador; as leituras dos veículos passam,
por faixa, pela composição; cada composição vira uma passagem (com ``id`` novo e a hora da
caixa) e vai para a fila de envio com a foto de cada placa, em JPEG. A câmera de contexto não
lê placa; a foto dela entra com o borrão de rostos ([[8.3 LGPD|SDD 8.3]]), depois.

O remetente (``envio.Remetente``) esvazia a fila em outra linha de execução.

Dois jeitos de rodar: ``rodar`` junta fontes que acabam (arquivos, pastas) pela hora dos
quadros; ``rodar_ao_vivo`` lê câmeras ao vivo, cada uma na sua linha, até a caixa desligar
(SDD [[D-30]]).

- **`VERSAO_DO_LEITOR`** = `'v0'`: Vai em cada passagem (``versao_leitor``): o leitor v0, com pesos de terceiros ([[T15]]).
- **`ESPERA_DE_QUADROS`** = `60`: Quantos quadros podem esperar o agente ao vivo (cerca de 2 s de 6 câmeras a 5 por segundo).
- **`PRAZO_PARA_DESLIGAR`** = `5.0`: Segundos para processar, ao desligar, os quadros que já tinham chegado.
- **`FaixaDoAgente`** (classe): Uma faixa do site, como a nuvem a manda.
- **`CameraDoAgente`** (classe): Uma câmera do site, com o que a caixa precisa para ler o vídeo.
- **`ConfiguracaoDoAgente`** (classe): A configuração que a caixa baixa da nuvem (``GET /api/borda/configuracao``).
- **`RastreadorDeCamera`** (classe): O que o agente usa de um rastreador (``rastreio.Rastreador``).
- **`Agente`** (classe): O processo da caixa, uma câmera de cada vez (quem chama decide a ordem dos quadros).
- **`rodar`**: Roda o agente sobre as fontes (uma por câmera), na ordem do tempo, até acabarem.
- **`AgenteAoVivo`** (classe): O que ``rodar_ao_vivo`` usa do agente.
- **`rodar_ao_vivo`**: Roda o agente sobre câmeras ao vivo até ``parar`` ser ligado (SDD [[D-30]]).

### `borda.ativacao`

`borda/src/borda/ativacao.py`

Ativação da caixa e configuração baixada da nuvem ([[7.4 A caixa de borda|SDD 7.4]]).

A administração gera um código de uso único para o site; a caixa troca o código por uma chave
própria e, com ela, baixa as faixas e as câmeras do site. A chave é um segredo: fica num arquivo
que só o dono lê e não aparece ao imprimir a caixa.

- **`CaixaAtivada`** (classe): A caixa depois da ativação: a nuvem dela, os ids da nuvem e a chave.
- **`CodigoRecusadoError`** (classe): O código de ativação é inválido, já foi usado ou venceu.
- **`ChaveRecusadaError`** (classe): A nuvem não reconhece mais a chave (a caixa foi revogada, ou o banco foi zerado).
- **`ativar`**: Troca o código de ativação pela chave da caixa.
- **`baixar_configuracao`**: Baixa as faixas e as câmeras do site da caixa (com as senhas das câmeras).
- **`guardar_caixa`**: Guarda a caixa ativada num arquivo que só o dono lê (a chave é um segredo).
- **`ler_caixa`**: Lê a caixa guardada, ou ``None`` se ela ainda não foi ativada.

### `borda.caixa`

`borda/src/borda/caixa.py`

O programa da caixa de borda ([[7.4 A caixa de borda|SDD 7.4]]): ativa, baixa a configuração, lê as câmeras e envia.

Uso::

    caixa ativar --nuvem https://patio-br.example --codigo XXXX-XXXX-XXXX
    caixa rodar

- ``ativar`` troca o código (gerado pela administração para o site) pela chave da caixa e a
  guarda em ``dados/caixa/caixa.json``, que só o dono lê.
- ``rodar`` baixa a configuração, abre as câmeras de placa por RTSP, roda o agente, o remetente
  da fila (``dados/caixa/fila.sqlite``) e o pulso da saúde (a cada minuto, [[D-65]]) até receber o
  sinal de término (ou Ctrl+C). Os modelos do leitor v0 ficam em ``modelos/v0``
  (``uv run tarefas modelos``).

A configuração vale até o programa reiniciar. Sem a nuvem no ar, a caixa espera para começar:
a configuração não fica no disco, porque traz as senhas das câmeras.

- **`principal`**: Ponto de entrada do comando ``caixa``.
- **`main`**: O comando ``caixa`` de verdade: registro no terminal e o FFmpeg com RTSP por TCP.
- **`baixar_com_paciencia`**: Baixa a configuração; se a nuvem não responde, tenta de novo, esperando 1 s, 2 s, 4 s... até 5 min.

### `borda.captura`

`borda/src/borda/captura.py`

Captura ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]]): os quadros de uma câmera chegam por uma fonte, à taxa configurada.

A fonte entrega quadros com a hora em que foram vistos. ``amostrar`` deixa passar no máximo
``QUADROS_POR_SEGUNDO`` por segundo: caminhão na portaria anda devagar, e 3 a 5 quadros por
segundo bastam ([[4.4 Onde roda|SDD 4.4]]).

Fontes:

- ``FonteDeCamera``: uma câmera ao vivo (RTSP); se ela cai, a fonte tenta reabrir;
- ``FonteDeArquivo``: um arquivo de vídeo (ex.: uma gravação da portaria);
- ``FonteDePasta``: as imagens de uma pasta, em ordem de nome (os quadros de um vídeo);
- ``FonteDeMemoria``: quadros já prontos (testes e simulador).

O vídeo é lido pelo OpenCV sem interface gráfica, cujo FFmpeg é LGPL (SDD [[D-27]] e [[D-29]]).

- **`ESPERA_MAXIMA_DA_CAMERA`** = `30.0`: Segundos entre as tentativas de reabrir uma câmera: 1, 2, 4... até 30.
- **`PRAZO_DA_CAMERA`** = `10.0`: Segundos que a câmera tem para abrir e para mandar cada quadro; depois, conta como caída.
- **`QuadroNoTempo`** (classe): Um quadro e a hora em que a câmera o viu (o relógio da caixa).
- **`FonteDeQuadros`** (classe): De onde vêm os quadros de uma câmera.
- **`amostrar`**: Deixa passar no máximo ``por_segundo`` quadros por segundo.
- **`FonteAmostrada`** (classe): Uma fonte com a taxa limitada por ``amostrar`` (ex.: uma pasta de 30 quadros/s a 5).
- **`FonteDeMemoria`** (classe): Quadros já prontos, em memória.
- **`FonteDePasta`** (classe): As imagens de uma pasta, em ordem de nome, como quadros de um vídeo.
- **`VideoIlegivelError`** (classe): O arquivo de vídeo não abre (não existe, ou o formato não é lido).
- **`FonteDeArquivo`** (classe): Um arquivo de vídeo, lido do começo ao fim (ex.: uma gravação da portaria).
- **`VideoAberto`** (classe): Uma câmera aberta.
- **`abrir_camera`**: Abre a câmera pelo OpenCV, com prazo para abrir e para cada quadro.
- **`sem_credenciais`**: O endereço sem o login e a senha, para registro.
- **`com_credenciais`**: O endereço da câmera com o login e a senha (codificados: ``@``, ``:`` e ``/`` não quebram o endereço). Credenciais que já estavam no endereço são trocadas.
- **`FonteDeCamera`** (classe): Uma câmera ao vivo (RTSP): a hora de cada quadro é a do relógio da caixa.

### `borda.composicao`

`borda/src/borda/composicao.py`

Composição na caixa ([[4.3 Composições e o que a câmera não vê|SDD 4.3]], [[D-23]]): junta, por faixa, o cavalo e o reboque de um caminhão.

A câmera da frente lê o cavalo (reboque não tem placa na frente). A de trás lê a placa traseira
do último reboque, ou a do próprio cavalo quando ele passa sem reboque. As regras:

- leitura da frente: é o cavalo, e espera a de trás até o fim da janela (padrão 30 s);
- leitura de trás com placa diferente: é o reboque da composição mais recente da faixa, que
  se fecha ali; as mais antigas que ainda esperavam saem sozinhas (veio um veículo depois);
- leitura de trás igual à da frente: é o mesmo veículo, sem reboque; fecha só com o cavalo;
- leitura de trás sem frente na janela: sai na hora, com papel ``desconhecido``;
- leitura da frente sem a de trás no fim da janela: sai sozinha, como cavalo;
- leitura sem placa legível (o veículo foi visto, a placa não) segue as mesmas regras, mas não
  vira placa: a frente ilegível deixa a traseira com papel ``desconhecido``, e sem placa
  nenhuma a composição sai vazia (a nuvem trata como exceção).

O tempo é o das leituras (relógio da caixa): ``vencer`` recebe a hora atual e devolve o que já
passou da janela.

- **`LeituraDeVeiculo`** (classe): A placa de um veículo numa câmera, já votada entre os quadros (ver ``votacao``).
- **`Composicao`** (classe): Uma passagem montada: as placas de um veículo numa faixa, com papel.
- **`Compositor`** (classe): Junta as leituras de cada faixa em composições.

### `borda.envio`

`borda/src/borda/envio.py`

Fila de envio da caixa ([[7.4 A caixa de borda|SDD 7.4]], [[D-24]]): nenhuma passagem se perde se a internet cair.

1. Toda passagem é gravada primeiro na fila (SQLite, no disco da caixa), com as fotos.
2. O remetente envia na ordem em que as passagens aconteceram: as fotos e depois a passagem.
3. Falha passageira (rede, 5xx, 401, 408, 429): espera 1 s, 2 s, 4 s... até 5 min e tenta a
   mesma passagem de novo, sem passar à frente.
4. 201 ou 200: a passagem sai da fila.
5. Recusa definitiva (403, 409, 422): a passagem sai da fila e fica guardada à parte, com o
   motivo, para não travar as seguintes. Foto recusada de vez (409, 413, 415) fica de fora.

- **`ESPERA_MAXIMA`** = `300.0`: 5 minutos: o máximo entre duas tentativas, com a internet fora.
- **`RECUSA_DA_PASSAGEM`** = `frozenset({403, 409, 422})`: Respostas que não mudam se a mesma passagem for de novo (outro site, id de outra caixa, campo que não confere).
- **`RECUSA_DA_FOTO`** = `frozenset({409, 413, 415})`: Outra foto no mesmo ref, grande demais, não é JPEG.
- **`RECUSA_DA_SAUDE`** = `frozenset({403, 422})`: A saúde de outra caixa, ou fora do formato: a próxima vai do mesmo jeito.
- **`PassagemNaFila`** (classe): A próxima passagem a enviar, com as fotos que ainda não foram.
- **`ContagemDaFila`** (classe): O tamanho da fila, para a saúde da caixa ([[D-65]]).
- **`PassagemRecusada`** (classe): Uma passagem que a nuvem recusou de vez, guardada para o suporte ver.
- **`FilaDeEnvio`** (classe): As passagens que ainda não chegaram à nuvem, num arquivo SQLite.
- **`Resultado`** (classe): O que a nuvem respondeu, do ponto de vista da fila.
- **`Resposta`** (classe): A resposta da nuvem a um envio.
- **`Nuvem`** (classe): O lado da nuvem que a caixa usa: fotos e passagens, com a chave da caixa.
- **`Remetente`** (classe): Esvazia a fila, na ordem, esperando mais a cada falha seguida.

### `borda.rastreio`

`borda/src/borda/rastreio.py`

Rastreamento ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]], [[D-25]]): segue cada veículo entre os quadros de uma câmera.

Um rastreador nosso, no estilo do ByteTrack, sem o filtro de Kalman:

1. o detector acha os veículos do quadro;
2. as detecções de confiança alta se juntam às trilhas abertas pela maior sobreposição (IoU);
   depois, as de confiança baixa se juntam às trilhas que sobraram (o veículo segue mesmo
   quando o detector fica em dúvida), mas nunca abrem trilha nova;
3. em cada veículo achado, o leitor lê a placa no recorte do veículo;
4. a trilha que fica alguns quadros sem detecção se fecha: as leituras passam pela votação e
   viram uma ``LeituraDeVeiculo``, com o recorte da placa mais confiável para a foto.

Na portaria o caminhão anda devagar: a 5 quadros por segundo, a caixa de um quadro cobre boa
parte da do seguinte, e a sobreposição basta para seguir o veículo.

- **`CONFIANCA_ALTA`** = `0.5`: Detecção que abre trilha nova e tem a preferência.
- **`CONFIANCA_MINIMA`** = `0.1`: Abaixo disso, a detecção é ignorada.
- **`IOU_MINIMO`** = `0.3`: Sobreposição mínima para dizer que é o mesmo veículo do quadro anterior.
- **`QUADROS_PARA_SUMIR`** = `3`: Quadros seguidos sem o veículo para dar a passagem dele por encerrada.
- **`QUADROS_MINIMOS`** = `3`: Trilha sem placa lida só vira leitura (sem placa) se o veículo apareceu nesses quadros.
- **`Deteccao`** (classe): Um veículo achado num quadro.
- **`DetectorDeVeiculos`** (classe): Acha os veículos (caminhões, carros, ônibus) num quadro.
- **`Rastreador`** (classe): Segue os veículos de uma câmera e entrega uma leitura por veículo.
- **`iou`**: A sobreposição de duas regiões: a área em comum dividida pela área das duas juntas.

### `borda.saude`

`borda/src/borda/saude.py`

A saúde da caixa ([[7.4 A caixa de borda|SDD 7.4]], [[D-65]]): a cada minuto, a caixa conta à nuvem como está.

- **As câmeras:** ``FonteMedida`` anota cada quadro que chega ao agente (depois da amostragem);
  ``MedidorDasCameras`` diz se cada câmera está no ar (mandou quadro nos últimos 10 s), os
  quadros por segundo dos últimos 10 s e a hora do último quadro.
- **A máquina:** o psutil (BSD-3) mede a CPU (a média desde a medida anterior), a memória, o
  disco da pasta da fila e a temperatura do sensor mais quente.
- **O pulso:** manda uma saúde logo ao começar e outra a cada minuto. A saúde não entra na
  fila: a que não chega fica registrada e não vai de novo.

- **`INTERVALO`** = `60.0`: Segundos entre duas saúdes.
- **`JANELA_DOS_QUADROS`** = `timedelta(seconds=10)`: Os quadros por segundo são os desta janela; a câmera sem quadro nela saiu do ar.
- **`MAXIMO_DE_QUADROS_GUARDADOS`** = `1000`: Por câmera: o bastante para 100 quadros por segundo na janela.
- **`MedidorDasCameras`** (classe): Os quadros que chegam de cada câmera, contados para a saúde.
- **`FonteMedida`** (classe): Uma fonte cujos quadros são anotados no medidor, um a um, quando passam.
- **`Maquina`** (classe): A máquina da caixa num momento.
- **`medir_a_maquina`**: A CPU (desde a medida anterior), a temperatura, a memória e o disco da ``pasta``.
- **`temperatura_mais_quente`**: A temperatura do sensor mais quente, em °C; ``None`` sem sensor.
- **`montar_saude`**: A saúde da caixa em ``agora``, no formato do contrato.
- **`Pulso`** (classe): Manda a saúde logo ao começar e, depois, a cada minuto, até a caixa desligar.

## Testes

- `borda/tests/test_borda_agente.py`: Agente da caixa ([[7.4 A caixa de borda|SDD 7.4]]): junta rastreamento, composição e fila numa passagem por veículo.
- `borda/tests/test_borda_ativacao.py`: Ativação da caixa e configuração baixada da nuvem ([[7.4 A caixa de borda|SDD 7.4]]).
- `borda/tests/test_borda_caixa.py`: O programa da caixa ([[7.4 A caixa de borda|SDD 7.4]]): ativa, baixa a configuração, lê as câmeras e guarda passagens.
- `borda/tests/test_borda_captura.py`: Captura ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]]): os quadros chegam por uma fonte, à taxa configurada (padrão 5 por segundo).
- `borda/tests/test_borda_composicao.py`: Composição na caixa ([[4.3 Composições e o que a câmera não vê|SDD 4.3]], [[D-23]]): junta cavalo (frente) e reboque (trás) de cada faixa.
- `borda/tests/test_borda_envio.py`: Fila de envio da caixa ([[7.4 A caixa de borda|SDD 7.4]], [[D-24]]): nenhuma passagem se perde se a internet cair.
- `borda/tests/test_borda_formato.py`: Formato da placa lida ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]]): corrige por posição, nunca inventa caractere.
- `borda/tests/test_borda_pacote.py`: O pacote borda usa o mesmo contrato de passagem que o resto do sistema ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]]).
- `borda/tests/test_borda_rastreio.py`: Rastreamento ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]], [[D-25]]): uma leitura por veículo, com um vídeo sintético feito aqui.
- `borda/tests/test_borda_saude.py`: A saúde da caixa ([[7.4 A caixa de borda|SDD 7.4]], [[D-65]]): as câmeras, a máquina e o envio a cada minuto.
- `borda/tests/test_borda_votacao.py`: Votação entre os quadros de um mesmo veículo ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]]).

---

Do [[Mapa do código]].

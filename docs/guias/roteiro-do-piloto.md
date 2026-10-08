# Roteiro do piloto em homologação (T62)

O marco do mês 4: a versão do piloto rodada de ponta a ponta **na homologação**, com dados
inventados, antes de a produção receber o cliente (SDD 9, item 3). Cada passo diz o que fazer e o
que conferir. Anote o resultado de cada um (deu certo, ou o que deu errado e a hora) no PR da
T62: o que der errado vira uma tarefa.

## Antes de começar

- **A homologação no ar** (o guia da produção, `docs/guias/producao.md`): o `/saude` responde
  pelo domínio, e os e-mails dos alarmes foram confirmados.
- **Só dados inventados** (D-57): uma empresa de teste e placas inventadas. Para o WhatsApp e o
  SMS, o celular do Lorenzo, como o plano do mês 4 diz (ou um chip só para testes). Nunca o
  celular de outra pessoa.
- **A empresa de teste, pela administração** (a tela de cadastro, T63):
  - a empresa e o site;
  - a portaria, com uma faixa de entrada e uma de saída, e uma câmera inventada em cada;
  - duas docas;
  - o gestor, o porteiro e o líder de pátio.
- **O simulador numa imagem**, no papel da caixa (em qualquer máquina com Docker):

  ```bash
  docker build -f ferramentas/Dockerfile -t patio-simulador:local .
  ```

- **O código de ativação** da caixa de teste: na administração, na frota, para o site de teste.

O simulador guarda a chave, a configuração e a fila num volume (`patio-simulador`). Daqui em
diante, `simular` quer dizer:

```bash
docker run --rm -v patio-simulador:/simulador/dados \
  -v "$PWD/passagens.json:/simulador/passagens.json:ro" \
  patio-simulador:local --nuvem https://<domínio da homologação> --passagens /simulador/passagens.json
```

Na primeira vez, com `--codigo <código de ativação>` no fim.

## 1. O agendamento pela planilha

1. Entre como o gestor (com a verificação em duas etapas) e baixe o modelo da planilha.
2. Preencha quatro agendamentos para a próxima hora, com as placas do arquivo de passagens
   abaixo; ponha o celular de teste em um deles.
3. Suba a planilha.

**Conferir:** os quatro aparecem na tela de agendamentos, na janela certa; subir a mesma
planilha de novo não cria nada (os "iguais").

## 2. O aviso ao motorista e a autorização do WhatsApp

Precisa do número do WhatsApp (N19) e da conta de SMS (N20). Sem eles, as mensagens ficam no
canal de demonstração, e o passo confere só o que a tela mostra.

1. O celular de teste recebe o primeiro aviso por SMS, com o link que abre o WhatsApp com a
   mensagem pronta (D-58).
2. Mande a mensagem (`AVISOS A<número do agendamento>`).

**Conferir:** a resposta de confirmação chega; a conversa do agendamento mostra a autorização;
dali em diante, as mensagens vão pelo WhatsApp. Mandar `SAIR` cancela a autorização.

## 3. A chegada, a exceção, a fila, a doca e a saída

O arquivo `passagens.json` (as placas são inventadas; os ids fixos servem ao teste da passagem
repetida):

```json
[
  {"id": "00000000-0000-4000-8000-0000000000a1",
   "placas": [{"placa": "TST1A23", "papel": "cavalo", "confianca": 0.97, "quadros": 6}]},
  {"id": "00000000-0000-4000-8000-0000000000a2",
   "placas": [{"placa": "TST4B56", "papel": "cavalo", "confianca": 0.95, "quadros": 6}]},
  {"id": "00000000-0000-4000-8000-0000000000a3",
   "placas": [{"placa": "TST7C80", "papel": "cavalo", "confianca": 0.62, "quadros": 3}]}
]
```

A terceira tem uma letra errada de propósito (o agendamento é `TST7C89`): vira exceção.

1. `simular` (com o código, na primeira vez).
2. Na portaria, o porteiro resolve a exceção (corrige a placa).
3. No pátio, o líder chama as três para as docas, começa e termina.
4. Mande a saída de uma delas: `simular` com um `saida.json` montado no lugar do
   `passagens.json`, que só diz o sentido:
   `[{"sentido": "saida", "placas": [{"placa": "TST1A23", "papel": "cavalo", "confianca": 0.9, "quadros": 4}]}]`.

**Conferir:** o check-in de cada chegada, na hora da caixa; a exceção com os candidatos; a fila e
as docas no pátio; a visita encerrada na saída. O celular de teste recebe "na fila, posição X",
"vá para a doca" e "pode sair".

## 4. Os alertas

- **"Não veio":** o quarto agendamento, sem chegada, vira "não veio" depois da janela e da
  tolerância.
- **A câmera parada** (precisa da caixa de verdade, N23): desligue o cabo de uma câmera. Em 60
  segundos, o alerta abre no sino e chega pelo WhatsApp de quem autorizou; religue, e ele fecha.

**Conferir:** cada alerta abre uma vez e fecha sozinho; não se repete a cada minuto.

## 5. A prova da visita

Abra a página da prova de uma visita encerrada.

**Conferir:** a cadeia confere do começo ao fim; o arquivo da prova baixa e traz a regra do
resumo; no dia seguinte, a âncora do dia aparece (na homologação, sem trava).

## 6. O extrato

**Conferir:** o extrato do mês em curso (parcial) conta as visitas do roteiro, com a estadia de
quem foi liberado na doca.

## As falhas (SDD 9)

1. **A internet da caixa cai e volta:** `simular` com `--network none` (antes do nome da
   imagem). O simulador avisa "sem rede: usando a configuração guardada" e deixa as passagens na
   fila. Depois, `simular` com a rede e um arquivo só com `[]`: as passagens da fila vão, com a
   hora em que a caixa as viu. Com a caixa de verdade (N23), o mesmo tirando o cabo de rede
   por 10 minutos.
2. **A passagem chega duas vezes:** `simular` de novo com o mesmo `passagens.json`. Nada novo na
   portaria: a nuvem ignora a repetida (SDD 5.5).
3. **A câmera para:** o passo 4, com a caixa de verdade (N23).
4. **A nuvem reinicia:** na homologação, `docker compose restart api worker` durante um
   `simular`. Nada se perde: o que não chegou fica na fila e vai na próxima rodada. O alarme
   "fora do ar" pode tocar e voltar a "OK".
5. **A atualização da caixa dá errado e volta** (precisa da caixa de verdade, N23): na
   administração, escolha para a caixa de teste uma versão cuja imagem não sobe. A caixa volta
   para a anterior sozinha, e a frota mostra a atualização como "voltou" (D-67).

## A restauração da cópia do banco

No primeiro dia, o worker faz a primeira cópia e a primeira restauração de teste (D-74).

**Conferir:** no CloudWatch, o registro diz "restauração de teste: a cópia N voltou e conferiu".

## A versão para a produção

Com tudo certo:

```bash
git tag nuvem-v0.1.0 && git push origin nuvem-v0.1.0
```

**Conferir:** a produção só sobe depois da aprovação do Lorenzo; o `/saude` dela responde; ela
fica vazia, só com a administração (nós), pronta para cadastrar o cliente do piloto.

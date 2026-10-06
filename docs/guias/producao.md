# Guia da produção e da homologação na AWS (T49 e T50; D-57, D-73 e D-74)

Como subir a nuvem do piloto em São Paulo (`sa-east-1`), da conta vazia ao primeiro deploy. O
código já está pronto: o compose das máquinas (`infra/producao/`), o workflow que publica e faz o
deploy (`.github/workflows/nuvem.yml`) e a imagem (`nuvem/Dockerfile`); a CI já sobe esse compose
como na homologação, a cada PR (o trabalho `producao` do `ci.yml`). Este guia é o que se faz
**uma vez**, à mão, quando a conta da AWS e o domínio existirem (N21).

As duas máquinas são iguais por dentro (o mesmo compose e a mesma imagem):

| | Produção | Homologação |
|---|---|---|
| Máquina | Lightsail 4 GB | Lightsail 2 GB |
| Banco | RDS PostgreSQL 16, cifrado, sem acesso público | PostgreSQL num contêiner (perfil `homologacao`) |
| Fotos | balde S3 privado e cifrado | outro balde S3, só com dados inventados |
| Âncoras da prova | balde com Object Lock (D-69) | sem trava (vão para o balde das fotos) |
| Cópias do banco | balde só delas, 30 dias (D-74) | outro balde, igual |
| Vai pelo deploy | etiqueta `nuvem-v<versão>`, com a aprovação do Lorenzo | cada commit na `main` |

## 1. As máquinas

1. No Lightsail, em `sa-east-1`, crie as duas máquinas com Ubuntu 24.04. No firewall do
   Lightsail, deixe só as portas **80 e 443** (o Caddy). A porta 22 **fica fechada**: quem entra
   é a Tailscale SSH (D-13).
2. Em cada máquina, instale o Docker (o pacote `docker.io` e o `docker-compose-v2` do Ubuntu) e
   a Tailscale, e ligue a Tailscale SSH com a etiqueta das máquinas:

   ```bash
   sudo tailscale up --ssh --advertise-tags=tag:servidor --hostname=patio-producao
   ```

   (na homologação, `--hostname=patio-homologacao`).
3. Crie o usuário do deploy, dono da pasta da nuvem e do grupo do Docker:

   ```bash
   sudo useradd --create-home --groups docker patio
   sudo mkdir -p /opt/patio && sudo chown patio: /opt/patio
   ```

4. Na política da Tailscale (o "access control"), deixe a etiqueta do GitHub entrar nas máquinas
   como `patio`, e só ela:

   ```json
   "tagOwners": { "tag:servidor": ["autogroup:admin"], "tag:ci": ["autogroup:admin"] },
   "ssh": [{ "action": "accept", "src": ["tag:ci"], "dst": ["tag:servidor"], "users": ["patio"] }]
   ```

## 2. O banco da produção (RDS)

1. Crie o RDS PostgreSQL 16 na menor instância, com o disco cifrado, **sem acesso público**, os
   backups automáticos de 7 dias e a volta a qualquer minuto ligada.
2. Ligue o Lightsail à rede do RDS ("VPC peering" do Lightsail) e deixe o grupo de segurança do
   RDS aceitar a porta 5432 só da faixa do Lightsail.
3. Crie o banco `patio` e um usuário só dele, com uma senha longa sorteada, que fica no
   gerenciador de senhas e no `.env` da máquina.
4. O RDS fala por SSL com um certificado da AWS: baixe o pacote de certificados da região
   (`sa-east-1-bundle.pem`) e ponha o conteúdo em `PATIO_BANCO_CA`, no `.env`, entre aspas
   duplas e com as quebras de linha.
5. Deixe o usuário `patio` criar banco: a restauração de teste de cada mês volta a cópia num
   banco temporário no mesmo servidor (`patio_restauracao_...`) e o apaga no fim (D-74). Com o
   usuário principal do RDS:

   ```sql
   ALTER ROLE patio CREATEDB;
   ```

   Na homologação, o usuário do contêiner já pode.

## 3. Os baldes S3

1. **Fotos** (um por ambiente): privado (o "Block Public Access" todo ligado), cifrado (SSE-S3).
   A caixa envia as fotos pelo endereço assinado do próprio S3 (D-22); a guarda de 90 dias é do
   worker (D-70), e não de uma regra do balde.
2. **Âncoras da prova** (só a produção): um balde **criado com o Object Lock ligado** (não dá para
   ligar depois sem pedir à AWS), privado e cifrado. A trava de 5 anos vai em cada arquivo, pelo
   código (D-69).
3. **Cópias do banco** (um por ambiente, D-74): privado e cifrado, como o das fotos. Sem regra de
   expiração: quem apaga as cópias de mais de 30 dias é o worker, e ele nunca apaga a mais nova.
4. Um usuário do IAM só para a nuvem, com uma política que só alcança esses baldes: ler, gravar e
   apagar no das fotos e no das cópias; ler e gravar no das âncoras (apagar, a trava não deixa).
   A chave e o segredo dele vão no `.env` da máquina.

## 4. O domínio

Aponte o domínio da produção e o da homologação (registros A) para o IP fixo de cada máquina.
O Caddy pede e renova o certificado HTTPS sozinho, na primeira vez que sobe.

## 5. A pasta da nuvem em cada máquina

Como `patio`, em `/opt/patio`:

1. Copie `infra/producao/compose.yml`, `infra/producao/compose.registros.yml` e
   `infra/producao/Caddyfile`.
2. Copie `infra/producao/env.exemplo` para `.env`, preencha e feche:

   ```bash
   chmod 600 .env
   ```

   A chave da cifra da produção é **nova**, gerada uma vez e guardada no gerenciador de senhas
   (perdê-la é perder as senhas das câmeras e os segredos do app autenticador):

   ```bash
   python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
   ```

3. Entre no registro do GitHub com um token que **só baixa** pacotes (`read:packages`):

   ```bash
   docker login ghcr.io -u <usuário do GitHub>
   ```

## 6. O registro e os alarmes (T50, D-74)

Tudo fica em dois modelos do CloudFormation, em `infra/producao/aws/`, um de cada por ambiente.
Com a AWS CLI, numa conta com permissão de administrador:

1. **O registro e o alarme de erro**, em São Paulo:

   ```bash
   aws cloudformation deploy --region sa-east-1 --stack-name patio-producao-alarmes \
     --template-file infra/producao/aws/alarmes.yml --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides Ambiente=producao Email=<quem recebe>
   ```

   Ele cria o grupo do registro (`patio-producao`, 30 dias), o alarme de erro e o usuário do IAM
   `patio-producao-registro`, que só escreve no registro.
2. **A verificação de fora e o alerta de gasto**, na `us-east-1` (é lá que a AWS os mede):

   ```bash
   aws cloudformation deploy --region us-east-1 --stack-name patio-producao-verificacao \
     --template-file infra/producao/aws/verificacao.yml \
     --parameter-overrides Ambiente=producao Dominio=<domínio> Email=<quem recebe> \
       GastoDoMes=<dólares combinados (N2)>
   ```

   O alerta de gasto é da conta inteira: só sai com o da produção.
3. Confirme a inscrição em cada e-mail que a AWS mandar ("AWS Notification - Subscription
   Confirmation"); sem isso, nenhum alarme chega.
4. No console do IAM, crie uma chave para o usuário `patio-producao-registro` e ponha no Docker
   da máquina (é o Docker, e não a nuvem, que manda o registro ao CloudWatch):

   ```bash
   sudo mkdir -p /etc/systemd/system/docker.service.d
   sudo tee /etc/systemd/system/docker.service.d/registro.conf > /dev/null <<'FIM'
   [Service]
   Environment="AWS_ACCESS_KEY_ID=<a chave>" "AWS_SECRET_ACCESS_KEY=<o segredo>"
   FIM
   sudo chmod 600 /etc/systemd/system/docker.service.d/registro.conf
   sudo systemctl daemon-reload && sudo systemctl restart docker
   ```

5. No `.env` da máquina, o `COMPOSE_FILE` e o `REGISTRO_GRUPO` (estão no `env.exemplo`) ligam o
   registro no CloudWatch.

Na homologação, o mesmo, com `Ambiente=homologacao`, `patio-homologacao-...` e o domínio dela.

## 7. O GitHub

1. Em "Settings → Environments", crie `homologacao` (sem aprovação) e `producao`, com o Lorenzo
   como revisor obrigatório: a etiqueta só chega à produção depois que ele aprova.
2. Na Tailscale, crie um cliente OAuth com a etiqueta `tag:ci` e ponha o id e o segredo nos
   segredos do repositório: `TS_OAUTH_CLIENT_ID` e `TS_OAUTH_SECRET`.
3. Nas variáveis do repositório, os nomes das máquinas na Tailscale: `MAQUINA_HOMOLOGACAO`
   (`patio-homologacao`) e `MAQUINA_PRODUCAO` (`patio-producao`).

## 8. O primeiro deploy

- **Homologação:** um commit na `main` publica a imagem `patio-nuvem:<commit>` e sobe na
  homologação. O deploy troca a versão no `.env`, baixa a imagem, roda as migrações e só então
  sobe a API e o worker (uma parada de segundos: a caixa guarda as passagens na fila).
- **Produção:** crie a etiqueta e espere a aprovação:

  ```bash
  git tag nuvem-v0.1.0 && git push origin nuvem-v0.1.0
  ```

## 9. O que conferir

- Um commit na `main` chega sozinho à homologação.
- O `/saude` responde pelo domínio, com HTTPS (`curl https://<domínio>/saude`).
- O simulador manda passagens à homologação, e a foto chega ao balde S3.
- A etiqueta chega à produção só depois da aprovação.
- No `.env` de cada máquina, só o dono lê (`ls -l /opt/patio/.env` mostra `-rw-------`).
- **As cópias:** no primeiro dia, o worker faz a primeira cópia e a primeira restauração de
  teste; no CloudWatch, o registro mostra "restauração de teste: a cópia 1 voltou e conferiu", e
  o balde das cópias tem o arquivo.
- **O worker parado toca o alarme em até 5 minutos:** `docker compose stop worker`; o `/saude`
  responde 503 depois de 2 minutos, e o e-mail do alarme "fora do ar" chega. Depois,
  `docker compose start worker` e o e-mail de "OK".
- **Um erro de propósito chega por e-mail** (o `run` passa pelo registro do Docker; o `exec`, não):

  ```bash
  docker compose run --rm --no-deps worker python -c "import logging; from nuvem import registro; \
    registro.configurar('producao'); logging.getLogger('nuvem').error('erro de propósito')"
  ```

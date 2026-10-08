# Guia da produção e da homologação na AWS (T49, D-57 e D-73)

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

## 3. Os baldes S3

1. **Fotos** (um por ambiente): privado (o "Block Public Access" todo ligado), cifrado (SSE-S3).
   A caixa envia as fotos pelo endereço assinado do próprio S3 (D-22); a guarda de 90 dias é do
   worker (D-70), e não de uma regra do balde.
2. **Âncoras da prova** (só a produção): um balde **criado com o Object Lock ligado** (não dá para
   ligar depois sem pedir à AWS), privado e cifrado. A trava de 5 anos vai em cada arquivo, pelo
   código (D-69).
3. Um usuário do IAM só para a nuvem, com uma política que só alcança esses baldes: ler, gravar e
   apagar no das fotos; ler e gravar no das âncoras (apagar, a trava não deixa). A chave e o
   segredo dele vão no `.env` da máquina.

## 4. O domínio

Aponte o domínio da produção e o da homologação (registros A) para o IP fixo de cada máquina.
O Caddy pede e renova o certificado HTTPS sozinho, na primeira vez que sobe.

## 5. A pasta da nuvem em cada máquina

Como `patio`, em `/opt/patio`:

1. Copie `infra/producao/compose.yml` e `infra/producao/Caddyfile`.
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

## 6. O GitHub

1. Em "Settings → Environments", crie `homologacao` (sem aprovação) e `producao`, com o Lorenzo
   como revisor obrigatório: a etiqueta só chega à produção depois que ele aprova.
2. Na Tailscale, crie um cliente OAuth com a etiqueta `tag:ci` e ponha o id e o segredo nos
   segredos do repositório: `TS_OAUTH_CLIENT_ID` e `TS_OAUTH_SECRET`.
3. Nas variáveis do repositório, os nomes das máquinas na Tailscale: `MAQUINA_HOMOLOGACAO`
   (`patio-homologacao`) e `MAQUINA_PRODUCAO` (`patio-producao`).

## 7. O primeiro deploy

- **Homologação:** um commit na `main` publica a imagem `patio-nuvem:<commit>` e sobe na
  homologação. O deploy troca a versão no `.env`, baixa a imagem, roda as migrações e só então
  sobe a API e o worker (uma parada de segundos: a caixa guarda as passagens na fila).
- **Produção:** crie a etiqueta e espere a aprovação:

  ```bash
  git tag nuvem-v0.1.0 && git push origin nuvem-v0.1.0
  ```

## 8. O que conferir

- Um commit na `main` chega sozinho à homologação.
- O `/saude` responde pelo domínio, com HTTPS (`curl https://<domínio>/saude`).
- O simulador manda passagens à homologação, e a foto chega ao balde S3.
- A etiqueta chega à produção só depois da aprovação.
- No `.env` de cada máquina, só o dono lê (`ls -l /opt/patio/.env` mostra `-rw-------`).

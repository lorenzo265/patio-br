# Demonstração na internet (Vercel e Supabase)

O passo a passo para pôr a demonstração no ar (T47, D-51 e D-56). O código já está pronto. O
que falta são as contas (N17) e o primeiro deploy, que ainda não foi feito: as conferências da
seção 5 ficam para ele.

## 1. Como fica

| Peça | Onde | Para quê |
|---|---|---|
| A nuvem (FastAPI) | uma função da Vercel, em São Paulo (`gru1`) | as telas e a API |
| O banco (PostgreSQL) | Supabase, em São Paulo (`sa-east-1`), pelo pooler em modo sessão | os dados inventados da demonstração |
| As fotos | Supabase Storage, pela API S3, num balde privado `fotos` | as placas desenhadas do dia de demonstração |
| O trabalho do worker | o **tique**, antes das telas que se atualizam sozinhas | o dia de demonstração, o casamento e as mensagens |
| A faxina | o **cron diário** da Vercel (`/api/cron/diaria`, às 6h de São Paulo) | apaga as empresas dos links vencidos e confere o "não veio" |

No ambiente `demonstracao`, a API da caixa não existe: as passagens vêm só do dia de
demonstração.

**Os planos** (conferidos em 10/2026; a escolha é do Lorenzo ao abrir as contas):
- a Vercel Hobby é só para uso pessoal, não comercial; para apresentar a empresas, o **Pro**
  custa US$ 20 por mês por pessoa;
- o Supabase Free pausa o projeto depois de uma semana sem uso; o **Pro** custa a partir de
  US$ 25 por mês e não pausa.

## 2. Supabase

1. Crie o projeto na região **South America (São Paulo)**. Guarde a senha do banco num
   gerenciador de senhas.
2. **O banco**:
   - em *Connect*, copie a conexão do **pooler em modo sessão** (*Session pooler*, porta 5432);
   - a conexão direta só tem IPv6, e a Vercel precisa de IPv4;
   - troque o começo por `postgresql+pg8000://`. Fica assim:

   ```text
   postgresql+pg8000://postgres.<projeto>:<senha>@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
   ```

3. **O certificado:** em *Database → Settings → SSL Configuration*, baixe o certificado. O texto
   dele (`-----BEGIN CERTIFICATE-----` ...) vai na variável `PATIO_BANCO_CA`.
4. **As fotos:**
   - em *Storage*, crie o balde `fotos`, **privado**;
   - em *Storage → Settings → S3*, gere uma chave de acesso;
   - anote o endereço (`https://<projeto>.storage.supabase.co/storage/v1/s3`) e a região.

## 3. Do computador: o banco e a administração

Com as variáveis do Supabase só no terminal, sem gravar no `.env`:

```bash
export PATIO_URL_BANCO='postgresql+pg8000://postgres.<projeto>:<senha>@aws-0-sa-east-1.pooler.supabase.com:5432/postgres'
export PATIO_CHAVE_CIFRA='<a chave da demonstração>'   # gere uma: veja abaixo
export PATIO_AMBIENTE=demonstracao
export PATIO_BANCO_SSL=1
export PATIO_BANCO_CA="$(cat prod-ca-2021.crt)"
uv run tarefas migrar                                 # cria as tabelas no Supabase
uv run python -m nuvem.administracao --nome "Lorenzo" --email <seu e-mail>
```

A chave da cifra da demonstração é nova, gerada uma vez e guardada no gerenciador de senhas:

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

No Windows (PowerShell), troque `export X=...` por `$env:X = '...'`.

## 4. Vercel

1. Importe o repositório `lorenzo265/patio-br` como projeto novo:
   - *Root Directory*: a raiz;
   - a Vercel acha o `app` pelo `[tool.vercel] entrypoint` do `pyproject.toml` (`vercel_app.py`);
   - a região (`gru1`) e o cron vêm do `vercel.json`.
2. **As variáveis de ambiente** (*Settings → Environment Variables*, em *Production*):

   | Variável | Valor |
   |---|---|
   | `PATIO_AMBIENTE` | `demonstracao` |
   | `PATIO_URL_BANCO` | a conexão do pooler, como na seção 2 |
   | `PATIO_CHAVE_CIFRA` | a chave da seção 3 |
   | `PATIO_URL_PUBLICA` | `https://<o domínio da demonstração>` |
   | `PATIO_CABECALHO_DO_IP` | `x-real-ip` |
   | `PATIO_TIQUE` | `1` |
   | `PATIO_BANCO_SEM_POOL` | `1` |
   | `PATIO_BANCO_SSL` | `1` |
   | `PATIO_BANCO_CA` | o texto do certificado do Supabase |
   | `PATIO_FOTOS_S3_ENDERECO` | `https://<projeto>.storage.supabase.co/storage/v1/s3` |
   | `PATIO_FOTOS_S3_REGIAO` | `sa-east-1` |
   | `PATIO_FOTOS_S3_BALDE` | `fotos` |
   | `PATIO_FOTOS_S3_CHAVE` e `PATIO_FOTOS_S3_SEGREDO` | a chave S3 do Supabase |
   | `CRON_SECRET` | um texto aleatório e longo (a Vercel o manda ao cron) |

3. **O domínio:** em *Settings → Domains*, o domínio escolhido na E1 (N16).

## 5. Conferir no primeiro deploy

O código foi testado aqui com o banco local e o S3 imitado, mas não na Vercel nem no Supabase.
No primeiro deploy, confira:

1. **A instalação:**
   - a Vercel instala pelo `pyproject.toml` com o `uv.lock`, e o projeto é um workspace do uv
     com cinco pacotes;
   - confira no registro do build que o `patio-nuvem` e o `patio-contratos` entraram e que o
     pacote ficou abaixo de 500 MB;
   - o `vercel.json` já deixa de fora `borda/`, `ml/` e os testes;
   - se a instalação do workspace não der certo, o caminho é um `requirements.txt` gerado pelo
     `uv export --package patio-nuvem`.
2. **`/saude`** responde `{"ok": true}`: a função alcança o banco pelo pooler, com SSL.
3. **Entrar** como a administração, gerar um link, abrir no celular e "Entrar na demonstração":
   - a primeira entrada leva uns 15 segundos;
   - o `maxDuration` está em 60.
4. **"Começar o dia":**
   - as chegadas aparecem com a foto (o tique e o S3);
   - a exceção se resolve pela portaria.
5. **O cron:** em *Settings → Cron Jobs*, "Run" uma vez; ele responde com quantas empresas
   apagou.
6. **O pooler em modo transação** (porta 6543) não aceita *prepared statements*. Fica no modo
   sessão, a menos que se confira que o pg8000 funciona nele.

Se algo não funcionar, o registro da função (*Logs*) mostra o erro. Se faltar uma variável, ou
uma estiver errada, a nuvem não sobe, e o registro diz qual é.

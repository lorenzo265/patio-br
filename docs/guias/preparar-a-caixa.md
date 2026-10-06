# Guia de preparação da caixa de borda

Como deixar um mini PC pronto para a portaria de um site: o Ubuntu com o disco cifrado, o
Tailscale, o Docker e os dois contêineres da caixa, o agente e o go2rtc (SDD 7.4, D-66).

A caixa só faz conexões de saída. Depois da preparação, ninguém entra nela pela rede do cliente:
o acesso é só pelo Tailscale.

## O que é preciso

- O mini PC (N150, 16 GB), com o TPM ligado na BIOS (nas máquinas Intel, às vezes se chama
  "PTT").
- Dois pendrives: um com o Ubuntu Server 24.04 e outro, com o nome `CIDATA`, com o arquivo de
  instalação.
- Do cofre de senhas da equipe (nunca do repositório):
  - uma **senha de recuperação do disco** nova, só desta caixa;
  - o **resumo da senha** do usuário `patio` (`mkpasswd -m sha-512` na sua máquina);
  - a **chave pública SSH** de quem instala;
  - uma **chave de autorização do Tailscale** de uso único, com a etiqueta `tag:caixa`.
  - a **credencial do registro do GitHub** (`ghcr.io`) que só baixa imagens, para o atualizador.
- Um **código de ativação** do site, gerado pela administração (vale 24 horas).

## 1. O pendrive da instalação

1. Copie `infra/caixa/autoinstall.yaml` para uma pasta fora do repositório e troque os três
   `TROQUE-...` pelos valores do cofre. **Essa cópia nunca volta para o repositório.**
2. No pendrive `CIDATA`, grave a cópia com o nome `user-data` e um arquivo vazio `meta-data`.
3. Depois da instalação, apague o pendrive `CIDATA`: ele tem a senha do disco.

## 2. A instalação

1. Ligue o mini PC com os dois pendrives e escolha o pendrive do Ubuntu.
2. A instalação roda sozinha:
   - apaga o disco e o cifra (LUKS);
   - instala o Docker, o firewall e o Tailscale;
   - fecha a entrada (só o Tailscale entra);
   - acerta o relógio pelo NTP.br.
3. Ela pede uma confirmação antes de apagar o disco. No fim, a máquina reinicia e pede a senha
   do disco, só desta vez.

## 3. O primeiro acesso (com teclado e monitor)

1. Entre como `patio`.
2. Ligue a caixa ao Tailscale, com o nome do site:

   ```bash
   sudo tailscale up --auth-key=<chave do Tailscale> --hostname=caixa-<site>
   ```

3. Ligue o disco ao TPM, para ele destravar sozinho ao ligar (pede a senha de recuperação):

   ```bash
   sudo clevis luks bind -d "$(sudo blkid -t TYPE=crypto_LUKS -o device)" tpm2 '{"pcr_ids":"7"}'
   sudo update-initramfs -u -k all
   sudo reboot
   ```

   A máquina tem de voltar sem pedir a senha. Se pedir, o TPM não está ligado na BIOS.
4. Confira o relógio: `timedatectl` mostra `System clock synchronized: yes`.

Daqui em diante, entre pelo Tailscale: `ssh patio@caixa-<site>`.

## 4. Os programas da caixa

As imagens são montadas a partir do repositório, na sua máquina, e vão para a caixa pelo
Tailscale. Com a T56, a caixa passa a baixá-las sozinha.

```bash
docker build -f borda/Dockerfile -t patio-caixa:local .
docker build -f infra/caixa/go2rtc.Dockerfile -t patio-go2rtc:local infra/caixa
docker save patio-caixa:local patio-go2rtc:local | ssh patio@caixa-<site> docker load
```

Os pesos do leitor (`uv run tarefas modelos`) e o compose vão para `/opt/patio/`:

```bash
scp -r modelos/v0 patio@caixa-<site>:/opt/patio/modelos/
scp infra/caixa/compose.yml patio@caixa-<site>:/opt/patio/caixa/
```

Na caixa, em `/opt/patio/caixa/`:

```bash
docker compose run --rm agente caixa ativar --nuvem https://<nuvem> --codigo XXXX-XXXX-XXXX --pasta /caixa/dados
docker compose up -d
docker compose logs -f agente
```

## 5. O atualizador

O atualizador troca a versão do agente sozinho e volta para a anterior se der errado (SDD 7.4,
D-67). Ele roda no Ubuntu da caixa, fora dos contêineres, a cada 5 minutos:

```bash
scp borda/src/borda/atualizador.py patio@caixa-<site>:/opt/patio/
scp infra/caixa/patio-atualizador.service infra/caixa/patio-atualizador.timer patio@caixa-<site>:/tmp/
```

Na caixa:

```bash
sudo mv /tmp/patio-atualizador.* /etc/systemd/system/
# A credencial do registro do GitHub que só baixa imagens (do cofre de senhas da equipe):
sudo docker login ghcr.io -u <conta> --password-stdin
sudo systemctl enable --now patio-atualizador.timer
```

Para ver o que ele fez: `journalctl -u patio-atualizador`. Cada troca também aparece na frota de
borda.

### Uma versão nova

1. Crie a etiqueta `caixa-v0.2.0` no GitHub. O workflow "imagens publicadas" monta a imagem do
   agente, publica no `ghcr.io` e mostra o resumo (`sha256:…`).
2. Na administração, em "Versões da caixa", cadastre a versão com o nome e o resumo.
3. Escolha a versão para **uma caixa** e espere a atualização dar certo na frota.
4. Só então escolha para o site ou para todas as caixas.

## 6. Conferir

- **As câmeras:** na sua máquina, abra um túnel até a tela do go2rtc. Ela só responde na
  própria caixa:

  ```bash
  ssh -L 1984:127.0.0.1:1984 patio@caixa-<site>
  ```

  Depois, abra `http://localhost:1984`: as câmeras de placa aparecem como `camera-<id>`.
- **A frota de borda** (administração): a caixa aparece no ar, com as versões, as câmeras e a
  fila.
- **Sem a nuvem:** desligue a internet da caixa e reinicie (`docker compose restart agente`).
  A caixa começa com a configuração guardada e as passagens esperam na fila.

## Se a caixa se perder

1. Revogue a chave na administração (`POST /api/admin/caixas/<id>/revogar`): as chamadas dela
   passam a receber 401. Na próxima vez que começar, ela apaga a configuração guardada e para.
2. Tire a máquina do Tailscale.
3. Sem o TPM da própria máquina, o disco não abre: quem leva só o disco não lê as senhas das
   câmeras.

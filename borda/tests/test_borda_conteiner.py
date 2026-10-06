"""A caixa em contêineres (SDD 7.4, D-66): o que os arquivos da imagem, do compose e da
instalação do Ubuntu prometem. A CI monta as imagens de verdade ("imagens da caixa")."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.integracao  # lê os arquivos do repositório

RAIZ = Path(__file__).resolve().parents[2]
DOCKERFILE_DO_AGENTE = RAIZ / "borda" / "Dockerfile"
DOCKERFILE_DO_GO2RTC = RAIZ / "infra" / "caixa" / "go2rtc.Dockerfile"
COMPOSE = RAIZ / "infra" / "caixa" / "compose.yml"
AUTOINSTALL = RAIZ / "infra" / "caixa" / "autoinstall.yaml"


def _yaml(arquivo: Path) -> Any:
    return yaml.safe_load(arquivo.read_text(encoding="utf-8"))


def _ultimo_estagio(arquivo: Path) -> str:
    texto = arquivo.read_text(encoding="utf-8")
    return texto[texto.rindex("\nFROM ") :]


def _servicos() -> dict[str, Any]:
    servicos: dict[str, Any] = _yaml(COMPOSE)["services"]
    return servicos


# --- As imagens -----------------------------------------------------------------------------


def test_o_agente_roda_sem_root() -> None:
    ultimo = _ultimo_estagio(DOCKERFILE_DO_AGENTE)

    usuario = re.findall(r"^USER (\S+)", ultimo, re.MULTILINE)
    assert usuario
    assert usuario[-1] not in ("root", "0")


def test_a_imagem_do_agente_nao_leva_pesos_nem_dados() -> None:
    copias = re.findall(r"^COPY (.+)$", DOCKERFILE_DO_AGENTE.read_text(encoding="utf-8"), re.M)

    assert copias
    assert not [copia for copia in copias if "modelos" in copia or "dados" in copia]
    # E o contexto da montagem não manda o que não pode (CLAUDE.md, regras 3 e 4).
    ignorados = (RAIZ / ".dockerignore").read_text(encoding="utf-8").split()
    assert {"dados/", "modelos/", ".env"} <= set(ignorados)


def test_o_agente_comeca_rodando_a_caixa() -> None:
    assert 'CMD ["caixa", "rodar", "--pasta", "/caixa/dados"]' in _ultimo_estagio(
        DOCKERFILE_DO_AGENTE
    )


def test_o_go2rtc_e_montado_do_codigo_numa_versao_fixa_e_sem_ffmpeg() -> None:
    # As linhas que continuam na seguinte (com \ no fim) viram uma só.
    texto = DOCKERFILE_DO_GO2RTC.read_text(encoding="utf-8").replace("\\\n", " ")

    assert re.search(r"go install .*github\.com/AlexxIT/go2rtc@\$\{GO2RTC\}", texto)
    assert re.search(r"^ARG GO2RTC=v\d+\.\d+\.\d+$", texto, re.MULTILINE)
    # Nenhum pacote instalado; a imagem final é vazia e recebe só o binário do go2rtc.
    assert not re.search(r"(apk add|apt-get install|apt install)", texto)
    ultimo = _ultimo_estagio(DOCKERFILE_DO_GO2RTC)
    assert ultimo.startswith("\nFROM scratch")
    assert re.findall(r"^COPY .*$", ultimo, re.MULTILINE) == [
        "COPY --from=montagem /saida/go2rtc /go2rtc",
        "COPY --from=montagem /saida/licencas /licencas",  # MIT e BSD pedem o aviso junto
    ]
    usuario = re.findall(r"^USER (\S+)", ultimo, re.MULTILINE)
    assert usuario
    assert usuario[-1].split(":")[0] not in ("root", "0")


def test_o_go2rtc_nao_tem_arquivo_de_configuracao() -> None:
    # Sem arquivo, a senha de uma câmera nunca vai para o disco do go2rtc.
    ultimo = _ultimo_estagio(DOCKERFILE_DO_GO2RTC)

    assert ".yaml" not in ultimo
    assert "listen: ''" in ultimo  # o WebRTC desligado


# --- O compose ------------------------------------------------------------------------------


def test_o_compose_tem_o_agente_e_o_go2rtc() -> None:
    assert set(_servicos()) == {"agente", "go2rtc"}


@pytest.mark.parametrize("servico", ["agente", "go2rtc"])
def test_cada_conteiner_sobe_com_a_maquina_e_sem_privilegios(servico: str) -> None:
    conteiner = _servicos()[servico]

    assert conteiner["restart"] == "unless-stopped"
    assert conteiner["read_only"] is True
    assert conteiner["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in conteiner["security_opt"]


def test_nenhuma_porta_aberta_na_rede_do_cliente() -> None:
    for nome, conteiner in _servicos().items():
        for porta in conteiner.get("ports", []):
            assert str(porta).startswith("127.0.0.1:"), (nome, porta)
    assert "ports" not in _servicos()["agente"]


def test_os_pesos_entram_so_para_leitura() -> None:
    volumes = _servicos()["agente"]["volumes"]

    assert [volume for volume in volumes if volume.endswith(":/caixa/modelos:ro")]
    assert "dados:/caixa/dados" in volumes


def test_o_agente_le_as_cameras_pelo_go2rtc() -> None:
    agente = _servicos()["agente"]

    assert agente["environment"]["PATIO_GO2RTC"] == "http://go2rtc:1984"
    assert agente["depends_on"] == ["go2rtc"]


# --- A instalação do Ubuntu -----------------------------------------------------------------


def _autoinstall() -> dict[str, Any]:
    texto = AUTOINSTALL.read_text(encoding="utf-8")
    assert texto.startswith("#cloud-config\n")
    instalacao: dict[str, Any] = yaml.safe_load(texto)["autoinstall"]
    return instalacao


def test_a_instalacao_cifra_o_disco_sem_senha_de_verdade_no_repositorio() -> None:
    instalacao = _autoinstall()

    # O LVM com senha é o disco cifrado (LUKS); a senha de verdade fica no cofre da equipe.
    assert instalacao["storage"]["layout"]["name"] == "lvm"
    assert instalacao["storage"]["layout"]["password"].startswith("TROQUE-")
    assert instalacao["identity"]["password"].startswith("TROQUE-")
    assert all(chave.startswith("TROQUE-") for chave in instalacao["ssh"]["authorized-keys"])


def test_a_instalacao_nao_aceita_senha_pelo_ssh() -> None:
    assert _autoinstall()["ssh"]["allow-pw"] is False


def test_a_instalacao_traz_o_docker_o_firewall_e_o_tpm() -> None:
    pacotes = set(_autoinstall()["packages"])

    assert {"docker.io", "docker-compose-v2", "ufw", "clevis-tpm2", "clevis-luks"} <= pacotes


def test_a_instalacao_fecha_a_entrada_e_acerta_o_relogio() -> None:
    comandos = "\n".join(_autoinstall()["late-commands"])

    assert "ufw default deny incoming" in comandos
    assert "ufw allow in on tailscale0" in comandos
    assert "ntp.br" in comandos
    assert "pkgs.tailscale.com" in comandos


# --- A atualização (D-67) -------------------------------------------------------------------

SERVICO = RAIZ / "infra" / "caixa" / "patio-atualizador.service"
TIMER = RAIZ / "infra" / "caixa" / "patio-atualizador.timer"
PUBLICACAO = RAIZ / ".github" / "workflows" / "imagens.yml"


def test_o_atualizador_roda_fora_dos_conteineres_a_cada_5_minutos() -> None:
    servico = SERVICO.read_text(encoding="utf-8")
    timer = TIMER.read_text(encoding="utf-8")

    assert "Type=oneshot" in servico
    assert (
        "ExecStart=/usr/bin/python3 /opt/patio/atualizador.py --pasta /opt/patio/caixa" in servico
    )
    assert "OnUnitActiveSec=5min" in timer
    assert "OnBootSec=" in timer
    assert "WantedBy=timers.target" in timer


def test_o_agente_conta_a_versao_que_o_compose_passa() -> None:
    agente = _servicos()["agente"]

    assert agente["image"] == "${IMAGEM_DO_AGENTE:-patio-caixa:local}"
    assert agente["environment"]["PATIO_VERSAO"] == "${VERSAO_DO_AGENTE:-local}"


def test_a_imagem_e_publicada_so_pela_etiqueta_da_caixa() -> None:
    publicacao = _yaml(PUBLICACAO)
    gatilho = publicacao.get("on", publicacao.get(True))  # o YAML 1.1 lê "on" como verdadeiro

    assert gatilho == {"push": {"tags": ["caixa-v*"]}}
    assert publicacao["permissions"] == {"contents": "read", "packages": "write"}
    passos = publicacao["jobs"]["publicar"]["steps"]
    acoes = [passo["uses"] for passo in passos if "uses" in passo]
    # Só a ação de checkout, fixada pelo commit, como no resto da CI.
    assert [acao.split("@")[0] for acao in acoes] == ["actions/checkout"]
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", acao) for acao in acoes)
    comandos = "\n".join(passo.get("run", "") for passo in passos)
    assert "docker build -f borda/Dockerfile" in comandos
    assert "docker push" in comandos

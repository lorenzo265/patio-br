"""A produção e a homologação (SDD 7.2 e 7.3, D-57 e D-73): o que o compose das máquinas, o
Caddy, o ``.env`` de exemplo e o workflow do deploy prometem. Subir de verdade espera a conta da
AWS (N21); a CI sobe o compose como na homologação (o trabalho ``producao`` do ``ci.yml``)."""

import json
import logging
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from nuvem.registro import FormatoJson

pytestmark = pytest.mark.integracao  # lê os arquivos do repositório

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "infra" / "producao"
COMPOSE = PASTA / "compose.yml"
CADDYFILE = PASTA / "Caddyfile"
ENV_EXEMPLO = PASTA / "env.exemplo"
WORKFLOW = RAIZ / ".github" / "workflows" / "nuvem.yml"
CI = RAIZ / ".github" / "workflows" / "ci.yml"
DA_NUVEM = ("migracoes", "api", "worker")


def _yaml(arquivo: Path) -> Any:
    return yaml.safe_load(arquivo.read_text(encoding="utf-8"))


def _servicos() -> dict[str, Any]:
    servicos: dict[str, Any] = _yaml(COMPOSE)["services"]
    return servicos


# --- O compose ------------------------------------------------------------------------------


def test_a_api_o_worker_e_as_migracoes_sao_a_mesma_imagem() -> None:
    servicos = _servicos()

    imagens = {servicos[nome]["image"] for nome in DA_NUVEM}

    assert imagens == {"ghcr.io/lorenzo265/patio-nuvem:${VERSAO:?a versão da imagem, no .env}"}
    assert servicos["worker"]["command"] == ["python", "-m", "nuvem.worker"]
    assert servicos["migracoes"]["command"] == [
        "alembic", "-c", "nuvem/alembic.ini", "upgrade", "head"
    ]  # fmt: skip


def test_as_migracoes_rodam_antes_da_api_e_do_worker() -> None:
    servicos = _servicos()

    for nome in ("api", "worker"):
        dependencia = servicos[nome]["depends_on"]["migracoes"]
        assert dependencia["condition"] == "service_completed_successfully"
    assert servicos["migracoes"]["restart"] == "no"


def test_so_o_caddy_abre_portas() -> None:
    servicos = _servicos()

    abertas = {nome for nome, servico in servicos.items() if servico.get("ports")}

    assert abertas == {"caddy"}
    assert sorted(servicos["caddy"]["ports"]) == ["443:443", "443:443/udp", "80:80"]


@pytest.mark.parametrize("servico", DA_NUVEM)
def test_a_nuvem_roda_sem_privilegios_e_com_os_segredos_do_env(servico: str) -> None:
    configuracao = _servicos()[servico]

    assert configuracao["read_only"] is True
    assert configuracao["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in configuracao["security_opt"]
    assert configuracao["env_file"] == [".env"]
    assert "environment" not in configuracao  # os segredos só no .env da máquina


def test_a_homologacao_tem_o_banco_num_conteiner_e_a_producao_nao() -> None:
    servicos = _servicos()

    assert servicos["postgres"]["profiles"] == ["homologacao"]
    assert servicos["postgres"]["image"].startswith("postgres:16")
    assert "ports" not in servicos["postgres"]
    for nome in ("migracoes", "api", "worker"):
        dependencia = servicos[nome]["depends_on"]["postgres"]
        assert dependencia == {"condition": "service_healthy", "required": False}


def test_a_api_so_conta_como_no_ar_quando_responde_a_saude() -> None:
    saude = " ".join(_servicos()["api"]["healthcheck"]["test"])

    assert "/saude" in saude
    assert _servicos()["caddy"]["depends_on"]["api"]["condition"] == "service_healthy"


# --- O Caddy --------------------------------------------------------------------------------


def test_o_caddy_leva_o_dominio_a_api_e_diz_quem_pede() -> None:
    texto = CADDYFILE.read_text(encoding="utf-8")

    assert texto.lstrip().startswith("{$DOMINIO}")
    assert "reverse_proxy api:8000" in texto
    # O endereço de quem pede vai num cabeçalho que o Caddy escreve: quem pede não o falsifica.
    assert "header_up X-Real-IP {remote_host}" in texto


# --- O .env de exemplo ----------------------------------------------------------------------


def _env_exemplo() -> dict[str, str]:
    valores = {}
    for linha in ENV_EXEMPLO.read_text(encoding="utf-8").splitlines():
        if linha.strip() and not linha.lstrip().startswith("#"):
            nome, _, valor = linha.partition("=")
            valores[nome.strip()] = valor.split("#")[0].strip()
    return valores


def test_o_env_de_exemplo_tem_tudo_e_nenhum_segredo() -> None:
    valores = _env_exemplo()

    for obrigatoria in (
        "VERSAO", "DOMINIO", "PATIO_AMBIENTE", "PATIO_URL_BANCO", "PATIO_CHAVE_CIFRA",
        "PATIO_URL_PUBLICA", "PATIO_CABECALHO_DO_IP", "PATIO_FOTOS_S3_ENDERECO",
        "PATIO_FOTOS_S3_BALDE", "PATIO_FOTOS_S3_CHAVE", "PATIO_FOTOS_S3_SEGREDO",
    ):  # fmt: skip
        assert obrigatoria in valores, obrigatoria
    assert valores["PATIO_CABECALHO_DO_IP"] == "X-Real-IP"
    assert valores["PATIO_AMBIENTE"] == "producao"
    for nome in ("PATIO_CHAVE_CIFRA", "PATIO_FOTOS_S3_CHAVE", "PATIO_FOTOS_S3_SEGREDO"):
        assert valores[nome].startswith("TROQUE"), nome
    assert "TROQUE" in valores["PATIO_URL_BANCO"]


# --- O workflow do deploy -------------------------------------------------------------------


def _workflow() -> dict[str, Any]:
    conteudo: dict[str, Any] = _yaml(WORKFLOW)
    return conteudo


def test_a_main_vai_para_a_homologacao_e_a_etiqueta_para_a_producao() -> None:
    workflow = _workflow()
    gatilhos = workflow[True]  # o "on" do YAML vira True
    implantar = workflow["jobs"]["implantar"]

    assert gatilhos["push"] == {"branches": ["main"], "tags": ["nuvem-v*"]}
    assert implantar["needs"] == "publicar"
    # A produção é um ambiente do GitHub que pede a aprovação do Lorenzo.
    assert implantar["environment"] == (
        "${{ startsWith(github.ref, 'refs/tags/nuvem-v') && 'producao' || 'homologacao' }}"
    )
    maquina = implantar["env"]["MAQUINA"]
    assert "vars.MAQUINA_PRODUCAO" in maquina and "vars.MAQUINA_HOMOLOGACAO" in maquina


def test_o_deploy_entra_pela_tailscale_sem_chave_ssh() -> None:
    texto = WORKFLOW.read_text(encoding="utf-8")

    assert re.search(r"tailscale/github-action@[0-9a-f]{40} # v\d", texto)
    tailscale = [
        passo
        for passo in _workflow()["jobs"]["implantar"]["steps"]
        if passo.get("uses", "").startswith("tailscale/")
    ]
    assert [passo["with"]["tags"] for passo in tailscale] == ["tag:ci"]
    assert "ssh-key" not in texto.lower()
    assert "id_rsa" not in texto and "id_ed25519" not in texto


def test_nenhuma_expressao_do_github_dentro_dos_comandos() -> None:
    # Injeção de comandos: o que vem de fora (a etiqueta) entra por variável de ambiente, nunca
    # colado no script.
    for trabalho in _workflow()["jobs"].values():
        for passo in trabalho["steps"]:
            assert "${{" not in passo.get("run", ""), passo.get("name")


def test_a_versao_e_conferida_antes_de_ir_para_a_maquina() -> None:
    texto = WORKFLOW.read_text(encoding="utf-8")

    assert "[0-9A-Za-z._-]" in texto
    assert "docker compose up -d --wait" in texto


def test_a_ci_sobe_o_compose_da_producao_como_na_homologacao() -> None:
    passos = _yaml(CI)["jobs"]["producao"]["steps"]
    comandos = "\n".join(passo.get("run", "") for passo in passos)
    [subir] = [passo["run"] for passo in passos if "up -d --wait" in passo.get("run", "")]

    assert "cp infra/producao/compose.yml infra/producao/Caddyfile" in comandos
    assert "compose.registros.yml" in comandos
    assert "cp infra/producao/env.exemplo" in comandos  # o exemplo precisa ser lido
    assert "\nCOMPOSE_PROFILES=homologacao\n" in subir  # o banco num contêiner
    assert "https://localhost/saude" in comandos


# --- O registro no CloudWatch e os alarmes (D-74) -------------------------------------------

REGISTROS = PASTA / "compose.registros.yml"
ALARMES = PASTA / "aws" / "alarmes.yml"
VERIFICACAO = PASTA / "aws" / "verificacao.yml"
DOCKERFILE = RAIZ / "nuvem" / "Dockerfile"


def test_o_registro_de_cada_servico_vai_ao_cloudwatch_sem_travar_a_nuvem() -> None:
    servicos = _yaml(REGISTROS)["services"]

    assert set(servicos) == {"migracoes", "api", "worker", "caddy"}
    for nome, servico in servicos.items():
        registro = servico["logging"]
        assert registro["driver"] == "awslogs", nome
        opcoes = registro["options"]
        assert opcoes["awslogs-region"] == "sa-east-1"  # o registro fica no Brasil
        assert opcoes["awslogs-group"].startswith("${REGISTRO_GRUPO:?")
        assert opcoes["mode"] == "non-blocking"


def test_o_env_de_exemplo_liga_o_registro_e_o_balde_das_copias() -> None:
    valores = _env_exemplo()

    assert valores["COMPOSE_FILE"] == "compose.yml:compose.registros.yml"
    assert valores["REGISTRO_GRUPO"] == "patio-producao"
    assert valores["PATIO_COPIAS_S3_BALDE"].startswith("TROQUE")


def _recursos(arquivo: Path) -> dict[str, Any]:
    recursos: dict[str, Any] = _yaml(arquivo)["Resources"]
    return recursos


def test_cada_erro_do_registro_toca_o_alarme_por_email() -> None:
    recursos = _recursos(ALARMES)
    filtro = recursos["ContagemDeErros"]["Properties"]
    alarme = recursos["AlarmeDeErro"]["Properties"]

    assert recursos["Registro"]["Properties"]["RetentionInDays"] == 30
    # O filtro lê o campo que a nuvem escreve em cada linha (nuvem.registro.FormatoJson).
    linha = json.loads(
        FormatoJson().format(
            logging.LogRecord("nuvem", logging.ERROR, __file__, 1, "falhou", None, None)
        )
    )
    assert linha["nivel"] == "ERROR"
    assert '($.nivel = "ERROR")' in filtro["FilterPattern"]
    [metrica] = filtro["MetricTransformations"]
    assert (alarme["MetricName"], alarme["Namespace"]) == (
        metrica["MetricName"],
        metrica["MetricNamespace"],
    )
    assert (alarme["Period"], alarme["Threshold"], alarme["Statistic"]) == (60, 1, "Sum")
    assert alarme["ComparisonOperator"] == "GreaterThanOrEqualToThreshold"
    assert alarme["AlarmActions"] == [{"Ref": "Avisos"}]
    assert recursos["Avisos"]["Properties"]["Subscription"][0]["Protocol"] == "email"


def test_quem_escreve_o_registro_so_escreve_nele() -> None:
    usuario = _recursos(ALARMES)["QuemEscreveORegistro"]["Properties"]

    [politica] = usuario["Policies"]
    [permissao] = politica["PolicyDocument"]["Statement"]
    assert permissao["Effect"] == "Allow"
    assert sorted(permissao["Action"]) == ["logs:CreateLogStream", "logs:PutLogEvents"]
    assert permissao["Resource"] == {"Fn::GetAtt": ["Registro", "Arn"]}
    assert not any(r["Type"] == "AWS::IAM::AccessKey" for r in _recursos(ALARMES).values())


def test_o_saude_e_verificado_de_fora_a_cada_30_segundos() -> None:
    recursos = _recursos(VERIFICACAO)
    verificacao = recursos["Saude"]["Properties"]["HealthCheckConfig"]
    alarme = recursos["AlarmeDaSaude"]["Properties"]

    assert (verificacao["Type"], verificacao["ResourcePath"]) == ("HTTPS", "/saude")
    assert (verificacao["RequestInterval"], verificacao["FailureThreshold"]) == (30, 2)
    assert len(verificacao["Regions"]) >= 3
    assert alarme["MetricName"] == "HealthCheckStatus"
    assert alarme["Dimensions"] == [{"Name": "HealthCheckId", "Value": {"Ref": "Saude"}}]
    assert (alarme["ComparisonOperator"], alarme["Threshold"]) == ("LessThanThreshold", 1)
    assert alarme["TreatMissingData"] == "breaching"  # sem resposta também é fora do ar
    assert alarme["AlarmActions"] == [{"Ref": "Avisos"}]


def test_o_alerta_de_gasto_e_da_conta_e_sai_so_com_a_producao() -> None:
    modelo = _yaml(VERIFICACAO)
    gasto = modelo["Resources"]["Gasto"]

    assert gasto["Condition"] == "EAProducao"
    assert modelo["Conditions"]["EAProducao"] == {"Fn::Equals": [{"Ref": "Ambiente"}, "producao"]}
    orcamento = gasto["Properties"]["Budget"]
    assert (orcamento["TimeUnit"], orcamento["BudgetLimit"]["Amount"]) == (
        "MONTHLY",
        {"Ref": "GastoDoMes"},
    )
    tipos = {n["Notification"]["NotificationType"] for n in gasto["Properties"][
        "NotificationsWithSubscribers"]}  # fmt: skip
    assert tipos == {"ACTUAL", "FORECASTED"}


def test_a_imagem_tem_o_cliente_do_postgresql_da_versao_do_servidor() -> None:
    texto = DOCKERFILE.read_text(encoding="utf-8")

    assert "postgresql-client-16" in texto
    assert "/usr/lib/postgresql/16/bin" in texto
    assert _servicos()["postgres"]["image"].startswith("postgres:16")  # a mesma versão
    passos = _yaml(CI)["jobs"]["producao"]["steps"]
    comandos = "\n".join(passo.get("run", "") for passo in passos)
    assert 'pg_dump --version | grep -q " 16\\."' in comandos

"""O atualizador da caixa (SDD 7.4, D-14 e D-67): troca o agente e volta para o anterior se a
saúde não vier em 5 minutos."""

import io
import json
import subprocess
import urllib.error
import urllib.request
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from borda import atualizador
from borda.atualizador import DockerDoCompose, DockerFalhouError, Estado, NuvemDaCaixa, Versao

INICIO = datetime(2026, 10, 6, 17, 0, tzinfo=UTC)
RESUMO = "sha256:" + "a" * 64
NOVA = Versao(nome="0.2.0", imagem=f"ghcr.io/exemplo/patio-caixa@{RESUMO}")
ANTIGA = ("ghcr.io/exemplo/patio-caixa@sha256:" + "0" * 64, "0.1.0")


class Relogio:
    """Um relógio que anda só quando o atualizador dorme."""

    def __init__(self) -> None:
        self.agora = INICIO
        self.esperas: list[float] = []

    def __call__(self) -> datetime:
        return self.agora

    def dormir(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.agora += timedelta(seconds=segundos)


class NuvemFalsa:
    def __init__(self, versao: Versao | None = NOVA) -> None:
        self.a_versao = versao
        self.relatos: list[dict[str, str]] = []
        self.fora_do_ar = False
        self.perguntas = 0

    def versao(self) -> Versao | None:
        self.perguntas += 1
        if self.fora_do_ar:
            raise OSError("a nuvem não respondeu")
        return self.a_versao

    def contar(self, relato: dict[str, str]) -> None:
        if self.fora_do_ar:
            raise OSError("a nuvem não respondeu")
        self.relatos.append(relato)


class DockerFalso:
    def __init__(self, em_uso: tuple[str, str] = ANTIGA) -> None:
        self.imagem_em_uso = em_uso
        self.baixadas: list[str] = []
        self.trocas: list[tuple[str, str]] = []
        self.erro_ao_baixar: str | None = None
        self.erro_ao_trocar: str | None = None

    def em_uso(self) -> tuple[str, str]:
        return self.imagem_em_uso

    def baixar(self, imagem: str) -> None:
        if self.erro_ao_baixar:
            raise DockerFalhouError(self.erro_ao_baixar)
        self.baixadas.append(imagem)

    def trocar(self, imagem: str, nome: str) -> None:
        self.trocas.append((imagem, nome))
        if self.erro_ao_trocar and len(self.trocas) == 1:
            raise DockerFalhouError(self.erro_ao_trocar)
        self.imagem_em_uso = (imagem, nome)


def _saude(
    relogio: Relogio,
    *,
    segundos_depois: float = 30,
    versao: str = "0.2.0",
    aceita: bool = True,
    cameras: Sequence[tuple[str, bool]] = (("21", True), ("22", True)),
) -> dict[str, Any]:
    return {
        "gravada_em": (INICIO + timedelta(seconds=segundos_depois)).isoformat(),
        "aceita": aceita,
        "saude": {
            "versao_programa": versao,
            "cameras": [{"camera_id": camera, "no_ar": no_ar} for camera, no_ar in cameras],
        },
    }


def _atualizar(
    nuvem: NuvemFalsa,
    docker: DockerFalso,
    relogio: Relogio,
    saudes: list[dict[str, Any] | None],
    estado: Estado | None = None,
) -> tuple[str | None, Estado]:
    # Cada leitura devolve a próxima saúde da lista; a última fica valendo.
    leituras = list(saudes)

    def ler_saude() -> dict[str, Any] | None:
        return leituras.pop(0) if len(leituras) > 1 else (leituras[0] if leituras else None)

    estado = estado or Estado()
    resultado = atualizador.atualizar(
        nuvem, docker, ler_saude, estado, agora=relogio, dormir=relogio.dormir
    )
    return resultado, estado


# --- Quando não faz nada --------------------------------------------------------------------


def test_sem_versao_escolhida_nao_mexe_em_nada() -> None:
    docker = DockerFalso()

    resultado, _ = _atualizar(NuvemFalsa(None), docker, Relogio(), [])

    assert resultado is None
    assert (docker.baixadas, docker.trocas) == ([], [])


def test_a_versao_que_ja_roda_nao_e_trocada() -> None:
    docker = DockerFalso(em_uso=(NOVA.imagem, NOVA.nome))

    resultado, _ = _atualizar(NuvemFalsa(), docker, Relogio(), [])

    assert resultado is None
    assert docker.baixadas == []


def test_a_versao_que_ja_falhou_nesta_caixa_nao_e_tentada_de_novo() -> None:
    docker = DockerFalso()

    resultado, _ = _atualizar(NuvemFalsa(), docker, Relogio(), [], Estado(falhas=[RESUMO]))

    assert resultado is None
    assert docker.baixadas == []


def test_sem_a_nuvem_nao_mexe_em_nada() -> None:
    nuvem = NuvemFalsa()
    nuvem.fora_do_ar = True
    docker = DockerFalso()

    resultado, _ = _atualizar(nuvem, docker, Relogio(), [])

    assert resultado is None
    assert docker.baixadas == []


# --- A troca --------------------------------------------------------------------------------


def test_troca_o_agente_e_conta_que_deu_certo() -> None:
    nuvem, docker, relogio = NuvemFalsa(), DockerFalso(), Relogio()

    resultado, estado = _atualizar(nuvem, docker, relogio, [None, _saude(relogio)])

    assert resultado == "ok"
    assert docker.baixadas == [NOVA.imagem]
    assert docker.trocas == [(NOVA.imagem, "0.2.0")]
    (relato,) = nuvem.relatos
    assert relato == {
        "de": ANTIGA[0],
        "para": RESUMO,
        "comecou_em": INICIO.isoformat(),
        "terminou_em": (INICIO + timedelta(seconds=atualizador.INTERVALO)).isoformat(),
        "resultado": "ok",
        "motivo": "",
    }
    assert estado.falhas == []


def test_a_saude_e_conferida_a_cada_10_segundos_por_ate_5_minutos() -> None:
    relogio = Relogio()

    _atualizar(NuvemFalsa(), DockerFalso(), relogio, [None])

    assert set(relogio.esperas) == {atualizador.INTERVALO}
    assert sum(relogio.esperas) == atualizador.PRAZO_DA_SAUDE == 300


@pytest.mark.parametrize(
    ("saude", "motivo"),
    [
        (None, "a saúde do agente novo não chegou em 5 minutos"),
        ("de_antes", "a saúde do agente novo não chegou em 5 minutos"),
        ("no_instante_da_troca", "a saúde do agente novo não chegou em 5 minutos"),
        ("da_versao_antiga", "a saúde do agente novo não chegou em 5 minutos"),
        ("nao_aceita", "a nuvem não aceitou a saúde do agente novo"),
        ("camera_parada", "câmeras fora do ar: 22"),
    ],
)
def test_sem_a_saude_boa_volta_para_a_versao_anterior(saude: str | None, motivo: str) -> None:
    nuvem, docker, relogio = NuvemFalsa(), DockerFalso(), Relogio()
    lida = {
        None: None,
        "de_antes": _saude(relogio, segundos_depois=-1),
        "no_instante_da_troca": _saude(relogio, segundos_depois=0),
        "da_versao_antiga": _saude(relogio, versao="0.1.0"),
        "nao_aceita": _saude(relogio, aceita=False),
        "camera_parada": _saude(relogio, cameras=(("21", True), ("22", False))),
    }[saude]

    resultado, estado = _atualizar(nuvem, docker, relogio, [lida])

    assert resultado == "voltou"
    assert docker.trocas == [(NOVA.imagem, "0.2.0"), ANTIGA]
    assert [(r["resultado"], r["motivo"]) for r in nuvem.relatos] == [("voltou", motivo)]
    assert estado.falhas == [RESUMO]


def test_a_imagem_que_nao_baixa_falha_sem_trocar() -> None:
    nuvem, docker = NuvemFalsa(), DockerFalso()
    docker.erro_ao_baixar = "manifest unknown"

    resultado, estado = _atualizar(nuvem, docker, Relogio(), [])

    assert resultado == "falhou"
    assert docker.trocas == []
    assert [(r["resultado"], r["motivo"]) for r in nuvem.relatos] == [
        ("falhou", "a imagem não baixou: manifest unknown")
    ]
    assert estado.falhas == [RESUMO]


def test_o_agente_que_nao_sobe_volta_para_o_anterior() -> None:
    nuvem, docker = NuvemFalsa(), DockerFalso()
    docker.erro_ao_trocar = "container exited"

    resultado, _ = _atualizar(nuvem, docker, Relogio(), [])

    assert resultado == "voltou"
    assert docker.trocas == [(NOVA.imagem, "0.2.0"), ANTIGA]
    assert nuvem.relatos[0]["motivo"] == "o agente novo não subiu: container exited"


def test_o_relato_que_nao_chegou_vai_na_proxima_vez() -> None:
    nuvem, relogio = NuvemFalsa(), Relogio()
    docker = DockerFalso()
    docker.erro_ao_baixar = "registro fora do ar"
    original = nuvem.contar

    def contar_fora_do_ar(relato: dict[str, str]) -> None:
        raise OSError("a nuvem caiu")

    nuvem.contar = contar_fora_do_ar  # type: ignore[method-assign]
    _, estado = _atualizar(nuvem, docker, relogio, [])
    assert len(estado.pendentes) == 1

    nuvem.contar = original  # type: ignore[method-assign]
    nuvem.a_versao = None
    _atualizar(nuvem, docker, relogio, [], estado)

    assert [r["resultado"] for r in nuvem.relatos] == ["falhou"]
    assert estado.pendentes == []


# --- O estado guardado ----------------------------------------------------------------------


@pytest.mark.integracao  # grava no disco
def test_o_estado_volta_igual(tmp_path: Path) -> None:
    arquivo = tmp_path / "atualizador.json"
    estado = Estado(falhas=[RESUMO], pendentes=[{"resultado": "falhou"}])

    estado.gravar(arquivo)

    assert Estado.ler(arquivo) == estado


@pytest.mark.integracao
@pytest.mark.parametrize("conteudo", [None, "não é json", "[]", '{"falhas": 3}'])
def test_estado_que_nao_ha_ou_estragado_comeca_vazio(tmp_path: Path, conteudo: str | None) -> None:
    arquivo = tmp_path / "atualizador.json"
    if conteudo is not None:
        arquivo.write_text(conteudo, encoding="utf-8")

    assert Estado.ler(arquivo) == Estado()


# --- O Docker pelo compose ------------------------------------------------------------------


class Comandos:
    def __init__(self, codigo: int = 0, saida: str = "", erro: str = "") -> None:
        self.rodados: list[list[str]] = []
        self.codigo, self.saida, self.erro = codigo, saida, erro

    def __call__(self, comando: list[str], pasta: Path) -> subprocess.CompletedProcess[str]:
        self.rodados.append(comando)
        return subprocess.CompletedProcess(comando, self.codigo, self.saida, self.erro)


@pytest.mark.integracao
def test_sem_env_o_agente_e_o_da_preparacao(tmp_path: Path) -> None:
    assert DockerDoCompose(tmp_path, rodar=Comandos()).em_uso() == ("patio-caixa:local", "local")


@pytest.mark.integracao
def test_trocar_grava_o_env_e_sobe_o_agente(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "PASTA_DOS_MODELOS=/opt/patio/modelos\nIMAGEM_DO_AGENTE=velha\n", encoding="utf-8"
    )
    comandos = Comandos()
    docker = DockerDoCompose(tmp_path, rodar=comandos)

    docker.trocar(NOVA.imagem, NOVA.nome)

    assert docker.em_uso() == (NOVA.imagem, "0.2.0")
    assert "PASTA_DOS_MODELOS=/opt/patio/modelos" in (tmp_path / ".env").read_text(encoding="utf-8")
    assert comandos.rodados == [["docker", "compose", "up", "-d", "--wait", "agente"]]


@pytest.mark.integracao
def test_baixar_e_pelo_resumo(tmp_path: Path) -> None:
    comandos = Comandos()

    DockerDoCompose(tmp_path, rodar=comandos).baixar(NOVA.imagem)

    assert comandos.rodados == [["docker", "pull", NOVA.imagem]]


@pytest.mark.integracao
def test_o_erro_do_docker_vira_o_motivo(tmp_path: Path) -> None:
    docker = DockerDoCompose(tmp_path, rodar=Comandos(1, erro="linha 1\nmanifest unknown\n"))

    with pytest.raises(DockerFalhouError, match="manifest unknown"):
        docker.baixar(NOVA.imagem)


@pytest.mark.integracao
def test_le_a_saude_do_volume_dos_dados(tmp_path: Path) -> None:
    (tmp_path / "saude.json").write_text(json.dumps({"aceita": True}), encoding="utf-8")
    comandos = Comandos(saida=f"{tmp_path}\n")

    lida = DockerDoCompose(tmp_path, rodar=comandos).ler_do_volume("saude.json")

    assert lida == {"aceita": True}
    assert comandos.rodados == [
        ["docker", "volume", "inspect", "--format", "{{.Mountpoint}}", "patio-caixa_dados"]
    ]


@pytest.mark.integracao
def test_sem_o_arquivo_no_volume(tmp_path: Path) -> None:
    lida = DockerDoCompose(tmp_path, rodar=Comandos(saida=f"{tmp_path}\n")).ler_do_volume("x.json")

    assert lida is None


# --- A nuvem, com a chave da caixa ----------------------------------------------------------


class Respostas:
    def __init__(self, codigo: int, corpo: bytes = b"") -> None:
        self.codigo, self.corpo = codigo, corpo
        self.pedidos: list[urllib.request.Request] = []

    def __call__(self, pedido: urllib.request.Request, timeout: float) -> Any:
        self.pedidos.append(pedido)
        if self.codigo >= 400:
            raise urllib.error.HTTPError(pedido.full_url, self.codigo, "erro", {}, io.BytesIO())  # type: ignore[arg-type]

        class Resposta(io.BytesIO):
            status = self.codigo

        return Resposta(self.corpo)


def test_pergunta_a_versao_com_a_chave() -> None:
    respostas = Respostas(200, json.dumps({"nome": "0.2.0", "imagem": NOVA.imagem}).encode())

    versao = NuvemDaCaixa("https://nuvem.example/", "chave-inventada", abrir=respostas).versao()

    assert versao == NOVA
    (pedido,) = respostas.pedidos
    assert pedido.full_url == "https://nuvem.example/api/borda/versao"
    assert pedido.get_header("Authorization") == "Bearer chave-inventada"


@pytest.mark.parametrize(
    "imagem",
    [
        "ghcr.io/exemplo/patio-caixa:latest",  # uma etiqueta muda por baixo; o resumo, não
        "ghcr.io/exemplo/patio-caixa@sha256:curto",
        "ghcr.io/exemplo/patio-caixa@sha256:" + "a" * 63,
        "",
    ],
)
def test_a_imagem_sem_o_resumo_e_recusada(imagem: str) -> None:
    respostas = Respostas(200, json.dumps({"nome": "0.2.0", "imagem": imagem}).encode())

    with pytest.raises(ValueError):
        NuvemDaCaixa("https://nuvem.example", "c", abrir=respostas).versao()


def test_sem_versao_escolhida_a_nuvem_responde_204() -> None:
    assert NuvemDaCaixa("https://nuvem.example", "c", abrir=Respostas(204)).versao() is None


def test_conta_o_relato_a_nuvem() -> None:
    respostas = Respostas(201)

    NuvemDaCaixa("https://nuvem.example", "c", abrir=respostas).contar({"resultado": "ok"})

    (pedido,) = respostas.pedidos
    assert (pedido.full_url, pedido.get_method()) == (
        "https://nuvem.example/api/borda/atualizacoes", "POST",
    )  # fmt: skip
    assert json.loads(pedido.data) == {"resultado": "ok"}  # type: ignore[arg-type]
    assert pedido.get_header("Content-type") == "application/json"


def test_a_nuvem_que_recusa_e_um_erro_para_quem_chama() -> None:
    with pytest.raises(OSError):
        NuvemDaCaixa("https://nuvem.example", "c", abrir=Respostas(503)).versao()


def test_o_atualizador_usa_so_a_biblioteca_padrao() -> None:
    # Ele roda no Python do Ubuntu da caixa, fora do ambiente do projeto.
    texto = Path(atualizador.__file__).read_text(encoding="utf-8")
    importados = {
        linha.split()[1].split(".")[0]
        for linha in texto.splitlines()
        if linha.startswith(("import ", "from "))
    }

    assert importados <= {
        "argparse", "dataclasses", "datetime", "json", "logging", "os", "pathlib", "subprocess",
        "sys", "time", "typing", "urllib", "collections", "__future__",
    }  # fmt: skip

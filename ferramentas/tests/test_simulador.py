"""Simulador de portaria (SDD 6.4): manda passagens à nuvem como uma caixa de borda."""

import io
import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import cv2
import httpx
import numpy as np
import pytest
from PIL import Image

from borda.leitor.interface import LeituraBruta, Quadro, Regiao
from borda.rastreio import Deteccao
from simulador.__main__ import (
    ARQUIVO_DA_CAIXA,
    ARQUIVO_DA_CONFIGURACAO,
    cliente_para,
    principal,
)

pytestmark = pytest.mark.integracao  # fila e chave ficam em arquivos

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
NUVEM = "http://localhost:18000"

CONFIGURACAO = {
    "caixa_id": "7",
    "site_id": "1",
    "faixas": [
        {
            "id": "11",
            "nome": "Entrada 1",
            "sentido": "entrada",
            "cameras": [
                {
                    "id": "21",
                    "nome": "Entrada 1 — frente",
                    "posicao": "frente",
                    "endereco": "rtsp://10.0.0.11:554/stream1",
                    "login": "l",
                    "senha": "s",
                },
                {
                    "id": "22",
                    "nome": "Entrada 1 — traseira",
                    "posicao": "tras",
                    "endereco": "rtsp://10.0.0.12:554/stream1",
                    "login": "l",
                    "senha": "s",
                },
            ],
        },
        {
            "id": "12",
            "nome": "Saída 1",
            "sentido": "saida",
            "cameras": [
                {
                    "id": "23",
                    "nome": "Saída 1 — traseira",
                    "posicao": "tras",
                    "endereco": "rtsp://10.0.0.13:554/stream1",
                    "login": "l",
                    "senha": "s",
                },
            ],
        },
    ],
}


class NuvemFalsa:
    """Responde como a nuvem local; guarda o que recebeu."""

    def __init__(self) -> None:
        self.passagens: list[dict[str, Any]] = []
        self.fotos: dict[str, bytes] = {}
        self.codigos_usados: list[str] = []
        self.chaves_usadas: set[str] = set()
        self.chaves_revogadas: set[str] = set()
        self.entrou_como: str | None = None
        self.enderecos: set[str] = set()
        self.planilhas: list[tuple[str | None, str]] = []
        """As planilhas recebidas: o site pedido e o texto do CSV."""
        self.ordem: list[str] = []
        self.planilha_recusada: str | None = None
        self.sem_rede = False
        """A internet da caixa caiu: nenhum pedido chega."""

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        if self.sem_rede:
            raise httpx.ConnectError("sem rede", request=pedido)
        caminho = pedido.url.path
        self.enderecos.add(f"{pedido.url.host}:{pedido.url.port}")
        autorizacao = pedido.headers.get("authorization", "")
        if autorizacao:
            self.chaves_usadas.add(autorizacao.removeprefix("Bearer "))
        self.ordem.append(caminho)
        if caminho == "/entrar":
            self.entrou_como = dict(httpx.QueryParams(pedido.content.decode()))["email"]
            return httpx.Response(303, headers={"set-cookie": "patio_sessao=x; Path=/"})
        if caminho == "/api/cadastro/sites":
            return httpx.Response(
                200, json=[{"id": 1, "nome": "CD Exemplo", "fuso": "America/Sao_Paulo"}]
            )
        if caminho == "/api/agendamentos/planilha":
            if self.planilha_recusada:
                return httpx.Response(422, json={"detail": self.planilha_recusada})
            corpo = pedido.content.decode()
            csv = corpo[corpo.index("código;") : corpo.rindex("\r\n--")]
            self.planilhas.append((pedido.url.params.get("site_id"), csv))
            linhas = len(csv.strip().splitlines()) - 1
            return httpx.Response(
                200, json={"criados": linhas, "alterados": 0, "iguais": 0, "recusados": []}
            )
        if caminho == "/api/admin/sites":
            return httpx.Response(200, json=[{"id": 1, "empresa_id": 1, "nome": "CD Exemplo"}])
        if caminho == "/api/admin/sites/1/codigos-de-ativacao":
            return httpx.Response(201, json={"codigo": "AAAA-BBBB-CCCC", "expira_em": "x"})
        if caminho == "/api/borda/ativar":
            self.codigos_usados.append(json.loads(pedido.content)["codigo"])
            caixa = str(6 + len(self.codigos_usados))  # a primeira é a 7, depois 8...
            return httpx.Response(
                201, json={"caixa_id": caixa, "site_id": "1", "chave": f"chave-{caixa}"}
            )
        if caminho == "/api/borda/configuracao":
            if autorizacao.removeprefix("Bearer ") in self.chaves_revogadas:
                return httpx.Response(401, json={"detail": "caixa não identificada"})
            return httpx.Response(200, json=CONFIGURACAO)
        if caminho == "/api/borda/fotos/endereco":
            ref = json.loads(pedido.content)["ref"]
            endereco = str(pedido.url.copy_with(path=f"/envio/{ref}"))  # a própria nuvem
            return httpx.Response(200, json={"ref": ref, "endereco": endereco})
        if caminho.startswith("/envio/"):
            self.fotos[caminho.removeprefix("/envio/")] = pedido.content
            return httpx.Response(201)
        if caminho == "/api/borda/passagens":
            self.passagens.append(json.loads(pedido.content))
            return httpx.Response(201, json={"id": self.passagens[-1]["id"]})
        return httpx.Response(404)


@pytest.fixture
def nuvem() -> NuvemFalsa:
    return NuvemFalsa()


def _rodar(nuvem: NuvemFalsa, raiz: Path, *argumentos: str, **extras: Any) -> tuple[int, str]:
    saida = io.StringIO()
    cliente = httpx.Client(transport=httpx.MockTransport(nuvem))
    codigo = principal(
        ["--nuvem", NUVEM, *argumentos],
        cliente=cliente,
        raiz=raiz,
        agora=AGORA,
        saida=saida,
        **extras,
    )
    return codigo, saida.getvalue()


def test_demonstracao_ativa_sozinha_e_manda_a_amostra_com_fotos(
    nuvem: NuvemFalsa, tmp_path: Path
) -> None:
    codigo, saida = _rodar(nuvem, tmp_path, "--demonstracao", "--passagens", "amostra")

    assert codigo == 0, saida
    assert nuvem.entrou_como == "admin@patio-br.example"
    assert nuvem.codigos_usados == ["AAAA-BBBB-CCCC"]
    assert len(nuvem.passagens) == 5
    assert {p["caixa_id"] for p in nuvem.passagens} == {"7"}
    # As quatro primeiras entram; a última sai (a amostra diz só o sentido).
    assert [p["faixa_id"] for p in nuvem.passagens] == ["11", "11", "11", "11", "12"]
    assert [p["sentido"] for p in nuvem.passagens][-1] == "saida"
    placas = [[placa["placa"] for placa in p["placas"]] for p in nuvem.passagens]
    assert placas == [["ABC1D23", "XYZ9876"], ["BRA2E19"], [], ["CDE3F45"], ["FGH6I78"]]
    assert nuvem.passagens[-1]["placas"][0]["camera_id"] == "23"  # a traseira da saída
    # Cada placa da amostra leva uma foto desenhada (inventada), em JPEG.
    assert len(nuvem.fotos) == 5
    for conteudo in nuvem.fotos.values():
        with Image.open(io.BytesIO(conteudo)) as foto:
            assert foto.format == "JPEG"
    assert "5 enviadas" in saida
    assert nuvem.planilhas == []  # sem --agendamentos, nada de agendamento


def test_horarios_da_amostra_ficam_no_passado_e_em_ordem(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    _rodar(nuvem, tmp_path, "--demonstracao", "--passagens", "amostra")

    inicios = [datetime.fromisoformat(p["inicio"]) for p in nuvem.passagens]
    assert inicios == sorted(inicios)
    assert all(inicio <= AGORA for inicio in inicios)


def test_chave_fica_guardada_e_e_usada_de_novo(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    _rodar(nuvem, tmp_path, "--demonstracao", "--passagens", "amostra")

    codigo, _ = _rodar(nuvem, tmp_path, "--passagens", "amostra")

    assert codigo == 0
    assert nuvem.codigos_usados == ["AAAA-BBBB-CCCC"]  # ativou uma vez só
    guardada = json.loads((tmp_path / ARQUIVO_DA_CAIXA).read_text(encoding="utf-8"))
    assert (guardada["nuvem"], guardada["chave"]) == (NUVEM, "chave-7")


def test_demonstracao_de_novo_usa_a_mesma_caixa(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    # O que ficou na fila de uma rodada anterior é da caixa dela: noutra caixa, a nuvem o
    # recusaria (403).
    _rodar(nuvem, tmp_path, "--demonstracao", "--passagens", "amostra")

    codigo, _ = _rodar(nuvem, tmp_path, "--demonstracao", "--passagens", "amostra")

    assert codigo == 0
    assert nuvem.codigos_usados == ["AAAA-BBBB-CCCC"]
    assert nuvem.chaves_usadas == {"chave-7"}


def test_demonstracao_ativa_outra_caixa_se_a_chave_nao_vale_mais(
    nuvem: NuvemFalsa, tmp_path: Path
) -> None:
    # Ex.: o banco de desenvolvimento foi zerado, ou a caixa foi revogada.
    _rodar(nuvem, tmp_path, "--demonstracao", "--passagens", "amostra")
    nuvem.chaves_revogadas.add("chave-7")

    codigo, _ = _rodar(nuvem, tmp_path, "--demonstracao", "--passagens", "amostra")

    assert codigo == 0
    assert len(nuvem.codigos_usados) == 2
    assert nuvem.chaves_usadas == {"chave-7", "chave-8"}


class _Responde200(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()

    def log_message(self, *argumentos: Any) -> None:
        pass


@pytest.mark.integracao  # abre uma porta local
def test_nuvem_local_nao_passa_pelo_proxy_do_sistema(monkeypatch: pytest.MonkeyPatch) -> None:
    # O httpx usaria o proxy do sistema (no Windows, o do registro) também para o localhost, e
    # numa rede de empresa a demonstração falharia. Este proxy não existe: usado, a conexão cai.
    for nome in ("HTTP_PROXY", "http_proxy"):
        monkeypatch.setenv(nome, "http://127.0.0.1:9")
    for nome in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(nome, raising=False)
    servidor = HTTPServer(("127.0.0.1", 0), _Responde200)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        with cliente_para(f"http://127.0.0.1:{servidor.server_port}") as cliente:
            resposta = cliente.get(f"http://127.0.0.1:{servidor.server_port}/saude")
    finally:
        servidor.shutdown()
        servidor.server_close()

    assert resposta.status_code == 200


def test_nuvem_de_verdade_usa_o_proxy_do_sistema() -> None:
    # Numa rede que só sai pelo proxy, a nuvem de homologação ou produção precisa dele.
    assert cliente_para("https://patio.exemplo.com.br").trust_env


def _rodar_sem_nuvem(nuvem: NuvemFalsa, raiz: Path) -> int:
    return principal(
        ["--demonstracao", "--passagens", "amostra"],
        cliente=httpx.Client(transport=httpx.MockTransport(nuvem)),
        raiz=raiz,
        agora=AGORA,
        saida=io.StringIO(),
    )


def test_sem_nuvem_usa_a_porta_da_api_do_ambiente(
    nuvem: NuvemFalsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Como no docker compose: a variável do ambiente vale mais que o .env.
    monkeypatch.setenv("API_PORTA", "18555")
    (tmp_path / ".env").write_text("API_PORTA=18666\n", encoding="utf-8")

    assert _rodar_sem_nuvem(nuvem, tmp_path) == 0
    assert nuvem.enderecos == {"localhost:18555"}


def test_sem_nuvem_usa_a_porta_da_api_do_env(
    nuvem: NuvemFalsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Quem trocou a porta no .env (a 18000 estava ocupada) não fala com outro programa.
    monkeypatch.delenv("API_PORTA", raising=False)
    (tmp_path / ".env").write_text("# a API\nAPI_PORTA=18666\n", encoding="utf-8")

    assert _rodar_sem_nuvem(nuvem, tmp_path) == 0
    assert nuvem.enderecos == {"localhost:18666"}


def test_sem_nuvem_nem_porta_usa_a_18000(
    nuvem: NuvemFalsa, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("API_PORTA", raising=False)

    assert _rodar_sem_nuvem(nuvem, tmp_path) == 0
    assert nuvem.enderecos == {"localhost:18000"}


def test_codigo_de_ativacao_dado_na_linha_de_comando(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    codigo, _ = _rodar(nuvem, tmp_path, "--codigo", "XXXX-YYYY-ZZZZ", "--passagens", "amostra")

    assert (codigo, nuvem.codigos_usados) == (0, ["XXXX-YYYY-ZZZZ"])


def test_sem_chave_guardada_e_sem_codigo_explica_o_que_fazer(
    nuvem: NuvemFalsa, tmp_path: Path
) -> None:
    codigo, saida = _rodar(nuvem, tmp_path, "--passagens", "amostra")

    assert codigo == 1
    assert "--codigo" in saida and "--demonstracao" in saida


def test_demonstracao_so_no_ambiente_local(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    saida = io.StringIO()
    codigo = principal(
        ["--nuvem", "https://patio.exemplo.com.br", "--demonstracao", "--passagens", "amostra"],
        cliente=httpx.Client(transport=httpx.MockTransport(nuvem)),
        raiz=tmp_path,
        agora=AGORA,
        saida=saida,
    )

    assert codigo == 2
    assert "ambiente local" in saida.getvalue()
    assert nuvem.entrou_como is None


def test_faixa_pelo_nome(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    _rodar(nuvem, tmp_path, "--demonstracao", "--passagens", "amostra", "--faixa", "saida-1")

    assert {(p["faixa_id"], p["sentido"]) for p in nuvem.passagens} == {("12", "saida")}
    # Na saída só há câmera traseira: é ela que lê.
    assert {placa["camera_id"] for p in nuvem.passagens for placa in p["placas"]} == {"23"}


def test_faixa_que_nao_existe(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    codigo, saida = _rodar(
        nuvem, tmp_path, "--demonstracao", "--passagens", "amostra", "--faixa", "doca-9"
    )

    assert codigo == 1
    assert "Entrada 1" in saida  # mostra as faixas que existem


def test_arquivo_de_passagens_mantem_o_que_ja_vem_preenchido(
    nuvem: NuvemFalsa, tmp_path: Path
) -> None:
    arquivo = tmp_path / "minhas.json"
    arquivo.write_text(
        json.dumps(
            [
                {
                    "id": "00000000-0000-4000-8000-000000000001",
                    "inicio": "2026-10-05T13:59:00-03:00",
                    "placas": [
                        {
                            "placa": "abc-1234",
                            "papel": "cavalo",
                            "confianca": 0.5,
                            "quadros": 2,
                            "camera_id": "21",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    codigo, _ = _rodar(nuvem, tmp_path, "--demonstracao", "--passagens", str(arquivo))

    (passagem,) = nuvem.passagens
    assert codigo == 0
    assert passagem["id"] == "00000000-0000-4000-8000-000000000001"
    assert passagem["inicio"] == "2026-10-05T13:59:00-03:00"
    assert passagem["placas"][0]["placa"] == "ABC1234"


def test_video_que_nao_abre_explica(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    codigo, saida = _rodar(
        nuvem,
        tmp_path,
        "--demonstracao",
        "--video",
        str(tmp_path / "nao-existe.mp4"),
        carregar_modelos=lambda: (DetectorDeTudo(), LeitorFixo()),
    )

    assert codigo == 1
    assert "não abre" in saida
    assert nuvem.passagens == []


class DetectorDeTudo:
    """Vê um veículo onde houver pixel aceso."""

    def detectar(self, quadro: Quadro) -> list[Deteccao]:
        linhas, colunas = np.nonzero(quadro[:, :, 0])
        if len(linhas) == 0:
            return []
        regiao = Regiao(
            x=int(colunas.min()),
            y=int(linhas.min()),
            largura=int(colunas.max() - colunas.min() + 1),
            altura=int(linhas.max() - linhas.min() + 1),
        )
        return [Deteccao(regiao=regiao, confianca=0.9)]


class LeitorFixo:
    def ler(self, quadro: Quadro) -> list[LeituraBruta]:
        return [LeituraBruta("ABC1D23", 0.95, Regiao(x=0, y=0, largura=8, altura=4))]


def test_quadros_de_uma_pasta_passam_pelo_agente(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    pasta = tmp_path / "quadros"
    pasta.mkdir()
    for indice in range(8):
        imagem = np.zeros((60, 120, 3), dtype=np.uint8)
        if indice < 5:
            imagem[10:40, 10 + indice * 5 : 60 + indice * 5] = 200  # um veículo passando
        Image.fromarray(imagem).save(pasta / f"q{indice:03d}.png")

    codigo, saida = _rodar(
        nuvem,
        tmp_path,
        "--demonstracao",
        "--quadros",
        str(pasta),
        "--faixa",
        "entrada-1",
        "--camera",
        "frente",
        carregar_modelos=lambda: (DetectorDeTudo(), LeitorFixo()),
    )

    assert codigo == 0, saida
    assert [[placa["placa"] for placa in p["placas"]] for p in nuvem.passagens] == [["ABC1D23"]]
    assert nuvem.passagens[0]["versao_leitor"] == "v0"
    assert len(nuvem.fotos) == 1


@pytest.mark.integracao  # grava o vídeo no disco
def test_video_passa_pelo_agente(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    video = tmp_path / "portaria.avi"
    gravador = cv2.VideoWriter(str(video), cv2.VideoWriter.fourcc(*"MJPG"), 5.0, (120, 60))
    for indice in range(8):
        imagem = np.zeros((60, 120, 3), dtype=np.uint8)
        if indice < 5:
            imagem[10:40, 10 + indice * 5 : 60 + indice * 5] = 200  # um veículo passando
        gravador.write(imagem)
    gravador.release()

    codigo, saida = _rodar(
        nuvem,
        tmp_path,
        "--demonstracao",
        "--video",
        str(video),
        "--faixa",
        "entrada-1",
        "--camera",
        "frente",
        carregar_modelos=lambda: (DetectorDeTudo(), LeitorFixo()),
    )

    assert codigo == 0, saida
    assert [[placa["placa"] for placa in p["placas"]] for p in nuvem.passagens] == [["ABC1D23"]]
    assert len(nuvem.fotos) == 1


def test_dados_da_demonstracao_batem_com_a_semente_da_nuvem() -> None:
    from nuvem import semente
    from simulador.__main__ import (
        EMAIL_DA_ADMINISTRACAO,
        SENHA_DA_DEMONSTRACAO,
        SITE_DA_DEMONSTRACAO,
    )

    assert SENHA_DA_DEMONSTRACAO == semente.SENHA_DA_DEMONSTRACAO
    assert EMAIL_DA_ADMINISTRACAO == "admin@patio-br.example"
    assert SITE_DA_DEMONSTRACAO == "CD Exemplo"
    assert EMAIL_DA_ADMINISTRACAO in Path(semente.__file__).read_text(encoding="utf-8")


# --- Agendamentos (T35) ---------------------------------------------------------------------

CABECALHO_DA_PLANILHA = (
    "código;dia;início;fim;tipo;placa do cavalo;reboque 1;reboque 2;reboque 3;motorista;"
    "celular;toneladas;chave da NF-e"
)


def test_agendamentos_da_amostra_sobem_pela_planilha_antes_das_passagens(
    nuvem: NuvemFalsa, tmp_path: Path
) -> None:
    codigo, saida = _rodar(
        nuvem, tmp_path, "--demonstracao", "--agendamentos", "amostra", "--passagens", "amostra"
    )

    assert codigo == 0, saida
    assert nuvem.entrou_como == "gestor@empresa-a.example"
    [(site, csv)] = nuvem.planilhas
    linhas = csv.strip().splitlines()
    assert site == "1"
    assert linhas[0] == CABECALHO_DA_PLANILHA
    # AGORA é 14h em São Paulo; a primeira janela vai de 1h antes a 1h depois.
    assert linhas[1] == (
        "DEMO-20261005-140000-1;05/10/2026;13:00;15:00;descarga;ABC1D23;XYZ9876;;;"
        "Motorista Demonstração 1;;32,5;"
    )
    assert [linha.split(";")[5] for linha in linhas[1:]] == [
        "ABC1D23",
        "BRA2E19",
        "BRA2E19",
        "CDE3F45",
    ]
    assert nuvem.ordem.index("/api/agendamentos/planilha") < nuvem.ordem.index(
        "/api/borda/passagens"
    )
    assert "4 agendamentos: 4 novos, 0 alterados, 0 iguais" in saida


def test_cada_rodada_tem_codigos_novos(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    _rodar(nuvem, tmp_path, "--demonstracao", "--agendamentos", "amostra", "--passagens", "amostra")
    saida = io.StringIO()
    principal(
        ["--nuvem", NUVEM, "--demonstracao", "--agendamentos", "amostra", "--passagens", "amostra"],
        cliente=httpx.Client(transport=httpx.MockTransport(nuvem)),
        raiz=tmp_path,
        agora=AGORA.replace(minute=7),
        saida=saida,
    )

    codigos = [csv.splitlines()[1].split(";")[0] for _, csv in nuvem.planilhas]
    assert codigos == ["DEMO-20261005-140000-1", "DEMO-20261005-140700-1"]


def test_janela_que_passaria_da_meia_noite_para_no_fim_do_dia(
    nuvem: NuvemFalsa, tmp_path: Path
) -> None:
    # 23h30 em São Paulo: a janela de 1h depois passaria da meia-noite.
    saida = io.StringIO()
    principal(
        ["--nuvem", NUVEM, "--demonstracao", "--agendamentos", "amostra", "--passagens", "amostra"],
        cliente=httpx.Client(transport=httpx.MockTransport(nuvem)),
        raiz=tmp_path,
        agora=datetime(2026, 10, 6, 2, 30, tzinfo=UTC),
        saida=saida,
    )

    primeira = nuvem.planilhas[0][1].splitlines()[1].split(";")
    assert primeira[1:4] == ["05/10/2026", "22:30", "23:59"]


def test_agendamentos_so_com_demonstracao(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    codigo, saida = _rodar(
        nuvem, tmp_path, "--codigo", "AAAA-BBBB-CCCC", "--agendamentos", "amostra",
        "--passagens", "amostra",
    )  # fmt: skip

    assert codigo == 2
    assert "--agendamentos só vale com --demonstracao" in saida
    assert nuvem.planilhas == []


def test_planilha_recusada_pela_nuvem_explica(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    nuvem.planilha_recusada = "faltam as colunas: dia"

    codigo, saida = _rodar(
        nuvem, tmp_path, "--demonstracao", "--agendamentos", "amostra", "--passagens", "amostra"
    )

    assert codigo == 1
    assert "a nuvem recusou os agendamentos: faltam as colunas: dia" in saida


def test_arquivo_de_agendamentos_proprio(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    arquivo = tmp_path / "meus-agendamentos.json"
    agendamento = {"codigo": "X", "cavalo": "XYZ9K87", "de_minutos": 0, "ate_minutos": 30}
    arquivo.write_text(json.dumps([agendamento | {"tipo": "carga"}]), encoding="utf-8")

    codigo, saida = _rodar(
        nuvem, tmp_path, "--demonstracao", "--agendamentos", str(arquivo), "--passagens", "amostra"
    )

    assert codigo == 0, saida
    linha = nuvem.planilhas[0][1].splitlines()[1]
    assert linha == "DEMO-20261005-140000-X;05/10/2026;14:00;14:30;carga;XYZ9K87;;;;;;;"


def test_gestor_da_demonstracao_bate_com_a_semente_da_nuvem() -> None:
    from nuvem import semente
    from simulador.__main__ import GESTOR_DA_DEMONSTRACAO

    assert GESTOR_DA_DEMONSTRACAO == "gestor@empresa-a.example"
    assert 'gestor", "gestor"' in Path(semente.__file__).read_text(encoding="utf-8")


def test_colunas_da_planilha_batem_com_o_modelo_da_nuvem() -> None:
    from nuvem.agendamento.planilha import COLUNAS
    from simulador.__main__ import COLUNAS_DA_PLANILHA

    assert tuple(coluna.nome for coluna in COLUNAS) == COLUNAS_DA_PLANILHA


# --- A internet da caixa cai e volta (SDD 9, item 3; T62) -----------------------------------


def test_sem_rede_usa_a_configuracao_guardada_e_as_passagens_esperam_na_fila(
    nuvem: NuvemFalsa, tmp_path: Path
) -> None:
    primeira, _ = _rodar(nuvem, tmp_path, "--codigo", "XXXX-YYYY-ZZZZ", "--passagens", "amostra")
    enviadas = len(nuvem.passagens)
    nuvem.sem_rede = True

    codigo, saida = _rodar(nuvem, tmp_path, "--passagens", "amostra", "--esperar-no-maximo", "0")

    assert (primeira, codigo) == (0, 1)
    assert "sem rede: usando a configuração guardada" in saida
    assert f"0 enviadas; 0 recusadas pela nuvem; {enviadas} na fila" in saida
    assert len(nuvem.passagens) == enviadas

    # A rede volta: a próxima rodada manda o que ficou, sem perder nada.
    nuvem.sem_rede = False
    vazio = tmp_path / "nenhuma.json"
    vazio.write_text("[]", encoding="utf-8")
    codigo, saida = _rodar(nuvem, tmp_path, "--passagens", str(vazio))

    assert codigo == 0
    assert f"{enviadas} enviadas; 0 recusadas pela nuvem; 0 na fila" in saida
    assert len(nuvem.passagens) == 2 * enviadas
    assert len({p["id"] for p in nuvem.passagens}) == 2 * enviadas


def test_a_configuracao_baixada_fica_guardada(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    _rodar(nuvem, tmp_path, "--codigo", "XXXX-YYYY-ZZZZ", "--passagens", "amostra")

    guardada = json.loads((tmp_path / ARQUIVO_DA_CONFIGURACAO).read_text(encoding="utf-8"))
    assert guardada["caixa_id"] == "7"
    assert [f["id"] for f in guardada["faixas"]] == ["11", "12"]


def test_sem_rede_e_sem_configuracao_guardada_explica(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    _rodar(nuvem, tmp_path, "--codigo", "XXXX-YYYY-ZZZZ", "--passagens", "amostra")
    (tmp_path / ARQUIVO_DA_CONFIGURACAO).unlink()
    nuvem.sem_rede = True

    codigo, saida = _rodar(nuvem, tmp_path, "--passagens", "amostra")

    assert codigo == 1
    assert "sem rede" in saida and "sem configuração guardada" in saida


def test_a_mesma_passagem_mandada_de_novo_vai_de_novo(nuvem: NuvemFalsa, tmp_path: Path) -> None:
    # A nuvem é quem ignora a repetida (SDD 5.5): o simulador manda, para o teste da T62.
    arquivo = tmp_path / "uma.json"
    arquivo.write_text(
        json.dumps([{"id": "00000000-0000-4000-8000-000000000002", "placas": []}]),
        encoding="utf-8",
    )

    _rodar(nuvem, tmp_path, "--codigo", "XXXX-YYYY-ZZZZ", "--passagens", str(arquivo))
    _rodar(nuvem, tmp_path, "--passagens", str(arquivo))

    assert [p["id"] for p in nuvem.passagens] == ["00000000-0000-4000-8000-000000000002"] * 2


# --- A imagem do simulador (T62) ------------------------------------------------------------

RAIZ = Path(__file__).resolve().parents[2]


def test_a_imagem_roda_o_simulador_sem_root_e_com_os_dados_num_volume() -> None:
    texto = (RAIZ / "ferramentas" / "Dockerfile").read_text(encoding="utf-8")

    assert 'ENTRYPOINT ["simulador"]' in texto
    assert "USER simulador" in texto
    assert "WORKDIR /simulador" in texto  # os dados ficam em /simulador/dados (ARQUIVO_DA_FILA)
    assert "--package patio-ferramentas" in texto
    ci = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "docker build -f ferramentas/Dockerfile" in ci

"""Simulador de portaria (SDD 6.4): manda passagens à nuvem como uma caixa de borda.

Exemplos (com o ambiente local no ar, ``uv run tarefas up``)::

    uv run simulador --demonstracao --passagens amostra
    uv run simulador --codigo XXXX-XXXX-XXXX --passagens minhas-passagens.json
    uv run simulador --quadros dados/amostras/portaria-1 --faixa entrada-1 --camera frente
    uv run simulador --video dados/amostras/portaria-1.mp4 --faixa entrada-1 --camera frente

- **Ativação:** ``--codigo`` usa um código gerado pela administração; ``--demonstracao`` (só no
  ambiente local) entra como a administração da semente e gera o código sozinho. A chave fica
  em ``dados/simulador/caixa.json`` (fora do Git) e é usada de novo nas próximas vezes.
- **Passagens prontas** (``--passagens``): um arquivo JSON com uma lista de passagens (ou
  ``amostra``, a do simulador). O que faltar (id, caixa, site, faixa, sentido, horários,
  câmeras) é completado pela ativação e pela hora atual; cada placa leva uma foto desenhada.
- **Quadros** (``--quadros``): as imagens de uma pasta passam pelo agente da caixa com o leitor
  v0 (``uv run tarefas modelos`` antes), como se fossem uma câmera.
- **Vídeo** (``--video``): o mesmo, sobre um arquivo de vídeo (ex.: uma gravação da portaria).

As passagens passam pela mesma fila da caixa (``dados/simulador/fila.sqlite``): o que a nuvem
não recebeu fica guardado para a próxima vez.
"""

import argparse
import io
import json
import os
import sys
import threading
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from PIL import Image, ImageDraw, ImageFont

from borda.agente import Agente, CameraDoAgente, ConfiguracaoDoAgente, FaixaDoAgente, rodar
from borda.captura import (
    FonteAmostrada,
    FonteDeArquivo,
    FonteDePasta,
    FonteDeQuadros,
    VideoIlegivelError,
)
from borda.composicao import Posicao
from borda.envio import FilaDeEnvio, Nuvem, Remetente
from borda.leitor.interface import LeitorDePlacas
from borda.rastreio import DetectorDeVeiculos, Rastreador
from contratos.passagem import Passagem

ARQUIVO_DA_CAIXA = Path("dados") / "simulador" / "caixa.json"
ARQUIVO_DA_FILA = Path("dados") / "simulador" / "fila.sqlite"
PASTA_DOS_MODELOS = Path("modelos") / "v0"

EMAIL_DA_ADMINISTRACAO = "admin@patio-br.example"
SENHA_DA_DEMONSTRACAO = "demonstracao-local"
SITE_DA_DEMONSTRACAO = "CD Exemplo"
"""Os mesmos da semente da nuvem (``nuvem/src/nuvem/semente.py``); um teste confere."""

ESPERA_MAXIMA_PADRAO = 60.0
"""Quanto o simulador espera a nuvem, somando as tentativas, antes de desistir por ora."""

ESPACO_ENTRE_PASSAGENS = timedelta(seconds=20)
DURACAO_DA_PASSAGEM = timedelta(seconds=6)
HOSTS_LOCAIS = frozenset({"localhost", "127.0.0.1", "::1"})
PORTA_PADRAO_DA_API = "18000"
"""A mesma do ``.env.exemplo`` e do docker compose."""

CarregarModelos = Callable[[], tuple[DetectorDeVeiculos, LeitorDePlacas]]


class SimuladorError(Exception):
    """Algo que quem roda o simulador precisa resolver (a mensagem diz o quê)."""

    def __init__(self, mensagem: str, codigo: int = 1) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


@dataclass(frozen=True)
class CaixaAtivada:
    """A caixa que o simulador finge ser."""

    nuvem: str
    caixa_id: str
    site_id: str
    chave: str


def principal(
    argv: Sequence[str] | None = None,
    *,
    cliente: httpx.Client | None = None,
    raiz: Path | None = None,
    agora: datetime | None = None,
    saida: TextIO = sys.stdout,
    carregar_modelos: CarregarModelos | None = None,
) -> int:
    """Ponto de entrada do comando ``simulador``.

    Args:
        argv: argumentos da linha de comando (padrão: os do processo).
        cliente: o cliente HTTP (os testes passam uma nuvem falsa).
        raiz: onde ficam ``dados/`` e ``modelos/`` (padrão: a pasta atual).
        agora: a hora da simulação (padrão: a do relógio).
        saida: onde escrever o relatório.
        carregar_modelos: monta o detector e o leitor (padrão: o leitor v0).

    Returns:
        0 se tudo foi enviado; 1 se algo precisa de ação; 2 se o pedido não é aceito.
    """
    raiz = raiz or Path.cwd()
    argumentos = _interpretador(_nuvem_local(raiz)).parse_args(argv)
    agora = agora or datetime.now(UTC)
    cliente = cliente or cliente_para(argumentos.nuvem)
    try:
        caixa = _caixa(argumentos, cliente, raiz)
        configuracao = _configuracao(cliente, caixa)
        faixa = _escolher_faixa(configuracao, argumentos.faixa)
        fila = FilaDeEnvio(raiz / ARQUIVO_DA_FILA)
        try:
            if argumentos.passagens:
                guardadas = _guardar_passagens(
                    argumentos.passagens, configuracao, faixa, fila, agora
                )
            else:
                camera = _escolher_camera(configuracao, faixa, argumentos.camera)
                guardadas = _rodar_fonte(
                    _fonte(argumentos, agora),
                    configuracao,
                    camera,
                    fila,
                    carregar_modelos or _carregar_v0(raiz),
                )
            print(f"{guardadas} passagens guardadas na fila da caixa", file=saida)
            _enviar(fila, caixa, cliente, argumentos.esperar_no_maximo, saida)
            if argumentos.demonstracao:
                print(
                    f"veja em {caixa.nuvem}/portaria (entre com porteiro@empresa-a.example e a "
                    f"senha {SENHA_DA_DEMONSTRACAO})",
                    file=saida,
                )
        finally:
            fila.fechar()
    except SimuladorError as erro:
        print(f"erro: {erro}", file=saida)
        return erro.codigo
    except httpx.HTTPError as erro:
        print(
            f"erro: a nuvem em {argumentos.nuvem} não respondeu como esperado: {erro}", file=saida
        )
        return 1
    return 0


def cliente_para(nuvem: str) -> httpx.Client:
    """O cliente HTTP para falar com a nuvem.

    Com a nuvem local, sem o proxy do sistema: o httpx o usaria também para o ``localhost``
    (no Windows, o proxy do registro), e numa rede de empresa a demonstração falharia.
    """
    return httpx.Client(timeout=30, trust_env=urlsplit(nuvem).hostname not in HOSTS_LOCAIS)


def _nuvem_local(raiz: Path) -> str:
    # A porta da API vem da API_PORTA, do ambiente ou do .env, como no docker compose: quem a
    # trocou no .env (a 18000 estava ocupada) não manda as passagens a outro programa.
    porta = os.environ.get("API_PORTA") or _valor_do_env(raiz / ".env", "API_PORTA")
    return f"http://localhost:{porta or PORTA_PADRAO_DA_API}"


def _valor_do_env(arquivo: Path, nome: str) -> str | None:
    if not arquivo.is_file():
        return None
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        chave, igual, valor = linha.strip().partition("=")
        if igual and chave.strip() == nome:
            return valor.strip().strip("\"'") or None
    return None


def _interpretador(nuvem_local: str) -> argparse.ArgumentParser:
    interpretador = argparse.ArgumentParser(
        prog="simulador", description="Faz o papel de uma caixa de borda (SDD 6.4)."
    )
    interpretador.add_argument(
        "--nuvem",
        default=nuvem_local,
        help=f"endereço da nuvem (padrão: a local, {nuvem_local}; a porta vem da API_PORTA)",
    )
    ativacao = interpretador.add_mutually_exclusive_group()
    ativacao.add_argument("--codigo", help="código de ativação gerado pela administração")
    ativacao.add_argument(
        "--demonstracao",
        action="store_true",
        help="só no ambiente local: gera o código com a administração da semente",
    )
    o_que = interpretador.add_mutually_exclusive_group(required=True)
    o_que.add_argument("--passagens", help="arquivo JSON com passagens, ou `amostra`")
    o_que.add_argument("--quadros", help="pasta com as imagens de uma câmera")
    o_que.add_argument("--video", help="arquivo de vídeo (ex.: uma gravação da portaria)")
    interpretador.add_argument("--faixa", help="id ou nome da faixa (ex.: entrada-1)")
    interpretador.add_argument(
        "--camera", default="frente", help="id ou posição da câmera na faixa (padrão: frente)"
    )
    interpretador.add_argument(
        "--por-segundo", type=float, default=5.0, help="quadros por segundo da pasta (padrão: 5)"
    )
    interpretador.add_argument(
        "--esperar-no-maximo",
        type=float,
        default=ESPERA_MAXIMA_PADRAO,
        help="segundos, somando as tentativas, antes de deixar o resto na fila",
    )
    return interpretador


# --- Ativação ------------------------------------------------------------------------------


def _caixa(argumentos: argparse.Namespace, cliente: httpx.Client, raiz: Path) -> CaixaAtivada:
    nuvem = argumentos.nuvem.rstrip("/")
    if argumentos.demonstracao:
        if urlsplit(nuvem).hostname not in HOSTS_LOCAIS:
            raise SimuladorError(
                "--demonstracao só vale no ambiente local (a senha da semente é pública)",
                codigo=2,
            )
        guardada = _caixa_guardada(raiz, nuvem)
        if guardada is not None and _chave_vale(cliente, guardada):
            # A mesma caixa: o que ficou na fila de uma rodada anterior é dela (noutra caixa, a
            # nuvem o recusaria).
            return guardada
        return _ativar(cliente, nuvem, _codigo_da_demonstracao(cliente, nuvem), raiz)
    if argumentos.codigo:
        return _ativar(cliente, nuvem, argumentos.codigo, raiz)
    guardada = _caixa_guardada(raiz, nuvem)
    if guardada is not None:
        return guardada
    raise SimuladorError(
        f"nenhuma caixa ativada para {nuvem}: use --codigo (gerado pela administração) "
        "ou, no ambiente local, --demonstracao"
    )


def _caixa_guardada(raiz: Path, nuvem: str) -> CaixaAtivada | None:
    arquivo = raiz / ARQUIVO_DA_CAIXA
    if not arquivo.is_file():
        return None
    guardada = CaixaAtivada(**json.loads(arquivo.read_text(encoding="utf-8")))
    return guardada if guardada.nuvem == nuvem else None


def _chave_vale(cliente: httpx.Client, caixa: CaixaAtivada) -> bool:
    resposta = cliente.get(
        f"{caixa.nuvem}/api/borda/configuracao",
        headers={"Authorization": f"Bearer {caixa.chave}"},
    )
    return resposta.status_code == httpx.codes.OK


def _codigo_da_demonstracao(cliente: httpx.Client, nuvem: str) -> str:
    cliente.post(
        f"{nuvem}/entrar",
        data={"email": EMAIL_DA_ADMINISTRACAO, "senha": SENHA_DA_DEMONSTRACAO},
        follow_redirects=False,
    )
    sites = cliente.get(f"{nuvem}/api/admin/sites")
    if sites.status_code != httpx.codes.OK:
        raise SimuladorError("a administração da demonstração não entrou: rode `tarefas semente`")
    site = next((s for s in sites.json() if s["nome"] == SITE_DA_DEMONSTRACAO), None)
    if site is None:
        raise SimuladorError(f"o site {SITE_DA_DEMONSTRACAO!r} não existe: rode `tarefas semente`")
    gerado = cliente.post(f"{nuvem}/api/admin/sites/{site['id']}/codigos-de-ativacao")
    gerado.raise_for_status()
    return str(gerado.json()["codigo"])


def _ativar(cliente: httpx.Client, nuvem: str, codigo: str, raiz: Path) -> CaixaAtivada:
    resposta = cliente.post(f"{nuvem}/api/borda/ativar", json={"codigo": codigo})
    if resposta.status_code == httpx.codes.UNAUTHORIZED:
        raise SimuladorError("código de ativação inválido, já usado ou vencido")
    resposta.raise_for_status()
    dados = resposta.json()
    caixa = CaixaAtivada(nuvem, str(dados["caixa_id"]), str(dados["site_id"]), dados["chave"])
    arquivo = raiz / ARQUIVO_DA_CAIXA
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(caixa.__dict__, indent=2), encoding="utf-8")
    return caixa


def _configuracao(cliente: httpx.Client, caixa: CaixaAtivada) -> ConfiguracaoDoAgente:
    resposta = cliente.get(
        f"{caixa.nuvem}/api/borda/configuracao",
        headers={"Authorization": f"Bearer {caixa.chave}"},
    )
    if resposta.status_code == httpx.codes.UNAUTHORIZED:
        raise SimuladorError("a chave guardada foi revogada: ative de novo com --codigo")
    resposta.raise_for_status()
    return ConfiguracaoDoAgente.de_json(resposta.json())


# --- Faixa e câmera ------------------------------------------------------------------------


def _simplificar(nome: str) -> str:
    # "Saída 1" → "saida-1": como a gente escreve na linha de comando.
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return "-".join(sem_acento.lower().split())


def _escolher_faixa(configuracao: ConfiguracaoDoAgente, pedida: str | None) -> FaixaDoAgente:
    if pedida is None:
        entradas = [f for f in configuracao.faixas if f.sentido == "entrada"]
        if not (entradas or configuracao.faixas):
            raise SimuladorError("o site não tem faixas cadastradas")
        return (entradas or list(configuracao.faixas))[0]
    for faixa in configuracao.faixas:
        if pedida in (faixa.id, _simplificar(faixa.nome)) or _simplificar(pedida) == _simplificar(
            faixa.nome
        ):
            return faixa
    existentes = ", ".join(f"{f.nome} ({f.id})" for f in configuracao.faixas)
    raise SimuladorError(f"a faixa {pedida!r} não existe; as do site: {existentes}")


def _escolher_camera(
    configuracao: ConfiguracaoDoAgente, faixa: FaixaDoAgente, pedida: str
) -> CameraDoAgente:
    da_faixa = [c for c in configuracao.cameras if c.faixa_id == faixa.id]
    for camera in da_faixa:
        if pedida in (camera.id, camera.posicao):
            return camera
    existentes = ", ".join(f"{c.nome} ({c.id}, {c.posicao})" for c in da_faixa)
    raise SimuladorError(f"a câmera {pedida!r} não existe na faixa; as dela: {existentes}")


def _camera_para(configuracao: ConfiguracaoDoAgente, faixa: FaixaDoAgente, papel: str) -> str:
    # Cavalo: a câmera da frente; reboque ou desconhecido: a de trás; senão, qualquer uma.
    preferida = "frente" if papel == "cavalo" else "tras"
    da_faixa = [
        c for c in configuracao.cameras if c.faixa_id == faixa.id and c.posicao != "contexto"
    ]
    if not da_faixa:
        raise SimuladorError(f"a faixa {faixa.nome} não tem câmera de placa")
    return next((c.id for c in da_faixa if c.posicao == preferida), da_faixa[0].id)


# --- Passagens prontas ---------------------------------------------------------------------


def _guardar_passagens(
    origem: str,
    configuracao: ConfiguracaoDoAgente,
    faixa: FaixaDoAgente,
    fila: FilaDeEnvio,
    agora: datetime,
) -> int:
    if origem == "amostra":
        texto = resources.files("simulador").joinpath("amostra.json").read_text(encoding="utf-8")
    else:
        texto = Path(origem).read_text(encoding="utf-8")
    escritas: list[dict[str, Any]] = json.loads(texto)
    for indice, escrita in enumerate(escritas):
        # As passagens ficam no passado, em ordem, a 20 s uma da outra.
        inicio = agora - (len(escritas) - indice) * ESPACO_ENTRE_PASSAGENS
        passagem, fotos = _completar(escrita, configuracao, faixa, inicio)
        fila.guardar(passagem, fotos)
    return len(escritas)


def _completar(
    escrita: dict[str, Any],
    configuracao: ConfiguracaoDoAgente,
    faixa: FaixaDoAgente,
    inicio: datetime,
) -> tuple[Passagem, dict[str, bytes]]:
    dados = dict(escrita)
    passagem_id = str(dados.setdefault("id", str(uuid4())))
    dados.setdefault("versao_contrato", 1)
    dados.setdefault("caixa_id", configuracao.caixa_id)
    dados.setdefault("site_id", configuracao.site_id)
    dados.setdefault("faixa_id", faixa.id)
    dados.setdefault("sentido", faixa.sentido)
    dados.setdefault("inicio", inicio.isoformat())
    if "fim" not in dados:
        dados["fim"] = (datetime.fromisoformat(dados["inicio"]) + DURACAO_DA_PASSAGEM).isoformat()
    dados.setdefault("versao_leitor", "simulador")
    placas = [dict(placa) for placa in dados.get("placas", [])]
    for placa in placas:
        placa.setdefault("camera_id", _camera_para(configuracao, faixa, placa["papel"]))
    dados["placas"] = placas
    fotos: dict[str, bytes] = {}
    if "fotos" not in dados:
        dados["fotos"] = []
        data = datetime.fromisoformat(dados["inicio"])
        for indice, placa in enumerate(placas):
            ref = f"{data:%Y/%m/%d}/{passagem_id}-{indice}.jpg"
            fotos[ref] = _foto_desenhada(placa["placa"])
            dados["fotos"].append({"tipo": "placa", "camera_id": placa["camera_id"], "ref": ref})
    return Passagem.model_validate(dados), fotos


def _foto_desenhada(placa: str) -> bytes:
    """Uma "foto" de placa desenhada (inventada): fundo branco, faixa azul, letras pretas."""
    imagem = Image.new("RGB", (200, 64), (245, 245, 245))
    desenho = ImageDraw.Draw(imagem)
    desenho.rectangle((0, 0, 200, 12), fill=(0, 51, 153))
    desenho.rectangle((0, 0, 199, 63), outline=(20, 20, 20), width=2)
    try:
        fonte: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.truetype(
            "DejaVuSans-Bold.ttf", 34
        )
    except OSError:
        fonte = ImageFont.load_default(size=34)
    desenho.text((14, 16), placa.upper().replace("-", ""), fill=(10, 10, 10), font=fonte)
    saida = io.BytesIO()
    imagem.save(saida, "JPEG", quality=90)
    return saida.getvalue()


# --- Quadros de uma pasta ------------------------------------------------------------------


def _carregar_v0(raiz: Path) -> CarregarModelos:
    def carregar() -> tuple[DetectorDeVeiculos, LeitorDePlacas]:
        from borda.leitor.v0 import carregar_v0  # só aqui: carrega o ONNX Runtime

        try:
            return carregar_v0(raiz / PASTA_DOS_MODELOS)
        except FileNotFoundError as erro:
            raise SimuladorError(str(erro)) from None

    return carregar


def _fonte(argumentos: argparse.Namespace, agora: datetime) -> FonteDeQuadros:
    # A pasta e o vídeo começam agora; a amostragem deixa 5 quadros por segundo (SDD 4.4).
    if argumentos.quadros:
        pasta = Path(argumentos.quadros)
        if not pasta.is_dir():
            raise SimuladorError(f"a pasta {pasta} não existe")
        return FonteAmostrada(FonteDePasta(pasta, inicio=agora, por_segundo=argumentos.por_segundo))
    return FonteAmostrada(FonteDeArquivo(Path(argumentos.video), inicio=agora))


def _rodar_fonte(
    fonte: FonteDeQuadros,
    configuracao: ConfiguracaoDoAgente,
    camera: CameraDoAgente,
    fila: FilaDeEnvio,
    carregar_modelos: CarregarModelos,
) -> int:
    detector, leitor = carregar_modelos()

    def criar(da_configuracao: CameraDoAgente) -> Rastreador:
        posicao: Posicao = "frente" if da_configuracao.posicao == "frente" else "tras"
        return Rastreador(
            detector,
            leitor,
            faixa_id=da_configuracao.faixa_id,
            camera_id=da_configuracao.id,
            posicao=posicao,
        )

    so_esta = ConfiguracaoDoAgente(
        caixa_id=configuracao.caixa_id,
        site_id=configuracao.site_id,
        faixas=configuracao.faixas,
        cameras=(camera,),
    )
    agente = Agente(so_esta, fila, criar_rastreador=criar)
    try:
        return len(rodar(agente, {camera.id: fonte}))
    except VideoIlegivelError as erro:
        raise SimuladorError(str(erro)) from None


# --- Envio ---------------------------------------------------------------------------------


def _enviar(
    fila: FilaDeEnvio, caixa: CaixaAtivada, cliente: httpx.Client, limite: float, saida: TextIO
) -> None:
    parar = threading.Event()
    esperado = 0.0

    def dormir(segundos: float) -> None:
        nonlocal esperado
        if esperado + segundos > limite:
            parar.set()
            return
        esperado += segundos
        parar.wait(segundos)

    antes = fila.pendentes()
    recusadas_antes = len(fila.recusadas())
    Remetente(
        fila, Nuvem(caixa.nuvem, caixa.chave, cliente=cliente), dormir=dormir, parar=parar
    ).enviar_pendentes()
    na_fila = fila.pendentes()
    recusadas = len(fila.recusadas()) - recusadas_antes
    enviadas = antes - na_fila - recusadas
    print(f"{enviadas} enviadas; {recusadas} recusadas pela nuvem; {na_fila} na fila", file=saida)
    if recusadas:
        ultima = fila.recusadas()[-1]
        print(f"  última recusa ({ultima.codigo}): {ultima.motivo}", file=saida)
    if na_fila:
        raise SimuladorError(
            f"a nuvem não recebeu {na_fila} passagens; elas ficam em {ARQUIVO_DA_FILA} "
            "e vão na próxima vez"
        )


if __name__ == "__main__":
    raise SystemExit(principal())

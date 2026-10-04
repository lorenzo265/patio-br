"""Comportamento dos comandos do projeto (`uv run tarefas ...`)."""

import io
from collections.abc import Sequence
from pathlib import Path

import pytest

from tarefas.comandos import (
    Etapa,
    ProgramaNaoEncontradoError,
    RaizNaoEncontradaError,
    encontrar_raiz,
    etapas_do_check,
    etapas_do_down,
    etapas_do_migrar,
    etapas_do_modelos,
    etapas_do_semente,
    etapas_do_test,
    etapas_do_up,
    executar_etapas,
    executar_processo,
    principal,
)


class ExecutorFalso:
    """Registra as etapas pedidas e devolve o código configurado para cada uma."""

    def __init__(self, codigos: dict[str, int] | None = None) -> None:
        self.codigos = codigos or {}
        self.chamadas: list[tuple[str, ...]] = []

    def __call__(self, argumentos: Sequence[str], raiz: Path) -> int:
        self.chamadas.append(tuple(argumentos))
        return self.codigos.get(argumentos[2], 0)


def _modulos(executor: ExecutorFalso) -> list[str]:
    # Cada etapa roda como `python -m <modulo> ...`; o módulo é o terceiro argumento.
    return [chamada[2] for chamada in executor.chamadas]


def test_check_roda_estilo_formato_tipos_e_testes_nessa_ordem() -> None:
    executor = ExecutorFalso()

    executar_etapas(etapas_do_check(), Path("."), executor, io.StringIO())

    assert _modulos(executor) == ["ruff", "ruff", "mypy", "pytest"]


def test_check_devolve_zero_quando_todas_as_etapas_passam() -> None:
    codigo = executar_etapas(etapas_do_check(), Path("."), ExecutorFalso(), io.StringIO())

    assert codigo == 0


def test_check_para_na_primeira_etapa_que_falha() -> None:
    executor = ExecutorFalso({"mypy": 1})

    executar_etapas(etapas_do_check(), Path("."), executor, io.StringIO())

    assert "pytest" not in _modulos(executor)


def test_check_devolve_o_codigo_da_etapa_que_falhou() -> None:
    codigo = executar_etapas(
        etapas_do_check(), Path("."), ExecutorFalso({"mypy": 2}), io.StringIO()
    )

    assert codigo == 2


def test_relatorio_diz_qual_etapa_falhou() -> None:
    saida = io.StringIO()

    executar_etapas(etapas_do_check(), Path("."), ExecutorFalso({"mypy": 1}), saida)

    assert "falhou: mypy" in saida.getvalue()


def test_test_repassa_os_argumentos_extras_ao_pytest() -> None:
    etapas = etapas_do_test(["-k", "placa"])

    assert etapas == [Etapa("pytest", (*etapas[0].argumentos[:3], "-k", "placa"))]


def test_principal_roda_o_comando_pedido_na_raiz_do_repositorio(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.uv.workspace]\n", encoding="utf-8")
    executor = ExecutorFalso()

    codigo = principal(["test"], partida=tmp_path, executor=executor, saida=io.StringIO())

    assert (codigo, _modulos(executor)) == (0, ["pytest"])


def test_principal_repassa_opcoes_do_pytest_que_comecam_com_hifen(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.uv.workspace]\n", encoding="utf-8")
    executor = ExecutorFalso()

    principal(["test", "-q", "-k", "placa"], partida=tmp_path, executor=executor)

    assert executor.chamadas[0][3:] == ("-q", "-k", "placa")


def test_principal_recusa_opcoes_desconhecidas_no_check(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.uv.workspace]\n", encoding="utf-8")

    with pytest.raises(SystemExit) as erro:
        principal(["check", "-k", "placa"], partida=tmp_path, saida=io.StringIO())

    assert erro.value.code == 2


@pytest.mark.integracao
def test_principal_fora_do_repositorio_avisa_e_sai_com_erro(tmp_path: Path) -> None:
    saida = io.StringIO()

    codigo = principal(["check"], partida=tmp_path, executor=ExecutorFalso(), saida=saida)

    assert (codigo, "rode dentro do repositório" in saida.getvalue()) == (1, True)


def test_principal_recusa_comando_desconhecido() -> None:
    with pytest.raises(SystemExit) as erro:
        principal(["voar"], saida=io.StringIO())

    assert erro.value.code == 2


@pytest.mark.integracao
def test_encontra_a_raiz_a_partir_de_uma_subpasta(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.uv.workspace]\n", encoding="utf-8")
    subpasta = tmp_path / "borda" / "src"
    subpasta.mkdir(parents=True)

    assert encontrar_raiz(subpasta) == tmp_path


@pytest.mark.integracao
def test_ignora_pyproject_que_nao_e_do_workspace(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.uv.workspace]\n", encoding="utf-8")
    pacote = tmp_path / "borda"
    pacote.mkdir()
    (pacote / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")

    assert encontrar_raiz(pacote) == tmp_path


@pytest.mark.integracao
def test_falha_com_erro_claro_fora_do_repositorio(tmp_path: Path) -> None:
    with pytest.raises(RaizNaoEncontradaError):
        encontrar_raiz(tmp_path)


def test_up_reconstroi_a_api_sobe_os_servicos_e_espera_ficarem_saudaveis() -> None:
    # --build: a API sobe sempre com o código atual (o cache evita refazer o que não mudou).
    (etapa,) = etapas_do_up()

    assert etapa.argumentos[6:] == ("up", "--build", "-d", "--wait")


def test_up_e_down_usam_o_compose_do_projeto_com_o_env_da_raiz() -> None:
    prefixo = ("docker", "compose", "-f", "infra/docker-compose.yml", "--project-directory", ".")

    assert [e.argumentos[:6] for e in (*etapas_do_up(), *etapas_do_down())] == [prefixo, prefixo]


def test_down_mantem_os_dados_do_banco() -> None:
    (etapa,) = etapas_do_down()

    assert etapa.argumentos[-1] == "down"


def test_migrar_aplica_as_migracoes_da_nuvem_ate_a_ultima() -> None:
    (etapa,) = etapas_do_migrar()

    assert etapa.argumentos[2:] == ("alembic", "-c", "nuvem/alembic.ini", "upgrade", "head")


def test_semente_grava_os_dados_de_demonstracao_da_nuvem() -> None:
    (etapa,) = etapas_do_semente()

    assert etapa.argumentos[2:] == ("nuvem.semente",)


def test_modelos_baixa_os_pesos_do_leitor_v0() -> None:
    (etapa,) = etapas_do_modelos()

    assert etapa.argumentos[2:] == ("ml.baixar_modelos",)


def test_principal_conhece_o_comando_modelos(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.uv.workspace]\n", encoding="utf-8")
    executor = ExecutorFalso()

    principal(["modelos"], partida=tmp_path, executor=executor, saida=io.StringIO())

    assert _modulos(executor) == ["ml.baixar_modelos"]


def test_principal_conhece_o_comando_migrar(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.uv.workspace]\n", encoding="utf-8")
    executor = ExecutorFalso()

    principal(["migrar"], partida=tmp_path, executor=executor, saida=io.StringIO())

    assert _modulos(executor) == ["alembic"]


class ExecutorSemPrograma:
    """Simula um programa que não está instalado (ex.: Docker Desktop ausente)."""

    def __call__(self, argumentos: Sequence[str], raiz: Path) -> int:
        raise ProgramaNaoEncontradoError(argumentos[0])


def test_principal_avisa_quando_falta_um_programa(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.uv.workspace]\n", encoding="utf-8")
    saida = io.StringIO()

    codigo = principal(["up"], partida=tmp_path, executor=ExecutorSemPrograma(), saida=saida)

    assert (codigo, "'docker' não foi encontrado" in saida.getvalue()) == (127, True)


@pytest.mark.integracao
def test_executar_processo_sem_o_programa_levanta_erro_claro(tmp_path: Path) -> None:
    with pytest.raises(ProgramaNaoEncontradoError):
        executar_processo(["programa-que-nao-existe-patio"], tmp_path)

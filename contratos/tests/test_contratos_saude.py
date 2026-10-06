"""A Saude v1: o que a caixa conta de si a cada minuto (SDD 3.2 e 7.4, D-65)."""

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from contratos.saude import Saude

EXEMPLO: dict[str, Any] = {
    "versao_contrato": 1,
    "caixa_id": "7",
    "site_id": "3",
    "momento": "2026-11-03T14:02:11.120-03:00",
    "versao_programa": "0.1.0",
    "versao_leitor": "v0",
    "cpu": 37.5,
    "temperatura": 61.0,
    "memoria": 48.2,
    "disco": 12.0,
    "cameras": [
        {
            "camera_id": "21",
            "no_ar": True,
            "quadros_por_segundo": 4.9,
            "ultimo_quadro": "2026-11-03T14:02:10.950-03:00",
        },
        {"camera_id": "22", "no_ar": False, "quadros_por_segundo": 0, "ultimo_quadro": None},
    ],
    "fila": {"passagens": 2, "fotos": 3, "recusadas": 0},
}


def _exemplo(**mudancas: Any) -> dict[str, Any]:
    dados = copy.deepcopy(EXEMPLO)
    dados.update(mudancas)
    return dados


def _onde_falha(dados: dict[str, Any]) -> list[tuple[int | str, ...]]:
    with pytest.raises(ValidationError) as erro:
        Saude.model_validate(dados)
    return [detalhe["loc"] for detalhe in erro.value.errors()]


def test_o_exemplo_vale_e_volta_igual_pelo_json() -> None:
    saude = Saude.model_validate(EXEMPLO)

    assert saude.cameras[0].no_ar
    assert saude.fila.passagens == 2
    assert Saude.model_validate_json(saude.model_dump_json()) == saude


def test_sem_sensor_a_temperatura_vai_vazia() -> None:
    assert Saude.model_validate(_exemplo(temperatura=None)).temperatura is None


def test_sem_camera_aberta_a_lista_vai_vazia() -> None:
    assert Saude.model_validate(_exemplo(cameras=[])).cameras == ()


def test_outra_versao_do_contrato_e_recusada() -> None:
    assert _onde_falha(_exemplo(versao_contrato=2)) == [("versao_contrato",)]


def test_campo_desconhecido_e_recusado() -> None:
    assert _onde_falha(_exemplo(bateria=90)) == [("bateria",)]


def test_a_hora_sem_fuso_e_recusada() -> None:
    assert _onde_falha(_exemplo(momento="2026-11-03T14:02:11")) == [("momento",)]


@pytest.mark.parametrize("campo", ["cpu", "memoria", "disco"])
@pytest.mark.parametrize("valor", [-0.1, 100.1, float("nan")])
def test_os_usos_ficam_entre_0_e_100(campo: str, valor: float) -> None:
    assert _onde_falha(_exemplo(**{campo: valor})) == [(campo,)]


@pytest.mark.parametrize("campo", ["cpu", "memoria", "disco"])
@pytest.mark.parametrize("valor", [0, 100])
def test_os_usos_aceitam_os_extremos(campo: str, valor: float) -> None:
    assert getattr(Saude.model_validate(_exemplo(**{campo: valor})), campo) == valor


@pytest.mark.parametrize("valor", [-60.1, 150.1, float("inf")])
def test_temperatura_fora_do_possivel_e_recusada(valor: float) -> None:
    assert _onde_falha(_exemplo(temperatura=valor)) == [("temperatura",)]


@pytest.mark.parametrize("valor", [-60, 150])
def test_temperatura_aceita_os_extremos(valor: float) -> None:
    assert Saude.model_validate(_exemplo(temperatura=valor)).temperatura == valor


@pytest.mark.parametrize(
    ("mudanca", "onde"),
    [
        ({"quadros_por_segundo": -1}, ("cameras", 0, "quadros_por_segundo")),
        ({"quadros_por_segundo": float("inf")}, ("cameras", 0, "quadros_por_segundo")),
        ({"camera_id": ""}, ("cameras", 0, "camera_id")),
        ({"ultimo_quadro": "2026-11-03T14:02:10"}, ("cameras", 0, "ultimo_quadro")),
        ({"no_ar": "talvez"}, ("cameras", 0, "no_ar")),
        ({"luz": 1}, ("cameras", 0, "luz")),
    ],
)
def test_camera_fora_do_formato_e_recusada(mudanca: dict[str, Any], onde: tuple[Any, ...]) -> None:
    dados = _exemplo()
    dados["cameras"][0].update(mudanca)

    assert _onde_falha(dados) == [onde]


@pytest.mark.parametrize("campo", ["passagens", "fotos", "recusadas"])
def test_a_fila_nao_tem_numero_negativo(campo: str) -> None:
    dados = _exemplo()
    dados["fila"][campo] = -1

    assert _onde_falha(dados) == [("fila", campo)]


@pytest.mark.parametrize("campo", ["caixa_id", "site_id", "versao_programa", "versao_leitor"])
def test_os_textos_nao_ficam_vazios_nem_enormes(campo: str) -> None:
    assert _onde_falha(_exemplo(**{campo: ""})) == [(campo,)]
    assert _onde_falha(_exemplo(**{campo: "x" * 101})) == [(campo,)]
    assert getattr(Saude.model_validate(_exemplo(**{campo: "x" * 100})), campo) == "x" * 100


def test_a_lista_de_cameras_tem_limite() -> None:
    camera = EXEMPLO["cameras"][1]
    cameras = [camera | {"camera_id": str(numero)} for numero in range(65)]

    assert _onde_falha(_exemplo(cameras=cameras)) == [("cameras",)]
    assert len(Saude.model_validate(_exemplo(cameras=cameras[:64])).cameras) == 64


def test_a_saude_nao_se_altera_depois_de_criada() -> None:
    saude = Saude.model_validate(EXEMPLO)

    with pytest.raises(ValidationError):
        saude.cpu = 1.0  # type: ignore[misc]

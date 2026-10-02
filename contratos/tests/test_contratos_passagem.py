"""A Passagem v1: o único formato que a borda envia à nuvem (SDD 3.2)."""

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from contratos.passagem import Passagem

# O exemplo do SDD 3.2, com dados inventados.
EXEMPLO_DO_SDD: dict[str, Any] = {
    "versao_contrato": 1,
    "id": "6f1c2c9e-8a0b-4c55-9b1e-2f0a3d4e5b6c",
    "caixa_id": "cx-0001",
    "site_id": "site-0001",
    "faixa_id": "entrada-1",
    "sentido": "entrada",
    "inicio": "2026-11-03T14:02:11.120-03:00",
    "fim": "2026-11-03T14:02:19.480-03:00",
    "placas": [
        {
            "placa": "ABC1D23",
            "papel": "cavalo",
            "confianca": 0.98,
            "camera_id": "cam-frente-1",
            "quadros": 7,
            "inferida": False,
        },
        {
            "placa": "XYZ9876",
            "papel": "reboque",
            "confianca": 0.91,
            "camera_id": "cam-tras-1",
            "quadros": 5,
            "inferida": False,
        },
    ],
    "fotos": [
        {"tipo": "placa", "camera_id": "cam-frente-1", "ref": "fotos/2026/11/03/6f1c-1.jpg"},
        {"tipo": "contexto", "camera_id": "cam-tras-1", "ref": "fotos/2026/11/03/6f1c-2.jpg"},
    ],
    "versao_leitor": "1.0.0",
}


def _exemplo() -> dict[str, Any]:
    return copy.deepcopy(EXEMPLO_DO_SDD)


def _com_placa(**mudancas: Any) -> dict[str, Any]:
    dados = _exemplo()
    dados["placas"][0].update(mudancas)
    return dados


def _onde_falha(dados: dict[str, Any]) -> list[tuple[int | str, ...]]:
    """Valida ``dados`` e devolve onde cada erro está (ex.: ``("placas", 0, "papel")``)."""
    with pytest.raises(ValidationError) as erro:
        Passagem.model_validate(dados)
    return [detalhe["loc"] for detalhe in erro.value.errors()]


def test_o_exemplo_do_sdd_e_uma_passagem_valida() -> None:
    passagem = Passagem.model_validate(_exemplo())

    assert passagem.placas[0].placa == "ABC1D23"


def test_passagem_vai_e_volta_em_json_sem_perder_nada() -> None:
    passagem = Passagem.model_validate(_exemplo())

    assert Passagem.model_validate_json(passagem.model_dump_json()) == passagem


def test_horarios_mantem_o_fuso_da_caixa() -> None:
    passagem = Passagem.model_validate(_exemplo())

    assert passagem.inicio.isoformat() == "2026-11-03T14:02:11.120000-03:00"


@pytest.mark.parametrize("campo", sorted(EXEMPLO_DO_SDD))
def test_todo_campo_e_obrigatorio(campo: str) -> None:
    dados = _exemplo()
    del dados[campo]

    assert _onde_falha(dados) == [(campo,)]


@pytest.mark.parametrize("campo", sorted(EXEMPLO_DO_SDD["placas"][0]))
def test_todo_campo_da_placa_lida_e_obrigatorio(campo: str) -> None:
    dados = _exemplo()
    del dados["placas"][0][campo]

    assert _onde_falha(dados) == [("placas", 0, campo)]


@pytest.mark.parametrize("campo", sorted(EXEMPLO_DO_SDD["fotos"][0]))
def test_todo_campo_da_foto_e_obrigatorio(campo: str) -> None:
    dados = _exemplo()
    del dados["fotos"][0][campo]

    assert _onde_falha(dados) == [("fotos", 0, campo)]


def test_recusa_campo_desconhecido() -> None:
    # Campo novo é mudança de formato: muda a versão do contrato, não entra calado.
    dados = _exemplo() | {"motorista": "Fulano"}

    assert _onde_falha(dados) == [("motorista",)]


def test_recusa_outra_versao_do_contrato() -> None:
    dados = _exemplo() | {"versao_contrato": 2}

    assert _onde_falha(dados) == [("versao_contrato",)]


def test_sentido_e_entrada_ou_saida() -> None:
    dados = _exemplo() | {"sentido": "saida"}

    assert Passagem.model_validate(dados).sentido == "saida"


def test_recusa_outro_sentido() -> None:
    dados = _exemplo() | {"sentido": "subida"}

    assert _onde_falha(dados) == [("sentido",)]


def test_recusa_fim_antes_do_inicio() -> None:
    dados = _exemplo() | {"fim": "2026-11-03T14:02:11.119-03:00"}

    assert _onde_falha(dados) == [("fim",)]


def test_aceita_fim_igual_ao_inicio() -> None:
    dados = _exemplo() | {"fim": EXEMPLO_DO_SDD["inicio"]}
    passagem = Passagem.model_validate(dados)

    assert passagem.fim == passagem.inicio


def test_compara_inicio_e_fim_pelo_instante_e_nao_pelo_relogio() -> None:
    # O início é 14:02:11.120 em -03:00, ou seja, 17:02:11.120 em UTC. Um fim às 17:02:11 UTC
    # parece depois pelo relógio, mas é 0,12 s antes do início.
    dados = _exemplo() | {"fim": "2026-11-03T17:02:11Z"}

    assert _onde_falha(dados) == [("fim",)]


@pytest.mark.parametrize("campo", ["inicio", "fim"])
def test_recusa_horario_sem_fuso(campo: str) -> None:
    dados = _exemplo() | {campo: "2026-11-03T14:02:15"}

    assert _onde_falha(dados) == [(campo,)]


@pytest.mark.parametrize("campo", ["caixa_id", "site_id", "faixa_id", "versao_leitor"])
def test_recusa_identificador_vazio(campo: str) -> None:
    dados = _exemplo() | {campo: ""}

    assert _onde_falha(dados) == [(campo,)]


def test_recusa_id_que_nao_e_uuid() -> None:
    dados = _exemplo() | {"id": "passagem-1"}

    assert _onde_falha(dados) == [("id",)]


def test_aceita_passagem_sem_placa_lida() -> None:
    # Veículo passou e nenhuma placa foi lida: a passagem vai com as fotos e vira exceção
    # na nuvem, para o porteiro resolver (SDD 4.7).
    dados = _exemplo() | {"placas": []}

    assert Passagem.model_validate(dados).placas == ()


def test_passagem_nao_se_altera_depois_de_criada() -> None:
    # Horários e leituras são a prova da chegada (SDD 5.5).
    passagem = Passagem.model_validate(_exemplo())

    with pytest.raises(ValidationError):
        passagem.fim = passagem.inicio  # type: ignore[misc]


def test_placas_e_fotos_da_passagem_nao_mudam_depois_de_criada() -> None:
    passagem = Passagem.model_validate(_exemplo())

    assert (type(passagem.placas), type(passagem.fotos)) == (tuple, tuple)


def test_placa_lida_guarda_a_placa_em_maiusculas_sem_hifen() -> None:
    passagem = Passagem.model_validate(_com_placa(placa="abc-1d23"))

    assert passagem.placas[0].placa == "ABC1D23"


def test_recusa_placa_lida_fora_do_formato() -> None:
    assert _onde_falha(_com_placa(placa="AB12345")) == [("placas", 0, "placa")]


@pytest.mark.parametrize("papel", ["cavalo", "reboque", "desconhecido"])
def test_papel_da_placa_e_cavalo_reboque_ou_desconhecido(papel: str) -> None:
    assert Passagem.model_validate(_com_placa(papel=papel)).placas[0].papel == papel


def test_recusa_outro_papel() -> None:
    assert _onde_falha(_com_placa(papel="carreta")) == [("placas", 0, "papel")]


@pytest.mark.parametrize("confianca", [0.0, 1.0])
def test_aceita_confianca_nos_limites(confianca: float) -> None:
    assert Passagem.model_validate(_com_placa(confianca=confianca)).placas[0].confianca == confianca


@pytest.mark.parametrize("confianca", [-0.01, 1.01, float("nan")])
def test_recusa_confianca_fora_de_0_a_1(confianca: float) -> None:
    assert _onde_falha(_com_placa(confianca=confianca)) == [("placas", 0, "confianca")]


def test_aceita_uma_placa_vista_em_um_so_quadro() -> None:
    assert Passagem.model_validate(_com_placa(quadros=1)).placas[0].quadros == 1


def test_recusa_placa_vista_em_zero_quadros() -> None:
    assert _onde_falha(_com_placa(quadros=0)) == [("placas", 0, "quadros")]


def test_recusa_placa_lida_sem_camera() -> None:
    assert _onde_falha(_com_placa(camera_id="")) == [("placas", 0, "camera_id")]


def test_recusa_foto_de_outro_tipo() -> None:
    dados = _exemplo()
    dados["fotos"][0]["tipo"] = "rosto"

    assert _onde_falha(dados) == [("fotos", 0, "tipo")]

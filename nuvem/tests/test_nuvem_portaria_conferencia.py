"""Conferência da placa pelo porteiro (SDD D-42): a placa certa de cada recorte, com prova."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from contratos.placa import PlacaInvalidaError
from nuvem import tarefas_de_fundo as fila
from nuvem.banco import SQLSTATE_CHAVE_ESTRANGEIRA, SQLSTATE_SO_ACRESCENTA, sqlstate
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, acesso_do_usuario
from nuvem.erros import NaoEncontradoError
from nuvem.portaria import conferencia
from nuvem.portaria.modelos import ConferenciaPlaca, Visita
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Registrar = Callable[..., Passagem]

AGORA = datetime(2026, 10, 5, 17, 5, tzinfo=UTC)


@pytest.fixture
def porteiro(sessao: Session, cenario: Demonstracao) -> Acesso:
    """O porteiro do site_a."""
    return acesso_do_usuario(sessao, cenario.porteiro_a.id)


@pytest.fixture
def camera_de_tras(sessao: Session, cenario: Demonstracao) -> str:
    """A câmera traseira da faixa de entrada do site_a (a da frente é a ``camera_a``)."""
    estrutura = cadastro.estrutura_do_site(
        sessao, empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id
    )
    cameras = estrutura[cenario.faixa_a.id].cameras - {cenario.camera_a.id}
    return str(min(cameras))


def _cavalo_e_reboque(cenario: Demonstracao, tras: str) -> dict[str, object]:
    """Uma passagem com o cavalo pela frente e o reboque por trás, cada um com o recorte."""
    frente = str(cenario.camera_a.id)
    return {
        "placas": [
            {"placa": "ABC1D23", "papel": "cavalo", "confianca": 0.97, "camera_id": frente,
             "quadros": 6},
            {"placa": "XYZ9876", "papel": "desconhecido", "confianca": 0.81, "camera_id": tras,
             "quadros": 4},
        ],
        "fotos": [
            {"tipo": "placa", "camera_id": frente, "ref": "p/1.jpg"},
            {"tipo": "contexto", "camera_id": frente, "ref": "p/2.jpg"},
            {"tipo": "placa", "camera_id": tras, "ref": "p/3.jpg"},
        ],
    }  # fmt: skip


# --- Conferir ---------------------------------------------------------------------------------


def test_confirmar_grava_a_placa_lida_quem_e_quando(
    sessao: Session, porteiro: Acesso, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    feita = conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D23", agora=AGORA)

    assert (feita.passagem_id, feita.foto, feita.placa_lida, feita.placa) == (
        passagem.id, 0, "ABC1D23", "ABC1D23",
    )  # fmt: skip
    assert (feita.usuario_id, feita.empresa_id, feita.momento) == (
        porteiro.usuario_id, porteiro.empresa_id, AGORA,
    )  # fmt: skip
    assert not feita.corrigida


def test_corrigir_grava_a_placa_certa_e_guarda_a_lida(
    sessao: Session, porteiro: Acesso, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    feita = conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D28", agora=AGORA)

    assert (feita.placa_lida, feita.placa, feita.corrigida) == ("ABC1D23", "ABC1D28", True)


def test_placa_digitada_vai_para_o_formato_canonico(
    sessao: Session, porteiro: Acesso, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    feita = conferencia.conferir(sessao, porteiro, passagem.id, 0, " abc-1d28 ", agora=AGORA)

    assert feita.placa == "ABC1D28"


def test_placa_fora_do_formato_e_recusada(
    sessao: Session, porteiro: Acesso, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    with pytest.raises(PlacaInvalidaError):
        conferencia.conferir(sessao, porteiro, passagem.id, 0, "AB12345", agora=AGORA)

    assert sessao.scalars(select(ConferenciaPlaca)).all() == []


def test_a_leitura_comparada_e_a_da_mesma_camera_do_recorte(
    sessao: Session,
    porteiro: Acesso,
    cenario: Demonstracao,
    camera_de_tras: str,
    registrar_passagem: Registrar,
) -> None:
    passagem = registrar_passagem(**_cavalo_e_reboque(cenario, camera_de_tras))

    feita = conferencia.conferir(sessao, porteiro, passagem.id, 2, "XYZ9876", agora=AGORA)

    assert (feita.placa_lida, feita.corrigida) == ("XYZ9876", False)


def test_duas_leituras_na_mesma_camera_compara_com_a_mais_confiavel(
    sessao: Session, porteiro: Acesso, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    frente = str(cenario.camera_a.id)
    passagem = registrar_passagem(
        placas=[
            {"placa": "ABC1D28", "papel": "cavalo", "confianca": 0.62, "camera_id": frente,
             "quadros": 2},
            {"placa": "ABC1D23", "papel": "cavalo", "confianca": 0.93, "camera_id": frente,
             "quadros": 5},
            {"placa": "ABC1D29", "papel": "cavalo", "confianca": 0.41, "camera_id": frente,
             "quadros": 1},
        ]
    )  # fmt: skip

    feita = conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D23", agora=AGORA)

    assert feita.placa_lida == "ABC1D23"


def test_recorte_sem_leitura_na_camera_e_uma_correcao(
    sessao: Session, porteiro: Acesso, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem(placas=[])

    feita = conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D23", agora=AGORA)

    assert (feita.placa_lida, feita.corrigida) == (None, True)


def test_foto_de_contexto_nao_se_confere(
    sessao: Session,
    porteiro: Acesso,
    cenario: Demonstracao,
    camera_de_tras: str,
    registrar_passagem: Registrar,
) -> None:
    passagem = registrar_passagem(**_cavalo_e_reboque(cenario, camera_de_tras))

    with pytest.raises(NaoEncontradoError):
        conferencia.conferir(sessao, porteiro, passagem.id, 1, "ABC1D23", agora=AGORA)


@pytest.mark.parametrize("foto", [-1, 1, 7])
def test_foto_que_nao_existe_nao_e_encontrada(
    sessao: Session, porteiro: Acesso, registrar_passagem: Registrar, foto: int
) -> None:
    passagem = registrar_passagem()

    with pytest.raises(NaoEncontradoError):
        conferencia.conferir(sessao, porteiro, passagem.id, foto, "ABC1D23", agora=AGORA)


def test_passagem_de_outra_empresa_nao_e_encontrada(
    sessao: Session, acesso_b: Acesso, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()

    with pytest.raises(NaoEncontradoError):
        conferencia.conferir(sessao, acesso_b, passagem.id, 0, "ABC1D23", agora=AGORA)
    with pytest.raises(NaoEncontradoError):
        conferencia.recortes(sessao, acesso_b, passagem.id)


def test_conferir_nao_muda_a_visita(
    sessao: Session, porteiro: Acesso, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    fila.executar_pendentes(sessao, agora=AGORA)  # sem agendamento: vira exceção
    visita = sessao.scalars(select(Visita)).one()
    antes = (visita.estado, visita.composicao, visita.agendamento_id)

    conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D28", agora=AGORA)
    sessao.expire_all()

    assert (visita.estado, visita.composicao, visita.agendamento_id) == antes


# --- Ler --------------------------------------------------------------------------------------


def test_recortes_traz_cada_recorte_de_placa_com_a_leitura(
    sessao: Session,
    porteiro: Acesso,
    cenario: Demonstracao,
    camera_de_tras: str,
    registrar_passagem: Registrar,
) -> None:
    passagem = registrar_passagem(**_cavalo_e_reboque(cenario, camera_de_tras))

    lista = conferencia.recortes(sessao, porteiro, passagem.id)

    assert [(r.foto, r.placa_lida, r.ultima) for r in lista] == [
        (0, "ABC1D23", None), (2, "XYZ9876", None),
    ]  # fmt: skip


def test_conferir_de_novo_vale_a_ultima(
    sessao: Session, porteiro: Acesso, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D28", agora=AGORA)
    depois = AGORA + timedelta(minutes=1)
    conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D23", agora=depois)

    (recorte,) = conferencia.recortes(sessao, porteiro, passagem.id)

    assert recorte.ultima is not None
    assert (recorte.ultima.placa, recorte.ultima.momento) == ("ABC1D23", depois)
    assert len(sessao.scalars(select(ConferenciaPlaca)).all()) == 2


def test_ultimas_por_passagem_para_a_lista(
    sessao: Session,
    porteiro: Acesso,
    cenario: Demonstracao,
    camera_de_tras: str,
    registrar_passagem: Registrar,
) -> None:
    com_duas = registrar_passagem(**_cavalo_e_reboque(cenario, camera_de_tras))
    sem_nenhuma = registrar_passagem()
    conferencia.conferir(sessao, porteiro, com_duas.id, 2, "XYZ9870", agora=AGORA)
    conferencia.conferir(sessao, porteiro, com_duas.id, 0, "ABC1D23", agora=AGORA)
    conferencia.conferir(sessao, porteiro, com_duas.id, 2, "XYZ9876", agora=AGORA)

    ultimas = conferencia.ultimas_por_passagem(sessao, porteiro, [com_duas.id, sem_nenhuma.id])

    assert [(c.foto, c.placa) for c in ultimas[com_duas.id]] == [(0, "ABC1D23"), (2, "XYZ9876")]
    assert sem_nenhuma.id not in ultimas


def test_ultimas_por_passagem_nao_ve_outra_empresa(
    sessao: Session, porteiro: Acesso, acesso_b: Acesso, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D23", agora=AGORA)

    assert conferencia.ultimas_por_passagem(sessao, acesso_b, [passagem.id]) == {}


# --- O banco também confere -------------------------------------------------------------------


def test_banco_recusa_alterar_uma_conferencia(
    sessao: Session, porteiro: Acesso, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D23", agora=AGORA)

    with pytest.raises(DBAPIError) as erro:
        sessao.execute(update(ConferenciaPlaca).values(placa="ABC1D28"))

    assert sqlstate(erro.value) == SQLSTATE_SO_ACRESCENTA


def test_banco_recusa_apagar_uma_conferencia(
    sessao: Session, porteiro: Acesso, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D23", agora=AGORA)

    with pytest.raises(DBAPIError) as erro:
        sessao.execute(delete(ConferenciaPlaca))

    assert sqlstate(erro.value) == SQLSTATE_SO_ACRESCENTA


def test_banco_recusa_esvaziar_a_tabela_de_conferencias(sessao: Session) -> None:
    with pytest.raises(DBAPIError) as erro:
        sessao.execute(text("truncate conferencia_placa"))

    assert sqlstate(erro.value) == SQLSTATE_SO_ACRESCENTA


def test_banco_recusa_conferencia_de_passagem_de_outra_empresa(
    sessao: Session, cenario: Demonstracao, registrar_passagem: Registrar
) -> None:
    passagem = registrar_passagem()
    sessao.add(
        ConferenciaPlaca(
            empresa_id=cenario.empresa_b.id, passagem_id=passagem.id, foto=0, placa_lida=None,
            placa="ABC1D23", usuario_id=cenario.porteiro_b.id, momento=AGORA,
        )
    )  # fmt: skip

    with pytest.raises(DBAPIError) as erro:
        sessao.flush()

    assert sqlstate(erro.value) == SQLSTATE_CHAVE_ESTRANGEIRA

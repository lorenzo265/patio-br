"""Câmeras: a senha fica cifrada no banco; o endereço não leva usuário nem senha."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nuvem.banco import SQLSTATE_CHECK, sqlstate
from nuvem.cadastro import servico
from nuvem.cifra import Cifra
from nuvem.erros import DadoInvalidoError
from nuvem.semente import SENHA_DAS_CAMERAS, Demonstracao

pytestmark = pytest.mark.integracao


def test_senha_da_camera_nao_fica_em_texto_no_banco(sessao: Session, cenario: Demonstracao) -> None:
    gravada = sessao.execute(
        text("select senha_cifrada from camera where id = :id"), {"id": cenario.camera_a.id}
    ).scalar_one()

    assert SENHA_DAS_CAMERAS not in gravada


def test_senha_da_camera_volta_com_a_chave_certa(
    sessao: Session, cenario: Demonstracao, cifra: Cifra
) -> None:
    assert cifra.decifrar(cenario.camera_a.senha_cifrada) == SENHA_DAS_CAMERAS


def test_senha_nao_aparece_ao_imprimir_a_camera(cenario: Demonstracao) -> None:
    assert cenario.camera_a.senha_cifrada not in repr(cenario.camera_a)


def test_recusa_endereco_com_usuario_e_senha_embutidos(
    sessao: Session, cenario: Demonstracao, cifra: Cifra
) -> None:
    # Usuário e senha vão nos campos próprios (a senha, cifrada), nunca dentro do endereço.
    with pytest.raises(DadoInvalidoError, match="endereço"):
        servico.criar_camera(
            sessao,
            cifra,
            cenario.faixa_a,
            nome="Traseira",
            posicao="tras",
            endereco="rtsp://admin:segredo@10.0.0.11:554/stream1",
            login="admin",
            senha="segredo",
        )


def test_banco_recusa_posicao_de_camera_desconhecida(
    sessao: Session, cenario: Demonstracao, cifra: Cifra
) -> None:
    with pytest.raises(DBAPIError) as erro:
        servico.criar_camera(
            sessao,
            cifra,
            cenario.faixa_a,
            nome="Teto",
            posicao="teto",  # type: ignore[arg-type]
            endereco="rtsp://10.0.0.12:554/stream1",
            login="leitura",
            senha="x",
        )

    assert sqlstate(erro.value) == SQLSTATE_CHECK


def test_banco_recusa_faixa_com_sentido_desconhecido(
    sessao: Session, cenario: Demonstracao
) -> None:
    with pytest.raises(DBAPIError) as erro:
        servico.criar_faixa(
            sessao,
            cenario.portaria_a,
            nome="Subida",
            sentido="subida",  # type: ignore[arg-type]
        )

    assert sqlstate(erro.value) == SQLSTATE_CHECK

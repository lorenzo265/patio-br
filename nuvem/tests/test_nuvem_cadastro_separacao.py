"""Separação por empresa (SDD 5.5): um cliente nunca vê dado de outro."""

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nuvem.banco import SQLSTATE_CHAVE_ESTRANGEIRA, sqlstate
from nuvem.cadastro import servico
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.modelos import Portaria, UsuarioSite
from nuvem.erros import NaoEncontradoError
from nuvem.semente import Demonstracao
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao


def test_usuario_da_empresa_a_nao_le_site_da_empresa_b(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    with pytest.raises(NaoEncontradoError):
        servico.obter_site(sessao, acesso_a, cenario.site_b.id)


def test_usuario_le_o_site_ligado_a_ele(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    assert servico.obter_site(sessao, acesso_a, cenario.site_a.id) == cenario.site_a


def test_lista_de_sites_traz_so_os_do_usuario(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    assert servico.listar_sites(sessao, acesso_a) == [cenario.site_a]


def test_site_da_mesma_empresa_sem_ligacao_com_o_usuario_nao_aparece(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    # O gestor A é ligado só ao site_a; o site_a2 é da mesma empresa, mas não é dele.
    with pytest.raises(NaoEncontradoError):
        servico.obter_site(sessao, acesso_a, cenario.site_a2.id)


def test_cameras_de_site_de_outra_empresa_nao_sao_encontradas(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    with pytest.raises(NaoEncontradoError):
        servico.listar_cameras(sessao, acesso_a, cenario.site_b.id)


def test_lista_as_cameras_do_proprio_site(
    sessao: Session, cenario: Demonstracao, acesso_b: Acesso
) -> None:
    assert servico.listar_cameras(sessao, acesso_b, cenario.site_b.id) == [cenario.camera_b]


def test_banco_recusa_portaria_de_uma_empresa_em_site_de_outra(
    sessao: Session, cenario: Demonstracao
) -> None:
    # Mesmo que o código erre, o banco não aceita misturar empresas (chave estrangeira composta).
    sessao.add(Portaria(empresa_id=cenario.empresa_b.id, site_id=cenario.site_a.id, nome="Errada"))

    with pytest.raises(DBAPIError) as erro:
        sessao.flush()

    assert sqlstate(erro.value) == SQLSTATE_CHAVE_ESTRANGEIRA


def test_banco_recusa_ligar_usuario_a_site_de_outra_empresa(
    sessao: Session, cenario: Demonstracao
) -> None:
    sessao.add(
        UsuarioSite(
            usuario_id=cenario.gestor_a.id,
            empresa_id=cenario.empresa_a.id,
            site_id=cenario.site_b.id,
        )
    )

    with pytest.raises(DBAPIError) as erro:
        sessao.flush()

    assert sqlstate(erro.value) == SQLSTATE_CHAVE_ESTRANGEIRA


def test_criar_usuario_recusa_site_de_outra_empresa(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    with pytest.raises(DBAPIError) as erro:
        servico.criar_usuario(
            sessao,
            senhas,
            cenario.empresa_a,
            nome="Porteiro",
            email="porteiro@a.example",
            papel="porteiro",
            sites=[cenario.site_b],
        )

    assert sqlstate(erro.value) == SQLSTATE_CHAVE_ESTRANGEIRA

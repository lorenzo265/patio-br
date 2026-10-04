"""Recebimento de passagens (SDD 3.2 e 5.5): reenvio seguro, só do site da caixa, como veio."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem.banco import SQLSTATE_CHAVE_ESTRANGEIRA, sqlstate
from nuvem.cadastro import servico as cadastro
from nuvem.frota import servico as frota
from nuvem.frota.servico import AcessoDaCaixa, CaixaAtivada
from nuvem.portaria import servico
from nuvem.portaria.modelos import PassagemRecebida
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)


@pytest.fixture
def caixa(sessao: Session, caixa_a: CaixaAtivada) -> AcessoDaCaixa:
    identificada = frota.caixa_da_chave(sessao, caixa_a.chave)
    assert identificada is not None
    return identificada


def _quantas(sessao: Session) -> int:
    return sessao.scalar(select(func.count()).select_from(PassagemRecebida)) or 0


def test_passagem_nova_e_guardada(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    passagem = fazer_passagem()

    assert servico.receber_passagem(sessao, caixa, passagem, agora=AGORA) is True
    assert _quantas(sessao) == 1


def test_mesma_passagem_de_novo_nao_cria_outra(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    # Reenvio seguro (SDD 5.5): a caixa reenvia quando não sabe se a nuvem recebeu.
    passagem = fazer_passagem()
    servico.receber_passagem(sessao, caixa, passagem, agora=AGORA)

    assert servico.receber_passagem(sessao, caixa, passagem, agora=AGORA) is False
    assert _quantas(sessao) == 1


def test_passagem_guardada_como_veio(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    # A passagem é prova: placas, fotos e horários ficam exatamente como a caixa mandou.
    passagem = fazer_passagem()
    servico.receber_passagem(sessao, caixa, passagem, agora=AGORA)

    guardada = sessao.get(PassagemRecebida, passagem.id)

    assert guardada is not None
    assert Passagem.model_validate(guardada.como_veio) == passagem
    assert (guardada.inicio, guardada.recebida_em) == (passagem.inicio, AGORA)
    assert (guardada.site_id, guardada.faixa_id) == (cenario.site_a.id, cenario.faixa_a.id)


def test_passagem_de_outro_site_e_recusada(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    passagem = fazer_passagem(site_id=str(cenario.site_b.id))

    with pytest.raises(servico.PassagemDeOutroSiteError):
        servico.receber_passagem(sessao, caixa, passagem, agora=AGORA)


def test_passagem_com_o_numero_de_outra_caixa_e_recusada(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    passagem = fazer_passagem(caixa_id=str(caixa_a.caixa_id + 1))

    with pytest.raises(servico.PassagemDeOutroSiteError):
        servico.receber_passagem(sessao, caixa, passagem, agora=AGORA)


def test_id_que_ja_e_de_outra_caixa_e_recusado(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    passagem = fazer_passagem()
    servico.receber_passagem(sessao, caixa, passagem, agora=AGORA)
    gerado = frota.gerar_codigo_de_ativacao(
        sessao, cenario.site_a.id, administrador_id=cenario.administrador.id, agora=AGORA
    )
    outra_ativada = frota.ativar(sessao, gerado.codigo, agora=AGORA)
    outra = frota.caixa_da_chave(sessao, outra_ativada.chave)
    assert outra is not None
    mesma_id = fazer_passagem(id=str(passagem.id), caixa_id=str(outra.caixa_id))

    with pytest.raises(servico.IdDeOutraCaixaError):
        servico.receber_passagem(sessao, outra, mesma_id, agora=AGORA)


def _recusa(
    sessao: Session, caixa: AcessoDaCaixa, passagem: Passagem
) -> servico.PassagemInvalidaError:
    with pytest.raises(servico.PassagemInvalidaError) as erro:
        servico.receber_passagem(sessao, caixa, passagem, agora=AGORA)
    return erro.value


def test_faixa_de_outro_site_da_mesma_empresa_e_recusada(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    portaria = cadastro.criar_portaria(sessao, cenario.site_a2, nome="Portaria 2")
    outra = cadastro.criar_faixa(sessao, portaria, nome="Entrada 2", sentido="entrada")
    passagem = fazer_passagem(faixa_id=str(outra.id))

    assert _recusa(sessao, caixa, passagem).loc == ("faixa_id",)


def test_faixa_que_nao_e_numero_e_recusada(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    passagem = fazer_passagem(faixa_id="entrada-1")

    assert _recusa(sessao, caixa, passagem).loc == ("faixa_id",)


def test_sentido_diferente_do_da_faixa_e_recusado(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    passagem = fazer_passagem(sentido="saida")

    assert _recusa(sessao, caixa, passagem).loc == ("sentido",)


def test_camera_de_outra_empresa_na_placa_e_recusada(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    placa = {
        "placa": "ABC1234",
        "papel": "cavalo",
        "confianca": 0.9,
        "camera_id": str(cenario.camera_b.id),
        "quadros": 3,
    }
    passagem = fazer_passagem(placas=[placa])

    assert _recusa(sessao, caixa, passagem).loc == ("placas", 0, "camera_id")


def test_camera_de_outra_empresa_na_foto_e_recusada(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    fotos = [
        {"tipo": "placa", "camera_id": str(cenario.camera_a.id), "ref": "p/1.jpg"},
        {"tipo": "contexto", "camera_id": str(cenario.camera_b.id), "ref": "p/2.jpg"},
    ]
    passagem = fazer_passagem(fotos=fotos)

    assert _recusa(sessao, caixa, passagem).loc == ("fotos", 1, "camera_id")


def test_ref_de_foto_fora_da_regra_e_recusado(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    fotos = [{"tipo": "placa", "camera_id": str(cenario.camera_a.id), "ref": "../fora.jpg"}]
    passagem = fazer_passagem(fotos=fotos)

    assert _recusa(sessao, caixa, passagem).loc == ("fotos", 0, "ref")


def test_passagem_sem_placas_tambem_e_guardada(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    caixa: AcessoDaCaixa,
    fazer_passagem: Callable[..., Passagem],
) -> None:
    # Nenhuma placa lida: a nuvem guarda e, no mês 2, trata como exceção (SDD 3.2).
    passagem = fazer_passagem(placas=[])

    assert servico.receber_passagem(sessao, caixa, passagem, agora=AGORA) is True


def test_banco_recusa_passagem_de_uma_empresa_em_site_de_outra(
    sessao: Session, cenario: Demonstracao, caixa_a: CaixaAtivada
) -> None:
    # Mesmo que o código erre, o banco não mistura empresas (chave estrangeira composta).
    with pytest.raises(DBAPIError) as erro:
        sessao.execute(
            text(
                "insert into passagem (id, empresa_id, site_id, caixa_id, faixa_id, sentido,"
                " inicio, fim, recebida_em, como_veio) values (:id, :empresa, :site, :caixa,"
                " :faixa, 'entrada', now(), now(), now(), '{}')"
            ),
            {
                "id": uuid4(),
                "empresa": cenario.empresa_b.id,
                "site": cenario.site_a.id,
                "caixa": caixa_a.caixa_id,
                "faixa": cenario.faixa_a.id,
            },
        )

    assert sqlstate(erro.value) == SQLSTATE_CHAVE_ESTRANGEIRA

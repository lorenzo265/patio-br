"""A guarda das fotos e a disputa (SDD 8.3, D-70): a foto vencida se apaga e a prova fica."""

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem import tarefas_de_fundo as fila
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.armazenamento import ArmazenamentoLocal
from nuvem.cadastro.acesso import Acesso
from nuvem.cifra import Cifra
from nuvem.erros import NaoEncontradoError
from nuvem.frota.servico import CaixaAtivada
from nuvem.guarda import servico as guarda
from nuvem.guarda.modelos import FotoApagada, MarcaDeDisputa
from nuvem.portaria.modelos import Evento, Visita
from nuvem.prova import servico as prova
from nuvem.prova.ancoras import AncorasNoDisco
from nuvem.prova.modelos import EloDaProva
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 17, 10, tzinfo=UTC)
JANELA = datetime(2026, 10, 5, 16, 0, tzinfo=UTC)
FOTO = b"\xff\xd8\xff" + b"recorte inventado"
DEPOIS_DO_PRAZO = AGORA + timedelta(days=91)


@pytest.fixture
def armazenamento(tmp_path: Path, cifra: Cifra) -> ArmazenamentoLocal:
    return ArmazenamentoLocal(tmp_path / "fotos", cifra)


@pytest.fixture
def chegar(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    registrar_passagem: Callable[..., Passagem],
) -> Callable[..., tuple[Passagem, Visita]]:
    """A passagem e a visita; com ``agendada``, ela casa com um agendamento (sem exceção)."""

    def _chegar(*, agendada: bool = True, **mudancas: Any) -> tuple[Passagem, Visita]:
        if agendada:
            destino = SiteDoAgendamento(
                empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id, usuario_id=None
            )
            dados = DadosDoAgendamento.model_validate(
                {
                    "codigo_externo": "AG-1",
                    "janela_inicio": JANELA,
                    "janela_fim": JANELA + timedelta(hours=2),
                    "tipo": "descarga",
                    "placa_cavalo": "ABC1D23",
                }
            )
            agendamentos.gravar(sessao, destino, "planilha", dados, agora=JANELA)
        armazenamento.guardar(caixa_a.caixa_id, "p/1.jpg", FOTO)
        passagem = registrar_passagem(**mudancas)
        contexto = fila.Contexto(armazenamento=armazenamento)
        fila.executar_pendentes(sessao, agora=AGORA, contexto=contexto)
        evento = sessao.scalars(select(Evento).where(Evento.passagem_id == passagem.id)).one()
        visita = sessao.get(Visita, evento.visita_id)
        assert visita is not None
        return passagem, visita

    return _chegar


def _arquivo(tmp_path: Path, caixa: CaixaAtivada, ref: str = "p/1.jpg") -> Path:
    return tmp_path / "fotos" / f"caixa-{caixa.caixa_id}" / ref


# --- A foto vencida -------------------------------------------------------------------------


def test_a_foto_vencida_e_apagada_e_fica_registrada(
    sessao: Session,
    tmp_path: Path,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    passagem, _ = chegar()

    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=DEPOIS_DO_PRAZO, dias=90) == 1
    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=DEPOIS_DO_PRAZO, dias=90) == 0

    assert not _arquivo(tmp_path, caixa_a).exists()
    (apagada,) = sessao.scalars(select(FotoApagada))
    assert (apagada.passagem_id, apagada.indice, apagada.ref) == (passagem.id, 0, "p/1.jpg")
    assert (apagada.existia, apagada.motivo, apagada.apagada_em) == (
        True,
        "prazo_de_guarda",
        DEPOIS_DO_PRAZO,
    )


def test_antes_do_prazo_a_foto_fica(
    sessao: Session,
    tmp_path: Path,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    chegar()

    # A passagem chegou às 17:02:21 de 05/10: 90 dias depois, ainda é dia dela.
    no_limite = datetime(2027, 1, 3, 17, 2, 20, tzinfo=UTC)
    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=no_limite, dias=90) == 0
    assert _arquivo(tmp_path, caixa_a).exists()
    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=DEPOIS_DO_PRAZO, dias=92) == 0


def test_a_visita_com_excecao_aberta_segura_as_fotos(
    sessao: Session,
    tmp_path: Path,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    _, visita = chegar(agendada=False)
    assert visita.estado == "EXCECAO"

    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=DEPOIS_DO_PRAZO, dias=90) == 0
    assert _arquivo(tmp_path, caixa_a).exists()


def test_a_excecao_resolvida_nao_segura_mais(
    sessao: Session,
    cenario: Demonstracao,
    armazenamento: ArmazenamentoLocal,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    from nuvem.cadastro.acesso import acesso_do_usuario
    from nuvem.portaria import resolucao
    from nuvem.portaria.modelos import Excecao

    _, visita = chegar(agendada=False)
    (excecao,) = sessao.scalars(select(Excecao).where(Excecao.visita_id == visita.id))
    porteiro = acesso_do_usuario(sessao, cenario.porteiro_a.id)
    resolucao.aceitar_sem_agendamento(sessao, porteiro, excecao.id, agora=AGORA)

    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=DEPOIS_DO_PRAZO, dias=90) == 1


def test_a_passagem_ja_limpa_sai_da_fila_da_guarda(
    sessao: Session,
    cenario: Demonstracao,
    armazenamento: ArmazenamentoLocal,
    chegar: Callable[..., tuple[Passagem, Visita]],
    registrar_passagem: Callable[..., Passagem],
    caixa_a: CaixaAtivada,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Uma passagem por vez: a já limpa não pode tomar o lugar da seguinte.
    monkeypatch.setattr(guarda, "PASSAGENS_POR_VEZ", 1)
    chegar()
    armazenamento.guardar(caixa_a.caixa_id, "p/2.jpg", FOTO)
    camera = str(cenario.camera_a.id)
    registrar_passagem(fotos=[{"tipo": "placa", "camera_id": camera, "ref": "p/2.jpg"}])

    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=DEPOIS_DO_PRAZO, dias=90) == 1
    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=DEPOIS_DO_PRAZO, dias=90) == 1
    assert len(list(sessao.scalars(select(FotoApagada)))) == 2


def test_a_disputa_segura_as_fotos_ate_ser_desmarcada(
    sessao: Session,
    acesso_a: Acesso,
    tmp_path: Path,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    _, visita = chegar()
    guarda.marcar_disputa(
        sessao, acesso_a, visita.id, motivo="estadia contestada", agora=AGORA + timedelta(days=30)
    )
    assert guarda.em_disputa(sessao, acesso_a, visita.id)

    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=DEPOIS_DO_PRAZO, dias=90) == 0
    assert _arquivo(tmp_path, caixa_a).exists()

    guarda.desmarcar_disputa(
        sessao, acesso_a, visita.id, motivo="acordo fechado", agora=DEPOIS_DO_PRAZO
    )
    assert not guarda.em_disputa(sessao, acesso_a, visita.id)
    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=DEPOIS_DO_PRAZO, dias=90) == 1
    marcas = [(m.acao, m.motivo) for m in sessao.scalars(select(MarcaDeDisputa))]
    assert marcas == [("marcar", "estadia contestada"), ("desmarcar", "acordo fechado")]


def test_a_foto_que_nunca_chegou_fica_registrada_como_tal(
    sessao: Session,
    cenario: Demonstracao,
    armazenamento: ArmazenamentoLocal,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    camera = str(cenario.camera_a.id)
    chegar(fotos=[{"tipo": "contexto", "camera_id": camera, "ref": "nunca/veio.jpg"}])

    assert guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=DEPOIS_DO_PRAZO, dias=90) == 0

    (apagada,) = sessao.scalars(select(FotoApagada))
    assert (apagada.ref, apagada.existia) == ("nunca/veio.jpg", False)


def test_a_disputa_e_de_quem_ve_a_visita(
    sessao: Session, acesso_b: Acesso, chegar: Callable[..., tuple[Passagem, Visita]]
) -> None:
    _, visita = chegar()

    with pytest.raises(NaoEncontradoError):
        guarda.marcar_disputa(sessao, acesso_b, visita.id, motivo="x", agora=AGORA)
    with pytest.raises(NaoEncontradoError):
        guarda.em_disputa(sessao, acesso_b, visita.id)


def test_marcar_de_novo_nao_repete_a_marca(
    sessao: Session, acesso_a: Acesso, chegar: Callable[..., tuple[Passagem, Visita]]
) -> None:
    _, visita = chegar()
    guarda.marcar_disputa(sessao, acesso_a, visita.id, motivo="um", agora=AGORA)
    guarda.marcar_disputa(sessao, acesso_a, visita.id, motivo="dois", agora=AGORA)
    guarda.desmarcar_disputa(sessao, acesso_a, visita.id, motivo="", agora=AGORA)
    guarda.desmarcar_disputa(sessao, acesso_a, visita.id, motivo="", agora=AGORA)

    assert [m.acao for m in sessao.scalars(select(MarcaDeDisputa))] == ["marcar", "desmarcar"]


# --- A prova guarda o que foi apagado -------------------------------------------------------


def test_a_foto_apagada_e_a_disputa_entram_na_cadeia_e_a_conferencia_aceita(
    sessao: Session,
    acesso_a: Acesso,
    tmp_path: Path,
    armazenamento: ArmazenamentoLocal,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    passagem, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    guarda.marcar_disputa(sessao, acesso_a, visita.id, motivo="contestada", agora=AGORA)
    guarda.desmarcar_disputa(sessao, acesso_a, visita.id, motivo="resolvida", agora=AGORA)
    guarda.apagar_fotos_vencidas(sessao, armazenamento, agora=DEPOIS_DO_PRAZO, dias=90)

    prova.selar(sessao, agora=DEPOIS_DO_PRAZO)

    elos = list(
        sessao.scalars(
            select(EloDaProva).where(EloDaProva.visita_id == visita.id).order_by(EloDaProva.ordem)
        )
    )
    tipos = [elo.tipo for elo in elos]
    assert tipos.count("disputa") == 2
    assert tipos[-1] == "foto_apagada"
    assert elos[-1].referencia == f"{passagem.id}:0"
    assert elos[-1].conteudo["motivo"] == "prazo_de_guarda"
    resultado = prova.conferir(
        sessao, acesso_a, visita.id, armazenamento, AncorasNoDisco(tmp_path / "fotos")
    )
    assert resultado.quebra is None


def test_a_marca_de_disputa_sozinha_entra_na_cadeia(
    sessao: Session, acesso_a: Acesso, chegar: Callable[..., tuple[Passagem, Visita]]
) -> None:
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    depois = AGORA + timedelta(days=20)
    guarda.marcar_disputa(sessao, acesso_a, visita.id, motivo="contestada", agora=depois)

    assert prova.selar(sessao, agora=depois) == 1


def test_a_foto_que_sumiu_sem_a_guarda_continua_quebrando(
    sessao: Session,
    acesso_a: Acesso,
    tmp_path: Path,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    _arquivo(tmp_path, caixa_a).unlink()

    resultado = prova.conferir(
        sessao, acesso_a, visita.id, armazenamento, AncorasNoDisco(tmp_path / "fotos")
    )

    assert resultado.quebra is not None
    assert resultado.quebra.motivo == "a foto sumiu"


# --- O worker -------------------------------------------------------------------------------


def test_o_worker_apaga_as_fotos_vencidas(
    sessao: Session,
    tmp_path: Path,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    chegar()
    parar = threading.Event()

    def dormir(_segundos: float) -> None:
        parar.set()

    fila.rodar(
        lambda: sessao, parar, relogio=lambda: DEPOIS_DO_PRAZO, dormir=dormir,
        armazenamento=armazenamento, dias_das_fotos=90,
    )  # fmt: skip

    assert not _arquivo(tmp_path, caixa_a).exists()

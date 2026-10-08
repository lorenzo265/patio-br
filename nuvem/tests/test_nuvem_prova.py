"""A prova da visita (SDD 5.5, D-69): o resumo das fotos, a cadeia, a conferência e a âncora."""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from contratos.saude import Saude
from nuvem import tarefas_de_fundo as fila
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.armazenamento import ArmazenamentoLocal
from nuvem.cadastro.acesso import Acesso, acesso_do_usuario
from nuvem.cifra import Cifra
from nuvem.erros import NaoEncontradoError
from nuvem.frota import saude as frota
from nuvem.frota import servico as caixas
from nuvem.frota.servico import CaixaAtivada
from nuvem.mensagens import servico as mensagens
from nuvem.mensagens.modelos import Mensagem
from nuvem.portaria import conferencia
from nuvem.portaria.modelos import Evento, PassagemRecebida, Visita
from nuvem.prova import cadeia
from nuvem.prova import servico as prova
from nuvem.prova.ancoras import AncorasNoDisco
from nuvem.prova.modelos import AncoraDoDia, EloDaProva, FotoRecebida
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 17, 10, tzinfo=UTC)
JANELA = datetime(2026, 10, 5, 16, 0, tzinfo=UTC)
FOTO = b"\xff\xd8\xff" + b"recorte inventado"
CELULAR = "+5511987654321"


@pytest.fixture
def armazenamento(tmp_path: Path, cifra: Cifra) -> ArmazenamentoLocal:
    return ArmazenamentoLocal(tmp_path / "fotos", cifra)


@pytest.fixture
def guarda(tmp_path: Path) -> AncorasNoDisco:
    return AncorasNoDisco(tmp_path / "fotos")


@pytest.fixture
def chegar(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    registrar_passagem: Callable[..., Passagem],
) -> Callable[..., tuple[Passagem, Visita]]:
    """Um agendamento, a passagem que casa com ele (a foto chegou antes) e as mensagens."""
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
            "motorista_celular": CELULAR,
        }
    )
    agendamentos.gravar(sessao, destino, "planilha", dados, agora=JANELA - timedelta(days=1))
    mensagens.preparar(sessao, agora=JANELA - timedelta(days=1))  # a confirmação, na véspera

    def _chegar(**mudancas: Any) -> tuple[Passagem, Visita]:
        armazenamento.guardar(caixa_a.caixa_id, "p/1.jpg", FOTO)
        passagem = registrar_passagem(**mudancas)
        contexto = fila.Contexto(armazenamento=armazenamento)
        fila.executar_pendentes(sessao, agora=AGORA, contexto=contexto)
        mensagens.preparar(sessao, agora=AGORA)
        evento = sessao.scalars(select(Evento).where(Evento.passagem_id == passagem.id)).one()
        visita = sessao.get(Visita, evento.visita_id)
        assert visita is not None
        return passagem, visita

    return _chegar


def _elos(sessao: Session, visita: Visita) -> list[EloDaProva]:
    return list(
        sessao.scalars(
            select(EloDaProva).where(EloDaProva.visita_id == visita.id).order_by(EloDaProva.ordem)
        )
    )


def _cadeia(elos: list[EloDaProva]) -> list[cadeia.Elo]:
    return [
        cadeia.Elo(e.ordem, e.tipo, e.referencia, e.conteudo, e.anterior, e.resumo) for e in elos
    ]


def _porteiro(sessao: Session, cenario: Demonstracao) -> Acesso:
    return acesso_do_usuario(sessao, cenario.porteiro_a.id)


# --- O resumo das fotos ---------------------------------------------------------------------


def test_a_nuvem_resume_cada_foto_que_chegou(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    registrar_passagem: Callable[..., Passagem],
) -> None:
    camera = str(cenario.camera_a.id)
    armazenamento.guardar(caixa_a.caixa_id, "p/2.jpg", FOTO)
    passagem = registrar_passagem(
        fotos=[
            {"tipo": "contexto", "camera_id": camera, "ref": "p/1.jpg"},  # não chegou
            {"tipo": "placa", "camera_id": camera, "ref": "p/2.jpg"},
        ]
    )

    assert prova.resumir_fotos(sessao, armazenamento, passagem.id, agora=AGORA) == 1
    assert prova.resumir_fotos(sessao, armazenamento, passagem.id, agora=AGORA) == 0

    (foto,) = sessao.scalars(select(FotoRecebida))
    assert (foto.indice, foto.ref, foto.tamanho) == (1, "p/2.jpg", len(FOTO))
    assert foto.resumo == hashlib.sha256(FOTO).hexdigest()
    assert foto.empresa_id == cenario.empresa_a.id


def test_a_passagem_que_chega_pede_o_resumo_das_fotos(
    sessao: Session,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    registrar_passagem: Callable[..., Passagem],
) -> None:
    armazenamento.guardar(caixa_a.caixa_id, "p/1.jpg", FOTO)
    registrar_passagem()
    registrar_passagem(fotos=[])  # sem fotos, sem tarefa

    tipos = sorted(tarefa.tipo for tarefa in sessao.scalars(select(fila.TarefaDeFundo)))
    assert tipos == ["casar_passagem", "casar_passagem", "resumir_fotos"]
    fila.executar_pendentes(
        sessao, agora=AGORA, contexto=fila.Contexto(armazenamento=armazenamento)
    )
    assert sessao.scalar(select(FotoRecebida.resumo)) == hashlib.sha256(FOTO).hexdigest()


def test_sem_o_armazenamento_a_tarefa_tenta_de_novo(
    sessao: Session,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    registrar_passagem: Callable[..., Passagem],
) -> None:
    armazenamento.guardar(caixa_a.caixa_id, "p/1.jpg", FOTO)
    registrar_passagem()

    fila.executar_pendentes(sessao, agora=AGORA)

    (tarefa,) = sessao.scalars(
        select(fila.TarefaDeFundo).where(fila.TarefaDeFundo.tipo == "resumir_fotos")
    )
    assert (tarefa.situacao, tarefa.tentativas) == ("pendente", 1)


# --- Selar ----------------------------------------------------------------------------------


def test_selar_encadeia_tudo_o_que_a_visita_tem(
    sessao: Session,
    cenario: Demonstracao,
    acesso_a: Acesso,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    passagem, visita = chegar()
    conferencia.conferir(sessao, _porteiro(sessao, cenario), passagem.id, 0, "ABC1D23", agora=AGORA)

    novos = prova.selar(sessao, agora=AGORA + timedelta(minutes=1))

    elos = _elos(sessao, visita)
    assert novos == len(elos)
    assert {elo.tipo for elo in elos} == {"passagem", "foto", "evento", "conferencia", "mensagem"}
    assert [elo.ordem for elo in elos] == list(range(1, len(elos) + 1))
    assert cadeia.primeira_quebra(_cadeia(elos)) is None
    # Na ordem em que chegaram: a confirmação da véspera vem antes da passagem, e a passagem, a
    # foto dela e o check-in, antes da conferência.
    assert (elos[0].tipo, elos[0].conteudo["modelo"]) == ("mensagem", "confirmacao")
    tipos = [elo.tipo for elo in elos]
    assert tipos.index("passagem") < tipos.index("conferencia")
    assert elos[0].selado_em == AGORA + timedelta(minutes=1)
    assert prova.selar(sessao, agora=AGORA + timedelta(minutes=2)) == 0


def test_os_retratos_trazem_o_registro_inteiro(
    sessao: Session, chegar: Callable[..., tuple[Passagem, Visita]]
) -> None:
    passagem, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    por_tipo = {elo.tipo: elo for elo in _elos(sessao, visita)}

    recebida = sessao.get(PassagemRecebida, passagem.id)
    assert recebida is not None
    assert por_tipo["passagem"].referencia == str(passagem.id)
    assert por_tipo["passagem"].conteudo["passagem"]["como_veio"] == recebida.como_veio
    assert por_tipo["foto"].referencia == f"{passagem.id}:0"
    assert por_tipo["foto"].conteudo["resumo"] == hashlib.sha256(FOTO).hexdigest()
    assert por_tipo["evento"].conteudo["tipo"] == "check_in"
    mensagem = sessao.scalars(select(Mensagem)).first()
    assert mensagem is not None
    assert f"{mensagem.id}:criada" in {elo.referencia for elo in _elos(sessao, visita)}


def test_o_que_chega_depois_continua_a_cadeia(
    sessao: Session,
    cenario: Demonstracao,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    passagem, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    ultimo = _elos(sessao, visita)[-1]

    conferencia.conferir(sessao, _porteiro(sessao, cenario), passagem.id, 0, "ABC1D24", agora=AGORA)
    assert prova.selar(sessao, agora=AGORA + timedelta(minutes=1)) == 1

    novo = _elos(sessao, visita)[-1]
    assert (novo.ordem, novo.anterior, novo.tipo) == (
        ultimo.ordem + 1,
        ultimo.resumo,
        "conferencia",
    )
    assert cadeia.primeira_quebra(_cadeia(_elos(sessao, visita))) is None


def test_a_foto_resumida_depois_entra_na_cadeia(
    sessao: Session,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    registrar_passagem: Callable[..., Passagem],
) -> None:
    # Na primeira vez a foto não estava lá; quando o resumo vem depois, a cadeia continua.
    passagem = registrar_passagem()
    fila.executar_pendentes(
        sessao, agora=AGORA, contexto=fila.Contexto(armazenamento=armazenamento)
    )
    evento = sessao.scalars(select(Evento).where(Evento.passagem_id == passagem.id)).one()
    prova.selar(sessao, agora=AGORA)
    visita = sessao.get(Visita, evento.visita_id)
    assert visita is not None
    assert "foto" not in {elo.tipo for elo in _elos(sessao, visita)}

    armazenamento.guardar(caixa_a.caixa_id, "p/1.jpg", FOTO)
    prova.resumir_fotos(sessao, armazenamento, passagem.id, agora=AGORA + timedelta(minutes=5))

    assert prova.selar(sessao, agora=AGORA + timedelta(minutes=6)) == 1
    assert _elos(sessao, visita)[-1].referencia == f"{passagem.id}:0"


def test_a_mensagem_ganha_um_elo_a_cada_situacao(
    sessao: Session, chegar: Callable[..., tuple[Passagem, Visita]]
) -> None:
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    mensagem = sessao.scalars(select(Mensagem).order_by(Mensagem.id)).first()
    assert mensagem is not None
    sessao.execute(
        update(Mensagem)
        .where(Mensagem.id == mensagem.id)
        .values(situacao="entregue", enviada_em=AGORA, entregue_em=AGORA + timedelta(minutes=1))
    )

    assert prova.selar(sessao, agora=AGORA + timedelta(minutes=2)) == 2

    novos = [elo.referencia for elo in _elos(sessao, visita)[-2:]]
    assert novos == [f"{mensagem.id}:enviada", f"{mensagem.id}:entregue"]


def test_a_passagem_leva_a_saude_da_caixa_naquela_hora(
    sessao: Session,
    caixa_a: CaixaAtivada,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    caixa = caixas.caixa_da_chave(sessao, caixa_a.chave)
    assert caixa is not None

    def _saude(recebida: datetime, adiantada: float) -> None:
        dados = {
            "versao_contrato": 1, "caixa_id": str(caixa.caixa_id), "site_id": str(caixa.site_id),
            "momento": (recebida + timedelta(seconds=adiantada)).isoformat(),
            "versao_programa": "0.1.0", "versao_leitor": "v0", "cpu": 10.0, "temperatura": None,
            "memoria": 10.0, "disco": 10.0, "cameras": [],
            "fila": {"passagens": 0, "fotos": 0, "recusadas": 0},
        }  # fmt: skip
        frota.receber_saude(sessao, caixa, Saude.model_validate(dados), agora=recebida)

    _saude(datetime(2026, 10, 5, 16, 59, tzinfo=UTC), adiantada=3.0)  # a anterior a ela
    _saude(datetime(2026, 10, 5, 17, 1, tzinfo=UTC), adiantada=0.5)  # a de antes da passagem
    _saude(datetime(2026, 10, 5, 17, 3, tzinfo=UTC), adiantada=9.0)  # a de depois não vale
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)

    (elo,) = [elo for elo in _elos(sessao, visita) if elo.tipo == "passagem"]
    assert elo.conteudo["saude"]["recebida_em"] == "2026-10-05T17:01:00+00:00"
    assert elo.conteudo["saude"]["diferenca_do_relogio"] == pytest.approx(0.5)


def test_sem_saude_a_passagem_diz_que_nao_tinha(
    sessao: Session, chegar: Callable[..., tuple[Passagem, Visita]]
) -> None:
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)

    (elo,) = [elo for elo in _elos(sessao, visita) if elo.tipo == "passagem"]
    assert elo.conteudo["saude"] is None


def test_o_worker_so_olha_os_ultimos_7_dias_e_a_pagina_sela_o_resto(
    sessao: Session, acesso_a: Acesso, chegar: Callable[..., tuple[Passagem, Visita]]
) -> None:
    _, visita = chegar()
    depois = AGORA + timedelta(days=8)

    assert prova.selar(sessao, agora=depois) == 0
    assert prova.selar_a_visita(sessao, acesso_a, visita.id, agora=depois) > 0
    assert prova.selar_a_visita(sessao, acesso_a, visita.id, agora=depois) == 0


def test_a_busca_e_os_nomes_ficam_nos_sites_e_na_empresa_de_quem_pede(
    sessao: Session,
    cenario: Demonstracao,
    acesso_a: Acesso,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    from nuvem.portaria import visitas
    from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita

    _, visita = chegar()
    # O gestor A só está ligado ao site_a: a visita do outro site da empresa não aparece.
    no_outro_site = visitas.abrir_visita(
        sessao, SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a2.id),
        "check_in", momento=AGORA, agora=AGORA,
        composicao=(PlacaNaVisita(placa="ABC1D23", papel="cavalo", como="lida"),),
    )  # fmt: skip

    achadas = [v.id for v in prova.visitas_para_a_prova(sessao, acesso_a, placa="ABC1D23")]
    nomes = prova.nomes_das_pessoas(sessao, acesso_a, [cenario.porteiro_a.id, cenario.gestor_b.id])

    assert achadas == [visita.id]
    assert no_outro_site.id not in achadas
    assert nomes == {cenario.porteiro_a.id: cenario.porteiro_a.nome}


def test_a_prova_de_outra_empresa_nao_existe(
    sessao: Session,
    acesso_b: Acesso,
    armazenamento: ArmazenamentoLocal,
    guarda: AncorasNoDisco,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    _, visita = chegar()

    with pytest.raises(NaoEncontradoError):
        prova.selar_a_visita(sessao, acesso_b, visita.id, agora=AGORA)
    with pytest.raises(NaoEncontradoError):
        prova.elos_da_visita(sessao, acesso_b, visita.id)
    with pytest.raises(NaoEncontradoError):
        prova.conferir(sessao, acesso_b, visita.id, armazenamento, guarda)


def test_o_elo_nao_se_edita(
    sessao: Session, chegar: Callable[..., tuple[Passagem, Visita]]
) -> None:
    from sqlalchemy.exc import DBAPIError

    from nuvem.banco import SQLSTATE_SO_ACRESCENTA, sqlstate

    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    primeiro = _elos(sessao, visita)[0]

    with pytest.raises(DBAPIError) as erro, sessao.begin_nested():
        sessao.execute(
            update(EloDaProva).where(EloDaProva.id == primeiro.id).values(resumo="0" * 64)
        )
    assert sqlstate(erro.value) == SQLSTATE_SO_ACRESCENTA


def test_o_worker_sela_a_cada_minuto_e_grava_a_ancora_do_dia(
    sessao: Session,
    armazenamento: ArmazenamentoLocal,
    guarda: AncorasNoDisco,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    import threading

    _, visita = chegar()
    visita_id = visita.id  # o laço fecha a sessão a cada volta
    parar = threading.Event()
    horas = iter([AGORA, datetime(2026, 10, 6, 0, 20, tzinfo=UTC)])
    voltas: list[int] = []

    def dormir(_segundos: float) -> None:
        voltas.append(1)
        if len(voltas) == 2:
            parar.set()

    fila.rodar(
        lambda: sessao, parar, relogio=lambda: next(horas), dormir=dormir,
        armazenamento=armazenamento, ancoras=guarda,
    )  # fmt: skip

    selados = sessao.scalars(select(EloDaProva.selado_em).where(EloDaProva.visita_id == visita_id))
    assert set(selados) == {AGORA}
    assert [a.dia for a in sessao.scalars(select(AncoraDoDia))] == [date(2026, 10, 5)]


# --- Conferir -------------------------------------------------------------------------------


def test_a_cadeia_que_ninguem_mexeu_confere(
    sessao: Session,
    acesso_a: Acesso,
    armazenamento: ArmazenamentoLocal,
    guarda: AncorasNoDisco,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)

    resultado = prova.conferir(sessao, acesso_a, visita.id, armazenamento, guarda)

    assert resultado.quebra is None
    assert resultado.elos == len(_elos(sessao, visita))
    assert resultado.integra
    assert [(a.dia, a.situacao) for a in resultado.ancoras] == [(date(2026, 10, 5), "sem_ancora")]


def _quebra(
    sessao: Session,
    acesso: Acesso,
    visita: Visita,
    armazenamento: ArmazenamentoLocal,
    guarda: AncorasNoDisco,
) -> tuple[str, str]:
    resultado = prova.conferir(sessao, acesso, visita.id, armazenamento, guarda)
    assert resultado.quebra is not None
    assert not resultado.integra
    (elo,) = [e for e in _elos(sessao, visita) if e.ordem == resultado.quebra.ordem]
    return elo.tipo, resultado.quebra.motivo


def test_a_passagem_mudada_no_banco_quebra_a_cadeia(
    sessao: Session,
    acesso_a: Acesso,
    armazenamento: ArmazenamentoLocal,
    guarda: AncorasNoDisco,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    passagem, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    recebida = sessao.get(PassagemRecebida, passagem.id)
    assert recebida is not None
    como_veio = {**recebida.como_veio, "inicio": "2026-10-05T15:00:00+00:00"}
    sessao.execute(
        update(PassagemRecebida)
        .where(PassagemRecebida.id == passagem.id)
        .values(como_veio=como_veio)
    )

    assert _quebra(sessao, acesso_a, visita, armazenamento, guarda) == (
        "passagem",
        "o registro mudou depois de selado",
    )


def test_a_mensagem_mudada_no_banco_quebra_a_cadeia(
    sessao: Session,
    acesso_a: Acesso,
    armazenamento: ArmazenamentoLocal,
    guarda: AncorasNoDisco,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    sessao.execute(update(Mensagem).values(criada_em=AGORA - timedelta(hours=3)))

    assert _quebra(sessao, acesso_a, visita, armazenamento, guarda) == (
        "mensagem",
        "o registro mudou depois de selado",
    )


@pytest.mark.parametrize(
    ("mexer", "motivo"), [("trocar", "a foto mudou"), ("apagar", "a foto sumiu")]
)
def test_a_foto_trocada_ou_apagada_quebra_a_cadeia(
    sessao: Session,
    acesso_a: Acesso,
    caixa_a: CaixaAtivada,
    tmp_path: Path,
    armazenamento: ArmazenamentoLocal,
    guarda: AncorasNoDisco,
    chegar: Callable[..., tuple[Passagem, Visita]],
    mexer: str,
    motivo: str,
) -> None:
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    arquivo = tmp_path / "fotos" / f"caixa-{caixa_a.caixa_id}" / "p" / "1.jpg"
    if mexer == "trocar":
        arquivo.write_bytes(FOTO + b"outra")
    else:
        arquivo.unlink()

    assert _quebra(sessao, acesso_a, visita, armazenamento, guarda) == ("foto", motivo)


def test_com_duas_quebras_vale_a_primeira_da_cadeia(
    sessao: Session,
    acesso_a: Acesso,
    caixa_a: CaixaAtivada,
    tmp_path: Path,
    armazenamento: ArmazenamentoLocal,
    guarda: AncorasNoDisco,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    # O aviso "na fila" (selado depois da foto) e a foto: vale a foto, que vem antes.
    sessao.execute(
        update(Mensagem)
        .where(Mensagem.modelo == "na_fila")
        .values(criada_em=AGORA - timedelta(hours=3))
    )
    (tmp_path / "fotos" / f"caixa-{caixa_a.caixa_id}" / "p" / "1.jpg").unlink()

    assert _quebra(sessao, acesso_a, visita, armazenamento, guarda) == ("foto", "a foto sumiu")


# --- A âncora do dia ------------------------------------------------------------------------


def test_a_ancora_guarda_o_ultimo_resumo_de_cada_visita_do_dia(
    sessao: Session,
    guarda: AncorasNoDisco,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)

    assert prova.gravar_ancoras(sessao, guarda, agora=AGORA + timedelta(hours=1)) == 0  # o dia
    # Nos 10 primeiros minutos do dia seguinte, ainda não: quem selava, ainda pode estar gravando.
    assert prova.gravar_ancoras(sessao, guarda, agora=datetime(2026, 10, 6, 0, 5, tzinfo=UTC)) == 0
    assert prova.gravar_ancoras(sessao, guarda, agora=datetime(2026, 10, 6, 0, 15, tzinfo=UTC)) == 1
    assert prova.gravar_ancoras(sessao, guarda, agora=datetime(2026, 10, 6, 0, 20, tzinfo=UTC)) == 0

    (ancora,) = sessao.scalars(select(AncoraDoDia))
    ultimo = _elos(sessao, visita)[-1]
    conteudo = guarda.ler(ancora.arquivo)
    assert conteudo is not None
    assert hashlib.sha256(conteudo).hexdigest() == ancora.resumo
    lido = json.loads(conteudo)
    assert lido["dia"] == "2026-10-05"
    assert lido["visitas"] == [
        {"visita": visita.id, "ordem": ultimo.ordem, "resumo": ultimo.resumo}
    ]
    assert (ancora.dia, ancora.visitas, ancora.travada) == (date(2026, 10, 5), 1, False)
    # Só números e resumos: nada da placa, do motorista ou do celular.
    assert b"ABC1D23" not in conteudo
    assert CELULAR.encode() not in conteudo


def test_cada_dia_tem_a_sua_ancora(
    sessao: Session,
    cenario: Demonstracao,
    guarda: AncorasNoDisco,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    passagem, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    primeiro_dia = _elos(sessao, visita)[-1]
    conferencia.conferir(sessao, _porteiro(sessao, cenario), passagem.id, 0, "ABC1D23", agora=AGORA)
    prova.selar(sessao, agora=AGORA + timedelta(days=1))

    assert prova.gravar_ancoras(sessao, guarda, agora=AGORA + timedelta(days=2)) == 2

    por_dia = {
        a.dia: json.loads(guarda.ler(a.arquivo) or b"") for a in sessao.scalars(select(AncoraDoDia))
    }
    assert por_dia[date(2026, 10, 5)]["visitas"][0]["resumo"] == primeiro_dia.resumo
    assert por_dia[date(2026, 10, 6)]["visitas"][0]["resumo"] == _elos(sessao, visita)[-1].resumo


def test_a_conferencia_olha_as_ancoras(
    sessao: Session,
    acesso_a: Acesso,
    armazenamento: ArmazenamentoLocal,
    guarda: AncorasNoDisco,
    tmp_path: Path,
    chegar: Callable[..., tuple[Passagem, Visita]],
) -> None:
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    prova.gravar_ancoras(sessao, guarda, agora=AGORA + timedelta(days=1))

    resultado = prova.conferir(sessao, acesso_a, visita.id, armazenamento, guarda)
    assert [(a.situacao, a.motivo) for a in resultado.ancoras] == [("confere", "")]
    assert resultado.integra

    # Quem refaz a cadeia no banco precisa refazer a âncora também: o registro dela aponta para
    # outro arquivo, e o arquivo de verdade, travado, continua com o resumo antigo.
    (ancora,) = sessao.scalars(select(AncoraDoDia))
    falsa = json.dumps(
        {
            "dia": "2026-10-05",
            "visitas": [
                {"visita": visita.id, "ordem": len(_elos(sessao, visita)), "resumo": "f" * 64}
            ],
        }
    ).encode()
    (tmp_path / "fotos" / "ancoras" / "falsa.json").write_bytes(falsa)
    sessao.execute(
        update(AncoraDoDia)
        .where(AncoraDoDia.id == ancora.id)
        .values(arquivo="ancoras/falsa.json", resumo=hashlib.sha256(falsa).hexdigest())
    )

    resultado = prova.conferir(sessao, acesso_a, visita.id, armazenamento, guarda)
    assert [(a.situacao, a.motivo) for a in resultado.ancoras] == [
        ("nao_confere", "a âncora não bate com a cadeia")
    ]
    assert resultado.quebra is None
    assert not resultado.integra


@pytest.mark.parametrize(
    ("mexer", "motivo"),
    [("trocar", "o arquivo da âncora mudou"), ("apagar", "o arquivo da âncora sumiu")],
)
def test_o_arquivo_da_ancora_mexido(
    sessao: Session,
    acesso_a: Acesso,
    armazenamento: ArmazenamentoLocal,
    guarda: AncorasNoDisco,
    tmp_path: Path,
    chegar: Callable[..., tuple[Passagem, Visita]],
    mexer: str,
    motivo: str,
) -> None:
    _, visita = chegar()
    prova.selar(sessao, agora=AGORA)
    prova.gravar_ancoras(sessao, guarda, agora=AGORA + timedelta(days=1))
    arquivo = tmp_path / "fotos" / "ancoras" / "2026-10-05.json"
    if mexer == "trocar":
        arquivo.write_bytes(b"{}")
    else:
        arquivo.unlink()

    resultado = prova.conferir(sessao, acesso_a, visita.id, armazenamento, guarda)

    assert [(a.situacao, a.motivo) for a in resultado.ancoras] == [("nao_confere", motivo)]

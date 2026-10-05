"""Mensagens do motorista (T43, SDD 2.2 e D-47): nascem dos eventos, no canal de demonstração."""

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem import tarefas_de_fundo as fila
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.banco import SQLSTATE_CHAVE_ESTRANGEIRA, SQLSTATE_CHECK, SQLSTATE_UNICIDADE, sqlstate
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.modelos import Doca
from nuvem.erros import NaoEncontradoError
from nuvem.mensagens import servico as mensagens
from nuvem.mensagens.modelos import Mensagem
from nuvem.patio import servico as patio
from nuvem.portaria import resolucao, visitas
from nuvem.portaria.modelos import Visita
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

Agendar = Callable[..., Agendamento]
Chegar = Callable[..., Visita]

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
"""14h em São Paulo."""
JANELA = datetime(2026, 10, 5, 16, 0, tzinfo=UTC)
"""13h em São Paulo; a janela vai até as 15h."""
CELULAR = "+5511987654321"
OUTRO_CELULAR = "+5521987650000"

CONFIRMACAO = (
    "Olá! Descarga agendada: CD Exemplo, 05/10, das 13:00 às 15:00 (agendamento AG-1). "
    "Os avisos da fila e da doca vão chegar por aqui."
)


@pytest.fixture
def agendar(sessao: Session, cenario: Demonstracao) -> Agendar:
    """Grava (ou regrava) um agendamento do site_a, das 13h às 15h de 05/10."""
    destino = SiteDoAgendamento(
        empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id, usuario_id=None
    )

    def _agendar(
        codigo: str = "AG-1",
        *,
        celular: str | None = CELULAR,
        tipo: str = "descarga",
        placa: str = "ABC1D23",
        inicio: datetime = JANELA,
        agora: datetime = AGORA,
        site_id: int | None = None,
    ) -> Agendamento:
        dados = DadosDoAgendamento.model_validate(
            {
                "codigo_externo": codigo,
                "janela_inicio": inicio,
                "janela_fim": inicio + timedelta(hours=2),
                "tipo": tipo,
                "placa_cavalo": placa,
                "motorista_celular": celular,
            }
        )
        no_site = (
            destino if site_id is None else SiteDoAgendamento(destino.empresa_id, site_id, None)
        )
        return agendamentos.gravar(sessao, no_site, "planilha", dados, agora=agora).agendamento

    return _agendar


@pytest.fixture
def chegar(sessao: Session, cenario: Demonstracao) -> Chegar:
    """Abre a visita de um caminhão que chegou ``ha`` tempo atrás (por padrão, no site_a)."""

    def _chegar(
        placa: str,
        *,
        ha: timedelta = timedelta(0),
        agendamento: Agendamento | None = None,
        site_id: int | None = None,
    ) -> Visita:
        site = SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=site_id or cenario.site_a.id)
        return visitas.abrir_visita(
            sessao, site, "check_in" if agendamento else "aceita_sem_agendamento",
            momento=AGORA - ha, agora=AGORA - ha,
            agendamento_id=agendamento.id if agendamento else None,
            composicao=(PlacaNaVisita(placa=placa, papel="cavalo", como="lida"),),
        )  # fmt: skip

    return _chegar


@pytest.fixture
def docas(sessao: Session, cenario: Demonstracao) -> list[Doca]:
    """As docas do site_a ("Doca 1" e "Doca 2")."""
    return list(
        sessao.scalars(select(Doca).where(Doca.site_id == cenario.site_a.id).order_by(Doca.nome))
    )


def _todas(sessao: Session) -> list[Mensagem]:
    return list(sessao.scalars(select(Mensagem).order_by(Mensagem.id)))


def _textos(sessao: Session, acesso: Acesso, agendamento: Agendamento) -> list[str]:
    return [m.texto for m in mensagens.conversa(sessao, acesso, agendamento.id)]


# --- A confirmação ----------------------------------------------------------------------------


def test_agendamento_com_celular_ganha_a_confirmacao(
    sessao: Session, acesso_a: Acesso, agendar: Agendar
) -> None:
    agendamento = agendar()

    assert mensagens.preparar(sessao, agora=AGORA) == 1

    [mensagem] = mensagens.conversa(sessao, acesso_a, agendamento.id)
    assert (mensagem.modelo, mensagem.texto, mensagem.para, mensagem.evento_id) == (
        "confirmacao", CONFIRMACAO, CELULAR, None,
    )  # fmt: skip
    assert (mensagem.canal, mensagem.situacao, mensagem.criada_em) == (
        "demonstracao", "guardada", AGORA,
    )  # fmt: skip
    assert (mensagem.empresa_id, mensagem.site_id) == (agendamento.empresa_id, agendamento.site_id)


def test_a_confirmacao_diz_carga_ou_descarga(
    sessao: Session, acesso_a: Acesso, agendar: Agendar
) -> None:
    agendamento = agendar(tipo="carga")

    mensagens.preparar(sessao, agora=AGORA)

    assert _textos(sessao, acesso_a, agendamento)[0].startswith("Olá! Carga agendada:")


def test_agendamento_sem_celular_nao_ganha_mensagem(sessao: Session, agendar: Agendar) -> None:
    agendar(celular=None)

    assert mensagens.preparar(sessao, agora=AGORA) == 0
    assert _todas(sessao) == []


def test_preparar_de_novo_nao_repete(sessao: Session, agendar: Agendar) -> None:
    agendar()
    mensagens.preparar(sessao, agora=AGORA)

    assert mensagens.preparar(sessao, agora=AGORA + timedelta(seconds=1)) == 0
    assert len(_todas(sessao)) == 1


def test_preparar_de_novo_nao_refaz_o_que_ja_foi_feito(
    sessao: Session,
    monkeypatch: pytest.MonkeyPatch,
    agendar: Agendar,
    chegar: Chegar,
) -> None:
    chegar("ABC1D23", agendamento=agendar())
    mensagens.preparar(sessao, agora=AGORA)

    def nao_devia_montar_texto(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("montou o texto de uma mensagem que já existe")

    monkeypatch.setattr(mensagens.cadastro, "horario_do_site", nao_devia_montar_texto)
    monkeypatch.setattr(mensagens.patio, "posicao_na_fila", nao_devia_montar_texto)

    assert mensagens.preparar(sessao, agora=AGORA + timedelta(seconds=1)) == 0


def test_dois_workers_ao_mesmo_tempo_nao_repetem(
    sessao: Session, monkeypatch: pytest.MonkeyPatch, agendar: Agendar
) -> None:
    agendamento = agendar()
    horario_do_site = mensagens.cadastro.horario_do_site

    def o_outro_worker_grava_antes(*args: Any, **kwargs: Any) -> Any:
        # Entre olhar o que falta e gravar, o outro worker grava a mesma confirmação.
        _gravar(sessao, **_valores(agendamento))
        return horario_do_site(*args, **kwargs)

    monkeypatch.setattr(mensagens.cadastro, "horario_do_site", o_outro_worker_grava_antes)

    assert mensagens.preparar(sessao, agora=AGORA) == 0
    assert len(_todas(sessao)) == 1


def test_agendamento_cancelado_nao_ganha_confirmacao(
    sessao: Session, acesso_a: Acesso, agendar: Agendar
) -> None:
    agendamento = agendar()
    agendamentos.cancelar(sessao, acesso_a, agendamento.id, agora=AGORA)

    assert mensagens.preparar(sessao, agora=AGORA) == 0


def test_agendamento_que_ja_terminou_nao_ganha_confirmacao(
    sessao: Session, agendar: Agendar
) -> None:
    agendar("AG-1", inicio=AGORA - timedelta(hours=2))  # a janela termina agora
    falta_um_segundo = agendar("AG-2", inicio=AGORA - timedelta(hours=2, seconds=-1))

    mensagens.preparar(sessao, agora=AGORA)

    assert [m.agendamento_id for m in _todas(sessao)] == [falta_um_segundo.id]


def test_agendamento_mudado_ha_mais_de_um_dia_nao_e_olhado(
    sessao: Session, agendar: Agendar
) -> None:
    agendar("AG-1", inicio=AGORA + timedelta(days=3), agora=AGORA - mensagens.AGENDAMENTOS_OLHADOS)
    agendar(
        "AG-2",
        inicio=AGORA + timedelta(days=3),
        agora=AGORA - mensagens.AGENDAMENTOS_OLHADOS - timedelta(seconds=1),
    )

    assert mensagens.preparar(sessao, agora=AGORA) == 1


def test_celular_que_chega_depois_ganha_a_confirmacao(sessao: Session, agendar: Agendar) -> None:
    agendar(celular=None)
    mensagens.preparar(sessao, agora=AGORA)

    agendar(celular=CELULAR, agora=AGORA + timedelta(minutes=5))

    assert mensagens.preparar(sessao, agora=AGORA + timedelta(minutes=5)) == 1


def test_celular_novo_ganha_outra_confirmacao(
    sessao: Session, acesso_a: Acesso, agendar: Agendar
) -> None:
    agendamento = agendar()
    mensagens.preparar(sessao, agora=AGORA)

    agendar(celular=OUTRO_CELULAR, agora=AGORA + timedelta(minutes=5))
    mensagens.preparar(sessao, agora=AGORA + timedelta(minutes=5))

    conversa = mensagens.conversa(sessao, acesso_a, agendamento.id)
    assert [(m.modelo, m.para) for m in conversa] == [
        ("confirmacao", CELULAR), ("confirmacao", OUTRO_CELULAR),
    ]  # fmt: skip


def test_um_aviso_nao_conta_como_confirmacao(
    sessao: Session, acesso_a: Acesso, agendar: Agendar, chegar: Chegar
) -> None:
    # Mudado há mais de um dia: a confirmação não saiu, mas o aviso da chegada saiu.
    antigo = AGORA - mensagens.AGENDAMENTOS_OLHADOS - timedelta(hours=1)
    agendamento = agendar(inicio=AGORA + timedelta(hours=1), agora=antigo)
    chegar("ABC1D23", agendamento=agendamento)
    mensagens.preparar(sessao, agora=AGORA)

    agendar(inicio=AGORA + timedelta(hours=2))  # a janela mudou agora
    mensagens.preparar(sessao, agora=AGORA + timedelta(minutes=1))

    conversa = mensagens.conversa(sessao, acesso_a, agendamento.id)
    assert [m.modelo for m in conversa] == ["na_fila", "confirmacao"]


# --- Os avisos da visita ----------------------------------------------------------------------


def test_check_in_avisa_a_posicao_na_fila(
    sessao: Session,
    cenario: Demonstracao,
    acesso_a: Acesso,
    agendar: Agendar,
    chegar: Chegar,
    docas: list[Doca],
) -> None:
    chegar("BRA2E19", ha=timedelta(hours=1))  # na fila, na frente
    chegar("CCC3C33", ha=timedelta(minutes=30))  # na fila, na frente
    chamado = chegar("DDD4D44", ha=timedelta(hours=2))  # chamado: saiu da fila
    patio.chamar(sessao, acesso_a, chamado.id, docas[0].id, agora=AGORA)
    chegar("EEE5E55", ha=timedelta(hours=3), site_id=cenario.site_a2.id)  # outro site
    agendamento = agendar()
    chegar("ABC1D23", agendamento=agendamento)
    chegar("FFF6F66", ha=-timedelta(minutes=1))  # chegou depois

    mensagens.preparar(sessao, agora=AGORA)

    assert _textos(sessao, acesso_a, agendamento) == [
        CONFIRMACAO,
        "Chegada registrada às 14:00. Você está na fila, posição 3. "
        "Espere o aviso da doca por aqui.",
    ]


def test_quem_chegou_na_mesma_hora_fica_atras_de_quem_entrou_antes(
    sessao: Session, acesso_a: Acesso, agendar: Agendar, chegar: Chegar
) -> None:
    primeiro, segundo = agendar("AG-1", placa="ABC1D23"), agendar("AG-2", placa="BRA2E19")
    chegar("ABC1D23", agendamento=primeiro)
    chegar("BRA2E19", agendamento=segundo)

    mensagens.preparar(sessao, agora=AGORA)

    assert "posição 1." in _textos(sessao, acesso_a, primeiro)[1]
    assert "posição 2." in _textos(sessao, acesso_a, segundo)[1]


def test_na_excecao_resolvida_a_chegada_e_a_da_passagem(
    sessao: Session,
    cenario: Demonstracao,
    acesso_a: Acesso,
    agendar: Agendar,
    registrar_passagem: Callable[..., Passagem],
) -> None:
    agendamento = agendar()
    passagem = registrar_passagem(inicio=AGORA - timedelta(minutes=10))
    excecao = visitas.abrir_excecao(
        sessao, SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id),
        passagem_id=passagem.id, momento=AGORA - timedelta(minutes=10), agora=AGORA,
        motivo="sem_candidato", candidatos=(),
        composicao=(PlacaNaVisita(placa="ABC1D23", papel="cavalo", como="lida"),),
    )  # fmt: skip
    resolucao.ligar_ao_agendamento(sessao, acesso_a, excecao.id, agendamento.id, agora=AGORA)

    mensagens.preparar(sessao, agora=AGORA)

    assert _textos(sessao, acesso_a, agendamento)[1].startswith("Chegada registrada às 13:50.")


def test_chamada_e_fim_na_doca_avisam_o_motorista(
    sessao: Session, acesso_a: Acesso, agendar: Agendar, chegar: Chegar, docas: list[Doca]
) -> None:
    agendamento = agendar()
    visita = chegar("ABC1D23", agendamento=agendamento)
    patio.chamar(sessao, acesso_a, visita.id, docas[1].id, agora=AGORA)
    patio.iniciar(sessao, acesso_a, visita.id, agora=AGORA)
    patio.finalizar(sessao, acesso_a, visita.id, agora=AGORA)

    mensagens.preparar(sessao, agora=AGORA)

    conversa = mensagens.conversa(sessao, acesso_a, agendamento.id)
    assert [m.modelo for m in conversa] == ["confirmacao", "na_fila", "chamada", "pode_sair"]
    assert conversa[2].texto == "Sua vez! Siga para a Doca 2."
    assert conversa[3].texto == "Descarga terminada. Pode sair pela portaria. Boa viagem!"
    assert all(m.para == CELULAR for m in conversa)


def test_o_fim_da_carga_diz_carga(
    sessao: Session, acesso_a: Acesso, agendar: Agendar, chegar: Chegar, docas: list[Doca]
) -> None:
    agendamento = agendar(tipo="carga")
    visita = chegar("ABC1D23", agendamento=agendamento)
    patio.chamar(sessao, acesso_a, visita.id, docas[0].id, agora=AGORA)
    patio.iniciar(sessao, acesso_a, visita.id, agora=AGORA)
    patio.finalizar(sessao, acesso_a, visita.id, agora=AGORA)

    mensagens.preparar(sessao, agora=AGORA)

    assert _textos(sessao, acesso_a, agendamento)[-1].startswith("Carga terminada.")


def test_cada_evento_gera_uma_mensagem_so(
    sessao: Session, acesso_a: Acesso, agendar: Agendar, chegar: Chegar, docas: list[Doca]
) -> None:
    agendamento = agendar()
    visita = chegar("ABC1D23", agendamento=agendamento)
    patio.chamar(sessao, acesso_a, visita.id, docas[0].id, agora=AGORA)
    mensagens.preparar(sessao, agora=AGORA)
    patio.cancelar_chamada(sessao, acesso_a, visita.id, agora=AGORA)
    patio.chamar(sessao, acesso_a, visita.id, docas[1].id, agora=AGORA)

    mensagens.preparar(sessao, agora=AGORA + timedelta(seconds=1))
    mensagens.preparar(sessao, agora=AGORA + timedelta(seconds=2))

    assert _textos(sessao, acesso_a, agendamento)[2:] == [
        "Sua vez! Siga para a Doca 1.",
        "Sua vez! Siga para a Doca 2.",
    ]


def test_aviso_velho_nao_sai(
    sessao: Session, acesso_a: Acesso, agendar: Agendar, chegar: Chegar
) -> None:
    no_limite, velho = agendar("AG-1", placa="ABC1D23"), agendar("AG-2", placa="BRA2E19")
    chegar("ABC1D23", agendamento=no_limite, ha=mensagens.AVISOS_OLHADOS)
    chegar("BRA2E19", agendamento=velho, ha=mensagens.AVISOS_OLHADOS + timedelta(seconds=1))

    mensagens.preparar(sessao, agora=AGORA)

    assert [m.modelo for m in mensagens.conversa(sessao, acesso_a, no_limite.id)] == [
        "confirmacao", "na_fila",
    ]  # fmt: skip
    assert [m.modelo for m in mensagens.conversa(sessao, acesso_a, velho.id)] == ["confirmacao"]


def test_visita_sem_agendamento_nao_avisa(sessao: Session, chegar: Chegar) -> None:
    chegar("ABC1D23")

    assert mensagens.preparar(sessao, agora=AGORA) == 0


def test_visita_de_agendamento_sem_celular_nao_avisa(
    sessao: Session, agendar: Agendar, chegar: Chegar
) -> None:
    chegar("ABC1D23", agendamento=agendar(celular=None))

    assert mensagens.preparar(sessao, agora=AGORA) == 0


def test_o_aviso_vai_para_o_celular_de_agora(
    sessao: Session, acesso_a: Acesso, agendar: Agendar, chegar: Chegar
) -> None:
    agendamento = agendar()
    chegar("ABC1D23", agendamento=agendamento)
    agendar(celular=OUTRO_CELULAR)

    mensagens.preparar(sessao, agora=AGORA)

    conversa = mensagens.conversa(sessao, acesso_a, agendamento.id)
    assert {m.para for m in conversa} == {OUTRO_CELULAR}


# --- Ler --------------------------------------------------------------------------------------


def test_conversa_de_outra_empresa_responde_nao_encontrado(
    sessao: Session, acesso_b: Acesso, agendar: Agendar
) -> None:
    agendamento = agendar()
    mensagens.preparar(sessao, agora=AGORA)

    with pytest.raises(NaoEncontradoError):
        mensagens.conversa(sessao, acesso_b, agendamento.id)


def test_conversas_do_site_pela_ultima_mensagem(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, agendar: Agendar, chegar: Chegar
) -> None:
    antes = AGORA - timedelta(minutes=10)
    primeiro = agendar("AG-1", placa="ABC1D23", agora=antes)
    mensagens.preparar(sessao, agora=antes)
    segundo = agendar("AG-2", placa="BRA2E19")
    mensagens.preparar(sessao, agora=AGORA)
    chegar("ABC1D23", agendamento=primeiro, ha=-timedelta(minutes=1))
    mensagens.preparar(sessao, agora=AGORA + timedelta(minutes=1))

    conversas = mensagens.conversas(sessao, acesso_a, cenario.site_a.id)

    assert [(c.agendamento_id, c.quantas, c.ultima.modelo) for c in conversas] == [
        (primeiro.id, 2, "na_fila"), (segundo.id, 1, "confirmacao"),
    ]  # fmt: skip
    assert len(mensagens.conversas(sessao, acesso_a, cenario.site_a.id, limite=1)) == 1


def test_conversas_so_do_site_pedido(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, agendar: Agendar
) -> None:
    agendar("AG-1")
    agendar("AG-9", site_id=cenario.site_a2.id)  # mesma empresa, outro site
    mensagens.preparar(sessao, agora=AGORA)

    conversas = mensagens.conversas(sessao, acesso_a, cenario.site_a.id)

    assert [c.ultima.site_id for c in conversas] == [cenario.site_a.id]


def test_conversas_de_site_de_outra_empresa_responde_nao_encontrado(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    with pytest.raises(NaoEncontradoError):
        mensagens.conversas(sessao, acesso_a, cenario.site_b.id)


def test_eventos_recentes_so_das_visitas_com_agendamento(
    sessao: Session, agendar: Agendar, chegar: Chegar
) -> None:
    com_agendamento = chegar("ABC1D23", agendamento=agendar())
    chegar("BRA2E19")

    recentes = visitas.eventos_recentes(sessao, ("check_in", "aceita_sem_agendamento"), desde=AGORA)

    assert [(e.tipo, v.id) for e, v in recentes] == [("check_in", com_agendamento.id)]


# --- O worker ---------------------------------------------------------------------------------


def test_o_laco_do_worker_prepara_as_mensagens(sessao: Session, agendar: Agendar) -> None:
    agendar()
    parar = threading.Event()

    def dormir(_segundos: float) -> None:
        parar.set()

    fila.rodar(lambda: sessao, parar, relogio=lambda: AGORA, dormir=dormir)

    assert [m.modelo for m in _todas(sessao)] == ["confirmacao"]


# --- O banco confere --------------------------------------------------------------------------


def _gravar(sessao: Session, **valores: Any) -> None:
    sessao.execute(insert(Mensagem).values(**valores))


def _valores(agendamento: Agendamento, **mudancas: Any) -> dict[str, Any]:
    return {
        "empresa_id": agendamento.empresa_id,
        "site_id": agendamento.site_id,
        "agendamento_id": agendamento.id,
        "evento_id": None,
        "modelo": "confirmacao",
        "canal": "demonstracao",
        "para": CELULAR,
        "texto": "oi",
        "situacao": "guardada",
        "criada_em": AGORA,
    } | mudancas


def test_banco_recusa_mensagem_com_agendamento_de_outra_empresa(
    sessao: Session, cenario: Demonstracao, agendar: Agendar
) -> None:
    agendamento = agendar()

    with pytest.raises(DBAPIError) as erro:
        _gravar(
            sessao,
            **_valores(agendamento, empresa_id=cenario.empresa_b.id, site_id=cenario.site_b.id),
        )

    assert sqlstate(erro.value) == SQLSTATE_CHAVE_ESTRANGEIRA


def test_banco_recusa_segunda_confirmacao_para_o_mesmo_celular(
    sessao: Session, agendar: Agendar
) -> None:
    agendamento = agendar()
    _gravar(sessao, **_valores(agendamento))

    with pytest.raises(DBAPIError) as erro:
        _gravar(sessao, **_valores(agendamento))

    assert sqlstate(erro.value) == SQLSTATE_UNICIDADE


def test_banco_recusa_aviso_sem_evento(sessao: Session, agendar: Agendar) -> None:
    agendamento = agendar()

    with pytest.raises(DBAPIError) as erro:
        _gravar(sessao, **_valores(agendamento, modelo="na_fila"))

    assert sqlstate(erro.value) == SQLSTATE_CHECK


def test_banco_recusa_celular_fora_do_formato(sessao: Session, agendar: Agendar) -> None:
    agendamento = agendar()

    with pytest.raises(DBAPIError) as erro:
        _gravar(sessao, **_valores(agendamento, para="11987654321"))

    assert sqlstate(erro.value) == SQLSTATE_CHECK


def test_banco_recusa_dois_avisos_do_mesmo_evento(
    sessao: Session, acesso_a: Acesso, agendar: Agendar, chegar: Chegar
) -> None:
    agendamento = agendar()
    visita = chegar("ABC1D23", agendamento=agendamento)
    [evento] = visitas.eventos_da_visita(sessao, acesso_a, visita.id)
    aviso = _valores(agendamento, modelo="na_fila", evento_id=evento.id)
    _gravar(sessao, **aviso)

    with pytest.raises(DBAPIError) as erro:
        _gravar(sessao, **aviso)

    assert sqlstate(erro.value) == SQLSTATE_UNICIDADE

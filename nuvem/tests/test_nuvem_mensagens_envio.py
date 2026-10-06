"""O envio das mensagens ao motorista (SDD 7.5, D-58 e D-63): o canal de cada uma, a fila, as
situações que a Meta avisa, a autorização do motorista e o "SAIR". A Meta é imitada."""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem import tarefas_de_fundo as fila
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.modelos import Agendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.mensagens import servico as mensagens
from nuvem.mensagens.canais import Canais, Envio, EnvioFalhouError, EnvioRecusadoError
from nuvem.mensagens.modelos import AutorizacaoWhatsApp, Mensagem, MensagemRecebida
from nuvem.portaria import visitas
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
JANELA = datetime(2026, 10, 5, 16, 0, tzinfo=UTC)
CELULAR = "+5511987654321"
WA_ID = "5511987654321"


@dataclass
class WhatsAppImitado:
    """O canal do WhatsApp sem a Meta: guarda o que mandaria, ou falha como pedido."""

    numero: str = "5511900000000"
    enviadas: list[Mensagem] = field(default_factory=list)
    respostas: list[tuple[str, str]] = field(default_factory=list)
    falhar_com: Exception | None = None

    def enviar(self, mensagem: Mensagem) -> Envio:
        if self.falhar_com is not None:
            raise self.falhar_com
        self.enviadas.append(mensagem)
        return Envio(id_no_canal=f"wamid.{mensagem.id}")

    def responder(self, para: str, texto: str) -> Envio:
        if self.falhar_com is not None:
            raise self.falhar_com
        self.respostas.append((para, texto))
        return Envio(id_no_canal=f"wamid.resposta.{len(self.respostas)}")


@pytest.fixture
def whatsapp() -> WhatsAppImitado:
    return WhatsAppImitado()


@pytest.fixture
def canais(whatsapp: WhatsAppImitado) -> Canais:
    return Canais(whatsapp=whatsapp)


@pytest.fixture
def agendar(sessao: Session, cenario: Demonstracao) -> Callable[..., Agendamento]:
    def _agendar(codigo: str = "AG-1", celular: str = CELULAR, empresa: str = "a") -> Agendamento:
        site = cenario.site_a if empresa == "a" else cenario.site_b
        destino = SiteDoAgendamento(empresa_id=site.empresa_id, site_id=site.id, usuario_id=None)
        dados = DadosDoAgendamento.model_validate(
            {
                "codigo_externo": codigo,
                "janela_inicio": JANELA,
                "janela_fim": JANELA + timedelta(hours=2),
                "tipo": "descarga",
                "placa_cavalo": "ABC1D23",
                "motorista_celular": celular,
            }
        )
        return agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento

    return _agendar


def _autorizar(sessao: Session, empresa_id: int, celular: str = CELULAR) -> None:
    sessao.add(
        AutorizacaoWhatsApp(
            empresa_id=empresa_id,
            celular=celular,
            autorizada_em=AGORA - timedelta(days=1),
            texto="AVISOS A1",
            id_no_whatsapp=f"wamid.autorizou.{empresa_id}.{celular}",
        )
    )
    sessao.flush()


def _mensagens(sessao: Session) -> list[Mensagem]:
    return list(sessao.scalars(select(Mensagem).order_by(Mensagem.id)))


def _tarefas(sessao: Session, tipo: str) -> list[fila.TarefaDeFundo]:
    return list(sessao.scalars(select(fila.TarefaDeFundo).where(fila.TarefaDeFundo.tipo == tipo)))


def _aviso(**valor: Any) -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": valor}]}],
    }


def _recebida(texto: str, *, de: str = WA_ID, id_: str = "wamid.R1") -> dict[str, Any]:
    return _aviso(
        messages=[
            {
                "from": de,
                "id": id_,
                "timestamp": str(int(AGORA.timestamp())),
                "type": "text",
                "text": {"body": texto},
            }
        ]
    )


def _situacao(id_: str, situacao: str, segundos: int = 0, **mais: Any) -> dict[str, Any]:
    return _aviso(
        statuses=[
            {
                "id": id_,
                "status": situacao,
                "timestamp": str(int((AGORA + timedelta(seconds=segundos)).timestamp())),
                **mais,
            }
        ]
    )


# --- O canal de cada mensagem --------------------------------------------------------------


def test_sem_whatsapp_configurado_tudo_fica_no_canal_de_demonstracao(
    sessao: Session, agendar: Callable[..., Agendamento]
) -> None:
    agendar()

    mensagens.preparar(sessao, agora=AGORA)

    assert [(m.canal, m.situacao) for m in _mensagens(sessao)] == [("demonstracao", "guardada")]
    assert _tarefas(sessao, "enviar_mensagem") == []


def test_celular_sem_autorizacao_recebe_por_sms(
    sessao: Session, agendar: Callable[..., Agendamento], canais: Canais
) -> None:
    agendar()

    mensagens.preparar(sessao, agora=AGORA, canais=canais)

    assert [(m.canal, m.situacao) for m in _mensagens(sessao)] == [("sms", "guardada")]
    # Sem o SMS configurado (a T53), a mensagem espera: não vira tarefa.
    assert _tarefas(sessao, "enviar_mensagem") == []


def test_celular_que_autorizou_a_empresa_recebe_pelo_whatsapp_e_vira_tarefa(
    sessao: Session, cenario: Demonstracao, agendar: Callable[..., Agendamento], canais: Canais
) -> None:
    agendar()
    _autorizar(sessao, cenario.empresa_a.id)

    mensagens.preparar(sessao, agora=AGORA, canais=canais)

    (mensagem,) = _mensagens(sessao)
    assert mensagem.canal == "whatsapp"
    assert mensagem.variaveis == ["Descarga", "CD Exemplo", "05/10", "13:00", "15:00", "AG-1"]
    (tarefa,) = _tarefas(sessao, "enviar_mensagem")
    assert (tarefa.chave, tarefa.dados) == (str(mensagem.id), {"mensagem_id": mensagem.id})


def test_a_autorizacao_de_outra_empresa_nao_vale(
    sessao: Session, cenario: Demonstracao, agendar: Callable[..., Agendamento], canais: Canais
) -> None:
    agendar()
    _autorizar(sessao, cenario.empresa_b.id)

    mensagens.preparar(sessao, agora=AGORA, canais=canais)

    assert [m.canal for m in _mensagens(sessao)] == ["sms"]


def test_a_autorizacao_revogada_nao_vale(
    sessao: Session, cenario: Demonstracao, agendar: Callable[..., Agendamento], canais: Canais
) -> None:
    agendar()
    _autorizar(sessao, cenario.empresa_a.id)
    for autorizacao in sessao.scalars(select(AutorizacaoWhatsApp)):
        autorizacao.revogada_em = AGORA - timedelta(hours=1)
    sessao.flush()

    mensagens.preparar(sessao, agora=AGORA, canais=canais)

    assert [m.canal for m in _mensagens(sessao)] == ["sms"]


# --- O envio -------------------------------------------------------------------------------


def _uma_pelo_whatsapp(
    sessao: Session, cenario: Demonstracao, agendar: Callable[..., Agendamento], canais: Canais
) -> Mensagem:
    agendar()
    _autorizar(sessao, cenario.empresa_a.id)
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    (mensagem,) = _mensagens(sessao)
    return mensagem


def test_enviar_marca_a_mensagem_como_enviada_com_o_id_da_meta(
    sessao: Session,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    canais: Canais,
    whatsapp: WhatsAppImitado,
) -> None:
    mensagem = _uma_pelo_whatsapp(sessao, cenario, agendar, canais)

    mensagens.enviar(sessao, canais, mensagem.id, agora=AGORA)

    assert (mensagem.situacao, mensagem.id_no_canal, mensagem.enviada_em) == (
        "enviada",
        f"wamid.{mensagem.id}",
        AGORA,
    )
    assert whatsapp.enviadas == [mensagem]


def test_enviar_de_novo_nao_manda_duas_vezes(
    sessao: Session,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    canais: Canais,
    whatsapp: WhatsAppImitado,
) -> None:
    mensagem = _uma_pelo_whatsapp(sessao, cenario, agendar, canais)

    mensagens.enviar(sessao, canais, mensagem.id, agora=AGORA)
    mensagens.enviar(sessao, canais, mensagem.id, agora=AGORA)

    assert len(whatsapp.enviadas) == 1


def test_recusa_definitiva_marca_falhou_com_o_codigo_e_nao_tenta_de_novo(
    sessao: Session,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    canais: Canais,
    whatsapp: WhatsAppImitado,
) -> None:
    mensagem = _uma_pelo_whatsapp(sessao, cenario, agendar, canais)
    whatsapp.falhar_com = EnvioRecusadoError("131026", "Message undeliverable")

    fila.executar_pendentes(sessao, agora=AGORA, contexto=fila.Contexto(canais=canais))

    assert (mensagem.situacao, mensagem.erro, mensagem.falhou_em) == (
        "falhou",
        "131026: Message undeliverable",
        AGORA,
    )
    (tarefa,) = _tarefas(sessao, "enviar_mensagem")
    assert tarefa.situacao == "feita"


def test_falha_passageira_volta_para_a_fila(
    sessao: Session,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    canais: Canais,
    whatsapp: WhatsAppImitado,
) -> None:
    mensagem = _uma_pelo_whatsapp(sessao, cenario, agendar, canais)
    whatsapp.falhar_com = EnvioFalhouError("a rede caiu")

    fila.executar_pendentes(sessao, agora=AGORA, contexto=fila.Contexto(canais=canais))

    assert mensagem.situacao == "guardada"
    (tarefa,) = _tarefas(sessao, "enviar_mensagem")
    assert (tarefa.situacao, tarefa.tentativas) == ("pendente", 1)


def test_o_laco_do_worker_prepara_e_envia(
    sessao: Session,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    canais: Canais,
    whatsapp: WhatsAppImitado,
) -> None:
    agendar()
    _autorizar(sessao, cenario.empresa_a.id)
    parar = threading.Event()
    voltas = []

    def dormir(_segundos: float) -> None:
        voltas.append(1)
        if len(voltas) == 2:
            parar.set()

    fila.rodar(lambda: sessao, parar, relogio=lambda: AGORA, dormir=dormir, canais=canais)

    assert [m.situacao for m in _mensagens(sessao)] == ["enviada"]
    assert len(whatsapp.enviadas) == 1


# --- As situações que a Meta avisa ---------------------------------------------------------


def test_a_meta_avisa_entregue_e_lida(
    sessao: Session, cenario: Demonstracao, agendar: Callable[..., Agendamento], canais: Canais
) -> None:
    mensagem = _uma_pelo_whatsapp(sessao, cenario, agendar, canais)
    mensagens.enviar(sessao, canais, mensagem.id, agora=AGORA)
    id_ = mensagem.id_no_canal or ""

    mensagens.tratar_aviso(
        sessao,
        canais,
        _situacao(id_, "delivered", 5, pricing={"billable": True, "category": "utility"}),
        agora=AGORA,
    )
    mensagens.tratar_aviso(sessao, canais, _situacao(id_, "read", 60), agora=AGORA)

    assert mensagem.situacao == "lida"
    assert mensagem.entregue_em == AGORA + timedelta(seconds=5)
    assert mensagem.lida_em == AGORA + timedelta(seconds=60)
    assert mensagem.cobranca == "utility"


def test_aviso_fora_de_ordem_nao_volta_a_situacao(
    sessao: Session, cenario: Demonstracao, agendar: Callable[..., Agendamento], canais: Canais
) -> None:
    mensagem = _uma_pelo_whatsapp(sessao, cenario, agendar, canais)
    mensagens.enviar(sessao, canais, mensagem.id, agora=AGORA)
    id_ = mensagem.id_no_canal or ""

    mensagens.tratar_aviso(sessao, canais, _situacao(id_, "read", 60), agora=AGORA)
    mensagens.tratar_aviso(sessao, canais, _situacao(id_, "delivered", 5), agora=AGORA)
    mensagens.tratar_aviso(sessao, canais, _situacao(id_, "sent", 1), agora=AGORA)

    assert mensagem.situacao == "lida"
    assert mensagem.entregue_em == AGORA + timedelta(seconds=5)


def test_a_meta_avisa_que_falhou(
    sessao: Session, cenario: Demonstracao, agendar: Callable[..., Agendamento], canais: Canais
) -> None:
    mensagem = _uma_pelo_whatsapp(sessao, cenario, agendar, canais)
    mensagens.enviar(sessao, canais, mensagem.id, agora=AGORA)

    mensagens.tratar_aviso(
        sessao,
        canais,
        _situacao(
            mensagem.id_no_canal or "",
            "failed",
            3,
            errors=[{"code": 131026, "title": "Message undeliverable"}],
        ),
        agora=AGORA,
    )

    assert (mensagem.situacao, mensagem.erro) == ("falhou", "131026: Message undeliverable")
    assert mensagem.falhou_em == AGORA + timedelta(seconds=3)


def test_falha_avisada_depois_de_entregue_nao_volta_a_situacao(
    sessao: Session, cenario: Demonstracao, agendar: Callable[..., Agendamento], canais: Canais
) -> None:
    mensagem = _uma_pelo_whatsapp(sessao, cenario, agendar, canais)
    mensagens.enviar(sessao, canais, mensagem.id, agora=AGORA)
    id_ = mensagem.id_no_canal or ""

    mensagens.tratar_aviso(sessao, canais, _situacao(id_, "delivered", 5), agora=AGORA)
    mensagens.tratar_aviso(
        sessao,
        canais,
        _situacao(id_, "failed", 9, errors=[{"code": 131000, "title": "x"}]),
        agora=AGORA,
    )

    assert (mensagem.situacao, mensagem.erro) == ("entregue", None)


def test_aviso_de_mensagem_que_nao_conhecemos_e_ignorado(
    sessao: Session, canais: Canais, cenario: Demonstracao
) -> None:
    mensagens.tratar_aviso(sessao, canais, _situacao("wamid.NINGUEM", "read"), agora=AGORA)

    assert _mensagens(sessao) == []


# --- A autorização e o "SAIR" --------------------------------------------------------------


def _autorizacoes(sessao: Session) -> list[AutorizacaoWhatsApp]:
    return list(sessao.scalars(select(AutorizacaoWhatsApp).order_by(AutorizacaoWhatsApp.id)))


def _recebidas(sessao: Session) -> list[MensagemRecebida]:
    return list(sessao.scalars(select(MensagemRecebida).order_by(MensagemRecebida.id)))


def test_avisos_do_agendamento_autoriza_a_empresa_dele_e_responde(
    sessao: Session,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    canais: Canais,
    whatsapp: WhatsAppImitado,
) -> None:
    agendamento = agendar()

    mensagens.tratar_aviso(sessao, canais, _recebida(f"AVISOS A{agendamento.id}"), agora=AGORA)

    (autorizacao,) = _autorizacoes(sessao)
    assert (autorizacao.empresa_id, autorizacao.celular, autorizacao.texto) == (
        cenario.empresa_a.id,
        CELULAR,
        f"AVISOS A{agendamento.id}",
    )
    assert autorizacao.autorizada_em == AGORA
    (recebida,) = _recebidas(sessao)
    assert (recebida.resultado, recebida.empresa_id, recebida.de) == (
        "autorizou",
        cenario.empresa_a.id,
        WA_ID,
    )
    (resposta,) = whatsapp.respostas
    assert resposta[0] == CELULAR
    assert "SAIR" in resposta[1]


def test_avisos_do_site_autoriza_a_empresa_do_site(
    sessao: Session, cenario: Demonstracao, canais: Canais
) -> None:
    mensagens.tratar_aviso(sessao, canais, _recebida(f"AVISOS S{cenario.site_b.id}"), agora=AGORA)

    assert [a.empresa_id for a in _autorizacoes(sessao)] == [cenario.empresa_b.id]


def test_o_celular_sem_o_9_do_whatsapp_vira_o_do_agendamento(
    sessao: Session,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    canais: Canais,
) -> None:
    agendamento = agendar()

    mensagens.tratar_aviso(
        sessao, canais, _recebida(f"AVISOS A{agendamento.id}", de="551187654321"), agora=AGORA
    )
    mensagens.preparar(sessao, agora=AGORA, canais=canais)

    assert [a.celular for a in _autorizacoes(sessao)] == [CELULAR]
    assert [m.canal for m in _mensagens(sessao)] == ["whatsapp"]


def test_autorizar_de_novo_nao_duplica(
    sessao: Session, agendar: Callable[..., Agendamento], canais: Canais
) -> None:
    agendamento = agendar()

    for numero in range(2):
        aviso = _recebida(f"AVISOS A{agendamento.id}", id_=f"wamid.R{numero}")
        mensagens.tratar_aviso(sessao, canais, aviso, agora=AGORA)

    assert len(_autorizacoes(sessao)) == 1
    assert len(_recebidas(sessao)) == 2


def test_o_mesmo_aviso_duas_vezes_nao_responde_duas_vezes(
    sessao: Session,
    agendar: Callable[..., Agendamento],
    canais: Canais,
    whatsapp: WhatsAppImitado,
) -> None:
    agendamento = agendar()
    aviso = _recebida(f"AVISOS A{agendamento.id}")

    mensagens.tratar_aviso(sessao, canais, aviso, agora=AGORA)
    mensagens.tratar_aviso(sessao, canais, aviso, agora=AGORA)

    assert len(_recebidas(sessao)) == 1
    assert len(whatsapp.respostas) == 1


def test_sair_cancela_a_autorizacao_em_todas_as_empresas(
    sessao: Session,
    cenario: Demonstracao,
    canais: Canais,
    whatsapp: WhatsAppImitado,
) -> None:
    _autorizar(sessao, cenario.empresa_a.id)
    _autorizar(sessao, cenario.empresa_b.id)
    _autorizar(sessao, cenario.empresa_a.id, celular="+5521987650000")  # outro número

    mensagens.tratar_aviso(sessao, canais, _recebida("Sair"), agora=AGORA)

    revogadas = [(a.celular, a.revogada_em) for a in _autorizacoes(sessao)]
    assert revogadas == [
        (CELULAR, AGORA),
        (CELULAR, AGORA),
        ("+5521987650000", None),
    ]
    assert _recebidas(sessao)[0].resultado == "saiu"
    assert len(whatsapp.respostas) == 1


def test_depois_de_sair_a_mensagem_vai_por_sms(
    sessao: Session,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    canais: Canais,
) -> None:
    _autorizar(sessao, cenario.empresa_a.id)
    mensagens.tratar_aviso(sessao, canais, _recebida("SAIR"), agora=AGORA)
    agendar()

    mensagens.preparar(sessao, agora=AGORA, canais=canais)

    assert [m.canal for m in _mensagens(sessao)] == ["sms"]


@pytest.mark.parametrize("texto", ["oi", "AVISOS A999999", "AVISOS S999999", ""])
def test_o_resto_e_ignorado_sem_resposta(
    sessao: Session,
    cenario: Demonstracao,
    canais: Canais,
    whatsapp: WhatsAppImitado,
    texto: str,
) -> None:
    mensagens.tratar_aviso(sessao, canais, _recebida(texto), agora=AGORA)

    assert _autorizacoes(sessao) == []
    assert [r.resultado for r in _recebidas(sessao)] == ["ignorada"]
    assert whatsapp.respostas == []


def test_numero_de_fora_do_brasil_e_ignorado(
    sessao: Session, agendar: Callable[..., Agendamento], canais: Canais
) -> None:
    agendamento = agendar()

    mensagens.tratar_aviso(
        sessao, canais, _recebida(f"AVISOS A{agendamento.id}", de="14155550123"), agora=AGORA
    )

    assert _autorizacoes(sessao) == []
    assert [r.resultado for r in _recebidas(sessao)] == ["ignorada"]


def test_resposta_que_falha_nao_desfaz_a_autorizacao(
    sessao: Session,
    agendar: Callable[..., Agendamento],
    canais: Canais,
    whatsapp: WhatsAppImitado,
) -> None:
    # A resposta é cortesia: repetir o aviso inteiro mandaria outra resposta a quem recebeu.
    agendamento = agendar()
    whatsapp.falhar_com = EnvioFalhouError("a rede caiu")

    mensagens.tratar_aviso(sessao, canais, _recebida(f"AVISOS A{agendamento.id}"), agora=AGORA)

    assert len(_autorizacoes(sessao)) == 1


def test_o_aviso_pela_fila_trata_tudo(
    sessao: Session,
    agendar: Callable[..., Agendamento],
    canais: Canais,
) -> None:
    agendamento = agendar()
    fila.enfileirar(
        sessao,
        "aviso_do_whatsapp",
        {"aviso": _recebida(f"AVISOS A{agendamento.id}")},
        chave="resumo-do-corpo",
        agora=AGORA,
    )

    fila.executar_pendentes(sessao, agora=AGORA, contexto=fila.Contexto(canais=canais))

    assert len(_autorizacoes(sessao)) == 1
    assert [t.situacao for t in _tarefas(sessao, "aviso_do_whatsapp")] == ["feita"]


# --- O aviso ao motorista, com a autorização -----------------------------------------------


def test_depois_de_autorizar_o_aviso_da_fila_vai_pelo_whatsapp(
    sessao: Session,
    cenario: Demonstracao,
    agendar: Callable[..., Agendamento],
    canais: Canais,
) -> None:
    agendamento = agendar()
    mensagens.preparar(sessao, agora=AGORA, canais=canais)  # a confirmação: SMS
    mensagens.tratar_aviso(sessao, canais, _recebida(f"AVISOS A{agendamento.id}"), agora=AGORA)
    visitas.abrir_visita(
        sessao,
        SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id),
        "check_in",
        momento=AGORA,
        agora=AGORA,
        agendamento_id=agendamento.id,
        composicao=(PlacaNaVisita(placa="ABC1D23", papel="cavalo", como="lida"),),
    )

    mensagens.preparar(sessao, agora=AGORA, canais=canais)

    assert [(m.modelo, m.canal) for m in _mensagens(sessao)] == [
        ("confirmacao", "sms"),
        ("na_fila", "whatsapp"),
    ]


def test_o_celular_novo_do_agendamento_nao_herda_a_autorizacao(
    sessao: Session, cenario: Demonstracao, agendar: Callable[..., Agendamento], canais: Canais
) -> None:
    # A autorização é do número (SDD 3.4): o celular novo ainda não autorizou nada.
    _autorizar(sessao, cenario.empresa_a.id)
    agendar(celular="+5521987650000")

    mensagens.preparar(sessao, agora=AGORA, canais=canais)

    assert [(m.para, m.canal) for m in _mensagens(sessao)] == [("+5521987650000", "sms")]

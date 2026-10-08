"""O SMS de reserva e o motorista não avisado (SDD 7.5, D-58 e D-64), com o banco: a Meta e a
Zenvia imitadas."""

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
from nuvem.cadastro.acesso import Acesso
from nuvem.mensagens import servico as mensagens
from nuvem.mensagens.canais import Canais, Envio, EnvioRecusadoError
from nuvem.mensagens.modelos import AutorizacaoWhatsApp, Mensagem
from nuvem.portaria import visitas
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
JANELA = datetime(2026, 10, 5, 16, 0, tzinfo=UTC)
CELULAR = "+5511987654321"


@dataclass
class CanalImitado:
    """Um canal sem o fornecedor: guarda o que mandaria, ou recusa como pedido."""

    numero: str = "5511900000000"
    prefixo: str = "id"
    enviadas: list[Mensagem] = field(default_factory=list)
    recusar: bool = False

    def enviar(self, mensagem: Mensagem) -> Envio:
        if self.recusar:
            raise EnvioRecusadoError("131026", "Message undeliverable")
        self.enviadas.append(mensagem)
        return Envio(id_no_canal=f"{self.prefixo}.{mensagem.id}")

    def responder(self, para: str, texto: str) -> Envio:
        return Envio(id_no_canal="resposta")


@pytest.fixture
def whatsapp() -> CanalImitado:
    return CanalImitado(prefixo="wamid")


@pytest.fixture
def zenvia() -> CanalImitado:
    return CanalImitado(prefixo="zenvia")


@pytest.fixture
def canais(whatsapp: CanalImitado, zenvia: CanalImitado) -> Canais:
    return Canais(whatsapp=whatsapp, sms=zenvia)


@pytest.fixture
def agendamento(sessao: Session, cenario: Demonstracao) -> Agendamento:
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
    return agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento


def _autorizar(sessao: Session, empresa_id: int) -> None:
    sessao.add(
        AutorizacaoWhatsApp(
            empresa_id=empresa_id,
            celular=CELULAR,
            autorizada_em=AGORA - timedelta(days=1),
            texto="AVISOS A1",
            id_no_whatsapp="wamid.autorizou",
        )
    )
    sessao.flush()


def _mensagens(sessao: Session) -> list[Mensagem]:
    return list(sessao.scalars(select(Mensagem).order_by(Mensagem.id)))


def _enviar_tudo(sessao: Session, canais: Canais, agora: datetime = AGORA) -> None:
    fila.executar_pendentes(sessao, agora=agora, contexto=fila.Contexto(canais=canais))


def _chegar(sessao: Session, cenario: Demonstracao, agendamento: Agendamento) -> None:
    visitas.abrir_visita(
        sessao,
        SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id),
        "check_in",
        momento=AGORA,
        agora=AGORA,
        agendamento_id=agendamento.id,
        composicao=(PlacaNaVisita(placa="ABC1D23", papel="cavalo", como="lida"),),
    )


# --- O SMS ----------------------------------------------------------------------------------


def test_a_confirmacao_por_sms_leva_o_link_do_whatsapp_e_sai(
    sessao: Session, agendamento: Agendamento, canais: Canais, zenvia: CanalImitado
) -> None:
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)

    (mensagem,) = _mensagens(sessao)
    assert mensagem.canal == "sms"
    assert mensagem.texto.endswith(f"https://wa.me/5511900000000?text=AVISOS%20A{agendamento.id}")
    assert (mensagem.situacao, mensagem.id_no_canal) == ("enviada", f"zenvia.{mensagem.id}")
    assert zenvia.enviadas == [mensagem]


def test_so_com_o_sms_configurado_tudo_vai_por_sms_sem_link(
    sessao: Session, agendamento: Agendamento, zenvia: CanalImitado
) -> None:
    canais = Canais(sms=zenvia)

    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)

    (mensagem,) = _mensagens(sessao)
    assert (mensagem.canal, mensagem.situacao) == ("sms", "enviada")
    assert "wa.me" not in mensagem.texto


def test_so_com_o_sms_quem_autorizou_tambem_recebe_por_sms(
    sessao: Session, cenario: Demonstracao, agendamento: Agendamento, zenvia: CanalImitado
) -> None:
    _autorizar(sessao, cenario.empresa_a.id)

    mensagens.preparar(sessao, agora=AGORA, canais=Canais(sms=zenvia))

    assert [m.canal for m in _mensagens(sessao)] == ["sms"]


def test_quem_autorizou_recebe_o_texto_do_whatsapp_com_acento(
    sessao: Session,
    cenario: Demonstracao,
    agendamento: Agendamento,
    canais: Canais,
) -> None:
    _autorizar(sessao, cenario.empresa_a.id)

    mensagens.preparar(sessao, agora=AGORA, canais=canais)

    (mensagem,) = _mensagens(sessao)
    assert mensagem.canal == "whatsapp"
    assert mensagem.texto.startswith("Olá!")


# --- A reserva pelo SMS ---------------------------------------------------------------------


def test_o_whatsapp_recusado_ganha_a_copia_pelo_sms(
    sessao: Session,
    cenario: Demonstracao,
    agendamento: Agendamento,
    canais: Canais,
    whatsapp: CanalImitado,
    zenvia: CanalImitado,
) -> None:
    _autorizar(sessao, cenario.empresa_a.id)
    whatsapp.recusar = True

    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)

    pelo_whatsapp, pelo_sms = _mensagens(sessao)
    assert (pelo_whatsapp.canal, pelo_whatsapp.situacao) == ("whatsapp", "falhou")
    assert (pelo_sms.canal, pelo_sms.situacao, pelo_sms.modelo) == ("sms", "enviada", "confirmacao")
    assert pelo_sms.texto.startswith("patio-br:")
    assert zenvia.enviadas == [pelo_sms]


def test_a_meta_avisa_que_falhou_e_a_copia_sai_pelo_sms(
    sessao: Session,
    cenario: Demonstracao,
    agendamento: Agendamento,
    canais: Canais,
    zenvia: CanalImitado,
) -> None:
    _autorizar(sessao, cenario.empresa_a.id)
    _chegar(sessao, cenario, agendamento)
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)
    aviso = next(m for m in _mensagens(sessao) if m.modelo == "na_fila")

    mensagens.tratar_aviso(
        sessao,
        canais,
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "statuses": [
                                    {
                                        "id": aviso.id_no_canal,
                                        "status": "failed",
                                        "timestamp": str(int(AGORA.timestamp()) + 5),
                                        "errors": [{"code": 131026, "title": "x"}],
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        },
        agora=AGORA,
    )
    _enviar_tudo(sessao, canais)

    copias = [m for m in _mensagens(sessao) if m.modelo == "na_fila" and m.canal == "sms"]
    assert [(c.evento_id, c.situacao) for c in copias] == [(aviso.evento_id, "enviada")]


def test_sem_sms_configurado_nao_ha_reserva(
    sessao: Session,
    cenario: Demonstracao,
    agendamento: Agendamento,
    whatsapp: CanalImitado,
) -> None:
    canais = Canais(whatsapp=whatsapp)
    _autorizar(sessao, cenario.empresa_a.id)
    whatsapp.recusar = True

    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)

    assert [(m.canal, m.situacao) for m in _mensagens(sessao)] == [("whatsapp", "falhou")]


def test_o_sms_que_falha_nao_ganha_outra_copia(
    sessao: Session, agendamento: Agendamento, canais: Canais, zenvia: CanalImitado
) -> None:
    zenvia.recusar = True

    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)

    assert [(m.canal, m.situacao) for m in _mensagens(sessao)] == [("sms", "falhou")]


# --- O retorno da Zenvia --------------------------------------------------------------------


def _retorno(id_no_canal: str, codigo: str) -> dict[str, Any]:
    return {
        "type": "MESSAGE_STATUS",
        "channel": "sms",
        "messageId": id_no_canal,
        "messageStatus": {"timestamp": "2026-10-05T17:00:30Z", "code": codigo},
    }


def test_a_zenvia_avisa_entregue_e_nao_entregue(
    sessao: Session, agendamento: Agendamento, canais: Canais
) -> None:
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)
    (mensagem,) = _mensagens(sessao)

    mensagens.tratar_aviso_do_sms(sessao, _retorno(mensagem.id_no_canal or "", "DELIVERED"))

    assert (mensagem.situacao, mensagem.entregue_em) == (
        "entregue",
        AGORA + timedelta(seconds=30),
    )


def test_a_zenvia_avisa_que_nao_entregou(
    sessao: Session, agendamento: Agendamento, canais: Canais
) -> None:
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)
    (mensagem,) = _mensagens(sessao)

    mensagens.tratar_aviso_do_sms(sessao, _retorno(mensagem.id_no_canal or "", "NOT_DELIVERED"))

    assert mensagem.situacao == "falhou"
    assert (mensagem.erro or "").startswith("NOT_DELIVERED")


def test_o_retorno_pela_fila(sessao: Session, agendamento: Agendamento, canais: Canais) -> None:
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)
    (mensagem,) = _mensagens(sessao)
    fila.enfileirar(
        sessao,
        "aviso_do_sms",
        {"aviso": _retorno(mensagem.id_no_canal or "", "DELIVERED")},
        chave="resumo",
        agora=AGORA,
    )

    _enviar_tudo(sessao, canais)

    assert mensagem.situacao == "entregue"


def test_retorno_de_mensagem_que_nao_conhecemos_e_ignorado(
    sessao: Session, cenario: Demonstracao
) -> None:
    mensagens.tratar_aviso_do_sms(sessao, _retorno("zenvia.ninguem", "DELIVERED"))

    assert _mensagens(sessao) == []


# --- O motorista não avisado ----------------------------------------------------------------


def test_o_motorista_nao_avisado_e_o_do_ultimo_aviso_que_falhou_em_tudo(
    sessao: Session,
    cenario: Demonstracao,
    agendamento: Agendamento,
    canais: Canais,
    whatsapp: CanalImitado,
    zenvia: CanalImitado,
    acesso_a: Acesso,
) -> None:
    _autorizar(sessao, cenario.empresa_a.id)
    whatsapp.recusar = zenvia.recusar = True
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)

    assert mensagens.nao_avisados(sessao, acesso_a, [agendamento.id]) == {agendamento.id}


def test_com_o_sms_entregue_o_motorista_foi_avisado(
    sessao: Session,
    cenario: Demonstracao,
    agendamento: Agendamento,
    canais: Canais,
    whatsapp: CanalImitado,
    acesso_a: Acesso,
) -> None:
    _autorizar(sessao, cenario.empresa_a.id)
    whatsapp.recusar = True
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)

    assert mensagens.nao_avisados(sessao, acesso_a, [agendamento.id]) == set()


def test_a_mensagem_que_ainda_nao_saiu_nao_conta_como_nao_avisado(
    sessao: Session, agendamento: Agendamento, canais: Canais, acesso_a: Acesso
) -> None:
    mensagens.preparar(sessao, agora=AGORA, canais=canais)

    assert mensagens.nao_avisados(sessao, acesso_a, [agendamento.id]) == set()


def test_o_aviso_novo_que_saiu_apaga_o_nao_avisado_do_antigo(
    sessao: Session,
    cenario: Demonstracao,
    agendamento: Agendamento,
    canais: Canais,
    zenvia: CanalImitado,
    acesso_a: Acesso,
) -> None:
    zenvia.recusar = True
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)  # a confirmação falhou
    zenvia.recusar = False
    _chegar(sessao, cenario, agendamento)
    mensagens.preparar(sessao, agora=AGORA + timedelta(minutes=1), canais=canais)
    _enviar_tudo(sessao, canais, AGORA + timedelta(minutes=1))  # o "na fila" saiu

    assert [m.situacao for m in _mensagens(sessao)] == ["falhou", "enviada"]
    assert mensagens.nao_avisados(sessao, acesso_a, [agendamento.id]) == set()


def test_o_aviso_novo_que_falhou_vale_mesmo_com_o_antigo_entregue(
    sessao: Session,
    cenario: Demonstracao,
    agendamento: Agendamento,
    canais: Canais,
    zenvia: CanalImitado,
    acesso_a: Acesso,
) -> None:
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)  # a confirmação saiu
    zenvia.recusar = True
    _chegar(sessao, cenario, agendamento)
    mensagens.preparar(sessao, agora=AGORA + timedelta(minutes=1), canais=canais)
    _enviar_tudo(sessao, canais, AGORA + timedelta(minutes=1))  # o "na fila" falhou

    assert [m.situacao for m in _mensagens(sessao)] == ["enviada", "falhou"]
    assert mensagens.nao_avisados(sessao, acesso_a, [agendamento.id]) == {agendamento.id}


def test_o_nao_avisado_de_outra_empresa_nao_aparece(
    sessao: Session,
    cenario: Demonstracao,
    agendamento: Agendamento,
    canais: Canais,
    zenvia: CanalImitado,
    acesso_b: Acesso,
) -> None:
    zenvia.recusar = True
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)

    assert mensagens.nao_avisados(sessao, acesso_b, [agendamento.id]) == set()


def test_o_quadro_do_patio_mostra_o_motorista_nao_avisado(
    sessao: Session,
    cenario: Demonstracao,
    agendamento: Agendamento,
    canais: Canais,
    zenvia: CanalImitado,
    entrar: Callable[..., Any],
) -> None:
    zenvia.recusar = True
    _chegar(sessao, cenario, agendamento)
    mensagens.preparar(sessao, agora=AGORA, canais=canais)
    _enviar_tudo(sessao, canais)
    sessao.commit()
    cliente = entrar(cenario.gestor_a.email)

    resposta = cliente.get(f"/patio/quadro?site={cenario.site_a.id}")

    assert "motorista não avisado" in resposta.text

"""O canal de SMS (SDD 7.5, D-59 e D-64), sem banco: a Zenvia imitada e os textos curtos."""

import json
from typing import Any

import httpx
import pytest

from nuvem.mensagens import sms
from nuvem.mensagens.canais import EnvioFalhouError, EnvioRecusadoError
from nuvem.mensagens.modelos import Mensagem

TOKEN = "token-inventado"
REMETENTE = "remetente-inventado"
NUMERO_DO_WHATSAPP = "5511900000000"
LETRAS_DO_GSM7_SEM_EXTENSAO = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

VARIAVEIS = {
    "confirmacao": ["Descarga", "CD Exemplo", "05/10", "13:00", "15:00", "AG-1"],
    "na_fila": ["14:00", "3"],
    "chamada": ["Doca 2"],
    "pode_sair": ["Carga"],
}


def _canal(responder: Any) -> tuple[sms.CanalSMS, list[httpx.Request]]:
    pedidos: list[httpx.Request] = []

    def transporte(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return responder(pedido)

    cliente = httpx.Client(transport=httpx.MockTransport(transporte))
    return sms.CanalSMS(cliente, token=TOKEN, remetente=REMETENTE), pedidos


def _mensagem(texto: str = "patio-br: sua vez! Siga para a Doca 2.") -> Mensagem:
    return Mensagem(para="+5511987654321", texto=texto, modelo="chamada", canal="sms")


# --- O texto --------------------------------------------------------------------------------


def test_o_texto_fica_sem_acento_e_so_com_o_gsm7() -> None:
    assert sms.para_gsm7("Atenção: São Paulo, café à beça") == "Atencao: Sao Paulo, cafe a beca"
    # Os da extensão do GSM-7, as aspas curvas e o travessão (que vira hífen).
    estranho = "Doca [2] {A} ~ € | ^ \\ \u2018x\u2019 \u201cy\u201d \u2013 z"
    assert sms.para_gsm7(estranho) == "Doca 2 A x y - z"


def test_a_confirmacao_leva_o_link_do_whatsapp_com_o_agendamento() -> None:
    texto = sms.texto_do_sms(
        "confirmacao",
        VARIAVEIS["confirmacao"],
        agendamento_id=1234,
        numero_do_whatsapp=NUMERO_DO_WHATSAPP,
    )

    assert texto == (
        "patio-br: Descarga agendada em CD Exemplo, 05/10, 13:00-15:00 (AG-1). "
        "Avisos pelo WhatsApp: https://wa.me/5511900000000?text=AVISOS%20A1234"
    )


def test_sem_whatsapp_a_confirmacao_nao_tem_link() -> None:
    texto = sms.texto_do_sms(
        "confirmacao", VARIAVEIS["confirmacao"], agendamento_id=1, numero_do_whatsapp=None
    )

    assert "wa.me" not in texto
    assert texto.endswith("Os avisos da fila chegam por SMS.")


@pytest.mark.parametrize(
    ("modelo", "esperado"),
    [
        (
            "na_fila",
            "patio-br: chegada as 14:00. Voce esta na fila, posicao 3. Espere o aviso da doca.",
        ),
        ("chamada", "patio-br: sua vez! Siga para a Doca 2."),
        ("pode_sair", "patio-br: carga terminada. Pode sair pela portaria. Boa viagem!"),
    ],
)
def test_os_avisos_curtos(modelo: str, esperado: str) -> None:
    texto = sms.texto_do_sms(
        modelo,  # type: ignore[arg-type]
        VARIAVEIS[modelo],
        agendamento_id=1,
        numero_do_whatsapp=NUMERO_DO_WHATSAPP,
    )

    assert texto == esperado


@pytest.mark.parametrize("modelo", list(VARIAVEIS))
@pytest.mark.parametrize("site", ["CD Exemplo", "Centro de Distribuição São José dos Campos " * 4])
def test_todo_sms_cabe_num_pedaco_de_160_so_com_o_gsm7(modelo: str, site: str) -> None:
    variaveis = list(VARIAVEIS[modelo])
    if modelo == "confirmacao":
        variaveis[1] = site
        variaveis[5] = "CODIGO-EXTERNO-COMPRIDO-12345"
    if modelo == "chamada":
        variaveis[0] = site

    texto = sms.texto_do_sms(
        modelo,  # type: ignore[arg-type]
        variaveis,
        agendamento_id=123456789,
        numero_do_whatsapp=NUMERO_DO_WHATSAPP,
    )

    assert len(texto) <= sms.TAMANHO_DO_PEDACO
    assert set(texto) <= LETRAS_DO_GSM7_SEM_EXTENSAO
    if modelo == "confirmacao":
        assert texto.endswith("?text=AVISOS%20A123456789")  # o link nunca é cortado


# --- Enviar ---------------------------------------------------------------------------------


def test_envia_o_texto_pela_zenvia() -> None:
    canal, pedidos = _canal(lambda _p: httpx.Response(200, json={"id": "zenvia-1"}))

    envio = canal.enviar(_mensagem())

    assert envio.id_no_canal == "zenvia-1"
    (pedido,) = pedidos
    assert str(pedido.url) == "https://api.zenvia.com/v2/channels/sms/messages"
    assert pedido.headers["x-api-token"] == TOKEN
    assert json.loads(pedido.content) == {
        "from": REMETENTE,
        "to": "5511987654321",
        "contents": [{"type": "text", "text": "patio-br: sua vez! Siga para a Doca 2."}],
    }


def test_numero_recusado_pela_zenvia_e_definitivo() -> None:
    canal, _ = _canal(
        lambda _p: httpx.Response(400, json={"code": "VALIDATION_ERROR", "message": "to inválido"})
    )

    with pytest.raises(EnvioRecusadoError) as erro:
        canal.enviar(_mensagem())

    assert erro.value.codigo == "VALIDATION_ERROR"


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_erro_passageiro_da_zenvia_tenta_de_novo(status: int) -> None:
    canal, _ = _canal(lambda _p: httpx.Response(status, json={"code": "X"}))

    with pytest.raises(EnvioFalhouError):
        canal.enviar(_mensagem())


def test_a_rede_caida_tenta_de_novo() -> None:
    def cair(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("demorou", request=pedido)

    canal, _ = _canal(cair)

    with pytest.raises(EnvioFalhouError):
        canal.enviar(_mensagem())


def test_resposta_sem_id_tenta_de_novo() -> None:
    canal, _ = _canal(lambda _p: httpx.Response(200, json={}))

    with pytest.raises(EnvioFalhouError):
        canal.enviar(_mensagem())


# --- O retorno da Zenvia --------------------------------------------------------------------


def _evento(codigo: str, **mais: Any) -> dict[str, Any]:
    return {
        "type": "MESSAGE_STATUS",
        "channel": "sms",
        "messageId": "zenvia-1",
        "messageStatus": {"timestamp": "2026-10-05T17:00:05Z", "code": codigo, **mais},
    }


@pytest.mark.parametrize(
    ("codigo", "situacao"),
    [
        ("SENT", "enviada"),
        ("DELIVERED", "entregue"),
        ("NOT_DELIVERED", "falhou"),
        ("REJECTED", "falhou"),
    ],
)
def test_le_a_situacao_do_sms(codigo: str, situacao: str) -> None:
    lida = sms.ler_aviso_do_sms(_evento(codigo, description="operadora recusou"))

    assert lida is not None
    assert (lida.id_no_canal, lida.situacao) == ("zenvia-1", situacao)
    assert lida.momento.isoformat() == "2026-10-05T17:00:05+00:00"
    assert lida.erro == (f"{codigo}: operadora recusou" if situacao == "falhou" else None)


@pytest.mark.parametrize(
    "evento",
    [
        {},
        {"type": "MESSAGE", "messageId": "x"},
        _evento("QUALQUER"),
        {"type": "MESSAGE_STATUS", "messageStatus": {"code": "DELIVERED"}},
        {"type": "MESSAGE_STATUS", "messageId": "x", "messageStatus": "DELIVERED"},
        # Sem o fuso, a hora não diz quando foi.
        _evento("DELIVERED")
        | {"messageStatus": {"code": "DELIVERED", "timestamp": "2026-10-05T17:00:05"}},
    ],
)
def test_aviso_estranho_da_zenvia_e_ignorado(evento: dict[str, Any]) -> None:
    assert sms.ler_aviso_do_sms(evento) is None

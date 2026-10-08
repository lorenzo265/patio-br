"""O canal do WhatsApp (SDD 7.5, D-12 e D-63), sem banco: a Cloud API da Meta imitada."""

import hashlib
import hmac
import json
import re
from typing import Any

import httpx
import pytest

from nuvem.mensagens import modelos_do_whatsapp as modelos
from nuvem.mensagens import whatsapp
from nuvem.mensagens.canais import EnvioFalhouError, EnvioRecusadoError

SEGREDO_DO_APP = "segredo-do-app-inventado"
NUMERO_ID = "1234567890"
NUMERO = "5511900000000"
TOKEN = "token-inventado"


def _assinar(corpo: bytes, segredo: str = SEGREDO_DO_APP) -> str:
    return "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()


def _canal(responder: Any) -> tuple[whatsapp.CanalWhatsApp, list[httpx.Request]]:
    pedidos: list[httpx.Request] = []

    def transporte(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return responder(pedido)

    cliente = httpx.Client(transport=httpx.MockTransport(transporte))
    canal = whatsapp.CanalWhatsApp(
        cliente, versao="v25.0", numero_id=NUMERO_ID, token=TOKEN, numero=NUMERO
    )
    return canal, pedidos


def _ok(_pedido: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"messages": [{"id": "wamid.INVENTADO"}]})


def _erro(status: int, codigo: int) -> Any:
    def responder(_pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"code": codigo, "message": "inventado"}})

    return responder


# --- A assinatura do webhook --------------------------------------------------------------


def test_a_assinatura_certa_confere() -> None:
    corpo = b'{"object":"whatsapp_business_account"}'

    assert whatsapp.assinatura_confere(SEGREDO_DO_APP, corpo, _assinar(corpo))


@pytest.mark.parametrize(
    "cabecalho",
    [
        None,
        "",
        "sha256=",
        "sha1=abc",
        _assinar(b"outro corpo"),
        _assinar(b'{"object":"whatsapp_business_account"}', "outro-segredo"),
    ],
)
def test_assinatura_ausente_ou_errada_nao_confere(cabecalho: str | None) -> None:
    corpo = b'{"object":"whatsapp_business_account"}'

    assert not whatsapp.assinatura_confere(SEGREDO_DO_APP, corpo, cabecalho)


# --- O celular -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("wa_id", "celular"),
    [
        ("5511987654321", "+5511987654321"),
        # O WhatsApp manda alguns números do Brasil sem o 9 do celular.
        ("551187654321", "+5511987654321"),
        ("+5521987650000", "+5521987650000"),
        ("14155550123", None),  # de fora do Brasil
        ("5511", None),
        ("abc", None),
        ("551107654321", None),  # sem o 9, mas começa com 0: não é celular
    ],
)
def test_o_celular_do_whatsapp_vira_o_do_agendamento(wa_id: str, celular: str | None) -> None:
    assert whatsapp.celular_do_whatsapp(wa_id) == celular


def test_o_link_abre_o_whatsapp_com_a_mensagem_pronta() -> None:
    assert (
        whatsapp.link_para_autorizar(NUMERO, "AVISOS A12")
        == "https://wa.me/5511900000000?text=AVISOS%20A12"
    )


# --- Ler o aviso da Meta -------------------------------------------------------------------


def _aviso(**valor: Any) -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": valor}]}],
    }


def test_le_as_situacoes_das_mensagens() -> None:
    aviso = _aviso(
        statuses=[
            {
                "id": "wamid.A",
                "status": "delivered",
                "timestamp": "1791280800",
                "recipient_id": "5511987654321",
                "pricing": {"billable": True, "pricing_model": "PMP", "category": "utility"},
            },
            {
                "id": "wamid.B",
                "status": "failed",
                "timestamp": "1791280801",
                "errors": [{"code": 131026, "title": "Message undeliverable"}],
            },
        ]
    )

    situacoes, recebidas = whatsapp.ler_aviso(aviso)

    assert recebidas == []
    assert [(s.id_no_canal, s.situacao, s.categoria) for s in situacoes] == [
        ("wamid.A", "entregue", "utility"),
        ("wamid.B", "falhou", None),
    ]
    assert situacoes[0].momento.timestamp() == 1791280800
    assert situacoes[1].erro == "131026: Message undeliverable"


def test_le_as_mensagens_recebidas() -> None:
    aviso = _aviso(
        messages=[
            {
                "from": "5511987654321",
                "id": "wamid.R",
                "timestamp": "1791280800",
                "type": "text",
                "text": {"body": "AVISOS A12"},
            },
            {"from": "5511987654321", "id": "wamid.F", "timestamp": "1791280801", "type": "image"},
        ]
    )

    _, recebidas = whatsapp.ler_aviso(aviso)

    assert [(r.id_no_whatsapp, r.de, r.texto) for r in recebidas] == [
        ("wamid.R", "5511987654321", "AVISOS A12"),
        ("wamid.F", "5511987654321", ""),
    ]


@pytest.mark.parametrize(
    "aviso", [{}, {"entry": "x"}, {"entry": [{"changes": [{"value": {"statuses": [{}]}}]}]}]
)
def test_aviso_estranho_nao_derruba_nada(aviso: dict[str, Any]) -> None:
    assert whatsapp.ler_aviso(aviso) == ([], [])


# --- Enviar --------------------------------------------------------------------------------


def test_envia_o_modelo_com_as_variaveis_na_ordem() -> None:
    canal, pedidos = _canal(_ok)

    envio = canal.enviar_modelo("+5511987654321", "chamada", ["Doca 2"])

    assert envio.id_no_canal == "wamid.INVENTADO"
    (pedido,) = pedidos
    assert str(pedido.url) == f"https://graph.facebook.com/v25.0/{NUMERO_ID}/messages"
    assert pedido.headers["authorization"] == f"Bearer {TOKEN}"
    assert json.loads(pedido.content) == {
        "messaging_product": "whatsapp",
        "to": "5511987654321",
        "type": "template",
        "template": {
            "name": modelos.MODELOS["chamada"].nome,
            "language": {"code": "pt_BR"},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": "Doca 2"}]}],
        },
    }


def test_responde_com_texto_livre() -> None:
    canal, pedidos = _canal(_ok)

    canal.responder("+5511987654321", "Pronto!")

    assert json.loads(pedidos[0].content) == {
        "messaging_product": "whatsapp",
        "to": "5511987654321",
        "type": "text",
        "text": {"body": "Pronto!"},
    }


@pytest.mark.parametrize("codigo", [131026, 132001, 100, 131049])
def test_erro_definitivo_da_meta_recusa_o_envio(codigo: int) -> None:
    canal, _ = _canal(_erro(400, codigo))

    with pytest.raises(EnvioRecusadoError) as erro:
        canal.enviar_modelo("+5511987654321", "chamada", ["Doca 2"])

    assert erro.value.codigo == str(codigo)


@pytest.mark.parametrize(
    ("status", "codigo"),
    [(400, 131056), (400, 130429), (429, 4), (429, 999999), (500, 131000), (503, 1)],
)
def test_erro_passageiro_faz_a_tarefa_tentar_de_novo(status: int, codigo: int) -> None:
    canal, _ = _canal(_erro(status, codigo))

    with pytest.raises(EnvioFalhouError):
        canal.enviar_modelo("+5511987654321", "chamada", ["Doca 2"])


def test_token_vencido_tenta_de_novo_ate_alguem_trocar() -> None:
    canal, _ = _canal(_erro(401, 190))

    with pytest.raises(EnvioFalhouError):
        canal.enviar_modelo("+5511987654321", "chamada", ["Doca 2"])


def test_a_rede_caida_faz_a_tarefa_tentar_de_novo() -> None:
    def cair(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=pedido)

    canal, _ = _canal(cair)

    with pytest.raises(EnvioFalhouError):
        canal.enviar_modelo("+5511987654321", "chamada", ["Doca 2"])


def test_resposta_sem_id_faz_a_tarefa_tentar_de_novo() -> None:
    canal, _ = _canal(lambda _p: httpx.Response(200, json={"messages": []}))

    with pytest.raises(EnvioFalhouError):
        canal.enviar_modelo("+5511987654321", "chamada", ["Doca 2"])


# --- Os modelos de mensagem ----------------------------------------------------------------


@pytest.mark.parametrize("modelo", list(modelos.MODELOS))
def test_nenhum_modelo_comeca_ou_termina_com_uma_variavel(modelo: str) -> None:
    # A Meta recusa o modelo assim (o que vai na variável poderia ser qualquer coisa).
    corpo = modelos.MODELOS[modelo].corpo  # type: ignore[index]

    assert not corpo.startswith("{{")
    assert not corpo.endswith("}}")
    assert len(corpo) <= 1024
    numeros = [int(n) for n in re.findall(r"\{\{(\d+)\}\}", corpo)]
    assert numeros == list(range(1, len(numeros) + 1))


def test_o_nome_do_modelo_segue_a_regra_da_meta() -> None:
    for modelo in modelos.MODELOS.values():
        assert re.fullmatch(r"[a-z0-9_]{1,512}", modelo.nome)


def test_preencher_poe_as_variaveis_no_texto() -> None:
    texto = modelos.preencher("chamada", ["Doca 2"])

    assert texto == "Sua vez! Siga para a Doca 2."


def test_preencher_com_variaveis_a_menos_ou_a_mais_e_erro() -> None:
    with pytest.raises(ValueError, match="variáveis"):
        modelos.preencher("chamada", [])
    with pytest.raises(ValueError, match="variáveis"):
        modelos.preencher("chamada", ["Doca 2", "a mais"])


@pytest.mark.parametrize(
    ("texto", "pedido"),
    [
        ("AVISOS A12", ("agendamento", 12)),
        ("  avisos   a12 ", ("agendamento", 12)),
        ("AVISOS S7", ("site", 7)),
        ("SAIR", ("sair", None)),
        ("parar", ("sair", None)),
        ("Sair.", ("sair", None)),
        ("oi", None),
        ("AVISOS", None),
        ("AVISOS A", None),
        ("AVISOS X12", None),
    ],
)
def test_entende_o_que_o_motorista_pediu(texto: str, pedido: tuple[str, int | None] | None) -> None:
    assert whatsapp.o_que_pediu(texto) == pedido

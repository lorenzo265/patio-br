"""O pedido do titular (SDD 8.3, D-70): tudo o que existe de uma placa ou de um celular."""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem import tarefas_de_fundo as fila
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.cadastro.acesso import AcessoAdmin, acesso_do_usuario
from nuvem.erros import DadoInvalidoError
from nuvem.guarda import titular
from nuvem.mensagens import servico as mensagens
from nuvem.mensagens.modelos import AutorizacaoWhatsApp, MensagemRecebida
from nuvem.portaria import conferencia
from nuvem.portaria.modelos import Evento
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 17, 10, tzinfo=UTC)
JANELA = datetime(2026, 10, 5, 16, 0, tzinfo=UTC)
CELULAR = "+5511987654321"


@pytest.fixture
def administracao(cenario: Demonstracao) -> AcessoAdmin:
    return AcessoAdmin(administrador_id=cenario.administrador.id)


def _agendar(
    sessao: Session, cenario: Demonstracao, empresa: str, codigo: str, **mudancas: object
) -> None:
    site = cenario.site_a if empresa == "a" else cenario.site_b
    destino = SiteDoAgendamento(empresa_id=site.empresa_id, site_id=site.id, usuario_id=None)
    dados = DadosDoAgendamento.model_validate(
        {
            "codigo_externo": codigo,
            "janela_inicio": JANELA,
            "janela_fim": JANELA + timedelta(hours=2),
            "tipo": "descarga",
            "placa_cavalo": "ABC1D23",
            "motorista_celular": CELULAR,
            **mudancas,
        }
    )
    agendamentos.gravar(sessao, destino, "planilha", dados, agora=JANELA - timedelta(days=1))


@pytest.fixture
def historia(
    sessao: Session, cenario: Demonstracao, registrar_passagem: Callable[..., Passagem]
) -> tuple[Passagem, int]:
    """A placa ABC1D23 e o celular nas duas empresas: a chegada, a conferência e as mensagens."""
    _agendar(sessao, cenario, "a", "AG-1")
    _agendar(sessao, cenario, "b", "AG-B")  # a mesma placa e o mesmo celular, noutra empresa
    # A placa como reboque de outro cavalo, num agendamento sem celular.
    _agendar(
        sessao, cenario, "a", "AG-2", placa_cavalo="XYZ9K87", placas_reboques=["ABC1D23"],
        motorista_celular=None, janela_inicio=JANELA + timedelta(days=1),
        janela_fim=JANELA + timedelta(days=1, hours=2),
    )  # fmt: skip
    passagem = registrar_passagem()
    fila.executar_pendentes(sessao, agora=AGORA)
    mensagens.preparar(sessao, agora=AGORA)
    porteiro = acesso_do_usuario(sessao, cenario.porteiro_a.id)
    # O porteiro corrigiu a leitura: a conferência vale pela placa lida e pela conferida.
    conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D24", agora=AGORA)
    for empresa in (cenario.empresa_a, cenario.empresa_b):
        sessao.add(
            AutorizacaoWhatsApp(
                empresa_id=empresa.id, celular=CELULAR, autorizada_em=AGORA,
                texto="AVISOS A1", id_no_whatsapp=f"wamid.autorizou.{empresa.id}",
            )
        )  # fmt: skip
        # O WhatsApp às vezes dá o número sem o 9 do celular.
        for de in ("5511987654321", "551187654321"):
            sessao.add(
                MensagemRecebida(
                    id_no_whatsapp=f"wamid.recebida.{empresa.id}.{de}", de=de,
                    texto="AVISOS A1", recebida_em=AGORA, empresa_id=empresa.id,
                    resultado="autorizou", tratada_em=AGORA,
                )
            )  # fmt: skip
    sessao.flush()
    evento = sessao.scalars(select(Evento).where(Evento.passagem_id == passagem.id)).one()
    return passagem, evento.visita_id


def test_pela_placa_vem_tudo_da_empresa_e_nada_da_outra(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    historia: tuple[Passagem, int],
) -> None:
    passagem, visita_id = historia

    achado = titular.levantar(
        sessao, administracao, empresa_id=cenario.empresa_a.id, placa="abc-1d23"
    )

    assert achado.procurado == "placa ABC1D23"
    assert [v["id"] for v in achado.visitas] == [visita_id]
    assert [p["id"] for p in achado.passagens] == [str(passagem.id)]
    assert [c["placa"] for c in achado.conferencias] == ["ABC1D24"]
    assert [a["codigo"] for a in achado.agendamentos] == ["AG-1", "AG-2"]
    assert achado.mensagens
    assert {m["para"] for m in achado.mensagens} == {CELULAR}
    # Pela placa, a autorização e as recebidas (que são do celular) não vêm.
    assert achado.autorizacoes == []
    assert achado.recebidas == []


def test_pelo_celular_vem_o_que_e_dele_na_empresa(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    historia: tuple[Passagem, int],
) -> None:
    _, visita_id = historia

    achado = titular.levantar(
        sessao, administracao, empresa_id=cenario.empresa_a.id, celular="(11) 98765-4321"
    )

    assert achado.procurado == f"celular {CELULAR}"
    assert [a["codigo"] for a in achado.agendamentos] == ["AG-1"]
    assert [v["id"] for v in achado.visitas] == [visita_id]
    assert achado.mensagens
    assert [a["celular"] for a in achado.autorizacoes] == [CELULAR]
    assert sorted(r["de"] for r in achado.recebidas) == ["551187654321", "5511987654321"]
    assert achado.passagens == []  # a passagem não tem celular


def test_o_levantamento_vira_arquivo(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    historia: tuple[Passagem, int],
) -> None:
    achado = titular.levantar(
        sessao, administracao, empresa_id=cenario.empresa_a.id, placa="ABC1D23"
    )

    arquivo = json.loads(json.dumps(achado.como_dicionario()))

    assert arquivo["empresa"] == cenario.empresa_a.nome
    assert set(arquivo) >= {"visitas", "passagens", "agendamentos", "mensagens", "autorizacoes"}


@pytest.mark.parametrize(
    ("placa", "celular"), [("", ""), ("ABC", ""), ("", "123"), ("ABC1D23", "(11) 98765-4321")]
)
def test_pede_uma_placa_ou_um_celular_valido(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    placa: str,
    celular: str,
) -> None:
    with pytest.raises(DadoInvalidoError):
        titular.levantar(
            sessao, administracao, empresa_id=cenario.empresa_a.id, placa=placa, celular=celular
        )

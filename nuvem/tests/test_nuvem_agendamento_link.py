"""Link da transportadora (SDD 3.4, 8.2 e D-34): gerar, abrir, agendar, vencer, revogar, limitar."""

from dataclasses import replace
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nuvem.agendamento import link as links
from nuvem.agendamento.conectores import Lido, Recusado
from nuvem.agendamento.link import FormularioDoLink, LinkEsgotadoError
from nuvem.agendamento.modelos import Agendamento, LinkTransportadora, MudancaAgendamento
from nuvem.banco import SQLSTATE_CHECK, sqlstate
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.semente import Demonstracao
from nuvem.senhas import resumo_rapido

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)
"""15h em São Paulo; o site_a da demonstração abre das 6h às 22h."""

FORMULARIO = FormularioDoLink(
    data="2026-11-05",
    hora_inicio="08:00",
    hora_fim="10:00",
    tipo="descarga",
    placa_cavalo="abc-1d23",
    reboque_1="DEF4G56",
    motorista_nome="Motorista Inventado",
    motorista_celular="(11) 98765-4321",
    toneladas="32,5",
)


@pytest.fixture
def gerado(sessao: Session, cenario: Demonstracao, acesso_a: Acesso) -> links.LinkGerado:
    """Um link do site_a, gerado pelo gestor A agora."""
    return links.gerar_link(
        sessao, acesso_a, cenario.site_a.id, nome="Transportadora Inventada", agora=AGORA
    )


# --- Gerar ------------------------------------------------------------------------------------


def test_gerar_guarda_so_o_resumo_do_codigo(
    sessao: Session, cenario: Demonstracao, gerado: links.LinkGerado
) -> None:
    link = gerado.link

    assert len(gerado.codigo) >= 32
    assert link.codigo_resumo == resumo_rapido(gerado.codigo)
    assert gerado.codigo not in str(sessao.execute(select(LinkTransportadora.__table__)).all())
    assert (link.empresa_id, link.site_id, link.criado_por) == (
        cenario.empresa_a.id,
        cenario.site_a.id,
        cenario.gestor_a.id,
    )


def test_gerar_usa_a_validade_e_o_limite_padrao(gerado: links.LinkGerado) -> None:
    assert gerado.link.vence_em == AGORA + timedelta(days=30)
    assert (gerado.link.limite_de_envios, gerado.link.envios) == (50, 0)


def test_cada_link_tem_o_proprio_codigo(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, gerado: links.LinkGerado
) -> None:
    outro = links.gerar_link(sessao, acesso_a, cenario.site_a.id, nome="Outra", agora=AGORA)

    assert outro.codigo != gerado.codigo


@pytest.mark.parametrize(
    "mudanca",
    [
        {"nome": " "},
        {"nome": "x" * 121},
        {"validade": timedelta(hours=23)},
        {"validade": timedelta(days=181)},
        {"limite": 0},
        {"limite": 1001},
    ],
)
def test_gerar_recusa_valores_fora_da_regra(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, mudanca: dict[str, object]
) -> None:
    argumentos: dict[str, object] = {"nome": "Transportadora", "agora": AGORA} | mudanca

    with pytest.raises(DadoInvalidoError):
        links.gerar_link(sessao, acesso_a, cenario.site_a.id, **argumentos)  # type: ignore[arg-type]


def test_gerar_em_site_fora_do_alcance_nao_encontra(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    for site in (cenario.site_a2, cenario.site_b):
        with pytest.raises(NaoEncontradoError):
            links.gerar_link(sessao, acesso_a, site.id, nome="Transportadora", agora=AGORA)


def test_listar_traz_os_links_do_site_do_mais_novo_ao_mais_velho(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, acesso_b: Acesso,
    gerado: links.LinkGerado,
) -> None:  # fmt: skip
    depois = links.gerar_link(
        sessao, acesso_a, cenario.site_a.id, nome="Depois", agora=AGORA + timedelta(hours=1)
    )

    assert links.listar_links(sessao, acesso_a, cenario.site_a.id) == [depois.link, gerado.link]
    with pytest.raises(NaoEncontradoError):
        links.listar_links(sessao, acesso_b, cenario.site_a.id)


# --- Abrir ------------------------------------------------------------------------------------


def test_abrir_traz_o_site_e_o_horario(
    sessao: Session, cenario: Demonstracao, gerado: links.LinkGerado
) -> None:
    aberto = links.abrir_link(sessao, gerado.codigo, agora=AGORA)

    assert (aberto.nome, aberto.site.nome, aberto.site.fuso) == (
        "Transportadora Inventada",
        cenario.site_a.nome,
        "America/Sao_Paulo",
    )
    assert (aberto.site.abre, aberto.site.fecha) == (time(6), time(22))


def test_codigo_inventado_nao_encontra(sessao: Session, gerado: links.LinkGerado) -> None:
    with pytest.raises(NaoEncontradoError):
        links.abrir_link(sessao, gerado.codigo + "x", agora=AGORA)


def test_link_vencido_nao_encontra(sessao: Session, gerado: links.LinkGerado) -> None:
    with pytest.raises(NaoEncontradoError):
        links.abrir_link(sessao, gerado.codigo, agora=gerado.link.vence_em)


def test_link_revogado_nao_encontra(
    sessao: Session, acesso_a: Acesso, gerado: links.LinkGerado
) -> None:
    links.revogar_link(sessao, acesso_a, gerado.link.id, agora=AGORA)

    with pytest.raises(NaoEncontradoError):
        links.abrir_link(sessao, gerado.codigo, agora=AGORA)


def test_revogar_de_novo_mantem_a_primeira_hora(
    sessao: Session, acesso_a: Acesso, gerado: links.LinkGerado
) -> None:
    links.revogar_link(sessao, acesso_a, gerado.link.id, agora=AGORA)
    links.revogar_link(sessao, acesso_a, gerado.link.id, agora=AGORA + timedelta(hours=1))

    assert gerado.link.revogado_em == AGORA


def test_revogar_link_de_outra_empresa_nao_encontra(
    sessao: Session, acesso_b: Acesso, gerado: links.LinkGerado
) -> None:
    with pytest.raises(NaoEncontradoError):
        links.revogar_link(sessao, acesso_b, gerado.link.id, agora=AGORA)

    assert gerado.link.revogado_em is None


def test_link_no_limite_avisa_que_esgotou(sessao: Session, gerado: links.LinkGerado) -> None:
    gerado.link.envios = gerado.link.limite_de_envios
    sessao.flush()

    with pytest.raises(LinkEsgotadoError):
        links.abrir_link(sessao, gerado.codigo, agora=AGORA)


# --- Agendar pelo link ------------------------------------------------------------------------


def test_agendar_cria_o_agendamento_do_link(
    sessao: Session, cenario: Demonstracao, gerado: links.LinkGerado
) -> None:
    agendamento = links.agendar_pelo_link(sessao, gerado.codigo, FORMULARIO, agora=AGORA)

    assert isinstance(agendamento, Agendamento)
    assert (agendamento.origem, agendamento.codigo_externo, agendamento.link_id) == (
        "link",
        f"{gerado.link.id}-1",
        gerado.link.id,
    )
    assert agendamento.site_id == cenario.site_a.id
    # 8h e 10h em São Paulo (UTC-3).
    assert agendamento.janela_inicio == datetime(2026, 11, 5, 11, 0, tzinfo=UTC)
    assert agendamento.janela_fim == datetime(2026, 11, 5, 13, 0, tzinfo=UTC)
    assert (agendamento.placa_cavalo, agendamento.placas_reboques) == ("ABC1D23", ["DEF4G56"])
    assert agendamento.motorista_celular == "+5511987654321"
    assert gerado.link.envios == 1


def test_a_mudanca_do_link_nao_tem_usuario(sessao: Session, gerado: links.LinkGerado) -> None:
    agendamento = links.agendar_pelo_link(sessao, gerado.codigo, FORMULARIO, agora=AGORA)
    assert isinstance(agendamento, Agendamento)

    mudanca = sessao.scalars(
        select(MudancaAgendamento).where(MudancaAgendamento.agendamento_id == agendamento.id)
    ).one()

    assert (mudanca.tipo, mudanca.via, mudanca.usuario_id) == ("criado", "link", None)


def test_cada_envio_e_um_agendamento_novo(sessao: Session, gerado: links.LinkGerado) -> None:
    primeiro = links.agendar_pelo_link(sessao, gerado.codigo, FORMULARIO, agora=AGORA)
    segundo = links.agendar_pelo_link(sessao, gerado.codigo, FORMULARIO, agora=AGORA)

    assert isinstance(primeiro, Agendamento)
    assert isinstance(segundo, Agendamento)
    assert (primeiro.codigo_externo, segundo.codigo_externo) == (
        f"{gerado.link.id}-1",
        f"{gerado.link.id}-2",
    )
    assert gerado.link.envios == 2


def test_o_ultimo_envio_do_limite_entra_e_o_seguinte_nao(
    sessao: Session, gerado: links.LinkGerado
) -> None:
    gerado.link.envios = gerado.link.limite_de_envios - 1
    sessao.flush()

    assert isinstance(
        links.agendar_pelo_link(sessao, gerado.codigo, FORMULARIO, agora=AGORA), Agendamento
    )
    with pytest.raises(LinkEsgotadoError):
        links.agendar_pelo_link(sessao, gerado.codigo, FORMULARIO, agora=AGORA)


def test_envio_recusado_nao_gasta_o_limite(sessao: Session, gerado: links.LinkGerado) -> None:
    erros = links.agendar_pelo_link(
        sessao, gerado.codigo, replace(FORMULARIO, placa_cavalo="ABC12"), agora=AGORA
    )

    assert erros == [
        "placa do cavalo: placa inválida: 'ABC12' (formatos aceitos: ABC1234 e ABC1D23)"
    ]
    assert gerado.link.envios == 0
    assert sessao.scalar(select(Agendamento.id)) is None


def test_agendar_por_link_revogado_nao_encontra(
    sessao: Session, acesso_a: Acesso, gerado: links.LinkGerado
) -> None:
    links.revogar_link(sessao, acesso_a, gerado.link.id, agora=AGORA)

    with pytest.raises(NaoEncontradoError):
        links.agendar_pelo_link(sessao, gerado.codigo, FORMULARIO, agora=AGORA)


def test_agendamento_do_link_traz_o_que_ele_criou(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, gerado: links.LinkGerado
) -> None:
    agendamento = links.agendar_pelo_link(sessao, gerado.codigo, FORMULARIO, agora=AGORA)
    assert isinstance(agendamento, Agendamento)
    outro = links.gerar_link(sessao, acesso_a, cenario.site_a.id, nome="Outra", agora=AGORA)

    assert (
        links.agendamento_do_link(sessao, gerado.codigo, agendamento.codigo_externo, agora=AGORA)
        == agendamento
    )
    with pytest.raises(NaoEncontradoError):
        links.agendamento_do_link(sessao, outro.codigo, agendamento.codigo_externo, agora=AGORA)


def test_confirmacao_do_ultimo_envio_abre_mesmo_com_o_link_esgotado(
    sessao: Session, gerado: links.LinkGerado
) -> None:
    gerado.link.envios = gerado.link.limite_de_envios - 1
    sessao.flush()
    agendamento = links.agendar_pelo_link(sessao, gerado.codigo, FORMULARIO, agora=AGORA)
    assert isinstance(agendamento, Agendamento)

    assert (
        links.agendamento_do_link(sessao, gerado.codigo, agendamento.codigo_externo, agora=AGORA)
        == agendamento
    )


# --- O formulário -----------------------------------------------------------------------------


def _erros(sessao: Session, gerado: links.LinkGerado, **mudancas: str) -> list[str]:
    resultado = links.agendar_pelo_link(
        sessao, gerado.codigo, replace(FORMULARIO, **mudancas), agora=AGORA
    )
    assert isinstance(resultado, list), resultado
    return resultado


@pytest.mark.parametrize(
    ("mudancas", "erro"),
    [
        ({"motorista_nome": " "}, "motorista: falta"),
        ({"motorista_celular": ""}, "celular: falta"),
        ({"toneladas": ""}, "toneladas: falta"),
        ({"tipo": ""}, "tipo: falta"),
        ({"placa_cavalo": ""}, "placa do cavalo: falta"),
        ({"data": "05/11/2026"}, "data: use o formato do calendário"),
        ({"data": ""}, "data: falta"),
        ({"hora_inicio": "8h"}, "hora de início: use o formato do relógio"),
        ({"hora_fim": ""}, "hora de fim: falta"),
        (
            {"hora_inicio": "05:30"},
            "a janela precisa ficar dentro do horário do site, das 06:00 às 22:00",
        ),
        (
            {"hora_fim": "22:30"},
            "a janela precisa ficar dentro do horário do site, das 06:00 às 22:00",
        ),
        (
            {"data": "2026-11-04", "hora_inicio": "14:00", "hora_fim": "15:00"},
            "a janela precisa começar no futuro",
        ),
        ({"data": "2027-01-04"}, "a janela pode ser marcada até 60 dias à frente"),
        ({"hora_fim": "08:00"}, "o fim da janela precisa ser depois do início"),
    ],
)
def test_formulario_fora_da_regra_diz_o_porque(
    sessao: Session, gerado: links.LinkGerado, mudancas: dict[str, str], erro: str
) -> None:
    assert _erros(sessao, gerado, **mudancas) == [erro]


def test_varios_erros_aparecem_juntos(sessao: Session, gerado: links.LinkGerado) -> None:
    erros = _erros(sessao, gerado, data="", placa_cavalo="ABC12", motorista_celular="123")

    assert erros == [
        "data: falta",
        "placa do cavalo: placa inválida: 'ABC12' (formatos aceitos: ABC1234 e ABC1D23)",
        "celular: celular inválido: '123' (use o DDD e os 9 números do celular)",
    ]


def test_reboques_em_branco_no_meio_sao_ignorados(
    sessao: Session, gerado: links.LinkGerado
) -> None:
    agendamento = links.agendar_pelo_link(
        sessao,
        gerado.codigo,
        replace(FORMULARIO, reboque_1="", reboque_2="DEF4G56", reboque_3="GHI7J89"),
        agora=AGORA,
    )

    assert isinstance(agendamento, Agendamento)
    assert agendamento.placas_reboques == ["DEF4G56", "GHI7J89"]


def test_site_sem_horario_aceita_qualquer_hora(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, gerado: links.LinkGerado
) -> None:
    cenario.site_a.abre = cenario.site_a.fecha = None
    sessao.flush()

    agendamento = links.agendar_pelo_link(
        sessao, gerado.codigo, replace(FORMULARIO, hora_inicio="02:00"), agora=AGORA
    )

    assert isinstance(agendamento, Agendamento)


def test_o_conector_do_link_segue_a_interface(sessao: Session, gerado: links.LinkGerado) -> None:
    aberto = links.abrir_link(sessao, gerado.codigo, agora=AGORA)
    conector = links.ConectorDoLink(aberto.site, codigo_externo="7-1", agora=AGORA)

    [lido] = conector.ler(FORMULARIO)
    [recusado] = conector.ler(replace(FORMULARIO, toneladas=""))

    assert conector.origem == "link"
    assert isinstance(lido, Lido)
    assert (lido.onde, lido.dados.codigo_externo) == ("formulário", "7-1")
    assert recusado == Recusado(onde="formulário", motivo="toneladas: falta")


# --- O banco também confere -------------------------------------------------------------------


def test_banco_recusa_horario_do_site_fora_de_ordem(sessao: Session, cenario: Demonstracao) -> None:
    cenario.site_a.abre, cenario.site_a.fecha = time(22), time(6)

    with pytest.raises(DBAPIError) as erro:
        sessao.flush()

    assert sqlstate(erro.value) == SQLSTATE_CHECK


def test_banco_recusa_horario_pela_metade(sessao: Session, cenario: Demonstracao) -> None:
    cenario.site_a.fecha = None

    with pytest.raises(DBAPIError) as erro:
        sessao.flush()

    assert sqlstate(erro.value) == SQLSTATE_CHECK


def test_banco_recusa_envios_alem_do_limite(sessao: Session, gerado: links.LinkGerado) -> None:
    gerado.link.envios = gerado.link.limite_de_envios + 1

    with pytest.raises(DBAPIError) as erro:
        sessao.flush()

    assert sqlstate(erro.value) == SQLSTATE_CHECK


def test_criar_site_com_horario(sessao: Session, cenario: Demonstracao) -> None:
    site = cadastro.criar_site(
        sessao, cenario.empresa_a, nome="CD Noturno", abre=time(7, 30), fecha=time(19)
    )

    assert (site.abre, site.fecha) == (time(7, 30), time(19))


def test_revogar_link_de_site_fora_do_alcance_nao_encontra(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    # O site_a2 é da empresa A, mas o gestor A não o vê.
    link = LinkTransportadora(
        empresa_id=cenario.empresa_a.id,
        site_id=cenario.site_a2.id,
        nome="Do outro site",
        codigo_resumo=resumo_rapido("codigo-do-outro-site"),
        criado_por=cenario.gestor_a.id,
        criado_em=AGORA,
        vence_em=AGORA + timedelta(days=1),
        limite_de_envios=1,
        envios=0,
    )
    sessao.add(link)
    sessao.flush()

    with pytest.raises(NaoEncontradoError):
        links.revogar_link(sessao, acesso_a, link.id, agora=AGORA)

    assert link.revogado_em is None

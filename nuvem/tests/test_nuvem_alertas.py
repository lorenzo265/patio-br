"""Os alertas (SDD 8.1, D-62 e D-68): abrem uma vez, fecham sozinhos e avisam quem autorizou."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from contratos.saude import Saude
from nuvem import tarefas_de_fundo
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.formato import DadosDoAgendamento
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.alertas import servico as alertas
from nuvem.alertas.modelos import Alerta, AlertasNoWhatsApp, AvisoDeAlerta
from nuvem.cadastro.acesso import Acesso, AcessoAdmin, acesso_do_usuario
from nuvem.cadastro.modelos import Usuario
from nuvem.frota import saude as frota
from nuvem.frota import servico as caixas
from nuvem.frota.servico import AcessoDaCaixa
from nuvem.mensagens import servico as mensagens
from nuvem.mensagens.canais import Canais, Envio, EnvioRecusadoError
from nuvem.mensagens.modelos import Mensagem, MensagemRecebida
from nuvem.portaria import resolucao, visitas
from nuvem.portaria.modelos import Visita
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita
from nuvem.semente import Demonstracao

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 6, 17, 0, tzinfo=UTC)
"""14:00 em São Paulo, o fuso dos sites da demonstração."""
CELULAR_DO_GESTOR = "+5511990000001"
CELULAR_DA_ADMINISTRACAO = "+5511990000002"


def _abertos(sessao: Session) -> list[tuple[str, str]]:
    return [
        (alerta.tipo, alerta.chave)
        for alerta in sessao.scalars(
            select(Alerta).where(Alerta.fechado_em.is_(None)).order_by(Alerta.id)
        )
    ]


@pytest.fixture
def site_a(cenario: Demonstracao) -> SiteDaVisita:
    return SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id)


def _chegar(sessao: Session, site: SiteDaVisita, placa: str, ha: timedelta) -> Visita:
    return visitas.abrir_visita(
        sessao, site, "check_in", momento=AGORA - ha, agora=AGORA - ha,
        composicao=(PlacaNaVisita(placa=placa, papel="cavalo", como="lida"),),
    )  # fmt: skip


def _sair(sessao: Session, visita: Visita, quando: datetime) -> None:
    sessao.execute(
        update(Visita).where(Visita.id == visita.id).values(estado="SAIU", saiu_em=quando)
    )


# --- A estadia ------------------------------------------------------------------------------


def test_a_estadia_perto_das_5_horas_abre_com_4_horas(
    sessao: Session, site_a: SiteDaVisita
) -> None:
    visita = _chegar(sessao, site_a, "ABC1D23", timedelta(hours=3, minutes=59))

    alertas.conferir(sessao, agora=AGORA)
    assert _abertos(sessao) == []

    alertas.conferir(sessao, agora=AGORA + timedelta(minutes=1))
    assert _abertos(sessao) == [("estadia_perto", f"visita:{visita.id}")]
    (alerta,) = sessao.scalars(select(Alerta))
    assert alerta.texto == "ABC1D23 no site há 4 horas (chegou às 10:01)"
    assert (alerta.aberto_em, alerta.site_id) == (AGORA + timedelta(minutes=1), site_a.site_id)


def test_a_estadia_que_passou_das_5_horas_fecha_a_de_perto(
    sessao: Session, site_a: SiteDaVisita
) -> None:
    visita = _chegar(sessao, site_a, "ABC1D23", timedelta(hours=4, minutes=30))
    alertas.conferir(sessao, agora=AGORA)

    alertas.conferir(sessao, agora=AGORA + timedelta(minutes=30))

    assert _abertos(sessao) == [("estadia_passou", f"visita:{visita.id}")]
    perto = sessao.scalar(select(Alerta).where(Alerta.tipo == "estadia_perto"))
    assert perto is not None
    assert perto.fechado_em == AGORA + timedelta(minutes=30)


def test_o_alerta_abre_uma_vez_so(sessao: Session, site_a: SiteDaVisita) -> None:
    _chegar(sessao, site_a, "ABC1D23", timedelta(hours=4))

    for minuto in range(5):
        alertas.conferir(sessao, agora=AGORA + timedelta(minutes=minuto))

    assert len(list(sessao.scalars(select(Alerta)))) == 1


def test_a_visita_que_sai_fecha_o_alerta(sessao: Session, site_a: SiteDaVisita) -> None:
    visita = _chegar(sessao, site_a, "ABC1D23", timedelta(hours=6))
    alertas.conferir(sessao, agora=AGORA)

    _sair(sessao, visita, AGORA)
    conferencia = alertas.conferir(sessao, agora=AGORA + timedelta(minutes=1))

    assert _abertos(sessao) == []
    assert (conferencia.abertos, conferencia.fechados) == (0, 1)


def test_a_estadia_volta_a_abrir_depois_de_fechar_noutra_visita(
    sessao: Session, site_a: SiteDaVisita
) -> None:
    primeira = _chegar(sessao, site_a, "ABC1D23", timedelta(hours=6))
    alertas.conferir(sessao, agora=AGORA)
    _sair(sessao, primeira, AGORA)
    alertas.conferir(sessao, agora=AGORA)
    segunda = _chegar(sessao, site_a, "ABC1D23", timedelta(hours=6))

    alertas.conferir(sessao, agora=AGORA + timedelta(minutes=1))

    assert _abertos(sessao) == [("estadia_passou", f"visita:{segunda.id}")]


# --- A chegada sem agendamento --------------------------------------------------------------


def test_a_chegada_sem_agendamento_abre_e_fecha_com_a_excecao(
    sessao: Session,
    site_a: SiteDaVisita,
    acesso_a: Acesso,
    registrar_passagem: Callable[..., Passagem],
) -> None:
    passagem = registrar_passagem(inicio=AGORA - timedelta(minutes=10))
    excecao = visitas.abrir_excecao(
        sessao, site_a, passagem_id=passagem.id, momento=AGORA - timedelta(minutes=10),
        agora=AGORA, motivo="sem_candidato", candidatos=(),
        composicao=(PlacaNaVisita(placa="ABC1D23", papel="cavalo", como="lida"),),
    )  # fmt: skip
    outra = visitas.abrir_excecao(
        sessao, site_a, passagem_id=registrar_passagem(inicio=AGORA - timedelta(minutes=9)).id,
        momento=AGORA - timedelta(minutes=9), agora=AGORA, motivo="pontos_baixos",
        candidatos=(), composicao=(PlacaNaVisita(placa="BRA2E19", papel="cavalo", como="lida"),),
    )  # fmt: skip

    alertas.conferir(sessao, agora=AGORA)
    abertos = _abertos(sessao)
    resolucao.aceitar_sem_agendamento(sessao, acesso_a, excecao.id, agora=AGORA)
    alertas.conferir(sessao, agora=AGORA + timedelta(minutes=1))

    # Só a "sem candidato" é chegada sem agendamento; a dos pontos baixos é a conferência.
    assert abertos == [("sem_agendamento", f"excecao:{excecao.id}")]
    assert outra.id != excecao.id
    assert _abertos(sessao) == []


# --- A caixa, as câmeras e o relógio --------------------------------------------------------


@pytest.fixture
def caixa(sessao: Session, caixa_a: caixas.CaixaAtivada) -> AcessoDaCaixa:
    identificada = caixas.caixa_da_chave(sessao, caixa_a.chave)
    assert identificada is not None
    return identificada


def _saude(
    sessao: Session,
    caixa: AcessoDaCaixa,
    recebida: datetime,
    *,
    cameras: list[tuple[str, bool]] | None = None,
    adiantada: float = 0,
) -> None:
    dados: dict[str, Any] = {
        "versao_contrato": 1,
        "caixa_id": str(caixa.caixa_id),
        "site_id": str(caixa.site_id),
        "momento": (recebida + timedelta(seconds=adiantada)).isoformat(),
        "versao_programa": "0.1.0",
        "versao_leitor": "v0",
        "cpu": 10.0,
        "temperatura": None,
        "memoria": 10.0,
        "disco": 10.0,
        "cameras": [
            {
                "camera_id": camera,
                "no_ar": no_ar,
                "quadros_por_segundo": 5.0 if no_ar else 0,
                "ultimo_quadro": recebida.isoformat() if no_ar else None,
            }
            for camera, no_ar in (cameras if cameras is not None else [("21", True)])
        ],
        "fila": {"passagens": 0, "fotos": 0, "recusadas": 0},
    }
    frota.receber_saude(sessao, caixa, Saude.model_validate(dados), agora=recebida)


def test_a_caixa_sem_contato_abre_e_fecha_quando_a_saude_volta(
    sessao: Session, caixa: AcessoDaCaixa
) -> None:
    _saude(sessao, caixa, AGORA - timedelta(minutes=3))

    alertas.conferir(sessao, agora=AGORA)
    abertos = _abertos(sessao)
    _saude(sessao, caixa, AGORA + timedelta(minutes=1))
    alertas.conferir(sessao, agora=AGORA + timedelta(minutes=1))

    assert abertos == [("caixa_sem_contato", f"caixa:{caixa.caixa_id}")]
    assert _abertos(sessao) == []
    (alerta,) = sessao.scalars(select(Alerta))
    assert alerta.texto == f"Caixa {caixa.caixa_id} sem contato desde 13:57"


def test_a_caixa_que_nunca_mandou_saude_nao_abre_alerta(
    sessao: Session, caixa: AcessoDaCaixa
) -> None:
    alertas.conferir(sessao, agora=AGORA + timedelta(days=1))

    assert _abertos(sessao) == []


def test_a_camera_parada_em_duas_saudes_seguidas(
    sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    camera = str(cenario.camera_a.id)
    # Logo depois de ligar, a primeira saúde ainda não tem quadro: não é câmera parada.
    _saude(sessao, caixa, AGORA - timedelta(minutes=1), cameras=[(camera, False)])
    alertas.conferir(sessao, agora=AGORA - timedelta(minutes=1))
    assert _abertos(sessao) == []

    _saude(sessao, caixa, AGORA, cameras=[(camera, False)])
    alertas.conferir(sessao, agora=AGORA)
    assert _abertos(sessao) == [("camera_parada", f"camera:{caixa.caixa_id}:{camera}")]
    (alerta,) = sessao.scalars(select(Alerta))
    assert alerta.texto == "Câmera Entrada 1 — frente sem quadros na caixa " + str(caixa.caixa_id)

    _saude(sessao, caixa, AGORA + timedelta(minutes=1), cameras=[(camera, True)])
    alertas.conferir(sessao, agora=AGORA + timedelta(minutes=1))
    assert _abertos(sessao) == []

    # Uma saúde sem quadro, logo depois de uma com quadro, ainda não é câmera parada.
    _saude(sessao, caixa, AGORA + timedelta(minutes=2), cameras=[(camera, False)])
    alertas.conferir(sessao, agora=AGORA + timedelta(minutes=2))
    assert _abertos(sessao) == []


def test_sem_contato_vale_o_alerta_da_caixa_e_nao_o_da_camera(
    sessao: Session, caixa: AcessoDaCaixa
) -> None:
    _saude(sessao, caixa, AGORA - timedelta(minutes=5), cameras=[("21", False)])
    _saude(sessao, caixa, AGORA - timedelta(minutes=4), cameras=[("21", False)], adiantada=9)

    alertas.conferir(sessao, agora=AGORA)

    assert _abertos(sessao) == [("caixa_sem_contato", f"caixa:{caixa.caixa_id}")]


@pytest.mark.parametrize(("adiantada", "abre"), [(2.0, False), (2.1, True), (-2.1, True)])
def test_o_relogio_da_caixa_errado(
    sessao: Session, caixa: AcessoDaCaixa, adiantada: float, abre: bool
) -> None:
    _saude(sessao, caixa, AGORA, adiantada=adiantada)

    alertas.conferir(sessao, agora=AGORA)

    esperado = [("relogio_errado", f"caixa:{caixa.caixa_id}")] if abre else []
    assert _abertos(sessao) == esperado


# --- O motorista não avisado e a tarefa que falhou ------------------------------------------


def test_o_motorista_nao_avisado_com_a_visita_no_site(
    sessao: Session, cenario: Demonstracao, site_a: SiteDaVisita
) -> None:
    destino = SiteDoAgendamento(
        empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id, usuario_id=None
    )
    dados = DadosDoAgendamento(
        codigo_externo="AG-7", janela_inicio=AGORA, janela_fim=AGORA + timedelta(hours=2),
        tipo="descarga", placa_cavalo="ABC1D23", motorista_celular="+5511987654321",
    )  # fmt: skip
    agendamento = agendamentos.gravar(sessao, destino, "planilha", dados, agora=AGORA).agendamento
    visita = visitas.abrir_visita(
        sessao, site_a, "check_in", momento=AGORA, agora=AGORA, agendamento_id=agendamento.id,
        composicao=(PlacaNaVisita(placa="ABC1D23", papel="cavalo", como="lida"),),
    )  # fmt: skip
    sessao.add(
        Mensagem(
            empresa_id=cenario.empresa_a.id, site_id=cenario.site_a.id,
            agendamento_id=agendamento.id, modelo="confirmacao", para="+5511987654321",
            texto="x", canal="sms", situacao="falhou", criada_em=AGORA,
        )
    )  # fmt: skip
    sessao.flush()

    alertas.conferir(sessao, agora=AGORA)
    abertos = _abertos(sessao)
    _sair(sessao, visita, AGORA)
    alertas.conferir(sessao, agora=AGORA + timedelta(minutes=1))

    assert abertos == [("motorista_nao_avisado", f"agendamento:{agendamento.id}")]
    assert _abertos(sessao) == []


def test_a_tarefa_que_falhou_de_vez_e_da_administracao(sessao: Session) -> None:
    tarefas_de_fundo.enfileirar(
        sessao, "enviar_mensagem", {"mensagem_id": 1}, chave="mensagem:1", agora=AGORA
    )
    tarefa = sessao.scalars(select(tarefas_de_fundo.TarefaDeFundo)).one()
    tarefa.situacao, tarefa.ultimo_erro = "falhou", "RuntimeError: a Meta respondeu 500"
    sessao.flush()

    alertas.conferir(sessao, agora=AGORA)

    (alerta,) = sessao.scalars(select(Alerta))
    assert (alerta.tipo, alerta.chave, alerta.empresa_id, alerta.site_id) == (
        "tarefa_falhou", f"tarefa:{tarefa.id}", None, None,
    )  # fmt: skip
    assert alerta.texto == (
        f"A tarefa {tarefa.id} (enviar_mensagem) falhou de vez: RuntimeError: a Meta respondeu 500"
    )


# --- Quem vê --------------------------------------------------------------------------------


def test_cada_empresa_ve_os_alertas_dos_sites_dela(
    sessao: Session,
    cenario: Demonstracao,
    acesso_a: Acesso,
    acesso_b: Acesso,
    site_a: SiteDaVisita,
) -> None:
    _chegar(sessao, site_a, "ABC1D23", timedelta(hours=6))
    # O gestor A só está ligado ao site_a: o outro site da mesma empresa não aparece.
    site_a2 = SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a2.id)
    _chegar(sessao, site_a2, "BRA2E19", timedelta(hours=6))
    alertas.conferir(sessao, agora=AGORA)

    assert [alerta.tipo for alerta in alertas.abertos(sessao, acesso_a)] == ["estadia_passou"]
    assert alertas.abertos(sessao, acesso_b) == []


def test_os_recentes_trazem_os_fechados_das_ultimas_24_horas(
    sessao: Session, acesso_a: Acesso, site_a: SiteDaVisita
) -> None:
    antiga = _chegar(sessao, site_a, "ABC1D23", timedelta(hours=40))
    alertas.conferir(sessao, agora=AGORA - timedelta(hours=30))
    _sair(sessao, antiga, AGORA - timedelta(hours=25))
    alertas.conferir(sessao, agora=AGORA - timedelta(hours=25))
    recente = _chegar(sessao, site_a, "BRA2E19", timedelta(hours=6))
    alertas.conferir(sessao, agora=AGORA - timedelta(hours=1))
    _sair(sessao, recente, AGORA)
    alertas.conferir(sessao, agora=AGORA)

    lista = alertas.recentes(sessao, acesso_a, agora=AGORA)

    assert [alerta.chave for alerta in lista] == [f"visita:{recente.id}"]


def test_a_administracao_ve_a_caixa_a_camera_e_as_tarefas(
    sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa, site_a: SiteDaVisita
) -> None:
    _chegar(sessao, site_a, "ABC1D23", timedelta(hours=6))
    _saude(sessao, caixa, AGORA - timedelta(minutes=5))
    alertas.conferir(sessao, agora=AGORA)

    lista = alertas.abertos_da_administracao(
        sessao, AcessoAdmin(administrador_id=cenario.administrador.id)
    )

    assert [alerta.tipo for alerta in lista] == ["caixa_sem_contato"]


def test_a_administracao_sabe_a_empresa_e_o_site_de_cada_alerta(
    sessao: Session, cenario: Demonstracao, caixa: AcessoDaCaixa
) -> None:
    _saude(sessao, caixa, AGORA - timedelta(minutes=5))
    tarefas_de_fundo.enfileirar(sessao, "enviar_mensagem", {}, chave="m:1", agora=AGORA)
    sessao.execute(update(tarefas_de_fundo.TarefaDeFundo).values(situacao="falhou"))
    alertas.conferir(sessao, agora=AGORA)
    administracao = AcessoAdmin(administrador_id=cenario.administrador.id)
    da_caixa, da_tarefa = sorted(
        alertas.abertos_da_administracao(sessao, administracao), key=lambda a: a.tipo
    )

    lugares = alertas.lugares_da_administracao(sessao, administracao, [da_tarefa, da_caixa])

    assert lugares == {
        da_caixa.id: alertas.Lugar(
            empresa=cenario.empresa_a.nome, site=cenario.site_a.nome, fuso=cenario.site_a.fuso
        )
    }


# --- O WhatsApp de quem autorizou -----------------------------------------------------------


def _autorizar(sessao: Session, quem: Acesso | AcessoAdmin, celular: str) -> None:
    codigo = alertas.pedir_codigo(sessao, quem, agora=AGORA)
    assert alertas.autorizar_pelo_codigo(
        sessao, codigo=codigo, celular=celular, texto=f"ALERTAS {codigo}",
        id_no_whatsapp=f"wamid.{celular}", agora=AGORA + timedelta(minutes=1),
    )  # fmt: skip


def test_o_codigo_liga_o_celular_a_quem_pediu(sessao: Session, acesso_a: Acesso) -> None:
    codigo = alertas.pedir_codigo(sessao, acesso_a, agora=AGORA)

    ligado = alertas.autorizar_pelo_codigo(
        sessao, codigo=codigo.lower(), celular=CELULAR_DO_GESTOR, texto=f"alertas {codigo}",
        id_no_whatsapp="wamid.1", agora=AGORA + timedelta(minutes=9),
    )  # fmt: skip

    assert ligado
    (autorizacao,) = sessao.scalars(select(AlertasNoWhatsApp))
    assert (autorizacao.usuario_id, autorizacao.celular) == (acesso_a.usuario_id, CELULAR_DO_GESTOR)
    assert codigo not in autorizacao.codigo_resumo  # só o resumo


@pytest.mark.parametrize("problema", ["vencido", "usado", "inventado"])
def test_o_codigo_vencido_usado_ou_inventado_nao_liga(
    sessao: Session, acesso_a: Acesso, problema: str
) -> None:
    codigo = alertas.pedir_codigo(sessao, acesso_a, agora=AGORA)
    quando = AGORA + timedelta(minutes=1)
    if problema == "vencido":
        quando = AGORA + timedelta(minutes=10)
    if problema == "usado":
        alertas.autorizar_pelo_codigo(
            sessao, codigo=codigo, celular=CELULAR_DO_GESTOR, texto="x", id_no_whatsapp="w1",
            agora=quando,
        )  # fmt: skip
    if problema == "inventado":
        codigo = "ZZZZ-ZZZZ"

    ligado = alertas.autorizar_pelo_codigo(
        sessao, codigo=codigo, celular=CELULAR_DA_ADMINISTRACAO, texto="x", id_no_whatsapp="w2",
        agora=quando,
    )  # fmt: skip

    assert not ligado
    assert CELULAR_DA_ADMINISTRACAO not in [
        a.celular for a in sessao.scalars(select(AlertasNoWhatsApp))
    ]


def test_o_porteiro_nao_pede_os_alertas_pelo_whatsapp(
    sessao: Session, cenario: Demonstracao
) -> None:
    from nuvem.cadastro.acesso import acesso_do_usuario
    from nuvem.erros import SemPermissaoError

    porteiro = acesso_do_usuario(sessao, cenario.porteiro_a.id)

    with pytest.raises(SemPermissaoError):
        alertas.pedir_codigo(sessao, porteiro, agora=AGORA)


def test_o_alerta_grave_avisa_o_gestor_e_a_administracao_que_autorizaram(
    sessao: Session,
    cenario: Demonstracao,
    acesso_a: Acesso,
    acesso_b: Acesso,
    caixa: AcessoDaCaixa,
) -> None:
    administracao = AcessoAdmin(administrador_id=cenario.administrador.id)
    _autorizar(sessao, acesso_a, CELULAR_DO_GESTOR)
    _autorizar(sessao, acesso_b, "+5511990000003")  # de outra empresa: não recebe
    _autorizar(sessao, administracao, CELULAR_DA_ADMINISTRACAO)
    _saude(sessao, caixa, AGORA - timedelta(minutes=3))

    alertas.conferir(sessao, agora=AGORA)

    avisos = list(sessao.scalars(select(AvisoDeAlerta).order_by(AvisoDeAlerta.id)))
    assert [(a.celular, a.situacao) for a in avisos] == [
        (CELULAR_DO_GESTOR, "guardado"), (CELULAR_DA_ADMINISTRACAO, "guardado"),
    ]  # fmt: skip
    tarefas = list(
        sessao.scalars(
            select(tarefas_de_fundo.TarefaDeFundo).where(
                tarefas_de_fundo.TarefaDeFundo.tipo == "avisar_alerta"
            )
        )
    )
    assert sorted(t.dados["aviso_id"] for t in tarefas) == sorted(a.id for a in avisos)


def test_o_alerta_que_nao_e_grave_fica_so_no_painel(
    sessao: Session, acesso_a: Acesso, site_a: SiteDaVisita
) -> None:
    _autorizar(sessao, acesso_a, CELULAR_DO_GESTOR)
    _chegar(sessao, site_a, "ABC1D23", timedelta(hours=4, minutes=10))

    alertas.conferir(sessao, agora=AGORA)

    assert _abertos(sessao) == [("estadia_perto", _abertos(sessao)[0][1])]
    assert list(sessao.scalars(select(AvisoDeAlerta))) == []


def test_a_estadia_que_passou_avisa_o_gestor_mas_nao_a_administracao(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, site_a: SiteDaVisita
) -> None:
    _autorizar(sessao, acesso_a, CELULAR_DO_GESTOR)
    _autorizar(
        sessao, AcessoAdmin(administrador_id=cenario.administrador.id), CELULAR_DA_ADMINISTRACAO
    )
    _chegar(sessao, site_a, "ABC1D23", timedelta(hours=6))

    alertas.conferir(sessao, agora=AGORA)

    assert [a.celular for a in sessao.scalars(select(AvisoDeAlerta))] == [CELULAR_DO_GESTOR]


def test_a_tarefa_que_falhou_nao_vai_pelo_whatsapp(sessao: Session, cenario: Demonstracao) -> None:
    _autorizar(sessao, AcessoAdmin(administrador_id=cenario.administrador.id), "+5511990000002")
    tarefas_de_fundo.enfileirar(sessao, "enviar_mensagem", {}, chave="m:1", agora=AGORA)
    sessao.execute(update(tarefas_de_fundo.TarefaDeFundo).values(situacao="falhou"))

    alertas.conferir(sessao, agora=AGORA)

    assert [alerta.tipo for alerta in sessao.scalars(select(Alerta))] == ["tarefa_falhou"]
    assert list(sessao.scalars(select(AvisoDeAlerta))) == []


def test_so_o_gestor_ligado_ao_site_do_alerta_recebe(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    _autorizar(sessao, acesso_a, CELULAR_DO_GESTOR)
    site_a2 = SiteDaVisita(empresa_id=cenario.empresa_a.id, site_id=cenario.site_a2.id)
    _chegar(sessao, site_a2, "ABC1D23", timedelta(hours=6))

    alertas.conferir(sessao, agora=AGORA)

    assert list(sessao.scalars(select(AvisoDeAlerta))) == []


def test_quem_deixou_de_ser_gestor_nao_recebe(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, site_a: SiteDaVisita
) -> None:
    _autorizar(sessao, acesso_a, CELULAR_DO_GESTOR)
    sessao.execute(
        update(Usuario).where(Usuario.id == cenario.gestor_a.id).values(papel="porteiro")
    )
    _chegar(sessao, site_a, "ABC1D23", timedelta(hours=6))

    alertas.conferir(sessao, agora=AGORA)

    assert list(sessao.scalars(select(AvisoDeAlerta))) == []


def test_sair_cancela_os_alertas_pelo_whatsapp(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, site_a: SiteDaVisita
) -> None:
    administracao = AcessoAdmin(administrador_id=cenario.administrador.id)
    _autorizar(sessao, acesso_a, CELULAR_DO_GESTOR)
    _autorizar(sessao, administracao, CELULAR_DA_ADMINISTRACAO)

    assert alertas.revogar_do_celular(sessao, CELULAR_DO_GESTOR, agora=AGORA) == 1
    _chegar(sessao, site_a, "ABC1D23", timedelta(hours=6))
    alertas.conferir(sessao, agora=AGORA)

    assert list(sessao.scalars(select(AvisoDeAlerta))) == []
    # O outro celular continua ligado.
    assert alertas.celular_autorizado(sessao, administracao) == CELULAR_DA_ADMINISTRACAO


def test_a_autorizacao_nova_troca_a_anterior_da_mesma_pessoa(
    sessao: Session, acesso_a: Acesso
) -> None:
    _autorizar(sessao, acesso_a, CELULAR_DO_GESTOR)
    _autorizar(sessao, acesso_a, "+5511990000009")

    ativas = [
        a.celular
        for a in sessao.scalars(
            select(AlertasNoWhatsApp).where(
                AlertasNoWhatsApp.autorizada_em.is_not(None),
                AlertasNoWhatsApp.revogada_em.is_(None),
            )
        )
    ]
    assert ativas == ["+5511990000009"]


def test_a_tela_sabe_o_celular_que_a_pessoa_ligou(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso, acesso_b: Acesso
) -> None:
    administracao = AcessoAdmin(administrador_id=cenario.administrador.id)
    alertas.pedir_codigo(sessao, acesso_b, agora=AGORA)  # pediu e não mandou
    _autorizar(sessao, acesso_a, CELULAR_DO_GESTOR)
    _autorizar(sessao, administracao, CELULAR_DA_ADMINISTRACAO)

    assert alertas.celular_autorizado(sessao, acesso_a) == CELULAR_DO_GESTOR
    assert alertas.celular_autorizado(sessao, administracao) == CELULAR_DA_ADMINISTRACAO
    assert alertas.celular_autorizado(sessao, acesso_b) is None
    # Nem outra pessoa da mesma empresa, nem outra pessoa da administração.
    assert alertas.celular_autorizado(sessao, acesso_do_usuario(sessao, cenario.patio_a.id)) is None
    outro_administrador = AcessoAdmin(administrador_id=cenario.administrador.id + 1000)
    assert alertas.celular_autorizado(sessao, outro_administrador) is None
    alertas.revogar_do_celular(sessao, CELULAR_DO_GESTOR, agora=AGORA)
    assert alertas.celular_autorizado(sessao, acesso_a) is None


# --- O envio do aviso -----------------------------------------------------------------------


class WhatsAppDosAlertas:
    numero = "5511900000000"

    def __init__(self, recusar: bool = False) -> None:
        self.enviados: list[tuple[str, str, str]] = []
        self.respostas: list[tuple[str, str]] = []
        self.recusar = recusar

    def enviar(self, mensagem: Any) -> Envio:
        raise AssertionError("o aviso de alerta não é uma mensagem ao motorista")

    def enviar_alerta(self, para: str, site: str, texto: str) -> Envio:
        if self.recusar:
            raise EnvioRecusadoError("131026", "número sem WhatsApp")
        self.enviados.append((para, site, texto))
        return Envio(id_no_canal=f"wamid.alerta.{len(self.enviados)}")

    def responder(self, para: str, texto: str) -> Envio:
        self.respostas.append((para, texto))
        return Envio(id_no_canal="wamid.resposta")


def _aviso_guardado(sessao: Session, acesso_a: Acesso, site_a: SiteDaVisita) -> AvisoDeAlerta:
    _autorizar(sessao, acesso_a, CELULAR_DO_GESTOR)
    _chegar(sessao, site_a, "ABC1D23", timedelta(hours=6))
    alertas.conferir(sessao, agora=AGORA)
    (aviso,) = sessao.scalars(select(AvisoDeAlerta))
    return aviso


def test_o_aviso_vai_pelo_modelo_do_alerta(
    sessao: Session, acesso_a: Acesso, site_a: SiteDaVisita
) -> None:
    aviso = _aviso_guardado(sessao, acesso_a, site_a)
    whatsapp = WhatsAppDosAlertas()

    alertas.avisar(sessao, Canais(whatsapp=whatsapp), aviso.id, agora=AGORA)

    assert whatsapp.enviados == [
        (CELULAR_DO_GESTOR, "CD Exemplo", "ABC1D23 no site há 6 horas (chegou às 08:00)")
    ]
    assert (aviso.situacao, aviso.id_no_canal, aviso.enviado_em) == (
        "enviado", "wamid.alerta.1", AGORA,
    )  # fmt: skip


def test_o_aviso_recusado_fica_como_falhou(
    sessao: Session, acesso_a: Acesso, site_a: SiteDaVisita
) -> None:
    aviso = _aviso_guardado(sessao, acesso_a, site_a)

    alertas.avisar(sessao, Canais(whatsapp=WhatsAppDosAlertas(recusar=True)), aviso.id, agora=AGORA)

    assert (aviso.situacao, aviso.erro) == ("falhou", "131026: número sem WhatsApp")


def test_sem_o_whatsapp_o_aviso_fica_guardado(
    sessao: Session, acesso_a: Acesso, site_a: SiteDaVisita
) -> None:
    aviso = _aviso_guardado(sessao, acesso_a, site_a)

    alertas.avisar(sessao, Canais(), aviso.id, agora=AGORA)

    assert aviso.situacao == "guardado"


def test_o_aviso_enviado_nao_vai_de_novo(
    sessao: Session, acesso_a: Acesso, site_a: SiteDaVisita
) -> None:
    aviso = _aviso_guardado(sessao, acesso_a, site_a)
    whatsapp = WhatsAppDosAlertas()
    alertas.avisar(sessao, Canais(whatsapp=whatsapp), aviso.id, agora=AGORA)

    alertas.avisar(sessao, Canais(whatsapp=whatsapp), aviso.id, agora=AGORA)

    assert len(whatsapp.enviados) == 1


# --- A mensagem "ALERTAS <código>" que chega pelo WhatsApp ----------------------------------


def _mensagem_recebida(texto: str, *, id_: str = "wamid.R1") -> dict[str, Any]:
    valor = {
        "messages": [
            {
                "from": CELULAR_DO_GESTOR.removeprefix("+"),
                "id": id_,
                "timestamp": str(int(AGORA.timestamp())),
                "type": "text",
                "text": {"body": texto},
            }
        ]
    }
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": valor}]}],
    }


def test_a_mensagem_com_o_codigo_liga_o_celular_e_responde(
    sessao: Session, acesso_a: Acesso
) -> None:
    codigo = alertas.pedir_codigo(sessao, acesso_a, agora=AGORA)
    whatsapp = WhatsAppDosAlertas()

    mensagens.tratar_aviso(
        sessao, Canais(whatsapp=whatsapp), _mensagem_recebida(f"ALERTAS {codigo}"),
        agora=AGORA + timedelta(minutes=1),
    )  # fmt: skip

    (autorizacao,) = sessao.scalars(select(AlertasNoWhatsApp))
    assert (autorizacao.celular, autorizacao.texto) == (CELULAR_DO_GESTOR, f"ALERTAS {codigo}")
    (recebida,) = sessao.scalars(select(MensagemRecebida))
    assert recebida.resultado == "autorizou"
    ((para, resposta),) = whatsapp.respostas
    assert para == CELULAR_DO_GESTOR
    assert "alertas" in resposta.lower()
    assert "SAIR" in resposta


def test_a_mensagem_com_codigo_errado_e_ignorada(sessao: Session, acesso_a: Acesso) -> None:
    alertas.pedir_codigo(sessao, acesso_a, agora=AGORA)
    whatsapp = WhatsAppDosAlertas()

    mensagens.tratar_aviso(
        sessao, Canais(whatsapp=whatsapp), _mensagem_recebida("ALERTAS AAAA-AAAA"), agora=AGORA
    )

    (recebida,) = sessao.scalars(select(MensagemRecebida))
    assert recebida.resultado == "ignorada"
    assert whatsapp.respostas == []


def test_sair_pelo_whatsapp_cancela_tambem_os_alertas(sessao: Session, acesso_a: Acesso) -> None:
    _autorizar(sessao, acesso_a, CELULAR_DO_GESTOR)

    mensagens.tratar_aviso(
        sessao, Canais(), _mensagem_recebida("SAIR", id_="wamid.R2"), agora=AGORA
    )

    (autorizacao,) = sessao.scalars(select(AlertasNoWhatsApp))
    assert autorizacao.revogada_em == AGORA

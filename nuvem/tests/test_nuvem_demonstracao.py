"""A empresa e o dia de demonstração com o banco (T45, D-49)."""

import threading
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nuvem import tarefas_de_fundo as fila
from nuvem.agendamento.modelos import Agendamento
from nuvem.armazenamento import ArmazenamentoLocal
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, acesso_do_usuario
from nuvem.cifra import Cifra
from nuvem.demonstracao import dia as demonstracao
from nuvem.demonstracao import empresa, local
from nuvem.demonstracao.dia import DiaJaComecouError, SiteSemCaixaError
from nuvem.demonstracao.empresa import EmpresaDeDemonstracao
from nuvem.demonstracao.fotos import placa_desenhada
from nuvem.demonstracao.modelos import DiaDeDemonstracao
from nuvem.erros import NaoEncontradoError
from nuvem.extrato import servico as extrato
from nuvem.frota import servico as frota
from nuvem.patio import servico as patio
from nuvem.portaria import visitas
from nuvem.portaria.modelos import Evento, PassagemRecebida, Visita
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita
from nuvem.semente import Demonstracao
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
"""14h de 05/10 em São Paulo."""
ANTES_DE_ABRIR = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)
"""5h em São Paulo: o dia ainda não teve caminhão."""


@pytest.fixture
def demo(
    sessao: Session, senhas: Senhas, cifra: Cifra, cenario: Demonstracao
) -> EmpresaDeDemonstracao:
    """Uma empresa de demonstração com 2 dias de histórico (03/10 e 04/10)."""
    return empresa.criar(
        sessao, senhas, cifra, nome="Empresa de demonstração", cnpj="DEMO0000000T00",
        dominio="teste.demonstracao.example", senha="senha-da-demonstracao", pin="246802",
        administrador_id=cenario.administrador.id, agora=AGORA, dias=2, semente=1,
    )  # fmt: skip


@pytest.fixture
def gestor(sessao: Session, demo: EmpresaDeDemonstracao) -> Acesso:
    return acesso_do_usuario(sessao, demo.gestor.id)


@pytest.fixture
def armazenamento(tmp_path: Path, cifra: Cifra) -> ArmazenamentoLocal:
    return ArmazenamentoLocal(tmp_path / "fotos", cifra)


Rodar = Callable[[datetime, datetime], None]


@pytest.fixture
def rodar(sessao: Session, armazenamento: ArmazenamentoLocal) -> Rodar:
    """Faz o que o worker faz, segundo a segundo, de ``de`` até ``ate``."""

    def _rodar(de: datetime, ate: datetime) -> None:
        momento = de
        while momento <= ate:
            demonstracao.avancar(sessao, agora=momento, armazenamento=armazenamento)
            fila.executar_pendentes(sessao, agora=momento)
            momento += timedelta(seconds=1)

    return _rodar


def _visitas(sessao: Session, demo: EmpresaDeDemonstracao) -> list[Visita]:
    return list(
        sessao.scalars(select(Visita).where(Visita.site_id == demo.site.id).order_by(Visita.id))
    )


def _do_dia(sessao: Session, demo: EmpresaDeDemonstracao) -> DiaDeDemonstracao:
    return sessao.scalars(
        select(DiaDeDemonstracao).where(DiaDeDemonstracao.site_id == demo.site.id)
    ).one()


# --- A empresa de demonstração ----------------------------------------------------------------


def test_a_empresa_de_demonstracao_tem_um_site_completo(
    sessao: Session, demo: EmpresaDeDemonstracao, gestor: Acesso
) -> None:
    assert demo.site.nome == "CD Demonstração"
    assert len(cadastro.listar_docas(sessao, gestor, demo.site.id)) == 6
    assert [p.papel for p in (demo.gestor, demo.porteiro, demo.lider)] == [
        "gestor", "porteiro", "patio",
    ]  # fmt: skip
    caixa = frota.caixa_do_site(sessao, empresa_id=demo.empresa.id, site_id=demo.site.id)
    assert caixa is not None and caixa.caixa_id == demo.caixa_id
    assert extrato.parametros(sessao, gestor, demo.site.id) == empresa.PARAMETROS


def test_o_historico_sao_dias_fechados(sessao: Session, demo: EmpresaDeDemonstracao) -> None:
    lidas = _visitas(sessao, demo)

    assert {v.estado for v in lidas} == {"SAIU"}
    dias = {
        v.chegou_em.astimezone(ZoneInfo("America/Sao_Paulo")).date() for v in lidas if v.chegou_em
    }
    assert dias == {date(2026, 10, 3), date(2026, 10, 4)}
    eventos = sessao.scalar(
        select(func.count()).select_from(Evento).where(Evento.visita_id.in_([v.id for v in lidas]))
    )
    assert eventos == 5 * len(lidas)  # check-in, chamada, início, fim e saída
    pelo_porteiro = sessao.scalar(
        select(func.count())
        .select_from(Evento)
        .where(Evento.tipo == "check_in", Evento.usuario_id == demo.porteiro.id)
    )
    assert pelo_porteiro  # nem todo check-in é automático


def test_os_celulares_sao_de_um_ddd_que_nao_existe(
    sessao: Session, demo: EmpresaDeDemonstracao
) -> None:
    celulares = sessao.scalars(
        select(Agendamento.motorista_celular).where(Agendamento.site_id == demo.site.id)
    ).all()

    assert celulares and all(c is not None and c.startswith("+55239") for c in celulares)


def test_a_linha_de_base_de_exemplo_e_pior_que_o_historico(
    sessao: Session, demo: EmpresaDeDemonstracao, gestor: Acesso
) -> None:
    outubro = extrato.do_mes(sessao, gestor, demo.site.id, date(2026, 10, 1), agora=AGORA)

    assert outubro.linha_de_base is not None and outubro.linha_de_base.origem == "exemplo"
    base, mes = outubro.linha_de_base.medidas, outubro.medidas
    assert base.espera_media is not None and mes.espera_media is not None
    assert base.espera_media > mes.espera_media + timedelta(hours=1)
    assert base.automaticas == 0  # antes do sistema, nada era automático
    assert outubro.economia is not None and outubro.economia.total > 0


# --- Começar o dia ----------------------------------------------------------------------------


def test_comecar_grava_a_manha_ate_agora(
    sessao: Session, demo: EmpresaDeDemonstracao, gestor: Acesso
) -> None:
    antes = len(_visitas(sessao, demo))

    demonstracao.comecar(sessao, gestor, demo.site.id, agora=AGORA, semente=2)

    de_hoje = _visitas(sessao, demo)[antes:]
    assert de_hoje and all(v.chegou_em is not None and v.chegou_em <= AGORA for v in de_hoje)
    assert {"SAIU", "NA_FILA"} <= {v.estado for v in de_hoje}
    ocupadas = [v.doca_id for v in de_hoje if v.estado in ("CHAMADA", "NA_DOCA")]
    assert len(ocupadas) == len(set(ocupadas))


def test_comecar_monta_as_chegadas_ao_vivo_com_uma_errada(
    sessao: Session, demo: EmpresaDeDemonstracao, gestor: Acesso
) -> None:
    dia = demonstracao.comecar(sessao, gestor, demo.site.id, agora=AGORA, semente=2)

    assert len(dia.chegadas) == demonstracao.AO_VIVO
    assert dia.termina_em == AGORA + demonstracao.DURACAO
    erradas = [i for i, c in enumerate(dia.chegadas) if c["placa"] != c["lida"]]
    assert erradas == [demonstracao.CHEGADA_ERRADA]
    primeira = datetime.fromisoformat(dia.chegadas[0]["em"])
    assert primeira == AGORA + demonstracao.PRIMEIRA_CHEGADA


def test_comecar_fecha_o_que_ficou_aberto(
    sessao: Session, demo: EmpresaDeDemonstracao, gestor: Acesso
) -> None:
    site = SiteDaVisita(empresa_id=demo.empresa.id, site_id=demo.site.id)
    ontem = visitas.abrir_visita(
        sessao, site, "aceita_sem_agendamento", momento=AGORA - timedelta(days=1),
        agora=AGORA - timedelta(days=1),
        composicao=(PlacaNaVisita(placa="ABC1D23", papel="cavalo", como="lida"),),
    )  # fmt: skip

    demonstracao.comecar(sessao, gestor, demo.site.id, agora=AGORA, semente=2)

    assert (ontem.estado, ontem.saiu_em) == ("SAIU", AGORA)


def test_nao_comeca_dois_dias_ao_mesmo_tempo(
    sessao: Session, demo: EmpresaDeDemonstracao, gestor: Acesso
) -> None:
    demonstracao.comecar(sessao, gestor, demo.site.id, agora=AGORA, semente=2)

    with pytest.raises(DiaJaComecouError):
        demonstracao.comecar(sessao, gestor, demo.site.id, agora=AGORA, semente=3)


def test_site_sem_caixa_nao_comeca(
    sessao: Session, cenario: Demonstracao, acesso_a: Acesso
) -> None:
    with pytest.raises(SiteSemCaixaError):
        demonstracao.comecar(sessao, acesso_a, cenario.site_a.id, agora=AGORA)


def test_site_de_outra_empresa_responde_nao_encontrado(
    sessao: Session, demo: EmpresaDeDemonstracao, acesso_a: Acesso
) -> None:
    with pytest.raises(NaoEncontradoError):
        demonstracao.comecar(sessao, acesso_a, demo.site.id, agora=AGORA)


# --- O dia ao vivo ----------------------------------------------------------------------------


def test_as_chegadas_vao_pelo_caminho_da_caixa_com_a_foto(
    sessao: Session,
    demo: EmpresaDeDemonstracao,
    gestor: Acesso,
    armazenamento: ArmazenamentoLocal,
) -> None:
    dia = demonstracao.comecar(sessao, gestor, demo.site.id, agora=AGORA, semente=2)
    tres = AGORA + demonstracao.PRIMEIRA_CHEGADA + 2 * demonstracao.ENTRE_CHEGADAS

    demonstracao.avancar(sessao, agora=tres, armazenamento=armazenamento)

    assert dia.enviadas == 3
    passagens = list(
        sessao.scalars(
            select(PassagemRecebida)
            .where(PassagemRecebida.site_id == demo.site.id)
            .order_by(PassagemRecebida.recebida_em, PassagemRecebida.inicio)
        )
    )
    assert len(passagens) == 3
    primeira = passagens[0].como_veio
    assert primeira["placas"][0]["placa"] == dia.chegadas[0]["placa"]
    foto = armazenamento.ler(demo.caixa_id, primeira["fotos"][0]["ref"])
    assert foto == placa_desenhada(dia.chegadas[0]["placa"])


def test_a_chegada_errada_vira_excecao_e_a_foto_mostra_a_placa_certa(
    sessao: Session,
    demo: EmpresaDeDemonstracao,
    gestor: Acesso,
    armazenamento: ArmazenamentoLocal,
    rodar: Rodar,
) -> None:
    dia = demonstracao.comecar(sessao, gestor, demo.site.id, agora=ANTES_DE_ABRIR, semente=2)
    errada = dia.chegadas[demonstracao.CHEGADA_ERRADA]

    rodar(ANTES_DE_ABRIR, datetime.fromisoformat(errada["em"]))

    [excecao] = visitas.excecoes_abertas(sessao, gestor, demo.site.id)
    passagem = sessao.get_one(PassagemRecebida, excecao.passagem_id)
    assert passagem.como_veio["placas"][0]["placa"] == errada["lida"]
    foto = armazenamento.ler(demo.caixa_id, passagem.como_veio["fotos"][0]["ref"])
    assert foto == placa_desenhada(errada["placa"])


def test_o_lider_chama_comeca_termina_e_manda_a_saida(
    sessao: Session, demo: EmpresaDeDemonstracao, gestor: Acesso, rodar: Rodar
) -> None:
    dia = demonstracao.comecar(sessao, gestor, demo.site.id, agora=ANTES_DE_ABRIR, semente=2)

    rodar(ANTES_DE_ABRIR, ANTES_DE_ABRIR + timedelta(minutes=2))

    primeira = next(
        v for v in _visitas(sessao, demo)
        if v.composicao[0]["placa"] == dia.chegadas[0]["placa"]
    )  # fmt: skip
    assert primeira.estado == "SAIU"
    eventos = visitas.eventos_da_visita(sessao, gestor, primeira.id)
    assert [e.tipo for e in eventos] == [
        "check_in", "chamada", "inicio_na_doca", "fim_na_doca", "saiu",
    ]  # fmt: skip
    assert {e.usuario_id for e in eventos[1:4]} == {demo.lider.id}


def test_o_lider_da_tempo_de_cada_etapa_aparecer_na_tela(
    sessao: Session, demo: EmpresaDeDemonstracao, gestor: Acesso, rodar: Rodar
) -> None:
    dia = demonstracao.comecar(sessao, gestor, demo.site.id, agora=ANTES_DE_ABRIR, semente=2)

    rodar(ANTES_DE_ABRIR, ANTES_DE_ABRIR + timedelta(minutes=2))

    primeira = next(
        v for v in _visitas(sessao, demo) if v.composicao[0]["placa"] == dia.chegadas[0]["placa"]
    )
    assert primeira.chegou_em and primeira.chamada_em and primeira.na_doca_em
    assert primeira.liberada_em and primeira.saiu_em
    assert primeira.chamada_em - primeira.chegou_em >= demonstracao.NA_FILA_HA
    assert primeira.na_doca_em - primeira.chamada_em >= demonstracao.CHAMADO_HA
    assert primeira.liberada_em - primeira.na_doca_em >= demonstracao.NA_DOCA_HA
    # a passagem de saída começa 6 s antes de ser mandada
    assert primeira.saiu_em - primeira.liberada_em >= demonstracao.LIBERADO_HA - timedelta(
        seconds=6
    )


def test_o_lider_so_termina_quem_esta_na_doca_ha_30_segundos(
    sessao: Session,
    demo: EmpresaDeDemonstracao,
    gestor: Acesso,
    armazenamento: ArmazenamentoLocal,
) -> None:
    demonstracao.comecar(sessao, gestor, demo.site.id, agora=ANTES_DE_ABRIR, semente=2)
    site = SiteDaVisita(empresa_id=demo.empresa.id, site_id=demo.site.id)
    antes = ANTES_DE_ABRIR - timedelta(minutes=10)
    visita = visitas.abrir_visita(
        sessao, site, "aceita_sem_agendamento", momento=antes, agora=antes,
        composicao=(PlacaNaVisita(placa="ABC1D23", papel="cavalo", como="lida"),),
    )  # fmt: skip
    [doca, *_] = cadastro.listar_docas(sessao, gestor, demo.site.id)
    patio.chamar(sessao, gestor, visita.id, doca.id, agora=antes)
    patio.iniciar(sessao, gestor, visita.id, agora=ANTES_DE_ABRIR - timedelta(seconds=29))

    demonstracao.avancar(sessao, agora=ANTES_DE_ABRIR, armazenamento=armazenamento)
    estado_aos_29 = visita.estado
    demonstracao.avancar(
        sessao, agora=ANTES_DE_ABRIR + timedelta(seconds=1), armazenamento=armazenamento
    )

    assert (estado_aos_29, visita.estado) == ("NA_DOCA", "LIBERADA")


def test_a_saida_e_mandada_uma_vez_so(
    sessao: Session,
    demo: EmpresaDeDemonstracao,
    gestor: Acesso,
    armazenamento: ArmazenamentoLocal,
    rodar: Rodar,
) -> None:
    dia = demonstracao.comecar(sessao, gestor, demo.site.id, agora=ANTES_DE_ABRIR, semente=2)
    # Até a primeira ser liberada, sem mandar ninguém à saída ainda.
    rodar(ANTES_DE_ABRIR, ANTES_DE_ABRIR + timedelta(seconds=75))
    saidas_antes = len(dia.saidas)

    # O worker atrasa o casamento: o líder volta duas vezes antes de a saída casar.
    for segundos in (100, 110):
        demonstracao.avancar(
            sessao, agora=ANTES_DE_ABRIR + timedelta(seconds=segundos), armazenamento=armazenamento
        )

    passagens_de_saida = sessao.scalar(
        select(func.count())
        .select_from(PassagemRecebida)
        .where(PassagemRecebida.site_id == demo.site.id, PassagemRecebida.sentido == "saida")
    )
    assert passagens_de_saida == len(dia.saidas) == saidas_antes + 1


def test_o_lider_faz_uma_coisa_de_cada_vez(
    sessao: Session, demo: EmpresaDeDemonstracao, gestor: Acesso, rodar: Rodar
) -> None:
    demonstracao.comecar(sessao, gestor, demo.site.id, agora=AGORA, semente=2)
    inicio = AGORA + timedelta(seconds=1)

    rodar(inicio, inicio + timedelta(seconds=30))

    do_lider = sessao.scalars(
        select(Evento.registrado_em).where(
            Evento.usuario_id == demo.lider.id, Evento.registrado_em >= inicio
        )
    ).all()
    assert do_lider
    momentos = sorted(do_lider)
    assert all(b - a >= demonstracao.LIDER_A_CADA for a, b in pairwise(momentos))


def test_o_dia_acaba_depois_de_5_minutos(
    sessao: Session,
    demo: EmpresaDeDemonstracao,
    gestor: Acesso,
    armazenamento: ArmazenamentoLocal,
) -> None:
    demonstracao.comecar(sessao, gestor, demo.site.id, agora=AGORA, semente=2)
    fim = AGORA + demonstracao.DURACAO

    demonstracao.avancar(sessao, agora=fim - timedelta(seconds=1), armazenamento=armazenamento)
    rodando = demonstracao.andamento(sessao, gestor, demo.site.id)
    demonstracao.avancar(sessao, agora=fim, armazenamento=armazenamento)
    acabou = demonstracao.andamento(sessao, gestor, demo.site.id)

    assert rodando is not None and rodando.rodando
    assert rodando.enviadas == rodando.chegadas == demonstracao.AO_VIVO
    assert acabou is not None and not acabou.rodando


def test_a_pessoa_mexer_no_mesmo_caminhao_nao_derruba_o_dia(
    sessao: Session,
    demo: EmpresaDeDemonstracao,
    gestor: Acesso,
    armazenamento: ArmazenamentoLocal,
    rodar: Rodar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dia = demonstracao.comecar(sessao, gestor, demo.site.id, agora=ANTES_DE_ABRIR, semente=2)
    # A primeira chegou (pela passagem) em +2 s; o líder poderia chamá-la a partir de +14 s.
    rodar(ANTES_DE_ABRIR, ANTES_DE_ABRIR + timedelta(seconds=13))

    def a_pessoa_chamou_antes(*_args: object, **_kwargs: object) -> None:
        raise visitas.TransicaoInvalidaError("o caminhão já mudou de situação")

    monkeypatch.setattr(patio, "chamar", a_pessoa_chamou_antes)
    demonstracao.avancar(
        sessao, agora=ANTES_DE_ABRIR + timedelta(seconds=18), armazenamento=armazenamento
    )

    assert dia.enviadas == 2  # a chegada da volta ficou
    assert dia.ultima_acao_em is None  # a ação do líder foi desfeita
    de_agora = [v for v in _visitas(sessao, demo) if v.chegou_em and v.chegou_em >= ANTES_DE_ABRIR]
    assert {v.estado for v in de_agora} == {"NA_FILA"}


def test_sem_dia_nao_ha_andamento(
    sessao: Session, demo: EmpresaDeDemonstracao, gestor: Acesso
) -> None:
    assert demonstracao.andamento(sessao, gestor, demo.site.id) is None


def test_o_worker_avanca_a_demonstracao(sessao: Session) -> None:
    chamadas: list[datetime] = []
    parar = threading.Event()

    def dormir(_segundos: float) -> None:
        parar.set()

    def avancar(_sessao: Session, agora: datetime) -> int:
        chamadas.append(agora)
        return 0

    fila.rodar(lambda: sessao, parar, relogio=lambda: AGORA, dormir=dormir, demonstracao=avancar)

    assert chamadas == [AGORA]


# --- A empresa do ambiente local --------------------------------------------------------------


def test_a_empresa_local_precisa_da_semente(sessao: Session, senhas: Senhas, cifra: Cifra) -> None:
    with pytest.raises(local.SemSementeError):
        local.criar_a_local(sessao, senhas, cifra, agora=AGORA, dias=1)


def test_a_empresa_local_e_criada_uma_vez(
    sessao: Session, senhas: Senhas, cifra: Cifra, cenario: Demonstracao
) -> None:
    criada = local.criar_a_local(sessao, senhas, cifra, agora=AGORA, dias=1)

    assert criada is not None and criada.empresa.cnpj == local.CNPJ_LOCAL
    assert criada.gestor.email == "gestor@demonstracao.example"
    assert local.criar_a_local(sessao, senhas, cifra, agora=AGORA, dias=1) is None

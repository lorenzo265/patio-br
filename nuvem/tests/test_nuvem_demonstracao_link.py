"""O link de demonstração por empresa (T48, D-52 e D-54): gerar, entrar, trocar e apagar."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nuvem import tarefas_de_fundo
from nuvem.agendamento.modelos import Agendamento
from nuvem.armazenamento import ArmazenamentoLocal
from nuvem.banco import Base, sqlstate
from nuvem.cadastro import login
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, AcessoAdmin, acesso_do_usuario
from nuvem.cadastro.modelos import Empresa, Usuario
from nuvem.cifra import Cifra
from nuvem.demonstracao import dia, empresa
from nuvem.demonstracao import link as demonstracao
from nuvem.demonstracao.link import LinkGerado
from nuvem.demonstracao.modelos import LinkDemonstracao
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.extrato import servico as extrato
from nuvem.mensagens import servico as mensagens
from nuvem.portaria.modelos import Evento, PassagemRecebida
from nuvem.semente import SENHA_DA_DEMONSTRACAO, Demonstracao
from nuvem.senhas import Senhas, resumo_rapido

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
"""14h em São Paulo."""
RECUSA_DA_PROVA = "23001"
"""O código do gatilho ``so_acrescenta`` (restrict_violation)."""


@pytest.fixture(autouse=True)
def _historico_curto(monkeypatch: pytest.MonkeyPatch) -> None:
    # Dois dias de histórico bastam; os 35 de verdade levam segundos.
    monkeypatch.setattr(empresa, "DIAS_DE_HISTORICO", 2)


@pytest.fixture
def administracao(cenario: Demonstracao) -> AcessoAdmin:
    return AcessoAdmin(administrador_id=cenario.administrador.id)


def _gerar(
    sessao: Session, administracao: AcessoAdmin, nome: str = "Transportes Exemplo"
) -> LinkGerado:
    return demonstracao.gerar_link(sessao, administracao, nome=nome, agora=AGORA)


def _entrar(
    sessao: Session, senhas: Senhas, cifra: Cifra, codigo: str, agora: datetime = AGORA
) -> str:
    return demonstracao.entrar_pelo_link(sessao, senhas, cifra, codigo, agora=agora)


def _quem(sessao: Session, codigo_da_sessao: str, agora: datetime = AGORA) -> Usuario:
    conta = login.conta_da_sessao(sessao, codigo_da_sessao, agora)
    assert isinstance(conta, Usuario)
    return conta


def _dias_com_agendamento(sessao: Session, empresa_id: int) -> set[date]:
    dia_no_site = func.date(func.timezone("America/Sao_Paulo", Agendamento.janela_inicio))
    consulta = select(dia_no_site).where(Agendamento.empresa_id == empresa_id).distinct()
    return set(sessao.scalars(consulta))


# --- Gerar e abrir ----------------------------------------------------------------------------


def test_gerar_guarda_so_o_resumo_e_vale_sete_dias(
    sessao: Session, administracao: AcessoAdmin
) -> None:
    gerado = _gerar(sessao, administracao)

    assert len(gerado.codigo) >= 32
    assert gerado.link.codigo_resumo == resumo_rapido(gerado.codigo)
    assert gerado.link.vence_em == AGORA + timedelta(days=7)
    assert gerado.link.empresa_id is None
    assert gerado.codigo not in str(sessao.execute(select(LinkDemonstracao.__table__)).all())


@pytest.mark.parametrize("nome", ["", "   ", "x" * 121])
def test_nome_vazio_ou_longo_demais_e_recusado(
    sessao: Session, administracao: AcessoAdmin, nome: str
) -> None:
    with pytest.raises(DadoInvalidoError):
        _gerar(sessao, administracao, nome)


def test_link_que_vale_abre(sessao: Session, administracao: AcessoAdmin) -> None:
    gerado = _gerar(sessao, administracao, "  Transportes Exemplo  ")

    aberto = demonstracao.abrir_link(sessao, gerado.codigo, agora=AGORA + timedelta(days=6))

    assert aberto.nome == "Transportes Exemplo"


def test_link_vencido_revogado_ou_inventado_nao_e_encontrado(
    sessao: Session, administracao: AcessoAdmin
) -> None:
    vencido = _gerar(sessao, administracao)
    revogado = _gerar(sessao, administracao)
    demonstracao.revogar_link(sessao, administracao, revogado.link.id, agora=AGORA)

    for codigo, quando in (
        (vencido.codigo, AGORA + timedelta(days=7)),
        (revogado.codigo, AGORA),
        ("codigo-inventado", AGORA),
    ):
        with pytest.raises(NaoEncontradoError):
            demonstracao.abrir_link(sessao, codigo, agora=quando)


def test_listar_mostra_os_links_do_mais_novo_ao_mais_antigo(
    sessao: Session, administracao: AcessoAdmin
) -> None:
    primeiro = _gerar(sessao, administracao, "Primeira")
    segundo = _gerar(sessao, administracao, "Segunda")

    links = demonstracao.listar_links(sessao, administracao)

    assert [link.id for link in links] == [segundo.link.id, primeiro.link.id]


# --- Entrar -----------------------------------------------------------------------------------


def test_a_primeira_entrada_cria_a_empresa_e_entra_como_gestor(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin
) -> None:
    gerado = _gerar(sessao, administracao)

    gestor = _quem(sessao, _entrar(sessao, senhas, cifra, gerado.codigo))

    assert gestor.papel == "gestor"
    assert gerado.link.empresa_id == gestor.empresa_id
    assert gerado.link.ultima_entrada_em == AGORA
    nome = sessao.get(Empresa, gestor.empresa_id)
    assert nome is not None
    assert nome.nome == "Transportes Exemplo (demonstração)"
    hoje = date(2026, 10, 5)
    assert _dias_com_agendamento(sessao, gestor.empresa_id) == {
        hoje - timedelta(days=2), hoje - timedelta(days=1),
    }  # fmt: skip


def test_quem_volta_entra_na_mesma_empresa(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin
) -> None:
    gerado = _gerar(sessao, administracao)
    primeira = _quem(sessao, _entrar(sessao, senhas, cifra, gerado.codigo))
    empresas = sessao.scalar(select(func.count()).select_from(Empresa))

    segunda = _quem(sessao, _entrar(sessao, senhas, cifra, gerado.codigo))

    assert segunda.id == primeira.id
    assert sessao.scalar(select(func.count()).select_from(Empresa)) == empresas


def test_a_entrada_completa_os_dias_que_faltam_ate_ontem(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin
) -> None:
    gerado = _gerar(sessao, administracao)
    gestor = _quem(sessao, _entrar(sessao, senhas, cifra, gerado.codigo))
    tres_dias_depois = AGORA + timedelta(days=3)

    _entrar(sessao, senhas, cifra, gerado.codigo, tres_dias_depois)

    hoje = date(2026, 10, 5)
    assert _dias_com_agendamento(sessao, gestor.empresa_id) == {
        hoje + timedelta(days=n) for n in range(-2, 3)
    }


def test_quem_ja_tem_os_dias_ate_ontem_nao_ganha_mais_nada(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin
) -> None:
    gerado = _gerar(sessao, administracao)
    gestor = _quem(sessao, _entrar(sessao, senhas, cifra, gerado.codigo))
    agendamentos = sessao.scalar(select(func.count()).select_from(Agendamento))

    _entrar(sessao, senhas, cifra, gerado.codigo, AGORA + timedelta(hours=1))

    assert sessao.scalar(select(func.count()).select_from(Agendamento)) == agendamentos
    assert gestor.ativo


def test_as_pessoas_da_empresa_do_link_nao_entram_com_senha(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin
) -> None:
    gerado = _gerar(sessao, administracao)
    gestor = _quem(sessao, _entrar(sessao, senhas, cifra, gerado.codigo))

    with pytest.raises(login.LoginRecusadoError):
        login.entrar(sessao, senhas, email=gestor.email, senha=SENHA_DA_DEMONSTRACAO, agora=AGORA)


def test_dois_links_sao_duas_empresas_que_nao_se_veem(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin
) -> None:
    um = _quem(sessao, _entrar(sessao, senhas, cifra, _gerar(sessao, administracao, "Um").codigo))
    outro = _quem(
        sessao, _entrar(sessao, senhas, cifra, _gerar(sessao, administracao, "Outro").codigo)
    )
    acesso_de_um = acesso_do_usuario(sessao, um.id)
    (site_do_outro,) = cadastro.listar_sites(sessao, acesso_do_usuario(sessao, outro.id))

    assert um.empresa_id != outro.empresa_id
    with pytest.raises(NaoEncontradoError):
        cadastro.obter_site(sessao, acesso_de_um, site_do_outro.id)


def test_revogar_desliga_as_pessoas_da_empresa_na_hora(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin
) -> None:
    gerado = _gerar(sessao, administracao)
    codigo_da_sessao = _entrar(sessao, senhas, cifra, gerado.codigo)

    demonstracao.revogar_link(sessao, administracao, gerado.link.id, agora=AGORA)

    assert login.conta_da_sessao(sessao, codigo_da_sessao, AGORA) is None
    with pytest.raises(NaoEncontradoError):
        _entrar(sessao, senhas, cifra, gerado.codigo)


def test_revogar_link_que_nao_existe_nao_e_encontrado(
    sessao: Session, administracao: AcessoAdmin
) -> None:
    with pytest.raises(NaoEncontradoError):
        demonstracao.revogar_link(sessao, administracao, 999_999, agora=AGORA)


# --- Trocar de papel --------------------------------------------------------------------------


def _acesso(sessao: Session, codigo_da_sessao: str) -> Acesso:
    return acesso_do_usuario(sessao, _quem(sessao, codigo_da_sessao).id)


def test_trocar_de_papel_leva_a_outra_pessoa_da_mesma_empresa(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin
) -> None:
    codigo_do_gestor = _entrar(sessao, senhas, cifra, _gerar(sessao, administracao).codigo)
    gestor = _quem(sessao, codigo_do_gestor)

    codigo_do_porteiro = demonstracao.trocar_de_papel(
        sessao, _acesso(sessao, codigo_do_gestor), codigo=codigo_do_gestor, papel="porteiro",
        agora=AGORA,
    )  # fmt: skip
    porteiro = _quem(sessao, codigo_do_porteiro)
    codigo_do_lider = demonstracao.trocar_de_papel(
        sessao, _acesso(sessao, codigo_do_porteiro), codigo=codigo_do_porteiro, papel="patio",
        agora=AGORA,
    )  # fmt: skip

    assert (porteiro.papel, porteiro.empresa_id) == ("porteiro", gestor.empresa_id)
    assert _quem(sessao, codigo_do_lider).papel == "patio"
    assert login.conta_da_sessao(sessao, codigo_do_gestor, AGORA) is None
    assert login.conta_da_sessao(sessao, codigo_do_porteiro, AGORA) is None


def test_trocar_para_o_proprio_papel_nao_muda_a_sessao(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin
) -> None:
    codigo = _entrar(sessao, senhas, cifra, _gerar(sessao, administracao).codigo)

    mesmo = demonstracao.trocar_de_papel(
        sessao, _acesso(sessao, codigo), codigo=codigo, papel="gestor", agora=AGORA
    )

    assert mesmo == codigo


def test_sem_ninguem_do_papel_nos_sites_dele_nao_troca(
    sessao: Session, senhas: Senhas, cenario: Demonstracao, acesso_b: Acesso
) -> None:
    # A empresa B da semente não tem líder de pátio.
    codigo = login.entrar(
        sessao, senhas, email=cenario.gestor_b.email, senha=SENHA_DA_DEMONSTRACAO, agora=AGORA
    )

    with pytest.raises(NaoEncontradoError):
        demonstracao.trocar_de_papel(sessao, acesso_b, codigo=codigo, papel="patio", agora=AGORA)


# --- Apagar -----------------------------------------------------------------------------------


def _empresa_com_tudo(
    sessao: Session,
    senhas: Senhas,
    cifra: Cifra,
    administracao: AcessoAdmin,
    armazenamento: ArmazenamentoLocal,
) -> tuple[LinkGerado, Acesso]:
    """Uma empresa de link com o dia rodado: passagens, fotos, eventos, mensagens e extrato."""
    gerado = _gerar(sessao, administracao)
    acesso = _acesso(sessao, _entrar(sessao, senhas, cifra, gerado.codigo))
    (site,) = cadastro.listar_sites(sessao, acesso)
    dia.comecar(sessao, acesso, site.id, agora=AGORA, semente=7)
    for segundos in range(0, 60, 2):
        momento = AGORA + timedelta(seconds=segundos)
        dia.avancar(sessao, agora=momento, armazenamento=armazenamento)
        tarefas_de_fundo.executar_pendentes(sessao, agora=momento)
    mensagens.preparar(sessao, agora=AGORA + timedelta(minutes=1))
    extrato.do_mes(sessao, acesso, site.id, date(2026, 9, 1), agora=AGORA)
    sessao.flush()
    return gerado, acesso


def _linhas_da_empresa(sessao: Session, empresa_id: int) -> dict[str, int]:
    contagens = {}
    for tabela in Base.metadata.sorted_tables:
        if "empresa_id" in tabela.c and tabela.name != LinkDemonstracao.__tablename__:
            consulta = select(func.count()).select_from(tabela)
            contagens[tabela.name] = sessao.scalar(
                consulta.where(tabela.c.empresa_id == empresa_id)
            )
    return {nome: quantas for nome, quantas in contagens.items() if quantas}


def test_a_empresa_vencida_e_apagada_inteira(
    sessao: Session,
    senhas: Senhas,
    cifra: Cifra,
    administracao: AcessoAdmin,
    cenario: Demonstracao,
    tmp_path: Path,
) -> None:
    armazenamento = ArmazenamentoLocal(tmp_path / "fotos", cifra)
    gerado, acesso = _empresa_com_tudo(sessao, senhas, cifra, administracao, armazenamento)
    antes = _linhas_da_empresa(sessao, acesso.empresa_id)
    da_semente = _linhas_da_empresa(sessao, cenario.empresa_a.id)
    assert {"evento", "passagem", "mensagem", "extrato", "agendamento_mudanca"} <= set(antes)
    assert any((tmp_path / "fotos").iterdir())
    tarefas = sessao.scalar(select(func.count()).select_from(tarefas_de_fundo.TarefaDeFundo))
    # As tarefas das passagens dela (casar e resumir as fotos) vão junto.
    passagens = sessao.scalars(
        select(PassagemRecebida.id).where(PassagemRecebida.empresa_id == acesso.empresa_id)
    )
    das_passagens = sessao.scalar(
        select(func.count()).where(
            tarefas_de_fundo.TarefaDeFundo.dados["passagem_id"].astext.in_(
                [str(passagem_id) for passagem_id in passagens]
            )
        )
    )
    assert das_passagens == 2 * antes["passagem"]

    apagadas = demonstracao.apagar_vencidas(sessao, armazenamento, agora=AGORA + timedelta(days=7))

    assert apagadas == 1
    assert _linhas_da_empresa(sessao, acesso.empresa_id) == {}
    assert sessao.get(Empresa, acesso.empresa_id) is None
    assert (gerado.link.empresa_id, gerado.link.apagada_em) == (None, AGORA + timedelta(days=7))
    assert not any((tmp_path / "fotos").iterdir())
    assert _linhas_da_empresa(sessao, cenario.empresa_a.id) == da_semente
    restantes = sessao.scalar(select(func.count()).select_from(tarefas_de_fundo.TarefaDeFundo))
    assert restantes == tarefas - das_passagens


def test_a_empresa_revogada_tambem_e_apagada(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin, tmp_path: Path
) -> None:
    gerado = _gerar(sessao, administracao)
    gestor = _quem(sessao, _entrar(sessao, senhas, cifra, gerado.codigo))
    demonstracao.revogar_link(sessao, administracao, gerado.link.id, agora=AGORA)

    armazenamento = ArmazenamentoLocal(tmp_path, cifra)
    apagadas = demonstracao.apagar_vencidas(sessao, armazenamento, agora=AGORA)

    assert apagadas == 1
    assert sessao.get(Empresa, gestor.empresa_id) is None


def test_a_empresa_do_link_que_ainda_vale_fica(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin, tmp_path: Path
) -> None:
    gerado = _gerar(sessao, administracao)
    gestor = _quem(sessao, _entrar(sessao, senhas, cifra, gerado.codigo))

    armazenamento = ArmazenamentoLocal(tmp_path, cifra)
    apagadas = demonstracao.apagar_vencidas(sessao, armazenamento, agora=AGORA + timedelta(days=6))

    assert apagadas == 0
    assert sessao.get(Empresa, gestor.empresa_id) is not None


# --- O banco: a prova só se apaga na empresa de demonstração ----------------------------------


def _apagar_eventos(sessao: Session, empresa_id: int, *, avisar: bool) -> None:
    with sessao.begin_nested():
        if avisar:
            sessao.execute(
                text("select set_config('patio.apagar_empresa', :empresa, true)"),
                {"empresa": str(empresa_id)},
            )
        sessao.execute(delete(Evento).where(Evento.empresa_id == empresa_id))


def test_o_banco_recusa_apagar_a_prova_de_empresa_que_nao_veio_de_um_link(
    sessao: Session, senhas: Senhas, cifra: Cifra, cenario: Demonstracao
) -> None:
    sem_link = empresa.criar(
        sessao, senhas, cifra, nome="Sem link", cnpj="DEMO0000000S00",
        dominio="sem-link.demonstracao.example", senha=SENHA_DA_DEMONSTRACAO, pin="135790",
        administrador_id=cenario.administrador.id, agora=AGORA, dias=1,
    )  # fmt: skip

    with pytest.raises(DBAPIError) as erro:
        _apagar_eventos(sessao, sem_link.empresa.id, avisar=True)

    assert sqlstate(erro.value) == RECUSA_DA_PROVA


def test_o_banco_recusa_apagar_a_prova_sem_o_aviso_da_transacao(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin
) -> None:
    gestor = _quem(sessao, _entrar(sessao, senhas, cifra, _gerar(sessao, administracao).codigo))

    with pytest.raises(DBAPIError) as erro:
        _apagar_eventos(sessao, gestor.empresa_id, avisar=False)

    assert sqlstate(erro.value) == RECUSA_DA_PROVA


def test_a_faxina_do_worker_apaga_no_maximo_uma_vez_por_hora(
    sessao: Session, senhas: Senhas, cifra: Cifra, administracao: AcessoAdmin, tmp_path: Path
) -> None:
    faxina = demonstracao.Faxina(ArmazenamentoLocal(tmp_path, cifra))
    primeiro = _gerar(sessao, administracao)
    _entrar(sessao, senhas, cifra, primeiro.codigo)
    demonstracao.revogar_link(sessao, administracao, primeiro.link.id, agora=AGORA)
    assert faxina(sessao, AGORA) == 1

    segundo = _gerar(sessao, administracao)
    _entrar(sessao, senhas, cifra, segundo.codigo)
    demonstracao.revogar_link(sessao, administracao, segundo.link.id, agora=AGORA)

    assert faxina(sessao, AGORA + timedelta(minutes=59)) == 0
    assert faxina(sessao, AGORA + timedelta(hours=1)) == 1

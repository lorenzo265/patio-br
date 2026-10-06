"""O link de demonstração por empresa visitada (T48, D-52 e D-54).

- **Gerar:** a administração dá o nome da empresa visitada; o código é aleatório e longo, vai
  no endereço e aparece uma vez só. O banco guarda só o resumo. Vale 7 dias.
- **Entrar:** na primeira vez, cria a empresa de demonstração (cerca de 15 segundos); quem volta
  entra na mesma, com os dias que faltavam até ontem já no histórico. Entra como gestor, sem
  senha: as pessoas da empresa do link têm senha sorteada, que ninguém sabe.
- **Trocar de papel:** gestor, porteiro ou líder de pátio da mesma empresa, sem senha. Só os
  ambientes da demonstração têm a rota (o serviço não sabe do ambiente; a tela confere).
- **Apagar:** a empresa do link vencido ou revogado é apagada inteira, com as fotos e as linhas
  de prova. O gatilho ``so_acrescenta`` só deixa apagar a prova de uma empresa que nasceu de um
  link, e só quando a transação avisa qual (``patio.apagar_empresa``).

Vencido, revogado ou inventado dá ``NaoEncontradoError`` (404, sem dizer qual). As funções
gravam com ``flush``; o ``commit`` é de quem chama.
"""

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import String, cast, delete, func, or_, select
from sqlalchemy.orm import Session

from nuvem import tarefas_de_fundo
from nuvem.agendamento import modelos as _agendamento  # noqa: F401
from nuvem.alertas import modelos as _alertas  # noqa: F401
from nuvem.armazenamento import Armazenamento
from nuvem.banco import Base
from nuvem.cadastro import login
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, AcessoAdmin, acesso_do_usuario
from nuvem.cadastro.modelos import Empresa, Papel, Usuario
from nuvem.cifra import Cifra
from nuvem.demonstracao import empresa
from nuvem.demonstracao.modelos import LinkDemonstracao
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.extrato import modelos as _extrato  # noqa: F401
from nuvem.frota.modelos import CaixaBorda
from nuvem.guarda import modelos as _guarda  # noqa: F401
from nuvem.mensagens import modelos as _mensagens  # noqa: F401
from nuvem.portaria.modelos import PassagemRecebida
from nuvem.prova import modelos as _prova  # noqa: F401
from nuvem.senhas import Senhas, resumo_rapido

_registro = logging.getLogger(__name__)

VALIDADE = timedelta(days=7)
INTERVALO_DA_FAXINA = timedelta(hours=1)
"""O worker apaga as empresas vencidas no máximo uma vez por hora."""
TAMANHO_DO_NOME = 120
DOMINIO_DOS_EMAILS = "demonstracao.example"
"""Os e-mails das pessoas da empresa do link: ``gestor@link12.demonstracao.example``."""


@dataclass(frozen=True)
class LinkGerado:
    """O link novo e o código dele (que só aparece agora, para a administração mandar)."""

    link: LinkDemonstracao
    codigo: str


# --- Administração ----------------------------------------------------------------------------


def gerar_link(
    sessao: Session, administracao: AcessoAdmin, *, nome: str, agora: datetime
) -> LinkGerado:
    """Gera um link de demonstração para uma empresa visitada.

    Raises:
        DadoInvalidoError: se o nome estiver vazio ou passar de ``TAMANHO_DO_NOME``.
    """
    nome = nome.strip()
    if not 0 < len(nome) <= TAMANHO_DO_NOME:
        raise DadoInvalidoError(f"o nome tem de 1 a {TAMANHO_DO_NOME} caracteres")
    codigo = secrets.token_urlsafe(32)
    link = LinkDemonstracao(
        nome=nome,
        codigo_resumo=resumo_rapido(codigo),
        criado_por=administracao.administrador_id,
        criado_em=agora,
        vence_em=agora + VALIDADE,
    )
    sessao.add(link)
    sessao.flush()
    return LinkGerado(link=link, codigo=codigo)


def listar_links(sessao: Session, _administracao: AcessoAdmin) -> list[LinkDemonstracao]:
    """Todos os links de demonstração, do mais novo ao mais antigo."""
    return list(sessao.scalars(select(LinkDemonstracao).order_by(LinkDemonstracao.id.desc())))


def revogar_link(
    sessao: Session, _administracao: AcessoAdmin, link_id: int, *, agora: datetime
) -> LinkDemonstracao:
    """Revoga o link: ele deixa de valer, e as pessoas da empresa dele saem na hora.

    A empresa é apagada depois, com as vencidas (``apagar_vencidas``).

    Raises:
        NaoEncontradoError: se o link não existir.
    """
    link = sessao.get(LinkDemonstracao, link_id)
    if link is None:
        raise NaoEncontradoError(f"link de demonstração {link_id}")
    if link.revogado_em is None:
        link.revogado_em = agora
    if link.empresa_id is not None:
        for pessoa in sessao.scalars(select(Usuario).where(Usuario.empresa_id == link.empresa_id)):
            pessoa.ativo = False
    sessao.flush()
    return link


def vale(link: LinkDemonstracao, *, agora: datetime) -> bool:
    """Se o link ainda abre: não venceu e não foi revogado."""
    return link.revogado_em is None and agora < link.vence_em


# --- Quem abre o link -------------------------------------------------------------------------


def abrir_link(sessao: Session, codigo: str, *, agora: datetime) -> LinkDemonstracao:
    """O link do código, para a página mostrar para quem é.

    Raises:
        NaoEncontradoError: se o link estiver vencido, revogado ou não existir.
    """
    return _que_vale(sessao, codigo, agora=agora, travar=False)


def entrar_pelo_link(
    sessao: Session, senhas: Senhas, cifra: Cifra, codigo: str, *, agora: datetime
) -> str:
    """Entra na empresa de demonstração do link como gestor; cria a empresa na primeira vez.

    Quem volta entra na mesma empresa, e os dias que faltavam até ontem entram no histórico.

    Returns:
        O código da sessão do gestor, para o cookie.

    Raises:
        NaoEncontradoError: se o link estiver vencido, revogado ou não existir.
    """
    # Travado: duas pessoas abrindo ao mesmo tempo não criam duas empresas.
    link = _que_vale(sessao, codigo, agora=agora, travar=True)
    if link.empresa_id is None:
        criada = empresa.criar(
            sessao, senhas, cifra, nome=f"{link.nome} (demonstração)", cnpj=_cnpj(link),
            dominio=f"link{link.id}.{DOMINIO_DOS_EMAILS}", senha=secrets.token_urlsafe(32),
            pin=f"{secrets.randbelow(1_000_000):06d}", administrador_id=link.criado_por,
            agora=agora, dias=empresa.DIAS_DE_HISTORICO, semente=link.id,
        )  # fmt: skip
        link.empresa_id = criada.empresa.id
        gestor = criada.gestor
    else:
        gestor = _gestor(sessao, link.empresa_id)
        empresa.completar_historico(sessao, acesso_do_usuario(sessao, gestor.id), agora=agora)
    link.ultima_entrada_em = agora
    sessao.flush()
    return login.abrir_sessao(sessao, gestor, agora)


def trocar_de_papel(
    sessao: Session, acesso: Acesso, *, codigo: str, papel: Papel, agora: datetime
) -> str:
    """Passa a sessão para a primeira pessoa do papel, da mesma empresa, num site em comum.

    Returns:
        O código da nova sessão (o mesmo, se o papel já é o de quem pediu); a antiga é fechada.

    Raises:
        NaoEncontradoError: se ninguém do papel estiver nos sites de quem pediu.
    """
    if papel == acesso.papel:
        return codigo
    for site_id in sorted(acesso.sites):
        pessoas = cadastro.pessoas_do_site(sessao, acesso, site_id, papel)
        if pessoas:
            login.sair(sessao, codigo)
            return login.abrir_sessao(sessao, pessoas[0], agora)
    raise NaoEncontradoError(f"ninguém do papel {papel}")


def _que_vale(sessao: Session, codigo: str, *, agora: datetime, travar: bool) -> LinkDemonstracao:
    consulta = select(LinkDemonstracao).where(
        LinkDemonstracao.codigo_resumo == resumo_rapido(codigo)
    )
    link = sessao.scalars(consulta.with_for_update() if travar else consulta).one_or_none()
    if link is None or not vale(link, agora=agora):
        raise NaoEncontradoError("link de demonstração")
    return link


def _gestor(sessao: Session, empresa_id: int) -> Usuario:
    gestor = sessao.scalars(
        select(Usuario)
        .where(Usuario.empresa_id == empresa_id, Usuario.papel == "gestor", Usuario.ativo)
        .order_by(Usuario.id)
        .limit(1)
    ).one_or_none()
    if gestor is None:
        raise NaoEncontradoError("gestor da empresa de demonstração")
    return gestor


def _cnpj(link: LinkDemonstracao) -> str:
    # 14 caracteres que não existem como CNPJ: as letras DEMO marcam a demonstração.
    return f"DEMO{link.id:08d}00"


# --- Apagar -----------------------------------------------------------------------------------


def apagar_vencidas(sessao: Session, armazenamento: Armazenamento, *, agora: datetime) -> int:
    """Apaga as empresas dos links vencidos ou revogados, inteiras, com as fotos.

    Returns:
        Quantas empresas foram apagadas.
    """
    vencidos = list(
        sessao.scalars(
            select(LinkDemonstracao)
            .where(
                LinkDemonstracao.empresa_id.is_not(None),
                or_(LinkDemonstracao.vence_em <= agora, LinkDemonstracao.revogado_em.is_not(None)),
            )
            .order_by(LinkDemonstracao.id)
            .with_for_update(skip_locked=True)
        )
    )
    for link in vencidos:
        _apagar_a_empresa(sessao, link, armazenamento, agora=agora)
        _registro.info("empresa de demonstração do link %d apagada", link.id)
    return len(vencidos)


class Faxina:
    """Apaga as empresas vencidas no máximo uma vez por intervalo (o worker chama a cada volta)."""

    def __init__(
        self, armazenamento: Armazenamento, intervalo: timedelta = INTERVALO_DA_FAXINA
    ) -> None:
        self._armazenamento = armazenamento
        self._intervalo = intervalo
        self._proxima: datetime | None = None

    def __call__(self, sessao: Session, agora: datetime) -> int:
        """Apaga as vencidas, se já for hora; devolve quantas apagou."""
        if self._proxima is not None and agora < self._proxima:
            return 0
        self._proxima = agora + self._intervalo
        return apagar_vencidas(sessao, self._armazenamento, agora=agora)


def _apagar_a_empresa(
    sessao: Session, link: LinkDemonstracao, armazenamento: Armazenamento, *, agora: datetime
) -> None:
    empresa_id = link.empresa_id
    assert empresa_id is not None
    caixas = list(sessao.scalars(select(CaixaBorda.id).where(CaixaBorda.empresa_id == empresa_id)))
    # O aviso ao gatilho so_acrescenta: vale só até o fim desta transação.
    sessao.execute(select(func.set_config("patio.apagar_empresa", str(empresa_id), True)))
    passagens = select(cast(PassagemRecebida.id, String)).where(
        PassagemRecebida.empresa_id == empresa_id
    )
    sessao.execute(
        delete(tarefas_de_fundo.TarefaDeFundo).where(
            tarefas_de_fundo.TarefaDeFundo.dados["passagem_id"].astext.in_(passagens)
        )
    )
    # Das filhas para as mães: a ordem das chaves estrangeiras, ao contrário. Os módulos de
    # tabelas importados aqui (_agendamento, _extrato, _mensagens e os outros) põem todas no
    # Base.metadata; uma tabela de fora deixaria a empresa sem apagar (chave estrangeira).
    for tabela in reversed(Base.metadata.sorted_tables):
        if "empresa_id" in tabela.c and tabela.name != LinkDemonstracao.__tablename__:
            sessao.execute(delete(tabela).where(tabela.c.empresa_id == empresa_id))
    link.empresa_id = None
    link.apagada_em = agora
    sessao.flush()
    sessao.execute(delete(Empresa).where(Empresa.id == empresa_id))
    sessao.flush()
    for caixa_id in caixas:
        armazenamento.apagar_da_caixa(caixa_id)

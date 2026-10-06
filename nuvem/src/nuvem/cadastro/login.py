"""Login (SDD 8.2): senha, sessão no banco (D-20), limite de tentativas e troca de porteiro.

Quem entra é uma **conta**: um usuário do cliente ou alguém da administração (D-19). As duas
entram pela mesma tela, com e-mail e senha; o e-mail é único entre as duas tabelas.

As funções gravam com ``flush``; o ``commit`` é de quem chama. Atenção: uma recusa também grava
o erro (para o limite de tentativas), então quem chama faz ``commit`` mesmo quando recebe
``LoginRecusadoError``.

As tentativas de um mesmo alvo passam uma de cada vez: a trava no banco vale até o ``commit``
(ou o ``rollback``) de quem chama.
"""

import secrets
from datetime import datetime, timedelta

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from nuvem.cadastro.modelos import Administrador, SessaoLogin, TentativaLogin, Usuario, UsuarioSite
from nuvem.erros import NaoEncontradoError
from nuvem.senhas import Senhas, resumo_rapido

VALIDADE_DA_SESSAO = timedelta(hours=12)
"""Um turno de portaria; depois disso, entra de novo."""

JANELA_DAS_TENTATIVAS = timedelta(minutes=15)
MAXIMO_DE_ERROS = 5
"""No máximo 5 erros por alvo (e-mail ou porteiro) a cada 15 minutos."""

Conta = Usuario | Administrador


class LoginRecusadoError(Exception):
    """E-mail, senha ou PIN não conferem (de propósito, sem dizer qual)."""


class MuitasTentativasError(Exception):
    """Erros demais para o mesmo alvo nos últimos 15 minutos: espere e tente de novo."""


def normalizar_email(email: str) -> str:
    """O e-mail como é guardado e comparado: sem espaços nas pontas, em minúsculas."""
    return email.strip().lower()


def conta_por_email(sessao: Session, email: str) -> Conta | None:
    """Devolve o usuário ou o administrador com este e-mail, se houver."""
    email = normalizar_email(email)
    usuario = sessao.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is not None:
        return usuario
    return sessao.scalar(select(Administrador).where(Administrador.email == email))


def entrar(sessao: Session, senhas: Senhas, *, email: str, senha: str, agora: datetime) -> str:
    """Confere e-mail e senha e abre uma sessão.

    Returns:
        O código da sessão, para o cookie (o banco guarda só o resumo dele).

    Raises:
        MuitasTentativasError: se o e-mail errou demais nos últimos 15 minutos (mesmo com a
            senha certa agora).
        LoginRecusadoError: se a conta não existir, estiver desativada, não tiver senha ou a
            senha não conferir. O erro fica gravado para o limite de tentativas.
    """
    alvo = resumo_rapido(f"email:{normalizar_email(email)}")
    _recusar_se_bloqueado(sessao, alvo, agora)
    conta = conta_por_email(sessao, email)
    if conta is None or not conta.ativo or conta.senha_resumo is None:
        senhas.gastar_o_mesmo_tempo(senha)
        _registrar_erro(sessao, alvo, agora)
        raise LoginRecusadoError
    if not senhas.confere(conta.senha_resumo, senha):
        _registrar_erro(sessao, alvo, agora)
        raise LoginRecusadoError
    if senhas.precisa_refazer(conta.senha_resumo):
        conta.senha_resumo = senhas.resumir(senha)
    _esquecer_erros(sessao, alvo)
    return abrir_sessao(sessao, conta, agora)


def sair(sessao: Session, codigo: str) -> None:
    """Fecha a sessão do código (se ela existir)."""
    sessao.execute(delete(SessaoLogin).where(SessaoLogin.codigo_resumo == resumo_rapido(codigo)))
    sessao.flush()


def conta_da_sessao(sessao: Session, codigo: str, agora: datetime) -> Conta | None:
    """Devolve quem está na sessão do código, ou ``None`` se ela não vale.

    Não vale a sessão que não existe, que venceu ou cuja conta foi desativada.
    """
    aberta = sessao.scalar(
        select(SessaoLogin).where(
            SessaoLogin.codigo_resumo == resumo_rapido(codigo), SessaoLogin.expira_em > agora
        )
    )
    if aberta is None:
        return None
    conta: Conta | None
    if aberta.usuario_id is not None:
        conta = sessao.get(Usuario, aberta.usuario_id)
    else:
        conta = sessao.get(Administrador, aberta.administrador_id)
    return conta if conta is not None and conta.ativo else None


def porteiros_da_troca(sessao: Session, usuario_id: int) -> list[Usuario]:
    """Os porteiros que podem assumir o tablet deste usuário, por nome.

    São os porteiros ativos da mesma empresa com pelo menos um site em comum, menos ele mesmo.
    """
    return list(sessao.scalars(_consulta_dos_porteiros_da_troca(sessao, usuario_id)))


def trocar_porteiro(
    sessao: Session, senhas: Senhas, *, codigo: str, porteiro_id: int, pin: str, agora: datetime
) -> str:
    """Passa a sessão aberta no tablet para o porteiro do turno, que confirma com o PIN.

    Returns:
        O código da nova sessão, do porteiro; a sessão antiga é fechada.

    Raises:
        NaoEncontradoError: se a sessão não for de um usuário do cliente, ou se o porteiro não
            estiver entre os da troca (outra empresa, outro site, outro papel, desativado).
        MuitasTentativasError: se o PIN deste porteiro errou demais nos últimos 15 minutos.
        LoginRecusadoError: se o PIN não conferir (o erro fica gravado).
    """
    atual = conta_da_sessao(sessao, codigo, agora)
    if not isinstance(atual, Usuario):
        raise NaoEncontradoError(f"porteiro {porteiro_id}")
    consulta = _consulta_dos_porteiros_da_troca(sessao, atual.id).where(Usuario.id == porteiro_id)
    porteiro = sessao.scalar(consulta)
    if porteiro is None:
        raise NaoEncontradoError(f"porteiro {porteiro_id}")
    alvo = resumo_rapido(f"pin:{porteiro.id}")
    _recusar_se_bloqueado(sessao, alvo, agora)
    if porteiro.pin_resumo is None or not senhas.confere(porteiro.pin_resumo, pin):
        _registrar_erro(sessao, alvo, agora)
        raise LoginRecusadoError
    _esquecer_erros(sessao, alvo)
    sair(sessao, codigo)
    return abrir_sessao(sessao, porteiro, agora)


def _consulta_dos_porteiros_da_troca(sessao: Session, usuario_id: int) -> Select[Usuario]:
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise NaoEncontradoError(f"usuário {usuario_id}")
    sites_dele = select(UsuarioSite.site_id).where(UsuarioSite.usuario_id == usuario.id)
    com_site_em_comum = (
        select(UsuarioSite.usuario_id)
        .where(UsuarioSite.empresa_id == usuario.empresa_id)
        .where(UsuarioSite.site_id.in_(sites_dele))
    )
    return (
        select(Usuario)
        .where(
            Usuario.empresa_id == usuario.empresa_id,
            Usuario.papel == "porteiro",
            Usuario.ativo,
            Usuario.id != usuario.id,
            Usuario.id.in_(com_site_em_comum),
        )
        .order_by(Usuario.nome)
    )


def abrir_sessao(sessao: Session, conta: Conta, agora: datetime) -> str:
    """Abre uma sessão para a conta, sem conferir nada: quem chama já sabe quem é.

    Além da senha e do PIN, só o link de demonstração abre sessão assim (D-54), depois de
    conferir o código do link.

    Returns:
        O código da sessão, para o cookie (o banco guarda só o resumo dele).
    """
    codigo = secrets.token_urlsafe(32)
    aberta = SessaoLogin(
        codigo_resumo=resumo_rapido(codigo), criada_em=agora, expira_em=agora + VALIDADE_DA_SESSAO
    )
    if isinstance(conta, Usuario):
        aberta.usuario_id = conta.id
        aberta.empresa_id = conta.empresa_id
    else:
        aberta.administrador_id = conta.id
    sessao.add(aberta)
    sessao.flush()
    return codigo


def _recusar_se_bloqueado(sessao: Session, alvo: str, agora: datetime) -> None:
    # Uma tentativa por vez para o mesmo alvo. Sem a trava, pedidos ao mesmo tempo contariam os
    # erros antes de qualquer um gravar o seu, e todos passariam do limite.
    sessao.execute(select(func.pg_advisory_xact_lock(_chave_da_trava(alvo))))
    erros = sessao.scalar(
        select(func.count())
        .select_from(TentativaLogin)
        .where(
            TentativaLogin.alvo_resumo == alvo,
            TentativaLogin.momento > agora - JANELA_DAS_TENTATIVAS,
        )
    )
    if erros is not None and erros >= MAXIMO_DE_ERROS:
        raise MuitasTentativasError


def _registrar_erro(sessao: Session, alvo: str, agora: datetime) -> None:
    # Aproveita para apagar os erros deste alvo que já saíram da janela.
    sessao.execute(
        delete(TentativaLogin).where(
            TentativaLogin.alvo_resumo == alvo,
            TentativaLogin.momento <= agora - JANELA_DAS_TENTATIVAS,
        )
    )
    sessao.add(TentativaLogin(alvo_resumo=alvo, momento=agora))
    sessao.flush()


def _esquecer_erros(sessao: Session, alvo: str) -> None:
    sessao.execute(delete(TentativaLogin).where(TentativaLogin.alvo_resumo == alvo))
    sessao.flush()


def _chave_da_trava(alvo: str) -> int:
    # A trava do PostgreSQL leva um número: os primeiros 60 bits do resumo cabem no bigint.
    return int(alvo[:15], 16)

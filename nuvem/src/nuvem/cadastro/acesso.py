"""Quem está pedindo: o usuário do cliente (com empresa, papel e sites) ou a administração.

Toda leitura de dado do cliente recebe um ``Acesso`` (SDD 5.5). Ele nasce da sessão de login
(D-20): o cookie traz o código, e o banco diz de quem é. A administração (nós) recebe um
``AcessoAdmin``, de outro tipo, que nunca serve onde se pede um ``Acesso`` (D-19).

As dependências do FastAPI daqui respondem 401 sem login e 403 com o papel errado.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import login
from nuvem.cadastro.modelos import Papel, Usuario, UsuarioSite
from nuvem.erros import NaoEncontradoError, NaoIdentificadoError, SemPermissaoError
from nuvem.relogio import agora

COOKIE_DA_SESSAO = "patio_sessao"


@dataclass(frozen=True)
class Acesso:
    """O que um usuário do cliente pode ver: só a empresa dele e, nela, só os sites dele."""

    usuario_id: int
    empresa_id: int
    papel: Papel
    sites: frozenset[int]


@dataclass(frozen=True)
class AcessoAdmin:
    """Alguém da administração da plataforma (nós), que atravessa empresas pelas rotas dela."""

    administrador_id: int


def acesso_do_usuario(sessao: Session, usuario_id: int) -> Acesso:
    """Monta o acesso de um usuário a partir do cadastro.

    Raises:
        NaoEncontradoError: se o usuário não existir.
    """
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise NaoEncontradoError(f"usuário {usuario_id}")
    sites = sessao.scalars(select(UsuarioSite.site_id).where(UsuarioSite.usuario_id == usuario.id))
    return Acesso(
        usuario_id=usuario.id,
        empresa_id=usuario.empresa_id,
        papel=usuario.papel,
        sites=frozenset(sites),
    )


def obter_quem(
    request: Request,
    sessao: Annotated[Session, Depends(obter_sessao)],
    momento: Annotated[datetime, Depends(agora)],
) -> Acesso | AcessoAdmin:
    """Dependência do FastAPI: quem está na sessão do cookie.

    Raises:
        NaoIdentificadoError: sem cookie, ou com uma sessão que não vale (401).
    """
    codigo = request.cookies.get(COOKIE_DA_SESSAO)
    conta = login.conta_da_sessao(sessao, codigo, momento) if codigo else None
    if conta is None:
        raise NaoIdentificadoError
    quem: Acesso | AcessoAdmin
    if isinstance(conta, Usuario):
        quem = acesso_do_usuario(sessao, conta.id)
    else:
        quem = AcessoAdmin(administrador_id=conta.id)
    # A tela usa para desenhar o que depende de quem entrou (a faixa da demonstração, D-54).
    request.state.quem = quem
    return quem


QuemPede = Annotated[Acesso | AcessoAdmin, Depends(obter_quem)]


def obter_acesso(quem: QuemPede) -> Acesso:
    """Dependência do FastAPI: o acesso do usuário do cliente que fez a requisição.

    Raises:
        NaoIdentificadoError: sem login (401).
        SemPermissaoError: se quem pede é a administração, que não usa as rotas do cliente (403).
    """
    if not isinstance(quem, Acesso):
        raise SemPermissaoError
    return quem


def exigir_papel(*papeis: Papel) -> Callable[[Acesso], Acesso]:
    """Cria a dependência que só deixa passar os papéis dados (os outros recebem 403).

    Ex.: ``Depends(exigir_papel("gestor"))``.
    """

    def dependencia(acesso: Annotated[Acesso, Depends(obter_acesso)]) -> Acesso:
        if acesso.papel not in papeis:
            raise SemPermissaoError
        return acesso

    return dependencia


def obter_acesso_admin(quem: QuemPede) -> AcessoAdmin:
    """Dependência do FastAPI: só a administração passa (o usuário do cliente recebe 403).

    Raises:
        NaoIdentificadoError: sem login (401).
        SemPermissaoError: se quem pede é usuário de um cliente (403).
    """
    if not isinstance(quem, AcessoAdmin):
        raise SemPermissaoError
    return quem

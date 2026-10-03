"""Quem está pedindo: o usuário, a empresa dele e os sites que ele vê.

Toda leitura de dado do cliente recebe um ``Acesso`` (SDD 5.5). O login (T09) é que vai
montá-lo a partir da sessão; até lá, ``obter_acesso`` fecha todas as rotas com 401.
"""

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem.cadastro.modelos import Usuario, UsuarioSite
from nuvem.erros import NaoEncontradoError


@dataclass(frozen=True)
class Acesso:
    """O que um usuário pode ver: só a empresa dele e, dentro dela, só os sites ligados a ele."""

    usuario_id: int
    empresa_id: int
    sites: frozenset[int]


def acesso_do_usuario(sessao: Session, usuario_id: int) -> Acesso:
    """Monta o acesso de um usuário a partir do cadastro.

    Raises:
        NaoEncontradoError: se o usuário não existir.
    """
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise NaoEncontradoError(f"usuário {usuario_id}")
    sites = sessao.scalars(select(UsuarioSite.site_id).where(UsuarioSite.usuario_id == usuario.id))
    return Acesso(usuario_id=usuario.id, empresa_id=usuario.empresa_id, sites=frozenset(sites))


def obter_acesso() -> Acesso:
    """Dependência do FastAPI: o acesso de quem fez a requisição.

    O login entra na T09; até lá, ninguém está identificado e toda rota que depende
    desta função responde 401. Os testes trocam esta dependência por um usuário de exemplo.
    """
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="entre no sistema")

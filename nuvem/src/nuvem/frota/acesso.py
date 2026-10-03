"""A caixa que está chamando a nuvem: identificada pela chave em ``Authorization: Bearer``."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.erros import CaixaNaoIdentificadaError
from nuvem.frota import servico
from nuvem.frota.servico import AcessoDaCaixa

_portador = HTTPBearer(auto_error=False, description="A chave que a caixa recebeu na ativação.")


def obter_caixa(
    sessao: Annotated[Session, Depends(obter_sessao)],
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_portador)],
) -> AcessoDaCaixa:
    """Dependência do FastAPI: a caixa dona da chave.

    Raises:
        CaixaNaoIdentificadaError: sem chave, ou com chave inventada ou revogada (401).
    """
    caixa = servico.caixa_da_chave(sessao, credenciais.credentials) if credenciais else None
    if caixa is None:
        raise CaixaNaoIdentificadaError
    return caixa

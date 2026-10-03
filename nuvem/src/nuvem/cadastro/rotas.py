"""Rotas do cadastro: o cliente consulta os sites e as câmeras que vê.

Toda rota exige o ``Acesso`` de quem pede (até o login da T09, ninguém: 401). Câmera sai sem
login nem senha.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import servico
from nuvem.cadastro.acesso import Acesso, obter_acesso
from nuvem.cadastro.modelos import Posicao

roteador = APIRouter(prefix="/api/cadastro", tags=["cadastro"])

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaRequisicao = Annotated[Acesso, Depends(obter_acesso)]


class SitePublico(BaseModel):
    """Um site como a API o mostra."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    fuso: str


class CameraPublica(BaseModel):
    """Uma câmera como a API a mostra: sem login nem senha."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    faixa_id: int
    nome: str
    posicao: Posicao
    endereco: str


@roteador.get("/sites")
def listar_sites(sessao: SessaoDaRequisicao, acesso: AcessoDaRequisicao) -> list[SitePublico]:
    """Os sites que o usuário vê."""
    return [SitePublico.model_validate(site) for site in servico.listar_sites(sessao, acesso)]


@roteador.get("/sites/{site_id}")
def obter_site(sessao: SessaoDaRequisicao, acesso: AcessoDaRequisicao, site_id: int) -> SitePublico:
    """Um site que o usuário vê (404 para qualquer outro)."""
    return SitePublico.model_validate(servico.obter_site(sessao, acesso, site_id))


@roteador.get("/sites/{site_id}/cameras")
def listar_cameras(
    sessao: SessaoDaRequisicao, acesso: AcessoDaRequisicao, site_id: int
) -> list[CameraPublica]:
    """As câmeras de um site que o usuário vê (404 para qualquer outro site)."""
    cameras = servico.listar_cameras(sessao, acesso, site_id)
    return [CameraPublica.model_validate(camera) for camera in cameras]

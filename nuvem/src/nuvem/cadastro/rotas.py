"""Rotas do cadastro: o cliente consulta os sites e as câmeras que vê; a administração, as
empresas.

Sem login, 401; com o papel errado, 403; o que é de outra empresa, 404. Câmera sai sem login
nem senha.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import servico
from nuvem.cadastro.acesso import (
    Acesso,
    AcessoAdmin,
    exigir_papel,
    obter_acesso,
    obter_acesso_admin,
)
from nuvem.cadastro.modelos import Posicao

roteador = APIRouter(prefix="/api/cadastro", tags=["cadastro"])
roteador_admin = APIRouter(prefix="/api/admin", tags=["administração"])

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaRequisicao = Annotated[Acesso, Depends(obter_acesso)]
AcessoDoGestor = Annotated[Acesso, Depends(exigir_papel("gestor"))]
AcessoDaAdministracao = Annotated[AcessoAdmin, Depends(obter_acesso_admin)]


class SitePublico(BaseModel):
    """Um site como a API o mostra."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    fuso: str


class EmpresaPublica(BaseModel):
    """Uma empresa como a API da administração a mostra."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cnpj: str


class SiteParaAdministracao(BaseModel):
    """Um site como a administração o vê: com a empresa."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    empresa_id: int
    nome: str


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
    sessao: SessaoDaRequisicao, acesso: AcessoDoGestor, site_id: int
) -> list[CameraPublica]:
    """As câmeras de um site que o gestor vê (404 para qualquer outro site)."""
    cameras = servico.listar_cameras(sessao, acesso, site_id)
    return [CameraPublica.model_validate(camera) for camera in cameras]


@roteador_admin.get("/empresas")
def listar_empresas(
    sessao: SessaoDaRequisicao, _administracao: AcessoDaAdministracao
) -> list[EmpresaPublica]:
    """Todas as empresas (só a administração)."""
    return [EmpresaPublica.model_validate(empresa) for empresa in servico.listar_empresas(sessao)]


@roteador_admin.get("/sites")
def listar_sites_para_administracao(
    sessao: SessaoDaRequisicao, _administracao: AcessoDaAdministracao
) -> list[SiteParaAdministracao]:
    """Todos os sites, de todas as empresas (só a administração)."""
    sites = servico.listar_sites_para_administracao(sessao)
    return [SiteParaAdministracao.model_validate(site) for site in sites]

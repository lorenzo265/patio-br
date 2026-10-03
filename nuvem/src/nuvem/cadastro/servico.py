"""Regras do cadastro.

Duas portas de entrada:

- **Leitura pelo cliente:** toda função recebe o ``Acesso`` de quem pede e só enxerga a empresa
  e os sites dele (SDD 5.5). O que é de outro "não existe" (``NaoEncontradoError``), sem dizer
  que existe.
- **Administração (nós):** criar a estrutura de um cliente. Cada filho herda a empresa do pai
  recebido, então não há como passar a empresa errada.

As funções gravam com ``flush`` (o registro ganha id); o ``commit`` é de quem chama.
"""

from collections.abc import Sequence
from urllib.parse import urlsplit

from sqlalchemy import Select, and_, select
from sqlalchemy.orm import Session

from nuvem.banco import Base
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.modelos import (
    FUSO_PADRAO,
    Camera,
    Doca,
    Empresa,
    Faixa,
    Papel,
    Portaria,
    Posicao,
    Sentido,
    Site,
    Usuario,
    UsuarioSite,
)
from nuvem.cifra import Cifra
from nuvem.erros import DadoInvalidoError, NaoEncontradoError

# --- Leitura pelo cliente ------------------------------------------------------------------


def _sites_visiveis(acesso: Acesso) -> Select[Site]:
    return select(Site).where(Site.empresa_id == acesso.empresa_id, Site.id.in_(acesso.sites))


def listar_sites(sessao: Session, acesso: Acesso) -> list[Site]:
    """Devolve os sites que o usuário vê, por nome."""
    return list(sessao.scalars(_sites_visiveis(acesso).order_by(Site.nome)))


def obter_site(sessao: Session, acesso: Acesso, site_id: int) -> Site:
    """Devolve um site que o usuário vê.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = sessao.scalars(_sites_visiveis(acesso).where(Site.id == site_id)).one_or_none()
    if site is None:
        raise NaoEncontradoError(f"site {site_id}")
    return site


def listar_cameras(sessao: Session, acesso: Acesso, site_id: int) -> list[Camera]:
    """Devolve as câmeras de um site que o usuário vê.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = obter_site(sessao, acesso, site_id)
    consulta = (
        select(Camera)
        .join(Faixa, and_(Faixa.id == Camera.faixa_id, Faixa.empresa_id == Camera.empresa_id))
        .join(
            Portaria,
            and_(Portaria.id == Faixa.portaria_id, Portaria.empresa_id == Faixa.empresa_id),
        )
        .where(Camera.empresa_id == acesso.empresa_id, Portaria.site_id == site.id)
        .order_by(Camera.id)
    )
    return list(sessao.scalars(consulta))


# --- Administração (nós) -------------------------------------------------------------------


def _gravar[M: Base](sessao: Session, registro: M) -> M:
    sessao.add(registro)
    sessao.flush()
    return registro


def criar_empresa(sessao: Session, *, nome: str, cnpj: str) -> Empresa:
    """Cadastra um cliente. O CNPJ vai sem pontuação (14 caracteres)."""
    return _gravar(sessao, Empresa(nome=nome, cnpj=cnpj))


def criar_site(sessao: Session, empresa: Empresa, *, nome: str, fuso: str = FUSO_PADRAO) -> Site:
    """Cadastra um site do cliente."""
    return _gravar(sessao, Site(empresa_id=empresa.id, nome=nome, fuso=fuso))


def criar_portaria(sessao: Session, site: Site, *, nome: str) -> Portaria:
    """Cadastra uma portaria no site."""
    return _gravar(sessao, Portaria(empresa_id=site.empresa_id, site_id=site.id, nome=nome))


def criar_faixa(sessao: Session, portaria: Portaria, *, nome: str, sentido: Sentido) -> Faixa:
    """Cadastra uma faixa na portaria, de entrada ou de saída."""
    faixa = Faixa(
        empresa_id=portaria.empresa_id, portaria_id=portaria.id, nome=nome, sentido=sentido
    )
    return _gravar(sessao, faixa)


def criar_camera(
    sessao: Session,
    cifra: Cifra,
    faixa: Faixa,
    *,
    nome: str,
    posicao: Posicao,
    endereco: str,
    login: str,
    senha: str,
) -> Camera:
    """Cadastra uma câmera na faixa, guardando a senha cifrada.

    Raises:
        DadoInvalidoError: se o endereço trouxer usuário ou senha embutidos.
    """
    partes = urlsplit(endereco)
    if partes.username is not None or partes.password is not None:
        raise DadoInvalidoError(
            "o endereço da câmera não pode levar usuário nem senha; use os campos próprios"
        )
    camera = Camera(
        empresa_id=faixa.empresa_id,
        faixa_id=faixa.id,
        nome=nome,
        posicao=posicao,
        endereco=endereco,
        login=login,
        senha_cifrada=cifra.cifrar(senha),
    )
    return _gravar(sessao, camera)


def criar_doca(sessao: Session, site: Site, *, nome: str) -> Doca:
    """Cadastra uma doca no site."""
    return _gravar(sessao, Doca(empresa_id=site.empresa_id, site_id=site.id, nome=nome))


def criar_usuario(
    sessao: Session,
    empresa: Empresa,
    *,
    nome: str,
    email: str,
    papel: Papel,
    sites: Sequence[Site],
) -> Usuario:
    """Cadastra um usuário do cliente e liga-o aos sites que ele vai ver.

    Raises:
        sqlalchemy.exc.IntegrityError: se um dos sites for de outra empresa (o banco recusa).
    """
    usuario = _gravar(
        sessao, Usuario(empresa_id=empresa.id, nome=nome, email=email.strip().lower(), papel=papel)
    )
    for site in sites:
        sessao.add(UsuarioSite(usuario_id=usuario.id, site_id=site.id, empresa_id=empresa.id))
    sessao.flush()
    return usuario

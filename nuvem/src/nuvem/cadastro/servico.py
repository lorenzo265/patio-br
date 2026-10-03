"""Regras do cadastro.

Três portas de entrada:

- **Leitura pelo cliente:** toda função recebe o ``Acesso`` de quem pede e só enxerga a empresa
  e os sites dele (SDD 5.5). O que é de outro "não existe" (``NaoEncontradoError``), sem dizer
  que existe.
- **Leitura pela borda:** a caixa de borda, já identificada pela chave, lê a estrutura do
  próprio site; a função recebe a empresa e o site da caixa e filtra pelos dois.
- **Administração (nós):** criar a estrutura de um cliente e as pessoas que usam o painel.
  Cada filho herda a empresa do pai recebido, então não há como passar a empresa errada.

As funções gravam com ``flush`` (o registro ganha id); o ``commit`` é de quem chama.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import Select, and_, select
from sqlalchemy.orm import Session

from nuvem.banco import Base
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.login import conta_por_email, normalizar_email
from nuvem.cadastro.modelos import (
    FUSO_PADRAO,
    Administrador,
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
from nuvem.senhas import Senhas

TAMANHO_DA_SENHA = range(10, 129)
"""De 10 a 128 caracteres: longa o bastante, sem deixar o resumo virar um peso para o servidor."""

FORMATO_DO_PIN = re.compile(r"[0-9]{6}")
"""Exatamente 6 números de 0 a 9."""

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


def nomes_das_faixas(sessao: Session, acesso: Acesso, site_id: int) -> dict[int, str]:
    """Os nomes das faixas de um site que o usuário vê, por id.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = obter_site(sessao, acesso, site_id)
    faixas, _ = _faixas_e_cameras_do_site(sessao, empresa_id=acesso.empresa_id, site_id=site.id)
    return {faixa.id: faixa.nome for faixa in faixas}


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


# --- Leitura pela borda --------------------------------------------------------------------


@dataclass(frozen=True)
class CameraDaBorda:
    """O que a caixa precisa para ler o vídeo de uma câmera, com a senha decifrada."""

    id: int
    nome: str
    posicao: Posicao
    endereco: str
    login: str
    senha: str


@dataclass(frozen=True)
class FaixaDaBorda:
    """Uma faixa do site, com as câmeras dela."""

    id: int
    nome: str
    sentido: Sentido
    cameras: tuple[CameraDaBorda, ...]


def faixas_para_a_borda(
    sessao: Session, cifra: Cifra, *, empresa_id: int, site_id: int
) -> list[FaixaDaBorda]:
    """As faixas e câmeras de um site, para a caixa de borda dele (SDD 7.4).

    Quem chama já conferiu a chave da caixa; ``empresa_id`` e ``site_id`` são os dela.
    """
    faixas, cameras = _faixas_e_cameras_do_site(sessao, empresa_id=empresa_id, site_id=site_id)
    return [
        FaixaDaBorda(
            id=faixa.id,
            nome=faixa.nome,
            sentido=faixa.sentido,
            cameras=tuple(
                CameraDaBorda(
                    id=camera.id,
                    nome=camera.nome,
                    posicao=camera.posicao,
                    endereco=camera.endereco,
                    login=camera.login,
                    senha=cifra.decifrar(camera.senha_cifrada),
                )
                for camera in cameras
                if camera.faixa_id == faixa.id
            ),
        )
        for faixa in faixas
    ]


@dataclass(frozen=True)
class FaixaDoSite:
    """Uma faixa do site e os ids das câmeras dela, para conferir o que a caixa manda."""

    id: int
    sentido: Sentido
    cameras: frozenset[int]


def estrutura_do_site(sessao: Session, *, empresa_id: int, site_id: int) -> dict[int, FaixaDoSite]:
    """As faixas de um site (por id), com as câmeras de cada uma, sem senhas.

    Quem chama já conferiu a chave da caixa; ``empresa_id`` e ``site_id`` são os dela.
    """
    faixas, cameras = _faixas_e_cameras_do_site(sessao, empresa_id=empresa_id, site_id=site_id)
    return {
        faixa.id: FaixaDoSite(
            id=faixa.id,
            sentido=faixa.sentido,
            cameras=frozenset(c.id for c in cameras if c.faixa_id == faixa.id),
        )
        for faixa in faixas
    }


def _faixas_e_cameras_do_site(
    sessao: Session, *, empresa_id: int, site_id: int
) -> tuple[Sequence[Faixa], Sequence[Camera]]:
    faixas = sessao.scalars(
        select(Faixa)
        .join(
            Portaria,
            and_(Portaria.id == Faixa.portaria_id, Portaria.empresa_id == Faixa.empresa_id),
        )
        .where(Faixa.empresa_id == empresa_id, Portaria.site_id == site_id)
        .order_by(Faixa.id)
    ).all()
    cameras = sessao.scalars(
        select(Camera)
        .where(Camera.empresa_id == empresa_id, Camera.faixa_id.in_([f.id for f in faixas]))
        .order_by(Camera.id)
    ).all()
    return faixas, cameras


# --- Administração (nós) -------------------------------------------------------------------


def obter_site_para_administracao(sessao: Session, site_id: int) -> Site:
    """Um site de qualquer empresa. Só para a administração (as rotas dela conferem).

    Raises:
        NaoEncontradoError: se o site não existir.
    """
    site = sessao.get(Site, site_id)
    if site is None:
        raise NaoEncontradoError(f"site {site_id}")
    return site


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
    senhas: Senhas,
    empresa: Empresa,
    *,
    nome: str,
    email: str,
    papel: Papel,
    sites: Sequence[Site],
    senha: str | None = None,
) -> Usuario:
    """Cadastra um usuário do cliente e liga-o aos sites que ele vai ver.

    Sem ``senha``, o usuário existe mas ainda não entra.

    Raises:
        DadoInvalidoError: se o e-mail já for de outra pessoa, ou a senha estiver fora da regra.
        sqlalchemy.exc.DBAPIError: se um dos sites for de outra empresa (o banco recusa).
    """
    email = _email_livre(sessao, email)
    usuario = _gravar(sessao, Usuario(empresa_id=empresa.id, nome=nome, email=email, papel=papel))
    for site in sites:
        sessao.add(UsuarioSite(usuario_id=usuario.id, site_id=site.id, empresa_id=empresa.id))
    if senha is not None:
        definir_senha(sessao, senhas, usuario, senha)
    sessao.flush()
    return usuario


def criar_administrador(
    sessao: Session, senhas: Senhas, *, nome: str, email: str, senha: str
) -> Administrador:
    """Cadastra alguém da administração da plataforma (nós; SDD D-19).

    Raises:
        DadoInvalidoError: se o e-mail já for de outra pessoa, ou a senha estiver fora da regra.
    """
    email = _email_livre(sessao, email)
    _conferir_senha(senha)
    administrador = Administrador(nome=nome, email=email, senha_resumo=senhas.resumir(senha))
    return _gravar(sessao, administrador)


def definir_senha(
    sessao: Session, senhas: Senhas, conta: Usuario | Administrador, senha: str
) -> None:
    """Troca a senha de um usuário ou administrador (guarda só o resumo).

    Raises:
        DadoInvalidoError: se a senha não tiver de 10 a 128 caracteres.
    """
    _conferir_senha(senha)
    conta.senha_resumo = senhas.resumir(senha)
    sessao.flush()


def definir_pin(sessao: Session, senhas: Senhas, usuario: Usuario, pin: str) -> None:
    """Define o PIN de um porteiro, usado na troca de porteiro no tablet (guarda só o resumo).

    Raises:
        DadoInvalidoError: se o usuário não for porteiro, ou o PIN não tiver 6 números.
    """
    if usuario.papel != "porteiro":
        raise DadoInvalidoError("só o porteiro tem PIN")
    if not FORMATO_DO_PIN.fullmatch(pin):
        raise DadoInvalidoError("o PIN tem exatamente 6 números")
    usuario.pin_resumo = senhas.resumir(pin)
    sessao.flush()


def listar_empresas(sessao: Session) -> list[Empresa]:
    """Todas as empresas, por nome. Só para a administração (as rotas dela conferem)."""
    return list(sessao.scalars(select(Empresa).order_by(Empresa.nome)))


def _email_livre(sessao: Session, email: str) -> str:
    email = normalizar_email(email)
    if conta_por_email(sessao, email) is not None:
        raise DadoInvalidoError(f"o e-mail {email} já é de outra pessoa")
    return email


def _conferir_senha(senha: str) -> None:
    if len(senha) not in TAMANHO_DA_SENHA:
        raise DadoInvalidoError("a senha precisa ter de 10 a 128 caracteres")

"""O cadastro do cliente pela administração (SDD 6.2 e 8.2, D-75).

A administração cadastra a empresa, os sites, as portarias, as faixas, as câmeras, as docas e as
pessoas. Tudo o que pendura numa empresa é conferido contra ela: pela empresa A, o site da B
"não existe" (SDD 5.5).

**Ninguém recebe a senha de outra pessoa:** a pessoa nova ganha um link de uso único, que vale
72 horas, para criar a própria senha (e o PIN, se for porteiro). A senha esquecida é um link
novo, que troca o anterior; criar a senha fecha as sessões abertas da pessoa. O código do link
aparece uma vez, e o banco guarda só o resumo.

Nada se apaga: a pessoa que sai é desativada (e as sessões dela se fecham).
"""

import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from nuvem.banco import Base
from nuvem.cadastro import servico
from nuvem.cadastro.acesso import AcessoAdmin
from nuvem.cadastro.modelos import (
    Camera,
    Doca,
    Empresa,
    Faixa,
    LinkDeSenha,
    Papel,
    Portaria,
    Posicao,
    Sentido,
    SessaoLogin,
    Site,
    Usuario,
    UsuarioSite,
)
from nuvem.cifra import Cifra
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.senhas import Senhas, resumo_rapido

VALIDADE_DO_LINK = timedelta(hours=72)
TAMANHO_DO_NOME = 100
ESQUEMAS_DA_CAMERA = ("rtsp", "rtsps")
_PESOS_DO_PRIMEIRO = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PESOS_DO_SEGUNDO = (6, *_PESOS_DO_PRIMEIRO)


# --- O CNPJ ---------------------------------------------------------------------------------


def _digito(caracteres: str, pesos: tuple[int, ...]) -> str:
    # O valor de cada caractere é o código ASCII menos 48: os números valem eles mesmos, e as
    # letras do CNPJ alfanumérico, de 17 (A) a 42 (Z). O resto da divisão por 11 dá o dígito.
    soma = sum((ord(c) - 48) * peso for c, peso in zip(caracteres, pesos, strict=True))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def conferir_cnpj(cnpj: str) -> str:
    """O CNPJ sem pontuação e em maiúsculas, se os dígitos conferem.

    Vale o numérico e o alfanumérico (letras nas 12 primeiras posições, desde 07/2026); os 2
    últimos são sempre números.

    Raises:
        DadoInvalidoError: se o CNPJ não tiver 14 caracteres válidos ou os dígitos não conferirem.
    """
    limpo = "".join(c for c in cnpj.strip().upper() if c not in "./- ")
    base, digitos = limpo[:12], limpo[12:]
    # Os 2 do fim não precisam de conferência à parte: o dígito calculado é sempre número.
    valido = (
        len(limpo) == 14
        and all(c.isascii() and (c.isdigit() or c.isalpha()) for c in base)
        and len(set(limpo)) > 1
    )
    if valido:
        primeiro = _digito(base, _PESOS_DO_PRIMEIRO)
        valido = digitos == primeiro + _digito(base + primeiro, _PESOS_DO_SEGUNDO)
    if not valido:
        raise DadoInvalidoError(f"o CNPJ {cnpj.strip()!r} não confere")
    return limpo


# --- O que pendura na empresa ---------------------------------------------------------------


def _nome(nome: str) -> str:
    limpo = nome.strip()
    if not limpo or len(limpo) > TAMANHO_DO_NOME:
        raise DadoInvalidoError(f"o nome precisa ter de 1 a {TAMANHO_DO_NOME} caracteres")
    return limpo


def _da_empresa[M: Base](sessao: Session, modelo: type[M], registro_id: int, empresa_id: int) -> M:
    registro = sessao.get(modelo, registro_id)
    if registro is None or getattr(registro, "empresa_id", None) != empresa_id:
        raise NaoEncontradoError(f"{modelo.__tablename__} {registro_id}")
    return registro


def _empresa(sessao: Session, empresa_id: int) -> Empresa:
    empresa = sessao.get(Empresa, empresa_id)
    if empresa is None:
        raise NaoEncontradoError(f"empresa {empresa_id}")
    return empresa


def cadastrar_empresa(
    sessao: Session, _administracao: AcessoAdmin, *, nome: str, cnpj: str
) -> Empresa:
    """Cadastra o cliente.

    Raises:
        DadoInvalidoError: sem nome, com o CNPJ errado ou já de outro cliente.
    """
    nome = _nome(nome)
    cnpj = conferir_cnpj(cnpj)
    if sessao.scalar(select(Empresa.id).where(Empresa.cnpj == cnpj)) is not None:
        raise DadoInvalidoError(f"o CNPJ {cnpj} já é de outro cliente")
    return servico.criar_empresa(sessao, nome=nome, cnpj=cnpj)


def cadastrar_site(
    sessao: Session,
    _administracao: AcessoAdmin,
    empresa_id: int,
    *,
    nome: str,
    fuso: str,
    abre: time | None,
    fecha: time | None,
) -> Site:
    """Cadastra um site da empresa; sem ``abre`` nem ``fecha``, ele funciona 24 horas.

    Raises:
        DadoInvalidoError: sem nome, com um fuso que não existe, ou só com um dos horários.
        NaoEncontradoError: se a empresa não existir.
    """
    empresa = _empresa(sessao, empresa_id)
    nome = _nome(nome)
    try:
        ZoneInfo(fuso)
    except (ZoneInfoNotFoundError, ValueError):
        raise DadoInvalidoError(f"o fuso {fuso!r} não existe") from None
    if (abre is None) != (fecha is None):
        raise DadoInvalidoError("o horário do site leva abre e fecha (ou nenhum, para 24 horas)")
    return servico.criar_site(sessao, empresa, nome=nome, fuso=fuso, abre=abre, fecha=fecha)


def cadastrar_portaria(
    sessao: Session, _administracao: AcessoAdmin, empresa_id: int, site_id: int, *, nome: str
) -> Portaria:
    """Cadastra uma portaria no site da empresa."""
    site = _da_empresa(sessao, Site, site_id, empresa_id)
    return servico.criar_portaria(sessao, site, nome=_nome(nome))


def cadastrar_faixa(
    sessao: Session,
    _administracao: AcessoAdmin,
    empresa_id: int,
    portaria_id: int,
    *,
    nome: str,
    sentido: Sentido,
) -> Faixa:
    """Cadastra uma faixa de entrada ou de saída na portaria da empresa."""
    portaria = _da_empresa(sessao, Portaria, portaria_id, empresa_id)
    return servico.criar_faixa(sessao, portaria, nome=_nome(nome), sentido=sentido)


def _conferir_endereco(endereco: str) -> str:
    endereco = endereco.strip()
    partes = urlsplit(endereco)
    if partes.scheme not in ESQUEMAS_DA_CAMERA or not partes.hostname:
        raise DadoInvalidoError("o endereço da câmera começa com rtsp:// (ou rtsps://)")
    if partes.username is not None or partes.password is not None:
        raise DadoInvalidoError(
            "o endereço da câmera não pode levar usuário nem senha; use os campos próprios"
        )
    return endereco


def cadastrar_camera(
    sessao: Session,
    _administracao: AcessoAdmin,
    cifra: Cifra,
    empresa_id: int,
    faixa_id: int,
    *,
    nome: str,
    posicao: Posicao,
    endereco: str,
    login: str,
    senha: str,
) -> Camera:
    """Cadastra uma câmera na faixa da empresa, com a senha cifrada."""
    faixa = _da_empresa(sessao, Faixa, faixa_id, empresa_id)
    return servico.criar_camera(
        sessao, cifra, faixa, nome=_nome(nome), posicao=posicao,
        endereco=_conferir_endereco(endereco), login=login.strip(), senha=senha,
    )  # fmt: skip


def trocar_camera(
    sessao: Session,
    _administracao: AcessoAdmin,
    cifra: Cifra,
    empresa_id: int,
    camera_id: int,
    *,
    endereco: str,
    login: str,
    senha: str | None,
) -> Camera:
    """Troca o endereço e o login da câmera; a senha, só se vier uma nova (vazia: a mesma).

    Raises:
        DadoInvalidoError: se o endereço não for rtsp:// ou trouxer usuário ou senha.
        NaoEncontradoError: se a câmera não for da empresa.
    """
    camera = _da_empresa(sessao, Camera, camera_id, empresa_id)
    camera.endereco = _conferir_endereco(endereco)
    camera.login = login.strip()
    if senha:
        camera.senha_cifrada = cifra.cifrar(senha)
    sessao.flush()
    return camera


def cadastrar_doca(
    sessao: Session, _administracao: AcessoAdmin, empresa_id: int, site_id: int, *, nome: str
) -> Doca:
    """Cadastra uma doca no site da empresa."""
    site = _da_empresa(sessao, Site, site_id, empresa_id)
    return servico.criar_doca(sessao, site, nome=_nome(nome))


# --- As pessoas e o link de senha -----------------------------------------------------------


@dataclass(frozen=True)
class LinkGerado:
    """O link de senha que acabou de nascer: o código só existe aqui (o banco tem o resumo)."""

    usuario: Usuario
    codigo: str
    vence_em: datetime


def cadastrar_pessoa(
    sessao: Session,
    administracao: AcessoAdmin,
    empresa_id: int,
    *,
    nome: str,
    email: str,
    papel: Papel,
    sites: Sequence[int],
    agora: datetime,
) -> LinkGerado:
    """Cadastra a pessoa, sem senha, nos sites da empresa, e gera o link para ela criar a senha.

    Raises:
        DadoInvalidoError: sem nome, sem site, ou com o e-mail de outra pessoa.
        NaoEncontradoError: se um dos sites não for da empresa.
    """
    empresa = _empresa(sessao, empresa_id)
    if not sites:
        raise DadoInvalidoError("a pessoa precisa de pelo menos um site")
    dos_sites = [_da_empresa(sessao, Site, site_id, empresa_id) for site_id in sites]
    usuario = servico.criar_usuario(
        sessao, Senhas(), empresa, nome=_nome(nome), email=email, papel=papel, sites=dos_sites
    )
    return _novo_link(sessao, administracao, usuario, agora=agora)


def gerar_link_de_senha(
    sessao: Session,
    administracao: AcessoAdmin,
    empresa_id: int,
    usuario_id: int,
    *,
    agora: datetime,
) -> LinkGerado:
    """Um link novo de senha para a pessoa (a senha esquecida); o anterior deixa de valer.

    Raises:
        DadoInvalidoError: se a pessoa estiver desativada.
        NaoEncontradoError: se a pessoa não for da empresa.
    """
    usuario = _da_empresa(sessao, Usuario, usuario_id, empresa_id)
    if not usuario.ativo:
        raise DadoInvalidoError("a pessoa está desativada: reative antes de gerar o link")
    return _novo_link(sessao, administracao, usuario, agora=agora)


def _novo_link(
    sessao: Session, administracao: AcessoAdmin, usuario: Usuario, *, agora: datetime
) -> LinkGerado:
    _trocar_os_links(sessao, usuario, agora)
    codigo = secrets.token_urlsafe(32)
    link = LinkDeSenha(
        usuario_id=usuario.id,
        empresa_id=usuario.empresa_id,
        codigo_resumo=resumo_rapido(codigo),
        criado_por=administracao.administrador_id,
        criado_em=agora,
        vence_em=agora + VALIDADE_DO_LINK,
    )
    sessao.add(link)
    sessao.flush()
    return LinkGerado(usuario=usuario, codigo=codigo, vence_em=link.vence_em)


def _trocar_os_links(sessao: Session, usuario: Usuario, agora: datetime) -> None:
    sessao.execute(
        update(LinkDeSenha)
        .where(
            LinkDeSenha.usuario_id == usuario.id,
            LinkDeSenha.usado_em.is_(None),
            LinkDeSenha.trocado_em.is_(None),
        )
        .values(trocado_em=agora)
    )


def _fechar_as_sessoes(sessao: Session, usuario: Usuario) -> None:
    sessao.execute(delete(SessaoLogin).where(SessaoLogin.usuario_id == usuario.id))


def mudar_situacao_da_pessoa(
    sessao: Session,
    _administracao: AcessoAdmin,
    empresa_id: int,
    usuario_id: int,
    *,
    ativa: bool,
    agora: datetime,
) -> Usuario:
    """Ativa ou desativa a pessoa; desativar fecha as sessões dela e tira o link de uso."""
    usuario = _da_empresa(sessao, Usuario, usuario_id, empresa_id)
    usuario.ativo = ativa
    if not ativa:
        _fechar_as_sessoes(sessao, usuario)
        _trocar_os_links(sessao, usuario, agora)
    sessao.flush()
    return usuario


def link_de_senha(sessao: Session, codigo: str, *, agora: datetime) -> LinkDeSenha | None:
    """O link do código, se ele ainda vale (não usado, não trocado, no prazo, pessoa ativa)."""
    link = sessao.scalar(
        select(LinkDeSenha).where(
            LinkDeSenha.codigo_resumo == resumo_rapido(codigo),
            LinkDeSenha.usado_em.is_(None),
            LinkDeSenha.trocado_em.is_(None),
            LinkDeSenha.vence_em > agora,
        )
    )
    if link is None:
        return None
    usuario = sessao.get(Usuario, link.usuario_id)
    return link if usuario is not None and usuario.ativo else None


def pessoa_do_link(sessao: Session, link: LinkDeSenha) -> Usuario:
    """A pessoa do link."""
    usuario = sessao.get(Usuario, link.usuario_id)
    assert usuario is not None  # a chave estrangeira garante
    return usuario


def criar_senha_pelo_link(
    sessao: Session,
    senhas: Senhas,
    codigo: str,
    *,
    senha: str,
    pin: str | None,
    agora: datetime,
) -> Usuario:
    """Cria a senha (e o PIN do porteiro) pelo link, que deixa de valer; fecha as sessões.

    Raises:
        NaoEncontradoError: se o link não vale (usado, trocado, vencido ou de pessoa desativada).
        DadoInvalidoError: com a senha fora da regra, sem o PIN do porteiro, ou com PIN de quem
            não é porteiro. Nada muda.
    """
    link = link_de_senha(sessao, codigo, agora=agora)
    if link is None:
        raise NaoEncontradoError("link de senha")
    usuario = pessoa_do_link(sessao, link)
    if usuario.papel == "porteiro":
        if pin is None or not servico.FORMATO_DO_PIN.fullmatch(pin):
            raise DadoInvalidoError("o porteiro precisa de um PIN de 6 números")
    elif pin:
        raise DadoInvalidoError("só o porteiro tem PIN")
    servico.definir_senha(sessao, senhas, usuario, senha)
    if pin is not None and usuario.papel == "porteiro":
        servico.definir_pin(sessao, senhas, usuario, pin)
    link.usado_em = agora
    _fechar_as_sessoes(sessao, usuario)
    sessao.flush()
    return usuario


# --- A ficha da empresa ---------------------------------------------------------------------


@dataclass(frozen=True)
class CameraDaFicha:
    """A câmera como a tela mostra: sem a senha."""

    id: int
    nome: str
    posicao: str
    endereco: str
    login: str


@dataclass(frozen=True)
class FaixaDaFicha:
    """A faixa e as câmeras dela."""

    faixa: Faixa
    cameras: list[CameraDaFicha]


@dataclass(frozen=True)
class PortariaDaFicha:
    """A portaria e as faixas dela."""

    portaria: Portaria
    faixas: list[FaixaDaFicha]


@dataclass(frozen=True)
class SiteDaFicha:
    """O site, as portarias e as docas."""

    site: Site
    portarias: list[PortariaDaFicha]
    docas: list[Doca]


@dataclass(frozen=True)
class PessoaDaFicha:
    """A pessoa, os sites dela, se já tem senha e até quando vale o link que ela ainda não usou."""

    usuario: Usuario
    sites: list[str]
    tem_senha: bool
    link_vence_em: datetime | None


@dataclass(frozen=True)
class FichaDaEmpresa:
    """Tudo o que a administração cadastrou de uma empresa."""

    empresa: Empresa
    sites: list[SiteDaFicha]
    pessoas: list[PessoaDaFicha]


def ficha_da_empresa(
    sessao: Session, _administracao: AcessoAdmin, empresa_id: int, *, agora: datetime
) -> FichaDaEmpresa:
    """A empresa, a estrutura de cada site e as pessoas, por nome.

    Raises:
        NaoEncontradoError: se a empresa não existir.
    """
    empresa = _empresa(sessao, empresa_id)

    def da_empresa[M: (Site, Portaria, Faixa, Camera, Doca, Usuario)](modelo: type[M]) -> list[M]:
        consulta = select(modelo).where(modelo.empresa_id == empresa_id).order_by(modelo.nome)
        return list(sessao.scalars(consulta))

    cameras = [
        (c.faixa_id, CameraDaFicha(c.id, c.nome, c.posicao, c.endereco, c.login))
        for c in da_empresa(Camera)
    ]
    faixas = [
        (f.portaria_id, FaixaDaFicha(f, [c for faixa_id, c in cameras if faixa_id == f.id]))
        for f in da_empresa(Faixa)
    ]
    portarias = da_empresa(Portaria)
    docas = da_empresa(Doca)
    sites = [
        SiteDaFicha(
            site,
            [
                PortariaDaFicha(p, [f for portaria_id, f in faixas if portaria_id == p.id])
                for p in portarias
                if p.site_id == site.id
            ],
            [d for d in docas if d.site_id == site.id],
        )
        for site in da_empresa(Site)
    ]
    nomes = {site.site.id: site.site.nome for site in sites}
    ligacoes = sessao.execute(
        select(UsuarioSite.usuario_id, UsuarioSite.site_id).where(
            UsuarioSite.empresa_id == empresa_id
        )
    ).all()
    links = {
        usuario_id: vence_em
        for usuario_id, vence_em in sessao.execute(
            select(LinkDeSenha.usuario_id, LinkDeSenha.vence_em).where(
                LinkDeSenha.empresa_id == empresa_id,
                LinkDeSenha.usado_em.is_(None),
                LinkDeSenha.trocado_em.is_(None),
                LinkDeSenha.vence_em > agora,
            )
        ).all()
    }
    pessoas = [
        PessoaDaFicha(
            usuario,
            sorted(nomes[site_id] for usuario_id, site_id in ligacoes if usuario_id == usuario.id),
            usuario.senha_resumo is not None,
            links.get(usuario.id),
        )
        for usuario in da_empresa(Usuario)
    ]
    return FichaDaEmpresa(empresa, sites, pessoas)

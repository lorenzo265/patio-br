"""Tabelas do cadastro (SDD 5.1): a estrutura física do cliente, os usuários e o login.

Toda tabela de dados do cliente tem ``empresa_id``. Cada tabela filha aponta para o pai por
uma chave estrangeira composta, (pai, empresa): o banco recusa, por exemplo, uma portaria da
empresa B num site da empresa A, mesmo que o código erre (SDD 5.5).

A administração (nós) fica fora das empresas, numa tabela própria (SDD D-19).
"""

from datetime import datetime
from typing import Literal, get_args

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base

Sentido = Literal["entrada", "saida"]
Posicao = Literal["frente", "tras", "contexto"]
Papel = Literal["porteiro", "patio", "gestor"]
"""Papéis dos usuários do cliente. A administração (nós) não é usuário de cliente (D-19)."""

FUSO_PADRAO = "America/Sao_Paulo"

FORMATO_CNPJ = "^[0-9A-Z]{12}[0-9]{2}$"
"""14 caracteres: 12 letras ou números (CNPJ alfanumérico, desde julho de 2026) e 2 dígitos."""


def _texto_de(valores: object, nome: str) -> Enum:
    # Guardado como texto com CHECK (e não como tipo ENUM do PostgreSQL): mais fácil de migrar.
    return Enum(*get_args(valores), name=nome, native_enum=False, create_constraint=True)


def _do_pai_na_mesma_empresa(pai: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint([f"{pai}_id", "empresa_id"], [f"{pai}.id", f"{pai}.empresa_id"])


def _pode_ser_pai() -> UniqueConstraint:
    # A chave estrangeira composta dos filhos precisa de (id, empresa_id) único no pai.
    return UniqueConstraint("id", "empresa_id")


class Empresa(Base):
    """Um cliente."""

    __tablename__ = "empresa"
    __table_args__ = (CheckConstraint(f"cnpj ~ '{FORMATO_CNPJ}'", name="cnpj_formato"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)


class Site(Base):
    """Um local do cliente com portaria e pátio (ex.: um centro de distribuição)."""

    __tablename__ = "site"
    __table_args__ = (_pode_ser_pai(),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    nome: Mapped[str]
    fuso: Mapped[str] = mapped_column(default=FUSO_PADRAO)


class Portaria(Base):
    """Uma portaria do site; tem uma ou mais faixas."""

    __tablename__ = "portaria"
    __table_args__ = (_pode_ser_pai(), _do_pai_na_mesma_empresa("site"))

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    nome: Mapped[str]


class Faixa(Base):
    """Uma faixa da portaria, de entrada ou de saída."""

    __tablename__ = "faixa"
    __table_args__ = (_pode_ser_pai(), _do_pai_na_mesma_empresa("portaria"))

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    portaria_id: Mapped[int]
    nome: Mapped[str]
    sentido: Mapped[Sentido] = mapped_column(_texto_de(Sentido, "sentido"))


class Camera(Base):
    """Uma câmera IP da faixa. A senha fica cifrada (ver ``nuvem.cifra``)."""

    __tablename__ = "camera"
    __table_args__ = (_do_pai_na_mesma_empresa("faixa"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    faixa_id: Mapped[int]
    nome: Mapped[str]
    posicao: Mapped[Posicao] = mapped_column(_texto_de(Posicao, "posicao"))
    endereco: Mapped[str]
    """Endereço RTSP, sem usuário nem senha."""
    login: Mapped[str]
    senha_cifrada: Mapped[str]


class Doca(Base):
    """Uma doca de carga e descarga do site."""

    __tablename__ = "doca"
    __table_args__ = (_do_pai_na_mesma_empresa("site"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    nome: Mapped[str]


class Usuario(Base):
    """Uma pessoa do cliente que usa o painel."""

    __tablename__ = "usuario"
    __table_args__ = (_pode_ser_pai(),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    nome: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    papel: Mapped[Papel] = mapped_column(_texto_de(Papel, "papel"))
    senha_resumo: Mapped[str | None]
    """Resumo argon2 da senha; vazio = ainda sem senha, e quem não tem senha não entra."""
    pin_resumo: Mapped[str | None]
    """Resumo argon2 do PIN de 6 números, só do porteiro (troca de porteiro no tablet)."""
    ativo: Mapped[bool] = mapped_column(default=True, server_default=true())
    """Desativado não entra, e as sessões que ele já tinha deixam de valer."""


class UsuarioSite(Base):
    """Os sites que um usuário vê; sempre da mesma empresa do usuário."""

    __tablename__ = "usuario_site"
    __table_args__ = (
        PrimaryKeyConstraint("usuario_id", "site_id"),
        _do_pai_na_mesma_empresa("usuario"),
        _do_pai_na_mesma_empresa("site"),
    )

    usuario_id: Mapped[int]
    site_id: Mapped[int]
    empresa_id: Mapped[int]


class Administrador(Base):
    """Uma pessoa da administração da plataforma (nós), fora de qualquer empresa (D-19)."""

    __tablename__ = "administrador"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    senha_resumo: Mapped[str]
    ativo: Mapped[bool] = mapped_column(default=True, server_default=true())


class SessaoLogin(Base):
    """Uma sessão aberta no painel (D-20): de um usuário do cliente ou da administração.

    O navegador guarda o código; aqui fica só o resumo dele. A sessão do usuário aponta para
    ele pela dupla (usuário, empresa), como toda tabela filha do cliente.
    """

    __tablename__ = "sessao_login"
    __table_args__ = (
        _do_pai_na_mesma_empresa("usuario"),
        CheckConstraint(
            "(usuario_id IS NOT NULL AND empresa_id IS NOT NULL AND administrador_id IS NULL)"
            " OR (usuario_id IS NULL AND empresa_id IS NULL AND administrador_id IS NOT NULL)",
            name="de_uma_pessoa_so",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_resumo: Mapped[str] = mapped_column(String(64), unique=True)
    """SHA-256 do código do cookie (o código é aleatório e longo; não precisa de argon2)."""
    usuario_id: Mapped[int | None]
    empresa_id: Mapped[int | None]
    administrador_id: Mapped[int | None] = mapped_column(ForeignKey("administrador.id"))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TentativaLogin(Base):
    """Um erro de senha ou de PIN, para o limite de tentativas (SDD 8.2).

    Guarda só o resumo do alvo (o e-mail digitado, ou o porteiro do PIN), nunca o e-mail.
    """

    __tablename__ = "tentativa_login"

    id: Mapped[int] = mapped_column(primary_key=True)
    alvo_resumo: Mapped[str] = mapped_column(String(64), index=True)
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True))

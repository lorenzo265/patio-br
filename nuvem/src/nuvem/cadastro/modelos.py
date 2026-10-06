"""Tabelas do cadastro (SDD 5.1): a estrutura física do cliente, os usuários e o login.

Toda tabela de dados do cliente tem ``empresa_id``. Cada tabela filha aponta para o pai por
uma chave estrangeira composta, (pai, empresa): o banco recusa, por exemplo, uma portaria da
empresa B num site da empresa A, mesmo que o código erre (SDD 5.5).

A administração (nós) fica fora das empresas, numa tabela própria (SDD D-19).
"""

from datetime import datetime, time
from typing import Literal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
    String,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from nuvem.banco import Base, do_pai_na_mesma_empresa, pode_ser_pai, texto_de_lista

Sentido = Literal["entrada", "saida"]
Posicao = Literal["frente", "tras", "contexto"]
Papel = Literal["porteiro", "patio", "gestor"]
"""Papéis dos usuários do cliente. A administração (nós) não é usuário de cliente (D-19)."""
Falta = Literal["codigo", "ligar"]
"""O que falta à sessão pela metade (D-60): o código do app, ou ligar a verificação."""

FUSO_PADRAO = "America/Sao_Paulo"

FORMATO_CNPJ = "^[0-9A-Z]{12}[0-9]{2}$"
"""14 caracteres: 12 letras ou números (CNPJ alfanumérico, desde julho de 2026) e 2 dígitos."""


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
    __table_args__ = (
        pode_ser_pai(),
        CheckConstraint(
            "(abre IS NULL AND fecha IS NULL)"
            " OR (abre IS NOT NULL AND fecha IS NOT NULL AND abre < fecha)",
            name="horario_em_ordem",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    nome: Mapped[str]
    fuso: Mapped[str] = mapped_column(default=FUSO_PADRAO)
    abre: Mapped[time | None]
    """Horário de operação, na hora do site; sem ``abre`` nem ``fecha``, funciona 24 horas."""
    fecha: Mapped[time | None]


class Portaria(Base):
    """Uma portaria do site; tem uma ou mais faixas."""

    __tablename__ = "portaria"
    __table_args__ = (pode_ser_pai(), do_pai_na_mesma_empresa("site"))

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    nome: Mapped[str]


class Faixa(Base):
    """Uma faixa da portaria, de entrada ou de saída."""

    __tablename__ = "faixa"
    __table_args__ = (pode_ser_pai(), do_pai_na_mesma_empresa("portaria"))

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    portaria_id: Mapped[int]
    nome: Mapped[str]
    sentido: Mapped[Sentido] = mapped_column(texto_de_lista(Sentido, "sentido"))


class Camera(Base):
    """Uma câmera IP da faixa. A senha fica cifrada (ver ``nuvem.cifra``)."""

    __tablename__ = "camera"
    __table_args__ = (do_pai_na_mesma_empresa("faixa"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    faixa_id: Mapped[int]
    nome: Mapped[str]
    posicao: Mapped[Posicao] = mapped_column(texto_de_lista(Posicao, "posicao"))
    endereco: Mapped[str]
    """Endereço RTSP, sem usuário nem senha."""
    login: Mapped[str]
    senha_cifrada: Mapped[str]


class Doca(Base):
    """Uma doca de carga e descarga do site."""

    __tablename__ = "doca"
    __table_args__ = (pode_ser_pai(), do_pai_na_mesma_empresa("site"))

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int]
    site_id: Mapped[int]
    nome: Mapped[str]


class ComDuasEtapas:
    """A verificação em duas etapas de uma conta (SDD 8.2, D-60)."""

    duas_etapas_cifrado: Mapped[str | None]
    """O segredo do app autenticador, cifrado (a nuvem precisa dele para conferir o código)."""
    duas_etapas_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Quando a verificação foi ligada; vazio com o segredo = ligação ainda não confirmada."""
    duas_etapas_passo: Mapped[int | None] = mapped_column(BigInteger)
    """O intervalo do último código aceito: ele e os anteriores não valem mais."""


class Usuario(ComDuasEtapas, Base):
    """Uma pessoa do cliente que usa o painel."""

    __tablename__ = "usuario"
    __table_args__ = (pode_ser_pai(),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    nome: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    papel: Mapped[Papel] = mapped_column(texto_de_lista(Papel, "papel"))
    senha_resumo: Mapped[str | None]
    """Resumo argon2 da senha; vazio = ainda sem senha, e quem não tem senha não entra."""
    pin_resumo: Mapped[str | None]
    """Resumo argon2 do PIN de 6 números, só do porteiro (troca de porteiro no tablet)."""
    ativo: Mapped[bool] = mapped_column(default=True, server_default=true())
    """Desativado não entra, e as sessões que ele já tinha deixam de valer."""
    duas_etapas_zerada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """A última vez que a administração zerou a verificação dele (perdeu o celular)."""
    duas_etapas_zerada_por: Mapped[int | None] = mapped_column(ForeignKey("administrador.id"))


class UsuarioSite(Base):
    """Os sites que um usuário vê; sempre da mesma empresa do usuário."""

    __tablename__ = "usuario_site"
    __table_args__ = (
        PrimaryKeyConstraint("usuario_id", "site_id"),
        do_pai_na_mesma_empresa("usuario"),
        do_pai_na_mesma_empresa("site"),
    )

    usuario_id: Mapped[int]
    site_id: Mapped[int]
    empresa_id: Mapped[int]


class Administrador(ComDuasEtapas, Base):
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
        do_pai_na_mesma_empresa("usuario"),
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
    falta: Mapped[Falta | None] = mapped_column(texto_de_lista(Falta, "falta"))
    """Vazio na sessão de sempre. Na sessão pela metade (D-60), o que falta para entrar: ela só
    serve para a tela do código ou de ligar a verificação."""


class CodigoRecuperacao(Base):
    """Um código de recuperação da verificação em duas etapas (D-60): vale uma vez.

    Guarda só o resumo argon2, como a senha (regra 6 do ``CLAUDE.md``).
    """

    __tablename__ = "codigo_recuperacao"
    __table_args__ = (
        do_pai_na_mesma_empresa("usuario"),
        CheckConstraint(
            "(usuario_id IS NOT NULL AND empresa_id IS NOT NULL AND administrador_id IS NULL)"
            " OR (usuario_id IS NULL AND empresa_id IS NULL AND administrador_id IS NOT NULL)",
            name="de_uma_pessoa_so",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(index=True)
    empresa_id: Mapped[int | None]
    administrador_id: Mapped[int | None] = mapped_column(ForeignKey("administrador.id"), index=True)
    resumo: Mapped[str]
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TentativaLogin(Base):
    """Um erro de senha ou de PIN, para o limite de tentativas (SDD 8.2).

    Guarda só o resumo do alvo (o e-mail digitado, ou o porteiro do PIN), nunca o e-mail.
    """

    __tablename__ = "tentativa_login"

    id: Mapped[int] = mapped_column(primary_key=True)
    alvo_resumo: Mapped[str] = mapped_column(String(64), index=True)
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True))

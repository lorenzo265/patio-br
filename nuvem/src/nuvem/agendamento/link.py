"""Link da transportadora (SDD 3.4, 6.2, 8.2 e D-34): agendar pelo celular, sem conta.

- **O link:** o gestor gera; o código é aleatório e longo, vai no endereço e aparece uma vez só,
  para quem gerou. O banco guarda só o resumo. O link vence, pode ser revogado e tem um limite de
  agendamentos.
- **Vencido, revogado ou inventado** dá ``NaoEncontradoError`` (404, sem dizer qual); **no
  limite**, ``LinkEsgotadoError`` (429).
- **O formulário** pede tudo (placas, motorista, celular, janela, tipo, toneladas; a NF-e é
  opcional). A janela é escolhida no fuso do site, num dia só, dentro do horário de operação,
  começando no futuro e no máximo 60 dias à frente.
- **Cada envio** é um agendamento novo, com o código externo ``<link>-<número do envio>``. O envio
  recusado não gasta o limite.

As funções gravam com ``flush``; o ``commit`` é de quem chama.
"""

import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem.agendamento import servico
from nuvem.agendamento.conectores import Lido, Recusado
from nuvem.agendamento.formato import Celular, DadosDoAgendamento, Toneladas, descrever_erros
from nuvem.agendamento.modelos import Agendamento, LinkTransportadora, Origem
from nuvem.agendamento.servico import SiteDoAgendamento
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.servico import HorarioDoSite
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.senhas import resumo_rapido

VALIDADE_PADRAO = timedelta(days=30)
VALIDADE_MINIMA = timedelta(days=1)
VALIDADE_MAXIMA = timedelta(days=180)
LIMITE_PADRAO = 50
LIMITE_MAXIMO = 1000
ANTECEDENCIA_MAXIMA = timedelta(days=60)
"""Até quantos dias à frente a transportadora marca pelo link."""

TAMANHO_DO_NOME = 120


class LinkEsgotadoError(Exception):
    """O link chegou ao limite de agendamentos: a API responde 429."""


@dataclass(frozen=True)
class LinkGerado:
    """O link novo e o código dele (que só aparece agora, para o gestor mandar)."""

    link: LinkTransportadora
    codigo: str


@dataclass(frozen=True)
class LinkAberto:
    """O que o formulário mostra: para quem é o link e o site onde se agenda."""

    nome: str
    site: HorarioDoSite


@dataclass(frozen=True)
class FormularioDoLink:
    """Os campos do formulário, como o navegador manda (texto; vazio = não preenchido)."""

    data: str = ""
    hora_inicio: str = ""
    hora_fim: str = ""
    tipo: str = ""
    placa_cavalo: str = ""
    reboque_1: str = ""
    reboque_2: str = ""
    reboque_3: str = ""
    motorista_nome: str = ""
    motorista_celular: str = ""
    toneladas: str = ""
    chave_nfe: str = ""


class _DadosDoLink(DadosDoAgendamento):
    """O formato interno, com o que o link pede a mais: motorista, celular e toneladas."""

    motorista_nome: Annotated[str, Field(max_length=120)]
    motorista_celular: Celular
    toneladas: Toneladas


# --- Gestor -----------------------------------------------------------------------------------


def gerar_link(
    sessao: Session,
    acesso: Acesso,
    site_id: int,
    *,
    nome: str,
    agora: datetime,
    validade: timedelta = VALIDADE_PADRAO,
    limite: int = LIMITE_PADRAO,
) -> LinkGerado:
    """Gera um link de agendamento para uma transportadora, num site do gestor.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
        DadoInvalidoError: se o nome, a validade ou o limite estiverem fora da regra.
    """
    nome = nome.strip()
    if not 0 < len(nome) <= TAMANHO_DO_NOME:
        raise DadoInvalidoError(f"o nome do link tem de 1 a {TAMANHO_DO_NOME} caracteres")
    if not VALIDADE_MINIMA <= validade <= VALIDADE_MAXIMA:
        raise DadoInvalidoError("o link vale de 1 a 180 dias")
    if not 0 < limite <= LIMITE_MAXIMO:
        raise DadoInvalidoError(f"o limite é de 1 a {LIMITE_MAXIMO} agendamentos")
    site = cadastro.obter_site(sessao, acesso, site_id)
    codigo = secrets.token_urlsafe(24)
    link = LinkTransportadora(
        empresa_id=site.empresa_id,
        site_id=site.id,
        nome=nome,
        codigo_resumo=resumo_rapido(codigo),
        criado_por=acesso.usuario_id,
        criado_em=agora,
        vence_em=agora + validade,
        limite_de_envios=limite,
        envios=0,
    )
    sessao.add(link)
    sessao.flush()
    return LinkGerado(link=link, codigo=codigo)


def revogar_link(
    sessao: Session, acesso: Acesso, link_id: int, *, agora: datetime
) -> LinkTransportadora:
    """Revoga um link: deixa de valer na hora. Revogar de novo não muda nada.

    Raises:
        NaoEncontradoError: se o link não for de um site visível para este usuário.
    """
    link = sessao.scalars(
        select(LinkTransportadora)
        .where(
            LinkTransportadora.id == link_id,
            LinkTransportadora.empresa_id == acesso.empresa_id,
            LinkTransportadora.site_id.in_(acesso.sites),
        )
        .with_for_update()
    ).one_or_none()
    if link is None:
        raise NaoEncontradoError(f"link {link_id}")
    if link.revogado_em is None:
        link.revogado_em = agora
        sessao.flush()
    return link


def listar_links(sessao: Session, acesso: Acesso, site_id: int) -> list[LinkTransportadora]:
    """Os links de um site, do mais novo ao mais velho.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    return list(
        sessao.scalars(
            select(LinkTransportadora)
            .where(
                LinkTransportadora.empresa_id == acesso.empresa_id,
                LinkTransportadora.site_id == site.id,
            )
            .order_by(LinkTransportadora.criado_em.desc(), LinkTransportadora.id.desc())
        )
    )


SituacaoDoLink = Literal["ativo", "revogado", "vencido", "esgotado"]


def situacao_do_link(link: LinkTransportadora, *, agora: datetime) -> SituacaoDoLink:
    """Como o link está agora, para a tela do gestor (o primeiro motivo que o impede de valer)."""
    if link.revogado_em is not None:
        return "revogado"
    if link.vence_em <= agora:
        return "vencido"
    if link.envios >= link.limite_de_envios:
        return "esgotado"
    return "ativo"


# --- Transportadora ---------------------------------------------------------------------------


def abrir_link(sessao: Session, codigo: str, *, agora: datetime) -> LinkAberto:
    """O que o formulário do link mostra.

    Raises:
        NaoEncontradoError: se o link não existir, tiver vencido ou sido revogado.
        LinkEsgotadoError: se o link chegou ao limite de agendamentos.
    """
    link = _link_que_vale(sessao, codigo, agora=agora)
    if link.envios >= link.limite_de_envios:
        raise LinkEsgotadoError
    return LinkAberto(nome=link.nome, site=_horario(sessao, link))


def agendar_pelo_link(
    sessao: Session, codigo: str, formulario: FormularioDoLink, *, agora: datetime
) -> Agendamento | list[str]:
    """Cria o agendamento que a transportadora mandou pelo link.

    Returns:
        O agendamento criado, ou os erros do formulário, em português (nada é gravado).

    Raises:
        NaoEncontradoError: se o link não existir, tiver vencido ou sido revogado.
        LinkEsgotadoError: se o link chegou ao limite de agendamentos.
    """
    # Trava o link: dois envios ao mesmo tempo não passam juntos do limite.
    link = _link_que_vale(sessao, codigo, agora=agora, travar=True)
    if link.envios >= link.limite_de_envios:
        raise LinkEsgotadoError
    numero = link.envios + 1
    conector = ConectorDoLink(
        _horario(sessao, link), codigo_externo=f"{link.id}-{numero}", agora=agora
    )
    dados = conector.conferir(formulario)
    if isinstance(dados, list):
        return dados
    site = SiteDoAgendamento(
        empresa_id=link.empresa_id, site_id=link.site_id, usuario_id=None, link_id=link.id
    )
    gravado = servico.gravar(sessao, site, "link", dados, agora=agora)
    link.envios = numero
    sessao.flush()
    return gravado.agendamento


def agendamento_do_link(
    sessao: Session, codigo: str, codigo_externo: str, *, agora: datetime
) -> Agendamento:
    """Um agendamento feito por este link (a confirmação que a transportadora vê).

    Vale mesmo com o link no limite: o último envio também tem confirmação.

    Raises:
        NaoEncontradoError: se o link não valer, ou o agendamento não for dele.
    """
    link = _link_que_vale(sessao, codigo, agora=agora)
    agendamento = sessao.scalars(
        select(Agendamento).where(
            Agendamento.empresa_id == link.empresa_id,
            Agendamento.site_id == link.site_id,
            Agendamento.link_id == link.id,
            Agendamento.origem == "link",
            Agendamento.codigo_externo == codigo_externo,
        )
    ).one_or_none()
    if agendamento is None:
        raise NaoEncontradoError(f"agendamento {codigo_externo} do link")
    return agendamento


def horario_do_link(sessao: Session, codigo: str, *, agora: datetime) -> HorarioDoSite:
    """O site do link (para mostrar a confirmação no fuso dele), mesmo com o link no limite.

    Raises:
        NaoEncontradoError: se o link não existir, tiver vencido ou sido revogado.
    """
    return _horario(sessao, _link_que_vale(sessao, codigo, agora=agora))


def _link_que_vale(
    sessao: Session, codigo: str, *, agora: datetime, travar: bool = False
) -> LinkTransportadora:
    consulta = select(LinkTransportadora).where(
        LinkTransportadora.codigo_resumo == resumo_rapido(codigo),
        LinkTransportadora.revogado_em.is_(None),
        LinkTransportadora.vence_em > agora,
    )
    if travar:
        consulta = consulta.with_for_update().execution_options(populate_existing=True)
    link = sessao.scalars(consulta).one_or_none()
    if link is None:
        raise NaoEncontradoError("link")
    return link


def _horario(sessao: Session, link: LinkTransportadora) -> HorarioDoSite:
    return cadastro.horario_do_site(sessao, empresa_id=link.empresa_id, site_id=link.site_id)


# --- O conector -------------------------------------------------------------------------------


class ConectorDoLink:
    """O conector do link (SDD 3.4): o formulário vira um agendamento no formato interno."""

    def __init__(self, site: HorarioDoSite, *, codigo_externo: str, agora: datetime) -> None:
        """Prepara o conector para um envio.

        Args:
            site: o fuso e o horário de operação do site do link.
            codigo_externo: o código do agendamento novo (``<link>-<número do envio>``).
            agora: a hora do envio (a janela precisa começar depois dela).
        """
        self._site = site
        self._codigo_externo = codigo_externo
        self._agora = agora

    @property
    def origem(self) -> Origem:
        """Os agendamentos do link têm origem ``link``."""
        return "link"

    def ler(self, entrada: FormularioDoLink) -> Iterable[Lido | Recusado]:
        """O formulário, entendido ou recusado (é um item só)."""
        dados = self.conferir(entrada)
        if isinstance(dados, list):
            return [Recusado(onde="formulário", motivo="; ".join(dados))]
        return [Lido(onde="formulário", dados=dados)]

    def conferir(self, formulario: FormularioDoLink) -> DadosDoAgendamento | list[str]:
        """Os dados do agendamento, ou todos os erros do formulário, em português."""
        erros, janela = self._janela(formulario)
        if janela is None:
            # Sem janela, os outros campos ainda são conferidos, com uma janela qualquer.
            janela = (self._agora + timedelta(hours=1), self._agora + timedelta(hours=2))
        reboques = (formulario.reboque_1, formulario.reboque_2, formulario.reboque_3)
        campos = {
            "codigo_externo": self._codigo_externo,
            "janela_inicio": janela[0],
            "janela_fim": janela[1],
            "tipo": formulario.tipo,
            "placa_cavalo": formulario.placa_cavalo,
            "placas_reboques": [placa for placa in reboques if placa.strip()],
            "motorista_nome": formulario.motorista_nome,
            "motorista_celular": formulario.motorista_celular,
            "toneladas": formulario.toneladas,
            "chave_nfe": formulario.chave_nfe,
        }
        try:
            dados = _DadosDoLink.model_validate(campos)
        except ValidationError as erro:
            return erros + descrever_erros(erro)
        return erros or dados

    def _janela(
        self, formulario: FormularioDoLink
    ) -> tuple[list[str], tuple[datetime, datetime] | None]:
        dia = _ler(formulario.data, date.fromisoformat, "data", "use o formato do calendário")
        inicio = _ler(
            formulario.hora_inicio, time.fromisoformat, "hora de início", "use o formato do relógio"
        )
        fim = _ler(
            formulario.hora_fim, time.fromisoformat, "hora de fim", "use o formato do relógio"
        )
        erros = [erro for erro in (dia, inicio, fim) if isinstance(erro, str)]
        if erros:
            return erros, None
        assert isinstance(dia, date) and isinstance(inicio, time) and isinstance(fim, time)
        fuso = ZoneInfo(self._site.fuso)
        janela = (datetime.combine(dia, inicio, fuso), datetime.combine(dia, fim, fuso))
        if fim <= inicio:
            return [], janela  # o formato interno diz o erro: o fim antes do início
        abre, fecha = self._site.abre, self._site.fecha
        if abre is not None and fecha is not None and (inicio < abre or fim > fecha):
            erros.append(
                "a janela precisa ficar dentro do horário do site, "
                f"das {abre:%H:%M} às {fecha:%H:%M}"
            )
        if janela[0] <= self._agora:
            erros.append("a janela precisa começar no futuro")
        elif janela[0] > self._agora + ANTECEDENCIA_MAXIMA:
            erros.append(f"a janela pode ser marcada até {ANTECEDENCIA_MAXIMA.days} dias à frente")
        return erros, janela


def _ler[T](texto: str, converter: Callable[[str], T], rotulo: str, formato: str) -> T | str:
    """Converte o campo; devolve o erro em português se ele faltar ou não estiver no formato."""
    texto = texto.strip()
    if not texto:
        return f"{rotulo}: falta"
    try:
        return converter(texto)
    except ValueError:
        return f"{rotulo}: {formato}"

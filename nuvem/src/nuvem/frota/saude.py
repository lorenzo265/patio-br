"""A saúde das caixas de borda na nuvem (SDD 7.4, D-65).

- **Receber:** a saúde atualiza a caixa (o último contato, as versões, a última saúde e a
  diferença do relógio) e entra no histórico; o histórico da caixa com mais de 7 dias se apaga.
- **Sem contato:** a última saúde chegou há 3 minutos ou mais. A caixa que nunca mandou saúde
  não conta (o site da demonstração tem caixa sem programa rodando).
- **A portaria** vê "site sem conexão desde HH:MM"; **a administração** vê a frota e o
  histórico de cada caixa, hora a hora.

As funções gravam com ``flush``; o ``commit`` é de quem chama.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Select, delete, func, select, text
from sqlalchemy.orm import Session

from contratos.saude import Saude
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, AcessoAdmin
from nuvem.cadastro.modelos import Camera, Empresa, Faixa, Portaria, Site
from nuvem.erros import NaoEncontradoError
from nuvem.frota.modelos import CaixaBorda, SaudeCaixa
from nuvem.frota.servico import AcessoDaCaixa

LIMITE_SEM_CONTATO = timedelta(minutes=3)
"""Sem saúde por este tempo, a caixa está sem contato (o tempo do alerta, ``[ABERTO-09]``)."""

GUARDA_DO_HISTORICO = timedelta(days=7)

SAUDES_POR_HORA = 60
"""Uma saúde por minuto: a hora sem falta tem 60."""


class SaudeDeOutraCaixaError(Exception):
    """A saúde diz outra caixa ou outro site que não os da chave (403)."""


@dataclass(frozen=True)
class CameraNaFrota:
    """Uma câmera de placa, como a caixa contou na última saúde."""

    nome: str
    no_ar: bool
    quadros_por_segundo: float
    ultimo_quadro: datetime | None


@dataclass(frozen=True)
class CaixaNaFrota:
    """Uma caixa como a administração a vê na frota."""

    caixa_id: int
    empresa: str
    site: str
    fuso: str
    """O fuso do site, para mostrar as horas."""
    ativada_em: datetime
    ultimo_contato: datetime | None
    sem_contato: bool
    versao_programa: str | None
    versao_leitor: str | None
    diferenca_do_relogio: float | None
    saude: Saude | None
    """A última saúde; vazia se a caixa nunca mandou."""
    cameras: list[CameraNaFrota]


@dataclass(frozen=True)
class HoraDaCaixa:
    """O resumo de uma hora do histórico de uma caixa (no fuso do site)."""

    hora: datetime
    contatos: int
    """Quantas saúdes chegaram (de 60)."""
    cpu: float
    """A maior."""
    temperatura: float | None
    """A maior; vazia se nenhuma saúde da hora disse."""
    disco: float
    """O maior."""
    cameras_no_ar: int
    """O menor número de câmeras no ar."""
    cameras: int
    """O maior número de câmeras abertas."""
    passagens_na_fila: int
    """A maior fila."""
    diferenca_do_relogio: float
    """A maior diferença, com o sinal (positiva = a caixa adiantada)."""


def receber_saude(sessao: Session, caixa: AcessoDaCaixa, saude: Saude, *, agora: datetime) -> None:
    """Grava a saúde que a caixa mandou e apaga o histórico dela com mais de 7 dias.

    Raises:
        SaudeDeOutraCaixaError: se ``caixa_id`` ou ``site_id`` não forem os da caixa.
    """
    if saude.caixa_id != str(caixa.caixa_id) or saude.site_id != str(caixa.site_id):
        raise SaudeDeOutraCaixaError
    registro = sessao.get(CaixaBorda, caixa.caixa_id)
    assert registro is not None  # a caixa veio da chave
    diferenca = (saude.momento - agora).total_seconds()
    dados = saude.model_dump(mode="json")
    registro.ultimo_contato = agora
    registro.versao_programa = saude.versao_programa
    registro.versao_leitor = saude.versao_leitor
    registro.ultima_saude = dados
    registro.diferenca_do_relogio = diferenca
    sessao.add(
        SaudeCaixa(
            empresa_id=caixa.empresa_id,
            caixa_id=caixa.caixa_id,
            recebida_em=agora,
            momento=saude.momento,
            diferenca_do_relogio=diferenca,
            cpu=saude.cpu,
            temperatura=saude.temperatura,
            memoria=saude.memoria,
            disco=saude.disco,
            cameras_no_ar=sum(camera.no_ar for camera in saude.cameras),
            cameras=len(saude.cameras),
            passagens_na_fila=saude.fila.passagens,
            dados=dados,
        )
    )
    sessao.execute(
        delete(SaudeCaixa).where(
            SaudeCaixa.empresa_id == caixa.empresa_id,
            SaudeCaixa.caixa_id == caixa.caixa_id,
            SaudeCaixa.recebida_em < agora - GUARDA_DO_HISTORICO,
        )
    )
    sessao.flush()


def sem_contato(ultimo_contato: datetime | None, *, agora: datetime) -> bool:
    """Se a caixa está sem contato: mandou saúde, e a última chegou há 3 minutos ou mais."""
    return ultimo_contato is not None and agora - ultimo_contato >= LIMITE_SEM_CONTATO


def sem_conexao_desde(
    sessao: Session, acesso: Acesso, site_id: int, *, agora: datetime
) -> datetime | None:
    """Desde quando o site está sem conexão: o último contato da caixa que sumiu (a mais
    antiga, se forem várias); ``None`` se nenhuma caixa do site sumiu.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    return sessao.scalar(
        select(func.min(CaixaBorda.ultimo_contato)).where(
            CaixaBorda.empresa_id == acesso.empresa_id,
            CaixaBorda.site_id == site.id,
            CaixaBorda.revogada_em.is_(None),
            CaixaBorda.ultimo_contato <= agora - LIMITE_SEM_CONTATO,
        )
    )


def frota(sessao: Session, _administracao: AcessoAdmin, *, agora: datetime) -> list[CaixaNaFrota]:
    """As caixas não revogadas de todas as empresas, das mais novas para as mais antigas."""
    linhas = sessao.execute(
        _caixas_com_site().where(CaixaBorda.revogada_em.is_(None)).order_by(CaixaBorda.id.desc())
    ).all()
    nomes = nomes_das_cameras(sessao, {caixa.site_id for caixa, _, _ in linhas})
    return [_na_frota(caixa, site, empresa, nomes, agora=agora) for caixa, site, empresa in linhas]


def caixa_da_frota(
    sessao: Session, _administracao: AcessoAdmin, caixa_id: int, *, agora: datetime
) -> CaixaNaFrota:
    """Uma caixa da frota (também a revogada).

    Raises:
        NaoEncontradoError: se a caixa não existir.
    """
    linha = sessao.execute(_caixas_com_site().where(CaixaBorda.id == caixa_id)).one_or_none()
    if linha is None:
        raise NaoEncontradoError(f"caixa {caixa_id}")
    caixa, site, empresa = linha
    return _na_frota(caixa, site, empresa, nomes_das_cameras(sessao, {site.id}), agora=agora)


def historico_por_hora(
    sessao: Session, administracao: AcessoAdmin, caixa_id: int, *, agora: datetime
) -> list[HoraDaCaixa]:
    """Os últimos 7 dias da caixa, hora a hora, no fuso do site; a hora mais recente primeiro.

    Raises:
        NaoEncontradoError: se a caixa não existir.
    """
    fuso = caixa_da_frota(sessao, administracao, caixa_id, agora=agora).fuso
    hora = func.date_trunc("hour", func.timezone(fuso, SaudeCaixa.recebida_em)).label("hora")
    linhas = sessao.execute(
        select(
            hora,
            func.count(),
            func.max(SaudeCaixa.cpu),
            func.max(SaudeCaixa.temperatura),
            func.max(SaudeCaixa.disco),
            func.min(SaudeCaixa.cameras_no_ar),
            func.max(SaudeCaixa.cameras),
            func.max(SaudeCaixa.passagens_na_fila),
            func.min(SaudeCaixa.diferenca_do_relogio),
            func.max(SaudeCaixa.diferenca_do_relogio),
        )
        .where(
            SaudeCaixa.caixa_id == caixa_id,
            SaudeCaixa.recebida_em >= agora - GUARDA_DO_HISTORICO,
        )
        # Pelo nome: repetida, a expressão iria com outros parâmetros, e o banco não a reconhece.
        .group_by(text("hora"))
        .order_by(hora.desc())
    ).all()
    return [
        HoraDaCaixa(
            hora=inicio.replace(tzinfo=ZoneInfo(fuso)),
            contatos=contatos,
            cpu=cpu,
            temperatura=temperatura,
            disco=disco,
            cameras_no_ar=cameras_no_ar,
            cameras=cameras,
            passagens_na_fila=passagens,
            diferenca_do_relogio=atrasada if abs(atrasada) > abs(adiantada) else adiantada,
        )
        for (
            inicio,
            contatos,
            cpu,
            temperatura,
            disco,
            cameras_no_ar,
            cameras,
            passagens,
            atrasada,
            adiantada,
        ) in linhas
    ]


def _caixas_com_site() -> Select[CaixaBorda, Site, Empresa]:
    return (
        select(CaixaBorda, Site, Empresa)
        .join(Site, (Site.id == CaixaBorda.site_id) & (Site.empresa_id == CaixaBorda.empresa_id))
        .join(Empresa, Empresa.id == CaixaBorda.empresa_id)
    )


def nomes_das_cameras(sessao: Session, sites: set[int]) -> dict[tuple[int, str], str]:
    """O nome de cada câmera dos sites, por (site, id da câmera em texto, como vem na saúde)."""
    linhas = sessao.execute(
        select(Portaria.site_id, Camera.id, Camera.nome)
        .join(Faixa, (Faixa.id == Camera.faixa_id) & (Faixa.empresa_id == Camera.empresa_id))
        .join(
            Portaria,
            (Portaria.id == Faixa.portaria_id) & (Portaria.empresa_id == Faixa.empresa_id),
        )
        .where(Portaria.site_id.in_(sites))
    ).all()
    return {(site_id, str(camera_id)): nome for site_id, camera_id, nome in linhas}


def _na_frota(
    caixa: CaixaBorda,
    site: Site,
    empresa: Empresa,
    nomes: dict[tuple[int, str], str],
    *,
    agora: datetime,
) -> CaixaNaFrota:
    saude = Saude.model_validate(caixa.ultima_saude) if caixa.ultima_saude else None
    cameras = [
        CameraNaFrota(
            nome=nomes.get((site.id, camera.camera_id), f"câmera {camera.camera_id}"),
            no_ar=camera.no_ar,
            quadros_por_segundo=camera.quadros_por_segundo,
            ultimo_quadro=camera.ultimo_quadro,
        )
        for camera in (saude.cameras if saude else ())
    ]
    return CaixaNaFrota(
        caixa_id=caixa.id,
        empresa=empresa.nome,
        site=site.nome,
        fuso=site.fuso,
        ativada_em=caixa.ativada_em,
        ultimo_contato=caixa.ultimo_contato,
        sem_contato=sem_contato(caixa.ultimo_contato, agora=agora),
        versao_programa=caixa.versao_programa,
        versao_leitor=caixa.versao_leitor,
        diferenca_do_relogio=caixa.diferenca_do_relogio,
        saude=saude,
        cameras=cameras,
    )

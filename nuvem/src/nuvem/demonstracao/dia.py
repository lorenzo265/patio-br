"""O dia de demonstração (D-49): a manhã pronta e o resto ao vivo, com o líder automático.

- **Começar:** fecha o que ficou aberto de antes; grava os agendamentos do dia e a manhã até
  agora (quem saiu, quem está na doca e quem espera na fila há horas); e monta o roteiro das
  chegadas ao vivo, uma a cada 10 segundos, cada uma com o seu agendamento. A quarta vem com a
  placa lida errada: vira exceção para a pessoa resolver (a foto mostra a placa certa).
- **Avançar** (o worker, a cada volta): manda as chegadas da hora, pelo caminho da caixa
  (receber e casar), com a foto desenhada; e o líder automático faz uma coisa a cada 6 segundos:
  manda à saída quem foi liberado, começa quem foi chamado, chama o mais antigo da fila para a
  doca livre ou termina quem está na doca há mais tempo. Depois de 5 minutos, o dia acaba e o
  pátio fica como está.

O relógio é o de verdade: as esperas e os alertas são os de um dia real.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.passagem import Foto, Passagem, PlacaLida
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.servico import AgendamentoInventado, SiteDoAgendamento
from nuvem.armazenamento import Armazenamento
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, acesso_do_usuario
from nuvem.cadastro.modelos import Papel, Sentido, Site
from nuvem.demonstracao import historico
from nuvem.demonstracao.empresa import (
    CAMINHOES_POR_DIA,
    DOCAS,
    Lugar,
    celular_inventado,
    gravar_jornadas,
)
from nuvem.demonstracao.fotos import placa_desenhada
from nuvem.demonstracao.historico import COM_O_SISTEMA
from nuvem.demonstracao.modelos import DiaDeDemonstracao
from nuvem.frota import servico as frota
from nuvem.frota.servico import AcessoDaCaixa
from nuvem.patio import servico as patio
from nuvem.patio.servico import DocaOcupadaError, Quadro
from nuvem.portaria import servico as portaria
from nuvem.portaria import visitas
from nuvem.portaria.modelos import TipoDeEvento
from nuvem.portaria.visitas import SiteDaVisita, TransicaoInvalidaError

AO_VIVO = 24
"""Quantas chegadas o roteiro manda depois de começar."""
PRIMEIRA_CHEGADA = timedelta(seconds=8)
ENTRE_CHEGADAS = timedelta(seconds=10)
DURACAO = timedelta(minutes=5)
CHEGADA_ERRADA = 3
"""A quarta chegada vem com a placa lida errada (vira exceção)."""

LIDER_A_CADA = timedelta(seconds=6)
LIBERADO_HA = timedelta(seconds=15)
"""O líder manda à saída quem foi liberado há pelo menos isso."""
CHAMADO_HA = timedelta(seconds=10)
NA_FILA_HA = timedelta(seconds=12)
"""Quem acabou de chegar fica um pouco na fila, para aparecer na tela."""
NA_DOCA_HA = timedelta(seconds=30)


class DiaJaComecouError(Exception):
    """O site já tem um dia de demonstração rodando."""


class SiteSemCaixaError(Exception):
    """O site não tem caixa de borda: as passagens não têm em nome de quem chegar."""


@dataclass(frozen=True)
class Andamento:
    """O dia de um site, como a tela mostra."""

    comecou_em: datetime
    termina_em: datetime
    rodando: bool
    enviadas: int
    chegadas: int


# --- Começar ----------------------------------------------------------------------------------


def comecar(
    sessao: Session, acesso: Acesso, site_id: int, *, agora: datetime, semente: int | None = None
) -> DiaDeDemonstracao:
    """Começa o dia de demonstração de um site do usuário (sem ``commit``).

    Raises:
        NaoEncontradoError: se o site não for visível para este usuário.
        SiteSemCaixaError: se o site não tiver caixa de borda.
        DiaJaComecouError: se já houver um dia rodando no site.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    caixa = frota.caixa_do_site(sessao, empresa_id=acesso.empresa_id, site_id=site.id)
    if caixa is None:
        raise SiteSemCaixaError(site.nome)
    if _rodando(sessao, site) is not None:
        raise DiaJaComecouError(site.nome)
    lider_id = _primeiro(sessao, acesso, site, "patio")
    lugar = Lugar(
        empresa_id=acesso.empresa_id,
        site_id=site.id,
        docas=tuple(cadastro.listar_docas(sessao, acesso, site.id)),
        porteiro_id=_primeiro(sessao, acesso, site, "porteiro"),
        lider_id=lider_id,
    )
    _fechar_o_que_ficou_aberto(sessao, lugar, agora)
    fuso = ZoneInfo(site.fuso)
    gerador = random.Random(semente if semente is not None else int(agora.timestamp()))
    prefixo = f"DEMO-{agora.astimezone(fuso):%Y%m%d-%H%M%S}"
    placas: set[str] = set()
    caminhoes = max(round(CAMINHOES_POR_DIA * len(lugar.docas) / DOCAS), 1)
    jornadas = historico.jornadas_do_dia(
        agora.astimezone(fuso).date(), fuso=fuso, docas=max(len(lugar.docas), 1),
        caminhoes=caminhoes, ritmo=COM_O_SISTEMA, gerador=gerador, placas_usadas=placas,
    )  # fmt: skip
    gravar_jornadas(sessao, lugar, jornadas, agora=agora, prefixo=prefixo)
    dia = DiaDeDemonstracao(
        empresa_id=acesso.empresa_id,
        site_id=site.id,
        caixa_id=caixa.caixa_id,
        lider_id=lider_id,
        comecou_em=agora,
        termina_em=agora + DURACAO,
        chegadas=_roteiro(sessao, lugar, gerador, placas, prefixo, agora),
        enviadas=0,
        saidas=[],
        ultima_acao_em=None,
        situacao="rodando",
    )
    sessao.add(dia)
    sessao.flush()
    return dia


def andamento(sessao: Session, acesso: Acesso, site_id: int) -> Andamento | None:
    """O último dia de demonstração de um site do usuário, ou ``None`` se nunca começou.

    Raises:
        NaoEncontradoError: se o site não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    dia = sessao.scalars(
        select(DiaDeDemonstracao)
        .where(
            DiaDeDemonstracao.empresa_id == acesso.empresa_id, DiaDeDemonstracao.site_id == site.id
        )
        .order_by(DiaDeDemonstracao.id.desc())
        .limit(1)
    ).one_or_none()
    if dia is None:
        return None
    return Andamento(
        dia.comecou_em, dia.termina_em, dia.situacao == "rodando", dia.enviadas, len(dia.chegadas)
    )


def _rodando(sessao: Session, site: Site) -> DiaDeDemonstracao | None:
    return sessao.scalars(
        select(DiaDeDemonstracao).where(
            DiaDeDemonstracao.empresa_id == site.empresa_id,
            DiaDeDemonstracao.site_id == site.id,
            DiaDeDemonstracao.situacao == "rodando",
        )
    ).one_or_none()


def _primeiro(sessao: Session, acesso: Acesso, site: Site, papel: Papel) -> int:
    """A primeira pessoa do papel no site; sem ninguém, quem começou o dia."""
    pessoas = cadastro.pessoas_do_site(sessao, acesso, site.id, papel)
    return pessoas[0].id if pessoas else acesso.usuario_id


def _fechar_o_que_ficou_aberto(sessao: Session, lugar: Lugar, agora: datetime) -> None:
    """Quem ficou no pátio de um dia anterior sai agora (pelo sistema)."""
    site = SiteDaVisita(empresa_id=lugar.empresa_id, site_id=lugar.site_id)
    for visita in visitas.abertas_do_site(sessao, site):
        evento: TipoDeEvento = (
            "saiu" if visita.estado in ("NA_DOCA", "LIBERADA") else "saiu_sem_atendimento"
        )
        visitas.registrar(sessao, visita, evento, momento=agora, agora=agora)
    sessao.flush()


def _roteiro(
    sessao: Session,
    lugar: Lugar,
    gerador: random.Random,
    placas: set[str],
    prefixo: str,
    agora: datetime,
) -> list[dict[str, Any]]:
    """As chegadas ao vivo, cada uma com o seu agendamento (a janela em volta de agora)."""
    chegadas = []
    inventados = []
    for numero in range(AO_VIVO):
        placa = historico.placa_inventada(gerador, placas)
        lida = _lida_errada(placa) if numero == CHEGADA_ERRADA else placa
        em = agora + PRIMEIRA_CHEGADA + ENTRE_CHEGADAS * numero
        chegadas.append({"em": em.isoformat(), "placa": placa, "lida": lida})
        inventados.append(
            AgendamentoInventado(
                codigo_externo=f"{prefixo}-V{numero + 1:02d}",
                janela_inicio=agora - timedelta(minutes=30),
                janela_fim=agora + timedelta(minutes=90),
                tipo="descarga" if gerador.random() < 0.6 else "carga",
                placa_cavalo=placa,
                toneladas=historico.toneladas_inventadas(gerador),
                motorista_celular=celular_inventado(gerador),
            )
        )
    agendamentos.gravar_inventados(
        sessao, SiteDoAgendamento(lugar.empresa_id, lugar.site_id, None), inventados
    )
    return chegadas


def _lida_errada(placa: str) -> str:
    """O último número trocado por outro que não se confunde com ele (não é troca fácil)."""
    return placa[:-1] + str((int(placa[-1]) + 3) % 10)


# --- Avançar ----------------------------------------------------------------------------------


def avancar(sessao: Session, *, agora: datetime, armazenamento: Armazenamento) -> int:
    """Avança os dias de demonstração que estão rodando, de todos os sites (sem ``commit``).

    Returns:
        Quantas coisas aconteceram (chegadas mandadas e ações do líder).
    """
    feitas = 0
    dias = sessao.scalars(
        select(DiaDeDemonstracao)
        .where(DiaDeDemonstracao.situacao == "rodando")
        .order_by(DiaDeDemonstracao.id)
        .with_for_update(skip_locked=True)
    ).all()
    for dia in dias:
        feitas += _mandar_chegadas(sessao, dia, agora, armazenamento)
        na_vez = dia.ultima_acao_em is None or agora - dia.ultima_acao_em >= LIDER_A_CADA
        if na_vez and _lider(sessao, dia, agora, armazenamento):
            dia.ultima_acao_em = agora
            feitas += 1
        if agora >= dia.termina_em:
            dia.situacao = "terminado"
    sessao.flush()
    return feitas


def _mandar_chegadas(
    sessao: Session, dia: DiaDeDemonstracao, agora: datetime, armazenamento: Armazenamento
) -> int:
    mandadas = 0
    while dia.enviadas < len(dia.chegadas):
        chegada = dia.chegadas[dia.enviadas]
        if datetime.fromisoformat(chegada["em"]) > agora:
            break
        _passagem(sessao, dia, "entrada", chegada["placa"], chegada["lida"], agora, armazenamento)
        dia.enviadas += 1
        mandadas += 1
    return mandadas


def _lider(
    sessao: Session, dia: DiaDeDemonstracao, agora: datetime, armazenamento: Armazenamento
) -> bool:
    """Uma ação do líder automático, a primeira que couber; ``False`` se não havia nada."""
    acesso = acesso_do_usuario(sessao, dia.lider_id)
    quadro = patio.quadro(sessao, acesso, dia.site_id, agora=agora)
    try:
        return (
            _mandar_a_saida(sessao, dia, acesso, quadro, agora, armazenamento)
            or _comecar_o_chamado(sessao, acesso, quadro, agora)
            or _chamar_da_fila(sessao, acesso, quadro, agora)
            or _terminar_na_doca(sessao, acesso, quadro, agora)
        )
    except (TransicaoInvalidaError, DocaOcupadaError):
        # A pessoa da demonstração mexeu no mesmo caminhão (a ação recusa antes de gravar
        # qualquer coisa): o líder tenta de novo depois.
        return False


def _mandar_a_saida(
    sessao: Session,
    dia: DiaDeDemonstracao,
    acesso: Acesso,
    quadro: Quadro,
    agora: datetime,
    armazenamento: Armazenamento,
) -> bool:
    for caminhao in quadro.liberados:
        if caminhao.visita_id in dia.saidas:
            continue
        visita = visitas.obter_visita(sessao, acesso, caminhao.visita_id)
        if visita.liberada_em is not None and visita.liberada_em <= agora - LIBERADO_HA:
            placa = caminhao.placas[0]
            _passagem(sessao, dia, "saida", placa, placa, agora, armazenamento)
            dia.saidas = [*dia.saidas, caminhao.visita_id]
            return True
    return False


def _comecar_o_chamado(sessao: Session, acesso: Acesso, quadro: Quadro, agora: datetime) -> bool:
    chamados = [d.caminhao for d in quadro.docas if d.caminhao and d.caminhao.estado == "CHAMADA"]
    for caminhao in chamados:
        visita = visitas.obter_visita(sessao, acesso, caminhao.visita_id)
        if visita.chamada_em is not None and visita.chamada_em <= agora - CHAMADO_HA:
            patio.iniciar(sessao, acesso, caminhao.visita_id, agora=agora)
            return True
    return False


def _chamar_da_fila(sessao: Session, acesso: Acesso, quadro: Quadro, agora: datetime) -> bool:
    livres = [d for d in quadro.docas if d.caminhao is None]
    esperando = [c for c in quadro.fila if c.chegou_em <= agora - NA_FILA_HA]
    if not livres or not esperando:
        return False
    patio.chamar(sessao, acesso, esperando[0].visita_id, livres[0].doca_id, agora=agora)
    return True


def _terminar_na_doca(sessao: Session, acesso: Acesso, quadro: Quadro, agora: datetime) -> bool:
    na_doca = [d.caminhao for d in quadro.docas if d.caminhao and d.caminhao.estado == "NA_DOCA"]
    inicios = []
    for caminhao in na_doca:
        visita = visitas.obter_visita(sessao, acesso, caminhao.visita_id)
        if visita.na_doca_em is not None and visita.na_doca_em <= agora - NA_DOCA_HA:
            inicios.append((visita.na_doca_em, caminhao.visita_id))
    if not inicios:
        return False
    patio.finalizar(sessao, acesso, min(inicios)[1], agora=agora)
    return True


def _passagem(
    sessao: Session,
    dia: DiaDeDemonstracao,
    sentido: Sentido,
    placa: str,
    lida: str,
    agora: datetime,
    armazenamento: Armazenamento,
) -> None:
    """Manda uma passagem como a caixa do site mandaria, com a foto desenhada da placa certa."""
    estrutura = cadastro.estrutura_do_site(sessao, empresa_id=dia.empresa_id, site_id=dia.site_id)
    faixa = next(f for f in sorted(estrutura.values(), key=lambda f: f.id) if f.sentido == sentido)
    camera = str(min(faixa.cameras))
    passagem_id = uuid4()
    ref = f"demonstracao/{agora:%Y/%m/%d}/{passagem_id}.jpg"
    armazenamento.guardar(dia.caixa_id, ref, placa_desenhada(placa))
    passagem = Passagem(
        versao_contrato=1,
        id=passagem_id,
        caixa_id=str(dia.caixa_id),
        site_id=str(dia.site_id),
        faixa_id=str(faixa.id),
        sentido=sentido,
        inicio=agora - timedelta(seconds=6),
        fim=agora - timedelta(seconds=1),
        placas=(
            PlacaLida(
                placa=lida,
                papel="cavalo" if sentido == "entrada" else "desconhecido",
                confianca=0.96,
                camera_id=camera,
                quadros=5,
            ),
        ),
        fotos=(Foto(tipo="placa", camera_id=camera, ref=ref),),
        versao_leitor="demonstracao",
    )
    caixa = AcessoDaCaixa(caixa_id=dia.caixa_id, empresa_id=dia.empresa_id, site_id=dia.site_id)
    portaria.receber_passagem(sessao, caixa, passagem, agora=agora)

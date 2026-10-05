"""O porteiro resolve a exceção, corrige a placa e registra a chegada à mão (SDD 5.2 e D-46).

- **Resolver a exceção:** "é este" liga a visita a um agendamento perto da chegada e ainda sem
  visita; "sem agendamento" aceita; "recusar" leva a ``RECUSADA``. Cada um é um evento, com quem
  fez, e a exceção fica resolvida por essa pessoa.
- **Corrigir a placa numa exceção casa de novo:** a placa conferida na foto (D-42) ou digitada
  entra no lugar da que o leitor leu, e o casamento roda com ela. Casou com segurança, a visita vai
  para a fila; senão, a exceção fica com o motivo e os candidatos novos.
- **Chegada manual** (a câmera falhou): o porteiro digita as placas e escolhe o agendamento entre
  as sugestões, ou nenhum. Não abre exceção: quem escolhe é ele, na hora.

Quem chama é a tela da portaria (porteiro ou gestor). As funções gravam com ``flush``; o
``commit`` é de quem chama.
"""

from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from contratos.passagem import PlacaLida
from contratos.placa import PlacaInvalidaError, normalizar_placa
from nuvem.agendamento.modelos import Agendamento
from nuvem.banco import SQLSTATE_UNICIDADE, sqlstate
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso
from nuvem.erros import NaoEncontradoError
from nuvem.portaria import conferencia, visitas
from nuvem.portaria.casamento import (
    PESOS_INICIAIS,
    TOLERANCIA_PADRAO,
    CheckIn,
    Pesos,
    agendamentos_sem_visita,
    compor,
    decidir,
    esperado_de,
    pontuar,
)
from nuvem.portaria.modelos import ConferenciaPlaca, Excecao, Visita
from nuvem.portaria.visitas import PlacaNaVisita, SiteDaVisita


class ExcecaoJaResolvidaError(Exception):
    """A exceção já foi resolvida (por outra pessoa, ou pelo sistema quando o caminhão saiu)."""


class AgendamentoIndisponivelError(Exception):
    """O agendamento não serve: já tem visita, foi cancelado, é de outro site ou está longe."""


@dataclass(frozen=True)
class Opcao:
    """Um agendamento que o porteiro pode escolher, com os pontos para as placas da chegada."""

    agendamento_id: int
    codigo: str
    placa_cavalo: str
    placas_reboques: tuple[str, ...]
    janela_inicio: datetime
    janela_fim: datetime
    motorista: str
    pontos: int


# --- Resolver a exceção -----------------------------------------------------------------------


def obter_excecao(sessao: Session, acesso: Acesso, excecao_id: int) -> tuple[Excecao, Visita]:
    """Uma exceção (aberta ou não) de um site que o usuário vê, com a visita dela.

    Raises:
        NaoEncontradoError: se não existir, ou for de outra empresa ou de outro site.
    """
    return _da_excecao(sessao, acesso, excecao_id, travar=False)


def opcoes(
    sessao: Session,
    acesso: Acesso,
    excecao_id: int,
    *,
    pesos: Pesos = PESOS_INICIAIS,
    tolerancia: timedelta = TOLERANCIA_PADRAO,
) -> list[Opcao]:
    """Os agendamentos perto da chegada e sem visita, dos mais pontos para os menos.

    Raises:
        NaoEncontradoError: se a exceção não for visível para o usuário.
    """
    _, visita = _da_excecao(sessao, acesso, excecao_id, travar=False)
    lidas = _lidas(visitas.composicao_da_visita(visita))
    return _opcoes(sessao, _site(visita), lidas, _chegada(visita), pesos, tolerancia)


def ligar_ao_agendamento(
    sessao: Session,
    acesso: Acesso,
    excecao_id: int,
    agendamento_id: int,
    *,
    agora: datetime,
    tolerancia: timedelta = TOLERANCIA_PADRAO,
) -> Visita:
    """ "É este": liga a visita ao agendamento e a leva para a fila.

    Raises:
        NaoEncontradoError: se a exceção não for visível para o usuário.
        ExcecaoJaResolvidaError: se a exceção já foi resolvida.
        AgendamentoIndisponivelError: se o agendamento não está entre os disponíveis.
    """
    _, visita = _aberta(sessao, acesso, excecao_id)
    agendamento = _disponivel(sessao, _site(visita), _chegada(visita), agendamento_id, tolerancia)
    _ligar(
        sessao,
        visita,
        agendamento,
        visitas.composicao_da_visita(visita),
        usuario_id=acesso.usuario_id,
        agora=agora,
        resolucao=f"ligada ao agendamento {agendamento.codigo_externo}",
        dados={"pelo_porteiro": True},
    )
    return visita


def aceitar_sem_agendamento(
    sessao: Session, acesso: Acesso, excecao_id: int, *, agora: datetime
) -> Visita:
    """Aceita a chegada sem agendamento: a visita vai para a fila.

    Raises:
        NaoEncontradoError: se a exceção não for visível para o usuário.
        ExcecaoJaResolvidaError: se a exceção já foi resolvida.
    """
    _, visita = _aberta(sessao, acesso, excecao_id)
    return visitas.registrar(
        sessao,
        visita,
        "aceita_sem_agendamento",
        momento=agora,
        agora=agora,
        usuario_id=acesso.usuario_id,
        resolucao="aceita sem agendamento",
    )


def recusar(sessao: Session, acesso: Acesso, excecao_id: int, *, agora: datetime) -> Visita:
    """Recusa a entrada: a visita vai para ``RECUSADA``.

    Raises:
        NaoEncontradoError: se a exceção não for visível para o usuário.
        ExcecaoJaResolvidaError: se a exceção já foi resolvida.
    """
    _, visita = _aberta(sessao, acesso, excecao_id)
    return visitas.registrar(
        sessao,
        visita,
        "recusada",
        momento=agora,
        agora=agora,
        usuario_id=acesso.usuario_id,
        resolucao="recusada",
    )


# --- Corrigir a placa numa exceção ------------------------------------------------------------


def conferir_placa(
    sessao: Session,
    acesso: Acesso,
    passagem_id: UUID,
    foto: int,
    placa: str,
    *,
    agora: datetime,
    pesos: Pesos = PESOS_INICIAIS,
    tolerancia: timedelta = TOLERANCIA_PADRAO,
) -> ConferenciaPlaca:
    """Confere a placa de um recorte (D-42); numa exceção aberta, casa de novo com a placa certa.

    Raises:
        NaoEncontradoError: se a passagem não for visível ou a foto não for um recorte de placa.
        PlacaInvalidaError: se a placa não estiver no formato antigo nem no Mercosul.
    """
    feita = conferencia.conferir(sessao, acesso, passagem_id, foto, placa, agora=agora)
    excecao_id = sessao.scalar(
        select(Excecao.id).where(
            Excecao.empresa_id == acesso.empresa_id,
            Excecao.passagem_id == passagem_id,
            Excecao.situacao == "aberta",
        )
    )
    if excecao_id is None or not feita.corrigida:
        return feita
    try:
        excecao, visita = _aberta(sessao, acesso, excecao_id)
    except ExcecaoJaResolvidaError:
        return feita  # resolvida enquanto o porteiro conferia: fica só a conferência
    nova = _trocar_placa(visitas.composicao_da_visita(visita), feita.placa_lida, feita.placa)
    _casar_de_novo(sessao, excecao, visita, nova, acesso.usuario_id, agora, pesos, tolerancia)
    return feita


def digitar_cavalo(
    sessao: Session,
    acesso: Acesso,
    excecao_id: int,
    placa: str,
    *,
    agora: datetime,
    pesos: Pesos = PESOS_INICIAIS,
    tolerancia: timedelta = TOLERANCIA_PADRAO,
) -> Visita:
    """A placa do cavalo digitada (quando não há foto para conferir); casa de novo.

    Raises:
        PlacaInvalidaError: se a placa não estiver no formato antigo nem no Mercosul.
        NaoEncontradoError: se a exceção não for visível para o usuário.
        ExcecaoJaResolvidaError: se a exceção já foi resolvida.
    """
    certa = normalizar_placa(placa)
    excecao, visita = _aberta(sessao, acesso, excecao_id)
    reboques = [
        p for p in visitas.composicao_da_visita(visita) if p.papel == "reboque" and p.placa != certa
    ]
    nova = (PlacaNaVisita(placa=certa, papel="cavalo", como="digitada"), *reboques)
    _casar_de_novo(sessao, excecao, visita, nova, acesso.usuario_id, agora, pesos, tolerancia)
    return visita


# --- Chegada manual ---------------------------------------------------------------------------


def sugestoes(
    sessao: Session,
    acesso: Acesso,
    site_id: int,
    placas: Sequence[str],
    *,
    agora: datetime,
    pesos: Pesos = PESOS_INICIAIS,
    tolerancia: timedelta = TOLERANCIA_PADRAO,
) -> list[Opcao]:
    """Os agendamentos perto de agora e sem visita, pelos pontos das placas digitadas.

    Raises:
        NaoEncontradoError: se o site não for visível para o usuário.
        PlacaInvalidaError: se faltar a placa do cavalo ou uma placa estiver fora do formato.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    digitadas = _digitadas(placas)
    lugar = SiteDaVisita(empresa_id=acesso.empresa_id, site_id=site.id)
    return _opcoes(sessao, lugar, _lidas(digitadas), agora, pesos, tolerancia)


def registrar_chegada_manual(
    sessao: Session,
    acesso: Acesso,
    site_id: int,
    placas: Sequence[str],
    agendamento_id: int | None,
    *,
    agora: datetime,
    tolerancia: timedelta = TOLERANCIA_PADRAO,
) -> Visita:
    """Abre a visita de uma chegada que a câmera não registrou, com as placas digitadas.

    A primeira placa é a do cavalo; as outras, dos reboques. Com agendamento, a visita nasce em
    check-in; sem, aceita sem agendamento. As duas vão para a fila.

    Raises:
        NaoEncontradoError: se o site não for visível para o usuário.
        PlacaInvalidaError: se faltar a placa do cavalo ou uma placa estiver fora do formato.
        AgendamentoIndisponivelError: se o agendamento não está entre os disponíveis.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    digitadas = _digitadas(placas)
    lugar = SiteDaVisita(empresa_id=acesso.empresa_id, site_id=site.id)
    if agendamento_id is None:
        return visitas.abrir_visita(
            sessao,
            lugar,
            "aceita_sem_agendamento",
            momento=agora,
            agora=agora,
            composicao=digitadas,
            usuario_id=acesso.usuario_id,
            dados={"manual": True},
        )
    agendamento = _disponivel(sessao, lugar, agora, agendamento_id, tolerancia)
    composicao = _composicao_com(agendamento, digitadas)
    with _agendamento_sem_outra_visita(sessao):
        return visitas.abrir_visita(
            sessao,
            lugar,
            "check_in",
            momento=agora,
            agora=agora,
            agendamento_id=agendamento.id,
            composicao=composicao,
            usuario_id=acesso.usuario_id,
            dados={"manual": True},
        )


# --- Por dentro -------------------------------------------------------------------------------


def _da_excecao(
    sessao: Session, acesso: Acesso, excecao_id: int, *, travar: bool
) -> tuple[Excecao, Visita]:
    excecao = sessao.scalars(
        select(Excecao).where(Excecao.id == excecao_id, Excecao.empresa_id == acesso.empresa_id)
    ).one_or_none()
    nao_encontrada = NaoEncontradoError(f"exceção {excecao_id}")
    if excecao is None:
        raise nao_encontrada
    consulta = select(Visita).where(
        Visita.id == excecao.visita_id,
        Visita.empresa_id == acesso.empresa_id,
        Visita.site_id.in_(acesso.sites),
    )
    if travar:
        # Dois porteiros na mesma exceção: o segundo espera o primeiro e vê o que ele fez.
        consulta = consulta.with_for_update().execution_options(populate_existing=True)
    visita = sessao.scalars(consulta).one_or_none()
    if visita is None:
        raise nao_encontrada
    if travar:
        sessao.refresh(excecao)
    return excecao, visita


def _aberta(sessao: Session, acesso: Acesso, excecao_id: int) -> tuple[Excecao, Visita]:
    excecao, visita = _da_excecao(sessao, acesso, excecao_id, travar=True)
    if excecao.situacao != "aberta" or visita.estado != "EXCECAO":
        raise ExcecaoJaResolvidaError(f"a exceção {excecao_id} já foi resolvida")
    return excecao, visita


def _site(visita: Visita) -> SiteDaVisita:
    return SiteDaVisita(empresa_id=visita.empresa_id, site_id=visita.site_id)


def _chegada(visita: Visita) -> datetime:
    return visita.chegou_em or visita.criada_em


def _lidas(placas: Iterable[PlacaNaVisita]) -> list[PlacaLida]:
    """As placas da visita como leituras certas, para o casamento."""
    return [
        PlacaLida(placa=p.placa, papel=p.papel, confianca=1.0, camera_id="visita", quadros=1)
        for p in placas
    ]


def _digitadas(placas: Sequence[str]) -> tuple[PlacaNaVisita, ...]:
    """As placas digitadas pelo porteiro: a primeira é o cavalo; as outras, reboques."""
    normalizadas = list(dict.fromkeys(normalizar_placa(p) for p in placas if p.strip()))
    if not normalizadas:
        raise PlacaInvalidaError("")
    cavalo, *reboques = normalizadas
    return (
        PlacaNaVisita(placa=cavalo, papel="cavalo", como="digitada"),
        *(PlacaNaVisita(placa=r, papel="reboque", como="digitada") for r in reboques),
    )


def _trocar_placa(
    composicao: Sequence[PlacaNaVisita], lida: str | None, certa: str
) -> tuple[PlacaNaVisita, ...]:
    """A composição com a placa lida trocada pela certa; sem a lida, a certa entra no fim."""
    nova: list[PlacaNaVisita] = []
    trocou = False
    for placa in composicao:
        if lida is not None and placa.placa == lida and not trocou:
            nova.append(PlacaNaVisita(placa=certa, papel=placa.papel, como="digitada"))
            trocou = True
        elif placa.placa != certa:
            nova.append(placa)
    if not trocou:
        nova.append(PlacaNaVisita(placa=certa, papel="desconhecido", como="digitada"))
    return tuple(nova)


def _opcoes(
    sessao: Session,
    site: SiteDaVisita,
    lidas: Sequence[PlacaLida],
    momento: datetime,
    pesos: Pesos,
    tolerancia: timedelta,
) -> list[Opcao]:
    opcoes = []
    for agendamento in agendamentos_sem_visita(sessao, site, momento, tolerancia):
        pontuado = pontuar(
            lidas, esperado_de(agendamento), momento, pesos=pesos, tolerancia=tolerancia
        )
        opcoes.append(
            Opcao(
                agendamento_id=agendamento.id,
                codigo=agendamento.codigo_externo,
                placa_cavalo=agendamento.placa_cavalo,
                placas_reboques=tuple(agendamento.placas_reboques),
                janela_inicio=agendamento.janela_inicio,
                janela_fim=agendamento.janela_fim,
                motorista=agendamento.motorista_nome or "",
                pontos=pontuado.pontos if pontuado is not None else 0,
            )
        )
    return sorted(opcoes, key=lambda o: (-o.pontos, o.janela_inicio, o.agendamento_id))


def _disponivel(
    sessao: Session,
    site: SiteDaVisita,
    momento: datetime,
    agendamento_id: int,
    tolerancia: timedelta,
) -> Agendamento:
    for agendamento in agendamentos_sem_visita(sessao, site, momento, tolerancia):
        if agendamento.id == agendamento_id:
            return agendamento
    raise AgendamentoIndisponivelError(f"o agendamento {agendamento_id} não está disponível")


def _composicao_com(
    agendamento: Agendamento, placas: Sequence[PlacaNaVisita]
) -> tuple[PlacaNaVisita, ...]:
    """A composição do check-in (D-17), mantendo marcadas as placas que o porteiro digitou."""
    digitadas = {p.placa for p in placas if p.como == "digitada"}
    return tuple(
        p.model_copy(update={"como": "digitada"}) if p.placa in digitadas else p
        for p in compor(_lidas(placas), esperado_de(agendamento))
    )


def _ligar(
    sessao: Session,
    visita: Visita,
    agendamento: Agendamento,
    placas: Sequence[PlacaNaVisita],
    *,
    usuario_id: int,
    agora: datetime,
    resolucao: str,
    dados: dict[str, Any],
) -> None:
    visitas.mudar_composicao(visita, _composicao_com(agendamento, placas))
    with _agendamento_sem_outra_visita(sessao):
        visita.agendamento_id = agendamento.id
        sessao.flush()
    visitas.registrar(
        sessao,
        visita,
        "check_in",
        momento=agora,
        agora=agora,
        dados={"agendamento_id": agendamento.id, **dados},
        usuario_id=usuario_id,
        resolucao=resolucao,
    )


def _casar_de_novo(
    sessao: Session,
    excecao: Excecao,
    visita: Visita,
    placas: Sequence[PlacaNaVisita],
    usuario_id: int,
    agora: datetime,
    pesos: Pesos,
    tolerancia: timedelta,
) -> None:
    lidas = _lidas(placas)
    chegada = _chegada(visita)
    disponiveis = {a.id: a for a in agendamentos_sem_visita(sessao, _site(visita), chegada,
                                                           tolerancia)}  # fmt: skip
    pontuados = [
        pontuado
        for agendamento in disponiveis.values()
        if (pontuado := pontuar(lidas, esperado_de(agendamento), chegada, pesos=pesos,
                                tolerancia=tolerancia)) is not None
    ]  # fmt: skip
    decisao = decidir(lidas, pontuados, pesos)
    if isinstance(decisao, CheckIn):
        agendamento = disponiveis[decisao.escolhido.agendamento_id]
        _ligar(
            sessao,
            visita,
            agendamento,
            placas,
            usuario_id=usuario_id,
            agora=agora,
            resolucao=f"placa corrigida, ligada ao agendamento {agendamento.codigo_externo}",
            dados={"pontos": decisao.escolhido.pontos, "placa_corrigida": True},
        )
        return
    candidatos = [{"agendamento_id": c.agendamento_id, "pontos": c.pontos}
                  for c in decisao.candidatos]  # fmt: skip
    visitas.mudar_composicao(visita, placas)
    excecao.motivo = decisao.motivo
    excecao.candidatos = candidatos
    visitas.registrar(
        sessao,
        visita,
        "placa_corrigida",
        momento=agora,
        agora=agora,
        dados={
            "placas": [p.placa for p in placas],
            "motivo": decisao.motivo,
            "candidatos": candidatos,
        },
        usuario_id=usuario_id,
    )


@contextmanager
def _agendamento_sem_outra_visita(sessao: Session) -> Iterator[None]:
    """Se outro porteiro ligou o agendamento antes (a unicidade no banco), o erro certo.

    O bloco roda num ponto de volta (``begin_nested``): a falha não estraga a transação.
    """
    try:
        with sessao.begin_nested():
            yield
    except DBAPIError as erro:
        if sqlstate(erro) == SQLSTATE_UNICIDADE:
            raise AgendamentoIndisponivelError("o agendamento já tem visita") from None
        raise

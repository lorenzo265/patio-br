"""Casamento da chegada com o agendamento, e a saída (SDD 5.3, D-17, D-23, D-36 e D-37).

As regras puras (``pontuar``, ``decidir``, ``compor``, ``escolher_saida``) não usam o banco.
``processar_passagem`` junta tudo: lê a passagem, procura os candidatos, decide e grava a visita
(check-in ou exceção) ou fecha a visita na saída.

Os pesos são os iniciais da SDD 5.3 (``PESOS_INICIAIS``); os definitivos saem dos dados do site
parceiro (``[ABERTO-02]``, T37). A tolerância padrão é a de ``[ABERTO-09]`` (4h).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem, PlacaLida
from nuvem.agendamento import servico as agendamentos
from nuvem.erros import NaoEncontradoError
from nuvem.portaria import visitas
from nuvem.portaria.modelos import MotivoDaExcecao, PassagemRecebida, Visita
from nuvem.portaria.visitas import Candidato, PlacaNaVisita, SiteDaVisita


@dataclass(frozen=True)
class Pesos:
    """Os pontos de cada critério e o limite do check-in automático (SDD 5.3)."""

    cavalo_identico: int = 60
    cavalo_troca_facil: int = 40
    reboque_identico: int = 20
    reboques_no_maximo: int = 2
    dentro_da_janela: int = 20
    dentro_da_tolerancia: int = 10
    minimo_para_check_in: int = 80
    vantagem_minima: int = 20


PESOS_INICIAIS = Pesos()
"""Os pesos iniciais da SDD 5.3, até o ``[ABERTO-02]`` ser fechado com os dados do mês 2."""

TOLERANCIA_PADRAO = timedelta(hours=4)
"""A tolerância da janela, para antes e para depois (padrão do ``[ABERTO-09]``)."""

CANDIDATOS_NA_EXCECAO = 5
"""Quantos candidatos a exceção mostra ao porteiro, do maior para o menor."""

TROCAS_FACEIS = frozenset({frozenset("O0"), frozenset("I1"), frozenset("B8"), frozenset("S5")})
"""Os pares que o leitor confunde (SDD 5.3)."""

_LETRA_MERCOSUL = "ABCDEFGHIJ"
"""Na troca para a Mercosul, o 5º caractere, de número, vira letra: 0→A, 1→B ... 9→J (D-36)."""

# --- A mesma placa, e a troca fácil -----------------------------------------------------------


def forma_mercosul(placa: str) -> str:
    """A placa na forma Mercosul (a antiga ``ABC1234`` vira ``ABC1C34``; a Mercosul fica igual)."""
    if len(placa) == 7 and placa[4].isdigit():
        return placa[:4] + _LETRA_MERCOSUL[int(placa[4])] + placa[5:]
    return placa


def mesma_placa(a: str, b: str) -> bool:
    """Diz se as duas placas são a do mesmo veículo (a antiga e a Mercosul contam juntas)."""
    return forma_mercosul(a) == forma_mercosul(b)


def troca_facil(a: str, b: str) -> bool:
    """Diz se as placas diferem num caractere só, e esse é uma troca fácil (O/0, I/1, B/8, S/5).

    Vale também contra a forma Mercosul da outra (D-36).
    """
    return any(_uma_troca(x, y) for x in (a, forma_mercosul(a)) for y in (b, forma_mercosul(b)))


def _uma_troca(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    diferentes = [(x, y) for x, y in zip(a, b, strict=True) if x != y]
    return len(diferentes) == 1 and frozenset(diferentes[0]) in TROCAS_FACEIS


# --- Pontos e decisão -------------------------------------------------------------------------


@dataclass(frozen=True)
class Esperado:
    """O que o casamento usa de um agendamento."""

    agendamento_id: int
    placa_cavalo: str
    placas_reboques: tuple[str, ...]
    janela_inicio: datetime
    janela_fim: datetime


@dataclass(frozen=True)
class Pontuado:
    """Um candidato com os pontos (e quantos deles vieram das placas)."""

    agendamento_id: int
    pontos: int
    pontos_de_placa: int


@dataclass(frozen=True)
class CheckIn:
    """O candidato que casou, e o segundo colocado (se houve)."""

    escolhido: Pontuado
    segundo: Pontuado | None


@dataclass(frozen=True)
class ParaExcecao:
    """A chegada não casou com segurança: o porteiro resolve."""

    motivo: MotivoDaExcecao
    candidatos: tuple[Pontuado, ...]


def pontuar(
    lidas: Sequence[PlacaLida],
    esperado: Esperado,
    chegada: datetime,
    *,
    pesos: Pesos,
    tolerancia: timedelta,
) -> Pontuado | None:
    """Os pontos de um agendamento para uma chegada (SDD 5.3).

    Returns:
        O candidato pontuado, ou ``None`` se a chegada está fora da janela com a tolerância.
    """
    if esperado.janela_inicio <= chegada <= esperado.janela_fim:
        pontos_da_janela = pesos.dentro_da_janela
    elif esperado.janela_inicio - tolerancia <= chegada <= esperado.janela_fim + tolerancia:
        pontos_da_janela = pesos.dentro_da_tolerancia
    else:
        return None
    cavalo, usada = _cavalo(lidas, esperado, pesos)
    reboques = len(_reboques_vistos(lidas, esperado, usada))
    pontos_de_placa = cavalo + min(reboques, pesos.reboques_no_maximo) * pesos.reboque_identico
    return Pontuado(
        agendamento_id=esperado.agendamento_id,
        pontos=pontos_de_placa + pontos_da_janela,
        pontos_de_placa=pontos_de_placa,
    )


def decidir(
    lidas: Sequence[PlacaLida], pontuados: Sequence[Pontuado], pesos: Pesos
) -> CheckIn | ParaExcecao:
    """Check-in automático ou exceção, com o motivo e os candidatos (SDD 5.3)."""
    if not lidas:
        return ParaExcecao(motivo="sem_placa", candidatos=())
    com_placa = sorted(
        (p for p in pontuados if p.pontos_de_placa > 0),
        key=lambda p: (-p.pontos, p.agendamento_id),
    )
    if not com_placa:
        return ParaExcecao(motivo="sem_candidato", candidatos=())
    melhor = com_placa[0]
    segundo = com_placa[1] if len(com_placa) > 1 else None
    candidatos = tuple(com_placa[:CANDIDATOS_NA_EXCECAO])
    if melhor.pontos < pesos.minimo_para_check_in:
        return ParaExcecao(motivo="pontos_baixos", candidatos=candidatos)
    if segundo is not None and melhor.pontos - segundo.pontos < pesos.vantagem_minima:
        return ParaExcecao(motivo="candidatos_proximos", candidatos=candidatos)
    return CheckIn(escolhido=melhor, segundo=segundo)


def _cavalo(
    lidas: Sequence[PlacaLida], esperado: Esperado, pesos: Pesos
) -> tuple[int, PlacaLida | None]:
    """Os pontos do cavalo, e a placa lida que bateu com ele (para não contar de novo)."""
    podem_ser = [lida for lida in lidas if lida.papel != "reboque"]
    for lida in podem_ser:
        if mesma_placa(lida.placa, esperado.placa_cavalo):
            return pesos.cavalo_identico, lida
    for lida in podem_ser:
        if troca_facil(lida.placa, esperado.placa_cavalo):
            return pesos.cavalo_troca_facil, lida
    return 0, None


def _reboques_vistos(
    lidas: Sequence[PlacaLida], esperado: Esperado, usada: PlacaLida | None
) -> dict[str, PlacaLida]:
    """Cada reboque do agendamento que a câmera viu, com a placa lida."""
    vistos: dict[str, PlacaLida] = {}
    for reboque in dict.fromkeys(esperado.placas_reboques):
        if mesma_placa(reboque, esperado.placa_cavalo):
            continue  # a agenda repetiu o cavalo como reboque: conta uma vez só
        for lida in lidas:
            if lida is not usada and lida.papel != "cavalo" and mesma_placa(lida.placa, reboque):
                vistos[reboque] = lida
                break
    return vistos


# --- A composição da visita (D-17) ------------------------------------------------------------


def compor(lidas: Sequence[PlacaLida], esperado: Esperado) -> tuple[PlacaNaVisita, ...]:
    """A composição confirmada no check-in: cada placa, lida ou inferida (D-17).

    O cavalo vem com a placa que a câmera leu (se é a mesma placa) ou com a da agenda (se a
    leitura teve uma troca fácil). Reboque visto entra lido; não visto, inferido, a não ser que a
    câmera tenha visto um reboque fora da agenda (reboque trocado).
    """
    _, usada = _cavalo(lidas, esperado, PESOS_INICIAIS)
    placa_do_cavalo = (
        usada.placa
        if usada is not None and mesma_placa(usada.placa, esperado.placa_cavalo)
        else esperado.placa_cavalo
    )
    composicao = [PlacaNaVisita(placa=placa_do_cavalo, papel="cavalo", como="lida")]
    vistos = _reboques_vistos(lidas, esperado, usada)
    usadas = {id(lida) for lida in (usada, *vistos.values()) if lida is not None}
    a_mais = [lida for lida in lidas if id(lida) not in usadas and lida.papel != "cavalo"]
    for reboque in dict.fromkeys(esperado.placas_reboques):
        if reboque in vistos:
            composicao.append(
                PlacaNaVisita(placa=vistos[reboque].placa, papel="reboque", como="lida")
            )
        elif not a_mais and not mesma_placa(reboque, esperado.placa_cavalo):
            composicao.append(PlacaNaVisita(placa=reboque, papel="reboque", como="inferida"))
    for lida in a_mais:
        composicao.append(PlacaNaVisita(placa=lida.placa, papel="reboque", como="lida"))
    return _sem_repetir(composicao)


def _lidas_na_visita(lidas: Sequence[PlacaLida]) -> tuple[PlacaNaVisita, ...]:
    """As placas da passagem como vieram (a composição da exceção), sem repetir nem dois cavalos."""
    composicao: list[PlacaNaVisita] = []
    tem_cavalo = False
    for lida in lidas:
        papel = lida.papel
        if papel == "cavalo":
            papel = "desconhecido" if tem_cavalo else "cavalo"
            tem_cavalo = True
        composicao.append(PlacaNaVisita(placa=lida.placa, papel=papel, como="lida"))
    return _sem_repetir(composicao)


def _sem_repetir(composicao: Sequence[PlacaNaVisita]) -> tuple[PlacaNaVisita, ...]:
    vistas: set[str] = set()
    unicas = []
    for placa in composicao:
        if placa.placa not in vistas:
            vistas.add(placa.placa)
            unicas.append(placa)
    return tuple(unicas)


# --- A saída (D-37) ---------------------------------------------------------------------------

Aberta = tuple[int, Sequence[str], datetime]
"""Uma visita aberta: o id, as placas da composição e a hora da chegada."""


def escolher_saida(lidas: Sequence[PlacaLida], abertas: Sequence[Aberta]) -> int | None:
    """A visita que a saída fecha: a de chegada mais recente com uma placa lida (D-37)."""
    com_a_placa = [
        (chegada, visita_id)
        for visita_id, placas, chegada in abertas
        if any(mesma_placa(lida.placa, placa) for lida in lidas for placa in placas)
    ]
    return max(com_a_placa)[1] if com_a_placa else None


# --- No banco ---------------------------------------------------------------------------------

Resultado = Literal["check_in", "excecao", "saida", "saida_sem_visita", "repetida"]


@dataclass(frozen=True)
class Processada:
    """O que a passagem fez: o resultado e a visita (se houve)."""

    resultado: Resultado
    visita_id: int | None


def processar_passagem(
    sessao: Session,
    passagem_id: UUID,
    *,
    agora: datetime,
    pesos: Pesos = PESOS_INICIAIS,
    tolerancia: timedelta = TOLERANCIA_PADRAO,
) -> Processada:
    """Casa a passagem de entrada (check-in ou exceção), ou fecha a visita na saída.

    A mesma passagem de novo não muda nada (``repetida``). Roda fora do pedido da caixa (T33).

    Raises:
        NaoEncontradoError: se a passagem não existir.
    """
    recebida = sessao.get(PassagemRecebida, passagem_id)
    if recebida is None:
        raise NaoEncontradoError(f"passagem {passagem_id}")
    passagem = Passagem.model_validate(recebida.como_veio)
    site = SiteDaVisita(empresa_id=recebida.empresa_id, site_id=recebida.site_id)
    if recebida.sentido == "entrada":
        return _entrada(sessao, site, passagem, agora, pesos, tolerancia)
    return _saida(sessao, site, passagem, agora)


def _entrada(
    sessao: Session,
    site: SiteDaVisita,
    passagem: Passagem,
    agora: datetime,
    pesos: Pesos,
    tolerancia: timedelta,
) -> Processada:
    ja = sessao.scalar(
        select(Visita.id).where(
            Visita.empresa_id == site.empresa_id, Visita.passagem_entrada_id == passagem.id
        )
    )
    if ja is not None:
        return Processada("repetida", ja)
    esperados = _sem_visita(sessao, site, passagem.inicio, tolerancia)
    pontuados = [
        pontuado
        for esperado in esperados.values()
        if (pontuado := pontuar(passagem.placas, esperado, passagem.inicio, pesos=pesos,
                                tolerancia=tolerancia)) is not None
    ]  # fmt: skip
    decisao = decidir(passagem.placas, pontuados, pesos)
    if isinstance(decisao, CheckIn):
        esperado = esperados[decisao.escolhido.agendamento_id]
        visita = visitas.abrir_visita(
            sessao,
            site,
            "check_in",
            momento=passagem.inicio,
            agora=agora,
            agendamento_id=esperado.agendamento_id,
            composicao=compor(passagem.placas, esperado),
            passagem_id=passagem.id,
            dados=_dados_do_check_in(decisao),
        )
        return Processada("check_in", visita.id)
    excecao = visitas.abrir_excecao(
        sessao,
        site,
        passagem_id=passagem.id,
        momento=passagem.inicio,
        agora=agora,
        motivo=decisao.motivo,
        candidatos=[Candidato(c.agendamento_id, c.pontos) for c in decisao.candidatos],
        composicao=_lidas_na_visita(passagem.placas),
    )
    return Processada("excecao", excecao.visita_id)


def _sem_visita(
    sessao: Session, site: SiteDaVisita, chegada: datetime, tolerancia: timedelta
) -> dict[int, Esperado]:
    """Os candidatos: agendamentos ativos perto da chegada que ainda não têm visita (D-35)."""
    ativos = agendamentos.ativos_perto(
        sessao, empresa_id=site.empresa_id, site_id=site.site_id, momento=chegada, folga=tolerancia
    )
    com_visita = set(
        sessao.scalars(
            select(Visita.agendamento_id).where(
                Visita.empresa_id == site.empresa_id,
                Visita.agendamento_id.in_([a.id for a in ativos]),
            )
        )
    )
    return {
        a.id: Esperado(
            agendamento_id=a.id,
            placa_cavalo=a.placa_cavalo,
            placas_reboques=tuple(a.placas_reboques),
            janela_inicio=a.janela_inicio,
            janela_fim=a.janela_fim,
        )
        for a in ativos
        if a.id not in com_visita
    }


def _dados_do_check_in(decisao: CheckIn) -> dict[str, Any]:
    segundo = decisao.segundo
    return {
        "pontos": decisao.escolhido.pontos,
        "segundo": None
        if segundo is None
        else {"agendamento_id": segundo.agendamento_id, "pontos": segundo.pontos},
    }


def _saida(sessao: Session, site: SiteDaVisita, passagem: Passagem, agora: datetime) -> Processada:
    ja = sessao.scalar(
        select(Visita.id).where(
            Visita.empresa_id == site.empresa_id, Visita.passagem_saida_id == passagem.id
        )
    )
    if ja is not None:
        return Processada("repetida", ja)
    abertas = list(
        sessao.scalars(
            select(Visita)
            .where(
                Visita.empresa_id == site.empresa_id,
                Visita.site_id == site.site_id,
                Visita.estado.in_(visitas.ABERTOS),
            )
            .with_for_update()
        )
    )
    escolhida = escolher_saida(
        passagem.placas,
        [(v.id, [p["placa"] for p in v.composicao], v.chegou_em or v.criada_em) for v in abertas],
    )
    if escolhida is None:
        return Processada("saida_sem_visita", None)
    visita = next(v for v in abertas if v.id == escolhida)
    visitas.registrar(
        sessao,
        visita,
        "saiu_sem_atendimento",
        momento=passagem.inicio,
        agora=agora,
        passagem_id=passagem.id,
    )
    return Processada("saida", visita.id)

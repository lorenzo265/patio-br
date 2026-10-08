"""A prova da visita (SDD 5.5, D-69).

- **O resumo das fotos:** logo que a passagem chega (as fotos chegam antes dela), a tarefa
  "resumir as fotos" lê cada foto do armazenamento e guarda o SHA-256 (``FotoRecebida``).
- **Selar:** cada registro da visita (a passagem, cada foto, cada evento, cada conferência da
  placa e cada situação das mensagens ao motorista) vira um elo da cadeia (``prova.cadeia``),
  com o retrato do registro. O worker sela a cada minuto o que chegou nos últimos 7 dias; a
  página da prova sela a visita que abre. Os novos de uma vez entram na ordem em que chegaram.
- **Conferir:** refaz a cadeia, compara cada elo com o registro de origem, relê as fotos e
  confere as âncoras; aponta o primeiro elo quebrado.
- **A âncora do dia:** uma vez por dia (UTC), o último resumo de cada visita que mudou no dia vai
  para um arquivo travado (``prova.ancoras``), fora do banco.
"""

import hashlib
import json
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import String, and_, cast, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nuvem.armazenamento import Armazenamento
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.modelos import Usuario
from nuvem.frota.modelos import SaudeCaixa
from nuvem.mensagens.modelos import Mensagem
from nuvem.portaria.modelos import ConferenciaPlaca, Evento, PassagemRecebida, Visita
from nuvem.portaria.visitas import obter_visita
from nuvem.prova import cadeia
from nuvem.prova.ancoras import GuardaDasAncoras
from nuvem.prova.cadeia import Quebra
from nuvem.prova.modelos import AncoraDoDia, EloDaProva, FotoRecebida, TipoDeElo

JANELA_DE_SELAR = timedelta(days=7)
"""O worker procura, a cada minuto, só o que chegou nesta janela (a página sela o resto)."""
MARGEM_DA_ANCORA = timedelta(minutes=10)
"""A âncora de um dia só é gravada 10 minutos depois de ele acabar: quem selava, já gravou."""
TRAVA_DA_PROVA = 7304
"""A trava do PostgreSQL de cada visita (com o id dela): dois selando a mesma não se cruzam."""
TRAVA_DAS_ANCORAS = 7305
VISITAS_NA_BUSCA = 50

ORDEM_DOS_TIPOS: dict[TipoDeElo, int] = {
    "passagem": 0,
    "foto": 1,
    "evento": 2,
    "conferencia": 3,
    "mensagem": 4,
}
"""Os que chegaram na mesma hora entram nesta ordem."""
SITUACOES_DA_MENSAGEM = (
    ("criada", "criada_em"),
    ("enviada", "enviada_em"),
    ("entregue", "entregue_em"),
    ("lida", "lida_em"),
    ("falhou", "falhou_em"),
)
"""Cada horário preenchido da mensagem é um elo (ela anda; o horário de cada situação, não)."""

SituacaoDaAncora = Literal["confere", "sem_ancora", "nao_confere"]


@dataclass(frozen=True)
class Registro:
    """Um registro da visita, com o retrato que vai no elo."""

    tipo: TipoDeElo
    referencia: str
    conteudo: dict[str, Any]
    momento: datetime
    """Quando chegou: decide a ordem dos novos."""

    @property
    def chave(self) -> tuple[str, str]:
        """O que identifica o registro na cadeia da visita."""
        return (self.tipo, self.referencia)


@dataclass(frozen=True)
class AncoraConferida:
    """O que a conferência achou na âncora de um dia."""

    dia: date
    situacao: SituacaoDaAncora
    motivo: str = ""
    travada: bool = False


@dataclass(frozen=True)
class Conferencia:
    """O resultado da conferência da prova de uma visita."""

    elos: int
    quebra: Quebra | None
    ancoras: list[AncoraConferida]

    @property
    def integra(self) -> bool:
        """Nenhum elo quebrado e nenhuma âncora que não confere."""
        return self.quebra is None and all(a.situacao != "nao_confere" for a in self.ancoras)


# --- O resumo das fotos ---------------------------------------------------------------------


def resumir_fotos(
    sessao: Session, armazenamento: Armazenamento, passagem_id: UUID, *, agora: datetime
) -> int:
    """Guarda o SHA-256 de cada foto da passagem que está no armazenamento; devolve quantas novas.

    A foto que não está lá não chegou (a caixa desiste da foto recusada e manda a passagem).
    De novo, não muda nada.
    """
    recebida = sessao.get(PassagemRecebida, passagem_id)
    if recebida is None:
        return 0
    novas = 0
    for indice, foto in enumerate(recebida.como_veio["fotos"]):
        conteudo = armazenamento.ler(recebida.caixa_id, foto["ref"])
        if conteudo is None:
            continue
        resultado = sessao.execute(
            insert(FotoRecebida)
            .values(
                empresa_id=recebida.empresa_id,
                passagem_id=recebida.id,
                indice=indice,
                ref=foto["ref"],
                resumo=hashlib.sha256(conteudo).hexdigest(),
                tamanho=len(conteudo),
                resumida_em=agora,
            )
            .on_conflict_do_nothing(index_elements=["passagem_id", "indice"])
        )
        novas += getattr(resultado, "rowcount", 0) or 0
    return novas


# --- Selar ----------------------------------------------------------------------------------


def selar(sessao: Session, *, agora: datetime) -> int:
    """Sela as visitas com registro novo nos últimos 7 dias (com ``flush``); devolve os elos."""
    desde = agora - JANELA_DE_SELAR
    return sum(
        _selar(sessao, visita, agora)
        for visita in sessao.scalars(
            select(Visita).where(Visita.id.in_(_visitas_com_novidade(desde))).order_by(Visita.id)
        )
    )


def selar_a_visita(sessao: Session, acesso: Acesso, visita_id: int, *, agora: datetime) -> int:
    """Sela o que falta de uma visita que o usuário vê; devolve quantos elos novos.

    Raises:
        NaoEncontradoError: se a visita não for visível para o usuário.
    """
    return _selar(sessao, obter_visita(sessao, acesso, visita_id), agora)


def elos_da_visita(sessao: Session, acesso: Acesso, visita_id: int) -> list[EloDaProva]:
    """Os elos de uma visita que o usuário vê, na ordem.

    Raises:
        NaoEncontradoError: se a visita não for visível para o usuário.
    """
    visita = obter_visita(sessao, acesso, visita_id)
    return _elos(sessao, visita)


def visitas_para_a_prova(
    sessao: Session, acesso: Acesso, *, placa: str | None = None
) -> list[Visita]:
    """As últimas visitas dos sites que o usuário vê, das mais novas; com ``placa``, só as dela.

    ``placa`` já vem no formato canônico (``contratos.placa``).
    """
    consulta = select(Visita).where(
        Visita.empresa_id == acesso.empresa_id, Visita.site_id.in_(acesso.sites)
    )
    if placa:
        consulta = consulta.where(Visita.composicao.contains([{"placa": placa}]))
    return list(
        sessao.scalars(
            consulta.order_by(
                func.coalesce(Visita.chegou_em, Visita.criada_em).desc(), Visita.id.desc()
            ).limit(VISITAS_NA_BUSCA)
        )
    )


def nomes_das_pessoas(sessao: Session, acesso: Acesso, ids: Iterable[int]) -> dict[int, str]:
    """Os nomes das pessoas da empresa do usuário, por id (quem registrou cada coisa)."""
    linhas = sessao.execute(
        select(Usuario.id, Usuario.nome).where(
            Usuario.empresa_id == acesso.empresa_id, Usuario.id.in_(set(ids))
        )
    )
    return {usuario_id: nome for usuario_id, nome in linhas}


def _elos(sessao: Session, visita: Visita) -> list[EloDaProva]:
    return list(
        sessao.scalars(
            select(EloDaProva)
            .where(EloDaProva.empresa_id == visita.empresa_id, EloDaProva.visita_id == visita.id)
            .order_by(EloDaProva.ordem)
        )
    )


def _selar(sessao: Session, visita: Visita, agora: datetime) -> int:
    sessao.execute(select(func.pg_advisory_xact_lock(TRAVA_DA_PROVA, visita.id)))
    elos = _elos(sessao, visita)
    seladas = {(elo.tipo, elo.referencia) for elo in elos}
    novos = sorted(
        (r for r in _registros(sessao, visita) if r.chave not in seladas),
        key=lambda r: (r.momento, ORDEM_DOS_TIPOS[r.tipo], r.referencia),
    )
    ordem, anterior = (elos[-1].ordem, elos[-1].resumo) if elos else (0, cadeia.INICIO)
    for registro in novos:
        conteudo = registro.conteudo
        if registro.tipo == "passagem":
            conteudo = {**conteudo, "saude": _saude_na_hora(sessao, conteudo["passagem"])}
        ordem += 1
        resumo = cadeia.resumo_do_elo(anterior, registro.tipo, registro.referencia, conteudo)
        sessao.add(
            EloDaProva(
                empresa_id=visita.empresa_id,
                visita_id=visita.id,
                ordem=ordem,
                tipo=registro.tipo,
                referencia=registro.referencia,
                conteudo=conteudo,
                anterior=anterior,
                resumo=resumo,
                selado_em=agora,
            )
        )
        anterior = resumo
    sessao.flush()
    return len(novos)


def _visitas_com_novidade(desde: datetime) -> Any:
    """As visitas com algum registro chegado desde ``desde`` que ainda não tem elo."""

    def sem_elo(visita_id: Any, tipo: TipoDeElo, referencia: Any) -> Any:
        return ~exists().where(
            EloDaProva.visita_id == visita_id,
            EloDaProva.tipo == tipo,
            EloDaProva.referencia == referencia,
        )

    # A passagem chega junto com o evento que ela gera: quem acha o evento, acha a passagem.
    eventos = select(Evento.visita_id).where(
        Evento.registrado_em >= desde, sem_elo(Evento.visita_id, "evento", _texto(Evento.id))
    )
    fotos = (
        select(Evento.visita_id)
        .join(
            FotoRecebida,
            and_(
                FotoRecebida.passagem_id == Evento.passagem_id,
                FotoRecebida.empresa_id == Evento.empresa_id,
            ),
        )
        .where(
            FotoRecebida.resumida_em >= desde,
            sem_elo(
                Evento.visita_id,
                "foto",
                _texto(FotoRecebida.passagem_id) + ":" + _texto(FotoRecebida.indice),
            ),
        )
    )
    conferencias = (
        select(Evento.visita_id)
        .join(
            ConferenciaPlaca,
            and_(
                ConferenciaPlaca.passagem_id == Evento.passagem_id,
                ConferenciaPlaca.empresa_id == Evento.empresa_id,
            ),
        )
        .where(
            ConferenciaPlaca.momento >= desde,
            sem_elo(Evento.visita_id, "conferencia", _texto(ConferenciaPlaca.id)),
        )
    )
    mensagens = (
        select(Visita.id)
        .join(
            Mensagem,
            and_(
                Mensagem.agendamento_id == Visita.agendamento_id,
                Mensagem.empresa_id == Visita.empresa_id,
            ),
        )
        .where(
            or_(
                *(
                    and_(
                        getattr(Mensagem, coluna) >= desde,
                        sem_elo(Visita.id, "mensagem", _texto(Mensagem.id) + f":{situacao}"),
                    )
                    for situacao, coluna in SITUACOES_DA_MENSAGEM
                )
            )
        )
    )
    return eventos.union(fotos, conferencias, mensagens)


def _texto(coluna: Any) -> Any:
    return cast(coluna, String)


# --- Os retratos ----------------------------------------------------------------------------


def _registros(sessao: Session, visita: Visita) -> list[Registro]:
    """Todos os registros da visita, com o retrato de cada um (o mesmo, sempre que refeito)."""
    eventos = list(
        sessao.scalars(
            select(Evento)
            .where(Evento.empresa_id == visita.empresa_id, Evento.visita_id == visita.id)
            .order_by(Evento.id)
        )
    )
    ids = {e.passagem_id for e in eventos if e.passagem_id is not None}
    registros = [_do_evento(evento) for evento in eventos]
    da_empresa = PassagemRecebida.empresa_id == visita.empresa_id
    for passagem in sessao.scalars(
        select(PassagemRecebida).where(da_empresa, PassagemRecebida.id.in_(ids))
    ):
        registros.append(_da_passagem(passagem))
    for foto in sessao.scalars(
        select(FotoRecebida).where(
            FotoRecebida.empresa_id == visita.empresa_id, FotoRecebida.passagem_id.in_(ids)
        )
    ):
        registros.append(_da_foto(foto))
    for conferida in sessao.scalars(
        select(ConferenciaPlaca).where(
            ConferenciaPlaca.empresa_id == visita.empresa_id, ConferenciaPlaca.passagem_id.in_(ids)
        )
    ):
        registros.append(_da_conferencia(conferida))
    if visita.agendamento_id is not None:
        for mensagem in sessao.scalars(
            select(Mensagem).where(
                Mensagem.empresa_id == visita.empresa_id,
                Mensagem.agendamento_id == visita.agendamento_id,
            )
        ):
            registros.extend(_da_mensagem(mensagem))
    return registros


def _hora(momento: datetime | None) -> str | None:
    return momento.astimezone(UTC).isoformat() if momento is not None else None


def _da_passagem(passagem: PassagemRecebida) -> Registro:
    retrato = {
        "id": str(passagem.id),
        "caixa_id": passagem.caixa_id,
        "faixa_id": passagem.faixa_id,
        "recebida_em": _hora(passagem.recebida_em),
        "como_veio": passagem.como_veio,
    }
    return Registro("passagem", str(passagem.id), {"passagem": retrato}, passagem.recebida_em)


def _saude_na_hora(sessao: Session, passagem: dict[str, Any]) -> dict[str, Any] | None:
    """A última saúde da caixa que chegou até a passagem chegar (a saúde só fica 7 dias)."""
    saude = sessao.scalars(
        select(SaudeCaixa)
        .where(
            SaudeCaixa.caixa_id == passagem["caixa_id"],
            SaudeCaixa.recebida_em <= datetime.fromisoformat(passagem["recebida_em"]),
        )
        .order_by(SaudeCaixa.recebida_em.desc(), SaudeCaixa.id.desc())
        .limit(1)
    ).first()
    if saude is None:
        return None
    return {
        "recebida_em": _hora(saude.recebida_em),
        "momento_da_caixa": _hora(saude.momento),
        "diferenca_do_relogio": saude.diferenca_do_relogio,
        "cameras_no_ar": saude.cameras_no_ar,
        "cameras": saude.cameras,
    }


def _da_foto(foto: FotoRecebida) -> Registro:
    retrato = {
        "passagem": str(foto.passagem_id),
        "indice": foto.indice,
        "ref": foto.ref,
        "resumo": foto.resumo,
        "tamanho": foto.tamanho,
        "resumida_em": _hora(foto.resumida_em),
    }
    return Registro("foto", f"{foto.passagem_id}:{foto.indice}", retrato, foto.resumida_em)


def _do_evento(evento: Evento) -> Registro:
    retrato = {
        "id": evento.id,
        "tipo": evento.tipo,
        "estado": evento.estado,
        "momento": _hora(evento.momento),
        "registrado_em": _hora(evento.registrado_em),
        "usuario_id": evento.usuario_id,
        "passagem_id": str(evento.passagem_id) if evento.passagem_id else None,
        "dados": evento.dados,
    }
    return Registro("evento", str(evento.id), retrato, evento.registrado_em)


def _da_conferencia(conferida: ConferenciaPlaca) -> Registro:
    retrato = {
        "id": conferida.id,
        "passagem": str(conferida.passagem_id),
        "foto": conferida.foto,
        "placa_lida": conferida.placa_lida,
        "placa": conferida.placa,
        "usuario_id": conferida.usuario_id,
        "momento": _hora(conferida.momento),
    }
    return Registro("conferencia", str(conferida.id), retrato, conferida.momento)


def _da_mensagem(mensagem: Mensagem) -> Iterator[Registro]:
    for situacao, coluna in SITUACOES_DA_MENSAGEM:
        momento: datetime | None = getattr(mensagem, coluna)
        if momento is None:
            continue
        retrato: dict[str, Any] = {
            "mensagem": mensagem.id,
            "modelo": mensagem.modelo,
            "canal": mensagem.canal,
            "para": mensagem.para,
            "situacao": situacao,
            "momento": _hora(momento),
        }
        if situacao == "criada":
            retrato["texto"] = mensagem.texto
        yield Registro("mensagem", f"{mensagem.id}:{situacao}", retrato, momento)


# --- Conferir -------------------------------------------------------------------------------


def conferir(
    sessao: Session,
    acesso: Acesso,
    visita_id: int,
    armazenamento: Armazenamento,
    guarda: GuardaDasAncoras,
) -> Conferencia:
    """Confere a prova de uma visita que o usuário vê: a cadeia, a origem, as fotos e as âncoras.

    Raises:
        NaoEncontradoError: se a visita não for visível para o usuário.
    """
    visita = obter_visita(sessao, acesso, visita_id)
    elos = _elos(sessao, visita)
    lidos = [
        cadeia.Elo(e.ordem, e.tipo, e.referencia, e.conteudo, e.anterior, e.resumo) for e in elos
    ]
    quebras = [cadeia.primeira_quebra(lidos), *_conferir_a_origem(sessao, visita, elos)]
    quebras.append(_conferir_as_fotos(armazenamento, visita, elos))
    achadas = [quebra for quebra in quebras if quebra is not None]
    primeira = min(achadas, key=lambda q: q.ordem) if achadas else None
    return Conferencia(
        len(elos), primeira, list(_conferir_as_ancoras(sessao, guarda, visita, elos))
    )


def _conferir_a_origem(
    sessao: Session, visita: Visita, elos: Sequence[EloDaProva]
) -> Iterator[Quebra]:
    registros = {r.chave: r for r in _registros(sessao, visita)}
    for elo in elos:
        registro = registros.get((elo.tipo, elo.referencia))
        if registro is None:
            yield Quebra(elo.ordem, "o registro sumiu")
            return
        selado = elo.conteudo
        if elo.tipo == "passagem":
            # A saúde da caixa não fica guardada: só a passagem se compara.
            selado = {"passagem": elo.conteudo.get("passagem")}
        if registro.conteudo != selado:
            yield Quebra(elo.ordem, "o registro mudou depois de selado")
            return


def _conferir_as_fotos(
    armazenamento: Armazenamento, visita: Visita, elos: Sequence[EloDaProva]
) -> Quebra | None:
    caixas = {
        elo.referencia: elo.conteudo["passagem"]["caixa_id"]
        for elo in elos
        if elo.tipo == "passagem"
    }
    for elo in elos:
        if elo.tipo != "foto":
            continue
        caixa_id = caixas.get(elo.conteudo["passagem"])
        conteudo = armazenamento.ler(caixa_id, elo.conteudo["ref"]) if caixa_id else None
        if conteudo is None:
            return Quebra(elo.ordem, "a foto sumiu")
        if hashlib.sha256(conteudo).hexdigest() != elo.conteudo["resumo"]:
            return Quebra(elo.ordem, "a foto mudou")
    return None


def _conferir_as_ancoras(
    sessao: Session, guarda: GuardaDasAncoras, visita: Visita, elos: Sequence[EloDaProva]
) -> Iterator[AncoraConferida]:
    ultimo_do_dia: dict[date, EloDaProva] = {}
    for elo in elos:
        ultimo_do_dia[elo.selado_em.astimezone(UTC).date()] = elo
    ancoras = {
        ancora.dia: ancora
        for ancora in sessao.scalars(
            select(AncoraDoDia).where(AncoraDoDia.dia.in_(list(ultimo_do_dia)))
        )
    }
    for dia, elo in sorted(ultimo_do_dia.items()):
        ancora = ancoras.get(dia)
        if ancora is None:
            yield AncoraConferida(dia, "sem_ancora")
            continue
        yield _conferir_a_ancora(guarda, ancora, visita, elo)


def _conferir_a_ancora(
    guarda: GuardaDasAncoras, ancora: AncoraDoDia, visita: Visita, elo: EloDaProva
) -> AncoraConferida:
    def nao(motivo: str) -> AncoraConferida:
        return AncoraConferida(ancora.dia, "nao_confere", motivo, ancora.travada)

    conteudo = guarda.ler(ancora.arquivo)
    if conteudo is None:
        return nao("o arquivo da âncora sumiu")
    if hashlib.sha256(conteudo).hexdigest() != ancora.resumo:
        return nao("o arquivo da âncora mudou")
    try:
        entradas = {e["visita"]: e for e in json.loads(conteudo)["visitas"]}
    except (ValueError, KeyError, TypeError):
        return nao("o arquivo da âncora não se lê")
    entrada = entradas.get(visita.id)
    if entrada is None:
        return nao("a âncora não tem esta visita")
    if (entrada.get("ordem"), entrada.get("resumo")) != (elo.ordem, elo.resumo):
        return nao("a âncora não bate com a cadeia")
    return AncoraConferida(ancora.dia, "confere", travada=ancora.travada)


# --- A âncora do dia ------------------------------------------------------------------------


def gravar_ancoras(sessao: Session, guarda: GuardaDasAncoras, *, agora: datetime) -> int:
    """Grava a âncora de cada dia (UTC) já terminado que tem elos e ainda não tem âncora.

    Um de cada vez (trava do PostgreSQL). Devolve quantas gravou.
    """
    if not sessao.scalar(select(func.pg_try_advisory_xact_lock(TRAVA_DAS_ANCORAS))):
        return 0
    hoje = (agora - MARGEM_DA_ANCORA).astimezone(UTC).date()
    dia_do_elo = func.date(func.timezone("UTC", EloDaProva.selado_em))
    dias = sorted(
        sessao.scalars(
            select(dia_do_elo)
            .where(
                EloDaProva.selado_em < datetime.combine(hoje, time(), UTC),
                ~exists().where(AncoraDoDia.dia == dia_do_elo),
            )
            .distinct()
        )
    )
    for dia in dias:
        _gravar_a_ancora(sessao, guarda, dia, agora)
    return len(dias)


def _gravar_a_ancora(sessao: Session, guarda: GuardaDasAncoras, dia: date, agora: datetime) -> None:
    inicio = datetime.combine(dia, time(), UTC)
    do_dia = and_(EloDaProva.selado_em >= inicio, EloDaProva.selado_em < inicio + timedelta(days=1))
    ultimas = (
        select(EloDaProva.visita_id, func.max(EloDaProva.ordem).label("ordem"))
        .where(do_dia)
        .group_by(EloDaProva.visita_id)
        .subquery()
    )
    linhas = sessao.execute(
        select(EloDaProva.visita_id, EloDaProva.ordem, EloDaProva.resumo)
        .join(
            ultimas,
            and_(EloDaProva.visita_id == ultimas.c.visita_id, EloDaProva.ordem == ultimas.c.ordem),
        )
        .order_by(EloDaProva.visita_id)
    ).all()
    conteudo = _arquivo_da_ancora(dia, ((v, o, r) for v, o, r in linhas))
    gravada = guarda.gravar(f"{dia.isoformat()}.json", conteudo, agora=agora)
    sessao.add(
        AncoraDoDia(
            dia=dia,
            arquivo=gravada.arquivo,
            resumo=hashlib.sha256(conteudo).hexdigest(),
            visitas=len(linhas),
            travada=gravada.travada,
            gravada_em=agora,
        )
    )
    sessao.flush()


def _arquivo_da_ancora(dia: date, linhas: Iterable[tuple[int, int, str]]) -> bytes:
    """O arquivo da âncora: só os números das visitas e os resumos (nenhum dado pessoal)."""
    visitas = [{"visita": v, "ordem": o, "resumo": r} for v, o, r in linhas]
    return cadeia.json_canonico(
        {"dia": dia.isoformat(), "regra": cadeia.REGRA, "visitas": visitas}
    ).encode()

"""O pedido do titular (SDD 8.3, D-70): tudo o que existe de uma placa ou de um celular.

O cliente é o controlador e responde ao titular; nós (a administração) levantamos, numa empresa,
o que existe: pela placa, as visitas, as passagens (com as fotos guardadas e apagadas), as
conferências, os agendamentos e as mensagens deles; pelo celular, os agendamentos, as visitas
deles, as mensagens, as autorizações do WhatsApp e as mensagens recebidas. Uma coisa de cada vez:
a placa ou o celular.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from contratos.placa import PlacaInvalidaError, normalizar_placa
from nuvem.agendamento.formato import CelularInvalidoError, normalizar_celular
from nuvem.agendamento.modelos import Agendamento
from nuvem.cadastro.acesso import AcessoAdmin
from nuvem.cadastro.modelos import Empresa, Site
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.guarda.modelos import FotoApagada
from nuvem.mensagens.modelos import AutorizacaoWhatsApp, Mensagem, MensagemRecebida
from nuvem.portaria.modelos import ConferenciaPlaca, PassagemRecebida, Visita
from nuvem.prova.modelos import FotoRecebida


@dataclass(frozen=True)
class Levantamento:
    """O que existe de uma placa ou de um celular numa empresa."""

    empresa: str
    procurado: str
    visitas: list[dict[str, Any]] = field(default_factory=list)
    passagens: list[dict[str, Any]] = field(default_factory=list)
    conferencias: list[dict[str, Any]] = field(default_factory=list)
    agendamentos: list[dict[str, Any]] = field(default_factory=list)
    mensagens: list[dict[str, Any]] = field(default_factory=list)
    autorizacoes: list[dict[str, Any]] = field(default_factory=list)
    recebidas: list[dict[str, Any]] = field(default_factory=list)

    def como_dicionario(self) -> dict[str, Any]:
        """O levantamento para o arquivo (JSON)."""
        return asdict(self)


def levantar(
    sessao: Session,
    _administracao: AcessoAdmin,
    *,
    empresa_id: int,
    placa: str = "",
    celular: str = "",
) -> Levantamento:
    """Levanta, numa empresa, tudo o que existe de uma placa ou de um celular.

    Raises:
        DadoInvalidoError: sem placa nem celular, com os dois, ou com um deles fora do formato.
        NaoEncontradoError: se a empresa não existe.
    """
    empresa = sessao.get(Empresa, empresa_id)
    if empresa is None:
        raise NaoEncontradoError(f"empresa {empresa_id}")
    if bool(placa.strip()) == bool(celular.strip()):
        raise DadoInvalidoError("informe a placa ou o celular (um de cada vez)")
    if placa.strip():
        try:
            canonica = normalizar_placa(placa)
        except PlacaInvalidaError as erro:
            raise DadoInvalidoError(f"placa inválida: {erro}") from erro
        return _pela_placa(sessao, empresa, canonica)
    try:
        normalizado = normalizar_celular(celular)
    except CelularInvalidoError as erro:
        raise DadoInvalidoError(f"celular inválido: {erro}") from erro
    return _pelo_celular(sessao, empresa, normalizado)


def _pela_placa(sessao: Session, empresa: Empresa, placa: str) -> Levantamento:
    da_empresa = empresa.id
    agendamentos = list(
        sessao.scalars(
            select(Agendamento)
            .where(
                Agendamento.empresa_id == da_empresa,
                or_(
                    Agendamento.placa_cavalo == placa,
                    Agendamento.placas_reboques.contains([placa]),
                ),
            )
            .order_by(Agendamento.janela_inicio, Agendamento.id)
        )
    )
    visitas = list(
        sessao.scalars(
            select(Visita)
            .where(Visita.empresa_id == da_empresa, Visita.composicao.contains([{"placa": placa}]))
            .order_by(Visita.criada_em, Visita.id)
        )
    )
    passagens = list(
        sessao.scalars(
            select(PassagemRecebida)
            .where(
                PassagemRecebida.empresa_id == da_empresa,
                PassagemRecebida.como_veio.contains({"placas": [{"placa": placa}]}),
            )
            .order_by(PassagemRecebida.recebida_em)
        )
    )
    conferencias = sessao.scalars(
        select(ConferenciaPlaca)
        .where(
            ConferenciaPlaca.empresa_id == da_empresa,
            or_(ConferenciaPlaca.placa == placa, ConferenciaPlaca.placa_lida == placa),
        )
        .order_by(ConferenciaPlaca.momento, ConferenciaPlaca.id)
    )
    mensagens = sessao.scalars(
        select(Mensagem)
        .where(
            Mensagem.empresa_id == da_empresa,
            Mensagem.agendamento_id.in_([a.id for a in agendamentos]),
        )
        .order_by(Mensagem.criada_em, Mensagem.id)
    )
    return Levantamento(
        empresa=empresa.nome,
        procurado=f"placa {placa}",
        visitas=_visitas(sessao, visitas),
        passagens=_passagens(sessao, passagens),
        conferencias=[_conferencia(c) for c in conferencias],
        agendamentos=[_agendamento(a) for a in agendamentos],
        mensagens=[_mensagem(m) for m in mensagens],
    )


def _pelo_celular(sessao: Session, empresa: Empresa, celular: str) -> Levantamento:
    da_empresa = empresa.id
    agendamentos = list(
        sessao.scalars(
            select(Agendamento)
            .where(Agendamento.empresa_id == da_empresa, Agendamento.motorista_celular == celular)
            .order_by(Agendamento.janela_inicio, Agendamento.id)
        )
    )
    visitas = list(
        sessao.scalars(
            select(Visita)
            .where(
                Visita.empresa_id == da_empresa,
                Visita.agendamento_id.in_([a.id for a in agendamentos]),
            )
            .order_by(Visita.criada_em, Visita.id)
        )
    )
    mensagens = sessao.scalars(
        select(Mensagem)
        .where(Mensagem.empresa_id == da_empresa, Mensagem.para == celular)
        .order_by(Mensagem.criada_em, Mensagem.id)
    )
    autorizacoes = sessao.scalars(
        select(AutorizacaoWhatsApp)
        .where(AutorizacaoWhatsApp.empresa_id == da_empresa, AutorizacaoWhatsApp.celular == celular)
        .order_by(AutorizacaoWhatsApp.autorizada_em, AutorizacaoWhatsApp.id)
    )
    # O WhatsApp dá o número sem o "+", e às vezes sem o 9 do celular.
    numeros = {celular.removeprefix("+"), celular.removeprefix("+")[:4] + celular[6:]}
    recebidas = sessao.scalars(
        select(MensagemRecebida)
        .where(MensagemRecebida.empresa_id == da_empresa, MensagemRecebida.de.in_(numeros))
        .order_by(MensagemRecebida.recebida_em, MensagemRecebida.id)
    )
    return Levantamento(
        empresa=empresa.nome,
        procurado=f"celular {celular}",
        visitas=_visitas(sessao, visitas),
        agendamentos=[_agendamento(a) for a in agendamentos],
        mensagens=[_mensagem(m) for m in mensagens],
        autorizacoes=[
            {
                "celular": a.celular,
                "autorizada_em": _hora(a.autorizada_em),
                "revogada_em": _hora(a.revogada_em),
                "texto": a.texto,
            }
            for a in autorizacoes
        ],
        recebidas=[
            {
                "de": r.de,
                "texto": r.texto,
                "recebida_em": _hora(r.recebida_em),
                "resultado": r.resultado,
            }
            for r in recebidas
        ],
    )


def _hora(momento: datetime | None) -> str | None:
    return momento.isoformat() if momento is not None else None


def _visitas(sessao: Session, visitas: list[Visita]) -> list[dict[str, Any]]:
    sites = {
        site.id: site.nome
        for site in sessao.scalars(select(Site).where(Site.id.in_({v.site_id for v in visitas})))
    }
    return [
        {
            "id": v.id,
            "site": sites.get(v.site_id, ""),
            "estado": v.estado,
            "placas": [item["placa"] for item in v.composicao or []],
            "chegou_em": _hora(v.chegou_em),
            "saiu_em": _hora(v.saiu_em),
        }
        for v in visitas
    ]


def _passagens(sessao: Session, passagens: list[PassagemRecebida]) -> list[dict[str, Any]]:
    ids = [p.id for p in passagens]
    resumidas = {
        (f.passagem_id, f.indice)
        for f in sessao.scalars(select(FotoRecebida).where(FotoRecebida.passagem_id.in_(ids)))
    }
    apagadas = {
        (f.passagem_id, f.indice): f.apagada_em
        for f in sessao.scalars(select(FotoApagada).where(FotoApagada.passagem_id.in_(ids)))
    }
    linhas = []
    for passagem in passagens:
        fotos = []
        for indice, foto in enumerate(passagem.como_veio["fotos"]):
            chave = (passagem.id, indice)
            situacao = "guardada" if chave in resumidas else "não chegou"
            if chave in apagadas:
                situacao = f"apagada em {apagadas[chave]:%d/%m/%Y} pelo prazo de guarda"
            fotos.append({"tipo": foto["tipo"], "situacao": situacao})
        linhas.append(
            {
                "id": str(passagem.id),
                "sentido": passagem.sentido,
                "inicio": _hora(passagem.inicio),
                "placas": [p["placa"] for p in passagem.como_veio["placas"]],
                "fotos": fotos,
            }
        )
    return linhas


def _conferencia(conferida: ConferenciaPlaca) -> dict[str, Any]:
    return {
        "passagem": str(conferida.passagem_id),
        "placa_lida": conferida.placa_lida,
        "placa": conferida.placa,
        "momento": _hora(conferida.momento),
    }


def _agendamento(agendamento: Agendamento) -> dict[str, Any]:
    return {
        "codigo": agendamento.codigo_externo,
        "janela_inicio": _hora(agendamento.janela_inicio),
        "placa_cavalo": agendamento.placa_cavalo,
        "placas_reboques": list(agendamento.placas_reboques or []),
        "motorista_nome": agendamento.motorista_nome,
        "motorista_celular": agendamento.motorista_celular,
        "situacao": agendamento.situacao,
    }


def _mensagem(mensagem: Mensagem) -> dict[str, Any]:
    return {
        "modelo": mensagem.modelo,
        "canal": mensagem.canal,
        "para": mensagem.para,
        "texto": mensagem.texto,
        "situacao": mensagem.situacao,
        "criada_em": _hora(mensagem.criada_em),
    }

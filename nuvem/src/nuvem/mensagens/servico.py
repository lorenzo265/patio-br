"""Mensagens ao motorista (SDD 2.2, D-47, D-58 e D-63): nascem dos eventos, pelo worker.

- **Confirmação:** o agendamento ativo com celular, que ainda não terminou, recebe uma para cada
  celular que teve (o celular novo ainda não sabe de nada).
- **Avisos:** o check-in avisa a posição na fila; a chamada, a doca; o fim na doca, que pode
  sair. Cada evento avisa uma vez só, no celular que o agendamento tem na hora.
- **Só o recente:** o worker olha os eventos dos últimos 30 minutos (aviso mais velho chegaria
  tarde) e os agendamentos criados ou mudados no último dia.
- **O canal** (D-63): sem o WhatsApp e sem o SMS configurados, o de demonstração, que só guarda;
  com eles, o WhatsApp para o celular que autorizou a empresa, e o SMS para os outros, com o
  texto curto do SMS (D-64). A mensagem que sai vira a tarefa "enviar mensagem".
- **A reserva** (D-64): a mensagem do WhatsApp que falha de vez ganha uma cópia pelo SMS.
- **O aviso da Meta** (``tratar_aviso``): a situação de cada mensagem (enviada, entregue, lida,
  falhou) e as mensagens que o motorista mandou: a autorização ("AVISOS ...") e o "SAIR".

O texto fica pronto na mensagem, sem o nome do motorista. O módulo lê a portaria, o pátio e o
agendamento só pelas funções de serviço deles (SDD 3.3). As funções gravam sem ``commit``; quem
lê passa o ``Acesso``.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nuvem import tarefas_de_fundo
from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.modelos import Agendamento
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.servico import HorarioDoSite
from nuvem.mensagens import sms, whatsapp
from nuvem.mensagens.canais import (
    Canais,
    CanalDeEnvio,
    EnvioFalhouError,
    EnvioRecusadoError,
    Situacao,
)
from nuvem.mensagens.modelos import (
    AutorizacaoWhatsApp,
    Canal,
    Mensagem,
    MensagemRecebida,
    ModeloDeMensagem,
    ResultadoDaRecebida,
    SituacaoDaMensagem,
)
from nuvem.mensagens.modelos_do_whatsapp import preencher
from nuvem.patio import servico as patio
from nuvem.portaria import visitas
from nuvem.portaria.modelos import Evento, TipoDeEvento, Visita

_registro = logging.getLogger(__name__)

AVISOS_OLHADOS = timedelta(minutes=30)
"""O evento mais velho que isso não avisa mais: o aviso chegaria tarde (ex.: a doca já mudou)."""

AGENDAMENTOS_OLHADOS = timedelta(days=1)
"""A confirmação olha os agendamentos criados ou mudados no último dia (cobre o worker parado)."""

SEM_ENVIO: Canal = "demonstracao"
"""O canal sem o WhatsApp configurado: só guarda (D-45)."""

RESPOSTA_DA_AUTORIZACAO = (
    "Pronto! Os avisos da fila e da doca vão chegar por aqui. Para parar, responda SAIR."
)
RESPOSTA_DO_SAIR = (
    "Pronto, você não vai mais receber avisos por aqui. Se mudar de ideia, use o link do SMS "
    "ou o QR da portaria."
)
ORDEM_DA_SITUACAO: dict[SituacaoDaMensagem, int] = {
    "guardada": 0,
    "enviada": 1,
    "entregue": 2,
    "lida": 3,
    "falhou": 1,
}
"""O aviso da Meta chega fora de ordem: a situação só anda para a frente (falhar, só antes de
entregar)."""
QUANDO_DA_SITUACAO = {
    "enviada": "enviada_em",
    "entregue": "entregue_em",
    "lida": "lida_em",
    "falhou": "falhou_em",
}

AVISO_DO_EVENTO: dict[TipoDeEvento, ModeloDeMensagem] = {
    "check_in": "na_fila",
    "chamada": "chamada",
    "fim_na_doca": "pode_sair",
}
"""Os eventos da visita que avisam o motorista, e o modelo de cada aviso."""

ULTIMAS_CONVERSAS = 50
"""Quantas conversas a lista de um site mostra."""


@dataclass(frozen=True)
class Conversa:
    """As mensagens de um agendamento, pela última."""

    agendamento_id: int
    ultima: Mensagem
    quantas: int


# --- Preparar ---------------------------------------------------------------------------------


def preparar(sessao: Session, *, agora: datetime, canais: Canais | None = None) -> int:
    """Grava as mensagens que faltam, de todos os sites (sem ``commit``).

    Dois workers ao mesmo tempo não repetem nada: o banco recusa a segunda, e ela fica de fora.
    A mensagem de um canal configurado vira a tarefa "enviar mensagem".

    Returns:
        Quantas mensagens gravou.
    """
    sites = _Sites(sessao)
    novas = _confirmacoes(sessao, sites, agora) + _avisos(sessao, sites, agora)
    if not novas:
        return 0
    _escolher_os_canais(sessao, novas, canais)
    gravadas = sessao.execute(
        insert(Mensagem)
        .values(novas)
        .on_conflict_do_nothing()
        .returning(Mensagem.id, Mensagem.canal)
    ).all()
    for mensagem_id, canal in gravadas:
        if canais is not None and _canal_de_envio(canais, canal) is not None:
            tarefas_de_fundo.enfileirar(
                sessao,
                "enviar_mensagem",
                {"mensagem_id": mensagem_id},
                chave=str(mensagem_id),
                agora=agora,
            )
    return len(gravadas)


def _escolher_os_canais(
    sessao: Session, novas: list[dict[str, Any]], canais: Canais | None
) -> None:
    # O WhatsApp só para o celular que autorizou aquela empresa (D-58); os outros, por SMS, com o
    # texto do SMS (D-64).
    if canais is None or (canais.whatsapp is None and canais.sms is None):
        for nova in novas:
            nova["canal"] = SEM_ENVIO
        return
    autorizados = {
        (empresa_id, celular)
        for empresa_id, celular in sessao.execute(
            select(AutorizacaoWhatsApp.empresa_id, AutorizacaoWhatsApp.celular).where(
                AutorizacaoWhatsApp.celular.in_({nova["para"] for nova in novas}),
                AutorizacaoWhatsApp.revogada_em.is_(None),
            )
        )
    }
    for nova in novas:
        par = (nova["empresa_id"], nova["para"])
        if canais.whatsapp is not None and par in autorizados:
            nova["canal"] = "whatsapp"
        else:
            nova["canal"] = "sms"
            nova["texto"] = _texto_do_sms(nova, canais)


def _texto_do_sms(mensagem: dict[str, Any], canais: Canais) -> str:
    return sms.texto_do_sms(
        mensagem["modelo"],
        mensagem["variaveis"],
        agendamento_id=mensagem["agendamento_id"],
        numero_do_whatsapp=canais.whatsapp.numero if canais.whatsapp else None,
    )


def _canal_de_envio(canais: Canais, canal: Canal) -> CanalDeEnvio | None:
    if canal == "whatsapp":
        return canais.whatsapp
    if canal == "sms":
        return canais.sms
    return None


def _confirmacoes(sessao: Session, sites: "_Sites", agora: datetime) -> list[dict[str, Any]]:
    candidatos = agendamentos.para_confirmar(
        sessao, mudados_desde=agora - AGENDAMENTOS_OLHADOS, agora=agora
    )
    confirmados = {
        (agendamento_id, para)
        for agendamento_id, para in sessao.execute(
            select(Mensagem.agendamento_id, Mensagem.para).where(
                Mensagem.modelo == "confirmacao",
                Mensagem.agendamento_id.in_([a.id for a in candidatos]),
            )
        )
    }
    return [
        _mensagem(a, "confirmacao", _variaveis_da_confirmacao(a, sites.de(a)), agora)
        for a in candidatos
        if (a.id, a.motorista_celular) not in confirmados
    ]


def _avisos(sessao: Session, sites: "_Sites", agora: datetime) -> list[dict[str, Any]]:
    recentes = visitas.eventos_recentes(
        sessao, tuple(AVISO_DO_EVENTO), desde=agora - AVISOS_OLHADOS
    )
    avisados = set(
        sessao.scalars(
            select(Mensagem.evento_id).where(Mensagem.evento_id.in_([e.id for e, _ in recentes]))
        )
    )
    pendentes = [(evento, visita) for evento, visita in recentes if evento.id not in avisados]
    contatos = agendamentos.com_celular(sessao, [v.agendamento_id or 0 for _, v in pendentes])
    novas = []
    for evento, visita in pendentes:
        agendamento = contatos.get(visita.agendamento_id or 0)
        if agendamento is None:
            continue
        modelo = AVISO_DO_EVENTO[evento.tipo]
        variaveis = _variaveis_do_aviso(
            sessao, modelo, evento, visita, agendamento, sites.de(agendamento)
        )
        novas.append(_mensagem(agendamento, modelo, variaveis, agora, evento_id=evento.id))
    return novas


def _mensagem(
    agendamento: Agendamento,
    modelo: ModeloDeMensagem,
    variaveis: list[str],
    agora: datetime,
    evento_id: int | None = None,
) -> dict[str, Any]:
    return {
        "empresa_id": agendamento.empresa_id,
        "site_id": agendamento.site_id,
        "agendamento_id": agendamento.id,
        "evento_id": evento_id,
        "modelo": modelo,
        "canal": SEM_ENVIO,
        "para": agendamento.motorista_celular,
        "texto": preencher(modelo, variaveis),
        "variaveis": variaveis,
        "situacao": "guardada",
        "criada_em": agora,
    }


class _Sites:
    """O nome e o fuso de cada site, lidos uma vez por preparo."""

    def __init__(self, sessao: Session) -> None:
        self._sessao = sessao
        self._lidos: dict[tuple[int, int], HorarioDoSite] = {}

    def de(self, agendamento: Agendamento) -> HorarioDoSite:
        chave = (agendamento.empresa_id, agendamento.site_id)
        if chave not in self._lidos:
            self._lidos[chave] = cadastro.horario_do_site(
                self._sessao, empresa_id=agendamento.empresa_id, site_id=agendamento.site_id
            )
        return self._lidos[chave]


# --- As variáveis dos modelos (os textos estão em ``modelos_do_whatsapp``) --------------------


def _variaveis_da_confirmacao(agendamento: Agendamento, site: HorarioDoSite) -> list[str]:
    fuso = ZoneInfo(site.fuso)
    inicio = agendamento.janela_inicio.astimezone(fuso)
    fim = agendamento.janela_fim.astimezone(fuso)
    return [
        agendamento.tipo.capitalize(),
        site.nome,
        f"{inicio:%d/%m}",
        f"{inicio:%H:%M}",
        f"{fim:%H:%M}",
        agendamento.codigo_externo,
    ]


def _variaveis_do_aviso(
    sessao: Session,
    modelo: ModeloDeMensagem,
    evento: Evento,
    visita: Visita,
    agendamento: Agendamento,
    site: HorarioDoSite,
) -> list[str]:
    if modelo == "na_fila":
        chegada = (visita.chegou_em or evento.momento).astimezone(ZoneInfo(site.fuso))
        return [f"{chegada:%H:%M}", str(patio.posicao_na_fila(sessao, visita))]
    if modelo == "chamada":
        return [str(evento.dados["doca"])]
    return [agendamento.tipo.capitalize()]


# --- Enviar -----------------------------------------------------------------------------------


def enviar(sessao: Session, canais: Canais, mensagem_id: int, *, agora: datetime) -> None:
    """Manda uma mensagem guardada pelo canal dela (a tarefa "enviar mensagem"; sem ``commit``).

    A que já saiu não sai de novo. A recusa definitiva deixa a mensagem como falhou.

    Raises:
        EnvioFalhouError: se vale tentar de novo (a tarefa volta para a fila); também quando o
            canal da mensagem não está configurado.
    """
    mensagem = sessao.get(Mensagem, mensagem_id)
    if mensagem is None or mensagem.situacao != "guardada":
        return
    canal = _canal_de_envio(canais, mensagem.canal)
    if canal is None:
        raise EnvioFalhouError(f"o canal {mensagem.canal} não está configurado")
    try:
        envio = canal.enviar(mensagem)
    except EnvioRecusadoError as erro:
        mensagem.situacao = "falhou"
        mensagem.falhou_em = agora
        mensagem.erro = str(erro)[:300]
        _reserva_pelo_sms(sessao, canais, mensagem, agora)
    else:
        mensagem.situacao = "enviada"
        mensagem.id_no_canal = envio.id_no_canal
        mensagem.enviada_em = agora
    sessao.flush()


# --- O aviso da Meta --------------------------------------------------------------------------


def tratar_aviso(
    sessao: Session, canais: Canais, aviso: dict[str, Any], *, agora: datetime
) -> None:
    """Trata um aviso do webhook do WhatsApp (a tarefa "aviso do WhatsApp"; sem ``commit``).

    Atualiza a situação das mensagens e trata as que chegaram: "AVISOS A<agendamento>" ou
    "AVISOS S<site>" autoriza o celular de quem mandou na empresa do pedido; "SAIR" cancela a
    autorização dele em todas as empresas (D-58). O resto fica registrado, sem resposta.
    """
    situacoes, recebidas = whatsapp.ler_aviso(aviso)
    for situacao in situacoes:
        mensagem = _atualizar(sessao, "whatsapp", situacao)
        if mensagem is not None and mensagem.situacao == "falhou":
            _reserva_pelo_sms(sessao, canais, mensagem, agora)
    for recebida in recebidas:
        _tratar_recebida(sessao, canais, recebida, agora)
    sessao.flush()


def tratar_aviso_do_sms(sessao: Session, evento: dict[str, Any]) -> None:
    """Trata um retorno da Zenvia (a tarefa "aviso do SMS"; sem ``commit``): a entrega do SMS.

    O SMS que falha não ganha outra cópia: o motorista fica sem aviso, e o pátio mostra isso.
    """
    situacao = sms.ler_aviso_do_sms(evento)
    if situacao is not None:
        _atualizar(sessao, "sms", situacao)
        sessao.flush()


def _reserva_pelo_sms(sessao: Session, canais: Canais, mensagem: Mensagem, agora: datetime) -> None:
    # A cópia do aviso pelo SMS (D-64), uma só por aviso: o banco recusa a segunda.
    if mensagem.canal != "whatsapp" or canais.sms is None:
        return
    copia = {
        "empresa_id": mensagem.empresa_id,
        "site_id": mensagem.site_id,
        "agendamento_id": mensagem.agendamento_id,
        "evento_id": mensagem.evento_id,
        "modelo": mensagem.modelo,
        "canal": "sms",
        "para": mensagem.para,
        "variaveis": mensagem.variaveis or [],
        "situacao": "guardada",
        "criada_em": agora,
    }
    copia["texto"] = _texto_do_sms(copia, canais)
    nova = sessao.scalar(
        insert(Mensagem).values(copia).on_conflict_do_nothing().returning(Mensagem.id)
    )
    if nova is not None:
        tarefas_de_fundo.enfileirar(
            sessao, "enviar_mensagem", {"mensagem_id": nova}, chave=str(nova), agora=agora
        )


def _atualizar(sessao: Session, canal: Canal, situacao: Situacao) -> Mensagem | None:
    mensagem = sessao.scalar(
        select(Mensagem).where(
            Mensagem.canal == canal, Mensagem.id_no_canal == situacao.id_no_canal
        )
    )
    if mensagem is None:
        return None
    coluna = QUANDO_DA_SITUACAO[situacao.situacao]
    if getattr(mensagem, coluna) is None:
        setattr(mensagem, coluna, situacao.momento)
    atual = ORDEM_DA_SITUACAO[mensagem.situacao]
    if situacao.situacao == "falhou":
        if mensagem.situacao in ("guardada", "enviada"):
            mensagem.situacao = "falhou"
            mensagem.erro = (situacao.erro or "")[:300] or None
    elif ORDEM_DA_SITUACAO[situacao.situacao] > atual and mensagem.situacao != "falhou":
        mensagem.situacao = situacao.situacao
    if situacao.categoria:
        mensagem.cobranca = situacao.categoria[:30]
    return mensagem


def _tratar_recebida(
    sessao: Session, canais: Canais, recebida: whatsapp.Recebida, agora: datetime
) -> None:
    repetida = sessao.scalar(
        select(MensagemRecebida.id).where(
            MensagemRecebida.id_no_whatsapp == recebida.id_no_whatsapp
        )
    )
    if repetida is not None:
        return  # a Meta repete o aviso que demorou a responder
    celular = whatsapp.celular_do_whatsapp(recebida.de)
    pedido = whatsapp.o_que_pediu(recebida.texto)
    resultado: ResultadoDaRecebida = "ignorada"
    empresa_id: int | None = None
    resposta: str | None = None
    if celular is not None and pedido is not None:
        if pedido[0] == "sair":
            sessao.execute(
                update(AutorizacaoWhatsApp)
                .where(
                    AutorizacaoWhatsApp.celular == celular,
                    AutorizacaoWhatsApp.revogada_em.is_(None),
                )
                .values(revogada_em=agora)
            )
            resultado, resposta = "saiu", RESPOSTA_DO_SAIR
        else:
            empresa_id = _empresa_do_pedido(sessao, pedido)
            if empresa_id is not None:
                _autorizar(sessao, empresa_id, celular, recebida, agora)
                resultado, resposta = "autorizou", RESPOSTA_DA_AUTORIZACAO
    sessao.add(
        MensagemRecebida(
            id_no_whatsapp=recebida.id_no_whatsapp,
            de=recebida.de[:20],
            texto=recebida.texto[:1000],
            recebida_em=recebida.momento,
            empresa_id=empresa_id,
            resultado=resultado,
            tratada_em=agora,
        )
    )
    sessao.flush()
    if resposta is not None and celular is not None and canais.whatsapp is not None:
        # A resposta é cortesia: se falha, não se tenta de novo o aviso inteiro (quem já
        # recebeu a resposta de outra mensagem do mesmo aviso receberia outra).
        try:
            canais.whatsapp.responder(celular, resposta)
        except (EnvioFalhouError, EnvioRecusadoError) as erro:
            _registro.warning(
                "a resposta à mensagem recebida %s falhou: %s", recebida.id_no_whatsapp, erro
            )


def _empresa_do_pedido(sessao: Session, pedido: whatsapp.Pedido) -> int | None:
    tipo, numero = pedido
    if numero is None:
        return None
    if tipo == "agendamento":
        return agendamentos.empresa_do_agendamento(sessao, numero)
    return cadastro.empresa_do_site(sessao, numero)


def _autorizar(
    sessao: Session,
    empresa_id: int,
    celular: str,
    recebida: whatsapp.Recebida,
    agora: datetime,
) -> None:
    # Autorizar de novo não muda nada: uma autorização ativa por empresa e celular.
    sessao.execute(
        insert(AutorizacaoWhatsApp)
        .values(
            empresa_id=empresa_id,
            celular=celular,
            autorizada_em=agora,
            texto=recebida.texto[:1000],
            id_no_whatsapp=recebida.id_no_whatsapp,
        )
        .on_conflict_do_nothing(
            index_elements=["empresa_id", "celular"], index_where=text("revogada_em IS NULL")
        )
    )


# --- Ler --------------------------------------------------------------------------------------


def conversa(sessao: Session, acesso: Acesso, agendamento_id: int) -> list[Mensagem]:
    """As mensagens de um agendamento que o usuário vê, na ordem em que foram feitas.

    Raises:
        NaoEncontradoError: se o agendamento não for visível para este usuário.
    """
    agendamento = agendamentos.obter(sessao, acesso, agendamento_id)
    return list(
        sessao.scalars(
            select(Mensagem)
            .where(
                Mensagem.empresa_id == acesso.empresa_id,
                Mensagem.agendamento_id == agendamento.id,
            )
            .order_by(Mensagem.criada_em, Mensagem.id)
        )
    )


def conversas(
    sessao: Session, acesso: Acesso, site_id: int, *, limite: int = ULTIMAS_CONVERSAS
) -> list[Conversa]:
    """As conversas de um site que o usuário vê, da última mensagem para a primeira.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    numeradas = (
        select(
            Mensagem.id,
            func.row_number()
            .over(
                partition_by=Mensagem.agendamento_id,
                order_by=(Mensagem.criada_em.desc(), Mensagem.id.desc()),
            )
            .label("ordem"),
            func.count().over(partition_by=Mensagem.agendamento_id).label("quantas"),
        )
        .where(Mensagem.empresa_id == acesso.empresa_id, Mensagem.site_id == site.id)
        .subquery()
    )
    linhas = sessao.execute(
        select(Mensagem, numeradas.c.quantas)
        .join(numeradas, numeradas.c.id == Mensagem.id)
        .where(numeradas.c.ordem == 1)
        .order_by(Mensagem.criada_em.desc(), Mensagem.id.desc())
        .limit(limite)
    )
    return [Conversa(mensagem.agendamento_id, mensagem, quantas) for mensagem, quantas in linhas]


def nao_avisados(sessao: Session, acesso: Acesso, agendamento_ids: Sequence[int]) -> set[int]:
    """Os agendamentos, entre estes, cujo motorista não recebeu o último aviso (D-64).

    O último aviso é o da mensagem mais nova; ele não chegou quando todas as tentativas dele (o
    WhatsApp e a reserva pelo SMS) falharam. A que ainda não saiu não conta.
    """
    if not agendamento_ids:
        return set()
    linhas = sessao.execute(
        select(Mensagem.agendamento_id, Mensagem.evento_id, Mensagem.modelo, Mensagem.situacao)
        .where(
            Mensagem.empresa_id == acesso.empresa_id,
            Mensagem.agendamento_id.in_(agendamento_ids),
            Mensagem.site_id.in_(acesso.sites),
        )
        .order_by(Mensagem.criada_em, Mensagem.id)
    )
    tentativas: dict[int, tuple[tuple[int | None, str], list[str]]] = {}
    for agendamento_id, evento_id, modelo, situacao in linhas:
        aviso = (evento_id, modelo)
        ultimo = tentativas.get(agendamento_id)
        if ultimo is None or ultimo[0] != aviso:
            tentativas[agendamento_id] = (aviso, [situacao])
        else:
            ultimo[1].append(situacao)
    return {
        agendamento_id
        for agendamento_id, (_, situacoes) in tentativas.items()
        if all(situacao == "falhou" for situacao in situacoes)
    }

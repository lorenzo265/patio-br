"""Os alertas (SDD 8.1, D-62 e D-68).

- **Conferir:** a cada minuto, o worker (um de cada vez) levanta as situações de agora; o alerta
  de uma situação nova abre, e o da situação que passou fecha. Um alerta aberto não se repete.
- **Quem vê:** quem é do cliente vê os alertas dos sites dele (o sino e a tela ``/alertas``); a
  administração vê a caixa, a câmera e as tarefas de todas as empresas.
- **O WhatsApp:** os graves vão a quem autorizou, por um código de uso único que a tela mostra
  ("ALERTAS <código>", 10 minutos). O aviso sai por uma tarefa da fila.

Os tempos ficam no código até o ``[ABERTO-09]`` e o cliente do piloto.
"""

import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from nuvem import tarefas_de_fundo
from nuvem.alertas.modelos import Alerta, AlertasNoWhatsApp, AvisoDeAlerta, TipoDeAlerta
from nuvem.cadastro.acesso import Acesso, AcessoAdmin
from nuvem.cadastro.modelos import Empresa, Site, Usuario, UsuarioSite
from nuvem.erros import SemPermissaoError
from nuvem.frota import saude as frota
from nuvem.frota.modelos import CaixaBorda, SaudeCaixa
from nuvem.mensagens import servico as mensagens
from nuvem.mensagens.canais import Canais, EnvioRecusadoError
from nuvem.portaria.modelos import Excecao, Visita
from nuvem.senhas import resumo_rapido

ESTADIA_PERTO = timedelta(hours=4)
ESTADIA_PASSOU = timedelta(hours=5)
DIFERENCA_DO_RELOGIO = 2.0
"""Segundos: acima disso, o relógio da caixa está errado."""
VALIDADE_DO_CODIGO = timedelta(minutes=10)
JANELA_DOS_RECENTES = timedelta(hours=24)

GRAVES: frozenset[TipoDeAlerta] = frozenset(
    {"estadia_passou", "caixa_sem_contato", "camera_parada"}
)
"""Os que vão pelo WhatsApp (D-62)."""
DA_ADMINISTRACAO: frozenset[TipoDeAlerta] = frozenset(
    {"caixa_sem_contato", "camera_parada", "tarefa_falhou"}
)
"""Os que a administração vê; dos graves, a caixa e a câmera vão também pelo WhatsApp a ela."""

NO_SITE = ("NA_FILA", "EXCECAO", "CHAMADA", "NA_DOCA", "LIBERADA")
"""A visita que chegou e ainda não saiu."""

TRAVA_DOS_ALERTAS = 7303
ALFABETO_DO_CODIGO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
"""Letras e números sem os que se confundem (0 e O, 1, I e L)."""
TAMANHO_DO_CODIGO = 8
TAMANHO_DO_TEXTO = 300


@dataclass(frozen=True)
class Situacao:
    """O que está acontecendo agora e pede um alerta."""

    tipo: TipoDeAlerta
    chave: str
    empresa_id: int | None
    site_id: int | None
    texto: str


@dataclass(frozen=True)
class Lugar:
    """A empresa e o site de um alerta, para a tela da administração."""

    empresa: str
    site: str
    fuso: str


@dataclass(frozen=True)
class Conferencia:
    """Quantos alertas abriram e quantos fecharam numa conferência."""

    abertos: int
    fechados: int


# --- Conferir -------------------------------------------------------------------------------


def conferir(sessao: Session, *, agora: datetime) -> Conferencia:
    """Abre os alertas das situações novas e fecha os das que passaram (com ``flush``).

    Um de cada vez (trava do PostgreSQL): com outra conferência rodando, esta não faz nada.
    """
    if not sessao.scalar(select(func.pg_try_advisory_xact_lock(TRAVA_DOS_ALERTAS))):
        return Conferencia(0, 0)
    atuais = {(s.tipo, s.chave): s for s in _situacoes(sessao, agora)}
    abertos = {
        (alerta.tipo, alerta.chave): alerta
        for alerta in sessao.scalars(select(Alerta).where(Alerta.fechado_em.is_(None)))
    }
    fechados = 0
    for chave, alerta in abertos.items():
        if chave not in atuais:
            alerta.fechado_em = agora
            fechados += 1
    novos = []
    for chave, situacao in atuais.items():
        if chave not in abertos:
            alerta = Alerta(
                empresa_id=situacao.empresa_id,
                site_id=situacao.site_id,
                tipo=situacao.tipo,
                chave=situacao.chave,
                texto=situacao.texto[:TAMANHO_DO_TEXTO],
                aberto_em=agora,
            )
            sessao.add(alerta)
            novos.append(alerta)
    sessao.flush()
    for alerta in novos:
        _avisar_quem_autorizou(sessao, alerta, agora)
    return Conferencia(abertos=len(novos), fechados=fechados)


def _situacoes(sessao: Session, agora: datetime) -> Iterator[Situacao]:
    fusos = {site_id: fuso for site_id, fuso in sessao.execute(select(Site.id, Site.fuso))}
    yield from _estadias(sessao, agora, fusos)
    yield from _chegadas_sem_agendamento(sessao, fusos)
    yield from _caixas(sessao, agora, fusos)
    yield from _motoristas_nao_avisados(sessao)
    yield from _tarefas_que_falharam(sessao)


def _estadias(sessao: Session, agora: datetime, fusos: dict[int, str]) -> Iterator[Situacao]:
    visitas = sessao.scalars(
        select(Visita).where(Visita.estado.in_(NO_SITE), Visita.chegou_em <= agora - ESTADIA_PERTO)
    )
    for visita in visitas:
        assert visita.chegou_em is not None  # quem está no site chegou
        tempo = agora - visita.chegou_em
        tipo: TipoDeAlerta = "estadia_passou" if tempo >= ESTADIA_PASSOU else "estadia_perto"
        chegada = visita.chegou_em.astimezone(ZoneInfo(fusos[visita.site_id]))
        horas = int(tempo.total_seconds() // 3600)
        yield Situacao(
            tipo,
            f"visita:{visita.id}",
            visita.empresa_id,
            visita.site_id,
            f"{_placa(visita)} no site há {horas} horas (chegou às {chegada:%H:%M})",
        )


def _chegadas_sem_agendamento(sessao: Session, fusos: dict[int, str]) -> Iterator[Situacao]:
    linhas = sessao.execute(
        select(Excecao.id, Visita)
        .join(
            Visita,
            (Visita.id == Excecao.visita_id) & (Visita.empresa_id == Excecao.empresa_id),
        )
        .where(Excecao.situacao == "aberta", Excecao.motivo == "sem_candidato")
    ).all()
    for excecao_id, visita in linhas:
        assert visita.chegou_em is not None
        chegada = visita.chegou_em.astimezone(ZoneInfo(fusos[visita.site_id]))
        yield Situacao(
            "sem_agendamento",
            f"excecao:{excecao_id}",
            visita.empresa_id,
            visita.site_id,
            f"Chegada sem agendamento: {_placa(visita)} às {chegada:%H:%M}",
        )


def _caixas(sessao: Session, agora: datetime, fusos: dict[int, str]) -> Iterator[Situacao]:
    caixas = list(
        sessao.scalars(
            select(CaixaBorda).where(
                CaixaBorda.revogada_em.is_(None), CaixaBorda.ultimo_contato.is_not(None)
            )
        )
    )
    nomes = frota.nomes_das_cameras(sessao, {caixa.site_id for caixa in caixas})
    for caixa in caixas:
        assert caixa.ultimo_contato is not None
        de = (caixa.empresa_id, caixa.site_id)
        if frota.sem_contato(caixa.ultimo_contato, agora=agora):
            desde = caixa.ultimo_contato.astimezone(ZoneInfo(fusos[caixa.site_id]))
            yield Situacao(
                "caixa_sem_contato",
                f"caixa:{caixa.id}",
                *de,
                f"Caixa {caixa.id} sem contato desde {desde:%H:%M}",
            )
            continue
        diferenca = caixa.diferenca_do_relogio or 0.0
        if abs(diferenca) > DIFERENCA_DO_RELOGIO:
            yield Situacao(
                "relogio_errado",
                f"caixa:{caixa.id}",
                *de,
                f"Relógio da caixa {caixa.id} com {diferenca:+.1f} s de diferença".replace(
                    ".", ","
                ),
            )
        for camera_id in _cameras_paradas(sessao, caixa.id):
            nome = nomes.get((caixa.site_id, camera_id), f"câmera {camera_id}")
            yield Situacao(
                "camera_parada",
                f"camera:{caixa.id}:{camera_id}",
                *de,
                f"Câmera {nome} sem quadros na caixa {caixa.id}",
            )


def _cameras_paradas(sessao: Session, caixa_id: int) -> list[str]:
    # Fora do ar nas duas últimas saúdes: logo depois de a caixa ligar, a primeira ainda não tem
    # quadro, e isso não é câmera parada.
    ultimas = list(
        sessao.scalars(
            select(SaudeCaixa.dados)
            .where(SaudeCaixa.caixa_id == caixa_id)
            .order_by(SaudeCaixa.recebida_em.desc(), SaudeCaixa.id.desc())
            .limit(2)
        )
    )
    if len(ultimas) < 2:
        return []
    fora = [_fora_do_ar(dados) for dados in ultimas]
    return sorted(fora[0] & fora[1])


def _fora_do_ar(dados: dict[str, Any]) -> set[str]:
    return {str(camera["camera_id"]) for camera in dados.get("cameras", []) if not camera["no_ar"]}


def _motoristas_nao_avisados(sessao: Session) -> Iterator[Situacao]:
    visitas = list(
        sessao.scalars(
            select(Visita).where(Visita.estado.in_(NO_SITE), Visita.agendamento_id.is_not(None))
        )
    )
    por_empresa: dict[int, list[Visita]] = {}
    for visita in visitas:
        por_empresa.setdefault(visita.empresa_id, []).append(visita)
    for empresa_id, da_empresa in por_empresa.items():
        ids = [visita.agendamento_id for visita in da_empresa if visita.agendamento_id]
        nao_avisados = mensagens.nao_avisados_da_empresa(sessao, empresa_id, ids)
        for visita in da_empresa:
            if visita.agendamento_id in nao_avisados:
                yield Situacao(
                    "motorista_nao_avisado",
                    f"agendamento:{visita.agendamento_id}",
                    empresa_id,
                    visita.site_id,
                    f"Motorista de {_placa(visita)} não avisado: o último aviso falhou",
                )


def _tarefas_que_falharam(sessao: Session) -> Iterator[Situacao]:
    tarefas = sessao.scalars(
        select(tarefas_de_fundo.TarefaDeFundo).where(
            tarefas_de_fundo.TarefaDeFundo.situacao == "falhou"
        )
    )
    for tarefa in tarefas:
        yield Situacao(
            "tarefa_falhou",
            f"tarefa:{tarefa.id}",
            None,
            None,
            f"A tarefa {tarefa.id} ({tarefa.tipo}) falhou de vez: {tarefa.ultimo_erro or ''}",
        )


def _placa(visita: Visita) -> str:
    composicao: list[dict[str, str]] = visita.composicao or []
    return composicao[0]["placa"] if composicao else "sem placa"


# --- Quem vê --------------------------------------------------------------------------------


def abertos(sessao: Session, acesso: Acesso) -> list[Alerta]:
    """Os alertas abertos dos sites que o usuário vê, dos mais novos para os mais antigos."""
    return list(
        sessao.scalars(
            _do_acesso(acesso)
            .where(Alerta.fechado_em.is_(None))
            .order_by(Alerta.aberto_em.desc(), Alerta.id.desc())
        )
    )


def recentes(sessao: Session, acesso: Acesso, *, agora: datetime) -> list[Alerta]:
    """Os abertos e os fechados nas últimas 24 horas, dos sites que o usuário vê."""
    return list(
        sessao.scalars(
            _do_acesso(acesso)
            .where(
                or_(Alerta.fechado_em.is_(None), Alerta.fechado_em >= agora - JANELA_DOS_RECENTES)
            )
            .order_by(Alerta.aberto_em.desc(), Alerta.id.desc())
        )
    )


def abertos_da_administracao(sessao: Session, _administracao: AcessoAdmin) -> list[Alerta]:
    """Os alertas abertos da caixa, da câmera e das tarefas, de todas as empresas."""
    return list(
        sessao.scalars(
            select(Alerta)
            .where(Alerta.fechado_em.is_(None), Alerta.tipo.in_(DA_ADMINISTRACAO))
            .order_by(Alerta.aberto_em.desc(), Alerta.id.desc())
        )
    )


def lugares_da_administracao(
    sessao: Session, _administracao: AcessoAdmin, lista: list[Alerta]
) -> dict[int, Lugar]:
    """A empresa e o site de cada alerta que tem site (os das tarefas não têm)."""
    sites = {alerta.site_id for alerta in lista if alerta.site_id is not None}
    linhas = sessao.execute(
        select(Site.id, Site.nome, Site.fuso, Empresa.nome)
        .join(Empresa, Empresa.id == Site.empresa_id)
        .where(Site.id.in_(sites))
    )
    por_site = {site_id: Lugar(empresa, site, fuso) for site_id, site, fuso, empresa in linhas}
    return {alerta.id: por_site[alerta.site_id] for alerta in lista if alerta.site_id is not None}


def _do_acesso(acesso: Acesso) -> Any:
    return select(Alerta).where(
        Alerta.empresa_id == acesso.empresa_id, Alerta.site_id.in_(acesso.sites)
    )


# --- O WhatsApp de quem autorizou -----------------------------------------------------------


def pedir_codigo(sessao: Session, quem: Acesso | AcessoAdmin, *, agora: datetime) -> str:
    """Um código de uso único, de 10 minutos, para a pessoa ligar o celular aos alertas.

    Raises:
        SemPermissaoError: se quem é do cliente não é gestor.
    """
    if isinstance(quem, Acesso) and quem.papel != "gestor":
        raise SemPermissaoError
    sorteado = "".join(secrets.choice(ALFABETO_DO_CODIGO) for _ in range(TAMANHO_DO_CODIGO))
    sessao.add(
        AlertasNoWhatsApp(
            empresa_id=quem.empresa_id if isinstance(quem, Acesso) else None,
            usuario_id=quem.usuario_id if isinstance(quem, Acesso) else None,
            administrador_id=quem.administrador_id if isinstance(quem, AcessoAdmin) else None,
            codigo_resumo=resumo_rapido(sorteado),
            pedido_em=agora,
            vence_em=agora + VALIDADE_DO_CODIGO,
        )
    )
    sessao.flush()
    return f"{sorteado[:4]}-{sorteado[4:]}"


def celular_autorizado(sessao: Session, quem: Acesso | AcessoAdmin) -> str | None:
    """O celular que recebe os alertas graves desta pessoa, ou ``None``."""
    return sessao.scalar(
        select(AlertasNoWhatsApp.celular).where(
            _da_pessoa(quem),
            AlertasNoWhatsApp.autorizada_em.is_not(None),
            AlertasNoWhatsApp.revogada_em.is_(None),
        )
    )


def _da_pessoa(quem: Acesso | AcessoAdmin) -> Any:
    if isinstance(quem, Acesso):
        return (AlertasNoWhatsApp.usuario_id == quem.usuario_id) & (
            AlertasNoWhatsApp.empresa_id == quem.empresa_id
        )
    return AlertasNoWhatsApp.administrador_id == quem.administrador_id


def autorizar_pelo_codigo(
    sessao: Session,
    *,
    codigo: str,
    celular: str,
    texto: str,
    id_no_whatsapp: str,
    agora: datetime,
) -> bool:
    """Liga o celular de quem mandou o código à pessoa que o pediu.

    A autorização anterior da mesma pessoa deixa de valer.

    Returns:
        ``False`` se o código não existe, já foi usado ou venceu (sem dizer qual).
    """
    digitado = "".join(codigo.split()).replace("-", "").upper()
    pedido = sessao.scalar(
        select(AlertasNoWhatsApp)
        .where(
            AlertasNoWhatsApp.codigo_resumo == resumo_rapido(digitado),
            AlertasNoWhatsApp.autorizada_em.is_(None),
            AlertasNoWhatsApp.revogada_em.is_(None),
            AlertasNoWhatsApp.vence_em > agora,
        )
        .with_for_update()
    )
    if pedido is None:
        return False
    if pedido.usuario_id is not None:
        da_pessoa = AlertasNoWhatsApp.usuario_id == pedido.usuario_id
    else:
        da_pessoa = AlertasNoWhatsApp.administrador_id == pedido.administrador_id
    sessao.execute(
        update(AlertasNoWhatsApp)
        .where(
            da_pessoa,
            AlertasNoWhatsApp.autorizada_em.is_not(None),
            AlertasNoWhatsApp.revogada_em.is_(None),
        )
        .values(revogada_em=agora)
    )
    pedido.celular = celular
    pedido.autorizada_em = agora
    pedido.texto = texto[:1000]
    pedido.id_no_whatsapp = id_no_whatsapp[:100]
    sessao.flush()
    return True


def revogar_do_celular(sessao: Session, celular: str, *, agora: datetime) -> int:
    """Cancela os alertas pelo WhatsApp deste celular ("SAIR"); devolve quantas autorizações."""
    resultado = sessao.execute(
        update(AlertasNoWhatsApp)
        .where(
            AlertasNoWhatsApp.celular == celular,
            AlertasNoWhatsApp.autorizada_em.is_not(None),
            AlertasNoWhatsApp.revogada_em.is_(None),
        )
        .values(revogada_em=agora)
    )
    return int(getattr(resultado, "rowcount", 0) or 0)


def _avisar_quem_autorizou(sessao: Session, alerta: Alerta, agora: datetime) -> None:
    ativas = (
        AlertasNoWhatsApp.autorizada_em.is_not(None),
        AlertasNoWhatsApp.revogada_em.is_(None),
    )
    para: list[AlertasNoWhatsApp] = []
    if alerta.tipo in GRAVES and alerta.site_id is not None:
        para += sessao.scalars(
            select(AlertasNoWhatsApp)
            .join(
                Usuario,
                (Usuario.id == AlertasNoWhatsApp.usuario_id)
                & (Usuario.empresa_id == AlertasNoWhatsApp.empresa_id),
            )
            .join(
                UsuarioSite,
                (UsuarioSite.usuario_id == Usuario.id) & (UsuarioSite.site_id == alerta.site_id),
            )
            .where(
                *ativas,
                AlertasNoWhatsApp.empresa_id == alerta.empresa_id,
                Usuario.papel == "gestor",
                Usuario.ativo.is_(True),
            )
            .order_by(AlertasNoWhatsApp.id)
        )
    if alerta.tipo in GRAVES and alerta.tipo in DA_ADMINISTRACAO:
        para += sessao.scalars(
            select(AlertasNoWhatsApp)
            .where(*ativas, AlertasNoWhatsApp.administrador_id.is_not(None))
            .order_by(AlertasNoWhatsApp.id)
        )
    for autorizacao in para:
        assert autorizacao.celular is not None  # autorizada
        aviso = AvisoDeAlerta(
            empresa_id=alerta.empresa_id,
            alerta_id=alerta.id,
            usuario_id=autorizacao.usuario_id,
            administrador_id=autorizacao.administrador_id,
            celular=autorizacao.celular,
            situacao="guardado",
            criado_em=agora,
        )
        sessao.add(aviso)
        sessao.flush()
        tarefas_de_fundo.enfileirar(
            sessao,
            "avisar_alerta",
            {"aviso_id": aviso.id},
            chave=f"aviso_de_alerta:{aviso.id}",
            agora=agora,
        )


def avisar(sessao: Session, canais: Canais, aviso_id: int, *, agora: datetime) -> None:
    """Manda o aviso de um alerta pelo WhatsApp (a tarefa "avisar alerta").

    Sem o WhatsApp configurado, o aviso fica guardado. O erro passageiro sobe, e a tarefa tenta
    de novo; o recusado de vez deixa o aviso como falhou.
    """
    aviso = sessao.get(AvisoDeAlerta, aviso_id)
    if aviso is None or aviso.situacao != "guardado" or canais.whatsapp is None:
        return
    alerta = sessao.get(Alerta, aviso.alerta_id)
    assert alerta is not None  # o aviso aponta para ele
    site = sessao.get(Site, alerta.site_id) if alerta.site_id is not None else None
    try:
        envio = canais.whatsapp.enviar_alerta(
            aviso.celular, site.nome if site else "patio-br", alerta.texto
        )
    except EnvioRecusadoError as erro:
        aviso.situacao = "falhou"
        aviso.erro = str(erro)[:300]
        sessao.flush()
        return
    aviso.situacao = "enviado"
    aviso.id_no_canal = envio.id_no_canal
    aviso.enviado_em = agora
    sessao.flush()

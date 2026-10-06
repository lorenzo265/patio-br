"""A guarda das fotos e a disputa (SDD 8.3, D-70).

- **A foto vencida:** a cada hora, o worker apaga o arquivo das fotos das passagens que chegaram
  há mais que o prazo (``PATIO_GUARDA_FOTOS_DIAS``, 90 dias), menos as de uma visita com exceção
  aberta ou em disputa. Cada foto vira uma ``FotoApagada``, que diz se o arquivo estava lá e
  entra na cadeia da prova; o resumo dela continua lá.
- **A disputa:** o gestor marca e desmarca a visita, com o motivo; a marca só se acrescenta, e
  vale a última. Marcar o que já está marcado não grava nada.
"""

from datetime import datetime, timedelta

from sqlalchemy import Select, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from nuvem.armazenamento import Armazenamento
from nuvem.cadastro.acesso import Acesso
from nuvem.guarda.modelos import AcaoDaDisputa, FotoApagada, MarcaDeDisputa
from nuvem.portaria.modelos import Evento, Excecao, PassagemRecebida
from nuvem.portaria.visitas import obter_visita

PASSAGENS_POR_VEZ = 200
"""O worker apaga as fotos de no máximo estas passagens a cada volta (o resto, na seguinte)."""
TAMANHO_DO_MOTIVO = 300


# --- A disputa ------------------------------------------------------------------------------


def marcar_disputa(
    sessao: Session, acesso: Acesso, visita_id: int, *, motivo: str, agora: datetime
) -> MarcaDeDisputa | None:
    """Marca a visita "em disputa" (sem ``commit``); ``None`` se ela já estava.

    Raises:
        NaoEncontradoError: se a visita não for visível para o usuário.
    """
    return _marcar(sessao, acesso, visita_id, "marcar", motivo, agora)


def desmarcar_disputa(
    sessao: Session, acesso: Acesso, visita_id: int, *, motivo: str, agora: datetime
) -> MarcaDeDisputa | None:
    """Tira a visita da disputa (sem ``commit``); ``None`` se ela não estava.

    Raises:
        NaoEncontradoError: se a visita não for visível para o usuário.
    """
    return _marcar(sessao, acesso, visita_id, "desmarcar", motivo, agora)


def em_disputa(sessao: Session, acesso: Acesso, visita_id: int) -> bool:
    """Se a última marca da visita é "marcar".

    Raises:
        NaoEncontradoError: se a visita não for visível para o usuário.
    """
    return ultima_marca(sessao, acesso, visita_id) is not None


def ultima_marca(sessao: Session, acesso: Acesso, visita_id: int) -> MarcaDeDisputa | None:
    """A marca que pôs a visita em disputa, se ela está em disputa (``None`` se não está).

    Raises:
        NaoEncontradoError: se a visita não for visível para o usuário.
    """
    visita = obter_visita(sessao, acesso, visita_id)
    marca = sessao.scalars(
        select(MarcaDeDisputa)
        .where(
            MarcaDeDisputa.empresa_id == visita.empresa_id, MarcaDeDisputa.visita_id == visita.id
        )
        .order_by(MarcaDeDisputa.id.desc())
        .limit(1)
    ).first()
    return marca if marca is not None and marca.acao == "marcar" else None


def _marcar(
    sessao: Session,
    acesso: Acesso,
    visita_id: int,
    acao: AcaoDaDisputa,
    motivo: str,
    agora: datetime,
) -> MarcaDeDisputa | None:
    if em_disputa(sessao, acesso, visita_id) == (acao == "marcar"):
        return None
    marca = MarcaDeDisputa(
        empresa_id=acesso.empresa_id,
        visita_id=visita_id,
        acao=acao,
        motivo=motivo.strip()[:TAMANHO_DO_MOTIVO],
        usuario_id=acesso.usuario_id,
        momento=agora,
    )
    sessao.add(marca)
    sessao.flush()
    return marca


# --- A foto vencida -------------------------------------------------------------------------


def apagar_fotos_vencidas(
    sessao: Session, armazenamento: Armazenamento, *, agora: datetime, dias: int
) -> int:
    """Apaga as fotos das passagens vencidas que nada segura (sem ``commit``).

    Returns:
        Quantos arquivos saíram do armazenamento.
    """
    apagados = 0
    for passagem in sessao.scalars(_vencidas(agora - timedelta(days=dias))):
        for indice, foto in enumerate(passagem.como_veio["fotos"]):
            existia = armazenamento.apagar(passagem.caixa_id, foto["ref"])
            sessao.execute(
                insert(FotoApagada)
                .values(
                    empresa_id=passagem.empresa_id,
                    passagem_id=passagem.id,
                    indice=indice,
                    ref=foto["ref"],
                    existia=existia,
                    motivo="prazo_de_guarda",
                    apagada_em=agora,
                )
                .on_conflict_do_nothing(index_elements=["passagem_id", "indice"])
            )
            apagados += existia
    sessao.flush()
    return apagados


def _vencidas(limite: datetime) -> Select[PassagemRecebida]:
    """As passagens com foto, chegadas antes do limite, ainda não limpas e que nada segura."""
    visitas = select(Evento.visita_id).where(
        Evento.passagem_id == PassagemRecebida.id,
        Evento.empresa_id == PassagemRecebida.empresa_id,
    )
    excecao_aberta = exists().where(
        Excecao.empresa_id == PassagemRecebida.empresa_id,
        Excecao.visita_id.in_(visitas),
        Excecao.situacao == "aberta",
    )
    marca = aliased(MarcaDeDisputa)
    depois = aliased(MarcaDeDisputa)
    em_disputa = exists().where(
        marca.empresa_id == PassagemRecebida.empresa_id,
        marca.visita_id.in_(visitas),
        marca.acao == "marcar",
        ~exists().where(depois.visita_id == marca.visita_id, depois.id > marca.id),
    )
    ja_limpa = exists().where(FotoApagada.passagem_id == PassagemRecebida.id)
    return (
        select(PassagemRecebida)
        .where(
            PassagemRecebida.recebida_em < limite,
            func.jsonb_array_length(PassagemRecebida.como_veio["fotos"]) > 0,
            ~ja_limpa,
            ~excecao_aberta,
            ~em_disputa,
        )
        .order_by(PassagemRecebida.recebida_em)
        .limit(PASSAGENS_POR_VEZ)
    )

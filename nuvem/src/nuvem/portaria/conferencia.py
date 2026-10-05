"""Conferência da placa pelo porteiro (SDD D-42).

A tela mostra cada recorte de placa de uma passagem ao lado do que o leitor leu pela mesma
câmera, e o porteiro confirma ou digita a placa certa. A conferência é um registro novo, que o
banco não deixa alterar nem apagar; conferir de novo cria outro, e o último vale. Ela não muda
a visita nem o casamento: o "corrigir" da fila de exceções vem no mês 3.

Cada conferência é a placa certa de um recorte: vira rótulo para o treino quando o contrato do
cliente autorizar (SDD 4.6 e 8.3).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.placa import normalizar_placa
from nuvem.cadastro.acesso import Acesso
from nuvem.erros import NaoEncontradoError
from nuvem.portaria import servico as portaria
from nuvem.portaria.modelos import ConferenciaPlaca, PassagemRecebida


@dataclass(frozen=True)
class Recorte:
    """Um recorte de placa de uma passagem, com a leitura e a última conferência."""

    foto: int
    """A posição do recorte nas fotos da passagem."""
    placa_lida: str | None
    """O que o leitor leu pela câmera do recorte; vazio se não leu nada."""
    ultima: ConferenciaPlaca | None


def recortes(sessao: Session, acesso: Acesso, passagem_id: UUID) -> list[Recorte]:
    """Os recortes de placa de uma passagem que o usuário vê, na ordem das fotos.

    Raises:
        NaoEncontradoError: se a passagem não existir ou não for visível para este usuário.
    """
    passagem = portaria.obter_passagem(sessao, acesso, passagem_id)
    ultimas = {
        c.foto: c for c in ultimas_por_passagem(sessao, acesso, [passagem.id]).get(passagem.id, [])
    }
    return [
        Recorte(foto=indice, placa_lida=_lida_na_camera(passagem, foto), ultima=ultimas.get(indice))
        for indice, foto in enumerate(passagem.como_veio["fotos"])
        if foto["tipo"] == "placa"
    ]


def conferir(
    sessao: Session, acesso: Acesso, passagem_id: UUID, foto: int, placa: str, *, agora: datetime
) -> ConferenciaPlaca:
    """Grava a placa certa de um recorte, conferida por quem pede (sem ``commit``).

    Raises:
        NaoEncontradoError: se a passagem não for visível para o usuário ou se a foto não for um
            recorte de placa dela.
        PlacaInvalidaError: se a placa não estiver no formato antigo nem no Mercosul.
    """
    passagem = portaria.obter_passagem(sessao, acesso, passagem_id)
    fotos = passagem.como_veio["fotos"]
    if not 0 <= foto < len(fotos) or fotos[foto]["tipo"] != "placa":
        raise NaoEncontradoError(f"recorte {foto} da passagem {passagem_id}")
    conferida = ConferenciaPlaca(
        empresa_id=acesso.empresa_id,
        passagem_id=passagem.id,
        foto=foto,
        placa_lida=_lida_na_camera(passagem, fotos[foto]),
        placa=normalizar_placa(placa),
        usuario_id=acesso.usuario_id,
        momento=agora,
    )
    sessao.add(conferida)
    sessao.flush()
    return conferida


def ultimas_por_passagem(
    sessao: Session, acesso: Acesso, passagem_ids: Sequence[UUID]
) -> dict[UUID, list[ConferenciaPlaca]]:
    """A última conferência de cada recorte, por passagem (na ordem das fotos).

    As passagens sem conferência (ou de outra empresa) ficam de fora.
    """
    ultimas: dict[tuple[UUID, int], ConferenciaPlaca] = {}
    for feita in sessao.scalars(
        select(ConferenciaPlaca)
        .where(
            ConferenciaPlaca.empresa_id == acesso.empresa_id,
            ConferenciaPlaca.passagem_id.in_(passagem_ids),
        )
        .order_by(ConferenciaPlaca.id)
    ):
        ultimas[(feita.passagem_id, feita.foto)] = feita  # a mais nova fica
    por_passagem: dict[UUID, list[ConferenciaPlaca]] = {}
    for (passagem_id, _foto), feita in sorted(ultimas.items(), key=lambda item: item[0][1]):
        por_passagem.setdefault(passagem_id, []).append(feita)
    return por_passagem


def _lida_na_camera(passagem: PassagemRecebida, foto: dict[str, Any]) -> str | None:
    """A placa que o leitor leu pela câmera da foto (a de maior confiança, se houver mais)."""
    lidas = [p for p in passagem.como_veio["placas"] if p["camera_id"] == foto["camera_id"]]
    if not lidas:
        return None
    melhor: str = max(lidas, key=lambda p: p["confianca"])["placa"]
    return melhor

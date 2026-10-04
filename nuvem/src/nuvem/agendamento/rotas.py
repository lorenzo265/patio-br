"""Rotas de leitura dos agendamentos: qualquer usuário do cliente, nos sites dele.

Sem login, 401; a administração, 403 (ela tem rotas próprias, D-19); o que é de outra empresa ou
de um site que o usuário não vê, 404. Quem grava são os conectores (o link e a planilha).
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AwareDatetime, BaseModel, ConfigDict
from sqlalchemy.orm import Session

from nuvem.agendamento import servico
from nuvem.agendamento.formato import Tipo
from nuvem.agendamento.modelos import Origem, Situacao
from nuvem.banco import obter_sessao
from nuvem.cadastro.acesso import Acesso, obter_acesso

roteador = APIRouter(prefix="/api/agendamentos", tags=["agendamento"])

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaRequisicao = Annotated[Acesso, Depends(obter_acesso)]

MAIOR_PERIODO = timedelta(days=31)
"""O maior período que a lista aceita de uma vez."""


class AgendamentoPublico(BaseModel):
    """Um agendamento como a API o mostra."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    janela_inicio: datetime
    janela_fim: datetime
    tipo: Tipo
    placa_cavalo: str
    placas_reboques: list[str]
    motorista_nome: str | None
    motorista_celular: str | None
    whatsapp_autorizado_em: datetime | None
    toneladas: Decimal | None
    chave_nfe: str | None
    origem: Origem
    codigo_externo: str
    situacao: Situacao


@roteador.get("")
def listar(
    sessao: SessaoDaRequisicao,
    acesso: AcessoDaRequisicao,
    site_id: int,
    de: AwareDatetime,
    ate: AwareDatetime,
) -> list[AgendamentoPublico]:
    """Os agendamentos de um site cuja janela toca o período ``[de, ate)`` (até 31 dias)."""
    if not timedelta(0) < ate - de <= MAIOR_PERIODO:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "o período vai de 'de' até 'ate', com no máximo 31 dias",
        )
    agendamentos = servico.listar(sessao, acesso, site_id, de=de, ate=ate)
    return [AgendamentoPublico.model_validate(agendamento) for agendamento in agendamentos]


@roteador.get("/{agendamento_id}")
def obter(
    sessao: SessaoDaRequisicao, acesso: AcessoDaRequisicao, agendamento_id: int
) -> AgendamentoPublico:
    """Um agendamento de um site que o usuário vê (404 para qualquer outro)."""
    return AgendamentoPublico.model_validate(servico.obter(sessao, acesso, agendamento_id))

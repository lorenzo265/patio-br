"""Rotas dos agendamentos: ler (qualquer usuário do cliente) e subir a planilha (o gestor).

Sem login, 401; a administração, 403 (ela tem rotas próprias, D-19); o papel errado, 403; o que
é de outra empresa ou de um site que o usuário não vê, 404. Planilha que não serve, 422.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import AwareDatetime, BaseModel, ConfigDict
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from nuvem.agendamento import servico
from nuvem.agendamento.conectores import Recusado
from nuvem.agendamento.formato import Tipo
from nuvem.agendamento.modelos import Origem, Situacao
from nuvem.agendamento.planilha import (
    MAXIMO_DE_BYTES,
    Planilha,
    PlanilhaInvalidaError,
    importar_planilha,
)
from nuvem.banco import obter_sessao
from nuvem.cadastro.acesso import Acesso, exigir_papel, obter_acesso
from nuvem.relogio import agora

roteador = APIRouter(prefix="/api/agendamentos", tags=["agendamento"])

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaRequisicao = Annotated[Acesso, Depends(obter_acesso)]
AcessoDoGestor = Annotated[Acesso, Depends(exigir_papel("gestor"))]
Agora = Annotated[datetime, Depends(agora)]

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
    toneladas: Decimal | None
    chave_nfe: str | None
    origem: Origem
    codigo_externo: str
    situacao: Situacao


class RelatorioPublico(BaseModel):
    """O resultado da importação, como a API o mostra."""

    criados: int
    alterados: int
    iguais: int
    recusados: list[Recusado]


@roteador.post("/planilha")
async def subir_planilha(
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoGestor,
    momento: Agora,
    site_id: int,
    arquivo: UploadFile,
) -> RelatorioPublico:
    """Importa a planilha (CSV ou XLSX) num site do gestor; devolve o relatório por linha."""
    # Lê um pouco além do limite: o que passar é recusado, sem ler o resto.
    conteudo = await arquivo.read(MAXIMO_DE_BYTES + 1)
    planilha = Planilha(nome=arquivo.filename or "", conteudo=conteudo)
    return await run_in_threadpool(_importar, sessao, acesso, site_id, planilha, momento)


def _importar(
    sessao: Session, acesso: Acesso, site_id: int, planilha: Planilha, momento: datetime
) -> RelatorioPublico:
    try:
        relatorio = importar_planilha(sessao, acesso, site_id, planilha, agora=momento)
    except PlanilhaInvalidaError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from erro
    sessao.commit()
    return RelatorioPublico(
        criados=relatorio.criados,
        alterados=relatorio.alterados,
        iguais=relatorio.iguais,
        recusados=relatorio.recusados,
    )


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

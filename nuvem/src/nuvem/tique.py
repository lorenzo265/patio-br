"""O tique (D-51 e D-56): o trabalho do worker, um pouco de cada vez, quando uma tela se atualiza.

A Vercel não tem processo que fica rodando. Com ``PATIO_TIQUE``, as telas que se atualizam
sozinhas (``TELAS``) rodam antes uma volta do que o worker faria: o dia de demonstração, as
tarefas da fila (o casamento) e as mensagens; os alertas, no máximo uma vez por minuto em cada
instância (D-68). Um tique de cada vez (trava do PostgreSQL): o pedido que chega com outro tique
rodando segue sem esperar. Um erro no tique fica registrado, e a tela abre do mesmo jeito.

O "não veio" e a faxina das empresas de demonstração ficam para o cron diário (``nuvem.cron``).
"""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nuvem import tarefas_de_fundo
from nuvem.alertas import servico as alertas
from nuvem.armazenamento import Armazenamento
from nuvem.banco import obter_sessao
from nuvem.demonstracao import dia
from nuvem.mensagens import servico as mensagens
from nuvem.relogio import agora

_registro = logging.getLogger(__name__)

TELAS = ("/portaria", "/patio", "/mensagens", "/demonstracao", "/alertas")
"""As telas que se atualizam sozinhas (HTMX ou o refresh da página); o sino dos alertas está em
todas."""
TRAVA_DO_TIQUE = 7302
TAREFAS_POR_TIQUE = 20
"""O tique não segura a tela: no máximo estas tarefas da fila de cada vez."""


def avancar(
    sessao: Session,
    *,
    agora: datetime,
    armazenamento: Armazenamento,
    conferir_alertas: bool = False,
) -> bool:
    """Uma volta do trabalho do worker (com ``commit``); com ``conferir_alertas``, os alertas.

    Returns:
        ``False`` se outro tique estava rodando (e este não fez nada).
    """
    if not sessao.scalar(select(func.pg_try_advisory_xact_lock(TRAVA_DO_TIQUE))):
        return False
    dia.avancar(sessao, agora=agora, armazenamento=armazenamento)
    sessao.commit()
    tarefas_de_fundo.executar_pendentes(sessao, agora=agora, limite=TAREFAS_POR_TIQUE)
    mensagens.preparar(sessao, agora=agora)
    if conferir_alertas:
        alertas.conferir(sessao, agora=agora)
    sessao.commit()
    return True


def na_tela(
    request: Request,
    sessao: Annotated[Session, Depends(obter_sessao)],
    momento: Annotated[datetime, Depends(agora)],
) -> None:
    """Dependência da aplicação: o tique antes das telas que se atualizam, se ligado."""
    if not (
        request.app.state.tique and request.method == "GET" and request.url.path.startswith(TELAS)
    ):
        return
    ultima = request.app.state.alertas_conferidos_em
    conferir = ultima is None or momento - ultima >= tarefas_de_fundo.INTERVALO_DOS_ALERTAS
    try:
        armazenamento = request.app.state.armazenamento
        rodou = avancar(
            sessao, agora=momento, armazenamento=armazenamento, conferir_alertas=conferir
        )
        if rodou and conferir:
            request.app.state.alertas_conferidos_em = momento
    except Exception:
        sessao.rollback()
        _registro.exception("erro no tique; a tela abre do mesmo jeito")

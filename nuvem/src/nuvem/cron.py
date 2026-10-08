"""O cron diário (D-56): ``GET /api/cron/diaria``, chamado pela Vercel uma vez por dia.

Apaga as empresas dos links de demonstração vencidos ou revogados (D-54), confere o "não
veio" (SDD 5.2) e grava a âncora da prova dos dias que terminaram (D-69), o que o worker faria.
Só com o segredo do cron (o ``CRON_SECRET`` da Vercel, que ela manda em ``Authorization: Bearer
...``); sem o segredo configurado, a rota não existe. Rodar duas vezes não faz mal: o que já foi
feito não se faz de novo.
"""

import hmac
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from nuvem import tarefas_de_fundo
from nuvem.banco import obter_sessao
from nuvem.demonstracao import link as links
from nuvem.prova import servico as prova
from nuvem.relogio import agora

roteador = APIRouter(prefix="/api/cron", include_in_schema=False)


@roteador.get("/diaria")
def diaria(
    request: Request,
    sessao: Annotated[Session, Depends(obter_sessao)],
    momento: Annotated[datetime, Depends(agora)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    """Apaga as empresas de demonstração vencidas, confere o "não veio" e grava as âncoras."""
    segredo: str | None = request.app.state.segredo_do_cron
    if segredo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if authorization is None or not hmac.compare_digest(authorization, f"Bearer {segredo}"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    apagadas = links.apagar_vencidas(sessao, request.app.state.armazenamento, agora=momento)
    sessao.commit()
    nao_veio = tarefas_de_fundo.conferir_nao_veio(sessao, agora=momento)
    sessao.commit()
    ancoras = prova.gravar_ancoras(sessao, request.app.state.ancoras, agora=momento)
    sessao.commit()
    return {"empresas_apagadas": apagadas, "nao_veio": nao_veio, "ancoras": ancoras}

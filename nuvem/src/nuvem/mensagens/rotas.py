"""O webhook do WhatsApp (SDD 7.5, D-63): ``/api/whatsapp``.

- ``GET``: a Meta confere o webhook ao cadastrá-lo, com o código que escolhemos; a resposta é o
  desafio que ela mandou.
- ``POST``: o aviso da Meta (a situação das mensagens, as mensagens recebidas). Só passa com a
  assinatura do segredo do app (``X-Hub-Signature-256``); o aviso vira a tarefa "aviso do
  WhatsApp", e o worker faz o resto. O mesmo aviso duas vezes vira uma tarefa só.

Sem o WhatsApp configurado, as duas respondem 404. O cookie não decide quem pede, então a rota
fica fora do código anti-CSRF (D-55).
"""

import hashlib
import hmac
import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from nuvem import tarefas_de_fundo
from nuvem.banco import obter_sessao
from nuvem.mensagens import whatsapp
from nuvem.relogio import agora

roteador = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


async def corpo_do_pedido(request: Request) -> bytes:
    """O corpo cru, como a Meta assinou (a assinatura é dos bytes, não do JSON lido)."""
    return await request.body()


@roteador.get("", response_class=PlainTextResponse)
def conferir_o_webhook(
    request: Request,
    modo: Annotated[str | None, Query(alias="hub.mode")] = None,
    codigo: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    desafio: Annotated[str, Query(alias="hub.challenge")] = "",
) -> Response:
    """A conferência da Meta: devolve o desafio se o código for o nosso."""
    esperado: str | None = request.app.state.whatsapp_codigo_do_webhook
    if esperado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if modo != "subscribe" or codigo is None or not hmac.compare_digest(codigo, esperado):
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    return PlainTextResponse(desafio)


@roteador.post("")
def receber_o_aviso(
    request: Request,
    sessao: Annotated[Session, Depends(obter_sessao)],
    momento: Annotated[datetime, Depends(agora)],
    corpo: Annotated[bytes, Depends(corpo_do_pedido)],
) -> Response:
    """Guarda o aviso assinado numa tarefa e responde logo (a Meta repete o que demora)."""
    segredo: str | None = request.app.state.whatsapp_segredo_do_app
    if segredo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if not whatsapp.assinatura_confere(segredo, corpo, request.headers.get("x-hub-signature-256")):
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    try:
        aviso = json.loads(corpo)
    except ValueError:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    if not isinstance(aviso, dict):
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    tarefas_de_fundo.enfileirar(
        sessao,
        "aviso_do_whatsapp",
        {"aviso": aviso},
        chave=hashlib.sha256(corpo).hexdigest(),
        agora=momento,
    )
    sessao.commit()
    return Response(status_code=status.HTTP_200_OK)

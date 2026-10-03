"""Rotas da borda para passagens e fotos (SDD 3.2, D-22).

As respostas são as que a fila da caixa precisa entender: 201 (nova), 200 (já tinha chegado),
401 (chave), 403 (outro site), 409 (id de outra caixa) e 422 (campo que não confere).
"""

from datetime import datetime
from typing import Annotated
from urllib.parse import urljoin
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from contratos.passagem import Passagem
from nuvem import armazenamento as fotos
from nuvem.armazenamento import Armazenamento, ArmazenamentoLocal, obter_armazenamento
from nuvem.banco import obter_sessao
from nuvem.frota.acesso import obter_caixa
from nuvem.frota.servico import AcessoDaCaixa
from nuvem.portaria import servico
from nuvem.relogio import agora

roteador_borda = APIRouter(prefix="/api/borda", tags=["borda"])

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
Agora = Annotated[datetime, Depends(agora)]
CaixaDaRequisicao = Annotated[AcessoDaCaixa, Depends(obter_caixa)]
ArmazenamentoDaAplicacao = Annotated[Armazenamento, Depends(obter_armazenamento)]


class PassagemAceita(BaseModel):
    """A resposta a uma passagem aceita (nova ou repetida)."""

    id: UUID


class PedidoDeEndereco(BaseModel):
    """O ``ref`` da foto que a caixa vai enviar (o mesmo que irá na passagem)."""

    model_config = ConfigDict(extra="forbid")

    ref: str

    @field_validator("ref")
    @classmethod
    def _ref_na_regra(cls, ref: str) -> str:
        fotos.validar_ref(ref)
        return ref


class EnderecoDeEnvio(BaseModel):
    """Para onde enviar a foto (com ``PUT``), até quando."""

    ref: str
    endereco: str
    expira_em: datetime


@roteador_borda.post(
    "/passagens",
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_200_OK: {"description": "A passagem já tinha chegado."}},
)
def receber_passagem(
    sessao: SessaoDaRequisicao,
    momento: Agora,
    caixa: CaixaDaRequisicao,
    passagem: Passagem,
    resposta: Response,
) -> PassagemAceita:
    """Recebe uma passagem da caixa: 201 se nova, 200 se repetida."""
    try:
        nova = servico.receber_passagem(sessao, caixa, passagem, agora=momento)
    except servico.PassagemDeOutroSiteError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="a passagem é de outro site ou de outra caixa"
        ) from None
    except servico.IdDeOutraCaixaError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="este id de passagem já é de outra caixa"
        ) from None
    except servico.PassagemInvalidaError as erro:
        # O mesmo formato dos erros de validação do FastAPI: a caixa lê um formato só.
        detalhe = [{"loc": ["body", *erro.loc], "msg": erro.mensagem, "type": "nao_confere"}]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detalhe) from None
    sessao.commit()
    if not nova:
        resposta.status_code = status.HTTP_200_OK
    return PassagemAceita(id=passagem.id)


@roteador_borda.post("/fotos/endereco")
def endereco_de_foto(
    request: Request,
    momento: Agora,
    caixa: CaixaDaRequisicao,
    armazenamento: ArmazenamentoDaAplicacao,
    pedido: PedidoDeEndereco,
) -> EnderecoDeEnvio:
    """Devolve o endereço temporário para a caixa enviar uma foto."""
    endereco = armazenamento.endereco_de_envio(caixa.caixa_id, pedido.ref, agora=momento)
    return EnderecoDeEnvio(
        ref=pedido.ref,
        # O armazenamento local devolve um caminho desta API; o S3, um endereço completo.
        endereco=urljoin(str(request.base_url), endereco),
        expira_em=momento + fotos.VALIDADE_DO_ENDERECO,
    )


@roteador_borda.put(
    "/fotos/envio/{codigo}",
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_200_OK: {"description": "A mesma foto já tinha chegado."}},
)
async def receber_foto(
    request: Request, codigo: str, momento: Agora, armazenamento: ArmazenamentoDaAplicacao
) -> Response:
    """Recebe a foto no armazenamento local (o endereço já autoriza; não leva a chave)."""
    if not isinstance(armazenamento, ArmazenamentoLocal):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    conteudo = await _corpo_com_limite(request, fotos.TAMANHO_MAXIMO_DA_FOTO)
    try:
        nova = await run_in_threadpool(armazenamento.receber, codigo, conteudo, agora=momento)
    except fotos.EnderecoRecusadoError as erro:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(erro)) from None
    except fotos.FotoGrandeDemaisError as erro:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(erro)) from None
    except fotos.FotoNaoJpegError as erro:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(erro)) from None
    except fotos.FotoDiferenteError as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(erro)) from None
    return Response(status_code=status.HTTP_201_CREATED if nova else status.HTTP_200_OK)


async def _corpo_com_limite(request: Request, limite: int) -> bytes:
    # Lê aos pedaços e para logo depois do limite: um envio enorme não ocupa a memória toda.
    partes: list[bytes] = []
    tamanho = 0
    async for parte in request.stream():
        tamanho += len(parte)
        partes.append(parte)
        if tamanho > limite:
            break
    return b"".join(partes)

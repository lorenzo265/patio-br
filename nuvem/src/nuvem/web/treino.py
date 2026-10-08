"""A base de treino na administração (SDD 6.2, D-71).

- ``/administracao/treino``: as empresas, cada uma com a cláusula do contrato (registrar e
  revogar), e os rótulos a revisar, com o recorte na tela.
- ``/administracao/treino/rotulos/<rótulo>``: aceitar, corrigir (com a placa certa) ou descartar.
- ``/administracao/treino/rotulos/<rótulo>/recorte``: a cópia do recorte (não fica guardada no
  navegador).
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro.acesso import AcessoAdmin, obter_acesso_admin
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.relogio import agora
from nuvem.treino import servico as treino
from nuvem.treino.servico import AcaoDaRevisao
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/administracao/treino", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaAdministracao = Annotated[AcessoAdmin, Depends(obter_acesso_admin)]
Agora = Annotated[datetime, Depends(agora)]

DA_TELA = "/administracao/treino"


@roteador.get("")
def tela_do_treino(
    request: Request, sessao: SessaoDaRequisicao, administracao: AcessoDaAdministracao
) -> HTMLResponse:
    """As cláusulas e os rótulos a revisar."""
    return _tela(request, sessao, administracao)


@roteador.post("/autorizacoes")
def registrar_clausula(
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    empresa: Annotated[int, Form()],
    clausula_em: Annotated[date, Form()],
) -> RedirectResponse:
    """Registra a data da cláusula do contrato de uma empresa."""
    treino.autorizar(sessao, administracao, empresa, clausula_em=clausula_em, agora=momento)
    sessao.commit()
    return RedirectResponse(DA_TELA, status.HTTP_303_SEE_OTHER)


@roteador.post("/autorizacoes/{empresa_id}/revogar")
def revogar_clausula(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    empresa_id: int,
) -> RedirectResponse:
    """Revoga a autorização: os rótulos e os recortes da empresa se apagam."""
    treino.revogar(
        sessao, administracao, empresa_id, request.app.state.base_de_treino, agora=momento
    )
    sessao.commit()
    return RedirectResponse(DA_TELA, status.HTTP_303_SEE_OTHER)


@roteador.post("/rotulos/{rotulo_id}", response_model=None)
def revisar(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    rotulo_id: int,
    acao: Annotated[AcaoDaRevisao, Form()],
    placa: Annotated[str, Form(max_length=20)] = "",
) -> HTMLResponse | RedirectResponse:
    """Aceita, corrige ou descarta um rótulo e volta à tela."""
    try:
        treino.revisar(sessao, administracao, rotulo_id, acao, placa=placa, agora=momento)
    except DadoInvalidoError as erro:
        sessao.rollback()
        return _tela(
            request, sessao, administracao, erro=str(erro), codigo=status.HTTP_400_BAD_REQUEST
        )
    sessao.commit()
    return RedirectResponse(DA_TELA, status.HTTP_303_SEE_OTHER)


@roteador.get("/rotulos/{rotulo_id}/recorte")
def recorte(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    rotulo_id: int,
) -> Response:
    """A cópia do recorte de um rótulo."""
    rotulo = treino.obter_rotulo(sessao, administracao, rotulo_id)
    conteudo = request.app.state.base_de_treino.ler(rotulo.recorte) if rotulo.recorte else None
    if conteudo is None:
        raise NaoEncontradoError(f"recorte do rótulo {rotulo_id}")
    return Response(conteudo, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


def _tela(
    request: Request,
    sessao: Session,
    administracao: AcessoAdmin,
    *,
    erro: str | None = None,
    codigo: int = status.HTTP_200_OK,
) -> HTMLResponse:
    empresas = [
        {
            "id": empresa.id,
            "nome": empresa.nome,
            "clausula": f"{autorizacao.clausula_em:%d/%m/%Y}" if autorizacao else None,
        }
        for empresa, autorizacao in treino.autorizacoes(sessao, administracao)
    ]
    contexto = {
        "empresas": empresas,
        "pendentes": treino.pendentes(sessao, administracao),
        "contagem": treino.contagem(sessao, administracao),
        "erro": erro,
    }
    return tela(request, "administracao_treino.html", contexto, codigo)

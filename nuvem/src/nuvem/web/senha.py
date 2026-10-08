"""A pessoa cria a própria senha pelo link da administração (SDD 8.2, D-75).

- ``GET /senha/{codigo}``: o formulário (a senha duas vezes e, para o porteiro, o PIN).
- ``POST /senha/{codigo}``: cria a senha; o link deixa de valer e as sessões da pessoa se fecham.

Quem decide quem pede é o código do endereço, e não o cookie: a rota fica de fora do código
anti-CSRF (como o link da transportadora), e o código sai do registro de acesso (D-34). A página
não guarda nada no navegador nem manda o endereço a outro site.
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import cliente
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.relogio import agora
from nuvem.senhas import Senhas, obter_senhas
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/senha", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
SenhasDaAplicacao = Annotated[Senhas, Depends(obter_senhas)]
Agora = Annotated[datetime, Depends(agora)]

CABECALHOS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
NAO_VALE = (
    "Este link não vale mais: ele já foi usado, venceu ou foi trocado. Peça outro a quem"
    " cadastrou você."
)


@roteador.get("/{codigo}")
def formulario(
    request: Request, sessao: SessaoDaRequisicao, momento: Agora, codigo: str
) -> HTMLResponse:
    """O formulário da senha, ou o aviso de que o link não vale."""
    link = cliente.link_de_senha(sessao, codigo, agora=momento)
    if link is None:
        return _tela(request, {"nao_vale": NAO_VALE}, status.HTTP_404_NOT_FOUND)
    pessoa = cliente.pessoa_do_link(sessao, link)
    return _tela(request, {"pessoa": pessoa, "codigo": codigo})


@roteador.post("/{codigo}")
def criar(
    request: Request,
    sessao: SessaoDaRequisicao,
    senhas: SenhasDaAplicacao,
    momento: Agora,
    codigo: str,
    senha: Annotated[str, Form(max_length=200)],
    confirmacao: Annotated[str, Form(max_length=200)],
    pin: Annotated[str, Form(max_length=20)] = "",
) -> HTMLResponse:
    """Cria a senha (e o PIN do porteiro)."""
    link = cliente.link_de_senha(sessao, codigo, agora=momento)
    if link is None:
        return _tela(request, {"nao_vale": NAO_VALE}, status.HTTP_404_NOT_FOUND)
    pessoa = cliente.pessoa_do_link(sessao, link)
    try:
        if senha != confirmacao:
            raise DadoInvalidoError("as duas senhas não são iguais")
        cliente.criar_senha_pelo_link(
            sessao, senhas, codigo, senha=senha, pin=pin or None, agora=momento
        )
    except DadoInvalidoError as erro:
        sessao.rollback()
        contexto = {"pessoa": pessoa, "codigo": codigo, "erro": str(erro)}
        return _tela(request, contexto, status.HTTP_400_BAD_REQUEST)
    except NaoEncontradoError:
        return _tela(request, {"nao_vale": NAO_VALE}, status.HTTP_404_NOT_FOUND)
    sessao.commit()
    return _tela(request, {"pronto": True})


def _tela(
    request: Request, contexto: dict[str, Any], codigo: int = status.HTTP_200_OK
) -> HTMLResponse:
    resposta = tela(request, "senha.html", contexto, codigo)
    resposta.headers.update(CABECALHOS)
    return resposta

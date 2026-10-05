"""Telas de entrar, sair, início e troca de porteiro (SDD 8.2).

O login abre uma sessão no banco e põe o código dela num cookie ``HttpOnly`` e
``SameSite=Lax`` (``Secure`` fora do ambiente local). O ``SameSite=Lax`` também impede que
outro site faça o navegador postar formulários aqui com o cookie. O login, que não usa o
cookie, recusa o envio que o navegador marca como vindo de outro site (``Sec-Fetch-Site``).
"""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import login, servico
from nuvem.cadastro.acesso import COOKIE_DA_SESSAO, Acesso, QuemPede, exigir_papel
from nuvem.cadastro.modelos import Administrador, Usuario
from nuvem.relogio import agora
from nuvem.senhas import Senhas, obter_senhas

roteador = APIRouter(include_in_schema=False)
telas = Jinja2Templates(directory=Path(__file__).parent / "telas")

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
SenhasDaAplicacao = Annotated[Senhas, Depends(obter_senhas)]
Agora = Annotated[datetime, Depends(agora)]
AcessoDaPortaria = Annotated[Acesso, Depends(exigir_papel("porteiro", "gestor"))]

ESPERE = f"Muitas tentativas. Espere {login.JANELA_DAS_TENTATIVAS.seconds // 60} minutos."


def tela(
    request: Request, nome: str, contexto: dict[str, Any], codigo: int = status.HTTP_200_OK
) -> HTMLResponse:
    """Desenha uma tela do painel."""
    return telas.TemplateResponse(request, nome, contexto, status_code=codigo)


@roteador.get("/entrar")
def tela_de_entrar(request: Request) -> HTMLResponse:
    """O formulário de e-mail e senha."""
    return tela(request, "entrar.html", {"email": "", "erro": None})


@roteador.post("/entrar")
def entrar(
    request: Request,
    sessao: SessaoDaRequisicao,
    senhas: SenhasDaAplicacao,
    momento: Agora,
    email: Annotated[str, Form()],
    senha: Annotated[str, Form()],
) -> Response:
    """Confere e-mail e senha; se baterem, abre a sessão e leva ao início."""
    if request.headers.get("sec-fetch-site") == "cross-site":
        # Outro site faria o tablet entrar numa conta dele, e a portaria trabalharia nela.
        contexto = {"email": "", "erro": "Entre por esta tela."}
        return tela(request, "entrar.html", contexto, status.HTTP_403_FORBIDDEN)
    try:
        codigo = login.entrar(sessao, senhas, email=email, senha=senha, agora=momento)
    except login.MuitasTentativasError:
        contexto = {"email": email, "erro": f"{ESPERE} Depois, tente de novo."}
        return tela(request, "entrar.html", contexto, status.HTTP_429_TOO_MANY_REQUESTS)
    except login.LoginRecusadoError:
        sessao.commit()  # o erro fica gravado, para o limite de tentativas
        contexto = {"email": email, "erro": "E-mail ou senha incorretos."}
        return tela(request, "entrar.html", contexto, status.HTTP_401_UNAUTHORIZED)
    sessao.commit()
    return _ir_ao_inicio_com_a_sessao(request, codigo)


@roteador.post("/sair")
def sair(request: Request, sessao: SessaoDaRequisicao) -> Response:
    """Fecha a sessão no servidor e apaga o cookie."""
    codigo = request.cookies.get(COOKIE_DA_SESSAO)
    if codigo:
        login.sair(sessao, codigo)
        sessao.commit()
    resposta = RedirectResponse("/entrar", status_code=status.HTTP_303_SEE_OTHER)
    resposta.delete_cookie(
        COOKIE_DA_SESSAO, httponly=True, samesite="lax", secure=request.app.state.cookie_seguro
    )
    return resposta


@roteador.get("/")
def inicio(request: Request, sessao: SessaoDaRequisicao, quem: QuemPede) -> HTMLResponse:
    """A tela inicial de quem entrou."""
    if isinstance(quem, Acesso):
        usuario = sessao.get(Usuario, quem.usuario_id)
        contexto = {
            "nome": usuario.nome if usuario else "",
            "administracao": False,
            "papel": quem.papel,
            "sites": [site.nome for site in servico.listar_sites(sessao, quem)],
            "pode_trocar_porteiro": quem.papel in ("porteiro", "gestor"),
            "pode_agendar": quem.papel == "gestor",
            "ve_o_patio": quem.papel in ("patio", "gestor"),
            "ve_a_demonstracao": quem.papel == "gestor" and request.app.state.tem_demonstracao,
        }
    else:
        administrador = sessao.get(Administrador, quem.administrador_id)
        contexto = {"nome": administrador.nome if administrador else "", "administracao": True}
    return tela(request, "inicio.html", contexto)


@roteador.get("/trocar-porteiro")
def tela_de_trocar_porteiro(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDaPortaria
) -> HTMLResponse:
    """Os porteiros que podem assumir o tablet, e o campo do PIN."""
    return _tela_da_troca(request, sessao, acesso)


@roteador.post("/trocar-porteiro")
def trocar_porteiro(
    request: Request,
    sessao: SessaoDaRequisicao,
    senhas: SenhasDaAplicacao,
    momento: Agora,
    acesso: AcessoDaPortaria,
    porteiro_id: Annotated[int, Form()],
    pin: Annotated[str, Form()],
) -> Response:
    """Passa a sessão para o porteiro escolhido, se o PIN dele conferir."""
    codigo = request.cookies.get(COOKIE_DA_SESSAO, "")
    try:
        novo = login.trocar_porteiro(
            sessao, senhas, codigo=codigo, porteiro_id=porteiro_id, pin=pin, agora=momento
        )
    except login.MuitasTentativasError:
        erro = f"{ESPERE} Depois, tente de novo com este PIN."
        return _tela_da_troca(request, sessao, acesso, erro, status.HTTP_429_TOO_MANY_REQUESTS)
    except login.LoginRecusadoError:
        sessao.commit()  # o erro fica gravado, para o limite de tentativas
        erro = "PIN incorreto."
        return _tela_da_troca(request, sessao, acesso, erro, status.HTTP_401_UNAUTHORIZED)
    sessao.commit()
    return _ir_ao_inicio_com_a_sessao(request, novo)


def _tela_da_troca(
    request: Request,
    sessao: Session,
    acesso: Acesso,
    erro: str | None = None,
    codigo: int = status.HTTP_200_OK,
) -> HTMLResponse:
    porteiros = login.porteiros_da_troca(sessao, acesso.usuario_id)
    return tela(request, "trocar_porteiro.html", {"porteiros": porteiros, "erro": erro}, codigo)


def _ir_ao_inicio_com_a_sessao(request: Request, codigo: str) -> Response:
    resposta = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    resposta.set_cookie(
        COOKIE_DA_SESSAO,
        codigo,
        max_age=int(login.VALIDADE_DA_SESSAO.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=request.app.state.cookie_seguro,
    )
    return resposta

"""Telas de entrar, sair, início e troca de porteiro (SDD 8.2).

O login abre uma sessão no banco e põe o código dela num cookie ``HttpOnly`` e
``SameSite=Lax`` (``Secure`` fora do ambiente local). O ``SameSite=Lax`` também impede que
outro site faça o navegador postar formulários aqui com o cookie. O login, que não usa o
cookie, recusa o envio que o navegador marca como vindo de outro site (``Sec-Fetch-Site``).
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import login, servico
from nuvem.cadastro.acesso import (
    COOKIE_DA_SESSAO,
    Acesso,
    AcessoAdmin,
    QuemPede,
    exigir_papel,
)
from nuvem.cadastro.duas_etapas import VALIDADE_DA_SESSAO_PELA_METADE
from nuvem.cadastro.modelos import Administrador, Empresa, Falta, Usuario
from nuvem.relogio import agora
from nuvem.senhas import Senhas, obter_senhas
from nuvem.web import csrf

roteador = APIRouter(include_in_schema=False)
telas = Jinja2Templates(directory=Path(__file__).parent / "telas")

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
SenhasDaAplicacao = Annotated[Senhas, Depends(obter_senhas)]
Agora = Annotated[datetime, Depends(agora)]
AcessoDaPortaria = Annotated[Acesso, Depends(exigir_papel("porteiro", "gestor"))]

ESPERE = f"Muitas tentativas. Espere {login.JANELA_DAS_TENTATIVAS.seconds // 60} minutos."
TELA_DO_QUE_FALTA: dict[Falta, str] = {"codigo": "/entrar/codigo", "ligar": "/entrar/ligar"}
"""Para onde vai a sessão pela metade (D-60)."""


def tela(
    request: Request, nome: str, contexto: dict[str, Any], codigo: int = status.HTTP_200_OK
) -> HTMLResponse:
    """Desenha uma tela do painel.

    Nos ambientes da demonstração, a tela de quem é do cliente ganha a faixa que troca de papel
    (D-54): ``papel_na_demonstracao`` é o papel de agora. A tela de quem entrou ganha o sino dos
    alertas (D-68), e com ele o HTMX: ``sino`` é o endereço que o sino busca.
    """
    quem = getattr(request.state, "quem", None)
    if isinstance(quem, Acesso):
        contexto = {"sino": "/alertas/sino", **contexto}
    elif isinstance(quem, AcessoAdmin):
        contexto = {"sino": "/administracao/alertas/sino", **contexto}
    if request.app.state.tem_demonstracao and isinstance(quem, Acesso):
        contexto = {"papel_na_demonstracao": quem.papel, **contexto}
    codigo_csrf = csrf.codigo_do_pedido(request)
    if codigo_csrf is not None:
        contexto = {"csrf": codigo_csrf, **contexto}
    return telas.TemplateResponse(request, nome, contexto, status_code=codigo)


def endereco_de(request: Request) -> str | None:
    """O endereço IP de quem pede: do cabeçalho de confiança, se configurado (D-55)."""
    cabecalho = request.app.state.cabecalho_do_ip
    if cabecalho and request.headers.get(cabecalho):
        return request.headers[cabecalho].split(",")[0].strip()
    return request.client.host if request.client else None


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
        codigo = login.entrar(
            sessao,
            senhas,
            email=email,
            senha=senha,
            agora=momento,
            endereco=endereco_de(request),
            exigir_duas_etapas=request.app.state.exige_duas_etapas,
        )
    except login.MuitasTentativasError:
        contexto = {"email": email, "erro": f"{ESPERE} Depois, tente de novo."}
        return tela(request, "entrar.html", contexto, status.HTTP_429_TOO_MANY_REQUESTS)
    except login.LoginRecusadoError:
        sessao.commit()  # o erro fica gravado, para o limite de tentativas
        contexto = {"email": email, "erro": "E-mail ou senha incorretos."}
        return tela(request, "entrar.html", contexto, status.HTTP_401_UNAUTHORIZED)
    sessao.commit()
    metade = login.sessao_pela_metade(sessao, codigo, momento)
    if metade is not None:
        # Falta a verificação em duas etapas (D-60): a sessão só serve para a tela dela.
        return ir_com_a_sessao(
            request, codigo, TELA_DO_QUE_FALTA[metade.falta], VALIDADE_DA_SESSAO_PELA_METADE
        )
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
        empresa = sessao.get(Empresa, quem.empresa_id)
        contexto = {
            "nome": usuario.nome if usuario else "",
            "empresa": empresa.nome if empresa else "",
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
        contexto = {
            "nome": administrador.nome if administrador else "",
            "administracao": True,
            "ve_os_links_de_demonstracao": request.app.state.tem_demonstracao,
        }
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
    return ir_com_a_sessao(request, codigo, "/")


def ir_com_a_sessao(
    request: Request, codigo: str, destino: str, validade: timedelta = login.VALIDADE_DA_SESSAO
) -> Response:
    """Leva a ``destino`` com o cookie da sessão aberta (o código só vai no cookie)."""
    resposta = RedirectResponse(destino, status_code=status.HTTP_303_SEE_OTHER)
    por_o_cookie(request, resposta, codigo, validade)
    return resposta


def por_o_cookie(
    request: Request,
    resposta: Response,
    codigo: str,
    validade: timedelta = login.VALIDADE_DA_SESSAO,
) -> None:
    """Põe na resposta o cookie da sessão aberta (``HttpOnly``, ``SameSite=Lax``)."""
    resposta.set_cookie(
        COOKIE_DA_SESSAO,
        codigo,
        max_age=int(validade.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=request.app.state.cookie_seguro,
    )

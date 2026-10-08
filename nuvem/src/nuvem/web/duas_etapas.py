"""As telas da verificação em duas etapas (SDD 8.2, D-60).

Depois da senha certa, a sessão pela metade leva a uma destas telas:
- **o código** (``/entrar/codigo``): o código do app, ou um código de recuperação;
- **ligar** (``/entrar/ligar``): na primeira vez, o QR para o app e o segredo em texto; o primeiro
  código confirma e mostra os códigos de recuperação, uma vez só.

Sem uma sessão pela metade que sirva, as telas levam ao login. As páginas com o segredo ou os
códigos de recuperação não vão para o cache.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, Response
from markupsafe import Markup
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import duas_etapas, login
from nuvem.cadastro.acesso import COOKIE_DA_SESSAO
from nuvem.cadastro.modelos import Falta
from nuvem.cifra import Cifra, obter_cifra
from nuvem.relogio import agora
from nuvem.senhas import Senhas, obter_senhas
from nuvem.web import csrf
from nuvem.web.rotas import ESPERE, TELA_DO_QUE_FALTA, ir_com_a_sessao, por_o_cookie, tela

roteador = APIRouter(include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
SenhasDaAplicacao = Annotated[Senhas, Depends(obter_senhas)]
CifraDaAplicacao = Annotated[Cifra, Depends(obter_cifra)]
Agora = Annotated[datetime, Depends(agora)]

SEM_CACHE = {"Cache-Control": "no-store"}


@roteador.get("/entrar/codigo")
def tela_do_codigo(request: Request, sessao: SessaoDaRequisicao, momento: Agora) -> Response:
    """Pede o código do app (ou um código de recuperação)."""
    desvio = _desvio(request, sessao, momento, "codigo")
    if desvio is not None:
        return desvio
    return tela(request, "entrar_codigo.html", {"erro": None})


@roteador.post("/entrar/codigo")
def confirmar_codigo(
    request: Request,
    sessao: SessaoDaRequisicao,
    senhas: SenhasDaAplicacao,
    cifra: CifraDaAplicacao,
    momento: Agora,
    codigo: Annotated[str, Form()],
) -> Response:
    """Confere o código; se bater, abre a sessão de sempre e leva ao início."""
    try:
        aberta = login.confirmar_codigo(
            sessao,
            senhas,
            cifra,
            codigo_da_sessao=request.cookies.get(COOKIE_DA_SESSAO, ""),
            digitado=codigo,
            agora=momento,
        )
    except login.MuitasTentativasError:
        contexto = {"erro": f"{ESPERE} Depois, tente de novo."}
        return tela(request, "entrar_codigo.html", contexto, status.HTTP_429_TOO_MANY_REQUESTS)
    except login.LoginRecusadoError:
        sessao.commit()  # o erro fica gravado, para o limite de tentativas
        contexto = {"erro": "Código incorreto."}
        return tela(request, "entrar_codigo.html", contexto, status.HTTP_401_UNAUTHORIZED)
    sessao.commit()
    return ir_com_a_sessao(request, aberta, "/")


@roteador.get("/entrar/ligar")
def tela_de_ligar(
    request: Request, sessao: SessaoDaRequisicao, cifra: CifraDaAplicacao, momento: Agora
) -> Response:
    """O QR para o app e o segredo em texto, para quem liga a verificação pela primeira vez."""
    desvio = _desvio(request, sessao, momento, "ligar")
    if desvio is not None:
        return desvio
    return _tela_de_ligar(request, sessao, cifra, momento, None, status.HTTP_200_OK)


@roteador.post("/entrar/ligar")
def ligar(
    request: Request,
    sessao: SessaoDaRequisicao,
    senhas: SenhasDaAplicacao,
    cifra: CifraDaAplicacao,
    momento: Agora,
    codigo: Annotated[str, Form()],
) -> Response:
    """Liga a verificação com o primeiro código do app e mostra os códigos de recuperação."""
    try:
        ligada = login.ligar(
            sessao,
            senhas,
            cifra,
            codigo_da_sessao=request.cookies.get(COOKIE_DA_SESSAO, ""),
            digitado=codigo,
            agora=momento,
        )
    except login.MuitasTentativasError:
        erro = f"{ESPERE} Depois, tente de novo."
        return _tela_de_ligar(
            request, sessao, cifra, momento, erro, status.HTTP_429_TOO_MANY_REQUESTS
        )
    except login.LoginRecusadoError:
        sessao.commit()  # o erro fica gravado, para o limite de tentativas
        erro = "Código incorreto. Confira se o relógio do celular está certo."
        return _tela_de_ligar(request, sessao, cifra, momento, erro, status.HTTP_401_UNAUTHORIZED)
    sessao.commit()
    # A tela já é da sessão nova: o código anti-CSRF sai dela, e não do cookie que chegou.
    contexto = {
        "codigos": ligada.recuperacao,
        "csrf": csrf.codigo(request.app.state.segredo_csrf, ligada.codigo_da_sessao),
    }
    resposta = tela(request, "entrar_recuperacao.html", contexto)
    resposta.headers.update(SEM_CACHE)
    por_o_cookie(request, resposta, ligada.codigo_da_sessao)
    return resposta


def _desvio(request: Request, sessao: Session, momento: datetime, falta: Falta) -> Response | None:
    # Sem a sessão pela metade, volta ao login; com a de outra tela, vai para ela.
    metade = login.sessao_pela_metade(sessao, request.cookies.get(COOKIE_DA_SESSAO, ""), momento)
    if metade is None:
        return RedirectResponse("/entrar", status_code=status.HTTP_303_SEE_OTHER)
    if metade.falta != falta:
        return RedirectResponse(
            TELA_DO_QUE_FALTA[metade.falta], status_code=status.HTTP_303_SEE_OTHER
        )
    return None


def _tela_de_ligar(
    request: Request,
    sessao: Session,
    cifra: Cifra,
    momento: datetime,
    erro: str | None,
    codigo: int,
) -> Response:
    ligacao = login.preparar_ligacao(
        sessao, cifra, codigo_da_sessao=request.cookies.get(COOKIE_DA_SESSAO, ""), agora=momento
    )
    sessao.commit()
    endereco = duas_etapas.endereco_do_app(ligacao.segredo, ligacao.email)
    # Em grupos de 4, para digitar no app sem se perder.
    segredo = " ".join(ligacao.segredo[i : i + 4] for i in range(0, len(ligacao.segredo), 4))
    # O SVG sai do segno, a partir do endereço que montamos: pode ir direto na tela.
    contexto = {"qr": Markup(duas_etapas.qr_em_svg(endereco)), "segredo": segredo, "erro": erro}
    resposta = tela(request, "entrar_ligar.html", contexto, codigo)
    resposta.headers.update(SEM_CACHE)
    return resposta

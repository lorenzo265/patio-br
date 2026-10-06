"""As telas da demonstração: o dia (T45, D-49) e o link por empresa (T48, D-52 e D-54).

Só existem nos ambientes ``local`` e ``demonstracao`` (fora deles, 404).

- **O dia:** só o gestor começa e acompanha; a tela se atualiza sozinha e leva às telas onde o
  dia acontece: portaria, pátio, mensagens e painel.
- **O link:** a página (``GET``) só mostra para quem é e o botão "Entrar"; o botão (``POST``)
  cria a empresa, na primeira vez, e entra como gestor. O pré-visualizador do WhatsApp abre a
  página e não cria nada.
- **A faixa de papel:** quem é do cliente troca de papel sem senha (gestor, porteiro, líder de
  pátio); o motorista é a tela das mensagens.
- **A administração** gera e revoga os links; o endereço aparece uma vez só.
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import (
    COOKIE_DA_SESSAO,
    Acesso,
    AcessoAdmin,
    exigir_papel,
    obter_acesso,
    obter_acesso_admin,
)
from nuvem.cadastro.modelos import FUSO_PADRAO
from nuvem.cifra import Cifra, obter_cifra
from nuvem.demonstracao import dia as demonstracao
from nuvem.demonstracao import link as links
from nuvem.demonstracao.dia import DiaJaComecouError, SiteSemCaixaError
from nuvem.demonstracao.modelos import LinkDemonstracao
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.relogio import agora
from nuvem.senhas import Senhas, obter_senhas
from nuvem.web.agendar import CABECALHOS
from nuvem.web.rotas import ir_com_a_sessao, tela


def so_com_demonstracao(request: Request) -> None:
    """Fora dos ambientes da demonstração, as rotas não existem (404)."""
    if not request.app.state.tem_demonstracao:
        raise HTTPException(status.HTTP_404_NOT_FOUND)


roteador = APIRouter(
    prefix="/demonstracao", include_in_schema=False, dependencies=[Depends(so_com_demonstracao)]
)
roteador_da_administracao = APIRouter(
    prefix="/administracao/demonstracao",
    include_in_schema=False,
    dependencies=[Depends(so_com_demonstracao)],
)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDoGestor = Annotated[Acesso, Depends(exigir_papel("gestor"))]
AcessoDoCliente = Annotated[Acesso, Depends(obter_acesso)]
AcessoDaAdministracao = Annotated[AcessoAdmin, Depends(obter_acesso_admin)]
SenhasDaAplicacao = Annotated[Senhas, Depends(obter_senhas)]
CifraDaAplicacao = Annotated[Cifra, Depends(obter_cifra)]
Agora = Annotated[datetime, Depends(agora)]

PapelDaFaixa = Literal["gestor", "porteiro", "patio"]
DESTINO_DO_PAPEL: dict[PapelDaFaixa, str] = {
    "gestor": "/demonstracao",
    "porteiro": "/portaria",
    "patio": "/patio",
}
"""Para onde a faixa leva depois de trocar de papel."""
LINK_FORA = "Este link de demonstração não vale mais. Peça um novo a quem o mandou."


@roteador.get("")
def andamento(
    request: Request, sessao: SessaoDaRequisicao, acesso: AcessoDoGestor, site: int | None = None
) -> HTMLResponse:
    """O dia de demonstração de um site do gestor: o botão de começar ou o andamento."""
    sites = cadastro.listar_sites(sessao, acesso)
    if not sites:
        return tela(request, "aviso.html", {"mensagem": "Você não está ligado a nenhum site."})
    escolhido = cadastro.obter_site(sessao, acesso, site) if site is not None else sites[0]
    dia = demonstracao.andamento(sessao, acesso, escolhido.id)
    fuso = ZoneInfo(escolhido.fuso)
    contexto = {
        "site": escolhido,
        "dia": dia,
        "termina": f"{dia.termina_em.astimezone(fuso):%H:%M:%S}" if dia else "",
        "comecou": f"{dia.comecou_em.astimezone(fuso):%d/%m às %H:%M}" if dia else "",
    }
    return tela(request, "demonstracao.html", contexto)


@roteador.post("/comecar", response_model=None)
def comecar(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoGestor,
    momento: Agora,
    site: Annotated[int, Form()],
) -> HTMLResponse | RedirectResponse:
    """Começa o dia de demonstração do site."""
    try:
        demonstracao.comecar(sessao, acesso, site, agora=momento)
    except DiaJaComecouError:
        return _aviso(request, sessao, "O dia de demonstração já está rodando neste site.")
    except SiteSemCaixaError:
        mensagem = "Este site não tem caixa de borda; o dia de demonstração precisa de uma."
        return _aviso(request, sessao, mensagem)
    sessao.commit()
    return RedirectResponse(f"/demonstracao?site={site}", status.HTTP_303_SEE_OTHER)


def _aviso(request: Request, sessao: Session, mensagem: str) -> HTMLResponse:
    sessao.rollback()
    return tela(request, "aviso.html", {"mensagem": mensagem}, status.HTTP_409_CONFLICT)


# --- O link (quem visita) ---------------------------------------------------------------------


@roteador.get("/link/{codigo}")
def pagina_do_link(
    request: Request, sessao: SessaoDaRequisicao, momento: Agora, codigo: str
) -> HTMLResponse:
    """Para quem é a demonstração e o botão de entrar; não cria nada."""
    try:
        link = links.abrir_link(sessao, codigo, agora=momento)
    except NaoEncontradoError:
        return _link_fora(request)
    contexto = {"nome": link.nome, "codigo": codigo, "vence": _quando(link.vence_em)}
    resposta = tela(request, "demonstracao_link.html", contexto)
    resposta.headers.update(CABECALHOS)
    return resposta


@roteador.post("/link/{codigo}")
def entrar_pelo_link(
    request: Request,
    sessao: SessaoDaRequisicao,
    senhas: SenhasDaAplicacao,
    cifra: CifraDaAplicacao,
    momento: Agora,
    codigo: str,
) -> Response:
    """Entra na empresa de demonstração do link como gestor (cria a empresa na primeira vez)."""
    if request.headers.get("sec-fetch-site") == "cross-site":
        # Outro site faria o navegador de alguém entrar numa empresa escolhida por ele.
        return tela(request, "aviso.html", {"mensagem": "Entre pela página do link."}, 403)
    try:
        codigo_da_sessao = links.entrar_pelo_link(sessao, senhas, cifra, codigo, agora=momento)
    except NaoEncontradoError:
        return _link_fora(request)
    sessao.commit()
    return ir_com_a_sessao(request, codigo_da_sessao, "/demonstracao")


@roteador.post("/papel")
def trocar_de_papel(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoCliente,
    momento: Agora,
    papel: Annotated[PapelDaFaixa, Form()],
) -> Response:
    """A faixa da demonstração: passa a sessão para a pessoa do papel, na mesma empresa."""
    codigo = request.cookies.get(COOKIE_DA_SESSAO, "")
    novo = links.trocar_de_papel(sessao, acesso, codigo=codigo, papel=papel, agora=momento)
    sessao.commit()
    return ir_com_a_sessao(request, novo, DESTINO_DO_PAPEL[papel])


def _link_fora(request: Request) -> HTMLResponse:
    resposta = tela(request, "aviso.html", {"mensagem": LINK_FORA}, status.HTTP_404_NOT_FOUND)
    resposta.headers.update(CABECALHOS)
    return resposta


# --- A administração --------------------------------------------------------------------------


@roteador_da_administracao.get("")
def lista_de_links(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
) -> HTMLResponse:
    """Os links de demonstração e o formulário de gerar um novo."""
    return _tela_dos_links(request, sessao, administracao, momento)


@roteador_da_administracao.post("")
def gerar_link(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    nome: Annotated[str, Form()],
) -> HTMLResponse:
    """Gera um link para uma empresa visitada e mostra o endereço, uma vez só."""
    try:
        gerado = links.gerar_link(sessao, administracao, nome=nome, agora=momento)
    except DadoInvalidoError as erro:
        sessao.rollback()
        return _tela_dos_links(request, sessao, administracao, momento, erro=str(erro), codigo=400)
    sessao.commit()
    base = request.app.state.url_publica or str(request.base_url)
    novo = {
        "nome": gerado.link.nome,
        "endereco": f"{base.rstrip('/')}/demonstracao/link/{gerado.codigo}",
    }
    resposta = _tela_dos_links(request, sessao, administracao, momento, novo=novo)
    resposta.headers.update(CABECALHOS)
    return resposta


@roteador_da_administracao.post("/{link_id}/revogar")
def revogar_link(
    sessao: SessaoDaRequisicao, administracao: AcessoDaAdministracao, momento: Agora, link_id: int
) -> RedirectResponse:
    """Revoga o link: ele deixa de valer, e as pessoas da empresa dele saem na hora."""
    links.revogar_link(sessao, administracao, link_id, agora=momento)
    sessao.commit()
    return RedirectResponse("/administracao/demonstracao", status.HTTP_303_SEE_OTHER)


def _tela_dos_links(
    request: Request,
    sessao: Session,
    administracao: AcessoAdmin,
    momento: datetime,
    *,
    novo: dict[str, str] | None = None,
    erro: str | None = None,
    codigo: int = status.HTTP_200_OK,
) -> HTMLResponse:
    linhas = [_linha(link, momento) for link in links.listar_links(sessao, administracao)]
    contexto = {"links": linhas, "novo": novo, "erro": erro, "validade": links.VALIDADE.days}
    return tela(request, "administracao_demonstracao.html", contexto, codigo)


def _linha(link: LinkDemonstracao, momento: datetime) -> dict[str, Any]:
    if link.revogado_em is not None:
        situacao = f"revogado em {_quando(link.revogado_em)}"
    elif links.vale(link, agora=momento):
        situacao = f"vale até {_quando(link.vence_em)}"
    else:
        situacao = f"venceu em {_quando(link.vence_em)}"
    if link.apagada_em is not None:
        empresa = f"apagada em {_quando(link.apagada_em)}"
    elif link.empresa_id is not None:
        empresa = "criada"
    else:
        empresa = "ainda não entraram"
    return {
        "id": link.id,
        "nome": link.nome,
        "gerado": _quando(link.criado_em),
        "situacao": situacao,
        "empresa": empresa,
        "ultima_entrada": _quando(link.ultima_entrada_em) if link.ultima_entrada_em else "",
        "pode_revogar": links.vale(link, agora=momento),
    }


def _quando(momento: datetime) -> str:
    return f"{momento.astimezone(ZoneInfo(FUSO_PADRAO)):%d/%m às %H:%M}"

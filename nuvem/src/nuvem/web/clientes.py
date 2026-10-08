"""O cadastro do cliente na administração (SDD 6.2, D-75).

- ``GET /administracao/clientes``: as empresas e o formulário da empresa nova.
- ``GET /administracao/clientes/{empresa}``: a ficha da empresa, com um formulário para cada
  coisa que se cadastra (site, portaria, faixa, câmera, doca e pessoa).
- Os ``POST`` cadastram e voltam à ficha. A pessoa nova e o link novo de senha mostram o link
  **uma vez só**, na própria resposta (que não fica guardada no navegador): o código nunca vai
  para um endereço de redirecionamento.
"""

from datetime import datetime, time
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import cliente
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import AcessoAdmin, obter_acesso_admin
from nuvem.cadastro.modelos import FUSO_PADRAO, Papel, Posicao, Sentido
from nuvem.cifra import Cifra, obter_cifra
from nuvem.erros import DadoInvalidoError
from nuvem.relogio import agora
from nuvem.web.rotas import tela

roteador = APIRouter(prefix="/administracao/clientes", include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDaAdministracao = Annotated[AcessoAdmin, Depends(obter_acesso_admin)]
CifraDaAplicacao = Annotated[Cifra, Depends(obter_cifra)]
Agora = Annotated[datetime, Depends(agora)]
Nome = Annotated[str, Form(max_length=cliente.TAMANHO_DO_NOME)]

SEM_CACHE = {"Cache-Control": "no-store"}
FUSO_DA_ADMINISTRACAO = ZoneInfo(FUSO_PADRAO)
PAPEIS: dict[str, str] = {"gestor": "gestor", "porteiro": "porteiro", "patio": "líder de pátio"}


@roteador.get("")
def empresas(
    request: Request, sessao: SessaoDaRequisicao, _administracao: AcessoDaAdministracao
) -> HTMLResponse:
    """As empresas e o formulário da empresa nova."""
    return _lista(request, sessao, {})


@roteador.post("", response_model=None)
def nova_empresa(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    nome: Nome,
    cnpj: Annotated[str, Form(max_length=30)],
) -> Response:
    """Cadastra a empresa e abre a ficha dela."""
    try:
        empresa = cliente.cadastrar_empresa(sessao, administracao, nome=nome, cnpj=cnpj)
    except DadoInvalidoError as erro:
        contexto = {"nome": nome, "cnpj": cnpj, "erro": str(erro)}
        return _lista(request, sessao, contexto, status.HTTP_400_BAD_REQUEST)
    sessao.commit()
    return _para_a_ficha(empresa.id)


@roteador.get("/{empresa_id}")
def ficha(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    empresa_id: int,
) -> HTMLResponse:
    """A ficha da empresa."""
    return _ficha(request, sessao, administracao, empresa_id, momento, {})


@roteador.post("/{empresa_id}/sites", response_model=None)
def novo_site(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    empresa_id: int,
    nome: Nome,
    fuso: Annotated[str, Form(max_length=60)] = FUSO_PADRAO,
    abre: Annotated[time | None, Form()] = None,
    fecha: Annotated[time | None, Form()] = None,
) -> Response:
    """Cadastra um site (sem horário, 24 horas)."""
    return _cadastrar(
        request, sessao, administracao, momento, empresa_id,
        lambda: cliente.cadastrar_site(
            sessao, administracao, empresa_id, nome=nome, fuso=fuso, abre=abre, fecha=fecha
        ),
    )  # fmt: skip


@roteador.post("/{empresa_id}/portarias", response_model=None)
def nova_portaria(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    empresa_id: int,
    site: Annotated[int, Form()],
    nome: Nome,
) -> Response:
    """Cadastra uma portaria no site."""
    return _cadastrar(
        request, sessao, administracao, momento, empresa_id,
        lambda: cliente.cadastrar_portaria(sessao, administracao, empresa_id, site, nome=nome),
    )  # fmt: skip


@roteador.post("/{empresa_id}/faixas", response_model=None)
def nova_faixa(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    empresa_id: int,
    portaria: Annotated[int, Form()],
    nome: Nome,
    sentido: Annotated[Sentido, Form()],
) -> Response:
    """Cadastra uma faixa de entrada ou de saída na portaria."""
    return _cadastrar(
        request, sessao, administracao, momento, empresa_id,
        lambda: cliente.cadastrar_faixa(
            sessao, administracao, empresa_id, portaria, nome=nome, sentido=sentido
        ),
    )  # fmt: skip


@roteador.post("/{empresa_id}/cameras", response_model=None)
def nova_camera(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    cifra: CifraDaAplicacao,
    momento: Agora,
    empresa_id: int,
    faixa: Annotated[int, Form()],
    nome: Nome,
    posicao: Annotated[Posicao, Form()],
    endereco: Annotated[str, Form(max_length=300)],
    login: Annotated[str, Form(max_length=100)] = "",
    senha: Annotated[str, Form(max_length=200)] = "",
) -> Response:
    """Cadastra uma câmera na faixa (a senha vai cifrada)."""
    return _cadastrar(
        request, sessao, administracao, momento, empresa_id,
        lambda: cliente.cadastrar_camera(
            sessao, administracao, cifra, empresa_id, faixa, nome=nome, posicao=posicao,
            endereco=endereco, login=login, senha=senha,
        ),
    )  # fmt: skip


@roteador.post("/{empresa_id}/cameras/{camera_id}", response_model=None)
def trocar_camera(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    cifra: CifraDaAplicacao,
    momento: Agora,
    empresa_id: int,
    camera_id: int,
    endereco: Annotated[str, Form(max_length=300)],
    login: Annotated[str, Form(max_length=100)] = "",
    senha: Annotated[str, Form(max_length=200)] = "",
) -> Response:
    """Troca o endereço e o login da câmera; a senha, só se vier uma nova."""
    return _cadastrar(
        request, sessao, administracao, momento, empresa_id,
        lambda: cliente.trocar_camera(
            sessao, administracao, cifra, empresa_id, camera_id,
            endereco=endereco, login=login, senha=senha,
        ),
    )  # fmt: skip


@roteador.post("/{empresa_id}/docas", response_model=None)
def nova_doca(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    empresa_id: int,
    site: Annotated[int, Form()],
    nome: Nome,
) -> Response:
    """Cadastra uma doca no site."""
    return _cadastrar(
        request, sessao, administracao, momento, empresa_id,
        lambda: cliente.cadastrar_doca(sessao, administracao, empresa_id, site, nome=nome),
    )  # fmt: skip


@roteador.post("/{empresa_id}/pessoas", response_model=None)
def nova_pessoa(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    empresa_id: int,
    nome: Nome,
    email: Annotated[str, Form(max_length=200)],
    papel: Annotated[Papel, Form()],
    sites: Annotated[list[int] | None, Form()] = None,
) -> Response:
    """Cadastra a pessoa, sem senha, e mostra o link para ela criar a senha (uma vez só)."""
    try:
        gerado = cliente.cadastrar_pessoa(
            sessao, administracao, empresa_id, nome=nome, email=email, papel=papel,
            sites=sites or [], agora=momento,
        )  # fmt: skip
    except DadoInvalidoError as erro:
        sessao.rollback()
        return _ficha(
            request, sessao, administracao, empresa_id, momento, {"erro": str(erro)},
            status.HTTP_400_BAD_REQUEST,
        )  # fmt: skip
    sessao.commit()
    return _com_o_link(request, sessao, administracao, empresa_id, momento, gerado)


@roteador.post("/{empresa_id}/pessoas/{usuario_id}/link", response_model=None)
def novo_link(
    request: Request,
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    empresa_id: int,
    usuario_id: int,
) -> Response:
    """Um link novo de senha (a senha esquecida); o anterior deixa de valer."""
    try:
        gerado = cliente.gerar_link_de_senha(
            sessao, administracao, empresa_id, usuario_id, agora=momento
        )
    except DadoInvalidoError as erro:
        return _ficha(
            request, sessao, administracao, empresa_id, momento, {"erro": str(erro)},
            status.HTTP_400_BAD_REQUEST,
        )  # fmt: skip
    sessao.commit()
    return _com_o_link(request, sessao, administracao, empresa_id, momento, gerado)


@roteador.post("/{empresa_id}/pessoas/{usuario_id}/situacao", response_model=None)
def mudar_situacao(
    sessao: SessaoDaRequisicao,
    administracao: AcessoDaAdministracao,
    momento: Agora,
    empresa_id: int,
    usuario_id: int,
    ativa: Annotated[bool, Form()],
) -> Response:
    """Ativa ou desativa a pessoa (desativar fecha as sessões dela)."""
    cliente.mudar_situacao_da_pessoa(
        sessao, administracao, empresa_id, usuario_id, ativa=ativa, agora=momento
    )
    sessao.commit()
    return _para_a_ficha(empresa_id)


# --- As telas -------------------------------------------------------------------------------


def _para_a_ficha(empresa_id: int) -> RedirectResponse:
    return RedirectResponse(
        f"/administracao/clientes/{empresa_id}", status_code=status.HTTP_303_SEE_OTHER
    )


def _cadastrar(
    request: Request,
    sessao: Session,
    administracao: AcessoAdmin,
    momento: datetime,
    empresa_id: int,
    fazer: Any,
) -> Response:
    try:
        fazer()
    except DadoInvalidoError as erro:
        sessao.rollback()
        return _ficha(
            request, sessao, administracao, empresa_id, momento, {"erro": str(erro)},
            status.HTTP_400_BAD_REQUEST,
        )  # fmt: skip
    sessao.commit()
    return _para_a_ficha(empresa_id)


def _lista(
    request: Request, sessao: Session, contexto: dict[str, Any], codigo: int = status.HTTP_200_OK
) -> HTMLResponse:
    contexto = {"empresas": cadastro.listar_empresas(sessao), **contexto}
    return tela(request, "administracao_clientes.html", contexto, codigo)


def _ficha(
    request: Request,
    sessao: Session,
    administracao: AcessoAdmin,
    empresa_id: int,
    momento: datetime,
    contexto: dict[str, Any],
    codigo: int = status.HTTP_200_OK,
) -> HTMLResponse:
    contexto = {
        "ficha": cliente.ficha_da_empresa(sessao, administracao, empresa_id, agora=momento),
        "papeis": PAPEIS,
        "fuso_padrao": FUSO_PADRAO,
        "quando": _quando,
        **contexto,
    }
    return tela(request, "administracao_cliente.html", contexto, codigo)


def _quando(momento: datetime) -> str:
    """Dia e hora em Brasília, como a administração lê."""
    return momento.astimezone(FUSO_DA_ADMINISTRACAO).strftime("%d/%m/%Y %H:%M")


def _com_o_link(
    request: Request,
    sessao: Session,
    administracao: AcessoAdmin,
    empresa_id: int,
    momento: datetime,
    gerado: cliente.LinkGerado,
) -> HTMLResponse:
    base = (request.app.state.url_publica or str(request.base_url)).rstrip("/")
    contexto = {
        "link": f"{base}/senha/{gerado.codigo}",
        "link_de": gerado.usuario.nome,
        "link_vence_em": gerado.vence_em,
    }
    resposta = _ficha(request, sessao, administracao, empresa_id, momento, contexto)
    resposta.headers.update(SEM_CACHE)
    return resposta

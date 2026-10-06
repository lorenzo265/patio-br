"""Rotas da frota: a caixa ativa, baixa a configuração, manda a saúde, pergunta a versão e conta
as atualizações; a administração gera códigos, revoga caixas e cuida das versões (D-67).

Os identificadores que a caixa recebe são os ids da nuvem em texto (SDD D-21): são os mesmos
que ela põe nas passagens.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from contratos.saude import Saude
from nuvem.banco import obter_sessao
from nuvem.cadastro.acesso import AcessoAdmin, obter_acesso_admin
from nuvem.cadastro.modelos import Posicao, Sentido
from nuvem.cifra import Cifra, obter_cifra
from nuvem.erros import DadoInvalidoError
from nuvem.frota import saude, servico, versoes
from nuvem.frota.acesso import obter_caixa
from nuvem.frota.modelos import CaixaBorda
from nuvem.frota.servico import AcessoDaCaixa
from nuvem.frota.versoes import RelatoDeAtualizacao
from nuvem.relogio import agora

roteador_borda = APIRouter(prefix="/api/borda", tags=["borda"])
roteador_admin = APIRouter(prefix="/api/admin", tags=["administração"])

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
Agora = Annotated[datetime, Depends(agora)]
CaixaDaRequisicao = Annotated[AcessoDaCaixa, Depends(obter_caixa)]
AcessoDaAdministracao = Annotated[AcessoAdmin, Depends(obter_acesso_admin)]

CODIGO_RECUSADO = "código de ativação inválido, já usado ou vencido"
SAUDE_DE_OUTRA_CAIXA = "a saúde é de outro site ou de outra caixa"
VERSAO_NAO_PROVADA = "a versão vai primeiro numa caixa: escolha para uma caixa e espere dar certo"


class PedidoDeAtivacao(BaseModel):
    """O que a caixa manda para se ativar."""

    model_config = ConfigDict(extra="forbid")

    codigo: Annotated[str, Field(min_length=1, max_length=40)]


class Ativacao(BaseModel):
    """O que a caixa recebe ao se ativar. Guarde a chave: ela não aparece de novo."""

    caixa_id: str
    site_id: str
    chave: str


class CameraDaConfiguracao(BaseModel):
    """Uma câmera, com o que a caixa precisa para ler o vídeo dela."""

    id: str
    nome: str
    posicao: Posicao
    endereco: str
    login: str
    senha: str


class FaixaDaConfiguracao(BaseModel):
    """Uma faixa do site, com as câmeras dela."""

    id: str
    nome: str
    sentido: Sentido
    cameras: list[CameraDaConfiguracao]


class Configuracao(BaseModel):
    """A configuração da caixa: o site dela, as faixas e as câmeras."""

    caixa_id: str
    site_id: str
    faixas: list[FaixaDaConfiguracao]


class CodigoDeAtivacao(BaseModel):
    """Um código gerado para a administração entregar a quem instala a caixa."""

    codigo: str
    expira_em: datetime


class CaixaPublica(BaseModel):
    """Uma caixa como a administração a vê."""

    id: int
    empresa_id: int
    site_id: int
    ativada_em: datetime
    revogada: bool
    ultimo_contato: datetime | None
    """Quando chegou a última saúde (D-65)."""
    versao_programa: str | None
    versao_leitor: str | None

    @classmethod
    def de(cls, caixa: CaixaBorda) -> "CaixaPublica":
        """Monta a partir da tabela."""
        return cls(
            id=caixa.id,
            empresa_id=caixa.empresa_id,
            site_id=caixa.site_id,
            ativada_em=caixa.ativada_em,
            revogada=caixa.revogada_em is not None,
            ultimo_contato=caixa.ultimo_contato,
            versao_programa=caixa.versao_programa,
            versao_leitor=caixa.versao_leitor,
        )


class VersaoParaCaixa(BaseModel):
    """A versão que vale para a caixa: o nome e a imagem pelo resumo."""

    nome: str
    imagem: str


class AtualizacaoRegistrada(BaseModel):
    """A atualização gravada."""

    id: int


class PedidoDeVersao(BaseModel):
    """Uma versão nova do agente (D-67)."""

    model_config = ConfigDict(extra="forbid")

    nome: Annotated[str, Field(max_length=50)]
    imagem: Annotated[str, Field(max_length=200)]
    resumo: Annotated[str, Field(max_length=71)]


class VersaoPublica(BaseModel):
    """Uma versão como a administração a vê."""

    id: int
    nome: str
    imagem: str
    resumo: str
    cadastrada_em: datetime
    caixas_com_sucesso: int = 0


class PedidoDeEscolha(BaseModel):
    """Para quem vale a versão: uma caixa, um site ou (sem os dois) todas as caixas."""

    model_config = ConfigDict(extra="forbid")

    site_id: int | None = None
    caixa_id: int | None = None


class EscolhaPublica(BaseModel):
    """A escolha gravada."""

    id: int
    versao_id: int
    site_id: int | None
    caixa_id: int | None
    escolhida_em: datetime


# --- A caixa -------------------------------------------------------------------------------


@roteador_borda.post("/ativar", status_code=status.HTTP_201_CREATED)
def ativar(sessao: SessaoDaRequisicao, momento: Agora, pedido: PedidoDeAtivacao) -> Ativacao:
    """Troca o código de ativação pela chave da caixa (401 se o código não vale)."""
    try:
        ativada = servico.ativar(sessao, pedido.codigo, agora=momento)
    except servico.CodigoRecusadoError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=CODIGO_RECUSADO) from None
    sessao.commit()
    return Ativacao(
        caixa_id=str(ativada.caixa_id), site_id=str(ativada.site_id), chave=ativada.chave
    )


@roteador_borda.get("/configuracao")
def configuracao(
    sessao: SessaoDaRequisicao,
    cifra: Annotated[Cifra, Depends(obter_cifra)],
    caixa: CaixaDaRequisicao,
) -> Configuracao:
    """As faixas e câmeras do site da caixa, com a senha das câmeras."""
    dados = servico.configuracao(sessao, cifra, caixa)
    return Configuracao(
        caixa_id=str(dados.caixa_id),
        site_id=str(dados.site_id),
        faixas=[
            FaixaDaConfiguracao(
                id=str(faixa.id),
                nome=faixa.nome,
                sentido=faixa.sentido,
                cameras=[
                    CameraDaConfiguracao(
                        id=str(camera.id),
                        nome=camera.nome,
                        posicao=camera.posicao,
                        endereco=camera.endereco,
                        login=camera.login,
                        senha=camera.senha,
                    )
                    for camera in faixa.cameras
                ],
            )
            for faixa in dados.faixas
        ],
    )


@roteador_borda.post("/saude", status_code=status.HTTP_204_NO_CONTENT)
def receber_saude(
    sessao: SessaoDaRequisicao, momento: Agora, caixa: CaixaDaRequisicao, pedido: Saude
) -> None:
    """A saúde da caixa, a cada minuto (D-65): 403 se é de outra caixa ou de outro site."""
    try:
        saude.receber_saude(sessao, caixa, pedido, agora=momento)
    except saude.SaudeDeOutraCaixaError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=SAUDE_DE_OUTRA_CAIXA) from None
    sessao.commit()


@roteador_borda.get("/versao", response_model=None)
def versao_da_caixa(
    sessao: SessaoDaRequisicao, caixa: CaixaDaRequisicao
) -> VersaoParaCaixa | Response:
    """A versão que vale para a caixa (D-67); 204 se nenhuma foi escolhida."""
    escolhida = versoes.versao_da_caixa(sessao, caixa)
    if escolhida is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return VersaoParaCaixa(nome=escolhida.nome, imagem=escolhida.referencia)


@roteador_borda.post("/atualizacoes", status_code=status.HTTP_201_CREATED)
def contar_atualizacao(
    sessao: SessaoDaRequisicao,
    momento: Agora,
    caixa: CaixaDaRequisicao,
    pedido: RelatoDeAtualizacao,
) -> AtualizacaoRegistrada:
    """A troca de versão que a caixa fez (D-67); 422 se o resumo não é de uma versão."""
    try:
        registro = versoes.registrar_atualizacao(sessao, caixa, pedido, agora=momento)
    except DadoInvalidoError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(erro)) from None
    sessao.commit()
    return AtualizacaoRegistrada(id=registro.id)


# --- A administração -----------------------------------------------------------------------


@roteador_admin.post("/sites/{site_id}/codigos-de-ativacao", status_code=status.HTTP_201_CREATED)
def gerar_codigo(
    sessao: SessaoDaRequisicao, momento: Agora, administracao: AcessoDaAdministracao, site_id: int
) -> CodigoDeAtivacao:
    """Gera um código de ativação para o site (vale 24 horas, uma vez)."""
    gerado = servico.gerar_codigo_de_ativacao(
        sessao, site_id, administrador_id=administracao.administrador_id, agora=momento
    )
    sessao.commit()
    return CodigoDeAtivacao(codigo=gerado.codigo, expira_em=gerado.expira_em)


@roteador_admin.get("/caixas")
def listar_caixas(
    sessao: SessaoDaRequisicao, _administracao: AcessoDaAdministracao
) -> list[CaixaPublica]:
    """Todas as caixas, das mais novas para as mais antigas."""
    return [CaixaPublica.de(caixa) for caixa in servico.listar_caixas(sessao)]


@roteador_admin.post("/caixas/{caixa_id}/revogar")
def revogar(
    sessao: SessaoDaRequisicao, momento: Agora, _administracao: AcessoDaAdministracao, caixa_id: int
) -> CaixaPublica:
    """Revoga a chave da caixa (404 se a caixa não existir)."""
    caixa = servico.revogar(sessao, caixa_id, agora=momento)
    sessao.commit()
    return CaixaPublica.de(caixa)


@roteador_admin.post("/versoes", status_code=status.HTTP_201_CREATED)
def cadastrar_versao(
    sessao: SessaoDaRequisicao,
    momento: Agora,
    administracao: AcessoDaAdministracao,
    pedido: PedidoDeVersao,
) -> VersaoPublica:
    """Cadastra uma versão do agente pelo resumo da imagem (422 se fora do formato ou repetida)."""
    try:
        versao = versoes.cadastrar_versao(
            sessao,
            administracao,
            nome=pedido.nome,
            imagem=pedido.imagem,
            resumo=pedido.resumo,
            agora=momento,
        )
    except DadoInvalidoError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(erro)) from None
    sessao.commit()
    return VersaoPublica.model_validate(versao, from_attributes=True)


@roteador_admin.get("/versoes")
def listar_versoes(
    sessao: SessaoDaRequisicao, administracao: AcessoDaAdministracao
) -> list[VersaoPublica]:
    """As versões, das mais novas para as mais antigas, com as caixas em que deram certo."""
    return [
        VersaoPublica.model_validate(item.versao, from_attributes=True).model_copy(
            update={"caixas_com_sucesso": item.caixas_com_sucesso}
        )
        for item in versoes.listar_versoes(sessao, administracao)
    ]


@roteador_admin.post("/versoes/{versao_id}/escolher", status_code=status.HTTP_201_CREATED)
def escolher_versao(
    sessao: SessaoDaRequisicao,
    momento: Agora,
    administracao: AcessoDaAdministracao,
    versao_id: int,
    pedido: PedidoDeEscolha,
) -> EscolhaPublica:
    """Escolhe a versão para uma caixa, um site ou todas (409 se ainda não deu certo numa caixa)."""
    try:
        escolha = versoes.escolher_versao(
            sessao,
            administracao,
            versao_id,
            site_id=pedido.site_id,
            caixa_id=pedido.caixa_id,
            agora=momento,
        )
    except versoes.VersaoNaoProvadaError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=VERSAO_NAO_PROVADA) from None
    except DadoInvalidoError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(erro)) from None
    sessao.commit()
    return EscolhaPublica.model_validate(escolha, from_attributes=True)

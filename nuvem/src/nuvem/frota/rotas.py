"""Rotas da frota: a caixa ativa, baixa a configuração e manda a saúde; a administração gera
códigos e revoga caixas.

Os identificadores que a caixa recebe são os ids da nuvem em texto (SDD D-21): são os mesmos
que ela põe nas passagens.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from contratos.saude import Saude
from nuvem.banco import obter_sessao
from nuvem.cadastro.acesso import AcessoAdmin, obter_acesso_admin
from nuvem.cadastro.modelos import Posicao, Sentido
from nuvem.cifra import Cifra, obter_cifra
from nuvem.frota import saude, servico
from nuvem.frota.acesso import obter_caixa
from nuvem.frota.modelos import CaixaBorda
from nuvem.frota.servico import AcessoDaCaixa
from nuvem.relogio import agora

roteador_borda = APIRouter(prefix="/api/borda", tags=["borda"])
roteador_admin = APIRouter(prefix="/api/admin", tags=["administração"])

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
Agora = Annotated[datetime, Depends(agora)]
CaixaDaRequisicao = Annotated[AcessoDaCaixa, Depends(obter_caixa)]
AcessoDaAdministracao = Annotated[AcessoAdmin, Depends(obter_acesso_admin)]

CODIGO_RECUSADO = "código de ativação inválido, já usado ou vencido"
SAUDE_DE_OUTRA_CAIXA = "a saúde é de outro site ou de outra caixa"


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

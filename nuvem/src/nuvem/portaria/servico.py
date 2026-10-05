"""Regras da portaria: receber as passagens da borda e mostrá-las (SDD 3.2 e 5.5).

- Reenvio seguro: o mesmo ``id`` de novo, da mesma caixa, não cria outra passagem.
- A caixa só manda passagens do site dela, com faixas e câmeras desse site.
- A passagem fica guardada como veio; nada aqui a altera depois.
- Quem lê (a tela da portaria) passa o ``Acesso``: só vê os sites dele, da empresa dele.
- A passagem nova vira a tarefa "casar", que o worker executa (``tarefas_de_fundo``).

As funções gravam com ``flush``; o ``commit`` é de quem chama.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem import tarefas_de_fundo as fila
from nuvem.armazenamento import Armazenamento, RefInvalidoError, validar_ref
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso
from nuvem.cadastro.servico import FaixaDoSite
from nuvem.erros import NaoEncontradoError
from nuvem.frota.servico import AcessoDaCaixa
from nuvem.portaria.modelos import PassagemRecebida

LIMITE_DA_TELA = 50
"""Quantas passagens a tela da portaria mostra (as últimas)."""

Local = tuple[str | int, ...]
"""Onde está o campo recusado dentro da passagem (ex.: ``("placas", 0, "camera_id")``)."""


class PassagemDeOutroSiteError(Exception):
    """A passagem diz ser de outro site ou de outra caixa que não a dona da chave."""


class IdDeOutraCaixaError(Exception):
    """O ``id`` da passagem já foi usado por outra caixa."""


class PassagemInvalidaError(ValueError):
    """Um campo da passagem não confere com o cadastro do site (``loc`` diz qual)."""

    def __init__(self, loc: Local, mensagem: str) -> None:
        super().__init__(mensagem)
        self.loc = loc
        self.mensagem = mensagem


def receber_passagem(
    sessao: Session, caixa: AcessoDaCaixa, passagem: Passagem, *, agora: datetime
) -> bool:
    """Guarda uma passagem mandada pela caixa.

    Returns:
        ``True`` se a passagem é nova; ``False`` se já tinha chegado (reenvio).

    Raises:
        PassagemDeOutroSiteError: se ``site_id`` ou ``caixa_id`` não forem os da caixa.
        IdDeOutraCaixaError: se o ``id`` já for de uma passagem de outra caixa.
        PassagemInvalidaError: se a faixa ou uma câmera não forem do site, se o sentido não
            for o da faixa, ou se o ``ref`` de uma foto fugir da regra.
    """
    if passagem.caixa_id != str(caixa.caixa_id) or passagem.site_id != str(caixa.site_id):
        raise PassagemDeOutroSiteError
    if _ja_chegou(sessao, caixa, passagem):
        return False
    faixa = _conferir_com_o_cadastro(sessao, caixa, passagem)
    resultado = sessao.execute(
        insert(PassagemRecebida)
        .values(
            id=passagem.id,
            empresa_id=caixa.empresa_id,
            site_id=caixa.site_id,
            caixa_id=caixa.caixa_id,
            faixa_id=faixa.id,
            sentido=passagem.sentido,
            inicio=passagem.inicio,
            fim=passagem.fim,
            recebida_em=agora,
            como_veio=passagem.model_dump(mode="json"),
        )
        # A mesma passagem chegando duas vezes ao mesmo tempo: só uma entra.
        .on_conflict_do_nothing(index_elements=["id"])
    )
    if getattr(resultado, "rowcount", 1) == 0:
        _ja_chegou(sessao, caixa, passagem)  # entrou a outra; erro se for de outra caixa
        return False
    # O casamento roda no worker, fora do pedido da caixa (D-38).
    fila.enfileirar(
        sessao,
        "casar_passagem",
        {"passagem_id": str(passagem.id)},
        chave=str(passagem.id),
        agora=agora,
    )
    sessao.flush()
    return True


def ultimas_passagens(
    sessao: Session, acesso: Acesso, site_id: int, *, limite: int = LIMITE_DA_TELA
) -> list[PassagemRecebida]:
    """As últimas passagens de um site que o usuário vê, das mais novas para as mais antigas.

    Raises:
        NaoEncontradoError: se o site não existir ou não for visível para este usuário.
    """
    site = cadastro.obter_site(sessao, acesso, site_id)
    return list(
        sessao.scalars(
            select(PassagemRecebida)
            .where(PassagemRecebida.empresa_id == acesso.empresa_id)
            .where(PassagemRecebida.site_id == site.id)
            .order_by(PassagemRecebida.inicio.desc())
            .limit(limite)
        )
    )


def foto_da_passagem(
    sessao: Session,
    acesso: Acesso,
    armazenamento: Armazenamento,
    passagem_id: UUID,
    indice: int,
) -> bytes:
    """A foto número ``indice`` de uma passagem que o usuário vê.

    Raises:
        NaoEncontradoError: se a passagem não for visível para o usuário, não tiver essa foto,
            ou a foto ainda não tiver chegado.
    """
    passagem = sessao.scalar(
        select(PassagemRecebida).where(
            PassagemRecebida.id == passagem_id,
            PassagemRecebida.empresa_id == acesso.empresa_id,
            PassagemRecebida.site_id.in_(acesso.sites),
        )
    )
    nao_encontrada = NaoEncontradoError(f"foto {indice} da passagem {passagem_id}")
    if passagem is None:
        raise nao_encontrada
    fotos = passagem.como_veio["fotos"]
    if not 0 <= indice < len(fotos):
        raise nao_encontrada
    conteudo = armazenamento.ler(passagem.caixa_id, fotos[indice]["ref"])
    if conteudo is None:
        raise nao_encontrada
    return conteudo


def _ja_chegou(sessao: Session, caixa: AcessoDaCaixa, passagem: Passagem) -> bool:
    """Diz se a passagem já chegou desta caixa.

    Raises:
        IdDeOutraCaixaError: se o id já for de uma passagem de outra caixa.
    """
    existente = sessao.get(PassagemRecebida, passagem.id, populate_existing=True)
    if existente is not None and existente.caixa_id != caixa.caixa_id:
        raise IdDeOutraCaixaError
    return existente is not None


def _conferir_com_o_cadastro(
    sessao: Session, caixa: AcessoDaCaixa, passagem: Passagem
) -> FaixaDoSite:
    estrutura = cadastro.estrutura_do_site(
        sessao, empresa_id=caixa.empresa_id, site_id=caixa.site_id
    )
    faixa = estrutura.get(_numero(passagem.faixa_id) or -1)
    if faixa is None:
        raise PassagemInvalidaError(("faixa_id",), "a faixa não é deste site")
    if passagem.sentido != faixa.sentido:
        raise PassagemInvalidaError(("sentido",), f"a faixa {faixa.id} é de {faixa.sentido}")
    cameras_do_site = frozenset().union(*(f.cameras for f in estrutura.values()))
    for indice, placa in enumerate(passagem.placas):
        if _numero(placa.camera_id) not in cameras_do_site:
            raise PassagemInvalidaError(
                ("placas", indice, "camera_id"), "a câmera não é deste site"
            )
    for indice, foto in enumerate(passagem.fotos):
        if _numero(foto.camera_id) not in cameras_do_site:
            raise PassagemInvalidaError(("fotos", indice, "camera_id"), "a câmera não é deste site")
        try:
            validar_ref(foto.ref)
        except RefInvalidoError as erro:
            raise PassagemInvalidaError(("fotos", indice, "ref"), str(erro)) from erro
    return faixa


def _numero(identificador: str) -> int | None:
    # Os ids da nuvem vão em texto na passagem (SDD D-21): "12".
    return int(identificador) if identificador.isascii() and identificador.isdigit() else None

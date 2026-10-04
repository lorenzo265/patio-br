"""Regras da portaria: receber as passagens da borda (SDD 3.2 e 5.5).

- Reenvio seguro: o mesmo ``id`` de novo, da mesma caixa, não cria outra passagem.
- A caixa só manda passagens do site dela, com faixas e câmeras desse site.
- A passagem fica guardada como veio; nada aqui a altera depois.

As funções gravam com ``flush``; o ``commit`` é de quem chama.
"""

from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem.armazenamento import RefInvalidoError, validar_ref
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.servico import FaixaDoSite
from nuvem.frota.servico import AcessoDaCaixa
from nuvem.portaria.modelos import PassagemRecebida

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
    sessao.flush()
    return True


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

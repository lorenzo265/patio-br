"""A base de treino (SDD 4.6 e 8.3, D-71).

- **A autorização:** a administração registra a data da cláusula do contrato de cada empresa (a
  de demonstração não entra). Revogar apaga os rótulos e as cópias dos recortes da empresa.
- **Rotular:** a cada hora, o worker transforma a última conferência de cada recorte, feita desde
  a data da cláusula, num rótulo a revisar, e copia o recorte para a base de treino (a foto se
  apaga aos 90 dias; a cópia, não). Sem o recorte (a foto já saiu), o rótulo nasce descartado.
- **A régua:** 1 em cada 10 rótulos, pelo resumo da passagem e da foto (``conjunto_de``): a mesma
  conferência cai sempre no mesmo conjunto, e o conjunto fica gravado.
- **A rotulagem:** aceitar, corrigir ou descartar. Só os aceitos e os corrigidos vão para o treino.
- **A exportação:** a pasta que o ambiente de treino lê (D-40): os recortes e um CSV por conjunto.
"""

import csv
import hashlib
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, delete, exists, func, select, update
from sqlalchemy.orm import Session

from contratos.placa import PlacaInvalidaError, normalizar_placa
from nuvem.armazenamento import Armazenamento
from nuvem.cadastro.acesso import AcessoAdmin
from nuvem.cadastro.modelos import Empresa
from nuvem.demonstracao.modelos import LinkDemonstracao
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.portaria.modelos import ConferenciaPlaca, PassagemRecebida
from nuvem.treino.guarda import GuardaDoTreino
from nuvem.treino.modelos import (
    AutorizacaoDeTreino,
    ConjuntoDoRotulo,
    Rotulo,
    SituacaoDoRotulo,
)

ROTULOS_POR_VEZ = 500
"""O worker rotula no máximo estes recortes a cada volta (o resto, na seguinte)."""
UM_EM = 10
"""A régua recebe 1 em cada 10 rótulos."""

AcaoDaRevisao = Literal["aceitar", "corrigir", "descartar"]
SITUACAO_DEPOIS: dict[AcaoDaRevisao, SituacaoDoRotulo] = {
    "aceitar": "aceito",
    "corrigir": "corrigido",
    "descartar": "descartado",
}


@dataclass(frozen=True)
class Exportacao:
    """Quantos recortes foram para cada conjunto."""

    treino: int
    regua: int


# --- A autorização do contrato --------------------------------------------------------------


def autorizar(
    sessao: Session,
    administracao: AcessoAdmin,
    empresa_id: int,
    *,
    clausula_em: date,
    agora: datetime,
) -> AutorizacaoDeTreino:
    """Registra a cláusula do contrato da empresa (a anterior deixa de valer; sem ``commit``).

    Raises:
        NaoEncontradoError: se a empresa não existe.
        DadoInvalidoError: se a empresa nasceu de um link de demonstração.
    """
    if sessao.get(Empresa, empresa_id) is None:
        raise NaoEncontradoError(f"empresa {empresa_id}")
    demonstracao = select(LinkDemonstracao.id).where(LinkDemonstracao.empresa_id == empresa_id)
    if sessao.scalar(demonstracao) is not None:
        raise DadoInvalidoError("a empresa de demonstração não entra na base de treino")
    sessao.execute(
        update(AutorizacaoDeTreino)
        .where(
            AutorizacaoDeTreino.empresa_id == empresa_id, AutorizacaoDeTreino.revogada_em.is_(None)
        )
        .values(revogada_em=agora)
    )
    autorizacao = AutorizacaoDeTreino(
        empresa_id=empresa_id,
        clausula_em=clausula_em,
        registrada_por=administracao.administrador_id,
        registrada_em=agora,
    )
    sessao.add(autorizacao)
    sessao.flush()
    return autorizacao


def revogar(
    sessao: Session,
    _administracao: AcessoAdmin,
    empresa_id: int,
    guarda: GuardaDoTreino,
    *,
    agora: datetime,
) -> int:
    """Revoga a autorização e apaga os rótulos e as cópias da empresa (sem ``commit``).

    Returns:
        Quantos rótulos foram apagados.

    Raises:
        NaoEncontradoError: se a empresa não tem autorização ativa.
    """
    resultado = sessao.execute(
        update(AutorizacaoDeTreino)
        .where(
            AutorizacaoDeTreino.empresa_id == empresa_id, AutorizacaoDeTreino.revogada_em.is_(None)
        )
        .values(revogada_em=agora)
    )
    if not getattr(resultado, "rowcount", 0):
        raise NaoEncontradoError(f"autorização de treino da empresa {empresa_id}")
    apagados = sessao.execute(delete(Rotulo).where(Rotulo.empresa_id == empresa_id))
    guarda.apagar_da_empresa(empresa_id)
    sessao.flush()
    return int(getattr(apagados, "rowcount", 0) or 0)


def autorizacoes(
    sessao: Session, _administracao: AcessoAdmin
) -> list[tuple[Empresa, AutorizacaoDeTreino | None]]:
    """As empresas (menos as de demonstração), cada uma com a autorização ativa, se tiver."""
    ativas = {
        a.empresa_id: a
        for a in sessao.scalars(
            select(AutorizacaoDeTreino).where(AutorizacaoDeTreino.revogada_em.is_(None))
        )
    }
    empresas = sessao.scalars(
        select(Empresa)
        .where(~exists().where(LinkDemonstracao.empresa_id == Empresa.id))
        .order_by(Empresa.nome)
    )
    return [(empresa, ativas.get(empresa.id)) for empresa in empresas]


# --- Rotular --------------------------------------------------------------------------------


def conjunto_de(passagem_id: UUID, foto: int) -> ConjuntoDoRotulo:
    """Treino ou régua, pelo resumo da passagem e da foto: sempre o mesmo para o mesmo recorte."""
    resumo = hashlib.sha256(f"{passagem_id}:{foto}".encode()).digest()
    return "regua" if resumo[0] % UM_EM == 0 else "treino"


def rotular(
    sessao: Session, armazenamento: Armazenamento, guarda: GuardaDoTreino, *, agora: datetime
) -> int:
    """Transforma as conferências autorizadas que ainda não são rótulos (sem ``commit``).

    Returns:
        Quantos rótulos nasceram (os descartados por falta do recorte também contam).
    """
    ultimas = (
        select(func.max(ConferenciaPlaca.id))
        .group_by(ConferenciaPlaca.passagem_id, ConferenciaPlaca.foto)
        .scalar_subquery()
    )
    candidatas = sessao.execute(
        select(ConferenciaPlaca, PassagemRecebida)
        .join(
            PassagemRecebida,
            and_(
                PassagemRecebida.id == ConferenciaPlaca.passagem_id,
                PassagemRecebida.empresa_id == ConferenciaPlaca.empresa_id,
            ),
        )
        .join(
            AutorizacaoDeTreino,
            and_(
                AutorizacaoDeTreino.empresa_id == ConferenciaPlaca.empresa_id,
                AutorizacaoDeTreino.revogada_em.is_(None),
            ),
        )
        .where(
            ConferenciaPlaca.id.in_(ultimas),
            func.date(func.timezone("UTC", ConferenciaPlaca.momento))
            >= AutorizacaoDeTreino.clausula_em,
            ~exists().where(
                Rotulo.passagem_id == ConferenciaPlaca.passagem_id,
                Rotulo.foto == ConferenciaPlaca.foto,
            ),
        )
        .order_by(ConferenciaPlaca.id)
        .limit(ROTULOS_POR_VEZ)
    ).all()
    for conferida, passagem in candidatas:
        rotulo = Rotulo(
            empresa_id=conferida.empresa_id,
            passagem_id=conferida.passagem_id,
            foto=conferida.foto,
            placa=conferida.placa,
            origem="conferencia",
            situacao="a_revisar",
            conjunto=conjunto_de(conferida.passagem_id, conferida.foto),
            criado_em=agora,
        )
        sessao.add(rotulo)
        sessao.flush()
        recorte = armazenamento.ler(
            passagem.caixa_id, passagem.como_veio["fotos"][conferida.foto]["ref"]
        )
        if recorte is None:
            rotulo.situacao, rotulo.revisado_em = "descartado", agora
            continue
        rotulo.recorte = guarda.gravar(conferida.empresa_id, f"{rotulo.id}.jpg", recorte)
        rotulo.resumo = hashlib.sha256(recorte).hexdigest()
    sessao.flush()
    return len(candidatas)


# --- A rotulagem ----------------------------------------------------------------------------


def pendentes(sessao: Session, _administracao: AcessoAdmin, *, limite: int = 20) -> list[Rotulo]:
    """Os rótulos a revisar, dos mais antigos."""
    return list(
        sessao.scalars(
            select(Rotulo).where(Rotulo.situacao == "a_revisar").order_by(Rotulo.id).limit(limite)
        )
    )


def contagem(sessao: Session, _administracao: AcessoAdmin) -> dict[str, int]:
    """Quantos rótulos há em cada situação, e quantos na régua."""
    por_situacao = dict(
        sessao.execute(select(Rotulo.situacao, func.count()).group_by(Rotulo.situacao)).all()
    )
    regua = sessao.scalar(select(func.count()).where(Rotulo.conjunto == "regua")) or 0
    return {
        **{s: por_situacao.get(s, 0) for s in ("a_revisar", "aceito", "corrigido", "descartado")},
        "regua": regua,
    }


def obter_rotulo(sessao: Session, _administracao: AcessoAdmin, rotulo_id: int) -> Rotulo:
    """Um rótulo.

    Raises:
        NaoEncontradoError: se ele não existe.
    """
    rotulo = sessao.get(Rotulo, rotulo_id)
    if rotulo is None:
        raise NaoEncontradoError(f"rótulo {rotulo_id}")
    return rotulo


def revisar(
    sessao: Session,
    administracao: AcessoAdmin,
    rotulo_id: int,
    acao: AcaoDaRevisao,
    *,
    placa: str = "",
    agora: datetime,
) -> Rotulo:
    """Aceita, corrige (com a placa certa) ou descarta um rótulo (sem ``commit``).

    Raises:
        NaoEncontradoError: se o rótulo não existe.
        DadoInvalidoError: se a placa da correção não é uma placa.
    """
    rotulo = obter_rotulo(sessao, administracao, rotulo_id)
    if acao == "corrigir":
        try:
            rotulo.placa = normalizar_placa(placa)
        except PlacaInvalidaError as erro:
            raise DadoInvalidoError(f"placa inválida: {erro}") from erro
    rotulo.situacao = SITUACAO_DEPOIS[acao]
    rotulo.revisado_por = administracao.administrador_id
    rotulo.revisado_em = agora
    sessao.flush()
    return rotulo


# --- A exportação ---------------------------------------------------------------------------


def exportar(sessao: Session, guarda: GuardaDoTreino, destino: Path) -> Exportacao:
    """Monta a pasta do treino: ``treino/`` e ``regua/`` com os recortes, e um CSV de cada.

    Só os aceitos e os corrigidos. A pasta é refeita a cada vez.
    """
    contagem_por_conjunto = {"treino": 0, "regua": 0}
    for conjunto in contagem_por_conjunto:
        shutil.rmtree(destino / conjunto, ignore_errors=True)
        (destino / conjunto).mkdir(parents=True)
    escritores = {}
    arquivos_csv = {}
    for conjunto in contagem_por_conjunto:
        arquivos_csv[conjunto] = (destino / f"{conjunto}.csv").open(
            "w", newline="", encoding="utf-8"
        )
        escritores[conjunto] = csv.writer(arquivos_csv[conjunto], lineterminator="\n")
        escritores[conjunto].writerow(["arquivo", "placa"])
    try:
        for rotulo in sessao.scalars(
            select(Rotulo)
            .where(Rotulo.situacao.in_(("aceito", "corrigido")), Rotulo.recorte.is_not(None))
            .order_by(Rotulo.id)
        ):
            assert rotulo.recorte is not None
            conteudo = guarda.ler(rotulo.recorte)
            if conteudo is None:
                continue
            nome = f"{rotulo.conjunto}/{rotulo.id}.jpg"
            (destino / nome).write_bytes(conteudo)
            escritores[rotulo.conjunto].writerow([nome, rotulo.placa])
            contagem_por_conjunto[rotulo.conjunto] += 1
    finally:
        for arquivo in arquivos_csv.values():
            arquivo.close()
    return Exportacao(treino=contagem_por_conjunto["treino"], regua=contagem_por_conjunto["regua"])

"""A empresa de demonstração do ambiente local: ``uv run tarefas demonstracao``.

Cria a "Distribuidora Exemplo (demonstração)" no banco de desenvolvimento, com o mês de
histórico, para ver o dia de demonstração (D-49) na própria máquina. Precisa da semente (a
administração dela gera o código da caixa). Roda uma vez: se a empresa já existe, não faz nada.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem.banco import criar_motor
from nuvem.cadastro.modelos import Administrador, Empresa
from nuvem.cifra import Cifra
from nuvem.config import ConfiguracaoInvalidaError, ler_configuracao
from nuvem.demonstracao import empresa
from nuvem.demonstracao.empresa import EmpresaDeDemonstracao
from nuvem.semente import PIN_DA_DEMONSTRACAO, SENHA_DA_DEMONSTRACAO
from nuvem.senhas import Senhas

CNPJ_LOCAL = "DEMO0000000D00"
"""Um CNPJ que não existe: as letras DEMO marcam os dados como de demonstração."""
EMAIL_DA_ADMINISTRACAO = "admin@patio-br.example"
"""A administração da semente."""


class SemSementeError(Exception):
    """A semente ainda não foi gravada: falta a administração que gera o código da caixa."""


def criar_a_local(
    sessao: Session,
    senhas: Senhas,
    cifra: Cifra,
    *,
    agora: datetime,
    dias: int = empresa.DIAS_DE_HISTORICO,
) -> EmpresaDeDemonstracao | None:
    """Cria a empresa de demonstração local (sem ``commit``); ``None`` se ela já existe.

    Raises:
        SemSementeError: se a semente ainda não foi gravada.
    """
    if sessao.scalar(select(Empresa).where(Empresa.cnpj == CNPJ_LOCAL)) is not None:
        return None
    administracao = sessao.scalar(
        select(Administrador).where(Administrador.email == EMAIL_DA_ADMINISTRACAO)
    )
    if administracao is None:
        raise SemSementeError("rode antes: uv run tarefas semente")
    return empresa.criar(
        sessao, senhas, cifra, nome="Distribuidora Exemplo (demonstração)", cnpj=CNPJ_LOCAL,
        dominio="demonstracao.example", senha=SENHA_DA_DEMONSTRACAO, pin=PIN_DA_DEMONSTRACAO,
        administrador_id=administracao.id, agora=agora, dias=dias, semente=2026,
    )  # fmt: skip


def principal() -> None:
    """Cria a empresa de demonstração no banco de desenvolvimento (``PATIO_URL_BANCO``)."""
    try:
        configuracao = ler_configuracao()
    except ConfiguracaoInvalidaError as erro:
        raise SystemExit(f"erro: {erro}") from None
    if configuracao.ambiente != "local":
        # As contas têm a senha pública da semente.
        raise SystemExit(
            "erro: a empresa de demonstração local só roda no ambiente local "
            f"(PATIO_AMBIENTE={configuracao.ambiente})"
        )
    motor = criar_motor(configuracao.url_banco.get_secret_value())
    with Session(motor) as sessao:
        try:
            criada = criar_a_local(
                sessao, Senhas(), Cifra(configuracao.chave_cifra), agora=datetime.now(UTC)
            )
        except SemSementeError as erro:
            raise SystemExit(f"erro: {erro}") from None
        sessao.commit()
        if criada is None:
            print("a empresa de demonstração já existia; nada mudou")
        else:
            print(f"empresa de demonstração criada: {criada.empresa.nome}, {criada.site.nome}")
            print(f"entre em /entrar com {criada.gestor.email} e abra o Dia de demonstração")
            print(f"senha de todos: {SENHA_DA_DEMONSTRACAO}; PIN: {PIN_DA_DEMONSTRACAO}")
            print("para o dia andar, deixe o worker rodando (python -m nuvem.worker)")
    motor.dispose()

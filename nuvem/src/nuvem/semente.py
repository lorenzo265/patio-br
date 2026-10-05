"""Dados de demonstração: ``uv run tarefas semente``.

Duas empresas inventadas, para ver a separação na prática:

- **Empresa A**: o site "CD Exemplo" (aberto das 6h às 22h; uma portaria com uma faixa de
  entrada e uma de saída, três câmeras e duas docas), mais o site "CD Exemplo 2", que ninguém da
  A vê; no CD Exemplo, um gestor, um líder de pátio e dois porteiros (dia e noite), e os
  parâmetros do extrato com uma linha de base **de exemplo** (D-48), marcada assim na tela;
- **Empresa B**: o site "CD Outra Empresa", com uma câmera, um gestor e um porteiro;
- **Administração** (nós): uma pessoa, fora das duas empresas.

Todos entram com a senha ``SENHA_DA_DEMONSTRACAO``; os porteiros têm o PIN
``PIN_DA_DEMONSTRACAO``. Os e-mails estão abaixo, em ``semear``.

Os mesmos dados servem de cenário aos testes da nuvem. Roda uma vez: se já existem, não faz
nada. Só para desenvolvimento e demonstração; nunca em produção.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem.banco import criar_motor
from nuvem.cadastro import servico
from nuvem.cadastro.modelos import (
    Administrador,
    Camera,
    Empresa,
    Faixa,
    Papel,
    Portaria,
    Posicao,
    Site,
    Usuario,
)
from nuvem.cifra import Cifra
from nuvem.config import ConfiguracaoInvalidaError, ler_configuracao
from nuvem.extrato import servico as extrato
from nuvem.extrato.contas import Medidas, Parametros
from nuvem.senhas import Senhas

CNPJ_A = "DEMO0000000A00"
CNPJ_B = "DEMO0000000B00"
"""CNPJs que não existem: as letras DEMO marcam os dados como de demonstração."""

SENHA_DAS_CAMERAS = "camera-local"
"""Senha inventada das câmeras de demonstração (gravada cifrada, como qualquer outra)."""

SENHA_DA_DEMONSTRACAO = "demonstracao-local"
"""Senha inventada de todas as pessoas da demonstração (gravada só como resumo)."""

PIN_DA_DEMONSTRACAO = "135790"
"""PIN inventado dos porteiros da demonstração."""

PARAMETROS_DE_EXEMPLO = Parametros(
    postos_antes=Decimal(3), postos_depois=Decimal(2), custo_mensal_do_posto=Decimal("21500.00")
)
"""Três pontos de portaria 24 horas, um a menos depois, pelo menor custo da seção 1.1 do SDD."""

LINHA_DE_BASE_DE_EXEMPLO = Medidas(
    visitas=682,  # 22 por dia em julho
    automaticas=0,
    chamadas=670,
    espera_total=timedelta(minutes=670 * 160),  # 2h40 de espera média
    liberadas=664,
    estadia_total=timedelta(minutes=664 * 265),  # 4h25 de estadia média
    acima_da_franquia=126,  # 19%
    exposicao=Decimal("10290.00"),  # cada uma: ~1h10 acima da franquia, 28 t, R$ 2,50
    sem_toneladas=0,
    horas_de_doca=Decimal("575.4"),  # 58% das horas disponíveis
    horas_disponiveis=Decimal(31 * 16 * 2),  # 31 dias, das 6h às 22h, 2 docas
)
"""Números inventados de um mês antes do sistema, para a demonstração ter com o que comparar."""


@dataclass(frozen=True)
class Demonstracao:
    """O que a semente gravou, para os testes e para quem quiser olhar."""

    empresa_a: Empresa
    empresa_b: Empresa
    site_a: Site
    site_a2: Site
    """Da empresa A, mas fora do alcance do gestor A."""
    site_b: Site
    portaria_a: Portaria
    faixa_a: Faixa
    """A faixa de entrada do site A."""
    camera_a: Camera
    camera_b: Camera
    gestor_a: Usuario
    patio_a: Usuario
    porteiro_a: Usuario
    porteiro_a_noite: Usuario
    gestor_b: Usuario
    porteiro_b: Usuario
    administrador: Administrador


def semear(sessao: Session, cifra: Cifra, senhas: Senhas) -> Demonstracao | None:
    """Grava os dados de demonstração (sem commit).

    Returns:
        O que foi gravado, ou ``None`` se os dados já existiam.
    """
    if sessao.scalar(select(Empresa).where(Empresa.cnpj == CNPJ_A)) is not None:
        return None

    empresa_a = servico.criar_empresa(sessao, nome="Empresa A (demonstração)", cnpj=CNPJ_A)
    site_a = servico.criar_site(sessao, empresa_a, nome="CD Exemplo", abre=time(6), fecha=time(22))
    site_a2 = servico.criar_site(sessao, empresa_a, nome="CD Exemplo 2")
    portaria_a = servico.criar_portaria(sessao, site_a, nome="Portaria principal")
    entrada = servico.criar_faixa(sessao, portaria_a, nome="Entrada 1", sentido="entrada")
    saida = servico.criar_faixa(sessao, portaria_a, nome="Saída 1", sentido="saida")
    camera_a = _camera(sessao, cifra, entrada, "Entrada 1 — frente", "frente", "10.0.0.11")
    _camera(sessao, cifra, entrada, "Entrada 1 — traseira", "tras", "10.0.0.12")
    _camera(sessao, cifra, saida, "Saída 1 — traseira", "tras", "10.0.0.13")
    for nome in ("Doca 1", "Doca 2"):
        servico.criar_doca(sessao, site_a, nome=nome)
    agora = datetime.now(UTC)
    extrato.gravar_parametros(sessao, site_a, PARAMETROS_DE_EXEMPLO, agora=agora)
    extrato.gravar_linha_de_base(
        sessao, site_a, "exemplo",
        de=datetime(2026, 7, 1, 3, tzinfo=UTC), ate=datetime(2026, 8, 1, 3, tzinfo=UTC),
        medidas=LINHA_DE_BASE_DE_EXEMPLO, agora=agora,
    )  # fmt: skip

    def pessoa_a(nome: str, email: str, papel: Papel) -> Usuario:
        return _pessoa(sessao, senhas, empresa_a, site_a, nome, f"{email}@empresa-a.example", papel)

    gestor_a = pessoa_a("Gestor A", "gestor", "gestor")
    patio_a = pessoa_a("Pátio A", "patio", "patio")
    porteiro_a = pessoa_a("Porteiro A", "porteiro", "porteiro")
    porteiro_a_noite = pessoa_a("Porteiro A (noite)", "porteiro-noite", "porteiro")

    empresa_b = servico.criar_empresa(sessao, nome="Empresa B (demonstração)", cnpj=CNPJ_B)
    site_b = servico.criar_site(sessao, empresa_b, nome="CD Outra Empresa")
    portaria_b = servico.criar_portaria(sessao, site_b, nome="Portaria")
    entrada_b = servico.criar_faixa(sessao, portaria_b, nome="Entrada", sentido="entrada")
    camera_b = _camera(sessao, cifra, entrada_b, "Entrada — frente", "frente", "10.1.0.11")
    gestor_b = _pessoa(
        sessao, senhas, empresa_b, site_b, "Gestor B", "gestor@empresa-b.example", "gestor"
    )
    porteiro_b = _pessoa(
        sessao, senhas, empresa_b, site_b, "Porteiro B", "porteiro@empresa-b.example", "porteiro"
    )

    administrador = servico.criar_administrador(
        sessao,
        senhas,
        nome="Administração (demonstração)",
        email="admin@patio-br.example",
        senha=SENHA_DA_DEMONSTRACAO,
    )

    return Demonstracao(
        empresa_a=empresa_a,
        empresa_b=empresa_b,
        site_a=site_a,
        site_a2=site_a2,
        site_b=site_b,
        portaria_a=portaria_a,
        faixa_a=entrada,
        camera_a=camera_a,
        camera_b=camera_b,
        gestor_a=gestor_a,
        patio_a=patio_a,
        porteiro_a=porteiro_a,
        porteiro_a_noite=porteiro_a_noite,
        gestor_b=gestor_b,
        porteiro_b=porteiro_b,
        administrador=administrador,
    )


def _pessoa(
    sessao: Session,
    senhas: Senhas,
    empresa: Empresa,
    site: Site,
    nome: str,
    email: str,
    papel: Papel,
) -> Usuario:
    # E-mails no domínio .example, que não existe; todos com a senha da demonstração.
    usuario = servico.criar_usuario(
        sessao,
        senhas,
        empresa,
        nome=nome,
        email=email,
        papel=papel,
        sites=[site],
        senha=SENHA_DA_DEMONSTRACAO,
    )
    if papel == "porteiro":
        servico.definir_pin(sessao, senhas, usuario, PIN_DA_DEMONSTRACAO)
    return usuario


def _camera(
    sessao: Session, cifra: Cifra, faixa: Faixa, nome: str, posicao: Posicao, ip: str
) -> Camera:
    return servico.criar_camera(
        sessao,
        cifra,
        faixa,
        nome=nome,
        posicao=posicao,
        endereco=f"rtsp://{ip}:554/stream1",
        login="leitura",
        senha=SENHA_DAS_CAMERAS,
    )


def principal() -> None:
    """Grava os dados de demonstração no banco de desenvolvimento (``PATIO_URL_BANCO``)."""
    try:
        configuracao = ler_configuracao()
    except ConfiguracaoInvalidaError as erro:
        raise SystemExit(f"erro: {erro}") from None
    if configuracao.ambiente != "local":
        # As contas da demonstração têm senha pública, inclusive a da administração.
        raise SystemExit(
            f"erro: a semente roda só no ambiente local (PATIO_AMBIENTE={configuracao.ambiente})"
        )
    motor = criar_motor(configuracao.url_banco.get_secret_value())
    with Session(motor) as sessao:
        demonstracao = semear(sessao, Cifra(configuracao.chave_cifra), Senhas())
        sessao.commit()
        if demonstracao is None:
            print("os dados de demonstração já existiam; nada mudou")
        else:
            # Ainda com a sessão aberta: depois do commit, os registros são relidos do banco.
            print("dados de demonstração gravados: empresas A e B (ver nuvem/src/nuvem/semente.py)")
            print(f"entre em /entrar com {demonstracao.gestor_a.email} (ou outro e-mail dali)")
            print(f"senha de todos: {SENHA_DA_DEMONSTRACAO}; PIN: {PIN_DA_DEMONSTRACAO}")
    motor.dispose()


if __name__ == "__main__":
    principal()

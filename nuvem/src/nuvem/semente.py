"""Dados de demonstração: ``uv run tarefas semente``.

Duas empresas inventadas, para ver a separação na prática:

- **Empresa A**: o site "CD Exemplo" (uma portaria com uma faixa de entrada e uma de saída, três
  câmeras e duas docas), mais o site "CD Exemplo 2", que o gestor A não vê;
- **Empresa B**: o site "CD Outra Empresa", com uma câmera.

Os mesmos dados servem de cenário aos testes da nuvem. Roda uma vez: se já existem, não faz
nada. Só para desenvolvimento e demonstração; nunca em produção.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from nuvem.banco import criar_motor
from nuvem.cadastro import servico
from nuvem.cadastro.modelos import Camera, Empresa, Faixa, Portaria, Posicao, Site, Usuario
from nuvem.cifra import Cifra
from nuvem.config import ConfiguracaoInvalidaError, ler_configuracao

CNPJ_A = "DEMO0000000A00"
CNPJ_B = "DEMO0000000B00"
"""CNPJs que não existem: as letras DEMO marcam os dados como de demonstração."""

SENHA_DAS_CAMERAS = "camera-local"
"""Senha inventada das câmeras de demonstração (gravada cifrada, como qualquer outra)."""


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
    gestor_b: Usuario


def semear(sessao: Session, cifra: Cifra) -> Demonstracao | None:
    """Grava os dados de demonstração (sem commit).

    Returns:
        O que foi gravado, ou ``None`` se os dados já existiam.
    """
    if sessao.scalar(select(Empresa).where(Empresa.cnpj == CNPJ_A)) is not None:
        return None

    empresa_a = servico.criar_empresa(sessao, nome="Empresa A (demonstração)", cnpj=CNPJ_A)
    site_a = servico.criar_site(sessao, empresa_a, nome="CD Exemplo")
    site_a2 = servico.criar_site(sessao, empresa_a, nome="CD Exemplo 2")
    portaria_a = servico.criar_portaria(sessao, site_a, nome="Portaria principal")
    entrada = servico.criar_faixa(sessao, portaria_a, nome="Entrada 1", sentido="entrada")
    saida = servico.criar_faixa(sessao, portaria_a, nome="Saída 1", sentido="saida")
    camera_a = _camera(sessao, cifra, entrada, "Entrada 1 — frente", "frente", "10.0.0.11")
    _camera(sessao, cifra, entrada, "Entrada 1 — traseira", "tras", "10.0.0.12")
    _camera(sessao, cifra, saida, "Saída 1 — traseira", "tras", "10.0.0.13")
    for nome in ("Doca 1", "Doca 2"):
        servico.criar_doca(sessao, site_a, nome=nome)
    gestor_a = servico.criar_usuario(
        sessao,
        empresa_a,
        nome="Gestor A",
        email="gestor@empresa-a.example",
        papel="gestor",
        sites=[site_a],
    )
    servico.criar_usuario(
        sessao,
        empresa_a,
        nome="Porteiro A",
        email="porteiro@empresa-a.example",
        papel="porteiro",
        sites=[site_a],
    )

    empresa_b = servico.criar_empresa(sessao, nome="Empresa B (demonstração)", cnpj=CNPJ_B)
    site_b = servico.criar_site(sessao, empresa_b, nome="CD Outra Empresa")
    portaria_b = servico.criar_portaria(sessao, site_b, nome="Portaria")
    entrada_b = servico.criar_faixa(sessao, portaria_b, nome="Entrada", sentido="entrada")
    camera_b = _camera(sessao, cifra, entrada_b, "Entrada — frente", "frente", "10.1.0.11")
    gestor_b = servico.criar_usuario(
        sessao,
        empresa_b,
        nome="Gestor B",
        email="gestor@empresa-b.example",
        papel="gestor",
        sites=[site_b],
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
        gestor_b=gestor_b,
    )


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
    motor = criar_motor(configuracao.url_banco.get_secret_value())
    with Session(motor) as sessao:
        demonstracao = semear(sessao, Cifra(configuracao.chave_cifra))
        sessao.commit()
    motor.dispose()
    if demonstracao is None:
        print("os dados de demonstração já existiam; nada mudou")
    else:
        print("dados de demonstração gravados: empresas A e B (veja nuvem/src/nuvem/semente.py)")


if __name__ == "__main__":
    principal()

"""A empresa de demonstração (D-49): um site completo, inventado, com um mês de histórico.

- **Cadastro:** a empresa, o "CD Demonstração" (das 6h às 22h, 6 docas), a portaria com uma faixa
  de entrada e uma de saída, as câmeras (endereços que não existem), o gestor, o porteiro e o
  líder de pátio, e uma caixa de borda ativada, que o dia de demonstração usa para mandar as
  passagens.
- **Histórico:** os dias passados, já fechados (todos saíram), gravados de uma vez.
- **Linha de base de exemplo:** um mês inventado "antes do sistema" (o ritmo ``ANTES``), medido
  pelas contas do extrato; fica marcada como exemplo (D-48).
- **Celulares:** do DDD 23, que não existe; nenhum número pode ser de alguém.

As funções gravam com ``flush``; o ``commit`` é de quem chama.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from nuvem.agendamento import servico as agendamentos
from nuvem.agendamento.servico import AgendamentoInventado, SiteDoAgendamento
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.modelos import Doca, Empresa, Faixa, Papel, Posicao, Site, Usuario
from nuvem.cifra import Cifra
from nuvem.demonstracao import historico
from nuvem.demonstracao.historico import ANTES, COM_O_SISTEMA, Jornada
from nuvem.extrato import contas
from nuvem.extrato import servico as extrato
from nuvem.extrato.contas import Parametros, VisitaMedida
from nuvem.frota import servico as frota
from nuvem.portaria import visitas
from nuvem.portaria.visitas import SiteDaVisita, VisitaInventada
from nuvem.senhas import Senhas

DOCAS = 6
CAMINHOES_POR_DIA = 55
"""Em média; cada dia varia até 8 para mais ou para menos."""
DIAS_DE_HISTORICO = 35
DIAS_DA_LINHA_DE_BASE = 30
ABRE, FECHA = time(6), time(22)
NOME_DO_SITE = "CD Demonstração"
DDD_QUE_NAO_EXISTE = "23"
SENHA_DAS_CAMERAS = "camera-demonstracao"
PARAMETROS = Parametros(
    postos_antes=Decimal(3), postos_depois=Decimal(2), custo_mensal_do_posto=Decimal("21500.00")
)
"""Três pontos de portaria 24 horas, um a menos depois, pelo menor custo da seção 1.1 do SDD."""


@dataclass(frozen=True)
class EmpresaDeDemonstracao:
    """O que foi criado: quem entra e a caixa que manda as passagens."""

    empresa: Empresa
    site: Site
    gestor: Usuario
    porteiro: Usuario
    lider: Usuario
    caixa_id: int


@dataclass(frozen=True)
class Lugar:
    """O site e quem faz cada coisa, para gravar as jornadas."""

    empresa_id: int
    site_id: int
    docas: tuple[Doca, ...]
    porteiro_id: int
    lider_id: int


def criar(
    sessao: Session,
    senhas: Senhas,
    cifra: Cifra,
    *,
    nome: str,
    cnpj: str,
    dominio: str,
    senha: str,
    pin: str,
    administrador_id: int,
    agora: datetime,
    dias: int = DIAS_DE_HISTORICO,
    semente: int = 0,
) -> EmpresaDeDemonstracao:
    """Cria uma empresa de demonstração inteira, com os ``dias`` passados de histórico.

    Args:
        dominio: o fim dos e-mails das pessoas (ex.: ``demo1.demonstracao.example``).
        administrador_id: quem gera o código de ativação da caixa (a administração).
        semente: a mesma semente dá a mesma empresa.
    """
    gerador = random.Random(semente)
    empresa = cadastro.criar_empresa(sessao, nome=nome, cnpj=cnpj)
    site = cadastro.criar_site(sessao, empresa, nome=NOME_DO_SITE, abre=ABRE, fecha=FECHA)
    portaria = cadastro.criar_portaria(sessao, site, nome="Portaria principal")
    entrada = cadastro.criar_faixa(sessao, portaria, nome="Entrada", sentido="entrada")
    saida = cadastro.criar_faixa(sessao, portaria, nome="Saída", sentido="saida")
    cameras: tuple[tuple[Faixa, Posicao, int], ...] = (
        (entrada, "frente", 11), (entrada, "tras", 12), (saida, "tras", 13),
    )  # fmt: skip
    for faixa, posicao, final in cameras:
        _camera(sessao, cifra, faixa, posicao, final)
    docas = tuple(cadastro.criar_doca(sessao, site, nome=f"Doca {n}") for n in range(1, DOCAS + 1))

    def pessoa(nome_da_pessoa: str, papel: Papel) -> Usuario:
        usuario = cadastro.criar_usuario(
            sessao, senhas, empresa, nome=nome_da_pessoa, email=f"{papel}@{dominio}",
            papel=papel, sites=[site], senha=senha,
        )  # fmt: skip
        if papel == "porteiro":
            cadastro.definir_pin(sessao, senhas, usuario, pin)
        return usuario

    gestor = pessoa("Gestor (demonstração)", "gestor")
    porteiro = pessoa("Porteiro (demonstração)", "porteiro")
    lider = pessoa("Líder de pátio (demonstração)", "patio")
    codigo = frota.gerar_codigo_de_ativacao(
        sessao, site.id, administrador_id=administrador_id, agora=agora
    )
    caixa = frota.ativar(sessao, codigo.codigo, agora=agora)
    extrato.gravar_parametros(sessao, site, PARAMETROS, agora=agora)

    lugar = Lugar(empresa.id, site.id, docas, porteiro.id, lider.id)
    fuso = ZoneInfo(site.fuso)
    hoje = agora.astimezone(fuso).date()
    placas: set[str] = set()
    for atras in range(dias, 0, -1):
        dia = hoje - timedelta(days=atras)
        gravar_jornadas(sessao, lugar, dia_inventado(dia, fuso, gerador, placas), agora=agora,
                        prefixo=f"DEMO-{dia:%Y%m%d}")  # fmt: skip
    _gravar_linha_de_base(sessao, site, fuso, hoje - timedelta(days=dias), gerador, agora)
    return EmpresaDeDemonstracao(empresa, site, gestor, porteiro, lider, caixa.caixa_id)


def dia_inventado(
    dia: date, fuso: ZoneInfo, gerador: random.Random, placas: set[str]
) -> list[Jornada]:
    """Os caminhões de um dia do CD Demonstração, com o sistema."""
    caminhoes = gerador.randint(CAMINHOES_POR_DIA - 8, CAMINHOES_POR_DIA + 8)
    return historico.jornadas_do_dia(
        dia, fuso=fuso, docas=DOCAS, caminhoes=caminhoes, ritmo=COM_O_SISTEMA, gerador=gerador,
        placas_usadas=placas,
    )  # fmt: skip


def gravar_jornadas(
    sessao: Session, lugar: Lugar, jornadas: Sequence[Jornada], *, agora: datetime, prefixo: str
) -> None:
    """Grava o agendamento de cada jornada e, das que já chegaram até ``agora``, a visita, até
    onde ela foi (a etapa que ainda não aconteceu fica de fora)."""
    gerador = random.Random(prefixo)
    inventados = [
        AgendamentoInventado(
            codigo_externo=f"{prefixo}-{numero:03d}", janela_inicio=j.janela_inicio,
            janela_fim=j.janela_fim, tipo=j.tipo, placa_cavalo=j.placa, toneladas=j.toneladas,
            motorista_celular=celular_inventado(gerador),
        )
        for numero, j in enumerate(jornadas, start=1)
    ]  # fmt: skip
    ids = agendamentos.gravar_inventados(
        sessao, SiteDoAgendamento(lugar.empresa_id, lugar.site_id, None), inventados
    )
    chegaram = [(i, j) for i, j in zip(ids, jornadas, strict=True) if j.chegada <= agora]
    visitas.gravar_inventadas(
        sessao,
        SiteDaVisita(empresa_id=lugar.empresa_id, site_id=lugar.site_id),
        [_ate_agora(i, j, lugar, agora) for i, j in chegaram],
        porteiro_id=lugar.porteiro_id,
        lider_id=lugar.lider_id,
    )


def celular_inventado(gerador: random.Random) -> str:
    """Um celular do DDD 23, que não existe (o Rio usa 21, 22 e 24)."""
    return f"+55{DDD_QUE_NAO_EXISTE}9{gerador.randint(0, 99_999_999):08d}"


def _ate_agora(agendamento_id: int, j: Jornada, lugar: Lugar, agora: datetime) -> VisitaInventada:
    def se_ja(momento: datetime) -> datetime | None:
        return momento if momento <= agora else None

    chamada = se_ja(j.chamada)
    doca = lugar.docas[j.doca] if chamada is not None else None
    return VisitaInventada(
        agendamento_id=agendamento_id, placa=j.placa, chegada=j.chegada, automatica=j.automatica,
        chamada=chamada, doca_id=doca.id if doca else None, doca=doca.nome if doca else None,
        inicio=se_ja(j.inicio), fim=se_ja(j.fim), saida=se_ja(j.saida),
    )  # fmt: skip


def _gravar_linha_de_base(
    sessao: Session,
    site: Site,
    fuso: ZoneInfo,
    antes_de: date,
    gerador: random.Random,
    agora: datetime,
) -> None:
    """Um mês "antes do sistema", só nas contas: as visitas dele não são gravadas."""
    inicio = antes_de - timedelta(days=DIAS_DA_LINHA_DE_BASE)
    medidas_das_visitas = []
    placas: set[str] = set()
    for numero in range(DIAS_DA_LINHA_DE_BASE):
        caminhoes = gerador.randint(CAMINHOES_POR_DIA - 8, CAMINHOES_POR_DIA + 8)
        for j in historico.jornadas_do_dia(
            inicio + timedelta(days=numero), fuso=fuso, docas=DOCAS, caminhoes=caminhoes,
            ritmo=ANTES, gerador=gerador, placas_usadas=placas,
        ):  # fmt: skip
            medidas_das_visitas.append(
                VisitaMedida(j.chegada, j.chamada, j.inicio, j.fim, j.saida, j.toneladas, False)
            )
    de, ate = datetime.combine(inicio, time(0), fuso), datetime.combine(antes_de, time(0), fuso)
    disponiveis = contas.horas_disponiveis(de, ate, fuso=fuso, abre=ABRE, fecha=FECHA, docas=DOCAS)
    medidas = contas.medir(
        medidas_das_visitas, de=de, ate=ate, parametros=PARAMETROS, horas_disponiveis=disponiveis
    )
    extrato.gravar_linha_de_base(sessao, site, "exemplo", de=de, ate=ate, medidas=medidas,
                                 agora=agora)  # fmt: skip


def _camera(sessao: Session, cifra: Cifra, faixa: Faixa, posicao: Posicao, final: int) -> None:
    # Endereços da faixa de documentação (198.51.100.0/24): não levam a câmera nenhuma.
    cadastro.criar_camera(
        sessao, cifra, faixa, nome=f"{faixa.nome} — {posicao}", posicao=posicao,
        endereco=f"rtsp://198.51.100.{final}:554/stream1", login="leitura",
        senha=SENHA_DAS_CAMERAS,
    )  # fmt: skip

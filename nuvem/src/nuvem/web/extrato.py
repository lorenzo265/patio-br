"""O painel do gestor e o extrato do mês (T44, SDD 6.2 e D-48).

- ``/painel``: o dia, o mês até agora contra a linha de base e um gráfico de barras por dia.
- ``/extrato?mes=aaaa-mm``: o extrato em R$, para ler, imprimir ou salvar em PDF.
- ``/extrato.csv?mes=aaaa-mm``: o mesmo extrato em planilha (``;`` e vírgula decimal, como o
  Excel em português abre).

Só o gestor vê. A linha de base de exemplo (a da demonstração) aparece marcada assim.
"""

import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from nuvem.banco import obter_sessao
from nuvem.cadastro import servico as cadastro
from nuvem.cadastro.acesso import Acesso, exigir_papel
from nuvem.cadastro.modelos import Site
from nuvem.extrato import servico as extrato
from nuvem.extrato.contas import Medidas
from nuvem.extrato.servico import ExtratoDoMes, LinhaDeBaseLida, MesFuturoError
from nuvem.patio import servico as patio
from nuvem.relogio import agora
from nuvem.web.rotas import tela

roteador = APIRouter(include_in_schema=False)

SessaoDaRequisicao = Annotated[Session, Depends(obter_sessao)]
AcessoDoGestor = Annotated[Acesso, Depends(exigir_papel("gestor"))]
Agora = Annotated[datetime, Depends(agora)]
Mes = Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro")  # fmt: skip
VAZIO = "—"


@roteador.get("/painel")
def painel(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoGestor,
    momento: Agora,
    site: int | None = None,
) -> HTMLResponse:
    """O dia, o mês até agora e cada dia do mês de um site do gestor."""
    escolhido = _site(sessao, acesso, site)
    if escolhido is None:
        return tela(request, "aviso.html", {"mensagem": "Você não está ligado a nenhum site."})
    atual = extrato.painel(sessao, acesso, escolhido.id, agora=momento)
    quadro = patio.quadro(sessao, acesso, escolhido.id, agora=momento)
    fuso = ZoneInfo(escolhido.fuso)
    mais_chegadas = max((d.medidas.visitas for d in atual.dias), default=0) or 1
    maior_espera = max((d.medidas.espera_media or timedelta(0) for d in atual.dias),
                       default=timedelta(0)) or timedelta(minutes=1)  # fmt: skip
    contexto = {
        "site": escolhido,
        "outros_sites": _outros(sessao, acesso, escolhido),
        "hoje": f"{momento.astimezone(fuso):%d/%m}",
        "mes_nome": MESES[atual.mes.mes.month - 1].capitalize(),
        "mes_param": f"{atual.mes.mes:%Y-%m}",
        "dia": _medidas(atual.hoje),
        "na_fila": len(quadro.fila),
        "docas_ocupadas": sum(d.caminhao is not None for d in quadro.docas),
        "docas": len(quadro.docas),
        "linhas": _comparacao(atual.mes),
        "base": _base(atual.mes.linha_de_base, fuso),
        "economia": _reais(atual.mes.economia.total) if atual.mes.economia else None,
        "barras": [
            {
                "dia": f"{d.dia:%d/%m}",
                "chegadas": d.medidas.visitas,
                "altura_chegadas": round(100 * d.medidas.visitas / mais_chegadas),
                "espera": _duracao(d.medidas.espera_media),
                "altura_espera": round(
                    100 * (d.medidas.espera_media or timedelta(0)) / maior_espera
                ),
            }
            for d in atual.dias
        ],
    }
    return tela(request, "painel.html", contexto)


@roteador.get("/extrato")
def extrato_do_mes(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoGestor,
    momento: Agora,
    site: int | None = None,
    mes: Mes = None,
) -> HTMLResponse:
    """O extrato em R$ de um mês (o atual, se nenhum for pedido)."""
    escolhido = _site(sessao, acesso, site)
    if escolhido is None:
        return tela(request, "aviso.html", {"mensagem": "Você não está ligado a nenhum site."})
    pedido = _mes(mes, momento, escolhido)
    try:
        atual = extrato.do_mes(sessao, acesso, escolhido.id, pedido, agora=momento)
    except MesFuturoError:
        return _nao_comecou(request, pedido)
    sessao.commit()  # o mês fechado fica guardado
    fuso = ZoneInfo(escolhido.fuso)
    anterior = (pedido - timedelta(days=1)).replace(day=1)
    seguinte = (pedido + timedelta(days=32)).replace(day=1)
    contexto = {
        "site": escolhido,
        "outros_sites": _outros(sessao, acesso, escolhido),
        "titulo": f"Extrato de {_nome_do_mes(pedido)}",
        "mes_param": f"{pedido:%Y-%m}",
        "parcial": f"{atual.ate.astimezone(fuso):%d/%m às %H:%M}" if atual.parcial else None,
        "anterior": {"param": f"{anterior:%Y-%m}", "nome": _nome_do_mes(anterior)},
        "seguinte": None if atual.parcial else {
            "param": f"{seguinte:%Y-%m}", "nome": _nome_do_mes(seguinte),
        },
        "base": _base(atual.linha_de_base, fuso),
        "linhas": _comparacao(atual),
        "economia": _economia(atual),
        "sem_toneladas": atual.medidas.sem_toneladas,
        "versao": atual.versao_da_regra,
        "guardado_em": (
            f"{atual.guardado_em.astimezone(fuso):%d/%m/%Y às %H:%M}" if atual.guardado_em else None
        ),
    }  # fmt: skip
    return tela(request, "extrato.html", contexto)


@roteador.get("/extrato.csv", response_model=None)
def planilha(
    request: Request,
    sessao: SessaoDaRequisicao,
    acesso: AcessoDoGestor,
    momento: Agora,
    site: int | None = None,
    mes: Mes = None,
) -> Response:
    """O extrato de um mês em planilha."""
    escolhido = _site(sessao, acesso, site)
    if escolhido is None:
        return tela(request, "aviso.html", {"mensagem": "Você não está ligado a nenhum site."})
    pedido = _mes(mes, momento, escolhido)
    try:
        atual = extrato.do_mes(sessao, acesso, escolhido.id, pedido, agora=momento)
    except MesFuturoError:
        return _nao_comecou(request, pedido)
    sessao.commit()
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\n")
    for linha in _linhas_da_planilha(atual, ZoneInfo(escolhido.fuso)):
        escritor.writerow(linha)
    return Response(
        saida.getvalue().encode("utf-8-sig"),  # com a marca do UTF-8: o Excel lê os acentos
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="extrato-{pedido:%Y-%m}.csv"'},
    )


# --- Por dentro -------------------------------------------------------------------------------


def _site(sessao: Session, acesso: Acesso, site_id: int | None) -> Site | None:
    if site_id is not None:
        return cadastro.obter_site(sessao, acesso, site_id)
    sites = cadastro.listar_sites(sessao, acesso)
    return sites[0] if sites else None


def _outros(sessao: Session, acesso: Acesso, escolhido: Site) -> list[Site]:
    return [s for s in cadastro.listar_sites(sessao, acesso) if s.id != escolhido.id]


def _mes(mes: str | None, momento: datetime, site: Site) -> date:
    if mes is None:
        return momento.astimezone(ZoneInfo(site.fuso)).date().replace(day=1)
    ano, numero = mes.split("-")
    return date(int(ano), int(numero), 1)


def _nao_comecou(request: Request, mes: date) -> HTMLResponse:
    mensagem = f"{_nome_do_mes(mes).capitalize()} ainda não começou."
    return tela(request, "aviso.html", {"mensagem": mensagem}, status.HTTP_404_NOT_FOUND)


def _nome_do_mes(mes: date) -> str:
    return f"{MESES[mes.month - 1]} de {mes.year}"


def _base(base: LinhaDeBaseLida | None, fuso: ZoneInfo) -> dict[str, str] | None:
    if base is None:
        return None
    ultimo_dia = (base.ate - timedelta(seconds=1)).astimezone(fuso)
    rotulo = "Linha de base de exemplo" if base.origem == "exemplo" else "Linha de base"
    detalhe = (
        "números inventados para a demonstração"
        if base.origem == "exemplo"
        else "medida no modo sombra"
    )
    periodo = f"{base.de.astimezone(fuso):%d/%m/%Y} a {ultimo_dia:%d/%m/%Y}"
    return {"rotulo": rotulo, "detalhe": detalhe, "periodo": periodo}


def _medidas(medidas: Medidas) -> dict[str, Any]:
    return {
        "visitas": medidas.visitas,
        "automatico": _pct(medidas.pct_automatico),
        "espera": _duracao(medidas.espera_media),
        "estadia": _duracao(medidas.estadia_media),
        "acima": _pct(medidas.pct_acima_da_franquia),
        "exposicao": _reais(medidas.exposicao_por_liberada),
        "docas": _pct(medidas.uso_das_docas),
    }


def _comparacao(atual: ExtratoDoMes) -> list[dict[str, Any]]:
    base = _medidas(atual.linha_de_base.medidas) if atual.linha_de_base else {}
    mes = _medidas(atual.medidas)
    nomes = {
        "visitas": "Visitas",
        "automatico": "Check-in automático",
        "espera": "Espera média (até a chamada)",
        "estadia": "Estadia média (até a liberação)",
        "acima": "Liberadas acima de 5 horas",
        "exposicao": "Exposição a estadia por visita liberada",
        "docas": "Uso das docas",
    }
    return [
        {"nome": nome, "base": base.get(chave, VAZIO), "mes": mes[chave]}
        for chave, nome in nomes.items()
    ]


def _economia(atual: ExtratoDoMes) -> dict[str, Any] | None:
    economia = atual.economia
    if economia is None:
        return None
    parametros = atual.parametros
    postos = None
    if parametros.postos_antes is not None and parametros.postos_depois is not None:
        a_menos = parametros.postos_antes - parametros.postos_depois
        postos = f"{_numero(a_menos)} {'posto' if a_menos == 1 else 'postos'} a menos"
    return {
        "total": _reais(economia.total),
        "estadia": _reais(economia.estadia),
        "portaria": _reais(economia.portaria),
        "postos": postos,
        "docas": _reais(economia.docas) if economia.docas is not None else None,
        "horas_de_espera": _horas_de_espera(economia.horas_de_espera),
    }  # fmt: skip


def _horas_de_espera(horas: Decimal | None) -> str:
    """Ex.: 100,5 h; negativo, 12,1 h a mais (o mês esperou mais que a linha de base)."""
    if horas is None:
        return VAZIO
    return f"{_numero(horas)} h" if horas >= 0 else f"{_numero(-horas)} h a mais"


def _linhas_da_planilha(atual: ExtratoDoMes, fuso: ZoneInfo) -> list[list[str]]:
    base = atual.linha_de_base.medidas if atual.linha_de_base else None

    def linha(nome: str, valor: Any) -> list[str]:
        return [nome, _celula(valor(base)) if base else "", _celula(valor(atual.medidas))]

    linhas = [["Medida", "Linha de base", "Mês"]]
    if atual.linha_de_base:
        linhas.append(["Origem da linha de base", atual.linha_de_base.origem, ""])
    if atual.parcial:
        linhas.append(["Parcial até", "", f"{atual.ate.astimezone(fuso):%d/%m/%Y %H:%M}"])
    linhas += [
        linha("Visitas", lambda m: m.visitas),
        linha("Check-in automático (%)", lambda m: m.pct_automatico),
        linha("Espera média (min)", lambda m: _minutos(m.espera_media)),
        linha("Estadia média (min)", lambda m: _minutos(m.estadia_media)),
        linha("Liberadas acima de 5 horas", lambda m: m.acima_da_franquia),
        linha("Liberadas acima de 5 horas (%)", lambda m: m.pct_acima_da_franquia),
        linha("Exposição a estadia (R$)", lambda m: m.exposicao),
        linha("Exposição por visita liberada (R$)", lambda m: m.exposicao_por_liberada),
        linha("Liberadas sem toneladas", lambda m: m.sem_toneladas),
        linha("Uso das docas (%)", lambda m: m.uso_das_docas),
    ]
    economia = atual.economia
    if economia is not None:
        linhas += [
            ["Economia com a estadia (R$)", "", _celula(economia.estadia)],
            ["Economia com a portaria (R$)", "", _celula(economia.portaria)],
            ["Economia com as docas (R$)", "", _celula(economia.docas)],
            ["Economia total (R$)", "", _celula(economia.total)],
            ["Horas de espera poupadas", "", _celula(economia.horas_de_espera)],
        ]
    linhas.append(["Versão da regra", "", str(atual.versao_da_regra)])
    return linhas


def _celula(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, Decimal):
        return str(valor).replace(".", ",")
    return str(valor)


def _minutos(tempo: timedelta | None) -> int | None:
    return None if tempo is None else int(tempo.total_seconds() // 60)


def _duracao(tempo: timedelta | None) -> str:
    """Ex.: 2h40; vazio vira um traço."""
    if tempo is None:
        return VAZIO
    minutos = int(tempo.total_seconds() // 60)
    return f"{minutos // 60}h{minutos % 60:02d}"


def _pct(valor: Decimal | None) -> str:
    """Ex.: 58,0%."""
    return VAZIO if valor is None else f"{_com_virgula(f'{valor:,.1f}')}%"


def _numero(valor: Decimal) -> str:
    """Ex.: 1234.5 vira 1.234,5 (sem casas, se for inteiro)."""
    return _com_virgula(
        f"{int(valor):,}" if valor == valor.to_integral_value() else f"{valor:,.1f}"
    )


def _com_virgula(texto: str) -> str:
    """Do jeito do Brasil: 1,234.5 vira 1.234,5."""
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def _reais(valor: Decimal | None) -> str:
    """Ex.: R$ 21.500,00; negativo, -R$ 10,00."""
    if valor is None:
        return VAZIO
    texto = _com_virgula(f"{abs(valor):,.2f}")
    return f"{'-' if valor < 0 else ''}R$ {texto}"

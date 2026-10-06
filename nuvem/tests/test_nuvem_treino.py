"""A base de treino (SDD 4.6 e 8.3, D-71): a conferência do porteiro vira rótulo, com o contrato."""

import csv
import hashlib
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from contratos.passagem import Passagem
from nuvem.armazenamento import ArmazenamentoLocal
from nuvem.cadastro.acesso import AcessoAdmin, acesso_do_usuario
from nuvem.cifra import Cifra
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.frota.servico import CaixaAtivada
from nuvem.portaria import conferencia
from nuvem.semente import Demonstracao
from nuvem.senhas import Senhas
from nuvem.treino import servico as treino
from nuvem.treino.guarda import TreinoNoDisco
from nuvem.treino.modelos import AutorizacaoDeTreino, Rotulo

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 17, 10, tzinfo=UTC)
CLAUSULA = date(2026, 10, 1)
FOTO = b"\xff\xd8\xff" + b"recorte inventado"


@pytest.fixture
def armazenamento(tmp_path: Path, cifra: Cifra) -> ArmazenamentoLocal:
    return ArmazenamentoLocal(tmp_path / "fotos", cifra)


@pytest.fixture
def base(tmp_path: Path) -> TreinoNoDisco:
    return TreinoNoDisco(tmp_path / "fotos")


@pytest.fixture
def administracao(cenario: Demonstracao) -> AcessoAdmin:
    return AcessoAdmin(administrador_id=cenario.administrador.id)


@pytest.fixture
def conferir(
    sessao: Session,
    cenario: Demonstracao,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    registrar_passagem: Callable[..., Passagem],
) -> Callable[..., UUID]:
    """Uma passagem com o recorte guardado, conferida pelo porteiro; devolve a passagem."""
    porteiro = acesso_do_usuario(sessao, cenario.porteiro_a.id)

    def _conferir(placa: str = "ABC1D23", quando: datetime = AGORA, ref: str = "p/1.jpg") -> UUID:
        camera = str(cenario.camera_a.id)
        armazenamento.guardar(caixa_a.caixa_id, ref, FOTO + ref.encode())
        passagem = registrar_passagem(fotos=[{"tipo": "placa", "camera_id": camera, "ref": ref}])
        conferencia.conferir(sessao, porteiro, passagem.id, 0, placa, agora=quando)
        return passagem.id

    return _conferir


def _autorizar(sessao: Session, administracao: AcessoAdmin, cenario: Demonstracao) -> None:
    treino.autorizar(sessao, administracao, cenario.empresa_a.id, clausula_em=CLAUSULA, agora=AGORA)


# --- A autorização do contrato --------------------------------------------------------------


def test_sem_a_clausula_nada_vira_rotulo(
    sessao: Session,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
) -> None:
    conferir()

    assert treino.rotular(sessao, armazenamento, base, agora=AGORA) == 0
    assert list(sessao.scalars(select(Rotulo))) == []


def test_com_a_clausula_a_conferencia_vira_rotulo_a_revisar(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
) -> None:
    _autorizar(sessao, administracao, cenario)
    passagem_id = conferir(placa="ABC1D24")

    assert treino.rotular(sessao, armazenamento, base, agora=AGORA) == 1
    assert treino.rotular(sessao, armazenamento, base, agora=AGORA) == 0

    (rotulo,) = sessao.scalars(select(Rotulo))
    assert (rotulo.empresa_id, rotulo.passagem_id, rotulo.foto) == (
        cenario.empresa_a.id,
        passagem_id,
        0,
    )
    assert (rotulo.placa, rotulo.origem, rotulo.situacao) == ("ABC1D24", "conferencia", "a_revisar")
    # O recorte foi copiado para a base de treino: dura mais que a foto.
    copia = base.ler(rotulo.recorte)
    assert copia == FOTO + b"p/1.jpg"
    assert rotulo.resumo == hashlib.sha256(copia).hexdigest()


def test_so_as_conferencias_desde_a_clausula(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
) -> None:
    _autorizar(sessao, administracao, cenario)
    conferir(quando=datetime(2026, 9, 30, 23, 0, tzinfo=UTC), ref="antes.jpg")
    depois = conferir(ref="depois.jpg")

    treino.rotular(sessao, armazenamento, base, agora=AGORA)

    assert [r.passagem_id for r in sessao.scalars(select(Rotulo))] == [depois]


def test_a_conferencia_de_outra_empresa_nao_entra(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
) -> None:
    treino.autorizar(sessao, administracao, cenario.empresa_b.id, clausula_em=CLAUSULA, agora=AGORA)
    conferir()

    assert treino.rotular(sessao, armazenamento, base, agora=AGORA) == 0


def test_a_ultima_conferencia_da_foto_vale(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
) -> None:
    _autorizar(sessao, administracao, cenario)
    passagem_id = conferir(placa="ABC1D23")
    porteiro = acesso_do_usuario(sessao, cenario.porteiro_a.id)
    conferencia.conferir(
        sessao, porteiro, passagem_id, 0, "ABC1D24", agora=AGORA + timedelta(minutes=1)
    )

    assert treino.rotular(sessao, armazenamento, base, agora=AGORA) == 1
    assert sessao.scalars(select(Rotulo.placa)).one() == "ABC1D24"


def test_cada_recorte_da_passagem_e_um_rotulo(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    registrar_passagem: Callable[..., Passagem],
) -> None:
    _autorizar(sessao, administracao, cenario)
    camera = str(cenario.camera_a.id)
    for ref in ("p/1.jpg", "p/2.jpg"):
        armazenamento.guardar(caixa_a.caixa_id, ref, FOTO + ref.encode())
    passagem = registrar_passagem(
        fotos=[
            {"tipo": "placa", "camera_id": camera, "ref": "p/1.jpg"},
            {"tipo": "placa", "camera_id": camera, "ref": "p/2.jpg"},
        ]
    )
    porteiro = acesso_do_usuario(sessao, cenario.porteiro_a.id)
    conferencia.conferir(sessao, porteiro, passagem.id, 0, "ABC1D23", agora=AGORA)
    assert treino.rotular(sessao, armazenamento, base, agora=AGORA) == 1

    # O outro recorte da mesma passagem, conferido depois, também vira rótulo.
    conferencia.conferir(sessao, porteiro, passagem.id, 1, "ABC1D23", agora=AGORA)
    assert treino.rotular(sessao, armazenamento, base, agora=AGORA) == 1
    assert sorted(r.foto for r in sessao.scalars(select(Rotulo))) == [0, 1]


def test_sem_o_recorte_o_rotulo_nasce_descartado(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    tmp_path: Path,
    caixa_a: CaixaAtivada,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
) -> None:
    _autorizar(sessao, administracao, cenario)
    conferir()
    (tmp_path / "fotos" / f"caixa-{caixa_a.caixa_id}" / "p" / "1.jpg").unlink()

    treino.rotular(sessao, armazenamento, base, agora=AGORA)

    (rotulo,) = sessao.scalars(select(Rotulo))
    assert (rotulo.situacao, rotulo.recorte, rotulo.revisado_em) == ("descartado", None, AGORA)
    assert treino.rotular(sessao, armazenamento, base, agora=AGORA) == 0


def test_a_empresa_de_demonstracao_nao_entra(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    senhas: Senhas,
    cifra: Cifra,
) -> None:
    from nuvem.demonstracao import link as links

    gerado = links.gerar_link(sessao, administracao, nome="Visita", agora=AGORA)
    links.entrar_pelo_link(sessao, senhas, cifra, gerado.codigo, agora=AGORA)
    assert gerado.link.empresa_id is not None

    with pytest.raises(DadoInvalidoError):
        treino.autorizar(
            sessao, administracao, gerado.link.empresa_id, clausula_em=CLAUSULA, agora=AGORA
        )
    nomes = [empresa.nome for empresa, _ in treino.autorizacoes(sessao, administracao)]
    assert cenario.empresa_a.nome in nomes
    assert len(nomes) == 2  # as duas da semente; a de demonstração não aparece


def test_autorizar_de_novo_troca_a_data(
    sessao: Session, cenario: Demonstracao, administracao: AcessoAdmin
) -> None:
    _autorizar(sessao, administracao, cenario)
    treino.autorizar(
        sessao, administracao, cenario.empresa_a.id, clausula_em=date(2026, 9, 1), agora=AGORA
    )

    ativas = sessao.scalars(
        select(AutorizacaoDeTreino.clausula_em).where(AutorizacaoDeTreino.revogada_em.is_(None))
    ).all()
    assert ativas == [date(2026, 9, 1)]


def test_revogar_apaga_os_rotulos_e_os_recortes_da_empresa(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
) -> None:
    _autorizar(sessao, administracao, cenario)
    conferir()
    treino.rotular(sessao, armazenamento, base, agora=AGORA)
    (rotulo,) = sessao.scalars(select(Rotulo))
    recorte = rotulo.recorte
    assert recorte is not None

    assert treino.revogar(sessao, administracao, cenario.empresa_a.id, base, agora=AGORA) == 1

    assert list(sessao.scalars(select(Rotulo))) == []
    assert base.ler(recorte) is None
    assert treino.rotular(sessao, armazenamento, base, agora=AGORA) == 0
    with pytest.raises(NaoEncontradoError):
        treino.revogar(sessao, administracao, cenario.empresa_a.id, base, agora=AGORA)


# --- A régua --------------------------------------------------------------------------------


def test_a_regua_e_sorteada_pelo_resumo_e_nao_muda() -> None:
    passagens = [UUID(int=n) for n in range(400)]
    conjuntos = [treino.conjunto_de(p, 0) for p in passagens]

    assert conjuntos == [treino.conjunto_de(p, 0) for p in passagens]  # repetível
    assert set(conjuntos) == {"treino", "regua"}
    assert 20 <= conjuntos.count("regua") <= 60  # cerca de 1 em cada 10
    regra = [
        "regua" if hashlib.sha256(f"{p}:0".encode()).digest()[0] % 10 == 0 else "treino"
        for p in passagens
    ]
    assert conjuntos == regra


# --- A rotulagem ----------------------------------------------------------------------------


def _rotulo(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
) -> Rotulo:
    _autorizar(sessao, administracao, cenario)
    conferir()
    treino.rotular(sessao, armazenamento, base, agora=AGORA)
    return sessao.scalars(select(Rotulo)).one()


@pytest.mark.parametrize(
    ("acao", "placa", "situacao", "placa_final"),
    [
        ("aceitar", "", "aceito", "ABC1D23"),
        ("corrigir", "xyz-9k87", "corrigido", "XYZ9K87"),
        ("descartar", "", "descartado", "ABC1D23"),
    ],
)
def test_a_rotulagem_aceita_corrige_ou_descarta(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
    acao: str,
    placa: str,
    situacao: str,
    placa_final: str,
) -> None:
    rotulo = _rotulo(sessao, cenario, administracao, armazenamento, base, conferir)

    revisado = treino.revisar(
        sessao,
        administracao,
        rotulo.id,
        acao,
        placa=placa,
        agora=AGORA,  # type: ignore[arg-type]
    )

    assert (revisado.situacao, revisado.placa) == (situacao, placa_final)
    assert (revisado.revisado_por, revisado.revisado_em) == (cenario.administrador.id, AGORA)
    assert treino.pendentes(sessao, administracao) == []


def test_corrigir_pede_uma_placa_valida(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
) -> None:
    rotulo = _rotulo(sessao, cenario, administracao, armazenamento, base, conferir)

    with pytest.raises(DadoInvalidoError):
        treino.revisar(sessao, administracao, rotulo.id, "corrigir", placa="ABC", agora=AGORA)


# --- A exportação ---------------------------------------------------------------------------


def test_a_exportacao_leva_so_os_revisados_separados_pela_regua(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    tmp_path: Path,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _autorizar(sessao, administracao, cenario)
    sorteio = iter(["treino", "regua", "treino", "treino"])
    monkeypatch.setattr(treino, "conjunto_de", lambda _p, _f: next(sorteio))
    for ref in ("a.jpg", "b.jpg", "c.jpg", "d.jpg"):
        conferir(ref=ref)
    treino.rotular(sessao, armazenamento, base, agora=AGORA)
    a, b, c, d = sessao.scalars(select(Rotulo).order_by(Rotulo.id))
    treino.revisar(sessao, administracao, a.id, "aceitar", agora=AGORA)
    treino.revisar(sessao, administracao, b.id, "corrigir", placa="BRA2E19", agora=AGORA)
    treino.revisar(sessao, administracao, c.id, "descartar", agora=AGORA)
    # O d fica a revisar: não vai.

    resultado = treino.exportar(sessao, base, tmp_path / "saida")

    assert (resultado.treino, resultado.regua) == (1, 1)
    linhas = list(csv.DictReader((tmp_path / "saida" / "treino.csv").open(encoding="utf-8")))
    assert linhas == [{"arquivo": f"treino/{a.id}.jpg", "placa": "ABC1D23"}]
    regua = list(csv.DictReader((tmp_path / "saida" / "regua.csv").open(encoding="utf-8")))
    assert regua == [{"arquivo": f"regua/{b.id}.jpg", "placa": "BRA2E19"}]
    assert (tmp_path / "saida" / "treino" / f"{a.id}.jpg").read_bytes() == FOTO + b"a.jpg"
    assert (tmp_path / "saida" / "regua" / f"{b.id}.jpg").read_bytes() == FOTO + b"b.jpg"
    assert not (tmp_path / "saida" / "treino" / f"{c.id}.jpg").exists()
    assert d.situacao == "a_revisar"


def test_a_exportacao_pela_linha_de_comando(
    sessao: Session,
    url_banco_teste: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from nuvem.treino import exportacao

    monkeypatch.setenv("PATIO_URL_BANCO", url_banco_teste)
    monkeypatch.setenv("PATIO_CHAVE_CIFRA", "e2u1sbXAG2Ri9_0ZHEe1QYdjCBzi-q2Wk1ZkkXBtEyw=")
    monkeypatch.setenv("PATIO_PASTA_FOTOS", str(tmp_path / "fotos"))
    monkeypatch.chdir(tmp_path)

    exportacao.principal(["--destino", str(tmp_path / "saida")])

    assert "0 no treino, 0 na régua" in capsys.readouterr().out
    assert (tmp_path / "saida" / "treino.csv").read_text(encoding="utf-8") == "arquivo,placa\n"


def test_o_worker_rotula_a_cada_hora(
    sessao: Session,
    cenario: Demonstracao,
    administracao: AcessoAdmin,
    armazenamento: ArmazenamentoLocal,
    base: TreinoNoDisco,
    conferir: Callable[..., UUID],
) -> None:
    import threading

    from nuvem import tarefas_de_fundo as fila

    _autorizar(sessao, administracao, cenario)
    conferir()
    parar = threading.Event()

    def dormir(_segundos: float) -> None:
        parar.set()

    fila.rodar(
        lambda: sessao, parar, relogio=lambda: AGORA, dormir=dormir,
        armazenamento=armazenamento, base_de_treino=base,
    )  # fmt: skip

    assert sessao.scalars(select(Rotulo.situacao)).all() == ["a_revisar"]

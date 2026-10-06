"""O login com a verificação em duas etapas (SDD 8.2, D-60): a sessão pela metade, ligar a
verificação, o código do app, os códigos de recuperação e zerar."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from nuvem.cadastro import duas_etapas, login
from nuvem.cadastro.modelos import Administrador, CodigoRecuperacao, Usuario
from nuvem.cifra import Cifra
from nuvem.erros import NaoIdentificadoError
from nuvem.semente import SENHA_DA_DEMONSTRACAO, Demonstracao
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)


def _entrar(
    sessao: Session, senhas: Senhas, email: str, *, exigir: bool = True, agora: datetime = AGORA
) -> str:
    return login.entrar(
        sessao,
        senhas,
        email=email,
        senha=SENHA_DA_DEMONSTRACAO,
        agora=agora,
        exigir_duas_etapas=exigir,
    )


def _falta(sessao: Session, codigo: str, agora: datetime = AGORA) -> str | None:
    metade = login.sessao_pela_metade(sessao, codigo, agora)
    return metade.falta if metade else None


def _ligar(
    sessao: Session, senhas: Senhas, cifra: Cifra, email: str, agora: datetime = AGORA
) -> tuple[str, login.Ligada]:
    """Entra pela primeira vez e liga a verificação; devolve o segredo e o resultado."""
    codigo = _entrar(sessao, senhas, email, agora=agora)
    segredo = login.preparar_ligacao(sessao, cifra, codigo_da_sessao=codigo, agora=agora).segredo
    digitado = duas_etapas.codigo_do_passo(segredo, duas_etapas.passo_de(agora))
    ligada = login.ligar(
        sessao, senhas, cifra, codigo_da_sessao=codigo, digitado=digitado, agora=agora
    )
    return segredo, ligada


def _codigo_do_app(segredo: str, agora: datetime, adiante: int = 0) -> str:
    return duas_etapas.codigo_do_passo(segredo, duas_etapas.passo_de(agora) + adiante)


# --- Quem passa pela verificação -----------------------------------------------------------


def test_gestor_sem_a_verificacao_ligada_cai_na_sessao_pela_metade_para_ligar(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)

    assert _falta(sessao, codigo) == "ligar"
    # A sessão pela metade não serve para as outras telas.
    assert login.conta_da_sessao(sessao, codigo, AGORA) is None


def test_administracao_tambem_passa_pela_verificacao(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.administrador.email)

    assert _falta(sessao, codigo) == "ligar"


@pytest.mark.parametrize("quem", ["porteiro_a", "patio_a"])
def test_porteiro_e_lider_de_patio_entram_direto(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, quem: str
) -> None:
    conta: Usuario = getattr(cenario, quem)

    codigo = _entrar(sessao, senhas, conta.email)

    assert _falta(sessao, codigo) is None
    assert login.conta_da_sessao(sessao, codigo, AGORA) == conta


def test_sem_exigir_quem_nao_ligou_entra_direto(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email, exigir=False)

    assert login.conta_da_sessao(sessao, codigo, AGORA) == cenario.gestor_a


def test_quem_ligou_responde_ao_codigo_mesmo_sem_exigir(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    _ligar(sessao, senhas, cifra, cenario.gestor_a.email)

    codigo = _entrar(sessao, senhas, cenario.gestor_a.email, exigir=False)

    assert _falta(sessao, codigo) == "codigo"


def test_a_sessao_pela_metade_vence_em_10_minutos(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)

    depois = AGORA + duas_etapas.VALIDADE_DA_SESSAO_PELA_METADE
    assert login.sessao_pela_metade(sessao, codigo, depois - timedelta(seconds=1)) is not None
    assert login.sessao_pela_metade(sessao, codigo, depois) is None


def test_a_sessao_de_sempre_nao_e_pela_metade(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.porteiro_a.email)

    assert login.sessao_pela_metade(sessao, codigo, AGORA) is None


# --- Ligar a verificação -------------------------------------------------------------------


def test_preparar_a_ligacao_guarda_o_segredo_cifrado_e_repete_o_mesmo(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)

    primeira = login.preparar_ligacao(sessao, cifra, codigo_da_sessao=codigo, agora=AGORA)
    segunda = login.preparar_ligacao(sessao, cifra, codigo_da_sessao=codigo, agora=AGORA)

    assert primeira.segredo == segunda.segredo
    assert primeira.email == cenario.gestor_a.email
    gravado = sessao.execute(
        text("select duas_etapas_cifrado from usuario where id = :id"), {"id": cenario.gestor_a.id}
    ).scalar_one()
    assert primeira.segredo not in gravado
    assert cifra.decifrar(gravado) == primeira.segredo
    # Preparar não liga: só o código do app confirma.
    assert cenario.gestor_a.duas_etapas_desde is None


def test_ligar_com_o_codigo_certo_abre_a_sessao_e_da_10_codigos_de_recuperacao(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)
    segredo = login.preparar_ligacao(sessao, cifra, codigo_da_sessao=codigo, agora=AGORA).segredo

    ligada = login.ligar(
        sessao,
        senhas,
        cifra,
        codigo_da_sessao=codigo,
        digitado=_codigo_do_app(segredo, AGORA),
        agora=AGORA,
    )

    assert login.conta_da_sessao(sessao, ligada.codigo_da_sessao, AGORA) == cenario.gestor_a
    assert login.sessao_pela_metade(sessao, codigo, AGORA) is None  # a pela metade fechou
    assert cenario.gestor_a.duas_etapas_desde == AGORA
    assert len(ligada.recuperacao) == 10
    resumos = sessao.scalars(
        select(CodigoRecuperacao.resumo).where(CodigoRecuperacao.usuario_id == cenario.gestor_a.id)
    ).all()
    assert len(resumos) == 10
    for recuperacao in ligada.recuperacao:
        assert all(recuperacao not in resumo for resumo in resumos)  # só o resumo fica
        assert any(senhas.confere(resumo, recuperacao) for resumo in resumos)


def test_ligar_com_o_codigo_errado_nao_liga_e_conta_o_erro(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)
    segredo = login.preparar_ligacao(sessao, cifra, codigo_da_sessao=codigo, agora=AGORA).segredo
    errado = _codigo_do_app(segredo, AGORA, adiante=5)

    for _ in range(login.MAXIMO_DE_ERROS):
        with pytest.raises(login.LoginRecusadoError):
            login.ligar(
                sessao, senhas, cifra, codigo_da_sessao=codigo, digitado=errado, agora=AGORA
            )

    with pytest.raises(login.MuitasTentativasError):
        login.ligar(
            sessao,
            senhas,
            cifra,
            codigo_da_sessao=codigo,
            digitado=_codigo_do_app(segredo, AGORA),
            agora=AGORA,
        )
    assert cenario.gestor_a.duas_etapas_desde is None


def test_quem_ja_ligou_nao_liga_de_novo_pela_sessao_do_codigo(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    _ligar(sessao, senhas, cifra, cenario.gestor_a.email)
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)

    with pytest.raises(NaoIdentificadoError):
        login.preparar_ligacao(sessao, cifra, codigo_da_sessao=codigo, agora=AGORA)


# --- O código do app -----------------------------------------------------------------------


def test_o_codigo_certo_abre_a_sessao_de_sempre_com_um_codigo_novo(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    segredo, _ = _ligar(sessao, senhas, cifra, cenario.gestor_a.email)
    depois = AGORA + timedelta(minutes=5)
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email, agora=depois)

    aberta = login.confirmar_codigo(
        sessao,
        senhas,
        cifra,
        codigo_da_sessao=codigo,
        digitado=_codigo_do_app(segredo, depois),
        agora=depois,
    )

    assert aberta != codigo
    assert login.conta_da_sessao(sessao, aberta, depois) == cenario.gestor_a
    assert login.sessao_pela_metade(sessao, codigo, depois) is None


def test_o_codigo_ja_usado_nao_abre_outra_sessao(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    segredo, _ = _ligar(sessao, senhas, cifra, cenario.gestor_a.email)
    depois = AGORA + timedelta(minutes=5)
    usado = _codigo_do_app(segredo, depois)
    primeira = _entrar(sessao, senhas, cenario.gestor_a.email, agora=depois)
    login.confirmar_codigo(
        sessao, senhas, cifra, codigo_da_sessao=primeira, digitado=usado, agora=depois
    )
    segunda = _entrar(sessao, senhas, cenario.gestor_a.email, agora=depois)

    with pytest.raises(login.LoginRecusadoError):
        login.confirmar_codigo(
            sessao, senhas, cifra, codigo_da_sessao=segunda, digitado=usado, agora=depois
        )


def test_codigo_errado_conta_e_5_erros_bloqueiam_mesmo_o_certo(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    segredo, _ = _ligar(sessao, senhas, cifra, cenario.gestor_a.email)
    depois = AGORA + timedelta(minutes=5)
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email, agora=depois)

    for _ in range(login.MAXIMO_DE_ERROS):
        with pytest.raises(login.LoginRecusadoError):
            login.confirmar_codigo(
                sessao,
                senhas,
                cifra,
                codigo_da_sessao=codigo,
                digitado=_codigo_do_app(segredo, depois, adiante=7),
                agora=depois,
            )

    with pytest.raises(login.MuitasTentativasError):
        login.confirmar_codigo(
            sessao,
            senhas,
            cifra,
            codigo_da_sessao=codigo,
            digitado=_codigo_do_app(segredo, depois),
            agora=depois,
        )


def test_o_codigo_de_recuperacao_vale_uma_vez(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    _, ligada = _ligar(sessao, senhas, cifra, cenario.gestor_a.email)
    recuperacao = ligada.recuperacao[3]
    primeira = _entrar(sessao, senhas, cenario.gestor_a.email)

    aberta = login.confirmar_codigo(
        sessao,
        senhas,
        cifra,
        codigo_da_sessao=primeira,
        digitado=recuperacao.upper().replace("-", " "),
        agora=AGORA,
    )

    assert login.conta_da_sessao(sessao, aberta, AGORA) == cenario.gestor_a
    segunda = _entrar(sessao, senhas, cenario.gestor_a.email)
    with pytest.raises(login.LoginRecusadoError):
        login.confirmar_codigo(
            sessao, senhas, cifra, codigo_da_sessao=segunda, digitado=recuperacao, agora=AGORA
        )


def test_o_codigo_de_recuperacao_de_outra_pessoa_nao_vale(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    _, do_gestor_b = _ligar(sessao, senhas, cifra, cenario.gestor_b.email)
    _ligar(sessao, senhas, cifra, cenario.gestor_a.email)
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)

    with pytest.raises(login.LoginRecusadoError):
        login.confirmar_codigo(
            sessao,
            senhas,
            cifra,
            codigo_da_sessao=codigo,
            digitado=do_gestor_b.recuperacao[0],
            agora=AGORA,
        )


def test_sem_sessao_pela_metade_o_codigo_nao_tem_onde_entrar(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    segredo, ligada = _ligar(sessao, senhas, cifra, cenario.gestor_a.email)
    digitado = _codigo_do_app(segredo, AGORA, adiante=1)

    for codigo in ("inventado", ligada.codigo_da_sessao):  # a de sempre não é pela metade
        with pytest.raises(NaoIdentificadoError):
            login.confirmar_codigo(
                sessao, senhas, cifra, codigo_da_sessao=codigo, digitado=digitado, agora=AGORA
            )


def test_a_sessao_para_ligar_nao_serve_para_o_codigo(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)

    with pytest.raises(NaoIdentificadoError):
        login.confirmar_codigo(
            sessao, senhas, cifra, codigo_da_sessao=codigo, digitado="123456", agora=AGORA
        )


def test_conta_desativada_no_meio_nao_termina_de_entrar(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    segredo, _ = _ligar(sessao, senhas, cifra, cenario.gestor_a.email)
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)
    cenario.gestor_a.ativo = False
    sessao.flush()

    assert login.sessao_pela_metade(sessao, codigo, AGORA) is None
    with pytest.raises(NaoIdentificadoError):
        login.confirmar_codigo(
            sessao,
            senhas,
            cifra,
            codigo_da_sessao=codigo,
            digitado=_codigo_do_app(segredo, AGORA, adiante=1),
            agora=AGORA,
        )


def test_a_administracao_liga_e_entra_com_o_codigo(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    segredo, _ = _ligar(sessao, senhas, cifra, cenario.administrador.email)
    codigo = _entrar(sessao, senhas, cenario.administrador.email)

    aberta = login.confirmar_codigo(
        sessao,
        senhas,
        cifra,
        codigo_da_sessao=codigo,
        digitado=_codigo_do_app(segredo, AGORA, adiante=1),
        agora=AGORA,
    )

    conta = login.conta_da_sessao(sessao, aberta, AGORA)
    assert isinstance(conta, Administrador)
    recuperacao = sessao.scalars(
        select(CodigoRecuperacao).where(
            CodigoRecuperacao.administrador_id == cenario.administrador.id
        )
    ).all()
    assert len(recuperacao) == 10


# --- Zerar ---------------------------------------------------------------------------------


def test_zerar_apaga_a_verificacao_fecha_as_sessoes_e_registra_quem(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    _, ligada = _ligar(sessao, senhas, cifra, cenario.gestor_a.email)
    depois = AGORA + timedelta(hours=1)

    login.zerar_duas_etapas(sessao, cenario.gestor_a, agora=depois, por=cenario.administrador)

    gestor = cenario.gestor_a
    assert (gestor.duas_etapas_cifrado, gestor.duas_etapas_desde, gestor.duas_etapas_passo) == (
        None,
        None,
        None,
    )
    assert (gestor.duas_etapas_zerada_em, gestor.duas_etapas_zerada_por) == (
        depois,
        cenario.administrador.id,
    )
    assert login.conta_da_sessao(sessao, ligada.codigo_da_sessao, depois) is None
    restantes = sessao.scalars(
        select(CodigoRecuperacao).where(CodigoRecuperacao.usuario_id == gestor.id)
    ).all()
    assert restantes == []
    # Na próxima entrada, liga de novo.
    assert _falta(sessao, _entrar(sessao, senhas, gestor.email, agora=depois), depois) == "ligar"


def test_zerar_a_administracao_pelo_servidor_nao_tem_quem(
    sessao: Session, cenario: Demonstracao, senhas: Senhas, cifra: Cifra
) -> None:
    _ligar(sessao, senhas, cifra, cenario.administrador.email)

    login.zerar_duas_etapas(sessao, cenario.administrador, agora=AGORA)

    assert cenario.administrador.duas_etapas_desde is None
    assert _falta(sessao, _entrar(sessao, senhas, cenario.administrador.email)) == "ligar"

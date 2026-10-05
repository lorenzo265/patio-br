"""Login (SDD 8.2, D-20): senha, sessão no banco, limite de tentativas e troca de porteiro."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nuvem.banco import sqlstate
from nuvem.cadastro import login, servico
from nuvem.erros import NaoEncontradoError
from nuvem.semente import PIN_DA_DEMONSTRACAO, SENHA_DA_DEMONSTRACAO, Demonstracao
from nuvem.senhas import Senhas

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)
SENHA_ERRADA = "nao-e-esta-a-senha"
EMAIL_INVENTADO = "ninguem@empresa-a.example"


def _entrar(
    sessao: Session,
    senhas: Senhas,
    email: str,
    senha: str = SENHA_DA_DEMONSTRACAO,
    agora: datetime = AGORA,
) -> str:
    return login.entrar(sessao, senhas, email=email, senha=senha, agora=agora)


def _errar(
    sessao: Session, senhas: Senhas, email: str, vezes: int, agora: datetime = AGORA
) -> None:
    for _ in range(vezes):
        with pytest.raises(login.LoginRecusadoError):
            _entrar(sessao, senhas, email, SENHA_ERRADA, agora)


# --- Senha e sessão ------------------------------------------------------------------------


def test_senha_certa_abre_uma_sessao_do_usuario(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)

    assert login.conta_da_sessao(sessao, codigo, AGORA) == cenario.gestor_a


def test_banco_guarda_so_o_resumo_do_codigo_da_sessao(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    # Quem copia o banco não consegue usar as sessões abertas.
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)

    gravados = sessao.execute(text("select codigo_resumo from sessao_login")).scalars().all()
    assert gravados
    assert all(codigo not in gravado for gravado in gravados)


def test_email_com_maiusculas_e_espacos_entra(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, f"  {cenario.gestor_a.email.upper()} ")

    assert login.conta_da_sessao(sessao, codigo, AGORA) == cenario.gestor_a


def test_senha_errada_e_recusada(sessao: Session, cenario: Demonstracao, senhas: Senhas) -> None:
    with pytest.raises(login.LoginRecusadoError):
        _entrar(sessao, senhas, cenario.gestor_a.email, SENHA_ERRADA)


def test_email_desconhecido_e_recusado_do_mesmo_jeito(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    # Mesmo erro da senha errada: a tela não revela quais e-mails existem.
    with pytest.raises(login.LoginRecusadoError):
        _entrar(sessao, senhas, "ninguem@empresa-a.example")


def test_usuario_desativado_nao_entra(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    cenario.gestor_a.ativo = False
    sessao.flush()

    with pytest.raises(login.LoginRecusadoError):
        _entrar(sessao, senhas, cenario.gestor_a.email)


def test_usuario_desativado_perde_a_sessao_que_ja_tinha(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)

    cenario.gestor_a.ativo = False
    sessao.flush()

    assert login.conta_da_sessao(sessao, codigo, AGORA) is None


def test_usuario_sem_senha_nao_entra(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    servico.criar_usuario(
        sessao,
        senhas,
        cenario.empresa_a,
        nome="Sem senha",
        email="sem-senha@empresa-a.example",
        papel="patio",
        sites=[cenario.site_a],
    )

    with pytest.raises(login.LoginRecusadoError):
        _entrar(sessao, senhas, "sem-senha@empresa-a.example", "")


def test_administracao_entra_pela_mesma_tela(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.administrador.email)

    assert login.conta_da_sessao(sessao, codigo, AGORA) == cenario.administrador


def test_sessao_vale_12_horas(sessao: Session, cenario: Demonstracao, senhas: Senhas) -> None:
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)
    quase = AGORA + timedelta(hours=12) - timedelta(seconds=1)

    assert login.conta_da_sessao(sessao, codigo, quase) == cenario.gestor_a
    assert login.conta_da_sessao(sessao, codigo, AGORA + timedelta(hours=12)) is None


def test_sair_apaga_a_sessao(sessao: Session, cenario: Demonstracao, senhas: Senhas) -> None:
    codigo = _entrar(sessao, senhas, cenario.gestor_a.email)

    login.sair(sessao, codigo)

    assert login.conta_da_sessao(sessao, codigo, AGORA) is None


def test_codigo_inventado_nao_abre_nada(sessao: Session, cenario: Demonstracao) -> None:
    assert login.conta_da_sessao(sessao, "codigo-inventado", AGORA) is None


def test_senha_certa_com_custo_antigo_refaz_o_resumo(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    # Subir o custo do argon2 não obriga ninguém a trocar a senha: o resumo é refeito ao entrar.
    padrao = Senhas()

    login.entrar(
        sessao, padrao, email=cenario.gestor_a.email, senha=SENHA_DA_DEMONSTRACAO, agora=AGORA
    )

    assert cenario.gestor_a.senha_resumo is not None
    assert not padrao.precisa_refazer(cenario.gestor_a.senha_resumo)


# --- Limite de tentativas ------------------------------------------------------------------


def test_cinco_erros_bloqueiam_o_email_mesmo_com_a_senha_certa(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    _errar(sessao, senhas, cenario.gestor_a.email, vezes=5)

    with pytest.raises(login.MuitasTentativasError):
        _entrar(sessao, senhas, cenario.gestor_a.email)


def test_quatro_erros_ainda_deixam_entrar(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    _errar(sessao, senhas, cenario.gestor_a.email, vezes=4)

    assert _entrar(sessao, senhas, cenario.gestor_a.email)


def test_bloqueio_acaba_quando_o_erro_mais_antigo_completa_15_minutos(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    for minuto in range(5):
        _errar(sessao, senhas, cenario.gestor_a.email, 1, AGORA + timedelta(minutes=minuto))

    with pytest.raises(login.MuitasTentativasError):
        _entrar(sessao, senhas, cenario.gestor_a.email, agora=AGORA + timedelta(minutes=14))
    assert _entrar(sessao, senhas, cenario.gestor_a.email, agora=AGORA + timedelta(minutes=15))


def test_erros_de_um_email_nao_bloqueiam_outro(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    _errar(sessao, senhas, cenario.gestor_a.email, vezes=5)

    assert _entrar(sessao, senhas, cenario.gestor_b.email)


def test_email_desconhecido_tambem_e_bloqueado(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    # Se só os e-mails que existem fossem bloqueados, o bloqueio revelaria quem existe.
    _errar(sessao, senhas, "ninguem@empresa-a.example", vezes=5)

    with pytest.raises(login.MuitasTentativasError):
        _entrar(sessao, senhas, "ninguem@empresa-a.example")


def test_entrar_com_a_senha_certa_zera_os_erros(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    _errar(sessao, senhas, cenario.gestor_a.email, vezes=4)
    _entrar(sessao, senhas, cenario.gestor_a.email)
    _errar(sessao, senhas, cenario.gestor_a.email, vezes=4)

    assert _entrar(sessao, senhas, cenario.gestor_a.email)


def test_tentativas_guardam_so_o_resumo_do_email(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    _errar(sessao, senhas, cenario.gestor_a.email, vezes=1)

    gravados = sessao.execute(text("select alvo_resumo from tentativa_login")).scalars().all()
    assert len(gravados) == 1
    assert "empresa-a" not in gravados[0]


def _tentar_na(conexao: Connection, senhas: Senhas, email: str = EMAIL_INVENTADO) -> None:
    # Uma tentativa com a senha errada, sem commit: ela ainda não terminou.
    login.entrar(Session(bind=conexao), senhas, email=email, senha=SENHA_ERRADA, agora=AGORA)


def test_tentativas_do_mesmo_email_passam_uma_de_cada_vez(
    url_banco_teste: str, senhas: Senhas
) -> None:
    # Sem isso, pedidos ao mesmo tempo contam os erros antes de qualquer um gravar o seu, e
    # todos passam do limite. Duas conexões fazem o papel de dois pedidos ao mesmo tempo.
    motor = create_engine(url_banco_teste)
    with motor.connect() as primeira, motor.connect() as segunda:
        primeira.begin()
        with pytest.raises(login.LoginRecusadoError):
            _tentar_na(primeira, senhas)
        segunda.begin()
        segunda.execute(text("set local lock_timeout = '200ms'"))

        with pytest.raises(DBAPIError) as erro:
            _tentar_na(segunda, senhas)

        assert sqlstate(erro.value) == "55P03"  # a segunda esperou a vez dela
    motor.dispose()


def test_tentativas_de_emails_diferentes_nao_esperam_uma_pela_outra(
    url_banco_teste: str, senhas: Senhas
) -> None:
    motor = create_engine(url_banco_teste)
    with motor.connect() as primeira, motor.connect() as segunda:
        primeira.begin()
        with pytest.raises(login.LoginRecusadoError):
            _tentar_na(primeira, senhas)
        segunda.begin()
        segunda.execute(text("set local lock_timeout = '200ms'"))

        with pytest.raises(login.LoginRecusadoError):
            _tentar_na(segunda, senhas, f"outro-{EMAIL_INVENTADO}")
    motor.dispose()


# --- Troca de porteiro por PIN -------------------------------------------------------------


def _trocar(
    sessao: Session, senhas: Senhas, codigo: str, porteiro_id: int, pin: str = PIN_DA_DEMONSTRACAO
) -> str:
    return login.trocar_porteiro(
        sessao, senhas, codigo=codigo, porteiro_id=porteiro_id, pin=pin, agora=AGORA
    )


def test_pin_certo_passa_a_sessao_para_o_porteiro_do_turno(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.porteiro_a.email)

    novo = _trocar(sessao, senhas, codigo, cenario.porteiro_a_noite.id)

    assert login.conta_da_sessao(sessao, novo, AGORA) == cenario.porteiro_a_noite
    assert login.conta_da_sessao(sessao, codigo, AGORA) is None


def test_pin_errado_e_recusado_e_a_sessao_continua_de_quem_estava(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.porteiro_a.email)

    with pytest.raises(login.LoginRecusadoError):
        _trocar(sessao, senhas, codigo, cenario.porteiro_a_noite.id, pin="000000")

    assert login.conta_da_sessao(sessao, codigo, AGORA) == cenario.porteiro_a


def test_cinco_pins_errados_bloqueiam_o_porteiro(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.porteiro_a.email)
    for _ in range(5):
        with pytest.raises(login.LoginRecusadoError):
            _trocar(sessao, senhas, codigo, cenario.porteiro_a_noite.id, pin="000000")

    with pytest.raises(login.MuitasTentativasError):
        _trocar(sessao, senhas, codigo, cenario.porteiro_a_noite.id)


def test_nao_troca_para_porteiro_de_outra_empresa(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.porteiro_a.email)

    with pytest.raises(NaoEncontradoError):
        _trocar(sessao, senhas, codigo, cenario.porteiro_b.id)


def test_nao_troca_para_quem_nao_e_porteiro(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    codigo = _entrar(sessao, senhas, cenario.porteiro_a.email)

    with pytest.raises(NaoEncontradoError):
        _trocar(sessao, senhas, codigo, cenario.gestor_a.id)


def test_nao_troca_para_porteiro_sem_site_em_comum(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    outro = servico.criar_usuario(
        sessao,
        senhas,
        cenario.empresa_a,
        nome="Porteiro do outro site",
        email="porteiro-site2@empresa-a.example",
        papel="porteiro",
        sites=[cenario.site_a2],
    )
    servico.definir_pin(sessao, senhas, outro, PIN_DA_DEMONSTRACAO)
    codigo = _entrar(sessao, senhas, cenario.porteiro_a.email)

    with pytest.raises(NaoEncontradoError):
        _trocar(sessao, senhas, codigo, outro.id)


def test_lista_os_porteiros_para_a_troca(sessao: Session, cenario: Demonstracao) -> None:
    porteiros = login.porteiros_da_troca(sessao, cenario.gestor_a.id)

    assert porteiros == [cenario.porteiro_a, cenario.porteiro_a_noite]


# --- Limite por endereço (D-55) ------------------------------------------------------------

ENDERECO = "203.0.113.7"
"""Da faixa de documentação: não é de ninguém."""


def _errar_do_endereco(
    sessao: Session, senhas: Senhas, vezes: int, endereco: str = ENDERECO
) -> None:
    # Cada erro com um e-mail diferente: o limite por e-mail nunca chega.
    for numero in range(vezes):
        with pytest.raises(login.LoginRecusadoError):
            login.entrar(
                sessao, senhas, email=f"tentativa{numero}@empresa-a.example", senha=SENHA_ERRADA,
                agora=AGORA, endereco=endereco,
            )  # fmt: skip


def test_vinte_erros_bloqueiam_o_endereco_mesmo_com_a_senha_certa(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    _errar_do_endereco(sessao, senhas, vezes=20)

    with pytest.raises(login.MuitasTentativasError):
        login.entrar(
            sessao, senhas, email=cenario.gestor_a.email, senha=SENHA_DA_DEMONSTRACAO,
            agora=AGORA, endereco=ENDERECO,
        )  # fmt: skip


def test_dezenove_erros_ainda_deixam_o_endereco_entrar(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    _errar_do_endereco(sessao, senhas, vezes=19)

    assert login.entrar(
        sessao, senhas, email=cenario.gestor_a.email, senha=SENHA_DA_DEMONSTRACAO, agora=AGORA,
        endereco=ENDERECO,
    )  # fmt: skip


def test_erros_de_um_endereco_nao_bloqueiam_outro(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    _errar_do_endereco(sessao, senhas, vezes=20)

    assert login.entrar(
        sessao, senhas, email=cenario.gestor_a.email, senha=SENHA_DA_DEMONSTRACAO, agora=AGORA,
        endereco="198.51.100.9",
    )  # fmt: skip


def test_entrar_com_a_senha_certa_nao_zera_os_erros_do_endereco(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    # Senão, quem tem uma conta poderia tentar a senha dos outros sem parar.
    _errar_do_endereco(sessao, senhas, vezes=19)
    login.entrar(
        sessao, senhas, email=cenario.gestor_a.email, senha=SENHA_DA_DEMONSTRACAO, agora=AGORA,
        endereco=ENDERECO,
    )  # fmt: skip
    _errar_do_endereco(sessao, senhas, vezes=1)

    with pytest.raises(login.MuitasTentativasError):
        login.entrar(
            sessao, senhas, email=cenario.gestor_b.email, senha=SENHA_DA_DEMONSTRACAO,
            agora=AGORA, endereco=ENDERECO,
        )  # fmt: skip


def test_o_endereco_tambem_fica_so_como_resumo(
    sessao: Session, cenario: Demonstracao, senhas: Senhas
) -> None:
    _errar_do_endereco(sessao, senhas, vezes=1)

    gravados = sessao.execute(text("select alvo_resumo from tentativa_login")).scalars().all()
    assert len(gravados) == 2  # o e-mail e o endereço
    assert not any(ENDERECO in alvo for alvo in gravados)

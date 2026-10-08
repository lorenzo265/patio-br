"""O cadastro do cliente pela administração (SDD 6.2 e 8.2, D-75). Nomes, e-mails e CNPJs
inventados (os CNPJs são os exemplos de conferência, não de empresas)."""

from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nuvem.cadastro import cliente, login
from nuvem.cadastro.acesso import AcessoAdmin
from nuvem.cadastro.modelos import Camera, LinkDeSenha, SessaoLogin, Usuario, UsuarioSite
from nuvem.cifra import Cifra
from nuvem.erros import DadoInvalidoError, NaoEncontradoError
from nuvem.semente import SENHA_DA_DEMONSTRACAO, Demonstracao
from nuvem.senhas import Senhas, resumo_rapido

pytestmark = pytest.mark.integracao

AGORA = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
CNPJ_NUMERICO = "11222333000181"
CNPJ_ALFANUMERICO = "12ABC34501DE35"
"""O exemplo da Receita para o CNPJ alfanumérico (12.ABC.345/01DE-35)."""
SENHA_NOVA = "uma senha longa inventada"


@pytest.fixture
def admin(cenario: Demonstracao) -> AcessoAdmin:
    return AcessoAdmin(administrador_id=cenario.administrador.id)


# --- O CNPJ ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("digitado", "guardado"),
    [
        (CNPJ_NUMERICO, CNPJ_NUMERICO),
        ("11.222.333/0001-81", CNPJ_NUMERICO),
        (CNPJ_ALFANUMERICO, CNPJ_ALFANUMERICO),
        # O resto 2 dá o dígito 9 (só o 0 e o 1 dão 0): no primeiro dígito e no segundo.
        ("11.222.333/0006-96", "11222333000696"),
        ("11.222.333/0009-39", "11222333000939"),
        ("12.abc.345/01de-35", CNPJ_ALFANUMERICO),
        (" 12.ABC.345/01DE-35 ", CNPJ_ALFANUMERICO),
    ],
)
def test_o_cnpj_certo_vai_sem_pontuacao_e_em_maiusculas(digitado: str, guardado: str) -> None:
    assert cliente.conferir_cnpj(digitado) == guardado


@pytest.mark.parametrize(
    "errado",
    [
        "11222333000182",  # o último dígito
        "11222333000191",  # o penúltimo
        "12ABC34501DE36",
        "12ABC34501DEA5",  # os dígitos do fim são números
        "1122233300018",  # 13
        "112223330001811",  # 15
        "11111111111111",  # todos iguais
        "00000000000000",
        "DEMO0000000A00",  # o da demonstração
        "11.222.333/0001-8!",
        "",
    ],
)
def test_o_cnpj_errado_e_recusado(errado: str) -> None:
    with pytest.raises(DadoInvalidoError, match="CNPJ"):
        cliente.conferir_cnpj(errado)


def test_a_empresa_nova_e_o_cnpj_repetido(sessao: Session, admin: AcessoAdmin) -> None:
    empresa = cliente.cadastrar_empresa(
        sessao, admin, nome="  Distribuidora Inventada  ", cnpj="11.222.333/0001-81"
    )

    assert (empresa.nome, empresa.cnpj) == ("Distribuidora Inventada", CNPJ_NUMERICO)
    with pytest.raises(DadoInvalidoError, match="já é de outro cliente"):
        cliente.cadastrar_empresa(sessao, admin, nome="Outra", cnpj=CNPJ_NUMERICO)


def test_a_empresa_sem_nome_e_recusada(sessao: Session, admin: AcessoAdmin) -> None:
    with pytest.raises(DadoInvalidoError, match="nome"):
        cliente.cadastrar_empresa(sessao, admin, nome="   ", cnpj=CNPJ_NUMERICO)


# --- O site e a estrutura -------------------------------------------------------------------


def test_o_site_com_fuso_e_horario(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    site = cliente.cadastrar_site(
        sessao, admin, cenario.empresa_a.id, nome="CD Norte", fuso="America/Manaus",
        abre=time(6, 0), fecha=time(22, 0),
    )  # fmt: skip

    assert (site.empresa_id, site.nome, site.fuso) == (
        cenario.empresa_a.id,
        "CD Norte",
        "America/Manaus",
    )
    assert (site.abre, site.fecha) == (time(6, 0), time(22, 0))


def test_o_site_24_horas_nao_tem_horario(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    site = cliente.cadastrar_site(
        sessao, admin, cenario.empresa_a.id, nome="CD 24h", fuso="America/Sao_Paulo",
        abre=None, fecha=None,
    )  # fmt: skip

    assert (site.abre, site.fecha) == (None, None)


@pytest.mark.parametrize(
    ("fuso", "abre", "fecha", "erro"),
    [
        ("America/Inventada", None, None, "fuso"),
        ("America/Sao_Paulo", time(6, 0), None, "abre e fecha"),
        ("America/Sao_Paulo", None, time(22, 0), "abre e fecha"),
    ],
)
def test_o_site_com_fuso_ou_horario_errado_e_recusado(
    sessao: Session,
    admin: AcessoAdmin,
    cenario: Demonstracao,
    fuso: str,
    abre: time | None,
    fecha: time | None,
    erro: str,
) -> None:
    with pytest.raises(DadoInvalidoError, match=erro):
        cliente.cadastrar_site(
            sessao, admin, cenario.empresa_a.id, nome="CD", fuso=fuso, abre=abre, fecha=fecha
        )


def test_o_site_de_uma_empresa_que_nao_existe(sessao: Session, admin: AcessoAdmin) -> None:
    with pytest.raises(NaoEncontradoError):
        cliente.cadastrar_site(
            sessao, admin, 999_999, nome="CD", fuso="America/Sao_Paulo", abre=None, fecha=None
        )


def test_a_portaria_a_faixa_a_camera_e_a_doca(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao, cifra: Cifra
) -> None:
    empresa = cenario.empresa_a.id
    portaria = cliente.cadastrar_portaria(sessao, admin, empresa, cenario.site_a.id, nome="Sul")
    faixa = cliente.cadastrar_faixa(
        sessao, admin, empresa, portaria.id, nome="Entrada Sul", sentido="entrada"
    )
    camera = cliente.cadastrar_camera(
        sessao, admin, cifra, empresa, faixa.id, nome="Frente", posicao="frente",
        endereco="rtsp://10.0.0.21:554/stream1", login="leitor", senha="senha-da-camera",
    )  # fmt: skip
    doca = cliente.cadastrar_doca(sessao, admin, empresa, cenario.site_a.id, nome="Doca 9")

    assert (portaria.site_id, faixa.portaria_id, camera.faixa_id) == (
        cenario.site_a.id,
        portaria.id,
        faixa.id,
    )
    assert (faixa.sentido, camera.posicao, doca.site_id) == ("entrada", "frente", cenario.site_a.id)
    assert cifra.decifrar(camera.senha_cifrada) == "senha-da-camera"
    assert "senha-da-camera" not in camera.senha_cifrada


def test_nada_se_pendura_no_que_e_de_outra_empresa(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao, cifra: Cifra
) -> None:
    # Pela empresa A, o site, a portaria, a faixa e a câmera da B não existem.
    a = cenario.empresa_a.id
    with pytest.raises(NaoEncontradoError):
        cliente.cadastrar_portaria(sessao, admin, a, cenario.site_b.id, nome="X")
    with pytest.raises(NaoEncontradoError):
        cliente.cadastrar_doca(sessao, admin, a, cenario.site_b.id, nome="X")
    portaria_b = cliente.cadastrar_portaria(
        sessao, admin, cenario.empresa_b.id, cenario.site_b.id, nome="B"
    )
    with pytest.raises(NaoEncontradoError):
        cliente.cadastrar_faixa(sessao, admin, a, portaria_b.id, nome="X", sentido="entrada")
    with pytest.raises(NaoEncontradoError):
        cliente.cadastrar_camera(
            sessao, admin, cifra, a, cenario.camera_b.faixa_id, nome="X", posicao="frente",
            endereco="rtsp://10.0.0.1/1", login="", senha="",
        )  # fmt: skip
    with pytest.raises(NaoEncontradoError):
        cliente.trocar_camera(
            sessao, admin, cifra, a, cenario.camera_b.id,
            endereco="rtsp://10.0.0.1/1", login="", senha=None,
        )  # fmt: skip


@pytest.mark.parametrize(
    ("endereco", "erro"),
    [
        ("http://10.0.0.21/stream", "rtsp://"),
        ("10.0.0.21:554/stream1", "rtsp://"),
        ("rtsp:///stream1", "rtsp://"),
        ("rtsp://leitor:segredo@10.0.0.21/stream1", "usuário nem senha"),
    ],
)
def test_o_endereco_da_camera_e_rtsp_sem_senha_embutida(
    sessao: Session,
    admin: AcessoAdmin,
    cenario: Demonstracao,
    cifra: Cifra,
    endereco: str,
    erro: str,
) -> None:
    with pytest.raises(DadoInvalidoError, match=erro):
        cliente.cadastrar_camera(
            sessao, admin, cifra, cenario.empresa_a.id, cenario.faixa_a.id, nome="X",
            posicao="frente", endereco=endereco, login="", senha="",
        )  # fmt: skip


def test_a_camera_troca_o_endereco_o_login_e_a_senha(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao, cifra: Cifra
) -> None:
    camera = cenario.camera_a
    antes = camera.senha_cifrada

    cliente.trocar_camera(
        sessao, admin, cifra, cenario.empresa_a.id, camera.id,
        endereco="rtsps://10.0.0.99:322/principal", login="novo", senha=None,
    )  # fmt: skip
    assert (camera.endereco, camera.login, camera.senha_cifrada) == (
        "rtsps://10.0.0.99:322/principal", "novo", antes,
    )  # fmt: skip

    cliente.trocar_camera(
        sessao, admin, cifra, cenario.empresa_a.id, camera.id,
        endereco="rtsps://10.0.0.99:322/principal", login="novo", senha="outra-senha",
    )  # fmt: skip
    assert cifra.decifrar(camera.senha_cifrada) == "outra-senha"
    with pytest.raises(DadoInvalidoError, match="usuário nem senha"):
        cliente.trocar_camera(
            sessao, admin, cifra, cenario.empresa_a.id, camera.id,
            endereco="rtsp://leitor:segredo@10.0.0.99/principal", login="", senha=None,
        )  # fmt: skip
    with pytest.raises(DadoInvalidoError, match="rtsp://"):
        cliente.trocar_camera(
            sessao, admin, cifra, cenario.empresa_a.id, camera.id,
            endereco="http://x", login="", senha=None,
        )  # fmt: skip


@pytest.mark.parametrize("nome", ["", "   "])
def test_o_que_nao_tem_nome_e_recusado(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao, nome: str
) -> None:
    with pytest.raises(DadoInvalidoError, match="nome"):
        cliente.cadastrar_doca(sessao, admin, cenario.empresa_a.id, cenario.site_a.id, nome=nome)


# --- As pessoas e o link de senha -----------------------------------------------------------


def _pessoa(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao, papel: str = "gestor"
) -> cliente.LinkGerado:
    return cliente.cadastrar_pessoa(
        sessao, admin, cenario.empresa_a.id, nome="Fulana Inventada",
        email=f"fulana.{papel}@exemplo.invalid", papel=papel,  # type: ignore[arg-type]
        sites=[cenario.site_a.id, cenario.site_a2.id], agora=AGORA,
    )  # fmt: skip


def test_a_pessoa_nova_nasce_sem_senha_e_com_um_link(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    gerado = _pessoa(sessao, admin, cenario)

    usuario = gerado.usuario
    assert (usuario.empresa_id, usuario.papel, usuario.senha_resumo) == (
        cenario.empresa_a.id,
        "gestor",
        None,
    )
    sites = sessao.scalars(select(UsuarioSite.site_id).where(UsuarioSite.usuario_id == usuario.id))
    assert set(sites) == {cenario.site_a.id, cenario.site_a2.id}
    assert gerado.vence_em == AGORA + timedelta(hours=72)
    [link] = sessao.scalars(select(LinkDeSenha).where(LinkDeSenha.usuario_id == usuario.id)).all()
    # O banco guarda só o resumo do código.
    assert link.codigo_resumo == resumo_rapido(gerado.codigo) != gerado.codigo
    assert (link.criado_por, link.criado_em) == (admin.administrador_id, AGORA)
    assert len(gerado.codigo) >= 40


def test_a_pessoa_so_ve_sites_da_propria_empresa(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    with pytest.raises(NaoEncontradoError):
        cliente.cadastrar_pessoa(
            sessao, admin, cenario.empresa_a.id, nome="X", email="x@exemplo.invalid",
            papel="gestor", sites=[cenario.site_b.id], agora=AGORA,
        )  # fmt: skip
    with pytest.raises(DadoInvalidoError, match="site"):
        cliente.cadastrar_pessoa(
            sessao, admin, cenario.empresa_a.id, nome="X", email="x@exemplo.invalid",
            papel="gestor", sites=[], agora=AGORA,
        )  # fmt: skip


def test_o_email_repetido_e_recusado(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    with pytest.raises(DadoInvalidoError, match="e-mail"):
        cliente.cadastrar_pessoa(
            sessao, admin, cenario.empresa_a.id, nome="X", email=cenario.gestor_b.email.upper(),
            papel="gestor", sites=[cenario.site_a.id], agora=AGORA,
        )  # fmt: skip


def test_o_link_cria_a_senha_uma_vez_so(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao, senhas: Senhas
) -> None:
    gerado = _pessoa(sessao, admin, cenario)
    assert cliente.link_de_senha(sessao, gerado.codigo, agora=AGORA) is not None

    usuario = cliente.criar_senha_pelo_link(
        sessao, senhas, gerado.codigo, senha=SENHA_NOVA, pin=None, agora=AGORA
    )

    assert usuario.id == gerado.usuario.id
    assert usuario.senha_resumo is not None and senhas.confere(usuario.senha_resumo, SENHA_NOVA)
    assert cliente.link_de_senha(sessao, gerado.codigo, agora=AGORA) is None
    with pytest.raises(NaoEncontradoError):
        cliente.criar_senha_pelo_link(
            sessao, senhas, gerado.codigo, senha=SENHA_NOVA, pin=None, agora=AGORA
        )


def test_o_link_vale_72_horas(sessao: Session, admin: AcessoAdmin, cenario: Demonstracao) -> None:
    gerado = _pessoa(sessao, admin, cenario)

    vespera = AGORA + timedelta(hours=72) - timedelta(seconds=1)
    assert cliente.link_de_senha(sessao, gerado.codigo, agora=vespera) is not None
    assert cliente.link_de_senha(sessao, gerado.codigo, agora=AGORA + timedelta(hours=72)) is None


def test_o_codigo_inventado_nao_vale(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    _pessoa(sessao, admin, cenario)

    assert cliente.link_de_senha(sessao, "codigo-inventado", agora=AGORA) is None


def test_o_link_novo_troca_o_anterior(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    primeiro = _pessoa(sessao, admin, cenario)

    segundo = cliente.gerar_link_de_senha(
        sessao, admin, cenario.empresa_a.id, primeiro.usuario.id, agora=AGORA + timedelta(hours=1)
    )

    depois = AGORA + timedelta(hours=1)
    assert cliente.link_de_senha(sessao, primeiro.codigo, agora=depois) is None
    assert cliente.link_de_senha(sessao, segundo.codigo, agora=depois) is not None
    trocado = sessao.scalar(
        select(LinkDeSenha).where(LinkDeSenha.codigo_resumo == resumo_rapido(primeiro.codigo))
    )
    assert trocado is not None and trocado.trocado_em == depois


def test_a_senha_esquecida_fecha_as_sessoes_abertas(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao, senhas: Senhas
) -> None:
    gestor = cenario.gestor_a
    login.entrar(sessao, senhas, email=gestor.email, senha=SENHA_DA_DEMONSTRACAO, agora=AGORA)
    assert sessao.scalar(select(func.count()).where(SessaoLogin.usuario_id == gestor.id)) == 1

    gerado = cliente.gerar_link_de_senha(
        sessao, admin, cenario.empresa_a.id, gestor.id, agora=AGORA
    )
    cliente.criar_senha_pelo_link(
        sessao, senhas, gerado.codigo, senha=SENHA_NOVA, pin=None, agora=AGORA
    )

    assert sessao.scalar(select(func.count()).where(SessaoLogin.usuario_id == gestor.id)) == 0
    assert gestor.senha_resumo is not None and senhas.confere(gestor.senha_resumo, SENHA_NOVA)


def test_o_link_de_outra_empresa_nao_se_gera(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    with pytest.raises(NaoEncontradoError):
        cliente.gerar_link_de_senha(
            sessao, admin, cenario.empresa_a.id, cenario.gestor_b.id, agora=AGORA
        )


def test_o_porteiro_cria_a_senha_e_o_pin(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao, senhas: Senhas
) -> None:
    gerado = _pessoa(sessao, admin, cenario, papel="porteiro")

    with pytest.raises(DadoInvalidoError, match="PIN"):
        cliente.criar_senha_pelo_link(
            sessao, senhas, gerado.codigo, senha=SENHA_NOVA, pin=None, agora=AGORA
        )
    with pytest.raises(DadoInvalidoError, match="PIN"):
        cliente.criar_senha_pelo_link(
            sessao, senhas, gerado.codigo, senha=SENHA_NOVA, pin="12345", agora=AGORA
        )
    assert gerado.usuario.senha_resumo is None  # nada mudou com o PIN errado
    usuario = cliente.criar_senha_pelo_link(
        sessao, senhas, gerado.codigo, senha=SENHA_NOVA, pin="246810", agora=AGORA
    )

    assert usuario.pin_resumo is not None and senhas.confere(usuario.pin_resumo, "246810")


def test_quem_nao_e_porteiro_nao_tem_pin(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao, senhas: Senhas
) -> None:
    gerado = _pessoa(sessao, admin, cenario, papel="patio")

    with pytest.raises(DadoInvalidoError, match="PIN"):
        cliente.criar_senha_pelo_link(
            sessao, senhas, gerado.codigo, senha=SENHA_NOVA, pin="246810", agora=AGORA
        )


def test_a_senha_curta_e_recusada_e_o_link_continua_valendo(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao, senhas: Senhas
) -> None:
    gerado = _pessoa(sessao, admin, cenario)

    with pytest.raises(DadoInvalidoError, match="10 a 128"):
        cliente.criar_senha_pelo_link(
            sessao, senhas, gerado.codigo, senha="curta", pin=None, agora=AGORA
        )

    assert cliente.link_de_senha(sessao, gerado.codigo, agora=AGORA) is not None


def test_a_pessoa_desativada_perde_as_sessoes_e_o_link(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao, senhas: Senhas
) -> None:
    gerado = _pessoa(sessao, admin, cenario)
    usuario = gerado.usuario
    porteiro = cenario.porteiro_a
    login.entrar(sessao, senhas, email=porteiro.email, senha=SENHA_DA_DEMONSTRACAO, agora=AGORA)

    cliente.mudar_situacao_da_pessoa(
        sessao, admin, cenario.empresa_a.id, usuario.id, ativa=False, agora=AGORA
    )
    cliente.mudar_situacao_da_pessoa(
        sessao, admin, cenario.empresa_a.id, porteiro.id, ativa=False, agora=AGORA
    )

    assert (usuario.ativo, porteiro.ativo) == (False, False)
    assert cliente.link_de_senha(sessao, gerado.codigo, agora=AGORA) is None
    assert sessao.scalar(select(func.count()).where(SessaoLogin.usuario_id == porteiro.id)) == 0
    with pytest.raises(DadoInvalidoError, match="desativada"):
        cliente.gerar_link_de_senha(sessao, admin, cenario.empresa_a.id, usuario.id, agora=AGORA)

    cliente.mudar_situacao_da_pessoa(
        sessao, admin, cenario.empresa_a.id, porteiro.id, ativa=True, agora=AGORA
    )
    assert porteiro.ativo


# --- A ficha da empresa ---------------------------------------------------------------------


def test_a_ficha_mostra_a_estrutura_e_as_pessoas_so_da_empresa(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    gerado = _pessoa(sessao, admin, cenario)

    ficha = cliente.ficha_da_empresa(sessao, admin, cenario.empresa_a.id, agora=AGORA)

    assert ficha.empresa.id == cenario.empresa_a.id
    assert {s.site.id for s in ficha.sites} == {cenario.site_a.id, cenario.site_a2.id}
    [site_a] = [s for s in ficha.sites if s.site.id == cenario.site_a.id]
    [portaria] = site_a.portarias
    cameras = [c.id for f in portaria.faixas for c in f.cameras]
    assert cenario.camera_a.id in cameras and cenario.camera_b.id not in cameras
    pessoas = {p.usuario.id: p for p in ficha.pessoas}
    assert cenario.gestor_b.id not in pessoas
    assert pessoas[cenario.gestor_a.id].tem_senha
    nova = pessoas[gerado.usuario.id]
    assert (nova.tem_senha, nova.link_vence_em) == (False, AGORA + timedelta(hours=72))
    assert set(nova.sites) == {cenario.site_a.nome, cenario.site_a2.nome}
    with pytest.raises(NaoEncontradoError):
        cliente.ficha_da_empresa(sessao, admin, 999_999, agora=AGORA)


def test_a_camera_nao_mostra_a_senha_na_ficha(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    ficha = cliente.ficha_da_empresa(sessao, admin, cenario.empresa_a.id, agora=AGORA)

    cameras = [c for s in ficha.sites for p in s.portarias for f in p.faixas for c in f.cameras]
    assert cameras and all(not hasattr(c, "senha_cifrada") for c in cameras)
    assert sessao.scalar(select(func.count()).select_from(Camera)) >= len(cameras)
    assert isinstance(cameras[0], cliente.CameraDaFicha)


def test_usuario_ativo_padrao(sessao: Session, admin: AcessoAdmin, cenario: Demonstracao) -> None:
    assert _pessoa(sessao, admin, cenario).usuario.ativo
    assert isinstance(sessao.get(Usuario, cenario.gestor_a.id), Usuario)


def test_reativar_a_pessoa_nao_traz_de_volta_o_link_antigo(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    gerado = _pessoa(sessao, admin, cenario)
    empresa = cenario.empresa_a.id

    cliente.mudar_situacao_da_pessoa(
        sessao, admin, empresa, gerado.usuario.id, ativa=False, agora=AGORA
    )
    cliente.mudar_situacao_da_pessoa(
        sessao, admin, empresa, gerado.usuario.id, ativa=True, agora=AGORA
    )

    assert gerado.usuario.ativo
    assert cliente.link_de_senha(sessao, gerado.codigo, agora=AGORA) is None


def test_o_link_da_pessoa_desativada_por_outro_caminho_nao_vale(
    sessao: Session, admin: AcessoAdmin, cenario: Demonstracao
) -> None:
    gerado = _pessoa(sessao, admin, cenario)
    gerado.usuario.ativo = False
    sessao.flush()

    assert cliente.link_de_senha(sessao, gerado.codigo, agora=AGORA) is None

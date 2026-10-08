"""Login (SDD 8.2): senha, sessão no banco (D-20), limite de tentativas e troca de porteiro.

Quem entra é uma **conta**: um usuário do cliente ou alguém da administração (D-19). As duas
entram pela mesma tela, com e-mail e senha; o e-mail é único entre as duas tabelas.

Com a verificação em duas etapas (D-60), a senha certa abre uma **sessão pela metade**, que só
serve para a tela do código do app (ou, na primeira vez, para ligar a verificação). O código
certo fecha a sessão pela metade e abre a de sempre.

As funções gravam com ``flush``; o ``commit`` é de quem chama. Atenção: uma recusa também grava
o erro (para o limite de tentativas), então quem chama faz ``commit`` mesmo quando recebe
``LoginRecusadoError``.

As tentativas de um mesmo alvo passam uma de cada vez: a trava no banco vale até o ``commit``
(ou o ``rollback``) de quem chama.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from nuvem.cadastro import duas_etapas
from nuvem.cadastro.modelos import (
    Administrador,
    CodigoRecuperacao,
    Falta,
    SessaoLogin,
    TentativaLogin,
    Usuario,
    UsuarioSite,
)
from nuvem.cifra import Cifra
from nuvem.erros import NaoEncontradoError, NaoIdentificadoError
from nuvem.senhas import Senhas, resumo_rapido

VALIDADE_DA_SESSAO = timedelta(hours=12)
"""Um turno de portaria; depois disso, entra de novo."""

JANELA_DAS_TENTATIVAS = timedelta(minutes=15)
MAXIMO_DE_ERROS = 5
"""No máximo 5 erros por alvo (e-mail ou porteiro) a cada 15 minutos."""
MAXIMO_DE_ERROS_POR_ENDERECO = 20
"""E no máximo 20 por endereço IP (D-55): uma rede pode ter várias pessoas."""

Conta = Usuario | Administrador


class LoginRecusadoError(Exception):
    """E-mail, senha ou PIN não conferem (de propósito, sem dizer qual)."""


class MuitasTentativasError(Exception):
    """Erros demais para o mesmo alvo nos últimos 15 minutos: espere e tente de novo."""


@dataclass(frozen=True)
class SessaoPelaMetade:
    """A sessão aberta pela senha que ainda espera a verificação em duas etapas (D-60)."""

    conta: "Conta"
    falta: Falta


@dataclass(frozen=True)
class Ligacao:
    """O que a tela de ligar a verificação mostra: o segredo do app, para a conta do e-mail."""

    email: str
    segredo: str


@dataclass(frozen=True)
class Ligada:
    """A verificação ligada: a sessão de sempre e os códigos de recuperação, mostrados uma vez."""

    codigo_da_sessao: str
    recuperacao: list[str]


def normalizar_email(email: str) -> str:
    """O e-mail como é guardado e comparado: sem espaços nas pontas, em minúsculas."""
    return email.strip().lower()


def conta_por_email(sessao: Session, email: str) -> Conta | None:
    """Devolve o usuário ou o administrador com este e-mail, se houver."""
    email = normalizar_email(email)
    usuario = sessao.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is not None:
        return usuario
    return sessao.scalar(select(Administrador).where(Administrador.email == email))


def entrar(
    sessao: Session,
    senhas: Senhas,
    *,
    email: str,
    senha: str,
    agora: datetime,
    endereco: str | None = None,
    exigir_duas_etapas: bool = False,
) -> str:
    """Confere e-mail e senha e abre uma sessão.

    A sessão é pela metade (veja ``sessao_pela_metade``) quando a conta ligou a verificação em
    duas etapas, ou quando ela é exigida e a conta é do gestor ou da administração (D-60).

    Args:
        endereco: o endereço IP de quem tenta; com ele, vale também o limite por endereço, que a
            senha certa não zera (quem tem uma conta não tenta a senha dos outros sem parar).
        exigir_duas_etapas: se o ambiente exige a verificação (homologação e produção).

    Returns:
        O código da sessão, para o cookie (o banco guarda só o resumo dele).

    Raises:
        MuitasTentativasError: se o e-mail (ou o endereço) errou demais nos últimos 15 minutos
            (mesmo com a senha certa agora).
        LoginRecusadoError: se a conta não existir, estiver desativada, não tiver senha ou a
            senha não conferir. O erro fica gravado para o limite de tentativas.
    """
    alvos = []
    if endereco is not None:
        # Sempre o endereço antes do e-mail: duas travas na mesma ordem nunca se esperam em roda.
        alvo_do_endereco = resumo_rapido(f"ip:{endereco}")
        _recusar_se_bloqueado(sessao, alvo_do_endereco, agora, MAXIMO_DE_ERROS_POR_ENDERECO)
        alvos.append(alvo_do_endereco)
    alvo = resumo_rapido(f"email:{normalizar_email(email)}")
    _recusar_se_bloqueado(sessao, alvo, agora)
    alvos.append(alvo)
    conta = conta_por_email(sessao, email)
    if conta is None or not conta.ativo or conta.senha_resumo is None:
        senhas.gastar_o_mesmo_tempo(senha)
        for errado in alvos:
            _registrar_erro(sessao, errado, agora)
        raise LoginRecusadoError
    if not senhas.confere(conta.senha_resumo, senha):
        for errado in alvos:
            _registrar_erro(sessao, errado, agora)
        raise LoginRecusadoError
    if senhas.precisa_refazer(conta.senha_resumo):
        conta.senha_resumo = senhas.resumir(senha)
    _esquecer_erros(sessao, alvo)
    return abrir_sessao(sessao, conta, agora, falta=_o_que_falta(conta, exigir_duas_etapas))


def precisa_das_duas_etapas(conta: Conta) -> bool:
    """Se a conta é das que a verificação em duas etapas protege: o gestor e a administração."""
    return isinstance(conta, Administrador) or conta.papel == "gestor"


def _o_que_falta(conta: Conta, exigir: bool) -> Falta | None:
    if conta.duas_etapas_desde is not None:
        return "codigo"  # quem ligou responde ao código em qualquer ambiente
    if exigir and precisa_das_duas_etapas(conta):
        return "ligar"
    return None


def sair(sessao: Session, codigo: str) -> None:
    """Fecha a sessão do código (se ela existir)."""
    sessao.execute(delete(SessaoLogin).where(SessaoLogin.codigo_resumo == resumo_rapido(codigo)))
    sessao.flush()


def conta_da_sessao(sessao: Session, codigo: str, agora: datetime) -> Conta | None:
    """Devolve quem está na sessão do código, ou ``None`` se ela não vale.

    Não vale a sessão que não existe, que venceu, que está pela metade (D-60) ou cuja conta foi
    desativada.
    """
    aberta = _sessao_do_codigo(sessao, codigo, agora)
    if aberta is None or aberta.falta is not None:
        return None
    return _conta_ativa(sessao, aberta)


def sessao_pela_metade(sessao: Session, codigo: str, agora: datetime) -> SessaoPelaMetade | None:
    """A sessão pela metade do código, ou ``None`` se não há uma que valha (D-60)."""
    aberta = _sessao_do_codigo(sessao, codigo, agora)
    if aberta is None or aberta.falta is None:
        return None
    conta = _conta_ativa(sessao, aberta)
    return SessaoPelaMetade(conta=conta, falta=aberta.falta) if conta else None


def preparar_ligacao(
    sessao: Session, cifra: Cifra, *, codigo_da_sessao: str, agora: datetime
) -> Ligacao:
    """O segredo do app para ligar a verificação: novo na primeira vez, o mesmo depois.

    A verificação só fica ligada quando um código do app confirma (``ligar``).

    Raises:
        NaoIdentificadoError: sem uma sessão pela metade que espera ligar a verificação.
    """
    conta = _metade_que_espera(sessao, codigo_da_sessao, agora, "ligar")
    if conta.duas_etapas_cifrado is None:
        conta.duas_etapas_cifrado = cifra.cifrar(duas_etapas.novo_segredo())
        sessao.flush()
    return Ligacao(email=conta.email, segredo=cifra.decifrar(conta.duas_etapas_cifrado))


def ligar(
    sessao: Session,
    senhas: Senhas,
    cifra: Cifra,
    *,
    codigo_da_sessao: str,
    digitado: str,
    agora: datetime,
) -> Ligada:
    """Liga a verificação com o primeiro código do app e abre a sessão de sempre.

    Returns:
        O código da sessão nova e os códigos de recuperação (o banco guarda só o resumo deles).

    Raises:
        NaoIdentificadoError: sem uma sessão pela metade que espera ligar a verificação.
        MuitasTentativasError: se a conta errou o código demais nos últimos 15 minutos.
        LoginRecusadoError: se o código não confere (o erro fica gravado).
    """
    conta = _metade_que_espera(sessao, codigo_da_sessao, agora, "ligar")
    alvo = _alvo_das_duas_etapas(conta)
    _recusar_se_bloqueado(sessao, alvo, agora)
    if not _confere_o_app(conta, cifra, digitado, agora):
        _registrar_erro(sessao, alvo, agora)
        raise LoginRecusadoError
    _esquecer_erros(sessao, alvo)
    conta.duas_etapas_desde = agora
    recuperacao = _novos_codigos_de_recuperacao(sessao, senhas, conta)
    sair(sessao, codigo_da_sessao)
    return Ligada(codigo_da_sessao=abrir_sessao(sessao, conta, agora), recuperacao=recuperacao)


def confirmar_codigo(
    sessao: Session,
    senhas: Senhas,
    cifra: Cifra,
    *,
    codigo_da_sessao: str,
    digitado: str,
    agora: datetime,
) -> str:
    """Confere o código do app (ou um código de recuperação) e abre a sessão de sempre.

    Returns:
        O código da sessão nova; a sessão pela metade é fechada.

    Raises:
        NaoIdentificadoError: sem uma sessão pela metade que espera o código.
        MuitasTentativasError: se a conta errou o código demais nos últimos 15 minutos.
        LoginRecusadoError: se o código não confere (o erro fica gravado).
    """
    conta = _metade_que_espera(sessao, codigo_da_sessao, agora, "codigo")
    alvo = _alvo_das_duas_etapas(conta)
    _recusar_se_bloqueado(sessao, alvo, agora)
    if not _confere_o_app(conta, cifra, digitado, agora) and not _usa_a_recuperacao(
        sessao, senhas, conta, digitado, agora
    ):
        _registrar_erro(sessao, alvo, agora)
        raise LoginRecusadoError
    _esquecer_erros(sessao, alvo)
    sair(sessao, codigo_da_sessao)
    return abrir_sessao(sessao, conta, agora)


def zerar_duas_etapas(
    sessao: Session, conta: Conta, *, agora: datetime, por: Administrador | None = None
) -> None:
    """Desliga a verificação de quem perdeu o celular, e fecha as sessões dele (D-60).

    Na próxima entrada, a conta liga a verificação de novo, se o ambiente exigir.

    Args:
        por: quem da administração zerou (fica no usuário); vazio quando é pelo comando do
            servidor.
    """
    conta.duas_etapas_cifrado = None
    conta.duas_etapas_desde = None
    conta.duas_etapas_passo = None
    if isinstance(conta, Usuario):
        conta.duas_etapas_zerada_em = agora
        conta.duas_etapas_zerada_por = por.id if por else None
        de_quem = CodigoRecuperacao.usuario_id == conta.id
        sessoes = SessaoLogin.usuario_id == conta.id
    else:
        de_quem = CodigoRecuperacao.administrador_id == conta.id
        sessoes = SessaoLogin.administrador_id == conta.id
    sessao.execute(delete(CodigoRecuperacao).where(de_quem))
    sessao.execute(delete(SessaoLogin).where(sessoes))
    sessao.flush()


def _sessao_do_codigo(sessao: Session, codigo: str, agora: datetime) -> SessaoLogin | None:
    return sessao.scalar(
        select(SessaoLogin).where(
            SessaoLogin.codigo_resumo == resumo_rapido(codigo), SessaoLogin.expira_em > agora
        )
    )


def _conta_ativa(sessao: Session, aberta: SessaoLogin) -> Conta | None:
    conta: Conta | None
    if aberta.usuario_id is not None:
        conta = sessao.get(Usuario, aberta.usuario_id)
    else:
        conta = sessao.get(Administrador, aberta.administrador_id)
    return conta if conta is not None and conta.ativo else None


def _metade_que_espera(sessao: Session, codigo: str, agora: datetime, falta: Falta) -> Conta:
    metade = sessao_pela_metade(sessao, codigo, agora)
    if metade is None or metade.falta != falta:
        raise NaoIdentificadoError
    return metade.conta


def _alvo_das_duas_etapas(conta: Conta) -> str:
    tipo = "usuario" if isinstance(conta, Usuario) else "administracao"
    return resumo_rapido(f"duas-etapas:{tipo}:{conta.id}")


def _confere_o_app(conta: Conta, cifra: Cifra, digitado: str, agora: datetime) -> bool:
    if conta.duas_etapas_cifrado is None:
        return False
    passo = duas_etapas.conferir(
        cifra.decifrar(conta.duas_etapas_cifrado),
        digitado,
        agora=agora,
        ultimo_passo=conta.duas_etapas_passo,
    )
    if passo is None:
        return False
    conta.duas_etapas_passo = passo
    return True


def _usa_a_recuperacao(
    sessao: Session, senhas: Senhas, conta: Conta, digitado: str, agora: datetime
) -> bool:
    codigo = duas_etapas.normalizar_recuperacao(digitado)
    if codigo is None:
        return False
    for guardado in sessao.scalars(
        _recuperacao_de(conta).where(CodigoRecuperacao.usado_em.is_(None))
    ):
        if senhas.confere(guardado.resumo, codigo):
            guardado.usado_em = agora
            sessao.flush()
            return True
    return False


def _recuperacao_de(conta: Conta) -> Select[CodigoRecuperacao]:
    if isinstance(conta, Usuario):
        return select(CodigoRecuperacao).where(CodigoRecuperacao.usuario_id == conta.id)
    return select(CodigoRecuperacao).where(CodigoRecuperacao.administrador_id == conta.id)


def _novos_codigos_de_recuperacao(sessao: Session, senhas: Senhas, conta: Conta) -> list[str]:
    codigos = duas_etapas.novos_codigos_de_recuperacao()
    if isinstance(conta, Usuario):
        sessao.execute(delete(CodigoRecuperacao).where(CodigoRecuperacao.usuario_id == conta.id))
        dono = {"usuario_id": conta.id, "empresa_id": conta.empresa_id}
    else:
        sessao.execute(
            delete(CodigoRecuperacao).where(CodigoRecuperacao.administrador_id == conta.id)
        )
        dono = {"administrador_id": conta.id}
    sessao.add_all(CodigoRecuperacao(resumo=senhas.resumir(c), **dono) for c in codigos)
    sessao.flush()
    return codigos


def porteiros_da_troca(sessao: Session, usuario_id: int) -> list[Usuario]:
    """Os porteiros que podem assumir o tablet deste usuário, por nome.

    São os porteiros ativos da mesma empresa com pelo menos um site em comum, menos ele mesmo.
    """
    return list(sessao.scalars(_consulta_dos_porteiros_da_troca(sessao, usuario_id)))


def trocar_porteiro(
    sessao: Session, senhas: Senhas, *, codigo: str, porteiro_id: int, pin: str, agora: datetime
) -> str:
    """Passa a sessão aberta no tablet para o porteiro do turno, que confirma com o PIN.

    Returns:
        O código da nova sessão, do porteiro; a sessão antiga é fechada.

    Raises:
        NaoEncontradoError: se a sessão não for de um usuário do cliente, ou se o porteiro não
            estiver entre os da troca (outra empresa, outro site, outro papel, desativado).
        MuitasTentativasError: se o PIN deste porteiro errou demais nos últimos 15 minutos.
        LoginRecusadoError: se o PIN não conferir (o erro fica gravado).
    """
    atual = conta_da_sessao(sessao, codigo, agora)
    if not isinstance(atual, Usuario):
        raise NaoEncontradoError(f"porteiro {porteiro_id}")
    consulta = _consulta_dos_porteiros_da_troca(sessao, atual.id).where(Usuario.id == porteiro_id)
    porteiro = sessao.scalar(consulta)
    if porteiro is None:
        raise NaoEncontradoError(f"porteiro {porteiro_id}")
    alvo = resumo_rapido(f"pin:{porteiro.id}")
    _recusar_se_bloqueado(sessao, alvo, agora)
    if porteiro.pin_resumo is None or not senhas.confere(porteiro.pin_resumo, pin):
        _registrar_erro(sessao, alvo, agora)
        raise LoginRecusadoError
    _esquecer_erros(sessao, alvo)
    sair(sessao, codigo)
    return abrir_sessao(sessao, porteiro, agora)


def _consulta_dos_porteiros_da_troca(sessao: Session, usuario_id: int) -> Select[Usuario]:
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise NaoEncontradoError(f"usuário {usuario_id}")
    sites_dele = select(UsuarioSite.site_id).where(UsuarioSite.usuario_id == usuario.id)
    com_site_em_comum = (
        select(UsuarioSite.usuario_id)
        .where(UsuarioSite.empresa_id == usuario.empresa_id)
        .where(UsuarioSite.site_id.in_(sites_dele))
    )
    return (
        select(Usuario)
        .where(
            Usuario.empresa_id == usuario.empresa_id,
            Usuario.papel == "porteiro",
            Usuario.ativo,
            Usuario.id != usuario.id,
            Usuario.id.in_(com_site_em_comum),
        )
        .order_by(Usuario.nome)
    )


def abrir_sessao(
    sessao: Session, conta: Conta, agora: datetime, *, falta: Falta | None = None
) -> str:
    """Abre uma sessão para a conta, sem conferir nada: quem chama já sabe quem é.

    Além da senha e do PIN, só o link de demonstração abre sessão assim (D-54), depois de
    conferir o código do link.

    Args:
        falta: o que falta para a sessão valer (D-60); com ele, a sessão é pela metade e vale
            só 10 minutos.

    Returns:
        O código da sessão, para o cookie (o banco guarda só o resumo dele).
    """
    codigo = secrets.token_urlsafe(32)
    validade = duas_etapas.VALIDADE_DA_SESSAO_PELA_METADE if falta else VALIDADE_DA_SESSAO
    aberta = SessaoLogin(
        codigo_resumo=resumo_rapido(codigo),
        criada_em=agora,
        expira_em=agora + validade,
        falta=falta,
    )
    if isinstance(conta, Usuario):
        aberta.usuario_id = conta.id
        aberta.empresa_id = conta.empresa_id
    else:
        aberta.administrador_id = conta.id
    sessao.add(aberta)
    sessao.flush()
    return codigo


def _recusar_se_bloqueado(
    sessao: Session, alvo: str, agora: datetime, maximo: int = MAXIMO_DE_ERROS
) -> None:
    # Uma tentativa por vez para o mesmo alvo. Sem a trava, pedidos ao mesmo tempo contariam os
    # erros antes de qualquer um gravar o seu, e todos passariam do limite.
    sessao.execute(select(func.pg_advisory_xact_lock(_chave_da_trava(alvo))))
    erros = sessao.scalar(
        select(func.count())
        .select_from(TentativaLogin)
        .where(
            TentativaLogin.alvo_resumo == alvo,
            TentativaLogin.momento > agora - JANELA_DAS_TENTATIVAS,
        )
    )
    if erros is not None and erros >= maximo:
        raise MuitasTentativasError


def _registrar_erro(sessao: Session, alvo: str, agora: datetime) -> None:
    # Aproveita para apagar os erros deste alvo que já saíram da janela.
    sessao.execute(
        delete(TentativaLogin).where(
            TentativaLogin.alvo_resumo == alvo,
            TentativaLogin.momento <= agora - JANELA_DAS_TENTATIVAS,
        )
    )
    sessao.add(TentativaLogin(alvo_resumo=alvo, momento=agora))
    sessao.flush()


def _esquecer_erros(sessao: Session, alvo: str) -> None:
    sessao.execute(delete(TentativaLogin).where(TentativaLogin.alvo_resumo == alvo))
    sessao.flush()


def _chave_da_trava(alvo: str) -> int:
    # A trava do PostgreSQL leva um número: os primeiros 60 bits do resumo cabem no bigint.
    return int(alvo[:15], 16)

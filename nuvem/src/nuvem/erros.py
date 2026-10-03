"""Erros de regra da nuvem, comuns a todos os módulos."""


class NaoEncontradoError(Exception):
    """O registro não existe ou não pertence a quem pediu: para quem pediu, dá no mesmo.

    A API responde 404 sem dizer qual dos dois, para não revelar dado de outra empresa.
    """


class DadoInvalidoError(ValueError):
    """Um dado recebido não segue a regra do cadastro (a mensagem diz qual)."""


class NaoIdentificadoError(Exception):
    """Ninguém entrou no sistema (sem sessão, ou sessão vencida): a API responde 401."""


class SemPermissaoError(Exception):
    """Quem pede entrou, mas o papel dele não permite isto: a API responde 403."""

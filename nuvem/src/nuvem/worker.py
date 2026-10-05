"""O worker da nuvem (SDD 6.1 e D-38): ``python -m nuvem.worker``.

Executa as tarefas da fila (o casamento das passagens), confere o "não veio", prepara as
mensagens e, nos ambientes que têm, avança o dia de demonstração (D-49), até receber o sinal de
parar (SIGTERM do Docker, ou Ctrl+C). Lê a configuração do ambiente, como a API.
"""

import logging
import signal
import threading
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from nuvem import tarefas_de_fundo
from nuvem.armazenamento import ArmazenamentoLocal
from nuvem.banco import criar_motor
from nuvem.cifra import Cifra
from nuvem.config import ConfiguracaoInvalidaError, ler_configuracao
from nuvem.demonstracao import dia as dia_de_demonstracao

_registro = logging.getLogger("nuvem.worker")


def main() -> None:
    """Sobe o worker e roda até o sinal de parar."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    try:
        configuracao = ler_configuracao()
    except ConfiguracaoInvalidaError as erro:
        raise SystemExit(f"erro: {erro}") from None
    motor = criar_motor(configuracao.url_banco.get_secret_value())
    parar = threading.Event()
    avancar_a_demonstracao = None
    if configuracao.tem_demonstracao:
        armazenamento = ArmazenamentoLocal(
            configuracao.pasta_fotos, Cifra(configuracao.chave_cifra)
        )

        def avancar_a_demonstracao(sessao: Session, agora: datetime) -> int:
            return dia_de_demonstracao.avancar(sessao, agora=agora, armazenamento=armazenamento)

    for sinal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sinal, lambda *_: parar.set())
    _registro.info("worker no ar")
    try:
        tarefas_de_fundo.rodar(sessionmaker(motor), parar, demonstracao=avancar_a_demonstracao)
    finally:
        motor.dispose()
        _registro.info("worker parado")


if __name__ == "__main__":
    main()

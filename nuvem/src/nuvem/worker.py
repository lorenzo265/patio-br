"""O worker da nuvem (SDD 6.1 e D-38): ``python -m nuvem.worker``.

Executa as tarefas da fila (o casamento das passagens) e confere o "não veio", até receber o
sinal de parar (SIGTERM do Docker, ou Ctrl+C). Lê a configuração do ambiente, como a API.
"""

import logging
import signal
import threading

from sqlalchemy.orm import sessionmaker

from nuvem import tarefas_de_fundo
from nuvem.banco import criar_motor
from nuvem.config import ConfiguracaoInvalidaError, ler_configuracao

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
    for sinal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sinal, lambda *_: parar.set())
    _registro.info("worker no ar")
    try:
        tarefas_de_fundo.rodar(sessionmaker(motor), parar)
    finally:
        motor.dispose()
        _registro.info("worker parado")


if __name__ == "__main__":
    main()

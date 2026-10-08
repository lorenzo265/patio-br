"""O worker da nuvem (SDD 6.1 e D-38): ``python -m nuvem.worker``.

Executa as tarefas da fila (o casamento das passagens; o envio das mensagens e o aviso do
WhatsApp, D-63; o resumo das fotos, D-69), confere o "não veio" e os alertas, prepara as
mensagens, sela a prova e grava a âncora do dia (D-69) e, nos ambientes que têm, avança o dia de
demonstração (D-49) e apaga as empresas dos links de demonstração vencidos (D-54), até receber o
sinal de parar (SIGTERM do Docker, ou Ctrl+C). Lê a configuração do ambiente, como a API.
"""

import logging
import signal
import threading
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from nuvem import tarefas_de_fundo
from nuvem.armazenamento import armazenamento_da_configuracao
from nuvem.banco import motor_da_configuracao
from nuvem.cifra import Cifra
from nuvem.config import ConfiguracaoInvalidaError, ler_configuracao
from nuvem.demonstracao import dia as dia_de_demonstracao
from nuvem.demonstracao import link as links_de_demonstracao
from nuvem.mensagens import sms, whatsapp
from nuvem.mensagens.canais import Canais
from nuvem.prova.ancoras import guarda_da_configuracao

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
    motor = motor_da_configuracao(configuracao)
    parar = threading.Event()
    avancar_a_demonstracao = None
    armazenamento = armazenamento_da_configuracao(configuracao, Cifra(configuracao.chave_cifra))
    if configuracao.tem_demonstracao:
        faxina = links_de_demonstracao.Faxina(armazenamento)

        def avancar_a_demonstracao(sessao: Session, agora: datetime) -> int:
            faxina(sessao, agora)
            return dia_de_demonstracao.avancar(sessao, agora=agora, armazenamento=armazenamento)

    canais = Canais(
        whatsapp=whatsapp.canal_da_configuracao(configuracao),
        sms=sms.canal_da_configuracao(configuracao),
    )
    for sinal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sinal, lambda *_: parar.set())
    _registro.info(
        "worker no ar (WhatsApp %s, SMS %s)",
        "ligado" if canais.whatsapp else "desligado",
        "ligado" if canais.sms else "desligado",
    )
    try:
        tarefas_de_fundo.rodar(
            sessionmaker(motor),
            parar,
            demonstracao=avancar_a_demonstracao,
            canais=canais,
            armazenamento=armazenamento,
            ancoras=guarda_da_configuracao(configuracao),
        )
    finally:
        motor.dispose()
        _registro.info("worker parado")


if __name__ == "__main__":
    main()

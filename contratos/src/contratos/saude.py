"""A Saude: o que a caixa de borda conta de si à nuvem, a cada minuto (SDD 3.2 e 7.4, D-65).

A saúde não entra na fila da caixa: sem internet, ela não é guardada, e a próxima vai um minuto
depois. Mudou o formato, muda a versão do contrato, como na passagem.
"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

_Texto = Annotated[str, Field(min_length=1, max_length=100)]
_Uso = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
"""Um uso em %, de 0 a 100."""
_Contagem = Annotated[int, Field(ge=0)]

TEMPERATURA_MINIMA = -60.0
TEMPERATURA_MAXIMA = 150.0
"""Fora disso, a leitura do sensor não é de verdade."""

MAXIMO_DE_CAMERAS = 64

_CONFIGURACAO = ConfigDict(extra="forbid", frozen=True, use_attribute_docstrings=True)


class SaudeDaCamera(BaseModel):
    """Uma câmera de placa aberta pela caixa."""

    model_config = _CONFIGURACAO

    camera_id: _Texto
    """A câmera, pelo id da nuvem (o mesmo da configuração)."""
    no_ar: bool
    """Se mandou quadro nos últimos 10 segundos."""
    quadros_por_segundo: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    """Os quadros que chegaram ao agente nos últimos 10 segundos, por segundo."""
    ultimo_quadro: AwareDatetime | None
    """Quando chegou o último quadro, no relógio da caixa; vazio se nunca chegou."""


class FilaDaCaixa(BaseModel):
    """O que espera o envio na caixa."""

    model_config = _CONFIGURACAO

    passagens: _Contagem
    """As passagens esperando o envio."""
    fotos: _Contagem
    """As fotos esperando o envio."""
    recusadas: _Contagem
    """As passagens que a nuvem recusou de vez, guardadas à parte na caixa."""


class Saude(BaseModel):
    """A saúde da caixa num momento: as versões, a máquina, as câmeras e a fila."""

    model_config = _CONFIGURACAO

    versao_contrato: Literal[1]
    """Versão deste formato."""
    caixa_id: _Texto
    """A caixa, pelo id da nuvem (o mesmo das passagens)."""
    site_id: _Texto
    """O site da caixa."""
    momento: AwareDatetime
    """A hora da caixa, com fuso: a nuvem mede a diferença do relógio."""
    versao_programa: _Texto
    """A versão do programa da caixa."""
    versao_leitor: _Texto
    """A versão do leitor de placas."""
    cpu: _Uso
    """O uso da CPU, em %, desde a saúde anterior."""
    temperatura: (
        Annotated[float, Field(ge=TEMPERATURA_MINIMA, le=TEMPERATURA_MAXIMA, allow_inf_nan=False)]
        | None
    )
    """A temperatura do sensor mais quente, em °C; vazia se a máquina não diz."""
    memoria: _Uso
    """O uso da memória, em %."""
    disco: _Uso
    """O uso do disco da fila, em %."""
    cameras: Annotated[tuple[SaudeDaCamera, ...], Field(max_length=MAXIMO_DE_CAMERAS)]
    """As câmeras de placa abertas pela caixa."""
    fila: FilaDaCaixa
    """O que espera o envio."""

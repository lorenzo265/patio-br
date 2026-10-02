"""A Passagem: o único formato que a borda envia à nuvem (SDD 3.2).

Uma passagem é o registro de um veículo passando por uma faixa da portaria: as placas lidas,
as fotos e os horários da caixa. Mudou o formato, muda a versão do contrato.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from contratos.placa import Placa

Sentido = Literal["entrada", "saida"]
Papel = Literal["cavalo", "reboque", "desconhecido"]
TipoDeFoto = Literal["placa", "contexto"]

_Texto = Annotated[str, Field(min_length=1)]

_CONFIGURACAO = ConfigDict(
    # Campo desconhecido é mudança de formato: exige versão nova do contrato, não entra calado.
    extra="forbid",
    # A passagem é prova da chegada (SDD 5.5): depois de criada, não se altera (por isso as
    # listas são tuplas).
    frozen=True,
    # As descrições do JSON Schema vêm das docstrings dos campos.
    use_attribute_docstrings=True,
)


class PlacaLida(BaseModel):
    """Uma placa lida por uma câmera durante a passagem.

    Só o que a câmera viu. A placa que a câmera não vê (o reboque do meio de um bitrem) é
    completada pela nuvem no casamento com o agendamento e registrada na visita (SDD 4.3).
    """

    model_config = _CONFIGURACAO

    placa: Placa
    """Placa canônica: ABC1234 (antiga) ou ABC1D23 (Mercosul)."""
    papel: Papel
    """Parte da composição: o cavalo (câmera da frente) ou um reboque (câmera de trás)."""
    confianca: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    """Confiança do leitor na placa, de 0 a 1."""
    camera_id: _Texto
    """Câmera que leu a placa."""
    quadros: Annotated[int, Field(ge=1)]
    """Em quantos quadros do vídeo a placa foi lida (a votação junta esses quadros)."""


class Foto(BaseModel):
    """Referência a uma foto já enviada ao armazenamento; a passagem não carrega a imagem."""

    model_config = _CONFIGURACAO

    tipo: TipoDeFoto
    """Recorte da placa ou foto de contexto (com os rostos borrados na caixa)."""
    camera_id: _Texto
    """Câmera que tirou a foto."""
    ref: _Texto
    """Endereço da foto no armazenamento."""


class Passagem(BaseModel):
    """Um veículo passando por uma faixa da portaria, como a caixa de borda o viu."""

    model_config = _CONFIGURACAO

    versao_contrato: Literal[1]
    """Versão deste formato."""
    id: UUID
    """Gerado na caixa. A nuvem ignora um id já recebido, então a caixa pode reenviar."""
    caixa_id: _Texto
    """Caixa de borda que gerou a passagem."""
    site_id: _Texto
    """Site do cliente onde fica a portaria."""
    faixa_id: _Texto
    """Faixa da portaria por onde o veículo passou."""
    sentido: Sentido
    """Entrada ou saída do site."""
    inicio: AwareDatetime
    """Quando o veículo começou a passar, no relógio da caixa, com fuso."""
    fim: AwareDatetime
    """Quando terminou de passar; nunca antes do início."""
    placas: tuple[PlacaLida, ...]
    """Placas lidas. Vazia quando nenhuma foi lida: a nuvem trata como exceção."""
    fotos: tuple[Foto, ...]
    """Fotos da passagem."""
    versao_leitor: _Texto
    """Versão do leitor de placas que rodou na caixa."""

    @field_validator("fim")
    @classmethod
    def _fim_nao_antecede_o_inicio(cls, fim: datetime, info: ValidationInfo) -> datetime:
        # Compara instantes, não o relógio: os dois podem vir em fusos diferentes.
        inicio = info.data.get("inicio")  # ausente se o próprio início foi recusado
        if inicio is not None and fim < inicio:
            raise ValueError(f"o fim ({fim.isoformat()}) é antes do início ({inicio.isoformat()})")
        return fim

"""Cifra dos segredos guardados no banco (ex.: senha da câmera)."""

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from nuvem.cifra import Cifra, SegredoIlegivelError


def _cifra_nova() -> Cifra:
    return Cifra(SecretStr(Fernet.generate_key().decode()))


def test_o_que_foi_cifrado_volta_igual() -> None:
    cifra = _cifra_nova()

    assert cifra.decifrar(cifra.cifrar("senha da câmera")) == "senha da câmera"


def test_texto_cifrado_nao_contem_o_original() -> None:
    assert "senha da câmera" not in _cifra_nova().cifrar("senha da câmera")


def test_outra_chave_nao_decifra() -> None:
    cifrado = _cifra_nova().cifrar("senha")

    with pytest.raises(SegredoIlegivelError):
        _cifra_nova().decifrar(cifrado)


def test_chave_invalida_e_recusada_ao_criar() -> None:
    with pytest.raises(ValueError, match="chave"):
        Cifra(SecretStr("curta-demais"))

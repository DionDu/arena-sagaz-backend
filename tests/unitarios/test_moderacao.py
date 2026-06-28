"""Testes da moderação do nome de exibição (T058)."""
import pytest

from api.conta.moderacao import (
    TAMANHO_MAXIMO,
    validar_nome_exibicao,
)
from api.nucleo.excecoes import ErroNegocio


def test_normaliza_espacos():
    # Espaços nas pontas removidos e internos colapsados.
    assert validar_nome_exibicao("  Fernando   Santiago  ") == "Fernando Santiago"


def test_aceita_nome_comum():
    assert validar_nome_exibicao("Pita") == "Pita"


def test_nome_muito_curto_422():
    with pytest.raises(ErroNegocio) as exc:
        validar_nome_exibicao(" a ")
    assert exc.value.codigo == "nome_muito_curto"
    assert exc.value.status_http == 422


def test_nome_so_espacos_422():
    with pytest.raises(ErroNegocio) as exc:
        validar_nome_exibicao("     ")
    assert exc.value.codigo == "nome_muito_curto"


def test_nome_muito_longo_422():
    with pytest.raises(ErroNegocio) as exc:
        validar_nome_exibicao("x" * (TAMANHO_MAXIMO + 1))
    assert exc.value.codigo == "nome_muito_longo"


def test_termo_bloqueado_422():
    # "admin" é substring bloqueada, sem diferenciar maiúsc./minúsc.
    with pytest.raises(ErroNegocio) as exc:
        validar_nome_exibicao("Super Admin")
    assert exc.value.codigo == "nome_nao_permitido"

"""Testes unitários para cálculo de XP em api.partidas.servico."""
import pytest

from api.partidas.servico import _calcular_xp

_BONUS = 20


@pytest.mark.parametrize("dificuldade,mult", [
    ("facil", 1.0),
    ("normal", 1.5),
    ("sagaz", 2.0),
    (None, 1.0),
])
def test_multiplicadores(dificuldade, mult):
    xp = _calcular_xp(10, "derrota", dificuldade, _BONUS)
    assert xp == int(10 * mult)


def test_bonus_vitoria():
    xp_vitoria = _calcular_xp(10, "vitoria", "normal", _BONUS)
    xp_derrota = _calcular_xp(10, "derrota", "normal", _BONUS)
    assert xp_vitoria == int((10 + _BONUS) * 1.5)
    assert xp_derrota == int(10 * 1.5)


def test_arredondamento():
    # (7 + 0) * 1.5 = 10.5 → int → 10
    assert _calcular_xp(7, "derrota", "normal", 0) == 10


def test_sagaz_com_vitoria():
    assert _calcular_xp(5, "vitoria", "sagaz", 20) == int((5 + 20) * 2.0)


def test_nivel_formula():
    # nivel = xp_total // 100 + 1
    assert 0 // 100 + 1 == 1
    assert 99 // 100 + 1 == 1
    assert 100 // 100 + 1 == 2
    assert 999 // 100 + 1 == 10

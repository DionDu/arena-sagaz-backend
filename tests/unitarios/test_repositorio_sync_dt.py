"""Testa o conversor de data ISO→datetime do repositório de sincronização.

Motivo: o app envia ``dh_inicio``/``dh_fim`` como STRING ISO-8601, e o asyncpg
NÃO aceita string em colunas ``timestamptz`` (só ``datetime``). O ``_dt`` faz a
ponte — sem ele, gravar a partida estoura com 500 e o evento fica "pendente".
"""
from datetime import datetime

from api.sincronizacao.repositorio import _dt


def test_string_iso_do_app_vira_datetime():
    # Formato que o Dart `toIso8601String()` produz (sem timezone).
    d = _dt("2026-07-04T11:38:00.000")
    assert isinstance(d, datetime)
    assert (d.year, d.month, d.day, d.hour, d.minute) == (2026, 7, 4, 11, 38)


def test_string_iso_com_z_utc():
    d = _dt("2026-07-04T11:38:00Z")
    assert isinstance(d, datetime)
    assert d.tzinfo is not None  # 'Z' vira offset UTC explícito


def test_none_passa_direto():
    assert _dt(None) is None


def test_datetime_passa_direto():
    agora = datetime(2026, 7, 4, 11, 38)
    assert _dt(agora) is agora


def test_string_invalida_vira_none():
    assert _dt("nao-e-data") is None

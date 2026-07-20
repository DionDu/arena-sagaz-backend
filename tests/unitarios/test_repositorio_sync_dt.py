"""Testa o conversor de data ISO→datetime do repositório de sincronização.

Motivo: o app envia ``dh_inicio``/``dh_fim`` como STRING ISO-8601, e o asyncpg
NÃO aceita string em colunas ``timestamptz`` (só ``datetime``). O ``_dt`` faz a
ponte — sem ele, gravar a partida estoura com 500 e o evento fica "pendente".
"""
from datetime import date, datetime

from api.sincronizacao.repositorio import _dt, calcular_sequencia_de_dias


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


# ── Chama (sequência) autoritativa a partir dos DIAS LOCAIS de jogo ────────────
# Regra "gentil" (mesma do app): +1 por dia consecutivo; decai (gap-1) ao faltar,
# nunca abaixo de 1; lista vazia = 0. É a correção definitiva do bug em que jogos
# da noite (BRT) caíam no dia seguinte por serem contados em UTC.


def test_chama_vazia_e_zero():
    assert calcular_sequencia_de_dias([]) == 0


def test_chama_um_dia_e_um():
    assert calcular_sequencia_de_dias([date(2026, 7, 18)]) == 1


def test_chama_dias_consecutivos_crescem():
    # O caso do relato: jogou 18, 19 e 20 → chama 3 (não 1).
    dias = [date(2026, 7, 18), date(2026, 7, 19), date(2026, 7, 20)]
    assert calcular_sequencia_de_dias(dias) == 3


def test_chama_muitos_dias_seguidos():
    dias = [date(2026, 6, d) for d in range(1, 11)]  # 10 dias em fila
    assert calcular_sequencia_de_dias(dias) == 10


def test_chama_decai_com_gentileza_sem_zerar():
    # 16,17,18,19 → 4; pula o 20; volta no 21 → decai 1 → 3 (não zera).
    dias = [
        date(2026, 6, 16),
        date(2026, 6, 17),
        date(2026, 6, 18),
        date(2026, 6, 19),
        date(2026, 6, 21),
    ]
    assert calcular_sequencia_de_dias(dias) == 3


def test_chama_gap_grande_nunca_abaixo_de_um():
    # 2 dias seguidos (chama 2), some por uma semana, volta: decai muito → piso 1.
    dias = [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 12)]
    assert calcular_sequencia_de_dias(dias) == 1

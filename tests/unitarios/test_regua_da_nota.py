"""🔒 A REGUA DA NOTA QUE A `0030` INSERE (T102, DECISOES-do-dono §8zzo).

O que estes casos protegem:

  · ⚠️ **a soma dos pesos de cada versao fecha em 1,000.** Ela atravessa linhas
    da `tb905_parcela_regua_nota`, e por isso nao cabe num `CHECK` do banco -
    sem este cadeado, uma versao com 0,95 entraria calada e toda nota sairia
    5% menor, sem erro nenhum;
  · **a versao 1 e a regua que o codigo usa hoje** (`extrato_xp.py`): ela
    existe para pontuar um reenvio atrasado de um dia antigo do mesmo jeito que
    os outros daquele dia foram pontuados;
  · **a versao 2 e a da §8zzo**, com os numeros que o dono aprovou.

⚠️ Os numeros da versao 2 estao escritos a mao, e nao lidos de outro lugar: um
caso que lesse a propria migracao para conferir a migracao passaria com
qualquer valor (memoria "teste nao se mede pela propria regua").
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from api.desafios.extrato_xp import (
    PESO_DICA,
    PESO_MERITO,
    PESO_TEMPO,
    PESO_TENTATIVAS,
    TENTATIVAS_QUE_ZERAM_A_PARCELA,
    TETO_DE_DICAS,
)
from api.desafios.modelos_evento import XP_DICA, XP_MERITO, XP_TEMPO, XP_TENTATIVAS
from tests.unitarios.leitura_de_migracao import sql_da_migracao

# `parents[2]` sobe de tests/unitarios/ ate a raiz do backend.
MIGRACAO = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "0030_regua_da_nota.py"
)


def _parcelas() -> dict[int, dict[int, tuple]]:
    """`{versao: {nu_tipo_xp: (peso, forma, x0, escala)}}`, do `INSERT` da 0030.

    ⚠️ A regex le cada tupla `(versao, tipo, peso, 'forma', x0, escala)` do
    `INSERT INTO ...tb905_parcela_regua_nota`; `NULL` vira `None`.
    """
    sql = sql_da_migracao(MIGRACAO)
    insert = sql[sql.index("INSERT INTO desafio_dia.tb905_parcela_regua_nota") :]
    tuplas = re.findall(
        r"\(\s*(\d+),\s*(\d+),\s*([\d.]+),\s*'(\w+)',\s*(\w+|[\d.]+),\s*(\w+|[\d.]+)\s*\)",
        insert,
    )
    assert tuplas, "⛔ nenhuma parcela lida: o cadeado ficaria cego"

    def numero(texto: str):
        return None if texto == "NULL" else Decimal(texto)

    versoes: dict[int, dict[int, tuple]] = {}
    for versao, tipo, peso, forma, x0, escala in tuplas:
        versoes.setdefault(int(versao), {})[int(tipo)] = (
            Decimal(peso),
            forma,
            numero(x0),
            numero(escala),
        )
    return versoes


def test_toda_versao_tem_as_quatro_parcelas():
    """Tentativas, tempo, dica e merito - nem mais, nem menos, hoje."""
    for versao, parcelas in _parcelas().items():
        assert set(parcelas) == {XP_TENTATIVAS, XP_TEMPO, XP_DICA, XP_MERITO}, versao


def test_a_soma_dos_pesos_de_cada_versao_fecha_em_1():
    """⚠️ O que o banco nao consegue garantir sozinho (atravessa linhas)."""
    for versao, parcelas in _parcelas().items():
        soma = sum(peso for peso, *_ in parcelas.values())
        assert soma == Decimal("1.000"), f"versao {versao}: soma {soma}"


def test_a_versao_1_e_a_regua_que_o_codigo_usa_hoje():
    """Linear, com os pesos e os tetos de `extrato_xp.py` (§8zs)."""
    v1 = _parcelas()[1]
    assert v1[XP_TENTATIVAS] == (
        PESO_TENTATIVAS,
        "linear",
        Decimal(1),
        # Zera na 4a: `(n - 1) / 3`.
        TENTATIVAS_QUE_ZERAM_A_PARCELA - 1,
    )
    # O tempo linear vai ate o teto de cada desafio: a escala fica vazia.
    assert v1[XP_TEMPO] == (PESO_TEMPO, "linear", Decimal(1), None)
    assert v1[XP_DICA] == (PESO_DICA, "linear", Decimal(0), TETO_DE_DICAS)
    assert v1[XP_MERITO] == (PESO_MERITO, "merito", None, None)


def test_a_versao_2_e_a_da_8zzo():
    """Hiperbolica, 50/15/20/15: tentativas `1/n`, tempo `2/(1 + t/piso)`,
    dica `2/(2 + d)`."""
    v2 = _parcelas()[2]
    assert v2[XP_TENTATIVAS] == (Decimal("0.500"), "hiperbolica", Decimal(1), Decimal(1))
    assert v2[XP_TEMPO] == (Decimal("0.150"), "hiperbolica", Decimal(1), Decimal(2))
    assert v2[XP_DICA] == (Decimal("0.200"), "hiperbolica", Decimal(0), Decimal(2))
    assert v2[XP_MERITO] == (Decimal("0.150"), "merito", None, None)


def test_a_vigencia_da_versao_2_e_o_dia_SEGUINTE_em_UTC():
    """⚠️ Calculada na migracao, e em UTC: `CURRENT_DATE` depende do fuso da
    sessao do Postgres, e o dia do desafio e UTC."""
    sql = sql_da_migracao(MIGRACAO)
    assert "CAST((now() AT TIME ZONE 'UTC') AS DATE) + 1" in sql
    assert "CURRENT_DATE" not in sql

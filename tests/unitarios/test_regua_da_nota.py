"""🔒 A REGUA DA NOTA QUE A `0030` INSERE (T102, DECISOES-do-dono §8zzo).

O que estes casos protegem:

  · ⚠️ **a soma dos pesos de cada versao fecha em 1,000.** Ela atravessa linhas
    da `tb905_parcela_regua_nota`, e por isso nao cabe num `CHECK` do banco -
    sem este cadeado, uma versao com 0,95 entraria calada e toda nota sairia
    5% menor, sem erro nenhum;
  · **a versao 1 e a regua de 04/10/2026** (§8zs), que ate a T103 eram
    constantes de `extrato_xp.py`: ela existe para pontuar um reenvio atrasado
    de um dia antigo do mesmo jeito que os outros daquele dia foram pontuados;
  · **a versao 2 e a da §8zzo**, com os numeros que o dono aprovou.

⚠️ Os numeros da versao 2 estao escritos a mao, e nao lidos de outro lugar: um
caso que lesse a propria migracao para conferir a migracao passaria com
qualquer valor (memoria "teste nao se mede pela propria regua").
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from api.desafios.modelos_evento import XP_DICA, XP_MERITO, XP_TEMPO, XP_TENTATIVAS
from api.desafios.regua_da_nota import (
    ReguaDaNotaInvalida,
    nota_da_curva,
    regua_para_publicar,
    regua_vigente,
    reguas_das_linhas,
)
from tests.unitarios.leitura_de_migracao import sql_da_migracao
from tests.unitarios.reguas_de_teste import (
    LINHAS_DAS_REGUAS,
    REGUA_V1,
    REGUA_V2,
    VIGENCIA_V1,
    VIGENCIA_V2,
)

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


def test_a_versao_1_e_a_regua_de_04_10():
    """Linear, 30/30/15/25 (§8zs) - os numeros que eram constantes de
    `extrato_xp.py` ate a T103, escritos a mao."""
    v1 = _parcelas()[1]
    # Zera na 4a: `(n - 1) / 3`.
    assert v1[XP_TENTATIVAS] == (Decimal("0.300"), "linear", Decimal(1), Decimal(3))
    # O tempo linear vai ate o teto de cada desafio: a escala fica vazia.
    assert v1[XP_TEMPO] == (Decimal("0.300"), "linear", Decimal(1), None)
    # Zera na 2a dica: `d / 2`.
    assert v1[XP_DICA] == (Decimal("0.150"), "linear", Decimal(0), Decimal(2))
    assert v1[XP_MERITO] == (Decimal("0.250"), "merito", None, None)


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


# ═══════════════════════════════════════════════════════════════════════════
# O CODIGO QUE LE A REGUA (`api/desafios/regua_da_nota.py`, T103)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    ("dt_dia", "versao"),
    [
        (VIGENCIA_V1, 1),
        (date(2026, 10, 10), 1),
        # ⚠️ A fronteira: no proprio dia da vigencia, ja vale a nova.
        (VIGENCIA_V2, 2),
        (date(2027, 1, 1), 2),
    ],
)
def test_vale_a_de_MAIOR_vigencia_ate_o_dia(dt_dia, versao):
    """A regra da `0030`: a versao de maior `dt_inicio_vigencia` <= `dt_dia`."""
    assert regua_vigente([REGUA_V1, REGUA_V2], dt_dia).nu_versao == versao


def test_a_ordem_das_versoes_na_lista_nao_importa():
    """Quem decide e a data, e nao a posicao na lista."""
    assert regua_vigente([REGUA_V2, REGUA_V1], VIGENCIA_V2).nu_versao == 2


def test_dia_antes_de_qualquer_regua_e_ERRO_e_nao_padrao():
    """⛔ RF-DES-223: sem regua, nao ha nota - e nao "usa a mais antiga"."""
    with pytest.raises(ReguaDaNotaInvalida):
        regua_vigente([REGUA_V1, REGUA_V2], date(2026, 8, 31))


def test_versao_que_nao_soma_1000_e_recusada_na_leitura():
    """⚠️ O que o banco nao garante sozinho, garantido por quem le."""
    linhas = [dict(linha) for linha in LINHAS_DAS_REGUAS if linha["nu_versao_regua"] == 2]
    linhas[0]["vr_peso"] = Decimal("0.450")
    with pytest.raises(ReguaDaNotaInvalida):
        reguas_das_linhas(linhas)


def test_versao_com_MENOS_parcelas_e_aceita_se_somar_1000():
    """O dono quis poder ter mais ou menos parcelas (§8zzq): a parcela que falta
    nao entra na nota, e o merito ausente vale peso zero."""
    linhas = [
        {**LINHAS_DAS_REGUAS[4], "vr_peso": Decimal("0.600")},
        {**LINHAS_DAS_REGUAS[5], "vr_peso": Decimal("0.400")},
    ]
    [regua] = reguas_das_linhas(linhas)
    assert regua.parcela(XP_DICA) is None
    assert regua.peso_do_merito == Decimal(0)


@pytest.mark.parametrize(
    ("medida", "esperado"),
    [(1, "1"), (2, "0.5"), (4, "0.25"), (9, "0.1111")],
)
def test_hiperbolica_de_tentativas_e_1_sobre_n(medida, esperado):
    """`1 / (1 + (n - 1) / 1)` = `1/n`."""
    q = nota_da_curva(REGUA_V2.parcela(XP_TENTATIVAS), Decimal(medida))
    assert round(q, 4) == Decimal(esperado)


@pytest.mark.parametrize(("medida", "esperado"), [(1, "1"), (2, "0.6667"), (4, "0"), (9, "0")])
def test_linear_de_tentativas_zera_na_4a(medida, esperado):
    """`1 - (n - 1) / 3`, presa em zero."""
    q = nota_da_curva(REGUA_V1.parcela(XP_TENTATIVAS), Decimal(medida))
    assert round(q, 4) == Decimal(esperado)


def test_o_tempo_e_medido_em_MULTIPLOS_DO_PISO():
    """`x0` e a escala do tempo estao em multiplos do piso; a medida, em ms."""
    tempo = REGUA_V2.parcela(XP_TEMPO)
    piso = Decimal(20_000)
    assert nota_da_curva(tempo, Decimal(60_000), unidade=piso) == Decimal("0.5")
    assert nota_da_curva(tempo, Decimal(10_000), unidade=piso) == Decimal(1)


def test_o_tempo_LINEAR_sem_escala_vai_ate_o_teto():
    """A versao 1 deixa a escala vazia, e quem a da e o teto do desafio."""
    tempo = REGUA_V1.parcela(XP_TEMPO)
    with pytest.raises(ReguaDaNotaInvalida):
        nota_da_curva(tempo, Decimal(30_000), unidade=Decimal(10_000))
    q = nota_da_curva(
        tempo,
        Decimal(30_000),
        unidade=Decimal(10_000),
        escala_sem_valor=Decimal(40_000),
    )
    assert q == Decimal("0.5")


def test_o_merito_nao_e_curva_de_sessao():
    """⛔ A linha do merito so leva o peso; pedir uma curva a ela e defeito."""
    with pytest.raises(ReguaDaNotaInvalida):
        nota_da_curva(REGUA_V2.parcela(XP_MERITO), Decimal(1))


def test_a_regua_publicada_vai_pelo_NOME_e_na_ordem_da_dimensao():
    """O app recebe `tentativas`, `tempo`, `dica`, `merito` - nessa ordem."""
    publicada = regua_para_publicar(REGUA_V1)
    assert publicada["versao"] == 1
    assert [p["parcela"] for p in publicada["parcelas"]] == [
        "tentativas",
        "tempo",
        "dica",
        "merito",
    ]
    assert publicada["parcelas"][1]["escala"] is None


def test_forma_desconhecida_e_recusada_ATE_dentro_do_x0():
    """⚠️ Dentro de `x0` toda curva da 1: a forma e conferida antes da conta,
    senao uma forma nova passaria calada na resolucao perfeita (achado no teste
    irmao do app, 10/10/2026)."""
    from dataclasses import replace

    futura = replace(REGUA_V2.parcela(XP_TENTATIVAS), co_forma="logistica")
    with pytest.raises(ReguaDaNotaInvalida):
        nota_da_curva(futura, Decimal(1))

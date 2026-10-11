"""🔒 A REGUA DA NOTA QUE AS MIGRACOES `0030` A `0032` INSEREM (T102, §8zzo e §8zzr).

O que estes casos protegem:

  · ⚠️ **a soma dos pesos de cada versao fecha em 1,000.** Ela atravessa linhas
    da `tb905_parcela_regua_nota`, e por isso nao cabe num `CHECK` do banco -
    sem este cadeado, uma versao com 0,95 entraria calada e toda nota sairia
    5% menor, sem erro nenhum;
  · **a versao 1 e a regua de 04/10/2026** (§8zs), que ate a T103 eram
    constantes de `extrato_xp.py`: ela existe para pontuar um reenvio atrasado
    de um dia antigo do mesmo jeito que os outros daquele dia foram pontuados;
  · **a versao 2 e a da §8zzo**, com os numeros que o dono aprovou;
  · ⚠️ **o conserto da vigencia (§8zzr)**: a `0030` entrou no `prd` antes do
    codigo e pos a versao 2 valendo desde 12/10/2026. A `0031` insere a versao
    3 (os numeros da 1) desde 13/10, e a `0032` a versao 4 (os numeros da 2) do
    dia seguinte a liberacao da 1.3.1 - com um piso de 14/10 na data, sem o
    qual a versao 4 podia nascer ANTES da 3 e nunca valer.

⚠️ Os numeros de todas as versoes estao escritos a mao, e nao lidos de outro lugar: um
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
from tests.unitarios.leitura_de_migracao import sql_da_migracao, sql_do_upgrade
from tests.unitarios.reguas_de_teste import (
    LINHAS_DAS_REGUAS,
    REGUA_V1,
    REGUA_V2,
    VIGENCIA_V1,
    VIGENCIA_V2,
)

# `parents[2]` sobe de tests/unitarios/ ate a raiz do backend.
VERSOES = Path(__file__).resolve().parents[2] / "migrations" / "versions"
MIGRACAO = VERSOES / "0030_regua_da_nota.py"
MIGRACAO_0031 = VERSOES / "0031_regua_antiga_ate_liberar.py"
MIGRACAO_0032 = VERSOES / "0032_regua_nova_na_liberacao.py"

#: ⚠️ Toda migracao que insere versao da regua entra aqui - e e por esta lista
#: que a soma 1,000 e as quatro parcelas sao conferidas em TODAS as versoes.
MIGRACOES_DA_REGUA = [MIGRACAO, MIGRACAO_0031, MIGRACAO_0032]


def _parcelas_de(caminho: Path) -> dict[int, dict[int, tuple]]:
    """`{versao: {nu_tipo_xp: (peso, forma, x0, escala)}}`, do `INSERT` de uma
    migracao.

    ⚠️ A regex le cada tupla `(versao, tipo, peso, 'forma', x0, escala)` do
    `INSERT INTO ...tb905_parcela_regua_nota`; `NULL` vira `None`. So o
    `upgrade()` e lido: o `downgrade()` das migracoes do conserto apaga linhas,
    e nao deve ser confundido com o que elas inserem.
    """
    sql = sql_do_upgrade(caminho)
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


def _parcelas() -> dict[int, dict[int, tuple]]:
    """As versoes de TODAS as migracoes da regua, juntas num dicionario so.

    ⚠️ Uma versao repetida em duas migracoes e defeito (a chave primaria
    recusaria no banco) - e aqui ela some calada no `update`, por isso a
    conferencia antes de juntar.
    """
    todas: dict[int, dict[int, tuple]] = {}
    for caminho in MIGRACOES_DA_REGUA:
        desta = _parcelas_de(caminho)
        assert not set(desta) & set(todas), f"versao repetida em {caminho.name}"
        todas.update(desta)
    return todas


def test_as_versoes_sao_1_2_3_e_4():
    """A `0030` insere 1 e 2; a `0031`, a 3; a `0032`, a 4."""
    assert sorted(_parcelas()) == [1, 2, 3, 4]
    assert set(_parcelas_de(MIGRACAO_0031)) == {3}
    assert set(_parcelas_de(MIGRACAO_0032)) == {4}


def test_toda_versao_tem_as_quatro_parcelas():
    """Tentativas, tempo, dica e merito - nem mais, nem menos, hoje."""
    for versao, parcelas in _parcelas().items():
        assert set(parcelas) == {XP_TENTATIVAS, XP_TEMPO, XP_DICA, XP_MERITO}, versao


def test_a_soma_dos_pesos_de_cada_versao_fecha_em_1():
    """⚠️ O que o banco nao consegue garantir sozinho (atravessa linhas)."""
    for versao, parcelas in _parcelas().items():
        soma = sum(peso for peso, *_ in parcelas.values())
        assert soma == Decimal("1.000"), f"versao {versao}: soma {soma}"


@pytest.mark.parametrize("versao", [1, 3])
def test_as_versoes_1_e_3_sao_a_regua_de_04_10(versao):
    """Linear, 30/30/15/25 (§8zs) - os numeros que eram constantes de
    `extrato_xp.py` ate a T103, escritos a mao. A versao 3 (`0031`) e a mesma
    regua de novo: e a conta que a 1.3.0 faz no aparelho (§8zzr)."""
    v1 = _parcelas()[versao]
    # Zera na 4a: `(n - 1) / 3`.
    assert v1[XP_TENTATIVAS] == (Decimal("0.300"), "linear", Decimal(1), Decimal(3))
    # O tempo linear vai ate o teto de cada desafio: a escala fica vazia.
    assert v1[XP_TEMPO] == (Decimal("0.300"), "linear", Decimal(1), None)
    # Zera na 2a dica: `d / 2`.
    assert v1[XP_DICA] == (Decimal("0.150"), "linear", Decimal(0), Decimal(2))
    assert v1[XP_MERITO] == (Decimal("0.250"), "merito", None, None)


@pytest.mark.parametrize("versao", [2, 4])
def test_as_versoes_2_e_4_sao_a_da_8zzo(versao):
    """Hiperbolica, 50/15/20/15: tentativas `1/n`, tempo `2/(1 + t/piso)`,
    dica `2/(2 + d)`. A versao 4 (`0032`) e a mesma regua, valendo da
    liberacao da 1.3.1 (§8zzr)."""
    v2 = _parcelas()[versao]
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
# O CONSERTO DA VIGENCIA (`0031` e `0032`, DECISOES-do-dono §8zzr)
# ═══════════════════════════════════════════════════════════════════════════


def _vigencia_do_cabecalho(caminho: Path) -> str:
    """O texto da data que o `INSERT` em `tb904_regua_nota` grava.

    A regex pega o que vem entre o numero da versao e o `de_motivo` (o texto
    entre aspas simples): `(3, DATE '2026-10-13', 'Os numeros...'`.
    """
    sql = sql_do_upgrade(caminho)
    insert = sql[sql.index("INSERT INTO desafio_dia.tb904_regua_nota") :]
    # `re.S` deixa o `.` atravessar quebras de linha; `.+?` e o menor trecho.
    achado = re.search(r"VALUES\s*\(\s*\d+,\s*(.+?),\s*\n?\s*'[A-Z]", insert, re.S)
    assert achado, f"⛔ vigencia nao lida em {caminho.name}: o cadeado ficaria cego"
    # Espacos e quebras de linha viram um espaco so, para comparar o texto.
    return " ".join(achado.group(1).split())


def test_a_versao_3_vale_de_13_10_com_data_FIXA():
    """⚠️ Fixa, e nao "o dia seguinte": 12/10 ja e da versao 2, e a
    `un001_inicio_vigencia` nao deixa duas versoes no mesmo dia."""
    assert _vigencia_do_cabecalho(MIGRACAO_0031) == "DATE '2026-10-13'"


def test_a_versao_4_vale_do_dia_SEGUINTE_em_UTC_mas_nunca_antes_de_14_10():
    """⚠️ O dia seguinte em UTC (como a `0030`), com o piso de 14/10: aplicada
    no `des` em 11/10, sem o piso, ela nasceria em 12/10 - antes da versao 3."""
    assert _vigencia_do_cabecalho(MIGRACAO_0032) == (
        "GREATEST(CAST((now() AT TIME ZONE 'UTC') AS DATE) + 1, DATE '2026-10-14')"
    )
    assert "CURRENT_DATE" not in sql_do_upgrade(MIGRACAO_0032)


def _versoes_com(vigencia_v4: date):
    """As quatro versoes com as datas do `prd`, e a versao 4 na data dada.

    ⚠️ Linhas de teste: os numeros das versoes 3 e 4 sao os das 1 e 2 (a
    conferencia de que a migracao os tem esta nos casos acima); o que estes
    casos provam e a REGRA da vigencia com as datas do conserto. A versao 2
    vai para 12/10, a data que a `0030` lhe deu no `prd` (`VIGENCIA_V2`, das
    linhas de teste, e outra de proposito).
    """
    linhas = []
    for linha in LINHAS_DAS_REGUAS:
        if linha["nu_versao_regua"] == 1:
            linhas.append(linha)
        else:
            linhas.append({**linha, "dt_inicio_vigencia": date(2026, 10, 12)})
    for linha in LINHAS_DAS_REGUAS:
        if linha["nu_versao_regua"] == 1:
            linhas.append({**linha, "nu_versao_regua": 3,
                           "dt_inicio_vigencia": date(2026, 10, 13)})
        else:
            linhas.append({**linha, "nu_versao_regua": 4,
                           "dt_inicio_vigencia": vigencia_v4})
    return reguas_das_linhas(linhas)


@pytest.mark.parametrize(
    ("dt_dia", "versao"),
    [
        (date(2026, 10, 11), 1),
        # O dia que a `0030` deu a versao 2, sem querer, no `prd`.
        (date(2026, 10, 12), 2),
        # Do deploy a liberacao: a conta que a 1.3.0 faz no aparelho.
        (date(2026, 10, 13), 3),
        (date(2026, 10, 19), 3),
        # Liberada a 1.3.1 em 19/10, a regua nova vale do dia 20.
        (date(2026, 10, 20), 4),
        (date(2027, 1, 1), 4),
    ],
)
def test_a_linha_do_tempo_do_conserto(dt_dia, versao):
    """O `prd`: a versao 2 so em 12/10; a 3 do deploy ate a liberacao; e a 4
    dali em diante."""
    reguas = _versoes_com(vigencia_v4=date(2026, 10, 20))
    assert regua_vigente(reguas, dt_dia).nu_versao == versao


def test_SEM_o_piso_a_versao_4_nunca_valeria():
    """O defeito que o piso de 14/10 impede, escrito como caso: com a versao 4
    em 12/10 (a `0032` aplicada em 11/10, sem o `GREATEST`), a versao 3 vence
    de 13/10 em diante PARA SEMPRE - sem erro nenhum."""
    reguas = _versoes_com(vigencia_v4=date(2026, 10, 12))
    assert regua_vigente(reguas, date(2027, 1, 1)).nu_versao == 3


def test_a_cadeia_das_revisoes_e_0030_0031_0032():
    """A `0031` vem depois da `0030`, e a `0032` depois da `0031` - e e isso que
    permite aplicar a `0031` PELO NOME no `prd`, deixando a `0032` para a
    liberacao. ⚠️ E o nome cabe na `alembic_version.version_num`, que e
    `VARCHAR(32)`: um nome maior so falharia na hora de aplicar."""
    for caminho, anterior in [
        (MIGRACAO_0031, "0030_regua_da_nota"),
        (MIGRACAO_0032, "0031_regua_antiga_ate_liberar"),
    ]:
        texto = caminho.read_text(encoding="utf-8")
        assert f'revision: str = "{caminho.stem}"' in texto
        assert f'down_revision: Union[str, None] = "{anterior}"' in texto
        assert len(caminho.stem) <= 32, caminho.stem


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

"""Testes do reparo dinâmico de V/D/E (T170) e backfill de XP (T171 — Opção A).

O que esta suíte trava:
  1. Cadeado de paridade entre:
       - `BONUS_DAS_CONQUISTAS` (servidor, 91 conquistas);
       - `scripts/aplicar_backfill_progressao_t171.py` (`SQL_REPARO_VDE_T170` e
         `SQL_BACKFILL_XP_T171`);
       - o arquivo `.sql` entregue ao dono em
         `arena-sagaz-frontend/specs/010-jogo-quatro-em-linha/backfill-progressao-t170-t171.sql`.
  2. Execução do SQL real num SQLite em memória (sem mocks) reproduzindo os
     exatos perfis das **9 contas abaixo de zero do `prd`** medidas em 30/10/2026:
       - `c1d497ac`: `2.720 -> 4.250` (`+1.530`, `dif = 0`) + reparo V/D/E
         `152: 56/90/8 -> 56/90/6`;
       - `2985d614`: `155 -> 545` (`+390`, `dif = 0`);
       - `3fc7be86` (Conta A — dono): `5.660 -> 5.960` (`+300`, `dif = -45`,
         sem inflar os `-45` para `6.005` e sem somar conquista `desafio_%`);
       - `59094f79`: `3.464 -> 3.704` (`+240`, `dif = 0`);
       - `1ca98aad`: `2.180 -> 2.400` (`+220`, `dif = 0`) + reparo V/D/E
         `39: 16/14/10 -> 16/14/9`;
       - `bdc1ee66`: `11.470 -> 11.620` (`+150`, `dif = -50`, parando antes do
         lote anterior `sequencia_30 = 400`);
       - `51f1d858`: `6.385 -> 6.555` (`+170`, `dif = 0`);
       - `4fa4623c`: `37.720 -> 37.870` (`+150`, `dif = 0`);
       - `462775e9`: `2.522 -> 2.661` (`+139`, `dif = 0`, conta com merge em
         `progressao.tb003_lote_migracao` onde `+151` pré-log abateu parte das
         4 conquistas finais de `290`).
  3. Controles (contas que não podem mudar):
       - conta com `diferenca = 0`;
       - conta com `diferenca = +86` (merge positivo sem perda);
       - conta com `diferenca < 0` mas cuja única conquista recente é
         `desafio_%` (já paga pelo servidor na resolução);
       - conta com `diferenca < 0`, sem merge, e último lote maior que `falta`
         (resíduo histórico puro);
       - conta com `diferenca < 0` e merge em `tb003_lote_migracao`, mas zero
         conquistas não-desafio;
       - conta com `V + D + E <= nu_partidas` cujos contadores diferem do log;
       - partidas `ic_pontua = false` ou `co_status != 'concluida'` e linhas de
         `vw004_xp_desafio` fora de `('consolo', 'ajuste')`.
  4. Idempotência natural (2ª execução atualiza 0 linhas em V/D/E e em XP) e
     travas transacionais de `executar_backfill_na_conexao` e
     `validar_ambiente_alvo`.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from api.sincronizacao.bonus_das_conquistas import BONUS_DAS_CONQUISTAS
from scripts.aplicar_backfill_progressao_t171 import (
    MARCADOR_FIM_VDE,
    MARCADOR_FIM_XP,
    MARCADOR_INICIO_VDE,
    MARCADOR_INICIO_XP,
    SQL_BACKFILL_XP_T171,
    SQL_DIAGNOSTICO_FORMULA,
    SQL_REPARO_VDE_T170,
    clausula_values_bonus,
    executar_backfill_na_conexao,
    extrair_bloco_sql,
    validar_ambiente_alvo,
)

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
ARQUIVO_SQL_SPEC = (
    RAIZ_BACKEND.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "010-jogo-quatro-em-linha"
    / "backfill-progressao-t170-t171.sql"
)

DDL_SCHEMAS_SQLITE = """
ATTACH DATABASE ':memory:' AS progressao;
ATTACH DATABASE ':memory:' AS partida;
ATTACH DATABASE ':memory:' AS desafio_dia;

CREATE TABLE progressao.tb001_progressao_usuario (
    id_usuario TEXT PRIMARY KEY,
    nu_xp_total INTEGER NOT NULL,
    nu_partidas INTEGER NOT NULL,
    nu_vitorias INTEGER NOT NULL,
    nu_derrotas INTEGER NOT NULL,
    nu_empates INTEGER NOT NULL,
    dh_atualizacao TEXT
);
CREATE TABLE progressao.tb002_conquista_usuario (
    id_usuario TEXT NOT NULL,
    co_conquista TEXT NOT NULL,
    dh_desbloqueio TEXT NOT NULL,
    PRIMARY KEY (id_usuario, co_conquista)
);
CREATE TABLE progressao.tb003_lote_migracao (
    co_lote_migracao TEXT PRIMARY KEY,
    id_usuario TEXT NOT NULL,
    dh_aplicado TEXT
);
CREATE TABLE partida.tb001_partida (
    id_partida TEXT PRIMARY KEY,
    id_usuario TEXT NOT NULL,
    ic_pontua BOOLEAN NOT NULL,
    co_status TEXT NOT NULL,
    co_resultado TEXT
);
CREATE VIEW partida.vw001_partida AS
    SELECT id_partida, id_usuario, ic_pontua, co_status, co_resultado
      FROM partida.tb001_partida;
CREATE TABLE partida.tb003_xp_partida (
    id_partida TEXT NOT NULL,
    id_usuario TEXT NOT NULL,
    nu_xp INTEGER NOT NULL
);
CREATE TABLE desafio_dia.vw003_resolucao (
    id_usuario TEXT NOT NULL,
    nu_xp INTEGER NOT NULL
);
CREATE TABLE desafio_dia.vw004_xp_desafio (
    id_usuario TEXT NOT NULL,
    vr_xp INTEGER NOT NULL,
    co_tipo_xp TEXT NOT NULL
);
"""


def criar_sqlite_memoria() -> sqlite3.Connection:
    """Abre um SQLite em memória com os três schemas necessários anexados."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(DDL_SCHEMAS_SQLITE)
    return con


def _semear_partidas_log(
    con: sqlite3.Connection,
    *,
    id_usuario: str,
    vitorias: int,
    derrotas: int,
    empates: int,
    xp_total_partidas: int,
) -> None:
    """Semeia as partidas concluídas que pontuam e concentra `xp_total_partidas`."""
    indice = 0
    primeira_id: str | None = None
    for desfecho, qtd in (
        ("venceu_j1", vitorias),
        ("venceu_j2", derrotas),
        ("empate", empates),
    ):
        for _ in range(qtd):
            indice += 1
            pid = f"{id_usuario}-p{indice}"
            if primeira_id is None:
                primeira_id = pid
            con.execute(
                "INSERT INTO partida.tb001_partida VALUES (?, ?, 1, 'concluida', ?)",
                (pid, id_usuario, desfecho),
            )
    if xp_total_partidas > 0:
        if primeira_id is None:
            primeira_id = f"{id_usuario}-p-xp"
            con.execute(
                "INSERT INTO partida.tb001_partida VALUES (?, ?, 1, 'concluida', 'venceu_j1')",
                (primeira_id, id_usuario),
            )
        con.execute(
            "INSERT INTO partida.tb003_xp_partida VALUES (?, ?, ?)",
            (primeira_id, id_usuario, xp_total_partidas),
        )


def semear_cenario_completo_prd(con: sqlite3.Connection) -> None:
    """Semeia as 9 contas abaixo de zero do `prd` + 5 controles representativos."""
    # 1) c1d497ac: total=2720, partidas_xp=1170, bonus=3080 (1550 pagos + 1530 perdidos),
    #    152 partidas na linha quebrada 56/90/8 (no log real: 56/90/6).
    u1 = "c1d497ac-76d8-4273-a743-a1356de6b64a"
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES (?, 2720, 152, 56, 90, 8, '2026-10-21T15:30:00Z')",
        (u1,),
    )
    _semear_partidas_log(con, id_usuario=u1, vitorias=56, derrotas=90, empates=6, xp_total_partidas=1170)
    # Lote antigo já pago somando 1.550 (680 + 480 + 350 + 40 = 1550)
    for cod in ("nivel_80", "nivel_55", "vitorias_100", "primeira_vitoria"):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-09-19T04:40:59Z')",
            (u1, cod),
        )
    # 11 conquistas seguintes somando 1.530 exatos (400 + 300 + 250 + 200 + 140 + 100 + 80 + 60 = 1530 -> em 3 lotes cronológicos)
    for cod, dh in (
        ("damas_vitorias_50", "2026-09-19T05:19:58Z"),         # 400
        ("damas_derrotar_magno", "2026-09-22T10:00:00Z"),      # 300
        ("damas_segurou_magno", "2026-09-25T10:00:00Z"),       # 250
        ("damas_vitorias_10", "2026-10-01T10:00:00Z"),         # 200
        ("damas_derrotar_pita", "2026-10-10T10:00:00Z"),       # 140
        ("dias_10", "2026-10-15T10:00:00Z"),                   # 100
        ("damas_vitorias_1", "2026-10-20T10:00:00Z"),          # 80
        ("sequencia_3", "2026-10-21T15:27:23Z"),               # 60
    ):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, ?)",
            (u1, cod, dh),
        )

    # 2) 2985d614: total=155, partidas_xp=155, 1 partida, 6 conquistas somando 390 exatos.
    u2 = "2985d614-dc56-4519-ad65-a11012aad9b2"
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES (?, 155, 1, 1, 0, 0, '2026-09-26T13:31:10Z')",
        (u2,),
    )
    _semear_partidas_log(con, id_usuario=u2, vitorias=1, derrotas=0, empates=0, xp_total_partidas=155)
    # 40 + 80 + 80 + 140 + 50 = 390 (ou 6 conquistas reais: primeira_vitoria 40, damas_vitorias_1 80,
    # damas_derrotar_cacau 80, damas_primeira_dama 40, damas_captura_tripla 120, damas_derrotar_cacau_com_poder 30 = 390)
    for cod in (
        "primeira_vitoria",
        "damas_vitorias_1",
        "damas_derrotar_cacau",
        "damas_primeira_dama",
        "damas_captura_tripla",
        "damas_derrotar_cacau_com_poder",
    ):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-09-26T13:31:08Z')",
            (u2, cod),
        )

    # 3) 3fc7be86 (Conta A — dono): total=5660, partidas_xp=2830, desafio_xp=565,
    #    bonus_total=2610 (260 desafio + 2050 antigos pagos + 300 perdidos em 3 conquistas),
    #    dif_antes = -345 -> credita +300 -> 5960 (dif_depois = -45).
    #    Inclui conquista `desafio_resolvidos_10` recente para provar que `desafio_%` é ignorada no sufixo!
    u3 = "3fc7be86-c396-4167-ad30-8d7048521ad9"
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES (?, 5660, 157, 47, 97, 13, '2026-10-30T13:36:52Z')",
        (u3,),
    )
    _semear_partidas_log(con, id_usuario=u3, vitorias=47, derrotas=97, empates=12, xp_total_partidas=2830)
    con.execute("INSERT INTO desafio_dia.vw003_resolucao VALUES (?, 545)", (u3,))
    con.execute("INSERT INTO desafio_dia.vw004_xp_desafio VALUES (?, 20, 'consolo')", (u3,))
    # Linha `'resolucao'` em vw004_xp_desafio NÃO pode ser somada de novo!
    con.execute("INSERT INTO desafio_dia.vw004_xp_desafio VALUES (?, 545, 'resolucao')", (u3,))
    # Desafio conquistas = 260 (40 + 100 + 120)
    for cod, dh in (
        ("desafio_primeiro", "2026-10-05T12:00:00Z"),
        ("desafio_semana_completa", "2026-10-12T12:00:00Z"),
        ("desafio_resolvidos_10", "2026-10-29T12:00:00Z"),
    ):
        con.execute("INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, ?)", (u3, cod, dh))
    # Antigas pagas de jogos/conta = 2.050 (800 + 600 + 350 + 300 = 2050)
    for cod in ("vitorias_500", "dias_100", "damas_lenda", "damas_derrotar_magno"):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-09-03T18:00:00Z')",
            (u3, cod),
        )
    # As 3 conquistas não-desafio perdidas: 80 + 100 + 120 = 300
    for cod, dh in (
        ("damas_derrotar_tex_com_poder", "2026-09-21T20:00:00Z"),
        ("damas_segurou_magno_com_poder", "2026-10-21T20:00:00Z"),
        ("sequencia_7", "2026-10-30T13:32:44Z"),
    ):
        con.execute("INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, ?)", (u3, cod, dh))

    # 4) 59094f79: total=3464, partidas_xp=1754, bonus_total=1950 (1710 pagos + 240 perdidos: 40 + 200) -> +240.
    u4 = "59094f79-3a6f-4cbd-b5ba-b88fa3cce181"
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES (?, 3464, 235, 77, 124, 34, '2026-08-14T10:00:00Z')",
        (u4,),
    )
    _semear_partidas_log(con, id_usuario=u4, vitorias=77, derrotas=124, empates=34, xp_total_partidas=1754)
    # 1710 pagos = 680 + 480 + 350 + 200
    for cod in ("nivel_80", "nivel_55", "vitorias_100", "nivel_20"):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-08-05T10:00:00Z')",
            (u4, cod),
        )
    con.execute("INSERT INTO progressao.tb002_conquista_usuario VALUES (?, 'velha_derrotar_cacau', '2026-08-10T18:22:00Z')", (u4,))
    con.execute("INSERT INTO progressao.tb002_conquista_usuario VALUES (?, 'vitorias_50', '2026-08-10T18:23:00Z')", (u4,))

    # 5) 1ca98aad: total=2180, partidas_xp=1000, bonus_total=1400 (1180 pagos + 220 perdidos: 40 + 60 + 120),
    #    linha quebrada 39: 16/14/10 (log real: 16/14/9).
    u5 = "1ca98aad-afe0-4352-8594-79fd4459039c"
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES (?, 2180, 39, 16, 14, 10, '2026-09-20T13:15:00Z')",
        (u5,),
    )
    _semear_partidas_log(con, id_usuario=u5, vitorias=16, derrotas=14, empates=9, xp_total_partidas=1000)
    # 1180 pagos = 680 + 500
    for cod in ("nivel_80", "velha_derrotar_magno"):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-09-13T12:08:28Z')",
            (u5, cod),
        )
    for cod, dh in (
        ("damas_primeira_dama", "2026-09-13T14:00:00Z"),   # 40
        ("sequencia_3", "2026-09-16T10:00:00Z"),           # 60
        ("damas_captura_tripla", "2026-09-20T13:10:00Z"),  # 120
    ):
        con.execute("INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, ?)", (u5, cod, dh))

    # 6) bdc1ee66: total=11470, partidas_xp=5461, desafio_xp=39 (29+10),
    #    bonus_total=6170 (40 desafio + 5580 antigos + 400 sequencia_30 + 150 lote final),
    #    dif_antes = -200 -> credita +150 -> 11620 (dif_depois = -50).
    u6 = "bdc1ee66-7360-43fe-92fc-b22c941f88c8"
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES (?, 11470, 470, 265, 143, 62, '2026-10-15T10:00:00Z')",
        (u6,),
    )
    _semear_partidas_log(con, id_usuario=u6, vitorias=265, derrotas=143, empates=62, xp_total_partidas=5461)
    con.execute("INSERT INTO desafio_dia.vw003_resolucao VALUES (?, 29)", (u6,))
    con.execute("INSERT INTO desafio_dia.vw004_xp_desafio VALUES (?, 10, 'consolo')", (u6,))
    con.execute("INSERT INTO progressao.tb002_conquista_usuario VALUES (?, 'desafio_primeiro', '2026-10-08T10:00:00Z')", (u6,))
    # 5580 antigos = 800 + 700 + 700 + 680 + 600 + 500 + 480 + 400 + 400 + 320
    for cod in (
        "vitorias_500",
        "damas_vitorias_100",
        "quatro_vitorias_100",
        "nivel_80",
        "dias_100",
        "velha_derrotar_magno",
        "nivel_55",
        "damas_vitorias_50",
        "velha_lenda",
        "nivel_35",
    ):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-09-20T10:00:00Z')",
            (u6, cod),
        )
    # Penúltimo lote: sequencia_30 (400) em 10/10 — se entrasse daria 550 > 200!
    con.execute(
        "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, 'sequencia_30', '2026-10-10T10:00:00Z')",
        (u6,),
    )
    # Último lote em 12/10 02:33:05: 30 + 50 + 70 = 150
    for cod in (
        "pontinhos_derrotar_cacau_com_poder",
        "pontinhos_derrotar_pita_com_poder",
        "pontinhos_derrotar_tex_com_poder",
    ):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-10-12T02:33:05Z')",
            (u6, cod),
        )

    # 7) 51f1d858: total=6385, partidas_xp=2943, desafio_xp=102, bonus_total=3510 (3340 pagos + 170 perdidos: 50+40+80) -> +170.
    u7 = "51f1d858-3d06-49ee-b41b-97b3daa7d09d"
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES (?, 6385, 568, 84, 361, 123, '2026-10-26T22:36:00Z')",
        (u7,),
    )
    _semear_partidas_log(con, id_usuario=u7, vitorias=84, derrotas=361, empates=123, xp_total_partidas=2943)
    con.execute("INSERT INTO desafio_dia.vw003_resolucao VALUES (?, 102)", (u7,))
    # 3340 pagos = 800 + 700 + 680 + 600 + 480 + 80
    for cod in ("vitorias_500", "damas_vitorias_100", "nivel_80", "dias_100", "nivel_55", "nivel_5"):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-10-01T10:00:00Z')",
            (u7, cod),
        )
    for cod in ("damas_derrotar_pita_com_poder", "damas_primeira_dama", "damas_vitorias_1"):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-10-26T22:35:50Z')",
            (u7, cod),
        )

    # 8) 4fa4623c: total=37720, partidas_xp=28025, desafio_xp=535, bonus_total=9310 (9160 pagos + 150 perdidos) -> +150.
    u8 = "4fa4623c-b32c-48e3-9276-ac80a9954d53"
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES (?, 37720, 2981, 1142, 1477, 362, '2026-10-29T10:00:00Z')",
        (u8,),
    )
    _semear_partidas_log(con, id_usuario=u8, vitorias=1, derrotas=0, empates=0, xp_total_partidas=28025)
    con.execute("INSERT INTO desafio_dia.vw003_resolucao VALUES (?, 535)", (u8,))
    # Semeia um conjunto de conquistas antigas somando 9.160:
    # Vamos somar códigos reais do catálogo até 9.160:
    # 800+700+700+680+600+500+480+400+400+400+400+350+350+350+350+350+320+300+300+250+180 = 9160!
    # Conferindo: 800+1400=2200; +680=2880; +600=3480; +500=3980; +480=4460; +1600(4x400)=6060;
    # +1750(5x350)=7810; +320=8130; +600(2x300)=8730; +250=8980; +180=9160! Exato!
    antigas_u8 = (
        "vitorias_500",          # 800
        "damas_vitorias_100",    # 700
        "quatro_vitorias_100",   # 700
        "nivel_80",              # 680
        "dias_100",              # 600
        "velha_derrotar_magno",  # 500
        "nivel_55",              # 480
        "sequencia_30",          # 400
        "velha_lenda",           # 400
        "damas_vitorias_50",     # 400
        "desafio_mes_completo",  # 400
        "vitorias_100",          # 350
        "pontinhos_vitorias_100",# 350
        "damas_lenda",           # 350
        "desafio_resolvidos_100",# 350
        "quatro_lenda",          # 350
        "nivel_35",              # 320
        "pontinhos_lenda",       # 300
        "velha_partida_perfeita",# 300
        "velha_segurou_magno",   # 250
        "pontinhos_derrotar_tex",# 180
    )
    assert sum(BONUS_DAS_CONQUISTAS[c] for c in antigas_u8) == 9160
    for cod in antigas_u8:
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-09-15T10:00:00Z')",
            (u8, cod),
        )
    for cod in (
        "pontinhos_derrotar_cacau_com_poder",
        "pontinhos_derrotar_pita_com_poder",
        "pontinhos_derrotar_tex_com_poder",
    ):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-10-11T02:48:15Z')",
            (u8, cod),
        )

    # 9) 462775e9: total=2522, partidas_xp=1611, bonus_total=1050 (dif = -139),
    #    lote de merge em tb003_lote_migracao, e conquistas finais em 21/08 23:39:49 (70)
    #    e 23:40:00 (220 = 100 + 120) -> sufixo = 0 (220 > 139), fallback merge -> +139 (2661, dif=0).
    u9 = "462775e9-f0b6-4e7c-a05b-cb0e88f19af5"
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES (?, 2522, 170, 46, 110, 14, '2026-08-21T23:40:02Z')",
        (u9,),
    )
    _semear_partidas_log(con, id_usuario=u9, vitorias=46, derrotas=110, empates=14, xp_total_partidas=1611)
    con.execute(
        "INSERT INTO progressao.tb003_lote_migracao VALUES ('lote-u9', ?, '2026-07-22T15:00:00Z')",
        (u9,),
    )
    # 760 antigos (480 + 200 + 80 = 760) + 70 + 220 = 1050
    for cod in ("nivel_55", "nivel_20", "nivel_5"):
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-08-01T10:00:00Z')",
            (u9, cod),
        )
    for cod in ("primeira_vitoria", "velha_vitorias_1"):  # 40 + 30 = 70
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-08-21T23:39:49Z')",
            (u9, cod),
        )
    for cod in ("vitorias_10", "nivel_10"):  # 100 + 120 = 220
        con.execute(
            "INSERT INTO progressao.tb002_conquista_usuario VALUES (?, ?, '2026-08-21T23:40:00Z')",
            (u9, cod),
        )

    # --- CONTROLES ---
    # C1) Conta com diferenca = 0 e partida pvp_local (ic_pontua=0) + abandonada: não muda!
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES ('ctrl-zero', 300, 2, 2, 0, 0, '2026-10-30T10:00:00Z')"
    )
    _semear_partidas_log(con, id_usuario="ctrl-zero", vitorias=2, derrotas=0, empates=0, xp_total_partidas=260)
    con.execute("INSERT INTO progressao.tb002_conquista_usuario VALUES ('ctrl-zero', 'primeira_vitoria', '2026-10-30T10:00:00Z')")
    # Partida que NÃO pontua (pvp_local) com XP espúrio e resultado: tem de ser ignorada!
    con.execute("INSERT INTO partida.tb001_partida VALUES ('ctrl-pvp', 'ctrl-zero', 0, 'concluida', 'venceu_j1')")
    con.execute("INSERT INTO partida.tb003_xp_partida VALUES ('ctrl-pvp', 'ctrl-zero', 999)")

    # C2) Conta com diferenca = +86 (merge positivo): não muda!
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES ('ctrl-positivo', 586, 1, 1, 0, 0, '2026-10-30T10:00:00Z')"
    )
    _semear_partidas_log(con, id_usuario="ctrl-positivo", vitorias=1, derrotas=0, empates=0, xp_total_partidas=500)

    # C3) Conta com diferenca = -40 cuja única conquista é `desafio_primeiro` (40): não muda!
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES ('ctrl-so-desafio', 100, 1, 1, 0, 0, '2026-10-30T10:00:00Z')"
    )
    _semear_partidas_log(con, id_usuario="ctrl-so-desafio", vitorias=1, derrotas=0, empates=0, xp_total_partidas=100)
    con.execute(
        "INSERT INTO progressao.tb002_conquista_usuario VALUES ('ctrl-so-desafio', 'desafio_primeiro', '2026-10-30T10:00:00Z')"
    )

    # C4) Conta com diferenca = -50, SEM merge, e último lote = 120 > 50 (resíduo puro): não muda!
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES ('ctrl-residuo-sem-merge', 1070, 1, 1, 0, 0, '2026-10-30T10:00:00Z')"
    )
    _semear_partidas_log(con, id_usuario="ctrl-residuo-sem-merge", vitorias=1, derrotas=0, empates=0, xp_total_partidas=1000)
    con.execute(
        "INSERT INTO progressao.tb002_conquista_usuario VALUES ('ctrl-residuo-sem-merge', 'sequencia_7', '2026-10-30T10:00:00Z')"
    )

    # C5) Conta com diferenca = -80, COM merge em tb003_lote_migracao, mas ZERO conquistas não-desafio,
    #     e V + D + E <= partidas (10 partidas, 4/3/2 = 9, mas no log só 1/0/0): nem XP nem V/D/E mudam!
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES ('ctrl-merge-sem-conquista', 920, 10, 4, 3, 2, '2026-10-30T10:00:00Z')"
    )
    _semear_partidas_log(con, id_usuario="ctrl-merge-sem-conquista", vitorias=1, derrotas=0, empates=0, xp_total_partidas=1000)
    con.execute(
        "INSERT INTO progressao.tb003_lote_migracao VALUES ('lote-ctrl5', 'ctrl-merge-sem-conquista', '2026-08-01T10:00:00Z')"
    )


def test_cadeado_arquivo_sql_da_spec_bate_com_script_e_91_conquistas() -> None:
    """O `.sql` entregue na spec 010 tem os mesmos 2 UPDATEs e as mesmas 91 conquistas do servidor."""
    assert len(BONUS_DAS_CONQUISTAS) == 91
    assert ARQUIVO_SQL_SPEC.exists(), f"Arquivo SQL não encontrado: {ARQUIVO_SQL_SPEC}"
    texto = ARQUIVO_SQL_SPEC.read_text(encoding="utf-8")

    sql_vde_spec = extrair_bloco_sql(texto, MARCADOR_INICIO_VDE, MARCADOR_FIM_VDE)
    sql_xp_spec = extrair_bloco_sql(texto, MARCADOR_INICIO_XP, MARCADOR_FIM_XP)

    assert sql_vde_spec.strip() == SQL_REPARO_VDE_T170.strip()

    # Confere todos os 91 pares ('codigo', bonus) extraídos da CTE `bonus` do `.sql`.
    pares_no_sql = {
        m.group(1): int(m.group(2))
        for m in re.finditer(r"\('([a-z0-9_]+)',\s*(\d+)\)", sql_xp_spec)
    }
    assert pares_no_sql == BONUS_DAS_CONQUISTAS

    # Normaliza espaços em branco para confirmar que a lógica SQL inteira é a mesma.
    normalizar = lambda s: re.sub(r"\s+", " ", s).strip()
    assert normalizar(sql_xp_spec) == normalizar(SQL_BACKFILL_XP_T171)


def test_backfill_9_contas_reais_do_prd_controles_e_idempotencia() -> None:
    """Roda os dois UPDATEs reais em SQLite sobre as 9 contas do `prd` + 5 controles."""
    con = criar_sqlite_memoria()
    semear_cenario_completo_prd(con)

    # 1ª execução do reparo V/D/E: repara somente as 2 linhas inconsistentes (`c1d497ac` e `1ca98aad`).
    reparadas = {
        row["id_usuario"]: (row["nu_partidas"], row["nu_vitorias"], row["nu_derrotas"], row["nu_empates"])
        for row in con.execute(SQL_REPARO_VDE_T170).fetchall()
    }
    assert reparadas == {
        "c1d497ac-76d8-4273-a743-a1356de6b64a": (152, 56, 90, 6),
        "1ca98aad-afe0-4352-8594-79fd4459039c": (39, 16, 14, 9),
    }

    # Controle V/D/E consistente divergente do log permanece intocado (10: 4/3/2).
    ctrl5_vde = tuple(
        con.execute(
            "SELECT nu_partidas, nu_vitorias, nu_derrotas, nu_empates "
            "FROM progressao.tb001_progressao_usuario WHERE id_usuario = 'ctrl-merge-sem-conquista'"
        ).fetchone()
    )
    assert ctrl5_vde == (10, 4, 3, 2)

    # 1ª execução do backfill de XP: credita exatamente as 9 contas com os valores aprovados.
    creditadas = {
        row["id_usuario"]: row["nu_xp_total"]
        for row in con.execute(SQL_BACKFILL_XP_T171).fetchall()
    }
    assert creditadas == {
        "c1d497ac-76d8-4273-a743-a1356de6b64a": 4250,   # 2720 + 1530
        "2985d614-dc56-4519-ad65-a11012aad9b2": 545,    # 155 + 390
        "3fc7be86-c396-4167-ad30-8d7048521ad9": 5960,   # 5660 + 300 (Conta A cravada!)
        "59094f79-3a6f-4cbd-b5ba-b88fa3cce181": 3704,   # 3464 + 240
        "1ca98aad-afe0-4352-8594-79fd4459039c": 2400,   # 2180 + 220
        "bdc1ee66-7360-43fe-92fc-b22c941f88c8": 11620,  # 11470 + 150
        "51f1d858-3d06-49ee-b41b-97b3daa7d09d": 6555,   # 6385 + 170
        "4fa4623c-b32c-48e3-9276-ac80a9954d53": 37870,  # 37720 + 150
        "462775e9-f0b6-4e7c-a05b-cb0e88f19af5": 2661,   # 2522 + 139
    }

    # Todos os 5 controles permanecem com o XP exato de antes.
    xps_controles = {
        row["id_usuario"]: row["nu_xp_total"]
        for row in con.execute(
            "SELECT id_usuario, nu_xp_total FROM progressao.tb001_progressao_usuario "
            "WHERE id_usuario LIKE 'ctrl-%'"
        ).fetchall()
    }
    assert xps_controles == {
        "ctrl-zero": 300,
        "ctrl-positivo": 586,
        "ctrl-so-desafio": 100,
        "ctrl-residuo-sem-merge": 1070,
        "ctrl-merge-sem-conquista": 920,
    }

    # 2ª execução imediata: idempotência total (0 linhas em ambos os UPDATEs).
    assert con.execute(SQL_REPARO_VDE_T170).fetchall() == []
    assert con.execute(SQL_BACKFILL_XP_T171).fetchall() == []

    # Fórmula da §2 após o crédito: as 7 contas sem resíduo dão diferenca = 0,
    # Conta A dá -45 e bdc1ee66 dá -50.
    diag = {
        row["id_usuario"]: row["diferenca"]
        for row in con.execute(SQL_DIAGNOSTICO_FORMULA).fetchall()
    }
    assert diag["c1d497ac-76d8-4273-a743-a1356de6b64a"] == 0
    assert diag["2985d614-dc56-4519-ad65-a11012aad9b2"] == 0
    assert diag["3fc7be86-c396-4167-ad30-8d7048521ad9"] == -45
    assert diag["59094f79-3a6f-4cbd-b5ba-b88fa3cce181"] == 0
    assert diag["1ca98aad-afe0-4352-8594-79fd4459039c"] == 0
    assert diag["bdc1ee66-7360-43fe-92fc-b22c941f88c8"] == -50
    assert diag["51f1d858-3d06-49ee-b41b-97b3daa7d09d"] == 0
    assert diag["4fa4623c-b32c-48e3-9276-ac80a9954d53"] == 0
    assert diag["462775e9-f0b6-4e7c-a05b-cb0e88f19af5"] == 0


def test_reparo_vde_ignora_partidas_em_andamento_abandonadas_ou_que_nao_pontuam() -> None:
    """No reparo V/D/E só contam partidas de `vw001_partida` com `ic_pontua` e `co_status = 'concluida'`."""
    con = criar_sqlite_memoria()
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES ('u-filtros', 100, 2, 2, 1, 0, '2026-10-30')"
    )
    # 2 válidas (1 vitória, 1 empate) + 3 que devem ser ignoradas pelos filtros:
    con.execute("INSERT INTO partida.tb001_partida VALUES ('p-ok-1', 'u-filtros', 1, 'concluida', 'venceu_j1')")
    con.execute("INSERT INTO partida.tb001_partida VALUES ('p-ok-2', 'u-filtros', 1, 'concluida', 'empate')")
    con.execute("INSERT INTO partida.tb001_partida VALUES ('p-pvp', 'u-filtros', 0, 'concluida', 'venceu_j1')")
    con.execute("INSERT INTO partida.tb001_partida VALUES ('p-aberta', 'u-filtros', 1, 'em_andamento', 'venceu_j1')")
    con.execute("INSERT INTO partida.tb001_partida VALUES ('p-aband', 'u-filtros', 1, 'abandonada', 'venceu_j2')")

    rows = con.execute(SQL_REPARO_VDE_T170).fetchall()
    assert len(rows) == 1
    assert tuple(rows[0]) == ("u-filtros", 2, 1, 0, 1)


def test_reparo_vde_nao_aplica_se_soma_do_log_exceder_nu_partidas() -> None:
    """A guarda `(r.vit + r.der + r.emp) <= nu_partidas` impede gravar soma ainda inconsistente."""
    con = criar_sqlite_memoria()
    con.execute(
        "INSERT INTO progressao.tb001_progressao_usuario VALUES ('u-anomalo', 100, 1, 1, 1, 0, '2026-10-30')"
    )
    con.execute("INSERT INTO partida.tb001_partida VALUES ('p1', 'u-anomalo', 1, 'concluida', 'venceu_j1')")
    con.execute("INSERT INTO partida.tb001_partida VALUES ('p2', 'u-anomalo', 1, 'concluida', 'venceu_j2')")

    assert con.execute(SQL_REPARO_VDE_T170).fetchall() == []


@pytest.mark.asyncio
async def test_executor_async_valida_invariantes_e_aborta_se_sobrar_vde_inconsistente() -> None:
    """`executar_backfill_na_conexao` roda completo no cenário válido e falha se sobrar V+D+E > partidas."""
    motor = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(motor.sync_engine, "connect")
    def _anexar(dbapi_con, _record) -> None:
        cur = dbapi_con.cursor()
        for cmd in DDL_SCHEMAS_SQLITE.split(";"):
            trecho = cmd.strip()
            if trecho:
                cur.execute(trecho)
        cur.close()

    try:
        async with motor.connect() as conexao:
            trans = await conexao.begin()
            await conexao.execute(
                text(
                    "INSERT INTO progressao.tb001_progressao_usuario "
                    "VALUES ('u-ok', 100, 1, 1, 1, 0, '2026-10-30')"
                )
            )
            await conexao.execute(
                text(
                    "INSERT INTO partida.tb001_partida VALUES ('p1', 'u-ok', 1, 'concluida', 'venceu_j1')"
                )
            )
            await conexao.execute(
                text("INSERT INTO partida.tb003_xp_partida VALUES ('p1', 'u-ok', 100)")
            )
            await conexao.execute(
                text(
                    "INSERT INTO progressao.tb002_conquista_usuario "
                    "VALUES ('u-ok', 'primeira_vitoria', '2026-10-30T10:00:00Z')"
                )
            )

            rel = await executar_backfill_na_conexao(conexao)
            assert len(rel.vde_reparadas) == 1
            assert rel.vde_reparadas[0].vde_depois == (1, 0, 0)
            assert len(rel.xp_creditadas) == 1
            assert rel.xp_creditadas[0].credito == 40
            assert rel.xp_creditadas[0].xp_depois == 140
            assert rel.contas_abaixo_zero_depois == []

            # Agora injeta uma conta irreconciliável (1 partida na progressão, 2 no log) -> deve falhar!
            await conexao.execute(
                text(
                    "INSERT INTO progressao.tb001_progressao_usuario "
                    "VALUES ('u-ruim', 100, 1, 1, 1, 0, '2026-10-30')"
                )
            )
            await conexao.execute(
                text(
                    "INSERT INTO partida.tb001_partida VALUES ('pr1', 'u-ruim', 1, 'concluida', 'venceu_j1')"
                )
            )
            await conexao.execute(
                text(
                    "INSERT INTO partida.tb001_partida VALUES ('pr2', 'u-ruim', 1, 'concluida', 'venceu_j2')"
                )
            )
            with pytest.raises(RuntimeError, match="V \\+ D \\+ E > nu_partidas"):
                await executar_backfill_na_conexao(conexao)
            await trans.rollback()
    finally:
        await motor.dispose()


def test_travas_de_ambiente_e_validacao_de_values_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    """`validar_ambiente_alvo` barra URL vazia, banco desconhecido e troca DES/PRD."""
    with pytest.raises(ValueError, match="Ambiente inválido"):
        validar_ambiente_alvo("postgresql://u:s@host:5432/railway", "HOM")
    with pytest.raises(RuntimeError, match="vazia"):
        validar_ambiente_alvo("", "DES")

    monkeypatch.setattr(
        "scripts.aplicar_backfill_progressao_t171._nomear_ambiente",
        lambda _url: ("DES", "bate com DATABASE_URL_DES"),
    )
    assert validar_ambiente_alvo("postgresql://u:s@h:5432/db", "DES")[0] == "DES"
    with pytest.raises(RuntimeError, match="Trava de ambiente acionada"):
        validar_ambiente_alvo("postgresql://u:s@h:5432/db", "PRD")

    with pytest.raises(ValueError, match="vazia"):
        clausula_values_bonus({})
    with pytest.raises(ValueError, match="inválido"):
        clausula_values_bonus({"codigo'ruim": 10})
    with pytest.raises(ValueError, match="inválido"):
        clausula_values_bonus({"codigo_bom": -5})

r"""EXECUTOR TRANSACIONAL DO REPARO V/D/E (T170) E BACKFILL DE XP (T171).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT FAZ (COMANDO DO DONO NA VIRADA — T171 / T174)
═══════════════════════════════════════════════════════════════════════════

Executa, numa única transação atômica, as duas correções de dados de
`progressao.tb001_progressao_usuario` aprovadas pelo dono em 30/10/2026
(`arena-sagaz-frontend/docs/DECISOES-do-dono.md` §8zzzz10):

  1. **Reparo dinâmico de `nu_vitorias / nu_derrotas / nu_empates` (T170)**:
     recalcula V/D/E a partir de `partida.vw001_partida`
     (`WHERE ic_pontua AND co_status = 'concluida'`) exclusivamente nas contas
     onde `nu_vitorias + nu_derrotas + nu_empates > nu_partidas` (e somente se
     a soma do log couber em `nu_partidas`).

  2. **Backfill dinâmico do bônus de conquistas perdido (T171 — Opção A)**:
     para cada conta com `falta = -(nu_xp_total - partidas_xp - desafio_xp - bonus_total) > 0`,
     agrupa as conquistas não-desafio (`co_conquista NOT LIKE 'desafio_%'`) por
     instante `dh_desbloqueio`, acumula de trás para frente
     (`ORDER BY dh_desbloqueio DESC`) e soma o **maior sufixo cronológico
     `<= falta`**; quando esse sufixo é `0` e a conta possui lote de merge de
     convidado em `progressao.tb003_lote_migracao` com conquistas não-desafio
     (caso em que o saldo pré-log do convidado reduziu `falta` abaixo do último
     lote), soma `MIN(falta, total_bonus_nao_desafio)`.

═══════════════════════════════════════════════════════════════════════════
TRAVAS DE SEGURANÇA
═══════════════════════════════════════════════════════════════════════════

  * **Ambiente explícito obrigatório (`--ambiente PRD` ou `--ambiente DES`)**:
    compara `DATABASE_URL` do `.env` com `ferramentas/debug-bancos/ambientes.env`
    via `identificar_banco._nomear_ambiente`. Se não bater, aborta antes de
    abrir conexão.
  * **Modo ENSAIO por padrão (`ROLLBACK` garantido)**: sem `--aplicar`, executa
    todos os passos na transação, imprime o antes/depois completo, prova a
    idempotência na própria transação e desfaz tudo no `finally`.
  * **Invariantes verificadas antes de qualquer `COMMIT`**:
      (i)   0 linhas continuam com `V + D + E > nu_partidas`;
      (ii)  nenhuma conta perdeu `nu_xp_total` nem mudou `nu_partidas`;
      (iii) uma 2ª passada imediata dos dois `UPDATE`s atualiza 0 linhas.
    Se qualquer invariante falhar, a transação sofre `ROLLBACK` automático.
  * **Nunca imprime a senha nem a URL crua.**

COMO O DONO USA (na pasta `arena-sagaz-backend`):

    .venv\Scripts\python scripts\identificar_banco.py
    .venv\Scripts\python scripts\aplicar_backfill_progressao_t171.py --ambiente PRD
    .venv\Scripts\python scripts\aplicar_backfill_progressao_t171.py --ambiente PRD --aplicar
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
if str(RAIZ_BACKEND) not in sys.path:
    sys.path.insert(0, str(RAIZ_BACKEND))
if str(RAIZ_BACKEND / "scripts") not in sys.path:
    sys.path.insert(0, str(RAIZ_BACKEND / "scripts"))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from api.sincronizacao.bonus_das_conquistas import BONUS_DAS_CONQUISTAS  # noqa: E402
from scripts.identificar_banco import (  # noqa: E402
    _carregar_dotenv,
    _mascarar,
    _nomear_ambiente,
)

MARCADOR_INICIO_VDE = "-- >>> INICIO_UPDATE_REPARO_VDE_T170"
MARCADOR_FIM_VDE = "-- <<< FIM_UPDATE_REPARO_VDE_T170"
MARCADOR_INICIO_XP = "-- >>> INICIO_UPDATE_BACKFILL_XP_T171"
MARCADOR_FIM_XP = "-- <<< FIM_UPDATE_BACKFILL_XP_T171"

#: Consulta de conferência: linhas onde V + D + E ultrapassa nu_partidas.
SQL_VDE_INCONSISTENTES = """
SELECT id_usuario,
       nu_partidas,
       nu_vitorias,
       nu_derrotas,
       nu_empates
  FROM progressao.tb001_progressao_usuario
 WHERE (nu_vitorias + nu_derrotas + nu_empates) > nu_partidas
 ORDER BY id_usuario
"""

#: Passo 2 (T170): reparo dinâmico de V/D/E pela `partida.vw001_partida`,
#: escrito em ANSI SQL (compatível com Postgres e SQLite 3.35+).
SQL_REPARO_VDE_T170 = """
WITH do_log AS (
  SELECT id_usuario,
         CAST(COUNT(*) FILTER (WHERE co_resultado = 'venceu_j1') AS INTEGER) AS vit,
         CAST(COUNT(*) FILTER (WHERE co_resultado = 'venceu_j2') AS INTEGER) AS der,
         CAST(COUNT(*) FILTER (WHERE co_resultado = 'empate') AS INTEGER)    AS emp
    FROM partida.vw001_partida
   WHERE ic_pontua
     AND co_status = 'concluida'
   GROUP BY id_usuario
),
recalculado AS (
  SELECT p.id_usuario AS id_alvo,
         COALESCE(l.vit, 0) AS vit,
         COALESCE(l.der, 0) AS der,
         COALESCE(l.emp, 0) AS emp
    FROM progressao.tb001_progressao_usuario AS p
    LEFT JOIN do_log AS l ON l.id_usuario = p.id_usuario
   WHERE (p.nu_vitorias + p.nu_derrotas + p.nu_empates) > p.nu_partidas
)
UPDATE progressao.tb001_progressao_usuario
   SET nu_vitorias    = r.vit,
       nu_derrotas    = r.der,
       nu_empates     = r.emp,
       dh_atualizacao = CURRENT_TIMESTAMP
  FROM recalculado AS r
 WHERE tb001_progressao_usuario.id_usuario = r.id_alvo
   AND (tb001_progressao_usuario.nu_vitorias + tb001_progressao_usuario.nu_derrotas + tb001_progressao_usuario.nu_empates) > tb001_progressao_usuario.nu_partidas
   AND (r.vit + r.der + r.emp) <= tb001_progressao_usuario.nu_partidas
RETURNING id_usuario, nu_partidas, nu_vitorias, nu_derrotas, nu_empates
"""


def clausula_values_bonus(
    tabela: dict[str, int] | None = None,
) -> str:
    """Formata o dicionário de bônus de conquistas como tuplas SQL `VALUES`.

    Valida que todos os códigos são identificadores simples (`[a-z0-9_]+`) e os
    valores são inteiros não negativos, evitando qualquer interpolação insegura.
    """
    fonte = BONUS_DAS_CONQUISTAS if tabela is None else tabela
    if not fonte:
        raise ValueError("A tabela de bônus de conquistas não pode ser vazia.")
    pares: list[str] = []
    for codigo, valor in fonte.items():
        if not codigo or not all(c.isalnum() or c == "_" for c in codigo):
            raise ValueError(f"Código de conquista inválido para SQL: {codigo!r}")
        if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
            raise ValueError(f"Valor de bônus inválido para {codigo!r}: {valor!r}")
        pares.append(f"('{codigo}', {valor})")
    return ", ".join(pares)


def montar_sql_diagnostico_formula(
    tabela: dict[str, int] | None = None,
) -> str:
    """Monta a consulta de diagnóstico da fórmula da §2 (`RETOMADA-progressao-1.4.0.md`)."""
    valores = clausula_values_bonus(tabela)
    return f"""
WITH bonus(co_conquista, nu_bonus) AS (
  VALUES {valores}
),
xp_partidas AS (
  SELECT x.id_usuario, CAST(SUM(x.nu_xp) AS INTEGER) AS xp
    FROM partida.tb003_xp_partida AS x
    JOIN partida.tb001_partida AS p ON p.id_partida = x.id_partida
   WHERE p.ic_pontua
   GROUP BY x.id_usuario
),
xp_desafio AS (
  SELECT u AS id_usuario, CAST(SUM(v) AS INTEGER) AS xp
    FROM (
      SELECT id_usuario AS u, nu_xp AS v FROM desafio_dia.vw003_resolucao
      UNION ALL
      SELECT id_usuario AS u, vr_xp AS v FROM desafio_dia.vw004_xp_desafio WHERE co_tipo_xp IN ('consolo', 'ajuste')
    ) AS t
   GROUP BY u
),
bonus_conta AS (
  SELECT c.id_usuario, CAST(SUM(COALESCE(b.nu_bonus, 0)) AS INTEGER) AS bonus
    FROM progressao.tb002_conquista_usuario AS c
    LEFT JOIN bonus AS b ON b.co_conquista = c.co_conquista
   GROUP BY c.id_usuario
)
SELECT CAST(g.id_usuario AS TEXT) AS id_usuario,
       g.nu_xp_total,
       g.nu_partidas,
       g.nu_vitorias,
       g.nu_derrotas,
       g.nu_empates,
       COALESCE(xp.xp, 0) AS partidas_xp,
       COALESCE(d.xp, 0) AS desafio_xp,
       COALESCE(bc.bonus, 0) AS bonus_total,
       g.nu_xp_total - COALESCE(xp.xp, 0) - COALESCE(d.xp, 0) - COALESCE(bc.bonus, 0) AS diferenca
  FROM progressao.tb001_progressao_usuario AS g
  LEFT JOIN xp_partidas AS xp ON xp.id_usuario = g.id_usuario
  LEFT JOIN xp_desafio AS d ON d.id_usuario = g.id_usuario
  LEFT JOIN bonus_conta AS bc ON bc.id_usuario = g.id_usuario
 ORDER BY diferenca, g.id_usuario
"""


def montar_sql_backfill_xp_t171(
    tabela: dict[str, int] | None = None,
) -> str:
    """Monta o `UPDATE` dinâmico de backfill de XP da T171 (Opção A aprovada pelo dono).

    Escrito em ANSI SQL puro para rodar de modo idêntico no Postgres de produção
    e no SQLite em memória dos testes unitários e de mutação.
    """
    valores = clausula_values_bonus(tabela)
    return f"""
WITH bonus(co_conquista, nu_bonus) AS (
  VALUES {valores}
),
xp_partidas AS (
  SELECT x.id_usuario, CAST(SUM(x.nu_xp) AS INTEGER) AS xp
    FROM partida.tb003_xp_partida AS x
    JOIN partida.tb001_partida AS p ON p.id_partida = x.id_partida
   WHERE p.ic_pontua
   GROUP BY x.id_usuario
),
xp_desafio AS (
  SELECT u AS id_usuario, CAST(SUM(v) AS INTEGER) AS xp
    FROM (
      SELECT id_usuario AS u, nu_xp AS v FROM desafio_dia.vw003_resolucao
      UNION ALL
      SELECT id_usuario AS u, vr_xp AS v FROM desafio_dia.vw004_xp_desafio WHERE co_tipo_xp IN ('consolo', 'ajuste')
    ) AS t
   GROUP BY u
),
bonus_conta AS (
  SELECT c.id_usuario, CAST(SUM(COALESCE(b.nu_bonus, 0)) AS INTEGER) AS bonus
    FROM progressao.tb002_conquista_usuario AS c
    LEFT JOIN bonus AS b ON b.co_conquista = c.co_conquista
   GROUP BY c.id_usuario
),
buraco AS (
  SELECT g.id_usuario,
         -(g.nu_xp_total - COALESCE(xp.xp, 0) - COALESCE(d.xp, 0) - COALESCE(bc.bonus, 0)) AS falta
    FROM progressao.tb001_progressao_usuario AS g
    LEFT JOIN xp_partidas AS xp ON xp.id_usuario = g.id_usuario
    LEFT JOIN xp_desafio AS d ON d.id_usuario = g.id_usuario
    LEFT JOIN bonus_conta AS bc ON bc.id_usuario = g.id_usuario
   WHERE (g.nu_xp_total - COALESCE(xp.xp, 0) - COALESCE(d.xp, 0) - COALESCE(bc.bonus, 0)) < 0
),
lotes_nao_desafio AS (
  SELECT c.id_usuario,
         c.dh_desbloqueio,
         CAST(SUM(COALESCE(b.nu_bonus, 0)) AS INTEGER) AS bonus_lote
    FROM progressao.tb002_conquista_usuario AS c
    JOIN buraco AS bu ON bu.id_usuario = c.id_usuario
    LEFT JOIN bonus AS b ON b.co_conquista = c.co_conquista
   WHERE c.co_conquista NOT LIKE 'desafio_%'
   GROUP BY c.id_usuario, c.dh_desbloqueio
),
sufixos AS (
  SELECT l.id_usuario,
         l.dh_desbloqueio,
         CAST(SUM(l.bonus_lote) OVER (
           PARTITION BY l.id_usuario
           ORDER BY l.dh_desbloqueio DESC
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
         ) AS INTEGER) AS soma_sufixo
    FROM lotes_nao_desafio AS l
),
melhor_sufixo AS (
  SELECT bu.id_usuario,
         bu.falta,
         COALESCE(MAX(s.soma_sufixo) FILTER (WHERE s.soma_sufixo <= bu.falta), 0) AS credito_sufixo,
         COALESCE(MAX(s.soma_sufixo), 0) AS total_bonus_nao_desafio,
         EXISTS (
           SELECT 1
             FROM progressao.tb003_lote_migracao AS m
            WHERE m.id_usuario = bu.id_usuario
         ) AS tem_merge
    FROM buraco AS bu
    LEFT JOIN sufixos AS s ON s.id_usuario = bu.id_usuario
   GROUP BY bu.id_usuario, bu.falta
),
calculo_credito AS (
  SELECT m.id_usuario AS id_alvo,
         m.falta,
         -- Se credito_sufixo = 0 e total_bonus_nao_desafio > 0, o último lote já é > falta,
         -- logo falta < total_bonus_nao_desafio é garantido matematicamente.
         CASE
           WHEN m.credito_sufixo > 0 THEN m.credito_sufixo
           WHEN m.tem_merge AND m.total_bonus_nao_desafio > 0 THEN m.falta
           ELSE 0
         END AS credito
    FROM melhor_sufixo AS m
)
UPDATE progressao.tb001_progressao_usuario
   SET nu_xp_total    = tb001_progressao_usuario.nu_xp_total + cc.credito,
       dh_atualizacao = CURRENT_TIMESTAMP
  FROM calculo_credito AS cc
 WHERE tb001_progressao_usuario.id_usuario = cc.id_alvo
   AND cc.credito > 0
RETURNING id_usuario, nu_xp_total
"""


SQL_DIAGNOSTICO_FORMULA = montar_sql_diagnostico_formula()
SQL_BACKFILL_XP_T171 = montar_sql_backfill_xp_t171()


def extrair_bloco_sql(
    texto_sql: str,
    marcador_inicio: str,
    marcador_fim: str,
) -> str:
    """Extrai um comando SQL delimitado por marcadores de comentário (sem `;` final)."""
    indice_ini = texto_sql.find(marcador_inicio)
    if indice_ini < 0:
        raise ValueError(f"Marcador inicial não encontrado: {marcador_inicio}")
    indice_fim = texto_sql.find(marcador_fim, indice_ini)
    if indice_fim < 0:
        raise ValueError(f"Marcador final não encontrado: {marcador_fim}")
    trecho = texto_sql[indice_ini + len(marcador_inicio) : indice_fim].strip()
    if trecho.endswith(";"):
        trecho = trecho[:-1].rstrip()
    return trecho


def normalizar_url_asyncpg(url: str) -> str:
    """Garante o prefixo `postgresql+asyncpg://` exigido pelo motor assíncrono."""
    texto = url.strip()
    if texto.startswith("postgresql://"):
        return texto.replace("postgresql://", "postgresql+asyncpg://", 1)
    if texto.startswith("postgres://"):
        return texto.replace("postgres://", "postgresql+asyncpg://", 1)
    return texto


def validar_ambiente_alvo(url: str, ambiente_esperado: str) -> tuple[str, str]:
    """Confere que `url` bate com o `ambiente_esperado` (`DES` ou `PRD`) no catálogo.

    Levanta `RuntimeError` se a URL não estiver definida, for desconhecida ou
    apontar para o outro banco.
    """
    alvo = ambiente_esperado.strip().upper()
    if alvo not in ("DES", "PRD"):
        raise ValueError(f"Ambiente inválido: {ambiente_esperado!r} (use DES ou PRD).")
    if not url or not url.strip():
        raise RuntimeError("DATABASE_URL está vazia.")
    detectado, explicacao = _nomear_ambiente(url)
    if detectado != alvo:
        raise RuntimeError(
            f"Trava de ambiente acionada: foi pedido --ambiente {alvo}, "
            f"mas DATABASE_URL aponta para {detectado} ({explicacao})."
        )
    return detectado, explicacao


@dataclass(frozen=True)
class MudancaVde:
    """Resumo de uma linha reparada pelo Passo 2 (T170)."""

    id_usuario: str
    nu_partidas: int
    vde_antes: tuple[int, int, int]
    vde_depois: tuple[int, int, int]


@dataclass(frozen=True)
class MudancaXp:
    """Resumo de uma linha creditada pelo Passo 3 (T171)."""

    id_usuario: str
    xp_antes: int
    credito: int
    xp_depois: int
    dif_antes: int
    dif_depois: int


@dataclass(frozen=True)
class RelatorioBackfill:
    """Fotografia completa antes/depois + prova de invariantes na transação."""

    total_contas: int
    vde_reparadas: list[MudancaVde]
    xp_creditadas: list[MudancaXp]
    contas_abaixo_zero_antes: int
    contas_abaixo_zero_depois: list[tuple[str, int, int]]


async def executar_backfill_na_conexao(
    conexao: AsyncConnection,
    *,
    sql_reparo_vde: str = SQL_REPARO_VDE_T170,
    sql_backfill_xp: str = SQL_BACKFILL_XP_T171,
    sql_diagnostico: str = SQL_DIAGNOSTICO_FORMULA,
) -> RelatorioBackfill:
    """Executa os dois `UPDATE`s e valida todas as invariantes na conexão aberta.

    Não faz `COMMIT` nem `ROLLBACK`: quem controla a transação é o chamador.
    Levanta `RuntimeError` se qualquer invariante pós-atualização falhar.
    """
    antes_rows = (await conexao.execute(text(sql_diagnostico))).mappings().all()
    antes_por_id: dict[str, dict[str, Any]] = {
        str(r["id_usuario"]): dict(r) for r in antes_rows
    }

    reparadas_raw = (await conexao.execute(text(sql_reparo_vde))).fetchall()
    creditadas_raw = (await conexao.execute(text(sql_backfill_xp))).fetchall()

    # Invariante (i): nenhuma linha pode restar com V + D + E > partidas.
    restantes_vde = (await conexao.execute(text(SQL_VDE_INCONSISTENTES))).fetchall()
    if restantes_vde:
        raise RuntimeError(
            f"Invariante violada: {len(restantes_vde)} conta(s) continuam com "
            "V + D + E > nu_partidas após o reparo."
        )

    # Invariante (iii): idempotência imediata na 2ª passada dentro da transação.
    reparo_2a = (await conexao.execute(text(sql_reparo_vde))).fetchall()
    credito_2a = (await conexao.execute(text(sql_backfill_xp))).fetchall()
    if reparo_2a or credito_2a:
        raise RuntimeError(
            "Invariante de idempotência violada na 2ª passada: "
            f"reparo_vde={len(reparo_2a)}, backfill_xp={len(credito_2a)}."
        )

    depois_rows = (await conexao.execute(text(sql_diagnostico))).mappings().all()
    depois_por_id: dict[str, dict[str, Any]] = {
        str(r["id_usuario"]): dict(r) for r in depois_rows
    }

    # Invariante (ii): mesmo conjunto de contas, sem regressão de XP e sem mexer em nu_partidas.
    if set(antes_por_id) != set(depois_por_id):
        raise RuntimeError("Invariante violada: conjunto de contas mudou.")
    for uid, antes in antes_por_id.items():
        depois = depois_por_id[uid]
        if int(depois["nu_xp_total"]) < int(antes["nu_xp_total"]):
            raise RuntimeError(
                f"Invariante violada: conta {uid} perdeu XP "
                f"({antes['nu_xp_total']} -> {depois['nu_xp_total']})."
            )
        if int(depois["nu_partidas"]) != int(antes["nu_partidas"]):
            raise RuntimeError(
                f"Invariante violada: nu_partidas mudou na conta {uid} "
                f"({antes['nu_partidas']} -> {depois['nu_partidas']})."
            )

    vde_reparadas: list[MudancaVde] = []
    for row in reparadas_raw:
        uid = str(row[0])
        a = antes_por_id[uid]
        d = depois_por_id[uid]
        vde_reparadas.append(
            MudancaVde(
                id_usuario=uid,
                nu_partidas=int(d["nu_partidas"]),
                vde_antes=(
                    int(a["nu_vitorias"]),
                    int(a["nu_derrotas"]),
                    int(a["nu_empates"]),
                ),
                vde_depois=(
                    int(d["nu_vitorias"]),
                    int(d["nu_derrotas"]),
                    int(d["nu_empates"]),
                ),
            )
        )

    xp_creditadas: list[MudancaXp] = []
    for row in sorted(
        creditadas_raw,
        key=lambda r: int(antes_por_id[str(r[0])]["diferenca"]),
    ):
        uid = str(row[0])
        a = antes_por_id[uid]
        d = depois_por_id[uid]
        xp_antes = int(a["nu_xp_total"])
        xp_depois = int(d["nu_xp_total"])
        xp_creditadas.append(
            MudancaXp(
                id_usuario=uid,
                xp_antes=xp_antes,
                credito=xp_depois - xp_antes,
                xp_depois=xp_depois,
                dif_antes=int(a["diferenca"]),
                dif_depois=int(d["diferenca"]),
            )
        )

    abaixo_antes = sum(1 for r in antes_por_id.values() if int(r["diferenca"]) < 0)
    abaixo_depois = [
        (uid, int(r["nu_xp_total"]), int(r["diferenca"]))
        for uid, r in sorted(
            depois_por_id.items(), key=lambda par: (int(par[1]["diferenca"]), par[0])
        )
        if int(r["diferenca"]) < 0
    ]

    return RelatorioBackfill(
        total_contas=len(depois_por_id),
        vde_reparadas=vde_reparadas,
        xp_creditadas=xp_creditadas,
        contas_abaixo_zero_antes=abaixo_antes,
        contas_abaixo_zero_depois=abaixo_depois,
    )


def imprimir_relatorio(
    relatorio: RelatorioBackfill,
    *,
    ambiente: str,
    url_mascarada: str,
    aplicado: bool,
) -> None:
    """Imprime o resumo legível das alterações e do estado final da transação."""
    modo = "APLICAÇÃO REAL (COMMIT)" if aplicado else "ENSAIO (ROLLBACK — NADA GRAVADO)"
    print("=" * 76)
    print(f"  BACKFILL T170 + T171 — AMBIENTE: {ambiente} — {modo}")
    print("=" * 76)
    print(f"  Banco: {url_mascarada}")
    print(f"  Contas na tabela de progressão: {relatorio.total_contas}")
    print()
    print(f"  1) Reparo de V/D/E (T170): {len(relatorio.vde_reparadas)} conta(s)")
    for m in relatorio.vde_reparadas:
        va = "/".join(str(x) for x in m.vde_antes)
        vd = "/".join(str(x) for x in m.vde_depois)
        print(f"     - {m.id_usuario}  partidas={m.nu_partidas:<4}  {va}  ->  {vd}")
    print()
    print(
        f"  2) Backfill de XP de conquistas (T171): {len(relatorio.xp_creditadas)} conta(s) "
        f"(abaixo de zero antes: {relatorio.contas_abaixo_zero_antes})"
    )
    for c in relatorio.xp_creditadas:
        print(
            f"     - {c.id_usuario}  xp: {c.xp_antes:>6} + {c.credito:>5} = {c.xp_depois:>6}  "
            f"(dif: {c.dif_antes:>6} -> {c.dif_depois:>4})"
        )
    print()
    print(
        f"  3) Resíduos abaixo de zero preservados após o crédito: "
        f"{len(relatorio.contas_abaixo_zero_depois)} conta(s)"
    )
    for uid, xp_final, dif_final in relatorio.contas_abaixo_zero_depois:
        print(f"     - {uid}  nu_xp_total={xp_final}  diferenca={dif_final}")
    print()
    print("  4) Invariantes conferidas na transação:")
    print("     - 0 contas com V + D + E > nu_partidas")
    print("     - 0 contas com regressão de XP ou alteração de nu_partidas")
    print("     - 2ª passada imediata atualizou 0 linhas (idempotente)")
    print("=" * 76)


async def rodar_cli(*, url: str, ambiente: str, aplicar: bool) -> int:
    """Abre conexão, roda a transação com verificação e faz COMMIT ou ROLLBACK."""
    detectado, _ = validar_ambiente_alvo(url, ambiente)
    url_async = normalizar_url_asyncpg(url)
    motor = create_async_engine(url_async, echo=False, poolclass=NullPool)
    try:
        async with motor.connect() as conexao:
            transacao = await conexao.begin()
            try:
                relatorio = await executar_backfill_na_conexao(conexao)
                if aplicar:
                    await transacao.commit()
                else:
                    await transacao.rollback()
                imprimir_relatorio(
                    relatorio,
                    ambiente=detectado,
                    url_mascarada=_mascarar(url_async),
                    aplicado=aplicar,
                )
                return 0
            except Exception:
                if transacao.is_active:
                    await transacao.rollback()
                raise
    finally:
        await motor.dispose()


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Reparo dinâmico de V/D/E (T170) e backfill de XP (T171)."
    )
    parser.add_argument(
        "--ambiente",
        required=True,
        choices=["DES", "PRD", "des", "prd"],
        help="Ambiente esperado na DATABASE_URL do .env (DES ou PRD).",
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Faz COMMIT se todas as invariantes passarem (sem esta flag, roda em ENSAIO com ROLLBACK).",
    )
    args = parser.parse_args(argv)

    _carregar_dotenv()
    url = os.environ.get("DATABASE_URL", "")
    return asyncio.run(
        rodar_cli(url=url, ambiente=args.ambiente.upper(), aplicar=bool(args.aplicar))
    )


if __name__ == "__main__":
    raise SystemExit(main())

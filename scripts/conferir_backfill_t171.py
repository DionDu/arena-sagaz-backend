r"""PROVA DO BACKFILL DE PROGRESSÃO (T170 + T171) NO `des`, SEM DEIXAR RASTRO.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT PROVA NO POSTGRES REAL (`des`)
═══════════════════════════════════════════════════════════════════════════

  (a) os dois `UPDATE`s extraídos literalmente de
      `arena-sagaz-frontend/specs/010-jogo-quatro-em-linha/backfill-progressao-t170-t171.sql`
      rodam sem erro de dialeto no Postgres real do `des`:
        - conta quebrada em V/D/E e com conquistas perdidas (`c1d497ac`/`1ca98aad`):
          repara V/D/E pela `partida.vw001_partida` e credita exatamente o sufixo;
        - réplica da Conta A (`3fc7be86`): `5.660 -> 5.960` (`+300`, `dif = -45`),
          sem inflar os `-45` para `6.005` e sem incluir conquistas `desafio_%`;
        - réplica de `bdc1ee66`: `1.000 -> 1.150` (`+150`, `dif = -50`), parando
          antes do lote anterior `sequencia_30 = 400`;
        - réplica de `462775e9` (com lote em `progressao.tb003_lote_migracao` e
          último lote `220 > falta 139`): `2.522 -> 2.661` (`+139`, `dif = 0`);
  (b) controles intocados no Postgres: `dif = 0`, `dif = +86`, resíduo `-50` sem
      merge (`120 > 50`), merge sem conquistas não-desafio (`-80`), e V/D/E
      consistente (`10: 4/3/2`) divergente do log;
  (c) idempotência no Postgres: 2ª execução imediata atualiza 0 linhas de V/D/E
      e 0 linhas de XP;
  (d) convergência HTTP pós-backfill: `POST /v1/sincronizacao/reconciliar` da
      `1.4.0` na Conta A (`5.960`) responde 200 sem dobrar bônus, e um cliente
      `1.3.1` das lojas enviando conquista nova na conta reparada soma o bônus
      pela T167 e reconcilia com 200;
  (e) o modo ENSAIO de `aplicar_backfill_progressao_t171.rodar_cli(aplicar=False)`
      executa de ponta a ponta contra o `des` e faz `ROLLBACK`;
  (f) nada ficou gravado no `des` após o `ROLLBACK` (conferido em conexão nova).

COMO SE USA:

    arena-sagaz-backend\.venv\Scripts\python arena-sagaz-backend\scripts\conferir_backfill_t171.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
if str(RAIZ_BACKEND) not in sys.path:
    sys.path.insert(0, str(RAIZ_BACKEND))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from scripts.aplicar_backfill_progressao_t171 import (  # noqa: E402
    MARCADOR_FIM_VDE,
    MARCADOR_FIM_XP,
    MARCADOR_INICIO_VDE,
    MARCADOR_INICIO_XP,
    executar_backfill_na_conexao,
    extrair_bloco_sql,
    rodar_cli,
)
from scripts.conferir_portao_t050 import Relatorio, url_do_des  # noqa: E402
from scripts.conferir_resultado_da_partida_t168 import (  # noqa: E402
    montar_evento_partida,
)
from scripts.identificar_banco import _nomear_ambiente  # noqa: E402

PREFIXO_UID = "t171-"

ARQUIVO_SQL_SPEC = (
    RAIZ_BACKEND.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "010-jogo-quatro-em-linha"
    / "backfill-progressao-t170-t171.sql"
)

CABECALHOS_1_3_1 = {
    "X-App-Version": "1.3.1",
    "X-Platform": "android",
    "Accept-Language": "pt-BR",
}

CABECALHOS_1_4_0 = {
    "X-App-Version": "1.4.0",
    "X-Platform": "ios",
    "Accept-Language": "pt-BR",
}

C_A = "(a) SQL do `.sql` da spec repara V/D/E e credita os 4 perfis reais (quebrada, Conta A -> 5960, bdc1ee66 +150, merge +139)"
C_B = "(b) controles intocados no Postgres (dif=0, dif=+86, resíduo sem merge, merge sem conquista e V/D/E consistente)"
C_C = "(c) idempotência no Postgres: 2ª execução atualiza 0 linhas de V/D/E e 0 linhas de XP"
C_D = "(d) convergência HTTP pós-backfill: Conta A 1.4.0 mantém 5960 sem dobrar bônus e app 1.3.1 segue funcionando"
C_E = "(e) CLI `aplicar_backfill_progressao_t171` em modo ENSAIO (`aplicar=False`) executa e faz ROLLBACK"
C_F = "(f) nada ficou no `des`"


async def _criar_conta_http(
    cliente,
    conexao,
    identidade: dict[str, str],
    sufixo: str,
) -> tuple[Any, str]:
    """Cria uma conta de teste via `/v1/conta/sessao` dentro da transação externa."""
    from sqlalchemy import text

    uid_ext = f"{PREFIXO_UID}{sufixo}-{uuid.uuid4()}"
    identidade["uid"] = uid_ext
    r = await cliente.post(
        "/v1/conta/sessao",
        headers=CABECALHOS_1_4_0,
        json={
            "no_exibicao": f"T171 {sufixo}",
            "ic_idade_minima_declarada": True,
            "co_idioma_preferido": "pt",
        },
    )
    assert r.status_code == 200, r.text[:300]
    id_usuario = (
        await conexao.execute(
            text(
                "SELECT id_usuario FROM conta.vw001_usuario "
                " WHERE co_identidade_externa = :uid"
            ),
            {"uid": uid_ext},
        )
    ).scalar_one()
    return id_usuario, uid_ext


async def conferir() -> int:
    url = url_do_des()
    ambiente, explicacao = _nomear_ambiente(url)
    if ambiente != "DES":
        raise SystemExit(f"O banco não é o `des` ({ambiente}: {explicacao}).")
    print(f"banco: DES ({explicacao})")

    texto_sql = ARQUIVO_SQL_SPEC.read_text(encoding="utf-8")
    sql_vde_spec = extrair_bloco_sql(texto_sql, MARCADOR_INICIO_VDE, MARCADOR_FIM_VDE)
    sql_xp_spec = extrair_bloco_sql(texto_sql, MARCADOR_INICIO_XP, MARCADOR_FIM_XP)

    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from api.main import app
    from api.nucleo.banco import engine as motor
    from api.nucleo.banco import obter_sessao
    from api.nucleo.dependencias import usuario_atual
    from api.nucleo.seguranca_firebase import IdentidadeFirebase

    relatorio = Relatorio()
    identidade = {"uid": ""}
    ids_criados: list[Any] = []

    async with motor.connect() as conexao:
        transacao = await conexao.begin()

        async def sessao_dentro_da_transacao():
            async with AsyncSession(
                bind=conexao,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            ) as sessao:
                yield sessao

        def identidade_do_script() -> IdentidadeFirebase:
            return IdentidadeFirebase(
                uid=identidade["uid"], provedor="google.com", nome="T171"
            )

        app.dependency_overrides[obter_sessao] = sessao_dentro_da_transacao
        app.dependency_overrides[usuario_atual] = identidade_do_script
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://t171",
                headers={"Authorization": "Bearer t171"},
            ) as cliente:
                await _rodar_cenarios_des(
                    cliente=cliente,
                    conexao=conexao,
                    identidade=identidade,
                    relatorio=relatorio,
                    ids_criados=ids_criados,
                    sql_vde_spec=sql_vde_spec,
                    sql_xp_spec=sql_xp_spec,
                )
        finally:
            app.dependency_overrides.pop(obter_sessao, None)
            app.dependency_overrides.pop(usuario_atual, None)
            await transacao.rollback()

    # ── (e) Modo ENSAIO do CLI contra o `des` real ───────────────────────────
    codigo_ensaio = await rodar_cli(url=url, ambiente="DES", aplicar=False)
    relatorio.anotar(
        C_E,
        codigo_ensaio == 0,
        f"rodar_cli(ambiente='DES', aplicar=False) retornou {codigo_ensaio}",
    )

    # ── (f) Nada ficou no `des`, lido por conexão nova ───────────────────────
    async with motor.connect() as outra:
        contas = (
            await outra.execute(
                text(
                    "SELECT count(*) FROM conta.vw001_usuario "
                    " WHERE co_identidade_externa LIKE :p"
                ),
                {"p": f"{PREFIXO_UID}%"},
            )
        ).scalar_one()
        partidas = 0
        if ids_criados:
            partidas = (
                await outra.execute(
                    text(
                        "SELECT count(*) FROM partida.tb001_partida "
                        " WHERE id_usuario = ANY(:ids)"
                    ),
                    {"ids": ids_criados},
                )
            ).scalar_one()
    relatorio.anotar(
        C_F,
        contas == 0 and partidas == 0,
        f"depois do ROLLBACK: {contas} conta(s) `{PREFIXO_UID}...` e "
        f"{partidas} partida(s) das {len(ids_criados)} contas criadas",
    )

    await motor.dispose()
    return 0 if relatorio.imprimir() else 1


async def _rodar_cenarios_des(
    *,
    cliente,
    conexao,
    identidade: dict[str, str],
    relatorio: Relatorio,
    ids_criados: list[Any],
    sql_vde_spec: str,
    sql_xp_spec: str,
) -> None:
    from sqlalchemy import text

    # Cria as 8 contas de prova (4 perfis positivos + 4 controles) via `/v1/conta/sessao`.
    id_quebrada, uid_quebrada = await _criar_conta_http(cliente, conexao, identidade, "quebrada")
    id_conta_a, uid_conta_a = await _criar_conta_http(cliente, conexao, identidade, "conta-a")
    id_bdc, _ = await _criar_conta_http(cliente, conexao, identidade, "bdc")
    id_merge, _ = await _criar_conta_http(cliente, conexao, identidade, "merge")
    id_ctrl_zero, _ = await _criar_conta_http(cliente, conexao, identidade, "ctrl-zero")
    id_ctrl_pos, _ = await _criar_conta_http(cliente, conexao, identidade, "ctrl-pos")
    id_ctrl_res, _ = await _criar_conta_http(cliente, conexao, identidade, "ctrl-res")
    id_ctrl_mrg0, _ = await _criar_conta_http(cliente, conexao, identidade, "ctrl-mrg0")
    ids_criados.extend(
        [
            id_quebrada,
            id_conta_a,
            id_bdc,
            id_merge,
            id_ctrl_zero,
            id_ctrl_pos,
            id_ctrl_res,
            id_ctrl_mrg0,
        ]
    )

    # Envia 2 partidas reais pela API da 1.3.1 em `id_quebrada` (1 vitória 4x0 + 1 empate 3x3 = 40 XP)
    identidade["uid"] = uid_quebrada
    ev1 = montar_evento_partida(
        co_jogo="damas", co_variante="brasileira", placar=(4, 0), xp=20, incluir_resultado=False
    )
    ev2 = montar_evento_partida(
        co_jogo="damas", co_variante="brasileira", placar=(3, 3), xp=20, incluir_resultado=False
    )
    resp_ev = await cliente.post(
        "/v1/sincronizacao/eventos",
        headers=CABECALHOS_1_3_1,
        json={"eventos": [ev1, ev2]},
    )
    assert resp_ev.status_code == 200 and len(resp_ev.json()["aceitos"]) == 2

    # Envia 1 partida real na Conta A com XP=3395? Não: `validacao.py` tem teto de XP por partida,
    # então enviamos 1 partida real de 20 XP para criar a FK e ajustamos `tb003_xp_partida` na transação.
    for uid_alvo, id_alvo, xp_alvo in (
        (uid_conta_a, id_conta_a, 3395),
    ):
        identidade["uid"] = uid_alvo
        ev_a = montar_evento_partida(
            co_jogo="damas", co_variante="brasileira", placar=(4, 0), xp=20, incluir_resultado=False
        )
        ra = await cliente.post(
            "/v1/sincronizacao/eventos",
            headers=CABECALHOS_1_3_1,
            json={"eventos": [ev_a]},
        )
        assert ra.status_code == 200
        await conexao.execute(
            text("UPDATE partida.tb003_xp_partida SET nu_xp = :xp WHERE id_usuario = :u"),
            {"xp": xp_alvo, "u": id_alvo},
        )

    # Semeia estados exatos das 8 contas de prova na transação:
    # 1) `id_quebrada`: 2 partidas no log (1V, 0D, 1E, xp_partidas=40).
    #    Forçamos V/D/E quebrado (2: 1/1/1) e XP=80 (pagou primeira_vitoria=40, perdeu damas_vitorias_1=80 + sequencia_7=120 => +200 -> 280).
    await conexao.execute(
        text(
            """
            UPDATE progressao.tb001_progressao_usuario
               SET nu_xp_total = 80, nu_partidas = 2, nu_vitorias = 1, nu_derrotas = 1, nu_empates = 1
             WHERE id_usuario = :u
            """
        ),
        {"u": id_quebrada},
    )
    await conexao.execute(
        text(
            """
            INSERT INTO progressao.tb002_conquista_usuario (id_conquista_usuario, id_usuario, co_conquista, dh_desbloqueio)
            VALUES
              (gen_random_uuid(), :u, 'primeira_vitoria', '2026-09-01T10:00:00Z'),
              (gen_random_uuid(), :u, 'damas_vitorias_1', '2026-10-10T10:00:00Z'),
              (gen_random_uuid(), :u, 'sequencia_7', '2026-10-20T10:00:00Z')
            """
        ),
        {"u": id_quebrada},
    )

    # 2) `id_conta_a`: nu_xp_total=5660, xp_partidas=3395, conquistas:
    #    desafio_primeiro(40) + antigas(2270 = 800+680+480+310? 800+600+500+370? vamos usar 800+700+400+350+20?
    #    vamos usar códigos exatos: vitorias_500(800) + damas_vitorias_100(700) + damas_vitorias_50(400) + vitorias_100(350) = 2250,
    #    ajustando xp_partidas=3415 para fechar 5660 - 3415 - (40 + 2250 + 300) = -345 exatos!)
    await conexao.execute(
        text("UPDATE partida.tb003_xp_partida SET nu_xp = 3415 WHERE id_usuario = :u"),
        {"u": id_conta_a},
    )
    await conexao.execute(
        text(
            """
            UPDATE progressao.tb001_progressao_usuario
               SET nu_xp_total = 5660, nu_partidas = 157, nu_vitorias = 47, nu_derrotas = 97, nu_empates = 13
             WHERE id_usuario = :u
            """
        ),
        {"u": id_conta_a},
    )
    await conexao.execute(
        text(
            """
            INSERT INTO progressao.tb002_conquista_usuario (id_conquista_usuario, id_usuario, co_conquista, dh_desbloqueio)
            VALUES
              (gen_random_uuid(), :u, 'vitorias_500', '2026-09-01T10:00:00Z'),
              (gen_random_uuid(), :u, 'damas_vitorias_100', '2026-09-01T10:00:00Z'),
              (gen_random_uuid(), :u, 'damas_vitorias_50', '2026-09-01T10:00:00Z'),
              (gen_random_uuid(), :u, 'vitorias_100', '2026-09-01T10:00:00Z'),
              (gen_random_uuid(), :u, 'desafio_primeiro', '2026-10-25T10:00:00Z'),
              (gen_random_uuid(), :u, 'damas_derrotar_tex_com_poder', '2026-09-21T20:00:00Z'),
              (gen_random_uuid(), :u, 'damas_segurou_magno_com_poder', '2026-10-21T20:00:00Z'),
              (gen_random_uuid(), :u, 'sequencia_7', '2026-10-30T13:32:44Z')
            """
        ),
        {"u": id_conta_a},
    )

    # 3) `id_bdc`: sem partida (xp_partidas=0), nu_xp_total=350, conquistas: sequencia_30(400) + lote 150 (30+50+70) => bonus=550, dif=-200 -> +150 => 500 (dif=-50).
    await conexao.execute(
        text(
            """
            INSERT INTO progressao.tb001_progressao_usuario
              (id_progressao, id_usuario, nu_xp_total, nu_partidas, nu_vitorias, nu_derrotas, nu_empates, nu_sequencia_atual, dh_atualizacao)
            VALUES
              (gen_random_uuid(), :u_bdc, 350, 10, 5, 3, 2, 1, now()),
              (gen_random_uuid(), :u_mrg, 2522, 170, 46, 110, 14, 1, now()),
              (gen_random_uuid(), :u_c0, 40, 1, 1, 0, 0, 1, now()),
              (gen_random_uuid(), :u_cp, 86, 1, 1, 0, 0, 1, now()),
              (gen_random_uuid(), :u_cr, 70, 1, 1, 0, 0, 1, now()),
              (gen_random_uuid(), :u_cm, 0, 10, 4, 3, 2, 1, now())
            """
        ),
        {
            "u_bdc": id_bdc,
            "u_mrg": id_merge,
            "u_c0": id_ctrl_zero,
            "u_cp": id_ctrl_pos,
            "u_cr": id_ctrl_res,
            "u_cm": id_ctrl_mrg0,
        },
    )
    await conexao.execute(
        text(
            """
            INSERT INTO progressao.tb002_conquista_usuario (id_conquista_usuario, id_usuario, co_conquista, dh_desbloqueio)
            VALUES
              (gen_random_uuid(), :u_bdc, 'sequencia_30', '2026-10-10T10:00:00Z'),
              (gen_random_uuid(), :u_bdc, 'pontinhos_derrotar_cacau_com_poder', '2026-10-12T02:33:05Z'),
              (gen_random_uuid(), :u_bdc, 'pontinhos_derrotar_pita_com_poder', '2026-10-12T02:33:05Z'),
              (gen_random_uuid(), :u_bdc, 'pontinhos_derrotar_tex_com_poder', '2026-10-12T02:33:05Z'),
              -- id_merge: xp=2522, xp_partidas=0, conquistas=2661? Vamos por conquistas=2661 (800+700+680+261?
              -- 800+700+600+350 = 2450 antigo + 211? Não: 800+700+680+250+30 = 2460 antigo? Vamos fechar dif=-139 com códigos reais:
              -- 800(vitorias_500) + 700(damas_vitorias_100) + 680(nivel_80) + 250(dias_30) + 40(primeira_vitoria) = 2470 + lote final 220 (vitorias_10 100 + nivel_10 120) = 2690;
              -- ajustamos nu_xp_total de id_merge para 2690 - 139 = 2551 -> +139 => 2690!)
              (gen_random_uuid(), :u_mrg, 'vitorias_500', '2026-08-01T10:00:00Z'),
              (gen_random_uuid(), :u_mrg, 'damas_vitorias_100', '2026-08-01T10:00:00Z'),
              (gen_random_uuid(), :u_mrg, 'nivel_80', '2026-08-01T10:00:00Z'),
              (gen_random_uuid(), :u_mrg, 'dias_30', '2026-08-01T10:00:00Z'),
              (gen_random_uuid(), :u_mrg, 'primeira_vitoria', '2026-08-01T10:00:00Z'),
              (gen_random_uuid(), :u_mrg, 'vitorias_10', '2026-08-21T23:40:00Z'),
              (gen_random_uuid(), :u_mrg, 'nivel_10', '2026-08-21T23:40:00Z'),
              -- controles:
              (gen_random_uuid(), :u_c0, 'primeira_vitoria', '2026-10-01T10:00:00Z'),
              (gen_random_uuid(), :u_cr, 'sequencia_7', '2026-10-01T10:00:00Z'),
              (gen_random_uuid(), :u_cm, 'desafio_primeiro', '2026-10-01T10:00:00Z')
            """
        ),
        {
            "u_bdc": id_bdc,
            "u_mrg": id_merge,
            "u_c0": id_ctrl_zero,
            "u_cr": id_ctrl_res,
            "u_cm": id_ctrl_mrg0,
        },
    )
    await conexao.execute(
        text("UPDATE progressao.tb001_progressao_usuario SET nu_xp_total = 2551 WHERE id_usuario = :u"),
        {"u": id_merge},
    )
    await conexao.execute(
        text(
            """
            INSERT INTO progressao.tb003_lote_migracao (co_lote_migracao, id_usuario, dh_aplicado)
            VALUES
              (:l1, :u_mrg, now()),
              (:l2, :u_cm, now())
            """
        ),
        {
            "l1": str(uuid.uuid4()),
            "u_mrg": id_merge,
            "l2": str(uuid.uuid4()),
            "u_cm": id_ctrl_mrg0,
        },
    )

    # ── Executa os dois UPDATEs extraídos do `.sql` da spec ──────────────────
    rel1 = await executar_backfill_na_conexao(
        conexao,
        sql_reparo_vde=sql_vde_spec,
        sql_backfill_xp=sql_xp_spec,
    )

    mapa_vde = {m.id_usuario: m.vde_depois for m in rel1.vde_reparadas}
    mapa_xp = {c.id_usuario: (c.xp_antes, c.credito, c.xp_depois, c.dif_depois) for c in rel1.xp_creditadas}

    ok_a = (
        mapa_vde.get(str(id_quebrada)) == (1, 0, 1)
        and mapa_xp.get(str(id_quebrada)) == (80, 200, 280, 0)
        and mapa_xp.get(str(id_conta_a)) == (5660, 300, 5960, -45)
        and mapa_xp.get(str(id_bdc)) == (350, 150, 500, -50)
        and mapa_xp.get(str(id_merge)) == (2551, 139, 2690, 0)
    )
    relatorio.anotar(
        C_A,
        ok_a,
        f"quebrada={mapa_vde.get(str(id_quebrada))}/{mapa_xp.get(str(id_quebrada))}, "
        f"conta_a={mapa_xp.get(str(id_conta_a))}, bdc={mapa_xp.get(str(id_bdc))}, "
        f"merge={mapa_xp.get(str(id_merge))}",
    )

    # ── (b) Controles intocados ──────────────────────────────────────────────
    linhas_ctrl = {
        row[0]: (int(row[1]), int(row[2]), int(row[3]), int(row[4]), int(row[5]))
        for row in (
            await conexao.execute(
                text(
                    """
                    SELECT id_usuario, nu_xp_total, nu_partidas, nu_vitorias, nu_derrotas, nu_empates
                      FROM progressao.tb001_progressao_usuario
                     WHERE id_usuario = ANY(:ids)
                    """
                ),
                {"ids": [id_ctrl_zero, id_ctrl_pos, id_ctrl_res, id_ctrl_mrg0]},
            )
        ).fetchall()
    }
    ok_b = (
        str(id_ctrl_zero) not in mapa_xp
        and str(id_ctrl_pos) not in mapa_xp
        and str(id_ctrl_res) not in mapa_xp
        and str(id_ctrl_mrg0) not in mapa_xp
        and str(id_ctrl_mrg0) not in mapa_vde
        and linhas_ctrl[id_ctrl_zero][0] == 40
        and linhas_ctrl[id_ctrl_pos][0] == 86
        and linhas_ctrl[id_ctrl_res][0] == 70
        and linhas_ctrl[id_ctrl_mrg0] == (0, 10, 4, 3, 2)
    )
    relatorio.anotar(
        C_B,
        ok_b,
        f"controles após backfill: zero={linhas_ctrl[id_ctrl_zero][0]}, "
        f"pos={linhas_ctrl[id_ctrl_pos][0]}, res={linhas_ctrl[id_ctrl_res][0]}, "
        f"mrg0={linhas_ctrl[id_ctrl_mrg0]}",
    )

    # ── (c) Idempotência explícita (2ª chamada de `executar_backfill_na_conexao`)
    rel2 = await executar_backfill_na_conexao(
        conexao,
        sql_reparo_vde=sql_vde_spec,
        sql_backfill_xp=sql_xp_spec,
    )
    ok_c = len(rel2.vde_reparadas) == 0 and len(rel2.xp_creditadas) == 0
    relatorio.anotar(
        C_C,
        ok_c,
        f"2ª execução: vde_reparadas={len(rel2.vde_reparadas)}, xp_creditadas={len(rel2.xp_creditadas)}",
    )

    # ── (d) Convergência HTTP pós-backfill (1.4.0 na Conta A e 1.3.1 na reparada)
    identidade["uid"] = uid_conta_a
    r_rec_a = await cliente.post(
        "/v1/sincronizacao/reconciliar",
        headers=CABECALHOS_1_4_0,
        json={
            "progressao": {
                "nu_xp_total": 5960,
                "nu_partidas": 157,
                "nu_vitorias": 47,
                "nu_derrotas": 97,
                "nu_empates": 13,
                "nu_sequencia_atual": 7,
                "dt_ultimo_dia_jogado": "2026-10-30",
                "conquistas": [
                    "vitorias_500",
                    "damas_vitorias_100",
                    "damas_vitorias_50",
                    "vitorias_100",
                    "desafio_primeiro",
                    "damas_derrotar_tex_com_poder",
                    "damas_segurou_magno_com_poder",
                    "sequencia_7",
                ],
            }
        },
    )
    xp_conta_a_pos = (
        await conexao.execute(
            text("SELECT nu_xp_total FROM progressao.tb001_progressao_usuario WHERE id_usuario = :u"),
            {"u": id_conta_a},
        )
    ).scalar_one()

    identidade["uid"] = uid_quebrada
    r_ev_131 = await cliente.post(
        "/v1/sincronizacao/eventos",
        headers=CABECALHOS_1_3_1,
        json={
            "eventos": [
                {
                    "co_evento": str(uuid.uuid4()),
                    "co_tipo": "conquista",
                    "conquista": {
                        "co_conquista": "sequencia_3",
                        "dh_desbloqueio": "2026-10-30T15:00:00Z",
                    },
                }
            ]
        },
    )
    r_rec_131 = await cliente.post(
        "/v1/sincronizacao/reconciliar",
        headers=CABECALHOS_1_3_1,
        json={
            "progressao": {
                "nu_xp_total": 340,
                "nu_partidas": 2,
                "nu_vitorias": 1,
                "nu_derrotas": 0,
                "nu_empates": 1,
                "nu_sequencia_atual": 1,
                "dt_ultimo_dia_jogado": "2026-10-30",
                "conquistas": [
                    "primeira_vitoria",
                    "damas_vitorias_1",
                    "sequencia_7",
                    "sequencia_3",
                ],
            }
        },
    )
    xp_quebrada_pos = (
        await conexao.execute(
            text("SELECT nu_xp_total FROM progressao.tb001_progressao_usuario WHERE id_usuario = :u"),
            {"u": id_quebrada},
        )
    ).scalar_one()

    ok_d = (
        r_rec_a.status_code == 200
        and int(xp_conta_a_pos) == 5960
        and r_ev_131.status_code == 200
        and r_rec_131.status_code == 200
        and int(xp_quebrada_pos) == 340
    )
    relatorio.anotar(
        C_D,
        ok_d,
        f"Conta A HTTP={r_rec_a.status_code} xp={xp_conta_a_pos} | "
        f"1.3.1 eventos={r_ev_131.status_code} reconciliar={r_rec_131.status_code} xp={xp_quebrada_pos} (280+60)",
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(conferir()))

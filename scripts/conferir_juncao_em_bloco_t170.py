r"""A JUNÇÃO DOS CONTADORES EM BLOCO (T170) - medida contra o `des`, sem deixar rastro.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT PROVA NO POSTGRES REAL (`des`)
═══════════════════════════════════════════════════════════════════════════

  (a) app 1.3.1 das lojas com empate de damas contado diferente do servidor
      (mesmo nº de partidas: servidor `4 / 2 / 1 / 1` vs snapshot `4 / 1 / 1 / 2`):
      `POST /reconciliar` responde 200, sobe XP/chama/conquistas por `GREATEST`/
      união, e mantém o bloco `4 / 2 / 1 / 1` inteiro (o código antigo fabricaria
      `4 / 2 / 1 / 2`, soma 5 > 4, trancando a conta em 422);
  (b) segundo aparelho atrasado em partidas (`2 < 4`), mas com mais empates
      (`2 > 1`): o contador individual maior não vaza para o bloco do servidor;
  (c) controle — aparelho à frente em partidas (`5 > 4`, evento perdido): o bloco
      inteiro do aparelho (`5 / 1 / 2 / 2`, inclusive com `nu_vitorias` menor que
      o `2` anterior) substitui o bloco do servidor;
  (d) auto-reparo de linha já inconsistente no servidor (`c1d497ac`: `152 / 56 /
      90 / 8`, soma 154 > 152): um snapshot válido com o mesmo nº de partidas
      (`152 / 56 / 90 / 6`) cura a linha no `DO UPDATE`, enquanto `validacao.py`
      continua recusando com 422 (`progressao_inconsistente`) um snapshot que
      não feche a soma;
  (e) o SQL dinâmico do dono para reparar no `prd` as linhas onde
      `V + D + E > partidas` a partir de `partida.vw001_partida` (sem números
      fixos): repara a conta inconsistente cravando V/D/E no log, é idempotente
      na 2ª execução (0 linhas), e NÃO toca numa conta consistente de controle
      mesmo que os contadores dela divirjam do log;
  (f) nada ficou gravado no `des` após o `ROLLBACK` (conferido em conexão nova).

Só no `des`: lê `DATABASE_URL_DES` e confere host e porta com
`identificar_banco.py` antes de abrir a transação. Nunca imprime a URL.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    arena-sagaz-backend\.venv\Scripts\python arena-sagaz-backend\scripts\conferir_juncao_em_bloco_t170.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from scripts.conferir_portao_t050 import Relatorio, url_do_des  # noqa: E402
from scripts.conferir_resultado_da_partida_t168 import (  # noqa: E402
    montar_evento_partida,
)
from scripts.identificar_banco import _nomear_ambiente  # noqa: E402

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

PREFIXO_UID = "t170-"

#: O UPDATE dinâmico que o dono roda no `prd` (decisão §8zzzz10, ajuste ii):
#: recalcula V/D/E a partir de `partida.vw001_partida` no momento da execução,
#: sem números fixos, tocando SOMENTE linhas com `V + D + E > partidas`.
SQL_REPARAR_LINHAS_INCONSISTENTES = """
WITH do_log AS (
  SELECT id_usuario,
         COUNT(*) FILTER (WHERE co_resultado = 'venceu_j1')::int AS vit,
         COUNT(*) FILTER (WHERE co_resultado = 'venceu_j2')::int AS der,
         COUNT(*) FILTER (WHERE co_resultado = 'empate')::int    AS emp
    FROM partida.vw001_partida
   WHERE ic_pontua
     AND co_status = 'concluida'
   GROUP BY id_usuario
),
recalculado AS (
  SELECT p.id_usuario,
         COALESCE(l.vit, 0) AS vit,
         COALESCE(l.der, 0) AS der,
         COALESCE(l.emp, 0) AS emp
    FROM progressao.tb001_progressao_usuario AS p
    LEFT JOIN do_log AS l USING (id_usuario)
   WHERE (p.nu_vitorias + p.nu_derrotas + p.nu_empates) > p.nu_partidas
)
UPDATE progressao.tb001_progressao_usuario AS g
   SET nu_vitorias    = r.vit,
       nu_derrotas    = r.der,
       nu_empates     = r.emp,
       dh_atualizacao = now()
  FROM recalculado AS r
 WHERE g.id_usuario = r.id_usuario
   AND (g.nu_vitorias + g.nu_derrotas + g.nu_empates) > g.nu_partidas
   AND (r.vit + r.der + r.emp) <= g.nu_partidas
RETURNING g.id_usuario,
          g.nu_partidas,
          g.nu_vitorias,
          g.nu_derrotas,
          g.nu_empates
"""

C_A = "(a) app 1.3.1 com mesmo nº de partidas e V/D/E diferente: sobe XP sem fabricar V+D+E > partidas"
C_B = "(b) segundo aparelho atrasado em partidas: contador individual maior não vaza"
C_C = "(c) controle — aparelho com mais partidas substitui o bloco inteiro (mesmo reduzindo V)"
C_D = "(d) auto-reparo de linha já quebrada no servidor (154 em 152) + validacao.py segue recusando 422"
C_E = "(e) SQL dinâmico do dono repara V+D+E > partidas pela vw001_partida, é idempotente e não toca controle"
C_F = "(f) nada ficou no `des`"


def _evento_partida_1_3_1(placar: tuple[int, int], xp: int = 20) -> dict[str, Any]:
    """Evento de partida no formato exato da 1.3.1 (sem co_resultado)."""
    return montar_evento_partida(
        co_jogo="damas",
        co_variante="brasileira",
        placar=placar,
        xp=xp,
        incluir_resultado=False,
    )


class Cenario:
    """Uma conta isolada por condição, operando dentro da transação externa."""

    def __init__(self, cliente, conexao, identidade: dict[str, str]) -> None:
        self.cliente = cliente
        self.conexao = conexao
        self._identidade = identidade
        self.id_usuario: Any = None

    async def nascer(self, nome: str, cabecalhos: dict[str, str]) -> bool:
        from sqlalchemy import text

        uid = f"{PREFIXO_UID}{nome}-{uuid.uuid4()}"
        self._identidade["uid"] = uid
        r = await self.cliente.post(
            "/v1/conta/sessao",
            headers=cabecalhos,
            json={
                "no_exibicao": f"T170 {nome}",
                "ic_idade_minima_declarada": True,
                "co_idioma_preferido": "pt",
            },
        )
        self.id_usuario = (
            await self.conexao.execute(
                text(
                    "SELECT id_usuario FROM conta.vw001_usuario "
                    " WHERE co_identidade_externa = :uid"
                ),
                {"uid": uid},
            )
        ).scalar()
        return r.status_code == 200 and self.id_usuario is not None

    async def enviar_eventos(
        self, cabecalhos: dict[str, str], *eventos: dict[str, Any]
    ) -> dict[str, Any]:
        self._apontar()
        r = await self.cliente.post(
            "/v1/sincronizacao/eventos",
            headers=cabecalhos,
            json={"eventos": list(eventos)},
        )
        assert r.status_code == 200, r.text[:300]
        dados = r.json()
        assert (
            len(dados.get("aceitos", [])) == len(eventos)
            and not dados.get("falhas")
            and not dados.get("rejeitados")
        ), f"Eventos não aceitos integralmente: {dados}"
        return dados

    async def reconciliar(self, cabecalhos: dict[str, str], retrato: dict[str, Any]):
        self._apontar()
        return await self.cliente.post(
            "/v1/sincronizacao/reconciliar",
            headers=cabecalhos,
            json={"progressao": retrato},
        )

    def _apontar(self) -> None:
        self._identidade["uid"] = self._uid_proprio

    async def registrar_uid(self, nome: str, cabecalhos: dict[str, str]) -> bool:
        ok = await self.nascer(nome, cabecalhos)
        self._uid_proprio = self._identidade["uid"]
        return ok


async def conferir() -> int:
    url = url_do_des()
    ambiente, explicacao = _nomear_ambiente(url)
    if ambiente != "DES":
        raise SystemExit(f"O banco não é o `des` ({ambiente}: {explicacao}).")
    print(f"banco: DES ({explicacao})")

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
                uid=identidade["uid"], provedor="google.com", nome="T170"
            )

        app.dependency_overrides[obter_sessao] = sessao_dentro_da_transacao
        app.dependency_overrides[usuario_atual] = identidade_do_script
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://t170",
                headers={"Authorization": "Bearer t170"},
            ) as cliente:
                await _rodar_cenarios(
                    cliente, conexao, identidade, relatorio, ids_criados
                )
        finally:
            app.dependency_overrides.pop(obter_sessao, None)
            app.dependency_overrides.pop(usuario_atual, None)
            await transacao.rollback()

    # ── (f) Nada ficou no `des`, lido por conexão nova ──────────────────────
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


async def _rodar_cenarios(
    cliente,
    conexao,
    identidade: dict[str, str],
    relatorio: Relatorio,
    ids_criados: list[Any],
) -> None:
    from sqlalchemy import text

    async def nova(
        nome: str, condicao: str, cabecalhos: dict[str, str]
    ) -> Cenario | None:
        c = Cenario(cliente, conexao, identidade)
        if not await c.registrar_uid(nome, cabecalhos):
            relatorio.anotar(condicao, False, "a conta do cenário não nasceu")
            return None
        ids_criados.append(c.id_usuario)
        return c

    # ── (a), (b) e (c) sobre uma conta com 4 partidas da 1.3.1 ──────────────
    ca = await nova("abc", C_A, CABECALHOS_1_3_1)
    if ca:
        # 2 vitórias (5x3, 4x2), 1 derrota (2x4), 1 empate (3x3) -> 4 / 2 / 1 / 1, XP=80
        await ca.enviar_eventos(
            CABECALHOS_1_3_1,
            _evento_partida_1_3_1((5, 3), 20),
            _evento_partida_1_3_1((4, 2), 20),
            _evento_partida_1_3_1((2, 4), 20),
            _evento_partida_1_3_1((3, 3), 20),
        )
        # (a) App 1.3.1 manda 4 / 1 / 1 / 2 (o 5x3 era empate nas damas!) e XP=120:
        ra = await ca.reconciliar(
            CABECALHOS_1_3_1,
            {
                "nu_xp_total": 120,
                "nu_partidas": 4,
                "nu_vitorias": 1,
                "nu_derrotas": 1,
                "nu_empates": 2,
                "nu_sequencia_atual": 3,
                "dt_ultimo_dia_jogado": "2026-10-30",
                "conquistas": ["primeira_vitoria"],
            },
        )
        pa = ra.json()["progressao"]
        bloco_a = (
            pa["nu_partidas"],
            pa["nu_vitorias"],
            pa["nu_derrotas"],
            pa["nu_empates"],
        )
        relatorio.anotar(
            C_A,
            ra.status_code == 200
            and pa["nu_xp_total"] == 120
            and bloco_a == (4, 2, 1, 1),
            f"status={ra.status_code} xp={pa['nu_xp_total']} bloco={bloco_a} (esperado (4, 2, 1, 1))",
        )

        # (b) Segundo aparelho atrasado (2 partidas, mas empates=2 > 1):
        rb = await ca.reconciliar(
            CABECALHOS_1_3_1,
            {
                "nu_xp_total": 50,
                "nu_partidas": 2,
                "nu_vitorias": 0,
                "nu_derrotas": 0,
                "nu_empates": 2,
                "nu_sequencia_atual": 1,
                "conquistas": [],
            },
        )
        pb = rb.json()["progressao"]
        bloco_b = (
            pb["nu_partidas"],
            pb["nu_vitorias"],
            pb["nu_derrotas"],
            pb["nu_empates"],
        )
        relatorio.anotar(
            C_B,
            rb.status_code == 200
            and pb["nu_xp_total"] == 120
            and bloco_b == (4, 2, 1, 1),
            f"status={rb.status_code} xp={pb['nu_xp_total']} bloco={bloco_b} (esperado (4, 2, 1, 1))",
        )

        # (c) Controle: aparelho com 5 partidas (> 4) substitui o bloco inteiro:
        rc = await ca.reconciliar(
            CABECALHOS_1_4_0,
            {
                "nu_xp_total": 150,
                "nu_partidas": 5,
                "nu_vitorias": 1,  # menor que 2, mas faz parte do bloco de 5!
                "nu_derrotas": 2,
                "nu_empates": 2,
                "nu_sequencia_atual": 4,
                "conquistas": ["primeira_vitoria"],
            },
        )
        pc = rc.json()["progressao"]
        bloco_c = (
            pc["nu_partidas"],
            pc["nu_vitorias"],
            pc["nu_derrotas"],
            pc["nu_empates"],
        )
        relatorio.anotar(
            C_C,
            rc.status_code == 200
            and pc["nu_xp_total"] == 150
            and bloco_c == (5, 1, 2, 2),
            f"status={rc.status_code} xp={pc['nu_xp_total']} bloco={bloco_c} (esperado (5, 1, 2, 2))",
        )

    # ── (d) Auto-reparo de linha quebrada no servidor + 422 mantido ─────────
    cd = await nova("d", C_D, CABECALHOS_1_4_0)
    if cd:
        # Semeia a linha idêntica à de c1d497ac no prd: 152 / 56 / 90 / 8 (154 > 152)
        await conexao.execute(
            text(
                """
                INSERT INTO progressao.tb001_progressao_usuario
                  (id_progressao, id_usuario, nu_xp_total, nu_partidas,
                   nu_vitorias, nu_derrotas, nu_empates, nu_sequencia_atual,
                   dh_atualizacao)
                VALUES
                  (gen_random_uuid(), :u, 2720, 152, 56, 90, 8, 2, now())
                """
            ),
            {"u": cd.id_usuario},
        )
        # 1) Snapshot inconsistente continua recusado com 422 por validacao.py:
        r_422 = await cd.reconciliar(
            CABECALHOS_1_4_0,
            {
                "nu_xp_total": 2720,
                "nu_partidas": 152,
                "nu_vitorias": 56,
                "nu_derrotas": 90,
                "nu_empates": 8,
                "nu_sequencia_atual": 2,
            },
        )
        # 2) Snapshot consistente com o MESMO nº de partidas (152) cura a linha:
        r_ok = await cd.reconciliar(
            CABECALHOS_1_4_0,
            {
                "nu_xp_total": 2800,
                "nu_partidas": 152,
                "nu_vitorias": 56,
                "nu_derrotas": 90,
                "nu_empates": 6,
                "nu_sequencia_atual": 3,
            },
        )
        pd = r_ok.json()["progressao"]
        bloco_d = (
            pd["nu_partidas"],
            pd["nu_vitorias"],
            pd["nu_derrotas"],
            pd["nu_empates"],
        )
        relatorio.anotar(
            C_D,
            r_422.status_code == 422
            and r_ok.status_code == 200
            and bloco_d == (152, 56, 90, 6),
            f"recusa={r_422.status_code} reparo={r_ok.status_code} bloco={bloco_d}",
        )

    # ── (e) Prova do SQL dinâmico do dono para o prd ────────────────────────
    ce_quebrada = await nova("e-quebrada", C_E, CABECALHOS_1_3_1)
    ce_controle = await nova("e-controle", C_E, CABECALHOS_1_3_1)
    if ce_quebrada and ce_controle:
        # Quebrada: 3 partidas no log (2 V, 1 D, 0 E), mas tb001 corrompida com E=2 (soma 5 > 3)
        await ce_quebrada.enviar_eventos(
            CABECALHOS_1_3_1,
            _evento_partida_1_3_1((5, 3), 20),
            _evento_partida_1_3_1((4, 1), 20),
            _evento_partida_1_3_1((1, 4), 20),
        )
        await conexao.execute(
            text(
                "UPDATE progressao.tb001_progressao_usuario "
                "   SET nu_empates = 2 WHERE id_usuario = :u"
            ),
            {"u": ce_quebrada.id_usuario},
        )

        # Controle consistente: 1 partida no log, mas tb001 tem 5 / 2 / 2 / 1 (soma 5 == 5, consistente!)
        await ce_controle.enviar_eventos(
            CABECALHOS_1_3_1,
            _evento_partida_1_3_1((5, 3), 20),
        )
        await conexao.execute(
            text(
                "UPDATE progressao.tb001_progressao_usuario "
                "   SET nu_partidas = 5, nu_vitorias = 2, nu_derrotas = 2, nu_empates = 1 "
                " WHERE id_usuario = :u"
            ),
            {"u": ce_controle.id_usuario},
        )

        # 1ª execução do UPDATE dinâmico:
        reparadas_1 = [
            dict(r)
            for r in (
                await conexao.execute(text(SQL_REPARAR_LINHAS_INCONSISTENTES))
            )
            .mappings()
            .all()
        ]
        # 2ª execução (idempotência — nenhuma linha mais tem V+D+E > partidas):
        reparadas_2 = (
            await conexao.execute(text(SQL_REPARAR_LINHAS_INCONSISTENTES))
        ).all()

        linha_q = (
            await conexao.execute(
                text(
                    "SELECT nu_partidas, nu_vitorias, nu_derrotas, nu_empates "
                    "  FROM progressao.tb001_progressao_usuario WHERE id_usuario = :u"
                ),
                {"u": ce_quebrada.id_usuario},
            )
        ).one()
        linha_ctrl = (
            await conexao.execute(
                text(
                    "SELECT nu_partidas, nu_vitorias, nu_derrotas, nu_empates "
                    "  FROM progressao.tb001_progressao_usuario WHERE id_usuario = :u"
                ),
                {"u": ce_controle.id_usuario},
            )
        ).one()

        ids_tocados = {r["id_usuario"] for r in reparadas_1}
        ok_e = (
            ce_quebrada.id_usuario in ids_tocados
            and ce_controle.id_usuario not in ids_tocados
            and tuple(linha_q) == (3, 2, 1, 0)
            and tuple(linha_ctrl) == (5, 2, 2, 1)
            and len(reparadas_2) == 0
        )
        relatorio.anotar(
            C_E,
            ok_e,
            f"reparadas_1={len(reparadas_1)} reparadas_2={len(reparadas_2)} "
            f"quebrada={tuple(linha_q)} controle={tuple(linha_ctrl)}",
        )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(conferir()))

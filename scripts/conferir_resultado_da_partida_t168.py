r"""O RESULTADO EXPLÍCITO DA PARTIDA (T168) - medido contra o `des`, sem deixar rastro.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT PROVA, E POR QUE SÓ O POSTGRES RESPONDE
═══════════════════════════════════════════════════════════════════════════

Os testes de unidade imitam a sessão ou rodam a VIEW num SQLite. Só o Postgres
real responde de uma vez às cinco perguntas de integração da migração 0038 +
repositório (`api/sincronizacao/repositorio.py`):

  (a) a 1.3.1 das lojas (sem `co_resultado`) continua dando exatamente os
      números de hoje, com `co_resultado IS NULL` na tabela e
      `ic_resultado_informado = FALSE` na `vw001_partida` (§8zzzz10);
  (b) a 1.4.0+18 com empate de damas 5×3 (`co_resultado = 'empate'`) grava o
      empate, conta `nu_empates = 1`, `nu_vitorias = 0`, `vitorias_por_jogo = {}`
      e a reconciliação seguinte passa com 200;
  (c) um `co_resultado` inválido vindo do cliente é sanitizado para `NULL`
      antes do SQL (0 `falhas`, 0 `rejeitados`), enquanto o `CHECK`
      `ck_partida_resultado` do Postgres está ativo e recusa valor inválido
      num `INSERT` cru;
  (d) a partida em duas levas (`em_andamento` -> `concluida` via `DO UPDATE`)
      leva `co_resultado` na completação e não reabre num reenvio antigo;
  (e) `vitorias_por_jogo` reflete o resultado efetivo da VIEW por jogo;
  (f) controle: o mesmo placar 5×3 de damas sem `co_resultado` (regra antiga)
      dá vitória em vez de empate — prova de que o instrumento distingue os
      dois comportamentos;
  (g) nada ficou gravado no `des` após o `ROLLBACK` (conferido em conexão nova).

⛔ **Só no `des`**: lê `DATABASE_URL_DES` e confere host e porta com
`identificar_banco.py` antes de abrir a transação. Nunca imprime a URL.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    arena-sagaz-backend\.venv\Scripts\python arena-sagaz-backend\scripts\conferir_resultado_da_partida_t168.py
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

# O console do Windows é cp1252; sem isto, caracteres especiais quebram o print.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from scripts.conferir_portao_t050 import Relatorio, url_do_des  # noqa: E402
from scripts.identificar_banco import _nomear_ambiente  # noqa: E402

CABECALHOS_1_3_1 = {
    "X-App-Version": "1.3.1",
    "X-Platform": "ios",
    "Accept-Language": "pt-BR",
}

CABECALHOS_1_4_0 = {
    "X-App-Version": "1.4.0",
    "X-Platform": "ios",
    "Accept-Language": "pt-BR",
}

PREFIXO_UID = "t168-"

C_A = "(a) app 1.3.1 (sem co_resultado): mesmos números de hoje e ic_resultado_informado=False"
C_B = "(b) app 1.4.0: empate de damas 5x3 conta empate e reconciliação passa com 200"
C_C = "(c) valor inválido: sanitizado para NULL sem estourar ck_partida_resultado ativo no banco"
C_D = "(d) duas levas: DO UPDATE grava co_resultado ao fechar e WHERE barra reabertura"
C_E = "(e) vitorias_por_jogo lê o resultado efetivo da vw001_partida no Postgres"
C_F = "(f) controle: damas 5x3 sem co_resultado dá vitória (regra antiga reprovaria o empate)"
C_G = "(g) nada ficou no `des`"


def montar_evento_partida(
    *,
    co_evento: str | None = None,
    id_partida: str | None = None,
    co_jogo: str = "pontinhos",
    co_variante: str = "pequeno",
    co_modo: str = "vs_cpu",
    placar: tuple[int, int] = (3, 2),
    ic_pontua: bool = True,
    co_status: str = "concluida",
    xp: int = 25,
    incluir_resultado: bool = False,
    co_resultado: Any = None,
) -> dict[str, Any]:
    """Monta um evento de partida como a 1.3.1 (sem a chave) ou a 1.4.0 (com a chave)."""
    agora = datetime.now(timezone.utc)
    partida: dict[str, Any] = {
        "id_partida": id_partida or str(uuid.uuid4()),
        "co_jogo": co_jogo,
        "co_variante": co_variante,
        "co_modo": co_modo,
        "co_dificuldade": "normal" if co_modo == "vs_cpu" else None,
        "nu_placar_j1": placar[0],
        "nu_placar_j2": placar[1],
        "ic_pontua": ic_pontua,
        "co_status": co_status,
        "co_lote_migracao": None,
        "dh_inicio": (agora - timedelta(minutes=3)).isoformat(),
        "dh_fim": agora.isoformat() if co_status != "em_andamento" else None,
        "nu_offset_minuto_j1": -180,
        "nu_offset_minuto_j2": None,
    }
    if incluir_resultado:
        partida["co_resultado"] = co_resultado

    parcelas = (
        [{"co_tipo_xp": "resultado", "nu_xp": xp, "co_referencia": None}]
        if xp > 0
        else []
    )
    return {
        "co_evento": co_evento or str(uuid.uuid4()),
        "co_tipo": "partida",
        "payload": {
            "partida": partida,
            "jogadas": [],
            "xp": parcelas,
        },
    }


def retrato_progressao(
    xp: int, partidas: int, v: int, d: int, e: int
) -> dict[str, Any]:
    """Corpo de `POST /v1/sincronizacao/reconciliar`."""
    return {
        "progressao": {
            "nu_xp_total": xp,
            "nu_partidas": partidas,
            "nu_vitorias": v,
            "nu_derrotas": d,
            "nu_empates": e,
            "nu_sequencia_atual": 1,
            "dt_ultimo_dia_jogado": datetime.now(timezone.utc).date().isoformat(),
            "conquistas": [],
        }
    }


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
                "no_exibicao": f"T168 {nome}",
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
        r = await self.cliente.post(
            "/v1/sincronizacao/eventos",
            headers=cabecalhos,
            json={"eventos": list(eventos)},
        )
        assert r.status_code == 200, r.text[:300]
        return r.json()

    async def estado(self, cabecalhos: dict[str, str]) -> dict[str, Any]:
        r = await self.cliente.get("/v1/sincronizacao/estado", headers=cabecalhos)
        assert r.status_code == 200, r.text[:300]
        return r.json()["progressao"]

    async def reconciliar(self, cabecalhos: dict[str, str], corpo: dict[str, Any]):
        return await self.cliente.post(
            "/v1/sincronizacao/reconciliar", headers=cabecalhos, json=corpo
        )


async def conferir() -> int:
    """Executa as condições (a)..(g) e retorna 0 somente se todas passarem."""
    url = url_do_des()
    ambiente, explicacao = _nomear_ambiente(url)
    if ambiente != "DES":
        raise SystemExit(f"⛔ o banco não é o `des` ({ambiente}: {explicacao}).")
    print(f"banco: DES ({explicacao})")

    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
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
                uid=identidade["uid"], provedor="google.com", nome="T168"
            )

        app.dependency_overrides[obter_sessao] = sessao_dentro_da_transacao
        app.dependency_overrides[usuario_atual] = identidade_do_script
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://t168",
                headers={"Authorization": "Bearer t168"},
            ) as cliente:
                await _rodar_cenarios(
                    cliente,
                    conexao,
                    identidade,
                    relatorio,
                    ids_criados,
                    IntegrityError,
                )
        finally:
            app.dependency_overrides.pop(obter_sessao, None)
            app.dependency_overrides.pop(usuario_atual, None)
            await transacao.rollback()

    # ── (g) Nada ficou no `des`, lido por conexão nova ──────────────────────
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
        C_G,
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
    erro_integridade_cls: type[BaseException],
) -> None:
    from sqlalchemy import text

    async def nova(
        nome: str, condicao: str, cabecalhos: dict[str, str]
    ) -> Cenario | None:
        c = Cenario(cliente, conexao, identidade)
        if not await c.nascer(nome, cabecalhos):
            relatorio.anotar(condicao, False, "a conta do cenário não nasceu")
            return None
        ids_criados.append(c.id_usuario)
        return c

    # ── (a) Corpo exato da 1.3.1 (sem co_resultado) ─────────────────────────
    ca = await nova("a", C_A, CABECALHOS_1_3_1)
    if ca:
        e1 = montar_evento_partida(placar=(3, 2), xp=20)
        e2 = montar_evento_partida(placar=(2, 3), xp=10)
        e3 = montar_evento_partida(placar=(2, 2), xp=15)
        e4 = montar_evento_partida(
            co_jogo="damas", co_variante="brasileira", placar=(5, 3), xp=25
        )
        await ca.enviar_eventos(CABECALHOS_1_3_1, e1, e2, e3, e4)
        est = await ca.estado(CABECALHOS_1_3_1)

        linhas_vw = (
            await conexao.execute(
                text(
                    "SELECT t.co_resultado, v.co_resultado, v.ic_resultado_informado "
                    "  FROM partida.tb001_partida t "
                    "  JOIN partida.vw001_partida v ON v.id_partida = t.id_partida "
                    " WHERE t.id_usuario = :u "
                    " ORDER BY t.nu_placar_j1, t.nu_placar_j2"
                ),
                {"u": ca.id_usuario},
            )
        ).all()

        relatorio.anotar(
            C_A,
            est["nu_partidas"] == 4
            and est["nu_vitorias"] == 2
            and est["nu_derrotas"] == 1
            and est["nu_empates"] == 1
            and est["nu_xp_total"] == 70
            and est["vitorias_por_jogo"] == {"pontinhos": 1, "damas": 1},
            f"estado 1.3.1: partidas={est['nu_partidas']} V={est['nu_vitorias']} "
            f"D={est['nu_derrotas']} E={est['nu_empates']} XP={est['nu_xp_total']} "
            f"vitorias_por_jogo={est['vitorias_por_jogo']}",
        )
        relatorio.anotar(
            C_A,
            all(l[0] is None and l[2] is False for l in linhas_vw)
            and sorted(l[1] for l in linhas_vw)
            == ["empate", "venceu_j1", "venceu_j1", "venceu_j2"],
            f"tb001 vs vw001 nas 4 linhas da 1.3.1: {[tuple(l) for l in linhas_vw]}",
        )

    # ── (b) Corpo novo 1.4.0: empate de damas 5x3 + reconciliação 200 ───────
    cb = await nova("b", C_B, CABECALHOS_1_4_0)
    if cb:
        ev_damas = montar_evento_partida(
            co_jogo="damas",
            co_variante="brasileira",
            placar=(5, 3),
            xp=25,
            incluir_resultado=True,
            co_resultado="empate",
        )
        await cb.enviar_eventos(CABECALHOS_1_4_0, ev_damas)
        est = await cb.estado(CABECALHOS_1_4_0)
        rec = await cb.reconciliar(
            CABECALHOS_1_4_0, retrato_progressao(25, 1, 0, 0, 1)
        )
        linha = (
            await conexao.execute(
                text(
                    "SELECT t.co_resultado, v.co_resultado, v.ic_resultado_informado "
                    "  FROM partida.tb001_partida t "
                    "  JOIN partida.vw001_partida v ON v.id_partida = t.id_partida "
                    " WHERE t.id_usuario = :u"
                ),
                {"u": cb.id_usuario},
            )
        ).one()
        relatorio.anotar(
            C_B,
            est["nu_partidas"] == 1
            and est["nu_vitorias"] == 0
            and est["nu_derrotas"] == 0
            and est["nu_empates"] == 1
            and est["vitorias_por_jogo"] == {}
            and rec.status_code == 200,
            f"damas 5x3 + empate: V={est['nu_vitorias']} E={est['nu_empates']} "
            f"vitorias_por_jogo={est['vitorias_por_jogo']} reconciliar={rec.status_code}",
        )
        relatorio.anotar(
            C_B,
            tuple(linha) == ("empate", "empate", True),
            f"tb001/vw001: {tuple(linha)}",
        )

    # ── (c) Valor inválido sanitizado + prova de que o CHECK está ativo ─────
    cc = await nova("c", C_C, CABECALHOS_1_4_0)
    if cc:
        ev_ruim = montar_evento_partida(
            placar=(2, 5),
            xp=12,
            incluir_resultado=True,
            co_resultado="FORA_DO_CHECK",
        )
        resp = await cc.enviar_eventos(CABECALHOS_1_4_0, ev_ruim)
        est = await cc.estado(CABECALHOS_1_4_0)
        linha = (
            await conexao.execute(
                text(
                    "SELECT t.co_resultado, v.co_resultado, v.ic_resultado_informado "
                    "  FROM partida.tb001_partida t "
                    "  JOIN partida.vw001_partida v ON v.id_partida = t.id_partida "
                    " WHERE t.id_usuario = :u"
                ),
                {"u": cc.id_usuario},
            )
        ).one()

        # Prova direta de que ck_partida_resultado está ativo no Postgres: um
        # UPDATE cru com valor de <= 10 caracteres (para caber em VARCHAR(10)
        # e bater na constraint CHECK, não no tamanho) dentro de um savepoint
        # precisa falhar com `ck_partida_resultado`.
        check_barrou = False
        sp = await conexao.begin_nested()
        try:
            await conexao.execute(
                text(
                    "UPDATE partida.tb001_partida "
                    "   SET co_resultado = 'invalido' "
                    " WHERE id_usuario = :u"
                ),
                {"u": cc.id_usuario},
            )
            await sp.rollback()
        except erro_integridade_cls as exc:
            check_barrou = "ck_partida_resultado" in str(exc)
            await sp.rollback()

        relatorio.anotar(
            C_C,
            len(resp["aceitos"]) == 1
            and resp["rejeitados"] == []
            and resp["falhas"] == []
            and est["nu_derrotas"] == 1
            and tuple(linha) == (None, "venceu_j2", False)
            and check_barrou,
            f"aceitos={len(resp['aceitos'])} falhas={resp['falhas']} "
            f"tb001/vw001={tuple(linha)} ck_ativo={check_barrou}",
        )

    # ── (d) Duas levas (`em_andamento` -> `concluida`) + reenvio antigo ─────
    cd = await nova("d", C_D, CABECALHOS_1_4_0)
    if cd:
        co_ev = str(uuid.uuid4())
        id_p = str(uuid.uuid4())
        leva_1 = montar_evento_partida(
            co_evento=co_ev,
            id_partida=id_p,
            co_jogo="damas",
            co_variante="brasileira",
            co_modo="desafio",
            ic_pontua=False,
            co_status="em_andamento",
            placar=(2, 1),
            xp=0,
        )
        await cd.enviar_eventos(CABECALHOS_1_4_0, leva_1)
        antes = (
            await conexao.execute(
                text(
                    "SELECT t.co_status, t.co_resultado, v.ic_resultado_informado "
                    "  FROM partida.tb001_partida t "
                    "  JOIN partida.vw001_partida v ON v.id_partida = t.id_partida "
                    " WHERE t.id_partida = :p"
                ),
                {"p": id_p},
            )
        ).one()

        leva_2 = montar_evento_partida(
            co_evento=co_ev,
            id_partida=id_p,
            co_jogo="damas",
            co_variante="brasileira",
            co_modo="desafio",
            ic_pontua=False,
            co_status="concluida",
            placar=(5, 3),
            xp=0,
            incluir_resultado=True,
            co_resultado="empate",
        )
        await cd.enviar_eventos(CABECALHOS_1_4_0, leva_2)

        # Reenvio atrasado da leva 1 não pode reabrir nem apagar o resultado.
        reenvio = montar_evento_partida(
            co_evento=co_ev,
            id_partida=id_p,
            co_jogo="damas",
            co_variante="brasileira",
            co_modo="desafio",
            ic_pontua=False,
            co_status="em_andamento",
            placar=(6, 1),
            xp=0,
            incluir_resultado=True,
            co_resultado="venceu_j1",
        )
        resp_reenvio = await cd.enviar_eventos(CABECALHOS_1_4_0, reenvio)
        depois = (
            await conexao.execute(
                text(
                    "SELECT t.co_status, t.co_resultado, v.co_resultado, v.ic_resultado_informado "
                    "  FROM partida.tb001_partida t "
                    "  JOIN partida.vw001_partida v ON v.id_partida = t.id_partida "
                    " WHERE t.id_partida = :p"
                ),
                {"p": id_p},
            )
        ).one()
        relatorio.anotar(
            C_D,
            tuple(antes) == ("em_andamento", None, False)
            and tuple(depois) == ("concluida", "empate", "empate", True)
            and len(resp_reenvio["ignorados"]) == 1,
            f"leva 1={tuple(antes)} -> leva 2={tuple(depois)} "
            f"(reenvio ignorados={len(resp_reenvio['ignorados'])})",
        )

    # ── (e) vitorias_por_jogo com mistura 1.3.1 + 1.4.0 ─────────────────────
    ce = await nova("e", C_E, CABECALHOS_1_4_0)
    if ce:
        await ce.enviar_eventos(
            CABECALHOS_1_4_0,
            montar_evento_partida(co_jogo="pontinhos", placar=(3, 1)),
            montar_evento_partida(co_jogo="pontinhos", placar=(4, 2)),
            montar_evento_partida(
                co_jogo="damas",
                co_variante="brasileira",
                placar=(5, 3),
                incluir_resultado=True,
                co_resultado="empate",
            ),
            montar_evento_partida(
                co_jogo="damas",
                co_variante="brasileira",
                placar=(2, 4),
                incluir_resultado=True,
                co_resultado="venceu_j1",
            ),
            montar_evento_partida(
                co_jogo="quatro",
                co_variante="tradicional",
                placar=(1, 0),
                incluir_resultado=True,
                co_resultado="venceu_j1",
            ),
            montar_evento_partida(
                co_jogo="quatro",
                co_variante="tradicional",
                co_modo="pvp_local",
                ic_pontua=False,
                placar=(1, 0),
                xp=0,
                incluir_resultado=True,
                co_resultado="venceu_j1",
            ),
        )
        est = await ce.estado(CABECALHOS_1_4_0)
        relatorio.anotar(
            C_E,
            est["vitorias_por_jogo"]
            == {"pontinhos": 2, "damas": 1, "quatro": 1},
            f"vitorias_por_jogo={est['vitorias_por_jogo']} "
            "(esperado pontinhos=2, damas=1, quatro=1)",
        )

    # ── (f) Controle: sem co_resultado, damas 5x3 conta vitória ─────────────
    cf = await nova("f", C_F, CABECALHOS_1_3_1)
    if cf:
        await cf.enviar_eventos(
            CABECALHOS_1_3_1,
            montar_evento_partida(
                co_jogo="damas",
                co_variante="brasileira",
                placar=(5, 3),
                xp=25,
                incluir_resultado=False,
            ),
        )
        est = await cf.estado(CABECALHOS_1_3_1)
        # Se a regra antiga estivesse valendo para (b), teria dado V=1 e não E=1.
        reprovaria_empate = (
            est["nu_vitorias"] == 1
            and est["nu_empates"] == 0
            and est["vitorias_por_jogo"] == {"damas": 1}
        )
        relatorio.anotar(
            C_F,
            reprovaria_empate,
            f"controle sem co_resultado em damas 5x3: V={est['nu_vitorias']} "
            f"E={est['nu_empates']} vitorias_por_jogo={est['vitorias_por_jogo']}",
        )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(conferir()))

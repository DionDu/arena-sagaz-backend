"""O BÔNUS DAS CONQUISTAS PELO SERVIDOR (T167) - medido contra o `des`, sem deixar rastro.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT PROVA, E POR QUE SÓ O BANCO RESPONDE
═══════════════════════════════════════════════════════════════════════════

Desde a T167 da spec 010 (30/10/2026) o servidor credita o bônus de TODA
conquista ao inseri-la (o evento `conquista` e o merge do convidado), e ⛔ nunca
na reconciliação (`api/sincronizacao/bonus_das_conquistas.py`). "Uma vez só"
depende do `xmax = 0`, do `ON CONFLICT` e do `RETURNING` do Postgres, que os
testes de unidade (`tests/unitarios/test_bonus_das_conquistas.py`) só imitam.
Aqui o aplicativo de verdade fala com o `des`, com os corpos que a **1.3.1 das
lojas** manda, e o total da conta é lido de volta a cada passo:

  (a) evento antes da reconciliação - a conta saudável não recebe em dobro;
  (b) reconciliação antes do evento - o evento atrasado não paga de novo;
  (c) o reenvio e o segundo aparelho pagam uma vez só;
  (d) a conta das 9 (reconciliação recusada): o bônus chega pelo evento, e a
      recusa fica no log (a T166 provada no Postgres);
  (e) o merge do convidado paga só o que a conta não tinha, e o retry do lote
      e os eventos do convidado que sobem depois não pagam de novo;
  (f) o código que o servidor não conhece grava e não paga;
  (g) nada ficou no `des`.

⚠️ **O que a T167 promete a quem NÃO atualizar** (`docs/DECISOES-do-dono.md`
§8zzzz10 do app): nada fica pior. Os casos (a), (b) e (c) são o app antigo que
já funcionava: o total do servidor tem de terminar IGUAL ao do aparelho.

═══════════════════════════════════════════════════════════════════════════
⛔ E NÃO DEIXA NADA NO `des`
═══════════════════════════════════════════════════════════════════════════

O molde é `conferir_merge_convidado_t079a.py`: tudo roda numa transação única,
desfeita com `ROLLBACK` no fim. A sessão de cada requisição nasce com
`join_transaction_mode="create_savepoint"`, e o `commit` da rota só fecha um
savepoint. A última condição confere, por uma CONEXÃO NOVA, que nenhuma das
contas criadas existe mais. ⚠️ Só a verificação do token do Firebase é
substituída; o dono de cada requisição continua resolvido no banco.

⛔ **Só no `des`**: a URL vem de `DATABASE_URL_DES` e `identificar_banco.py`
confere host e porta antes de abrir a transação. Nunca imprime a URL.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\conferir_bonus_das_conquistas_t167.py

Leva de 2 a 3 minutos (medido em 30/10/2026): são cerca de 40 requisições, e
cada uma vai e volta ao Postgres do Railway em 2 a 4 s. Saída: um relatório por
condição, com os números de onde cada veredito saiu; código 0 só quando todas
fecham. Olhe primeiro as linhas com ⛔ e a condição (g).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# `parents[1]` é a raiz do backend: é dela que `api` e `scripts` são importáveis.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

# ⚠️ O console do Windows é cp1252; sem isto, o primeiro emoji derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from scripts.conferir_portao_t050 import Relatorio, url_do_des  # noqa: E402
from scripts.identificar_banco import _nomear_ambiente  # noqa: E402

#: Os cabeçalhos de um aparelho com a 1.3.1 das lojas - a versão que NÃO pode
#: ficar pior (§8zzzz10).
CABECALHOS_1_3_1 = {
    "X-App-Version": "1.3.1",
    "X-Platform": "ios",
    "Accept-Language": "pt-BR",
}

#: O prefixo de todo uid criado aqui: é por ele que (g) procura o que sobrou.
PREFIXO_UID = "t167-"

C_A = "(a) evento antes da reconciliação: a conta saudável não recebe em dobro"
C_B = "(b) reconciliação antes do evento: o evento atrasado não paga de novo"
C_C = "(c) o reenvio e o segundo aparelho pagam uma vez só"
C_D = "(d) a conta das 9: o bônus chega pelo evento, e a recusa fica no log"
C_E = "(e) o merge do convidado paga só o que a conta não tinha"
C_F = "(f) o código que o servidor não conhece grava e não paga"
C_G = "(g) nada ficou no `des`"


# ═══════════════════════════════════════════════════════════════════════════
# Os corpos, como a 1.3.1 os monta
# ═══════════════════════════════════════════════════════════════════════════


def evento_de_partida(xp: int, *, placar: tuple[int, int] = (3, 2)) -> dict[str, Any]:
    """Uma partida de Pontinhos contra a CPU que PONTUA, no formato de
    `ServicoLogPartida._montarPayload` (o `co_evento` e o `id_partida` são UUID,
    como as colunas). Sem jogadas: o crédito do bônus não depende delas."""
    agora = datetime.now(timezone.utc)
    return {
        "co_evento": str(uuid.uuid4()),
        "co_tipo": "partida",
        "payload": {
            "partida": {
                "id_partida": str(uuid.uuid4()),
                "co_jogo": "pontinhos",
                "co_variante": "pequeno",
                "co_modo": "vs_cpu",
                "co_dificuldade": "facil",
                "nu_placar_j1": placar[0],
                "nu_placar_j2": placar[1],
                "ic_pontua": True,
                "co_status": "concluida",
                "co_lote_migracao": None,
                "dh_inicio": (agora - timedelta(minutes=3)).isoformat(),
                "dh_fim": agora.isoformat(),
                "nu_offset_minuto_j1": -180,
                "nu_offset_minuto_j2": None,
            },
            "jogadas": [],
            "xp": [{"co_tipo_xp": "resultado", "nu_xp": xp, "co_referencia": None}],
        },
    }


def evento_de_conquista(co_conquista: str, co_evento: str | None = None) -> dict[str, Any]:
    """O evento de conquista de `ServicoLogPartida.registrarConquista`."""
    return {
        "co_evento": co_evento or str(uuid.uuid4()),
        "co_tipo": "conquista",
        "payload": {
            "conquista": {
                "co_conquista": co_conquista,
                "dh_desbloqueio": datetime.now(timezone.utc).isoformat(),
            }
        },
    }


def retrato(xp: int, partidas: int, v: int, d: int, e: int,
            conquistas: list[str]) -> dict[str, Any]:
    """O corpo de `ServicoSync.reconciliarProgressao`."""
    return {
        "progressao": {
            "nu_xp_total": xp,
            "nu_partidas": partidas,
            "nu_vitorias": v,
            "nu_derrotas": d,
            "nu_empates": e,
            "nu_sequencia_atual": 1,
            "dt_ultimo_dia_jogado": datetime.now(timezone.utc).date().isoformat(),
            "conquistas": conquistas,
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
# A conferência
# ═══════════════════════════════════════════════════════════════════════════


class Cenario:
    """Uma conta nova por cenário, e os atalhos para falar com a API por ela."""

    def __init__(self, cliente, conexao, identidade: dict[str, str]) -> None:
        self.cliente = cliente
        self.conexao = conexao
        self._identidade = identidade
        self.id_usuario: Any = None

    async def nascer(self, nome: str) -> bool:
        """Cria a conta (`POST /v1/conta/sessao`, como no primeiro login)."""
        from sqlalchemy import text

        uid = f"{PREFIXO_UID}{nome}-{uuid.uuid4()}"
        self._identidade["uid"] = uid
        r = await self.cliente.post(
            "/v1/conta/sessao",
            json={
                "no_exibicao": f"T167 {nome}",
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

    async def eventos(self, *eventos: dict[str, Any]) -> dict[str, Any]:
        r = await self.cliente.post(
            "/v1/sincronizacao/eventos", json={"eventos": list(eventos)}
        )
        assert r.status_code == 200, r.text[:300]
        return r.json()

    async def reconciliar(self, corpo: dict[str, Any]):
        return await self.cliente.post("/v1/sincronizacao/reconciliar", json=corpo)

    async def merge(self, lote: str, conquistas: list[str]):
        # O corpo de `ServicoSync.mergeConvidado`: contadores em zero, de
        # propósito (sobem pelos eventos).
        return await self.cliente.post(
            "/v1/sincronizacao/merge-convidado",
            json={
                "co_lote_migracao": lote,
                "progressao_convidado": {
                    "nu_xp_total": 0, "nu_partidas": 0, "nu_vitorias": 0,
                    "nu_derrotas": 0, "nu_empates": 0, "nu_sequencia_atual": 3,
                    "conquistas": conquistas,
                },
            },
        )

    async def total(self) -> int:
        """O XP da conta como o ranking o lê (`GET /estado`)."""
        r = await self.cliente.get("/v1/sincronizacao/estado")
        assert r.status_code == 200, r.text[:300]
        return int(r.json()["progressao"].get("nu_xp_total") or 0)

    async def conquistas(self) -> list[str]:
        r = await self.cliente.get("/v1/sincronizacao/estado")
        return sorted(r.json()["progressao"].get("conquistas") or [])


async def conferir() -> int:
    """Roda as sete condições e devolve o código de saída."""
    url = url_do_des()
    ambiente, explicacao = _nomear_ambiente(url)
    if ambiente != "DES":
        raise SystemExit(f"⛔ o banco não é o `des` ({ambiente}: {explicacao}).")
    print(f"banco: DES ({explicacao})")

    # ⚠️ A URL tem de estar no ambiente ANTES de `api.main` ser importado: o motor
    # do SQLAlchemy nasce no import de `api.nucleo.banco`, lendo-a uma vez só.
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
    # O uid "logado" no momento; cada cenário troca ao criar a conta dele.
    identidade = {"uid": ""}
    ids_criados: list[Any] = []

    async with motor.connect() as conexao:
        transacao = await conexao.begin()

        async def sessao_dentro_da_transacao():
            """A sessão de cada requisição, presa à transação do script: o
            `commit()` da rota só libera um savepoint."""
            async with AsyncSession(
                bind=conexao,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            ) as sessao:
                yield sessao

        def identidade_do_script() -> IdentidadeFirebase:
            return IdentidadeFirebase(
                uid=identidade["uid"], provedor="google.com", nome="T167"
            )

        app.dependency_overrides[obter_sessao] = sessao_dentro_da_transacao
        app.dependency_overrides[usuario_atual] = identidade_do_script
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://t167",
                headers={**CABECALHOS_1_3_1, "Authorization": "Bearer t167"},
            ) as cliente:
                await _cenarios(cliente, conexao, identidade, relatorio, ids_criados)
        finally:
            app.dependency_overrides.pop(obter_sessao, None)
            app.dependency_overrides.pop(usuario_atual, None)
            await transacao.rollback()

    # ── (g) Nada ficou - por uma CONEXÃO NOVA ──────────────────────────────
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
        logs = 0
        if ids_criados:
            logs = (
                await outra.execute(
                    text(
                        "SELECT count(*) FROM log.tb001_evento_sync_rejeitado "
                        " WHERE id_usuario = ANY(:ids)"
                    ),
                    {"ids": ids_criados},
                )
            ).scalar_one()
    relatorio.anotar(
        C_G,
        contas == 0 and logs == 0,
        f"depois do ROLLBACK: {contas} conta(s) com uid `{PREFIXO_UID}...` e "
        f"{logs} linha(s) de log das {len(ids_criados)} contas do script",
    )

    await motor.dispose()
    return 0 if relatorio.imprimir() else 1


async def _cenarios(cliente, conexao, identidade, relatorio: Relatorio,
                    ids_criados: list[Any]) -> None:
    """Os cenários (a) a (f), cada um com a sua conta."""
    from sqlalchemy import text

    async def nova(nome: str, condicao: str) -> Cenario | None:
        c = Cenario(cliente, conexao, identidade)
        if not await c.nascer(nome):
            relatorio.anotar(condicao, False, "⛔ a conta do cenário não nasceu")
            return None
        ids_criados.append(c.id_usuario)
        return c

    # ── (a) Evento antes da reconciliação ───────────────────────────────────
    # O aparelho: vitória de 50 XP + `primeira_vitoria` (40) = 90 no total
    # local. Ele manda a partida e a conquista, e depois (fila vazia) reconcilia
    # com o total dele. O servidor tem de terminar em 90 - e não 130.
    c = await nova("a", C_A)
    if c:
        await c.eventos(evento_de_partida(50), evento_de_conquista("primeira_vitoria"))
        depois_dos_eventos = await c.total()
        r = await c.reconciliar(retrato(90, 1, 1, 0, 0, ["primeira_vitoria"]))
        final = await c.total()
        relatorio.anotar(
            C_A, depois_dos_eventos == 90,
            f"depois da partida (50) e da conquista (40): {depois_dos_eventos} (esperado 90)",
        )
        relatorio.anotar(
            C_A, r.status_code == 200 and final == 90,
            f"depois da reconciliação com o total do aparelho (90): {r.status_code}, "
            f"{final} (esperado 90; 130 seria o dobro)",
        )

    # ── (b) Reconciliação antes do evento ───────────────────────────────────
    # O evento da conquista atrasou (ex.: ficou na fila de um envio que caiu).
    # A reconciliação chega antes, insere a conquista pela união SEM crédito e
    # sobe o total pelo GREATEST. O evento que chega depois não pode pagar.
    c = await nova("b", C_B)
    if c:
        await c.eventos(evento_de_partida(50))
        r = await c.reconciliar(retrato(90, 1, 1, 0, 0, ["primeira_vitoria"]))
        depois_da_reconciliacao = await c.total()
        resposta = await c.eventos(evento_de_conquista("primeira_vitoria"))
        final = await c.total()
        relatorio.anotar(
            C_B, r.status_code == 200 and depois_da_reconciliacao == 90,
            f"partida (50) + reconciliação com 90: {r.status_code}, {depois_da_reconciliacao}",
        )
        relatorio.anotar(
            C_B, final == 90 and len(resposta["ignorados"]) == 1,
            f"o evento atrasado da conquista: ignorados={len(resposta['ignorados'])}, "
            f"total {final} (esperado 90; 130 seria o dobro)",
        )

    # ── (c) O reenvio e o segundo aparelho ──────────────────────────────────
    c = await nova("c", C_C)
    if c:
        co_evento = str(uuid.uuid4())
        await c.eventos(evento_de_conquista("sequencia_3", co_evento))
        primeiro = await c.total()
        # O mesmo evento de novo (o app reenvia quando a resposta se perde).
        await c.eventos(evento_de_conquista("sequencia_3", co_evento))
        reenvio = await c.total()
        # A mesma conquista desbloqueada noutro aparelho (outro `co_evento`).
        await c.eventos(evento_de_conquista("sequencia_3"))
        outro_aparelho = await c.total()
        relatorio.anotar(
            C_C, primeiro == 60,
            f"o 1º evento de `sequencia_3` (60) numa conta sem partida: {primeiro} "
            "(o crédito cria a linha de progressão)",
        )
        relatorio.anotar(
            C_C, reenvio == 60 and outro_aparelho == 60,
            f"o reenvio: {reenvio}; o segundo aparelho: {outro_aparelho} (esperado 60 nos dois)",
        )

    # ── (d) A conta das 9 ───────────────────────────────────────────────────
    # O aparelho tem a soma que não fecha (V + D + E > partidas), e a
    # reconciliação dele é recusada para sempre. Antes da T167 o bônus nunca
    # chegava; agora chega pelo evento, e a recusa deixa linha no log (T166).
    c = await nova("d", C_D)
    if c:
        await c.eventos(evento_de_partida(50), evento_de_conquista("sequencia_7"))
        depois_dos_eventos = await c.total()
        r = await c.reconciliar(retrato(170, 1, 1, 0, 1, ["sequencia_7"]))
        final = await c.total()
        linhas = (
            await conexao.execute(
                text(
                    "SELECT co_tipo, co_motivo, de_codigo FROM log.tb001_evento_sync_rejeitado "
                    " WHERE id_usuario = :u"
                ),
                {"u": c.id_usuario},
            )
        ).all()
        relatorio.anotar(
            C_D, depois_dos_eventos == 170,
            f"partida (50) + `sequencia_7` (120) pelo evento: {depois_dos_eventos} (esperado 170)",
        )
        relatorio.anotar(
            C_D,
            r.status_code == 422
            and r.json().get("codigo") == "progressao_inconsistente"
            and final == 170,
            f"a reconciliação inconsistente: {r.status_code} {r.json().get('codigo')}, total {final}",
        )
        relatorio.anotar(
            C_D,
            [tuple(l) for l in linhas]
            == [("reconciliacao", "rejeitado_contrato", "progressao_inconsistente")],
            f"o log da recusa, no Postgres: {[tuple(l) for l in linhas]}",
        )

    # ── (e) O merge do convidado ────────────────────────────────────────────
    # A conta já tem `nivel_5` (80, por evento). O convidado traz `nivel_5`,
    # `sequencia_3` (60) e `desafio_primeiro` (40): só as duas novas pagam.
    c = await nova("e", C_E)
    if c:
        await c.eventos(evento_de_conquista("nivel_5"))
        antes = await c.total()
        lote = str(uuid.uuid4())
        r = await c.merge(lote, ["nivel_5", "sequencia_3", "desafio_primeiro"])
        depois_do_merge = await c.total()
        r2 = await c.merge(lote, ["nivel_5", "sequencia_3", "desafio_primeiro"])
        depois_do_retry = await c.total()
        # A fila do convidado sobe depois do merge, com os eventos dele.
        await c.eventos(
            evento_de_conquista("sequencia_3"), evento_de_conquista("desafio_primeiro")
        )
        final = await c.total()
        relatorio.anotar(
            C_E, antes == 80 and r.status_code == 200 and depois_do_merge == 180,
            f"a conta com `nivel_5`: {antes}; depois do merge: {depois_do_merge} "
            "(esperado 80 + 60 + 40 = 180; `nivel_5` não paga de novo)",
        )
        relatorio.anotar(
            C_E,
            r2.status_code == 200 and r2.json().get("aplicado") is False
            and depois_do_retry == 180 and final == 180,
            f"o retry do lote (aplicado={r2.json().get('aplicado')}): {depois_do_retry}; "
            f"os eventos do convidado depois: {final} (esperado 180 nos dois)",
        )

    # ── (f) O código desconhecido ───────────────────────────────────────────
    c = await nova("f", C_F)
    if c:
        await c.eventos(evento_de_partida(50))
        resposta = await c.eventos(evento_de_conquista("xadrez_vitorias_1"))
        final = await c.total()
        tem = "xadrez_vitorias_1" in await c.conquistas()
        relatorio.anotar(
            C_F, len(resposta["aceitos"]) == 1 and tem and final == 50,
            f"aceitos={len(resposta['aceitos'])}, gravada={tem}, total {final} (esperado 50)",
        )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(conferir()))

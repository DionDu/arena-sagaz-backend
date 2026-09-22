"""O CREDITO DO DESAFIO NA CONTA (T082) — medido contra o `des`, sem deixar rastro.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT PROVA, E POR QUE SO O BANCO RESPONDE
═══════════════════════════════════════════════════════════════════════════

Ate 22/09/2026 a rota da resolucao gravava o extrato e ⛔ nunca somava nada em
`nu_xp_total`: o aplicativo mostrava *"+27 XP"* e o ranking nao mudava. E a chama
ignorava a partida de desafio, que ⛔ pontua (`ic_pontua = FALSE`). Os testes
unitarios provam a regra com um repositorio falso; o que so o Postgres responde
e se o SQL de verdade soma, le as VIEWs certas e cria a linha de quem nunca jogou
uma partida comum.

As condicoes, numa conta nova que ⛔ joga partida comum nenhuma:

  (a) a conta nasce, e ha dois dias com desafio resolvivel no `des`;
  (b) **a primeira falha paga 10**, e a segunda ⛔ paga nada (RF-DES-041);
  (c) **resolver depois de falhar fecha o dia em 30**: a resolucao guarda 27, o
      ajuste tira 7, a conta ganha 20 (RF-DES-047/181);
  (d) **o reenvio ⛔ credita de novo**;
  (e) **a ordem inversa fecha igual**: resolver antes e falhar depois da 27 + 3;
  (f) **a chama conta os dois dias de desafio** (RF-DES-048), numa conta sem
      partida que pontue - antes da T082 ela sairia zero;
  (g) nada ficou no `des`.

═══════════════════════════════════════════════════════════════════════════
⛔ E NAO DEIXA NADA NO `des`
═══════════════════════════════════════════════════════════════════════════

O mesmo desenho de `conferir_merge_convidado_t079a.py`: uma transacao do script,
as sessoes das rotas em *savepoint* dentro dela, e `ROLLBACK` no fim. Uma
conexao nova confere depois que a conta nao existe mais. ⛔ So o `des`, conferido
por `identificar_banco.py` antes de abrir a transacao, e ⛔ nunca imprime a URL.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\conferir_credito_do_dia_t082.py

Leva menos de um minuto. Saida: um relatorio por condicao, com o numero de onde
cada veredito saiu, e codigo de saida 0 so quando todas fecham.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# `parents[1]` e a raiz do backend: e dela que `api` e `scripts` sao importaveis.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

# ⚠️ O console do Windows e cp1252; sem isto, o primeiro emoji derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Reuso, e nao copia: o catalogo, a trava do ambiente, os corpos que o aparelho
# manda e a escolha de dias resolviveis sao os da T079a. Dois lugares para
# decidir "qual desafio da para resolver" acabariam discordando um dia.
from scripts.conferir_merge_convidado_t079a import (  # noqa: E402
    envio_de_resolucao,
    escolher_dias,
    evento_de_partida,
    instante_no_dia,
)
from scripts.conferir_portao_t050 import (  # noqa: E402
    CABECALHOS,
    Relatorio,
    url_do_des,
)
from scripts.identificar_banco import _nomear_ambiente  # noqa: E402

#: A pontuacao das resolucoes do script - a do exemplo do `data-model.md`.
PONTUACAO = 27

#: O fuso que `evento_de_partida` grava na partida (Brasil, UTC-3).
OFFSET_MINUTOS = -180

C_CONTA = "(a) a conta nasce, e ha dias para resolver"
C_CONSOLO = "(b) a primeira falha paga 10, a segunda nada"
C_TETO = "(c) falhar e depois resolver fecha o dia em 30"
C_REENVIO = "(d) o reenvio nao credita de novo"
C_ORDEM = "(e) a ordem inversa fecha nos mesmos 30"
C_CHAMA = "(f) a chama conta os dias de desafio"
C_RASTRO = "(g) nada ficou no `des`"


async def xp_da_conta(conexao, id_usuario: Any) -> int:
    """O `nu_xp_total` da conta, pela VIEW - zero quando ela ainda nao tem linha."""
    from sqlalchemy import text

    valor = (
        await conexao.execute(
            text(
                "SELECT nu_xp_total FROM progressao.vw001_progressao_usuario "
                " WHERE id_usuario = :u"
            ),
            {"u": id_usuario},
        )
    ).scalar()
    return int(valor or 0)


async def linhas_do_dia(conexao, id_usuario: Any, id_desafio_dia: Any) -> dict:
    """Quantas linhas de consolo, o ajuste somado e o `nu_xp` da resolucao."""
    from sqlalchemy import text

    linha = (
        (
            await conexao.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*) FROM desafio_dia.vw004_xp_desafio
                        WHERE id_usuario = :u AND id_desafio_dia = :d
                          AND co_tipo_xp = 'consolo') AS consolos,
                      (SELECT COALESCE(SUM(vr_xp), 0) FROM desafio_dia.vw004_xp_desafio
                        WHERE id_usuario = :u AND id_desafio_dia = :d
                          AND co_tipo_xp = 'ajuste') AS ajuste,
                      (SELECT nu_xp FROM desafio_dia.vw003_resolucao
                        WHERE id_usuario = :u AND id_desafio_dia = :d) AS nu_xp
                    """
                ),
                {"u": id_usuario, "d": id_desafio_dia},
            )
        )
        .mappings()
        .one()
    )
    return {
        "consolos": int(linha["consolos"]),
        "ajuste": int(linha["ajuste"]),
        "nu_xp": linha["nu_xp"],
    }


def falha(envio: dict[str, Any]) -> dict[str, Any]:
    """O mesmo corpo, como o aplicativo manda a tentativa que ⛔ resolveu."""
    return {
        **envio,
        "veredito": "tentativa",
        "nu_lance_cumpre_desafio": None,
        "pontuacao": 10,
    }


def dia_local(instante: datetime) -> date:
    """O dia do relogio de quem jogou - a mesma conta de `recalcular_chama`."""
    return (instante + timedelta(minutes=OFFSET_MINUTOS)).date()


async def conferir() -> int:
    """Roda as sete condicoes e devolve o codigo de saida."""
    url = url_do_des()
    ambiente, explicacao = _nomear_ambiente(url)
    if ambiente != "DES":
        raise SystemExit(f"⛔ o banco nao e o `des` ({ambiente}: {explicacao}).")
    print(f"banco: DES ({explicacao})")

    # ⚠️ Antes de `api.main`: o motor nasce no import, lendo a URL uma vez so.
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
    uid = f"t082-{uuid.uuid4()}"
    agora = datetime.now(timezone.utc)

    async with motor.connect() as conexao:
        transacao = await conexao.begin()

        async def sessao_dentro_da_transacao():
            """A sessao de cada requisicao, em savepoint na transacao do script."""
            async with AsyncSession(
                bind=conexao,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            ) as sessao:
                yield sessao

        app.dependency_overrides[obter_sessao] = sessao_dentro_da_transacao
        app.dependency_overrides[usuario_atual] = lambda: IdentidadeFirebase(
            uid=uid, provedor="google.com", nome="Conta T082"
        )
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://t082",
                headers=CABECALHOS,
            ) as cliente:
                await _creditar(cliente, conexao, relatorio, uid=uid, agora=agora)
        finally:
            app.dependency_overrides.pop(obter_sessao, None)
            app.dependency_overrides.pop(usuario_atual, None)
            await transacao.rollback()

    async with motor.connect() as outra:
        sobrou = (
            await outra.execute(
                text(
                    "SELECT count(*) FROM conta.vw001_usuario "
                    " WHERE co_identidade_externa = :uid"
                ),
                {"uid": uid},
            )
        ).scalar_one()
    relatorio.anotar(
        C_RASTRO,
        sobrou == 0,
        "depois do ROLLBACK a conta criada nao existe (0 linhas)"
        if sobrou == 0
        else f"⛔ a conta do script continua no `des` ({sobrou} linha)",
    )

    await motor.dispose()
    return 0 if relatorio.imprimir() else 1


async def _creditar(
    cliente, conexao, relatorio: Relatorio, *, uid: str, agora: datetime
) -> None:
    """As condicoes (a) a (f), numa conta que so joga o desafio."""
    from sqlalchemy import text

    # ── (a) ──────────────────────────────────────────────────────────────────
    r = await cliente.post(
        "/v1/conta/sessao",
        json={
            "no_exibicao": "Conta T082",
            "ic_idade_minima_declarada": True,
            "co_idioma_preferido": "pt",
        },
    )
    id_usuario = (
        await conexao.execute(
            text(
                "SELECT id_usuario FROM conta.vw001_usuario "
                " WHERE co_identidade_externa = :uid"
            ),
            {"uid": uid},
        )
    ).scalar()
    dias = await escolher_dias(conexao, agora.date())
    ok = r.status_code == 200 and id_usuario is not None and len(dias) >= 2
    relatorio.anotar(
        C_CONTA,
        ok,
        f"conta criada ({r.status_code}); {len(dias)} dias resolviveis, "
        f"usados os dois mais recentes"
        if ok
        else f"⛔ conta: {r.status_code}; dias resolviveis: {len(dias)}",
    )
    if not ok:
        return
    dia_a, dia_b = dias[0], dias[1]

    async def jogar(dia, *, resolveu: bool, minutos: int) -> tuple[dict, datetime]:
        """Sobe a partida de desafio pelo lote e devolve o corpo do envio dela."""
        inicio = instante_no_dia(dia["dt_dia"], agora) - timedelta(minutes=minutos)
        co_evento = str(uuid.uuid4())
        evento = evento_de_partida(
            co_evento=co_evento, dia=dia, lote=str(uuid.uuid4()), inicio=inicio
        )
        # Partida de conta, e ⛔ de convidado: sem lote.
        evento["payload"]["partida"]["co_lote_migracao"] = None
        await cliente.post("/v1/sincronizacao/eventos", json={"eventos": [evento]})
        envio = envio_de_resolucao(
            dia=dia,
            co_evento_partida=co_evento,
            pontuacao=PONTUACAO,
            resolvido_em=inicio + timedelta(minutes=2),
            origem={"tipo": "conta"},
        )
        return (envio if resolveu else falha(envio)), inicio + timedelta(minutes=2)

    async def enviar(dia, envio) -> int:
        """Manda o envio e devolve o status HTTP."""
        r = await cliente.post(f"/v1/desafios/{dia['id_desafio']}/resolucao", json=envio)
        return r.status_code

    instantes: list[datetime] = []

    # ── (b) O consolo, uma vez ───────────────────────────────────────────────
    xp_0 = await xp_da_conta(conexao, id_usuario)
    envio, quando = await jogar(dia_a, resolveu=False, minutos=50)
    instantes.append(quando)
    s1 = await enviar(dia_a, envio)
    xp_1 = await xp_da_conta(conexao, id_usuario)
    envio, quando = await jogar(dia_a, resolveu=False, minutos=40)
    instantes.append(quando)
    s2 = await enviar(dia_a, envio)
    xp_2 = await xp_da_conta(conexao, id_usuario)
    linhas = await linhas_do_dia(conexao, id_usuario, dia_a["id_desafio_dia"])
    ok = (
        (s1, s2) == (200, 200)
        and (xp_0, xp_1, xp_2) == (0, 10, 10)
        and linhas["consolos"] == 1
    )
    relatorio.anotar(
        C_CONSOLO,
        ok,
        f"{dia_a['dt_dia']}: nu_xp_total {xp_0} → {xp_1} → {xp_2}, "
        f"{linhas['consolos']} linha de consolo - a conta NASCEU no credito"
        if ok
        else f"⛔ status {s1}/{s2}, xp {xp_0}/{xp_1}/{xp_2}, linhas {linhas}",
    )

    # ── (c) Resolver depois de falhar ────────────────────────────────────────
    envio_resolvido, quando = await jogar(dia_a, resolveu=True, minutos=30)
    instantes.append(quando)
    s3 = await enviar(dia_a, envio_resolvido)
    xp_3 = await xp_da_conta(conexao, id_usuario)
    linhas = await linhas_do_dia(conexao, id_usuario, dia_a["id_desafio_dia"])
    ok = (
        s3 == 200
        and xp_3 == 30
        and linhas["nu_xp"] == PONTUACAO
        and linhas["ajuste"] == -7
    )
    relatorio.anotar(
        C_TETO,
        ok,
        f"a resolucao guardou {linhas['nu_xp']}, o ajuste somou {linhas['ajuste']}, "
        f"e a conta foi a {xp_3}: 10 + 27 - 7"
        if ok
        else f"⛔ status {s3}, xp {xp_3}, linhas {linhas}",
    )

    # ── (d) O reenvio ────────────────────────────────────────────────────────
    s4 = await enviar(dia_a, envio_resolvido)
    s5 = await enviar(dia_a, falha(envio_resolvido))
    xp_4 = await xp_da_conta(conexao, id_usuario)
    ok = s4 == 200 and xp_4 == xp_3
    relatorio.anotar(
        C_REENVIO,
        ok,
        f"resolucao reenviada ({s4}) e falha reenviada ({s5}): a conta ficou em {xp_4}"
        if ok
        else f"⛔ o reenvio mudou a conta: {xp_3} → {xp_4} ({s4}/{s5})",
    )

    # ── (e) A ordem inversa ──────────────────────────────────────────────────
    envio, quando = await jogar(dia_b, resolveu=True, minutos=30)
    instantes.append(quando)
    s6 = await enviar(dia_b, envio)
    xp_5 = await xp_da_conta(conexao, id_usuario)
    envio, quando = await jogar(dia_b, resolveu=False, minutos=20)
    instantes.append(quando)
    s7 = await enviar(dia_b, envio)
    xp_6 = await xp_da_conta(conexao, id_usuario)
    linhas = await linhas_do_dia(conexao, id_usuario, dia_b["id_desafio_dia"])
    ok = (
        (s6, s7) == (200, 200)
        and (xp_5 - xp_4, xp_6 - xp_5) == (27, 3)
        and linhas["ajuste"] == -7
    )
    relatorio.anotar(
        C_ORDEM,
        ok,
        f"{dia_b['dt_dia']}: +{xp_5 - xp_4} pela resolucao, +{xp_6 - xp_5} pelo "
        f"consolo, ajuste {linhas['ajuste']} - o dia fechou em 30"
        if ok
        else f"⛔ status {s6}/{s7}, ganhos {xp_5 - xp_4}/{xp_6 - xp_5}, {linhas}",
    )

    # ── (f) A chama ──────────────────────────────────────────────────────────
    #
    # ⚠️ Pela rota, e ⛔ chamando o repositorio: e o `GET /estado` que o
    # aplicativo le, e e nele que a chama e recalculada.
    r = await cliente.get("/v1/sincronizacao/estado")
    prog = r.json().get("progressao", {}) if r.status_code == 200 else {}
    esperados = {dia_local(i) for i in instantes}
    ultimo = str(max(esperados))
    ok = (
        prog.get("nu_dias_jogados") == len(esperados)
        and str(prog.get("dt_ultimo_dia_jogado")) == ultimo
        and prog.get("nu_partidas") == 0
    )
    relatorio.anotar(
        C_CHAMA,
        ok,
        f"{prog.get('nu_dias_jogados')} dias jogados, ultimo {ultimo}, chama "
        f"{prog.get('nu_sequencia_atual')} - com ZERO partidas que pontuam"
        if ok
        else f"⛔ esperava {len(esperados)} dias ate {ultimo}: {r.status_code} {prog}",
    )


def main() -> int:
    """Ponto de entrada."""
    return asyncio.run(conferir())


if __name__ == "__main__":
    raise SystemExit(main())

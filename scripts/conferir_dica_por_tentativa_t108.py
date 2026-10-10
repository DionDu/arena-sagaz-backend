"""A DICA QUE O APP ENVIA E O TETO POR TENTATIVA (T108) - medido contra o `des`.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT PROVA, E POR QUE SO O BANCO RESPONDE
═══════════════════════════════════════════════════════════════════════════

Em 10/10/2026 a `desafio_dia.tb005_poder_consumido` tinha ZERO linhas no `prd`,
com quatro dicas gastas em partidas de desafio (`DECISOES-do-dono.md` §8zzo). O
app 1.3.0 mandava cada dica com o `co_evento` da partida, e esse `co_evento` so
nascia na 1a leva da gravacao: o envio desistia em silencio.

⚠️ **O dono decidiu que a `tb005` e preenchida pelo APP**, como o desenho
original previa (10/10/2026): *"o App joga o dado para sincronizacao com o
servidor"*. ⛔ O servidor nao reconstroi dica a partir de `qt_usos_poder`. O
conserto do app (T109) e criar o `co_evento` no INICIO da partida; o que o
servidor precisa fazer, ele ja fazia - e este script prova, contra o Postgres de
verdade, a sequencia que o app 1.3.1 vai produzir:

  (a) a conta nasce, e ha um dia com desafio resolvivel no `des`;
  (b) **a dica que chega ANTES da partida recebe 409** - e o app reenvia;
  (c) **depois da 1a leva, a mesma dica entra** (204) e vira a linha de grau 1;
  (d) **a 2a da tentativa entra** (grau 2);
  (e) **a 3a na MESMA tentativa e recusada** (409 `teto_de_dicas`, T108);
  (f) **a resolucao dessa partida nao duplica nada** na `tb005`;
  (g) **uma tentativa NOVA recomeca com as duas**, com o dia ja em 2;
  (h) **o `meu-dia` devolve o total do dia** (3), que e o que vai para a nota;
  (i) nada ficou no `des`.

═══════════════════════════════════════════════════════════════════════════
⛔ E NAO DEIXA NADA NO `des`
═══════════════════════════════════════════════════════════════════════════

O desenho de `conferir_credito_do_dia_t082.py`: uma transacao do script, as
sessoes das rotas em *savepoint* dentro dela, e `ROLLBACK` no fim. Uma conexao
nova confere depois que a conta nao existe mais. ⛔ So o `des`, conferido por
`identificar_banco.py` antes de abrir a transacao, e ⛔ nunca imprime a URL.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\conferir_dica_por_tentativa_t108.py

Leva menos de um minuto. Saida: um relatorio por condicao, com o numero de onde
cada veredito saiu, e codigo de saida 0 so quando todas fecham.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# `parents[1]` e a raiz do backend: e dela que `api` e `scripts` sao importaveis.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

# ⚠️ O console do Windows e cp1252; sem isto, o primeiro emoji derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Reuso, e nao copia: os corpos que o aparelho manda e a escolha de dias
# resolviveis sao os da T079a; a trava do ambiente e o relatorio, os do T050.
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

C_CONTA = "(a) a conta nasce, e ha um dia para resolver"
C_ANTES = "(b) a dica que chega ANTES da partida recebe 409"
C_DEPOIS = "(c) depois da 1a leva, a mesma dica entra (grau 1)"
C_SEGUNDA = "(d) a 2a da tentativa entra (grau 2)"
C_TETO = "(e) a 3a na MESMA tentativa e recusada"
C_RESOLUCAO = "(f) a resolucao nao duplica as linhas"
C_NOVA = "(g) a tentativa NOVA recomeca com as duas"
C_MEU_DIA = "(h) o meu-dia devolve o total do dia"
C_RASTRO = "(i) nada ficou no `des`"

#: As linhas da `tb005` da conta, por partida, pela VIEW.
#:
#: ⚠️ `array_agg(... ORDER BY ...)` junta os graus de cada tentativa numa lista
#: ordenada (`{1,2}`), para o relatorio mostrar exatamente o que foi gravado.
SQL_DICAS_DA_CONTA = """
SELECT t.id_partida, array_agg(p.nu_grau ORDER BY p.nu_grau) AS graus
  FROM desafio_dia.vw005_poder_consumido p
  JOIN desafio_dia.vw002_tentativa t ON t.id_tentativa = p.id_tentativa
 WHERE t.id_usuario = :u
   AND p.co_tipo_poder = 'dica'
 GROUP BY t.id_partida
"""


async def dicas_por_partida(conexao, id_usuario: Any) -> dict[str, list[int]]:
    """`{id_partida: [graus]}` das dicas da conta na `tb005`."""
    from sqlalchemy import text

    linhas = (
        await conexao.execute(text(SQL_DICAS_DA_CONTA), {"u": id_usuario})
    ).mappings().all()
    return {str(l["id_partida"]): list(l["graus"]) for l in linhas}


async def conferir() -> int:
    """Roda as nove condicoes e devolve o codigo de saida."""
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
    uid = f"t108-{uuid.uuid4()}"
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
            uid=uid, provedor="google.com", nome="Conta T108"
        )
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://t108",
                headers=CABECALHOS,
            ) as cliente:
                await _dicas(cliente, conexao, relatorio, uid=uid, agora=agora)
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


async def _dicas(
    cliente, conexao, relatorio: Relatorio, *, uid: str, agora: datetime
) -> None:
    """As condicoes (a) a (h), numa conta que so joga o desafio."""
    from sqlalchemy import text

    # ── (a) ──────────────────────────────────────────────────────────────────
    r = await cliente.post(
        "/v1/conta/sessao",
        json={
            "no_exibicao": "Conta T108",
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
    ok = r.status_code == 200 and id_usuario is not None and len(dias) >= 1
    relatorio.anotar(
        C_CONTA,
        ok,
        f"conta criada ({r.status_code}); {len(dias)} dias resolviveis, usado o "
        "mais recente"
        if ok
        else f"⛔ conta: {r.status_code}; dias resolviveis: {len(dias)}",
    )
    if not ok:
        return
    dia = dias[0]

    def nova_partida(*, minutos: int) -> tuple[dict[str, Any], datetime]:
        """O evento da 1a leva de uma partida de desafio, ainda sem subir.

        ⚠️ O `co_evento` nasce AQUI, antes de qualquer envio - e o que o app
        1.3.1 passa a fazer no inicio da partida (T109).
        """
        inicio = instante_no_dia(dia["dt_dia"], agora) - timedelta(minutes=minutos)
        evento = evento_de_partida(
            co_evento=str(uuid.uuid4()),
            dia=dia,
            lote=str(uuid.uuid4()),
            inicio=inicio,
        )
        partida = evento["payload"]["partida"]
        # Partida de conta, e nao de convidado: sem lote. E a 1a leva de uma
        # partida que ainda corre: sem fim.
        partida["co_lote_migracao"] = None
        partida["co_status"] = "em_andamento"
        partida["dh_fim"] = None
        return evento, inicio

    async def subir(evento: dict[str, Any]) -> None:
        """Sobe a leva pela sincronizacao, como o outbox."""
        await cliente.post("/v1/sincronizacao/eventos", json={"eventos": [evento]})

    async def dica(co_evento: str, grau: int) -> tuple[int, Any]:
        """Manda a dica e devolve `(status, codigo de erro ou None)`."""
        r = await cliente.post(
            f"/v1/desafios/{dia['id_desafio']}/dica",
            json={
                "id_desafio_dia": str(dia["id_desafio_dia"]),
                "co_evento_partida": co_evento,
                "grau": grau,
                "consumida_em": agora.isoformat(),
            },
        )
        return r.status_code, (r.json().get("codigo") if r.status_code != 204 else None)

    # ── (b) a dica antes da partida ──────────────────────────────────────────
    evento, inicio = nova_partida(minutos=30)
    co_evento = evento["co_evento"]
    id_partida = evento["payload"]["partida"]["id_partida"]
    status, codigo = await dica(co_evento, 1)
    relatorio.anotar(
        C_ANTES,
        status == 409 and codigo == "partida_ainda_nao_chegou",
        f"status {status}, codigo {codigo!r} - o outbox do app reenvia",
    )

    # ── (c) a mesma dica depois da 1a leva ───────────────────────────────────
    await subir(evento)
    status, _ = await dica(co_evento, 1)
    graus = await dicas_por_partida(conexao, id_usuario)
    relatorio.anotar(
        C_DEPOIS,
        status == 204 and graus.get(id_partida) == [1],
        f"status {status}; graus na tentativa: {graus.get(id_partida)}",
    )

    # ── (d) a 2a ─────────────────────────────────────────────────────────────
    status, _ = await dica(co_evento, 2)
    graus = await dicas_por_partida(conexao, id_usuario)
    relatorio.anotar(
        C_SEGUNDA,
        status == 204 and graus.get(id_partida) == [1, 2],
        f"status {status}; graus na tentativa: {graus.get(id_partida)}",
    )

    # ── (e) a 3a na mesma tentativa ──────────────────────────────────────────
    status, codigo = await dica(co_evento, 2)
    relatorio.anotar(
        C_TETO,
        status == 409 and codigo == "teto_de_dicas",
        f"status {status}, codigo {codigo!r}",
    )

    # ── (f) a resolucao dessa partida ────────────────────────────────────────
    envio = envio_de_resolucao(
        dia=dia,
        co_evento_partida=co_evento,
        pontuacao=20,
        resolvido_em=inicio + timedelta(minutes=2),
        origem={"tipo": "conta"},
    )
    envio["dicas_usadas"] = 2
    r = await cliente.post(f"/v1/desafios/{dia['id_desafio']}/resolucao", json=envio)
    depois = await dicas_por_partida(conexao, id_usuario)
    relatorio.anotar(
        C_RESOLUCAO,
        r.status_code == 200 and depois == graus,
        f"resolucao {r.status_code}; linhas antes "
        f"{sum(len(g) for g in graus.values())}, depois "
        f"{sum(len(g) for g in depois.values())}",
    )

    # ── (g) uma tentativa nova ───────────────────────────────────────────────
    evento_novo, _ = nova_partida(minutos=5)
    await subir(evento_novo)
    status, _ = await dica(evento_novo["co_evento"], 1)
    id_nova = evento_novo["payload"]["partida"]["id_partida"]
    graus = await dicas_por_partida(conexao, id_usuario)
    relatorio.anotar(
        C_NOVA,
        status == 204 and graus.get(id_nova) == [1],
        f"status {status}; graus na tentativa nova: {graus.get(id_nova)}; o dia "
        "ja tinha 2",
    )

    # ── (h) o meu-dia ────────────────────────────────────────────────────────
    r = await cliente.get(f"/v1/desafios/{dia['id_desafio']}/meu-dia")
    dicas_do_dia = r.json().get("dicas") if r.status_code == 200 else None
    relatorio.anotar(
        C_MEU_DIA,
        r.status_code == 200 and dicas_do_dia == 3,
        f"status {r.status_code}; dicas no meu-dia: {dicas_do_dia!r} (esperado 3)",
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(conferir()))

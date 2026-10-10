"""AS DICAS NA `tb005` E O TETO POR TENTATIVA (T108 + T109) - medido contra o `des`.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT PROVA, E POR QUE SO O BANCO RESPONDE
═══════════════════════════════════════════════════════════════════════════

Em 10/10/2026 a `desafio_dia.tb005_poder_consumido` tinha ZERO linhas no `prd`,
com quatro dicas gastas em partidas de desafio (`DECISOES-do-dono.md` §8zzo). O
app mandava cada dica com o `co_evento` da partida, e esse `co_evento` so nasce
na 1a leva da gravacao: o envio desistia em silencio. Desde a T109 o SERVIDOR
reconstroi as linhas a partir de `qt_usos_poder` da partida, ao gravar a
tentativa. E desde a T108 o teto do botao e de 2 dicas por TENTATIVA.

Os testes unitarios provam a ordem e a chamada com um repositorio falso; o que
so o Postgres responde e se o `INSERT ... SELECT generate_series` grava, se a
VIEW enxerga, e se a contagem da sessao soma as tentativas.

As condicoes, numa conta nova:

  (a) a conta nasce, e ha um dia com desafio resolvivel no `des`;
  (b) **a tentativa que falhou, com 1 dica, deixa 1 linha** na `tb005` (grau 1);
  (c) **a que resolveu, com 2 dicas, deixa 2 linhas** (graus 1 e 2) - 3 no dia;
  (d) **o reenvio da resolucao nao duplica** (`ON CONFLICT DO NOTHING`);
  (e) **a rota da dica recusa a 3a NA MESMA tentativa** (409 `teto_de_dicas`);
  (f) **e aceita a 1a numa tentativa NOVA**, com o dia ja em 3 dicas (204);
  (g) **o `meu-dia` devolve o total do dia** (4 dicas), que e o que vai para a
      nota (§8zzo, decisao 2);
  (h) nada ficou no `des`.

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

    .venv\\Scripts\\python scripts\\conferir_dicas_na_tb005_t109.py

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
from scripts.conferir_credito_do_dia_t082 import falha  # noqa: E402
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
C_FALHA = "(b) a tentativa que falhou, com 1 dica, deixa 1 linha"
C_RESOLVEU = "(c) a que resolveu, com 2 dicas, deixa 2 linhas"
C_REENVIO = "(d) o reenvio nao duplica as linhas"
C_TETO = "(e) a 3a dica na MESMA tentativa e recusada"
C_NOVA = "(f) a 1a dica numa tentativa NOVA passa"
C_MEU_DIA = "(g) o meu-dia devolve o total do dia"
C_RASTRO = "(h) nada ficou no `des`"

#: As linhas da `tb005` da conta, por tentativa, pela VIEW.
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
    """Roda as oito condicoes e devolve o codigo de saida."""
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
    uid = f"t109-{uuid.uuid4()}"
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
            uid=uid, provedor="google.com", nome="Conta T109"
        )
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://t109",
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
    """As condicoes (a) a (g), numa conta que so joga o desafio."""
    from sqlalchemy import text

    # ── (a) ──────────────────────────────────────────────────────────────────
    r = await cliente.post(
        "/v1/conta/sessao",
        json={
            "no_exibicao": "Conta T109",
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

    async def subir_partida(*, minutos: int, dicas: int, em_andamento: bool = False):
        """Sobe a partida de desafio pelo lote, com `qt_usos_poder` = [dicas].

        Returns:
            `(co_evento, id_partida, inicio)`.
        """
        inicio = instante_no_dia(dia["dt_dia"], agora) - timedelta(minutes=minutos)
        co_evento = str(uuid.uuid4())
        evento = evento_de_partida(
            co_evento=co_evento, dia=dia, lote=str(uuid.uuid4()), inicio=inicio
        )
        partida = evento["payload"]["partida"]
        # Partida de conta, e nao de convidado: sem lote.
        partida["co_lote_migracao"] = None
        # ⚠️ O app so manda a chave quando ha uso (o payload dos jogos sem poder
        # fica igual ao que ja esta em campo) - aqui sempre ha.
        partida["qt_usos_poder"] = dicas
        if em_andamento:
            # A 1a leva de uma partida que ainda corre: sem fim.
            partida["co_status"] = "em_andamento"
            partida["dh_fim"] = None
        await cliente.post("/v1/sincronizacao/eventos", json={"eventos": [evento]})
        return co_evento, partida["id_partida"], inicio

    async def enviar(envio) -> int:
        """Manda o envio da tentativa e devolve o status HTTP."""
        r = await cliente.post(f"/v1/desafios/{dia['id_desafio']}/resolucao", json=envio)
        return r.status_code

    # ── (b) a falha, com 1 dica ──────────────────────────────────────────────
    co_falha, id_falha, inicio = await subir_partida(minutos=40, dicas=1)
    envio = envio_de_resolucao(
        dia=dia,
        co_evento_partida=co_falha,
        pontuacao=10,
        resolvido_em=inicio + timedelta(minutes=2),
        origem={"tipo": "conta"},
    )
    s1 = await enviar(falha(envio))
    graus = await dicas_por_partida(conexao, id_usuario)
    relatorio.anotar(
        C_FALHA,
        s1 == 200 and graus.get(id_falha) == [1],
        f"envio {s1}; graus gravados na tentativa: {graus.get(id_falha)}",
    )

    # ── (c) a resolucao, com 2 dicas ─────────────────────────────────────────
    co_ok, id_ok, inicio = await subir_partida(minutos=20, dicas=2)
    envio_ok = envio_de_resolucao(
        dia=dia,
        co_evento_partida=co_ok,
        pontuacao=20,
        resolvido_em=inicio + timedelta(minutes=2),
        origem={"tipo": "conta"},
    )
    # O que o app 1.4 manda: a 2a tentativa, com as 3 dicas do dia - e a nota
    # ainda presa em 2 ate a T103.
    envio_ok["tentativas"] = 2
    envio_ok["dicas_usadas"] = 2
    s2 = await enviar(envio_ok)
    graus = await dicas_por_partida(conexao, id_usuario)
    total = sum(len(g) for g in graus.values())
    relatorio.anotar(
        C_RESOLVEU,
        s2 == 200 and graus.get(id_ok) == [1, 2] and total == 3,
        f"envio {s2}; graus na tentativa: {graus.get(id_ok)}; total no dia: {total}",
    )

    # ── (d) o reenvio ────────────────────────────────────────────────────────
    s3 = await enviar(envio_ok)
    graus_depois = await dicas_por_partida(conexao, id_usuario)
    relatorio.anotar(
        C_REENVIO,
        s3 == 200 and graus_depois == graus,
        f"reenvio {s3}; linhas antes {total}, depois "
        f"{sum(len(g) for g in graus_depois.values())}",
    )

    # ── (e) a 3a dica na tentativa que ja tem 2 ──────────────────────────────
    def corpo_da_dica(co_evento: str, grau: int) -> dict[str, Any]:
        """O corpo de `POST /v1/desafios/{id}/dica`."""
        return {
            "id_desafio_dia": str(dia["id_desafio_dia"]),
            "co_evento_partida": co_evento,
            "grau": grau,
            "consumida_em": agora.isoformat(),
        }

    r = await cliente.post(
        f"/v1/desafios/{dia['id_desafio']}/dica", json=corpo_da_dica(co_ok, 2)
    )
    codigo = r.json().get("codigo") if r.status_code != 204 else None
    relatorio.anotar(
        C_TETO,
        r.status_code == 409 and codigo == "teto_de_dicas",
        f"status {r.status_code}, codigo {codigo!r}",
    )

    # ── (f) a 1a dica numa tentativa nova ────────────────────────────────────
    co_nova, id_nova, _ = await subir_partida(minutos=5, dicas=0, em_andamento=True)
    r = await cliente.post(
        f"/v1/desafios/{dia['id_desafio']}/dica", json=corpo_da_dica(co_nova, 1)
    )
    graus = await dicas_por_partida(conexao, id_usuario)
    relatorio.anotar(
        C_NOVA,
        r.status_code == 204 and graus.get(id_nova) == [1],
        f"status {r.status_code}; graus na tentativa nova: {graus.get(id_nova)}; "
        f"o dia ja tinha 3",
    )

    # ── (g) o meu-dia ────────────────────────────────────────────────────────
    r = await cliente.get(f"/v1/desafios/{dia['id_desafio']}/meu-dia")
    corpo = r.json() if r.status_code == 200 else {}
    dicas_do_dia = corpo.get("dicas")
    relatorio.anotar(
        C_MEU_DIA,
        r.status_code == 200 and dicas_do_dia == 4,
        f"status {r.status_code}; dicas no meu-dia: {dicas_do_dia!r} (esperado 4)",
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(conferir()))

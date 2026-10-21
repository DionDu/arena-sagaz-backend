"""A prova da T118 contra o Postgres do `des`, sem deixar linha nenhuma.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT EXISTE
═══════════════════════════════════════════════════════════════════════════

Os testes da T118 (`tests/unitarios/test_registro_do_aparelho.py` e irmãos)
rodam o SQL de verdade, mas num SQLite de memória - e o SQLite não prova o que
é só do Postgres: os tipos `UUID`, `DATE`, `NUMERIC(4,2)` e `JSONB`, o `CAST(...
AS JSONB)`, a inferência de tipo dos parâmetros do asyncpg dentro de `COALESCE`
e `CASE`. Este script prova exatamente isso, nas tabelas que a `0036` criou.

═══════════════════════════════════════════════════════════════════════════
COMO ELE NÃO SUJA O `des` (o molde é `conferir_merge_convidado_t079a.py`)
═══════════════════════════════════════════════════════════════════════════

Sobe o **aplicativo de verdade** (`api.main:app`) em memória, por
`ASGITransport`, e troca só a sessão: cada requisição recebe uma `AsyncSession`
presa a uma transação aberta pelo script, com
`join_transaction_mode="create_savepoint"`. O `commit` do serviço só fecha um
savepoint; o `rollback` do script no fim desfaz tudo. Uma conexão NOVA confere
depois que nenhuma linha ficou.

⚠️ A conta real que ele usa (para a linha legada do app 1.3) é só LIDA: o
registro escreve em `log.tb003`/`tb004`, e não na conta. A exclusão de conta é
provada sobre um `id_usuario` sorteado, que conta nenhuma tem.

⛔ **Só no `des`.** A URL vem de `DATABASE_URL_DES` no catálogo fora do Git, e
`identificar_banco.py` confere host e porta antes de qualquer import que crie o
motor.

Uso (do `arena-sagaz-backend`, ~10 s):

    .venv\\Scripts\\python scripts\\conferir_registro_do_aparelho_t118.py

Saída 0 só quando todas as condições fecham.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# `parents[1]` é a raiz do backend: é dela que `api` e `scripts` são importáveis.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

# O console do Windows é cp1252; sem isto, o primeiro emoji derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from scripts.conferir_portao_t050 import Relatorio, url_do_des  # noqa: E402
from scripts.identificar_banco import _nomear_ambiente  # noqa: E402

#: O fuso que o "app 1.4" do script manda: o do Brasil.
OFFSET_BRASIL = -180

C_VERSAO = "(a) o app 1.4 grava o dia LOCAL, com a maior versão, numa linha só"
C_LEGADO = "(b) o app 1.3 logado entra como legado, no fuso da última partida"
C_DETALHES = "(c) os detalhes: NUMERIC e JSONB gravados como o Postgres os guarda"
C_EXCLUSAO = "(d) a exclusão de conta zera o id_usuario do dia, e só o da pessoa"
C_LIMPO = "(e) depois do rollback, nada ficou no des"


async def conferir() -> int:
    """Roda as cinco condições e devolve o código de saída."""
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

    from api.aparelhos.regras import id_aparelho_legado
    from api.configuracao import configuracoes
    from api.conta.repositorio import RepositorioUsuario
    from api.main import app
    from api.nucleo.banco import engine as motor
    from api.nucleo.banco import obter_sessao
    from api.nucleo.dependencias import usuario_atual_opcional
    from api.nucleo.seguranca_firebase import IdentidadeFirebase

    relatorio = Relatorio()
    aparelho = str(uuid.uuid4())
    pessoa_sorteada = str(uuid.uuid4())
    agora = datetime.now(timezone.utc)
    dia_brasil = (agora + timedelta(minutes=OFFSET_BRASIL)).date()
    # Limites diferentes nas duas plataformas, como nos testes.
    configuracoes.ESPACO_APP_DETALHE_MB_ANDROID = 150
    configuracoes.ESPACO_APP_DETALHE_MB_IOS = 300

    cabecalhos_1_4 = {
        "X-App-Version": "1.4.0",
        "X-Platform": "android",
        "Accept-Language": "es",
        "X-Install-Id": aparelho,
        "X-Utc-Offset": str(OFFSET_BRASIL),
    }

    async with motor.connect() as conexao:
        transacao = await conexao.begin()

        async def sessao_dentro_da_transacao():
            """A sessão de cada requisição, presa à transação do script."""
            async with AsyncSession(
                bind=conexao, join_transaction_mode="create_savepoint", expire_on_commit=False
            ) as sessao:
                yield sessao

        identidade = {"atual": None}
        app.dependency_overrides[obter_sessao] = sessao_dentro_da_transacao
        app.dependency_overrides[usuario_atual_opcional] = lambda: identidade["atual"]

        async def linhas(sql: str, **parametros):
            return (await conexao.execute(text(sql), parametros)).mappings().all()

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://des"
            ) as cliente:
                # ── (a) a versão do dia ─────────────────────────────────────
                status = []
                for versao in ("1.4.0", "1.4.1", "1.4.0"):
                    r = await cliente.get(
                        "/v1/desafios/hoje", headers={**cabecalhos_1_4, "X-App-Version": versao}
                    )
                    status.append(r.status_code)
                dias = await linhas(
                    "SELECT dt_dia_local, co_versao_app, co_idioma, id_usuario "
                    "FROM log.vw004_aparelho_dia WHERE id_aparelho = :a",
                    a=aparelho,
                )
                ok = (
                    all(s in (200, 404) for s in status)
                    and len(dias) == 1
                    and dias[0]["dt_dia_local"] == dia_brasil
                    and dias[0]["co_versao_app"] == "1.4.1"
                    and dias[0]["co_idioma"] == "es"
                    and dias[0]["id_usuario"] is None
                )
                relatorio.anotar(
                    C_VERSAO,
                    ok,
                    f"três leituras ({status}), {len(dias)} linha(s): "
                    + (f"dia {dias[0]['dt_dia_local']} (esperado {dia_brasil}), "
                       f"versão {dias[0]['co_versao_app']}" if dias else "nenhuma"),
                )

                # ── (b) a linha legada de uma conta real (só LIDA) ──────────
                conta = (
                    await linhas(
                        """
                        SELECT u.id_usuario, u.co_identidade_externa,
                               (SELECT p.nu_offset_minuto_j1 FROM partida.vw001_partida p
                                 WHERE p.id_usuario = u.id_usuario
                                   AND p.nu_offset_minuto_j1 IS NOT NULL
                                 ORDER BY p.dh_inicio DESC LIMIT 1) AS offset_da_pessoa
                          FROM conta.vw001_usuario u
                         WHERE u.co_identidade_externa IS NOT NULL
                           AND EXISTS (SELECT 1 FROM partida.vw001_partida p
                                        WHERE p.id_usuario = u.id_usuario
                                          AND p.nu_offset_minuto_j1 IS NOT NULL)
                         LIMIT 1
                        """
                    )
                )[0]
                identidade["atual"] = IdentidadeFirebase(uid=conta["co_identidade_externa"])
                r = await cliente.get(
                    "/v1/desafios/hoje",
                    headers={"X-App-Version": "1.3.1", "X-Platform": "android",
                             "Accept-Language": "pt-BR"},
                )
                identidade["atual"] = None
                legado = str(id_aparelho_legado(str(conta["id_usuario"]), "android"))
                aparelhos = await linhas(
                    "SELECT ic_legado, co_plataforma FROM log.vw003_aparelho "
                    "WHERE id_aparelho = :a", a=legado,
                )
                dias = await linhas(
                    "SELECT dt_dia_local, co_versao_app, id_usuario FROM log.vw004_aparelho_dia "
                    "WHERE id_aparelho = :a", a=legado,
                )
                dia_dela = (agora + timedelta(minutes=conta["offset_da_pessoa"])).date()
                ok = (
                    r.status_code in (200, 404)
                    and [dict(a) for a in aparelhos] == [{"ic_legado": True, "co_plataforma": "android"}]
                    and len(dias) == 1
                    and dias[0]["dt_dia_local"] == dia_dela
                    and dias[0]["co_versao_app"] == "1.3.1"
                    and str(dias[0]["id_usuario"]) == str(conta["id_usuario"])
                )
                relatorio.anotar(
                    C_LEGADO,
                    ok,
                    f"conta com fuso {conta['offset_da_pessoa']} na última partida: "
                    f"{len(aparelhos)} aparelho legado, dia "
                    + (str(dias[0]["dt_dia_local"]) if dias else "nenhum")
                    + f" (esperado {dia_dela})",
                )

                # ── (c) os detalhes ─────────────────────────────────────────
                corpo = {
                    "fabricante": "samsung", "modelo": "SM-A065M", "abi": "arm64-v8a",
                    "nucleos": 8, "ram_mb": 3741, "tela_largura_dp": 384,
                    "tela_altura_dp": 853, "densidade_tela": 2.8125,
                    "versao_so": "Android 14 (SDK 34)", "espaco_app_kb": 204803,
                    "espaco_app": {"cache": 190000, "tmp": 0, "banco": 332, "pasta_nova": 9},
                }
                r = await cliente.post("/v1/aparelhos/detalhes", headers=cabecalhos_1_4, json=corpo)
                detalhe = await linhas(
                    "SELECT a.nu_densidade_tela, a.qt_nucleos, d.nu_espaco_app_kb, "
                    "       d.js_espaco_app, jsonb_typeof(d.js_espaco_app) AS forma, "
                    "       d.co_versao_so, d.co_versao_app "
                    "  FROM log.vw003_aparelho a "
                    "  JOIN log.vw004_aparelho_dia d USING (id_aparelho) "
                    " WHERE a.id_aparelho = :a", a=aparelho,
                )
                d = detalhe[0] if detalhe else {}
                js = d.get("js_espaco_app")
                js = json.loads(js) if isinstance(js, str) else js
                ok = (
                    r.status_code == 202
                    and r.json().get("detalhe_do_espaco_guardado") is True
                    and str(d.get("nu_densidade_tela")) == "2.81"
                    and d.get("forma") == "object"
                    and js == {"cache": 190000, "tmp": 0, "banco": 332}
                    and d.get("co_versao_so") == "Android 14 (SDK 34)"
                    and d.get("co_versao_app") == "1.4.1"  # a maior do dia continua
                )
                relatorio.anotar(
                    C_DETALHES,
                    ok,
                    f"{r.status_code}; densidade {d.get('nu_densidade_tela')}, "
                    f"js {d.get('forma')} {js}, versão do dia {d.get('co_versao_app')}",
                )

                # ── (d) a exclusão de conta, sobre uma pessoa sorteada ──────
                await conexao.execute(
                    text(
                        "INSERT INTO log.tb004_aparelho_dia "
                        "(id_aparelho, dt_dia_local, id_usuario, co_versao_app) "
                        "VALUES (:a, :d, :p, '1.4.0')"
                    ),
                    {"a": aparelho, "d": dia_brasil + timedelta(days=1), "p": pessoa_sorteada},
                )
                async with AsyncSession(
                    bind=conexao, join_transaction_mode="create_savepoint"
                ) as sessao:
                    await RepositorioUsuario(sessao).remover_dados_vinculados(pessoa_sorteada)
                    await sessao.commit()
                restantes = await linhas(
                    "SELECT count(*) AS n FROM log.vw004_aparelho_dia WHERE id_usuario = :p",
                    p=pessoa_sorteada,
                )
                legado_intacto = await linhas(
                    "SELECT count(*) AS n FROM log.vw004_aparelho_dia "
                    "WHERE id_aparelho = :a AND id_usuario IS NOT NULL", a=legado,
                )
                ok = restantes[0]["n"] == 0 and legado_intacto[0]["n"] == 1
                relatorio.anotar(
                    C_EXCLUSAO,
                    ok,
                    f"linhas da pessoa sorteada depois: {restantes[0]['n']} (esperado 0); "
                    f"a da conta real continua com dono: {legado_intacto[0]['n']} (esperado 1)",
                )
        finally:
            await transacao.rollback()
            app.dependency_overrides.clear()

    # ── (e) uma conexão NOVA: nada ficou ────────────────────────────────────
    # ⚠️ Conta só os ids do PRÓPRIO script: depois do push da T118 a API do
    # `des` grava linhas reais a cada abertura do app, e um "a tabela está
    # vazia" passaria a reprovar o certo.
    async with motor.connect() as nova:
        sobras = (
            await nova.execute(
                text(
                    "SELECT (SELECT count(*) FROM log.tb003_aparelho "
                    "         WHERE id_aparelho = :a) AS aparelhos, "
                    "       (SELECT count(*) FROM log.tb004_aparelho_dia "
                    "         WHERE id_aparelho = :a OR id_usuario = :p) AS dias"
                ),
                {"a": aparelho, "p": pessoa_sorteada},
            )
        ).mappings().one()
    relatorio.anotar(
        C_LIMPO,
        sobras["aparelhos"] == 0 and sobras["dias"] == 0,
        f"o aparelho do script: {sobras['aparelhos']} em log.tb003, "
        f"{sobras['dias']} dia(s) em log.tb004 (esperado 0 e 0)",
    )
    await motor.dispose()

    return 0 if relatorio.imprimir() else 1


def main() -> int:
    """Ponto de entrada."""
    return asyncio.run(conferir())


if __name__ == "__main__":
    raise SystemExit(main())

"""Recalcula a CHAMA (nu_sequencia_atual + dt_ultimo_dia_jogado) de TODOS os
usuários, de forma autoritativa, a partir dos DIAS LOCAIS de jogo.

    $env:DATABASE_URL = "<url-publica-do-postgres>"
    .venv\\Scripts\\python scripts/recalcular_chama_todos.py --confirmar

POR QUÊ: até jul/2026 o "dia jogado" saía de `dh_fim` lido em **UTC**, então uma
partida das 21h–23h no Brasil (BRT, UTC−3) caía no **dia seguinte** e a sequência
nunca crescia (ficava travada em 1). O servidor agora recalcula a chama sozinho a
cada `POST /eventos` — mas isso só conserta a linha GRAVADA quando o usuário joga
de novo. Este script conserta TODO MUNDO de uma vez, sem esperar (ex.: contas que
não vão jogar tão cedo, ou para inspeção imediata no banco).

É idempotente e NÃO destrutivo: só reescreve `nu_sequencia_atual` e
`dt_ultimo_dia_jogado` com o valor derivado do histórico de partidas. Rodar duas
vezes dá o mesmo resultado.

Exige `DATABASE_URL` explícita (não lê o `.env`) por segurança: no PowerShell
`set VAR=valor` NÃO define variável de ambiente, e cair no `.env` apontaria para
o DES. Sem a variável, o script se recusa a rodar.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Reaproveita EXATAMENTE a mesma regra "gentil" usada pelo servidor/app.
from api.sincronizacao.repositorio import calcular_sequencia_de_dias

# Mesma consulta do `RepositorioSincronizacao.recalcular_chama`: dias LOCAIS
# distintos (UTC + offset do jogador) das partidas concluídas que pontuam.
_SQL_DIAS = text(
    """
    SELECT DISTINCT
      ((COALESCE(dh_fim, dh_inicio) AT TIME ZONE 'UTC')
         + make_interval(mins => COALESCE(nu_offset_minuto_j1, 0)))::date AS dia
    FROM partida.tb001_partida
    WHERE id_usuario = :id
      AND ic_pontua = true
      AND co_status = 'concluida'
    ORDER BY dia
    """
)

_SQL_UPDATE = text(
    """
    UPDATE progressao.tb001_progressao_usuario
    SET nu_sequencia_atual = :seq,
        dt_ultimo_dia_jogado = :dia,
        dh_atualizacao = now()
    WHERE id_usuario = :id
    """
)


async def recalcular_todos(url: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as con:
            # Todo usuário que já tem linha de progressão (partidas criam a linha).
            ids = [
                linha[0]
                for linha in (
                    await con.execute(
                        text(
                            "SELECT id_usuario "
                            "FROM progressao.tb001_progressao_usuario"
                        )
                    )
                ).all()
            ]
            print(f"Usuários com progressão: {len(ids)}")
            mudados = 0
            for id_usuario in ids:
                dias = [
                    linha[0]
                    for linha in (
                        await con.execute(_SQL_DIAS, {"id": id_usuario})
                    ).all()
                ]
                if not dias:
                    # Sem partidas que pontuam: não mexe (pode haver seq de merge).
                    continue
                seq = calcular_sequencia_de_dias(dias)
                ultimo = dias[-1]
                await con.execute(
                    _SQL_UPDATE, {"id": id_usuario, "seq": seq, "dia": ultimo}
                )
                mudados += 1
                print(f"  {id_usuario}  →  chama={seq}  último={ultimo}")
            print(f"Pronto. Linhas recalculadas: {mudados}.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Exigido para executar (evita rodar sem querer).",
    )
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        sys.exit(
            "ERRO: defina DATABASE_URL (URL pública do Postgres do ambiente-alvo)."
        )
    if not args.confirmar:
        host = urlsplit(url).hostname or "?"
        sys.exit(
            f"Vai recalcular a chama de TODOS os usuários em '{host}'.\n"
            "Reexecute com --confirmar para prosseguir."
        )
    # O driver async precisa do prefixo asyncpg (a URL do Railway vem como
    # postgresql://). Normaliza como o resto do backend faz.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    asyncio.run(recalcular_todos(url))


if __name__ == "__main__":
    main()

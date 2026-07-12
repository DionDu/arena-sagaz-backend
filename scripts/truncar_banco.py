"""Zera TODOS os dados de um ambiente (des OU prd) para um teste limpo.

    $env:DATABASE_URL = "<url-publica-do-postgres>"
    .venv\\Scripts\\python scripts/truncar_banco.py --confirmar

⚠️ APAGA TUDO: contas, partidas, jogadas, XP, conquistas, dispositivos, aceites.
Só o que o banco precisa para continuar funcionando sobrevive:

  • `alembic_version`  → senão o Alembic acha que o banco nunca foi migrado e
                         tentaria rodar a 0001 por cima de um schema que já existe.
  • as DIMENSÕES `tb9xx_*` → são os CÓDIGOS (nu_acao, nu_tipo_xp…), semeados pela
                         migração 0006. Truncá-las derrubaria as FKs de todo o log
                         e a ingestão passaria a estourar 500 na primeira partida.

⚠️ ORDEM IMPORTA: **desinstale os apps dos aparelhos ANTES** de rodar isto. Um
aparelho com eventos pendentes na outbox local sincroniza tudo de volta assim que
abre — e o banco "limpo" nasce sujo.

Por que exige DATABASE_URL explícita (e não lê o `.env`): no PowerShell,
`set VAR=valor` NÃO define variável de ambiente (é apelido de `Set-Variable`), e o
script cairia no `.env` — que aponta para o DES. Já aconteceu de migrar o banco
errado assim. Aqui, sem a variável, o script simplesmente se recusa a rodar.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Schemas da aplicação. `public` fica de fora de propósito: é onde vive a
# `alembic_version`.
SCHEMAS = ("conta", "partida", "jogo_pontinhos", "progressao", "log")


async def truncar(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as con:
        # Descobre as tabelas na hora (em vez de listá-las à mão): assim o script
        # não envelhece quando uma tabela nova aparecer numa migração futura.
        resultado = await con.execute(
            text(
                """
                SELECT schemaname, tablename
                FROM pg_tables
                WHERE schemaname = ANY(:schemas)
                  AND tablename NOT LIKE 'tb9%'   -- preserva as DIMENSÕES
                ORDER BY schemaname, tablename
                """
            ),
            {"schemas": list(SCHEMAS)},
        )
        tabelas = [f"{s}.{t}" for s, t in resultado.all()]

        if not tabelas:
            print("Nenhuma tabela encontrada — o banco está migrado?")
            return

        print(f"\nTruncando {len(tabelas)} tabelas:")
        for t in tabelas:
            print(f"   • {t}")

        # CASCADE resolve a ordem das FKs sozinho; RESTART IDENTITY zera sequências.
        alvo = ", ".join(tabelas)
        await con.execute(text(f"TRUNCATE TABLE {alvo} RESTART IDENTITY CASCADE"))

        # Confere que as dimensões continuam de pé (elas são a espinha do log).
        print("\nDimensões preservadas:")
        for view in (
            "jogo_pontinhos.vw901_jogada_acao",
            "jogo_pontinhos.vw902_jogada_situacao",
            "partida.vw901_jogada_origem_decisao",
            "partida.vw902_tipo_xp",
        ):
            n = (await con.execute(text(f"SELECT count(*) FROM {view}"))).scalar()
            print(f"   • {view}: {n} códigos")

    await engine.dispose()
    print("\n✅ Banco zerado.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="obrigatório: confirma que você quer MESMO apagar tudo",
    )
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        sys.exit(
            "DATABASE_URL não está definida.\n"
            'No PowerShell:  $env:DATABASE_URL = "postgresql://..."\n'
            '(`set VAR=valor` NÃO funciona no PowerShell.)'
        )

    # Mostra o HOST antes de agir — é a última chance de perceber que a URL é a do
    # ambiente errado. Sem senha, para não vazar no histórico do terminal.
    partes = urlsplit(url)
    print(f"Banco alvo: {partes.hostname}:{partes.port}{partes.path}")

    if not args.confirmar:
        sys.exit(
            "\nNada foi feito. Confira o host acima; se for esse mesmo, repita com "
            "--confirmar."
        )

    asyncio.run(truncar(url.replace("postgresql://", "postgresql+asyncpg://")))


if __name__ == "__main__":
    main()

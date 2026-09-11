"""CONSULTA SOMENTE-LEITURA ao banco `des`, para o assistente nao depender de copia e cola.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT EXISTE
═══════════════════════════════════════════════════════════════════════════

Em 11/09/2026 o dono escreveu: *"estou cansado de ficar consultando o banco e
trazendo os dados das tabelas para voce"*. Ele estava copiando sete tabelas a
cada execucao do job.

⚠️ **A credencial NAO entra no repositorio, e nem no comando.** Ela mora em
`ferramentas/debug-bancos/ambientes.env`, na raiz do ecossistema, que ja e o
catalogo dos dois bancos e ja esta fora do Git. Este script le `DATABASE_URL_DES`
de la.

═══════════════════════════════════════════════════════════════════════════
⛔ SOMENTE LEITURA, E A TRAVA E DUPLA
═══════════════════════════════════════════════════════════════════════════

  1. **so o DES** — a URL usada e sempre `DATABASE_URL_DES`, nunca a de producao,
     e o arquivo tem as duas lado a lado (⚠️ e por isso que a trava importa: um
     erro de digitacao no nome da variavel apontaria para o `prd`);
  2. **a transacao e READ ONLY** (`SET TRANSACTION READ ONLY`), entao um `UPDATE`
     escrito por engano falha no banco, e nao so na conferencia do texto.

⚠️ **A checagem de palavra e a terceira trava, e a mais fraca das tres** — ela
existe para dar uma mensagem clara, e nao para ser a defesa: quem confia so em
procurar `DELETE` no texto e enganado pelo primeiro `/**/` do mundo.

⛔ **Nunca imprime a URL nem a senha.** A mesma regra de `identificar_banco.py`.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\consultar_des.py "SELECT count(*) FROM desafio.vw001_desafio"
    .venv\\Scripts\\python scripts\\consultar_des.py --arquivo consulta.sql

Saida em tabela de texto. `--json` devolve JSON, para quando o valor e um JSONB
que precisa ser lido inteiro.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

# `parents[2]` sobe de arena-sagaz-backend/scripts/ ate a raiz do ecossistema.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
RAIZ_ECOSSISTEMA = RAIZ_BACKEND.parent
sys.path.insert(0, str(RAIZ_BACKEND))

# ⚠️ O console do Windows e cp1252; sem isto, um acento no dado derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

#: O catalogo dos dois bancos, fora do Git.
CATALOGO = RAIZ_ECOSSISTEMA / "ferramentas" / "debug-bancos" / "ambientes.env"

#: Palavras que nao cabem numa consulta de leitura.
#:
#: ⚠️ Terceira trava, e a mais fraca — ver o cabecalho. Ela da a mensagem boa; a
#: defesa de verdade e o `SET TRANSACTION READ ONLY`.
PALAVRAS_DE_ESCRITA = (
    "insert", "update", "delete", "drop", "truncate", "alter", "create",
    "grant", "revoke", "copy", "vacuum", "call", "do",
)


def url_do_des() -> str:
    """A URL do `des`, lida do catalogo do ecossistema.

    Raises:
        SystemExit: quando o arquivo ou a chave nao existem — com o caminho na
            mensagem, porque quem le o erro precisa saber onde procurar.
    """
    if not CATALOGO.exists():
        raise SystemExit(f"⛔ catalogo nao encontrado: {CATALOGO}")

    for linha in CATALOGO.read_text(encoding="utf-8").splitlines():
        chave, _, valor = linha.partition("=")
        if chave.strip() == "DATABASE_URL_DES":
            bruta = valor.strip().strip('"').strip("'")
            if not bruta:
                raise SystemExit("⛔ DATABASE_URL_DES esta vazia no catalogo.")
            # O SQLAlchemy async precisa do driver no esquema.
            return re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", bruta, count=1)

    raise SystemExit(f"⛔ DATABASE_URL_DES nao esta em {CATALOGO}")


def conferir_leitura(sql: str) -> None:
    """Recusa o que nao parece consulta.

    Raises:
        SystemExit: quando uma palavra de escrita aparece como palavra inteira.
    """
    achadas = [
        palavra
        for palavra in PALAVRAS_DE_ESCRITA
        if re.search(rf"\b{palavra}\b", sql, flags=re.IGNORECASE)
    ]
    if achadas:
        raise SystemExit(
            f"⛔ isto nao e uma consulta de leitura: {', '.join(achadas)}.\n"
            "   Este script so le. Escrita no banco e comando do dono."
        )


def _texto(valor: Any, largura: int = 60) -> str:
    """Um valor de coluna em uma linha, encurtado quando enorme.

    ⚠️ JSONB inteiro nao cabe numa tabela de terminal; `--json` existe para
    quando ele precisa ser lido por completo.
    """
    if valor is None:
        return ""
    bruto = json.dumps(valor, ensure_ascii=False) if isinstance(valor, (dict, list)) else str(valor)
    bruto = bruto.replace("\n", " ")
    return bruto if len(bruto) <= largura else bruto[: largura - 1] + "…"


async def executar(sql: str, *, como_json: bool) -> int:
    """Roda a consulta numa transacao somente-leitura e imprime o resultado."""
    motor = create_async_engine(url_do_des(), echo=False, poolclass=NullPool)
    try:
        async with motor.connect() as conexao:
            # ⛔ A trava que o banco impoe, e nao o script.
            await conexao.execute(text("SET TRANSACTION READ ONLY"))
            resultado = await conexao.execute(text(sql))
            colunas = list(resultado.keys())
            linhas = resultado.fetchall()
    finally:
        await motor.dispose()

    if como_json:
        print(
            json.dumps(
                [dict(zip(colunas, linha)) for linha in linhas],
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        return 0

    if not linhas:
        print("(nenhuma linha)")
        return 0

    larguras = [
        max(len(coluna), *(len(_texto(linha[i])) for linha in linhas))
        for i, coluna in enumerate(colunas)
    ]
    print(" | ".join(c.ljust(larguras[i]) for i, c in enumerate(colunas)))
    print("-+-".join("-" * l for l in larguras))
    for linha in linhas:
        print(" | ".join(_texto(linha[i]).ljust(larguras[i]) for i in range(len(colunas))))
    print(f"\n({len(linhas)} linha(s))")
    return 0


def main() -> int:
    """Le os argumentos e roda."""
    argumentos = [a for a in sys.argv[1:]]
    como_json = "--json" in argumentos
    argumentos = [a for a in argumentos if a != "--json"]

    if argumentos and argumentos[0] == "--arquivo":
        if len(argumentos) < 2:
            raise SystemExit("⛔ --arquivo precisa do caminho do .sql")
        sql = Path(argumentos[1]).read_text(encoding="utf-8")
    elif argumentos:
        sql = " ".join(argumentos)
    else:
        raise SystemExit(__doc__ or "")

    conferir_leitura(sql)
    return asyncio.run(executar(sql, como_json=como_json))


if __name__ == "__main__":
    raise SystemExit(main())

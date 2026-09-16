"""CONSULTA SOMENTE-LEITURA ao banco `prd` — o de PRODUCAO, com usuarios reais.

═══════════════════════════════════════════════════════════════════════════
⛔ POR QUE ESTE SCRIPT EXISTE, E POR QUE ELE E SEPARADO DO `consultar_des.py`
═══════════════════════════════════════════════════════════════════════════

Ate 16/09/2026 a regra era simples: **o assistente nao fala com o `prd`**, e a
trava numero 1 de `consultar_des.py` e literalmente *"a URL usada e sempre
`DATABASE_URL_DES`"*. Naquele dia o dono abriu uma excecao, e a abriu com o
motivo escrito:

> *"Nela [no des] tem poucas partidas (todas jogadas por mim em alguns testes).
> Talvez fosse mais assertivo rodar no banco de Producao onde tem muitas partidas
> de usuarios reais no App. (...) Como voce esta rodando apenas SELECT no banco,
> nao vejo problema em acessar o banco de producao. So tomar cuidado pra nao
> rodar nem um DDL, DELETE, UPDATE ou INSERT."*

⛔ **E por isso este e um ARQUIVO NOVO, e nao um parametro `--ambiente` no script
do `des`.** Transformar o banco em argumento destruiria a trava que protege o
script antigo: hoje `consultar_des.py` **nao consegue** apontar para producao nem
se alguem quiser. Essa propriedade vale mais que evitar um arquivo a mais.
⚠️ A logica de conferencia, essa sim, e importada de la — uma fonte so.

═══════════════════════════════════════════════════════════════════════════
⛔ SOMENTE LEITURA, E AQUI A TRAVA E QUADRUPLA
═══════════════════════════════════════════════════════════════════════════

  1. **so o PRD** — a URL e sempre `DATABASE_URL_PRD`, lida do catalogo que fica
     fora do Git (`ferramentas/debug-bancos/ambientes.env`);
  2. **a transacao e READ ONLY** (`SET TRANSACTION READ ONLY`) — a defesa de
     verdade: uma escrita falha **no banco**, e nao so na conferencia do texto;
  3. **as palavras de escrita** (`conferir_leitura`, importada do irmao);
  4. ⚠️ **a consulta tem de COMECAR com `SELECT` ou `WITH`** — esta trava nao
     existe no script do `des`, e e a diferenca entre os dois. No `des` uma
     consulta esquisita e um erro; aqui e um incidente.

⛔ **Nunca imprime a URL nem a senha.**

⚠️ **E o aviso de producao vai para o STDERR, nao para o stdout** — quem faz
`> saida.json` precisa ver o aviso na tela **e** receber o JSON limpo no arquivo.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\consultar_prd.py "SELECT count(*) FROM jogo_damas.tb002_jogada"
    .venv\\Scripts\\python scripts\\consultar_prd.py --json "SELECT ..." > saida.json
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))
# A propria pasta `scripts/`, para o import do irmao funcionar quando o script e
# chamado de fora dela (`python scripts\consultar_prd.py`).
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ⚠️ O console do Windows e cp1252; sem isto, um acento no dado derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

# ⚠️ **Importado, e nao copiado.** `sem_comentarios` nasceu de um falso positivo
# real (a palavra "do" de um comentario em portugues); duplicar a regra aqui
# significaria consertar o mesmo defeito duas vezes, e uma das duas seria
# esquecida — que e o defeito que este projeto ja viu quatro vezes em telas.
from consultar_des import (  # noqa: E402
    CATALOGO,
    _texto,
    conferir_leitura,
    sem_comentarios,
)


def url_do_prd() -> str:
    """A URL do `prd`, lida do catalogo do ecossistema.

    ⛔ **Le `DATABASE_URL_PRD` e mais nada.** O mesmo arquivo tem a do `des` ao
    lado; a leitura por nome fixo e o que impede este script de virar generico.

    Raises:
        SystemExit: quando o arquivo ou a chave nao existem — com o caminho na
            mensagem, porque quem le o erro precisa saber onde procurar.
    """
    if not CATALOGO.exists():
        raise SystemExit(f"⛔ catalogo nao encontrado: {CATALOGO}")

    for linha in CATALOGO.read_text(encoding="utf-8").splitlines():
        chave, _, valor = linha.partition("=")
        if chave.strip() == "DATABASE_URL_PRD":
            bruta = valor.strip().strip('"').strip("'")
            if not bruta:
                raise SystemExit("⛔ DATABASE_URL_PRD esta vazia no catalogo.")
            # O SQLAlchemy async precisa do driver no esquema da URL.
            return re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", bruta, count=1)

    raise SystemExit(f"⛔ DATABASE_URL_PRD nao esta em {CATALOGO}")


def conferir_que_comeca_com_select(sql: str) -> None:
    """A quarta trava, que so existe na versao de producao.

    ⚠️ `conferir_leitura` procura palavras de escrita em **qualquer lugar** do
    texto; esta olha so a **primeira palavra do codigo**. As duas se completam: a
    primeira pega um `DELETE` no meio de um `WITH`, e esta recusa qualquer coisa
    que nao seja consulta logo de cara — um `EXPLAIN ANALYZE` (que **executa** o
    plano!), um `SET`, um `LISTEN`, um comando de psql colado por engano.

    Raises:
        SystemExit: quando a consulta nao comeca por `SELECT` ou `WITH`.
    """
    codigo = sem_comentarios(sql).strip()
    # O `lstrip` do parentese existe porque uma consulta pode legitimamente
    # comecar entre parenteses: `(SELECT ...) UNION (SELECT ...)`.
    primeira = codigo.lstrip("(").split(None, 1)[0].lower() if codigo else ""
    if primeira not in ("select", "with"):
        raise SystemExit(
            f"⛔ no PRD a consulta tem de comecar com SELECT ou WITH — veio `{primeira}`.\n"
            "   Este script so le, e este e o banco dos usuarios reais."
        )


async def executar(sql: str, *, como_json: bool) -> int:
    """Roda a consulta numa transacao somente-leitura e imprime o resultado.

    Igual a do irmao do `des`, com duas diferencas: a URL e a de producao e o
    aviso de ambiente vai para o stderr (ver o cabecalho).
    """
    print("⚠️  PRODUCAO (prd) — transacao SOMENTE LEITURA", file=sys.stderr)
    motor = create_async_engine(url_do_prd(), echo=False, poolclass=NullPool)
    try:
        async with motor.connect() as conexao:
            # ⛔ A trava que o BANCO impoe, e nao o script.
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
    """Le os argumentos e roda, passando pelas quatro travas."""
    argumentos = list(sys.argv[1:])
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
    conferir_que_comeca_com_select(sql)
    return asyncio.run(executar(sql, como_json=como_json))


if __name__ == "__main__":
    raise SystemExit(main())

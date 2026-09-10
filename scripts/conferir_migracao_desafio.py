"""CONFERE AS MIGRACOES 0018/0019/0020 NO BANCO — diagnostico SOMENTE-LEITURA.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT EXISTE
═══════════════════════════════════════════════════════════════════════════

`alembic upgrade head` que termina sem erro **nao prova** que o banco ficou como
deveria. Ele prova que os comandos rodaram — e a `0017` ensinou, em 08/2026, que
o defeito caro de migracao e o **silencioso**: uma VIEW que deixa de enxergar
uma coluna, uma dimensao que ninguem populou, um `CHECK` que continua recusando
a palavra nova. Nenhum desses da erro; todos aparecem semanas depois como *"o
app nao esta gravando"*.

⚠️ Este script **nao escreve nada**. Todas as consultas sao `SELECT`.

═══════════════════════════════════════════════════════════════════════════
O QUE ELE COMPARA, E CONTRA O QUE
═══════════════════════════════════════════════════════════════════════════

⛔ **Nao ha lista de tabelas escrita a mao aqui.** Uma lista a mao envelhece
calada: alguem acrescenta uma tabela na migracao, esquece de acrescenta-la aqui,
e o conferidor fica **verde e cego** — o mesmo defeito que ja custou quatro
fluxos de fim de partida no app. O esperado e **extraido das proprias
migracoes**, lendo os `CREATE TABLE` e `CREATE VIEW` dos arquivos.

Conferencias, na ordem em que um defeito custa caro:

  1. **a revisao do alembic** e a `head` dos arquivos — se nao for, o resto da
     conferencia estaria descrevendo outro estado do banco;
  2. **toda tabela e toda VIEW** das `0018`/`0019` existem, e nenhuma sobra;
  3. **as dimensoes que a migracao popula tem linha** — e a
     `desafio.tb903_perfil_dificuldade` esta VAZIA, de proposito: quem a
     preenche e o job, e enche-la aqui seria dado inventado;
  4. **o `CHECK` de `partida.co_modo` aceita `'desafio'`** — e a unica coisa que
     a `0020` faz, e a unica que toca tabela com dado real;
  5. **coluna de tabela que nao aparece na VIEW irma** — sai como AVISO, e nao
     como falha: ha VIEW que reduz de proposito.

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python scripts\\conferir_migracao_desafio.py

Codigo de saida: `0` = tudo confere; `2` = alguma conferencia reprovou; `1` =
nao deu para conectar (sem conexao nao ha conferencia).
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

# `parents[1]` sobe de scripts/ ate a raiz do repositorio do backend.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

MIGRACOES = RAIZ_BACKEND / "migrations" / "versions"

#: As duas migracoes que criam schema, e a revisao que tem de estar no banco.
ARQUIVOS_DE_SCHEMA = ("0018_schema_desafio.py", "0019_schema_desafio_dia.py")
REVISAO_ESPERADA = "0020_partida_modo_desafio"

#: As dimensoes que a propria migracao popula com `INSERT` — tem de ter linha.
DIMENSOES_POPULADAS = (
    "desafio.tb901_tipo_desafio",
    "desafio.tb902_catalogo_feito",
    "desafio_dia.tb901_tipo_xp_desafio",
    "desafio_dia.tb902_tipo_poder",
    "desafio_dia.tb903_tipo_reacao",
)

#: ⚠️ Esta NASCE VAZIA e continua vazia ate o job rodar. Uma linha aqui agora
#: seria perfil de dificuldade inventado, e ele decide o que a pessoa joga.
DIMENSAO_QUE_O_JOB_PREENCHE = "desafio.tb903_perfil_dificuldade"


def _ler_env(arquivo: Path) -> dict[str, str]:
    """Le um arquivo no formato `CHAVE=valor`, ignorando comentarios."""
    valores: dict[str, str] = {}
    if not arquivo.exists():
        return valores
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        valores[chave.strip()] = valor.strip()
    return valores


def _url_do_banco() -> str:
    """A `DATABASE_URL`, lida como `migrations/env.py` a le.

    ⚠️ O `setdefault` importa: uma variavel ja exportada no ambiente GANHA do
    arquivo. Ler diferente daqui faria este script conferir um banco enquanto a
    migracao rodou noutro.
    """
    for chave, valor in _ler_env(RAIZ_BACKEND / ".env").items():
        os.environ.setdefault(chave, valor)
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def _objetos_esperados() -> tuple[set[str], set[str]]:
    """`(tabelas, views)` que as migracoes `0018`/`0019` mandam criar.

    Lidos dos arquivos com expressao regular sobre o texto do `CREATE`. E de
    proposito que a fonte seja a migracao, e nao uma lista aqui: lista a mao
    envelhece em silencio.
    """
    tabelas: set[str] = set()
    views: set[str] = set()
    for nome in ARQUIVOS_DE_SCHEMA:
        texto = (MIGRACOES / nome).read_text(encoding="utf-8")
        tabelas |= set(re.findall(r"CREATE TABLE\s+(\w+\.\w+)", texto))
        views |= set(re.findall(r"CREATE (?:OR REPLACE )?VIEW\s+(\w+\.\w+)", texto))
    return tabelas, views


async def _conferir(url: str) -> int:
    """Faz as cinco conferencias e imprime o resultado de cada uma.

    Returns:
        `0` se todas passaram, `2` se alguma reprovou.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    tabelas_esperadas, views_esperadas = _objetos_esperados()
    reprovacoes: list[str] = []
    motor = create_async_engine(url)

    try:
        async with motor.connect() as conexao:

            # ── 1. a revisao ────────────────────────────────────────────────
            revisao = (
                await conexao.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                )
            ).scalar()
            print(f"  revisao do alembic        {revisao}")
            if revisao != REVISAO_ESPERADA:
                reprovacoes.append(
                    f"a revisao e {revisao!r}, e deveria ser {REVISAO_ESPERADA!r} — "
                    "o `upgrade` nao chegou ao fim, ou este e outro banco"
                )

            # ── 2. tabelas e VIEWs ──────────────────────────────────────────
            # `information_schema` responde pelo que o banco TEM; a migracao diz
            # o que ele DEVERIA ter. A diferenca nos dois sentidos importa:
            # faltar e migracao incompleta; sobrar e resto de tentativa anterior.
            existentes = {
                (linha[0], linha[1])
                for linha in (
                    await conexao.execute(
                        text(
                            "SELECT table_schema || '.' || table_name, table_type "
                            "FROM information_schema.tables "
                            "WHERE table_schema IN ('desafio','desafio_dia')"
                        )
                    )
                ).all()
            }
            tabelas = {n for n, tipo in existentes if tipo == "BASE TABLE"}
            views = {n for n, tipo in existentes if tipo == "VIEW"}

            for rotulo, tem, deveria in (
                ("tabelas", tabelas, tabelas_esperadas),
                ("VIEWs", views, views_esperadas),
            ):
                print(
                    f"  {rotulo:<25} {len(tem)} no banco, {len(deveria)} na migracao"
                )
                faltando = sorted(deveria - tem)
                if faltando:
                    reprovacoes.append(
                        f"{rotulo} que a migracao cria e o banco nao tem: {faltando}"
                    )
                sobrando = sorted(tem - deveria)
                if sobrando:
                    reprovacoes.append(
                        f"{rotulo} no banco que a migracao nao cria: {sobrando}"
                    )

            # ── 3. as dimensoes ─────────────────────────────────────────────
            for dimensao in DIMENSOES_POPULADAS:
                quantas = (
                    await conexao.execute(text(f"SELECT COUNT(*) FROM {dimensao}"))
                ).scalar()
                print(f"  {dimensao:<38} {quantas} linha(s)")
                if not quantas:
                    reprovacoes.append(
                        f"{dimensao} esta vazia — os `INSERT` da migracao nao "
                        "entraram, e toda FK que aponta para ela vai falhar na "
                        "primeira gravacao"
                    )

            vazia = (
                await conexao.execute(
                    text(f"SELECT COUNT(*) FROM {DIMENSAO_QUE_O_JOB_PREENCHE}")
                )
            ).scalar()
            print(
                f"  {DIMENSAO_QUE_O_JOB_PREENCHE:<38} {vazia} linha(s)  "
                "(quem preenche e o job)"
            )
            if vazia:
                reprovacoes.append(
                    f"{DIMENSAO_QUE_O_JOB_PREENCHE} deveria nascer VAZIA — quem a "
                    "preenche e o job, e perfil de dificuldade inventado decide o "
                    "que a pessoa joga"
                )

            # ── 4. o CHECK de `partida.co_modo` ─────────────────────────────
            # `pg_get_constraintdef` devolve o texto da constraint como o banco a
            # guarda; procurar a palavra nela e o mais perto de perguntar "voce
            # aceita isto?" sem escrever uma linha para descobrir.
            definicao = (
                await conexao.execute(
                    text(
                        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                        "WHERE conname = 'ck_partida_modo'"
                    )
                )
            ).scalar()
            print(f"  ck_partida_modo           {definicao}")
            if not definicao or "desafio" not in definicao:
                reprovacoes.append(
                    "o `CHECK` de partida.co_modo nao aceita 'desafio' — a `0020` "
                    "nao entrou, e toda resolucao de desafio seria recusada"
                )

            # ── 5. AVISO: coluna que a VIEW irma nao mostra ─────────────────
            # ⚠️ Aviso, e nao reprovacao: ha VIEW que reduz de proposito. O que
            # nao pode e o esquecimento passar despercebido, como na `0017`.
            colunas: dict[str, set[str]] = {}
            for linha in (
                await conexao.execute(
                    text(
                        "SELECT table_schema || '.' || table_name, column_name "
                        "FROM information_schema.columns "
                        "WHERE table_schema IN ('desafio','desafio_dia')"
                    )
                )
            ).all():
                colunas.setdefault(linha[0], set()).add(linha[1])

            avisos: list[str] = []
            for tabela in sorted(tabelas):
                # `tb001_desafio` -> `vw001_desafio`: a VIEW irma tem o mesmo
                # numero e o mesmo nome, so muda o prefixo (convencao do projeto).
                irma = tabela.replace(".tb", ".vw", 1)
                if irma not in views:
                    continue
                ausentes = sorted(colunas.get(tabela, set()) - colunas.get(irma, set()))
                if ausentes:
                    avisos.append(f"    {irma} nao mostra de {tabela}: {ausentes}")

            print()
            if avisos:
                print(
                    "  AVISO - coluna que a VIEW irma nao expoe "
                    "(confira se e de proposito):"
                )
                print("\n".join(avisos))
            else:
                print("  toda coluna de tabela aparece na VIEW irma")

    except Exception as erro:  # noqa: BLE001
        print(f"\n  NAO FOI POSSIVEL CONFERIR: {type(erro).__name__}: {erro}")
        return 1
    finally:
        await motor.dispose()

    print()
    if reprovacoes:
        print("  REPROVOU:")
        for motivo in reprovacoes:
            print(f"    · {motivo}")
        return 2
    print("  OK - o banco esta como as migracoes 0018/0019/0020 mandam")
    return 0


def main() -> int:
    """Le a URL, confere, e devolve o codigo de saida."""
    url = _url_do_banco()
    if not url:
        print("  DATABASE_URL nao esta definida (nem no ambiente, nem no .env)")
        return 1
    print()
    print("  CONFERENCIA DAS MIGRACOES DO DESAFIO  (so leitura)")
    print("  " + "-" * 66)
    return asyncio.run(_conferir(url))


if __name__ == "__main__":
    raise SystemExit(main())

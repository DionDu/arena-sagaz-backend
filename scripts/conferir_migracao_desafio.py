"""CONFERE AS MIGRACOES DO DESAFIO NO BANCO — diagnostico SOMENTE-LEITURA.

⚠️ **Quais migracoes, e qual revisao, sao DESCOBERTOS** — nao ha lista aqui.
Ate 10/09/2026 este arquivo nomeava `0018`/`0019` e esperava a revisao `0020`;
no dia em que a `0021` chegou, ele passou a acusar *"16 no banco, 15 na
migracao"* e a exigir uma revisao que nao era mais a cabeca. ⛔ Um conferidor que
reprova o banco CERTO ensina a ignora-lo, que e pior do que nao te-lo.

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
  2b. **as colunas de cada tabela, NA ORDEM**, batem com o que a migracao
     declara — ver a armadilha logo abaixo;
  3. **as dimensoes que a migracao popula tem linha** — e a
     `desafio.tb903_perfil_dificuldade` esta VAZIA, de proposito: quem a
     preenche e o job, e enche-la aqui seria dado inventado;
  4. **o `CHECK` de `partida.co_modo` aceita `'desafio'`** — e a unica coisa que
     a `0020` faz, e a unica que toca tabela com dado real;
  5. **coluna de tabela que nao aparece na VIEW irma** — sai como AVISO, e nao
     como falha: ha VIEW que reduz de proposito.

═══════════════════════════════════════════════════════════════════════════
⚠️ A ARMADILHA QUE A CONFERENCIA 2b EXISTE PARA PEGAR
═══════════════════════════════════════════════════════════════════════════

A regra §8b diz que, enquanto o `prd` nao tiver subido, defeito de modelagem
**dropa e recria dentro da propria migracao**. Depois que o `des` foi migrado
(10/09/2026) isso ganhou um degrau novo, e ele e silencioso:

    editar a `0018` e rodar `alembic upgrade head` **nao faz nada** —
    o banco ja esta em `0020`, e o alembic nao reaplica revisao aplicada.

O arquivo passa a dizer uma coisa e o `des` a ter outra. E o cadeado
`test_migracao_bate_com_data_model.py` continuaria **verde**: ele compara o
documento com o arquivo, e nenhum dos dois e o banco.

Quem edita uma dessas migracoes agora precisa de
`alembic downgrade 0017_poder_e_probing_base` e `upgrade head` — e e esta
conferencia que avisa quando alguem esquecer.

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

#: Os schemas que este conferidor cobre.
SCHEMAS = ("desafio", "desafio_dia")


def revisao_esperada() -> str:
    """A **cabeca** da cadeia de migracoes, descoberta dos arquivos.

    ⚠️ **Era uma constante escrita a mao**, e ela envelheceu no primeiro dia em
    que uma migracao nova chegou: a `0021` subiu e o conferidor continuou
    esperando a `0020`. Uma constante assim nao falha — ela passa a conferir a
    coisa errada, que e pior.

    A cabeca e a revisao que **nenhuma outra** aponta como `down_revision`.
    """
    revisoes: set[str] = set()
    anteriores: set[str] = set()
    for arquivo in sorted(MIGRACOES.glob("[0-9]*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        casa = re.search(r'^revision: str = "([^"]+)"', texto, re.M)
        if casa:
            revisoes.add(casa.group(1))
        casa = re.search(r'^down_revision[^=]*= "([^"]+)"', texto, re.M)
        if casa:
            anteriores.add(casa.group(1))
    cabecas = revisoes - anteriores
    if len(cabecas) != 1:
        raise RuntimeError(
            f"a cadeia de migracoes tem {len(cabecas)} cabecas ({sorted(cabecas)}). "
            "⛔ Ou ha um ramo, ou uma revisao ficou orfa."
        )
    return cabecas.pop()

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

    ⚠️ **Quais migracoes olhar tambem e DESCOBERTO**, e nao uma lista aqui: ate
    10/09/2026 estas duas linhas nomeavam a `0018` e a `0019`, e no dia em que a
    `0021` criou uma tabela o conferidor passou a dizer *"16 no banco, 15 na
    migracao"* — acusando divergencia onde nao havia, que ensina a ignora-lo.

    ⚠️ E o SQL vem do extrator por `ast`, e nao do texto cru do arquivo: um
    `CREATE TABLE` citado numa docstring contaria como tabela.
    """
    from tests.unitarios.leitura_de_migracao import sql_da_migracao
    from tests.unitarios.test_migracao_bate_com_data_model import (
        migracoes_dos_schemas,
    )

    tabelas: set[str] = set()
    views: set[str] = set()
    for arquivo in migracoes_dos_schemas():
        sql = sql_da_migracao(arquivo)
        tabelas |= set(re.findall(r"CREATE TABLE\s+(\w+\.\w+)", sql))
        views |= set(re.findall(r"CREATE (?:OR REPLACE )?VIEW\s+(\w+\.\w+)", sql))
    # ⛔ So os dois schemas cobertos: uma migracao pode criar tabela em `partida`
    # ou `log` na mesma passada, e ela nao e assunto deste conferidor.
    tabelas = {n for n in tabelas if n.split(".")[0] in SCHEMAS}
    views = {n for n in views if n.split(".")[0] in SCHEMAS}
    return tabelas, views


def _colunas_esperadas() -> dict[str, list[str]]:
    """`{tabela: [coluna, ...]}` NA ORDEM em que a migracao as declara.

    ⚠️ **O parser nao e escrito aqui.** Ele ja existe, em
    `tests/unitarios/test_migracao_bate_com_data_model.py`, e ler o SQL de uma
    migracao tem sutileza suficiente (`op.execute` com f-string, strings
    adjacentes concatenadas, comentario dentro do SQL) para que duas
    implementacoes acabem discordando — e a que discordasse em silencio seria
    justamente esta, a que ninguem roda no CI.

    Raises:
        Exception: se o modulo do cadeado nao puder ser importado. Falhar aqui e
            melhor que devolver `{}`: um dicionario vazio faria a conferencia
            passar sem ter olhado nada.
    """
    # O extrator de SQL e o parser de `CREATE TABLE` vivem nos cadeados, e sao os
    # mesmos que rodam no CI — e essa e a razao de importa-los em vez de
    # reescreve-los.
    from tests.unitarios.leitura_de_migracao import sql_da_migracao
    from tests.unitarios.test_migracao_bate_com_data_model import (
        _tabelas,
        migracoes_dos_schemas,
    )

    esperadas: dict[str, list[str]] = {}
    for arquivo in migracoes_dos_schemas():
        for tabela, dados in _tabelas(sql_da_migracao(arquivo)).items():
            esperadas[tabela] = [nome for nome, _tipo in dados["colunas"]]
    return esperadas


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
            cabeca = revisao_esperada()
            print(f"  revisao do alembic        {revisao}")
            if revisao != cabeca:
                reprovacoes.append(
                    f"a revisao e {revisao!r}, e deveria ser {cabeca!r} — "
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

            # ── 2b. as colunas, NA ORDEM ────────────────────────────────────
            # `ordinal_position` e a ordem fisica das colunas na tabela, e ela
            # entra na comparacao de proposito: a regra §8b diz que campo
            # importante nao fica no fim, e comparar conjuntos perderia
            # exatamente isso.
            colunas_no_banco: dict[str, list[str]] = {}
            for linha in (
                await conexao.execute(
                    text(
                        "SELECT table_schema || '.' || table_name, column_name "
                        "FROM information_schema.columns "
                        "WHERE table_schema IN ('desafio','desafio_dia') "
                        "ORDER BY table_schema, table_name, ordinal_position"
                    )
                )
            ).all():
                colunas_no_banco.setdefault(linha[0], []).append(linha[1])

            divergentes: list[str] = []
            esperadas = _colunas_esperadas()
            for tabela in sorted(tabelas_esperadas):
                no_banco = colunas_no_banco.get(tabela, [])
                na_migracao = esperadas.get(tabela, [])
                if no_banco != na_migracao:
                    divergentes.append(tabela)
            print(
                f"  {'colunas na ordem':<25} "
                f"{len(tabelas_esperadas) - len(divergentes)}/"
                f"{len(tabelas_esperadas)} tabelas conferem"
            )
            for tabela in divergentes:
                reprovacoes.append(
                    f"{tabela}: as colunas do banco nao batem com as da migracao.\n"
                    f"        no banco:    {colunas_no_banco.get(tabela, [])}\n"
                    f"        na migracao: {esperadas.get(tabela, [])}\n"
                    "        ⚠️ editar a migracao NAO reaplica: o alembic ja esta "
                    "em 0020. E preciso `downgrade 0017_poder_e_probing_base` e "
                    "`upgrade head`."
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

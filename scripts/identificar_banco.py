"""QUE BANCO E ESTE? — diagnostico SOMENTE-LEITURA, antes de qualquer escrita.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT EXISTE
═══════════════════════════════════════════════════════════════════════════

Em 2026-08-25 foi entregue ao dono o comando `alembic upgrade head` sem dizer
**contra qual banco** ele rodaria. A pergunta dele foi exatamente essa: *"Essa
migracao rodara no DES ou no PRD? Nao vejo no codigo a ser executado no
PowerShell qual o ambiente."*

Ele estava certo, e o problema e mais fundo do que o comando:

  · A URL vem de `DATABASE_URL`, que o `.env` do backend define
    (`migrations/env.py`), e o comando do alembic nao a menciona.
  · Os dois bancos se chamam `railway` — e o nome padrao do Postgres em TODO
    projeto Railway. O nome nao distingue nada.
  · O `.env` tem `AMBIENTE=...` ao lado, mas as duas variaveis sao
    INDEPENDENTES: ela diz como a API se comporta, nao a qual banco ela se liga.
    Trocar a URL e esquecer o `AMBIENTE` e um descuido de um segundo.

Ha usuarios reais em `prd` desde 04/08/2026. Uma migracao rodada no banco errado
nao e um susto — e um incidente.

═══════════════════════════════════════════════════════════════════════════
COMO ELE SABE QUAL E QUAL
═══════════════════════════════════════════════════════════════════════════

Comparando com `ferramentas/debug-bancos/ambientes.env`, na raiz do
ecossistema, que ja guardava `DATABASE_URL_DES` e `DATABASE_URL_PRD`. A
comparacao e por **host e porta**, nao pela URL inteira: a senha pode ser
rodada sem que o banco mude, e um diagnostico que dissesse "desconhecido" so
porque a senha girou seria abandonado no primeiro uso.

⚠️ **"Nao bate com nenhum dos dois" e o resultado mais perigoso**, nao o mais
inofensivo — significa um banco que ninguem catalogou. O script trata esse caso
como PARE, igual ao PRD.

⚠️ **Nunca imprime a senha.** A URL sai mascarada, e e assim que tem de
continuar: um diagnostico que vaza credencial para o terminal (e para o
historico do shell, e para o log da sessao) troca um risco por outro.

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python scripts\\identificar_banco.py

Codigo de saida: `0` = e o DES; `2` = e o PRD ou desconhecido; `1` = nao deu
para diagnosticar. Isso permite encadear num script sem ler a saida.
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

# O catalogo dos bancos vive na raiz do ECOSSISTEMA, um nivel acima do backend.
# ⚠️ E um arquivo com segredo: nao versionado, com irmao `.exemplo` ao lado.
CATALOGO = RAIZ_BACKEND.parent / "ferramentas" / "debug-bancos" / "ambientes.env"


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


def _carregar_dotenv() -> None:
    """Carrega o `.env` do backend, EXATAMENTE como `migrations/env.py` faz.

    ⚠️ A leitura precisa ser identica a de la, incluindo o `setdefault` (uma
    variavel ja exportada no ambiente GANHA do arquivo). Se este script lesse a
    URL de um jeito e o alembic de outro, o diagnostico descreveria um banco e a
    migracao rodaria noutro — que e o engano que ele existe para impedir.
    """
    for chave, valor in _ler_env(RAIZ_BACKEND / ".env").items():
        os.environ.setdefault(chave, valor)


def _mascarar(url: str) -> str:
    """Troca usuario e senha por marcadores, preservando host, porta e banco."""
    return re.sub(r"://[^:/@]+:[^@]+@", "://<usuario>:<senha>@", url)


def _host_e_porta(url: str) -> str:
    """Extrai `host:porta` de uma URL de conexao. Vazio se nao reconhecer.

    E o que identifica um banco: a senha pode ser rodada, o usuario pode mudar,
    o driver pode virar `+asyncpg` — o servidor continua o mesmo.
    """
    achado = re.search(r"://(?:[^@/]*@)?([^/:?]+):(\d+)", url)
    return f"{achado.group(1)}:{achado.group(2)}" if achado else ""


def _nomear_ambiente(url: str) -> tuple[str, str]:
    """Diz qual ambiente e a URL, comparando com o catalogo.

    Devolve `(nome, explicacao)`. O nome e `DES`, `PRD` ou `DESCONHECIDO`.
    """
    catalogo = _ler_env(CATALOGO)
    if not catalogo:
        return (
            "DESCONHECIDO",
            f"o catalogo nao foi encontrado em {CATALOGO}",
        )

    alvo = _host_e_porta(url)
    if not alvo:
        return "DESCONHECIDO", "nao consegui extrair host e porta da DATABASE_URL"

    for chave, valor in catalogo.items():
        if _host_e_porta(valor) == alvo:
            # `DATABASE_URL_DES` -> `DES`
            nome = chave.rsplit("_", 1)[-1].upper()
            return nome, f"host e porta batem com {chave} do catalogo"

    return (
        "DESCONHECIDO",
        f"{alvo} nao consta do catalogo — nao e o DES nem o PRD conhecidos",
    )


async def _inspecionar(url: str) -> int:
    """Consulta o banco e imprime o que ajuda a confirmar a identidade.

    Todas as consultas sao `SELECT`; nenhuma escreve, cria ou apaga nada.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    motor = create_async_engine(url)

    perguntas: list[tuple[str, str]] = [
        (
            "banco | usuario",
            "SELECT current_database() || '  |  ' || current_user",
        ),
        (
            "revisao do alembic",
            "SELECT COALESCE((SELECT version_num FROM alembic_version LIMIT 1), "
            "'(sem tabela alembic_version)')",
        ),
        (
            "schemas do projeto",
            "SELECT COALESCE(string_agg(nspname, ', ' ORDER BY nspname), '(nenhum)') "
            "FROM pg_namespace WHERE nspname IN "
            "('conta','partida','progressao','log','jogo_pontinhos','jogo_velha','jogo_damas')",
        ),
        ("contas cadastradas", "SELECT COUNT(*)::text FROM conta.tb001_usuario"),
        (
            "conta mais ANTIGA",
            "SELECT COALESCE(MIN(dh_criacao)::text, '(nenhuma)') FROM conta.tb001_usuario",
        ),
        (
            "conta mais RECENTE",
            "SELECT COALESCE(MAX(dh_criacao)::text, '(nenhuma)') FROM conta.tb001_usuario",
        ),
    ]

    try:
        async with motor.connect() as conexao:
            print()
            print("  E O QUE HA DENTRO DELE  (confirmacao - so leitura)")
            print("  " + "-" * 66)
            for rotulo, sql in perguntas:
                try:
                    resultado = await conexao.execute(text(sql))
                    valor = resultado.scalar()
                except Exception as erro:  # noqa: BLE001
                    # Uma pergunta que falha nao derruba as outras: a tabela pode
                    # nem existir ainda, e saber ISSO tambem identifica o banco.
                    valor = f"(nao respondeu: {type(erro).__name__})"
                print(f"  {rotulo:<26} {valor}")
    except Exception as erro:  # noqa: BLE001
        print()
        print(f"  NAO FOI POSSIVEL CONECTAR: {type(erro).__name__}: {erro}")
        print()
        print("  Sem conexao nao ha confirmacao - e sem confirmacao NAO se roda")
        print("  migracao. Confira a DATABASE_URL do .env: tem de ser a PUBLICA,")
        print("  terminada em .proxy.rlwy.net; a interna so funciona dentro da")
        print("  Railway.")
        return 1
    finally:
        await motor.dispose()
    return 0


def main() -> int:
    _carregar_dotenv()

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print()
        print("  DATABASE_URL nao esta definida (nem no ambiente, nem no .env).")
        print("  Nada a diagnosticar - e nada a migrar.")
        return 1

    # O alembic converte o esquema para o driver async; aqui e preciso fazer o
    # mesmo, ou o SQLAlchemy tentaria o driver sincrono e falharia.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    nome, explicacao = _nomear_ambiente(url)

    print()
    print("=" * 70)
    print("  QUE BANCO E ESTE?   (somente leitura - nada e escrito)")
    print("=" * 70)
    print()
    print("  Para onde a DATABASE_URL do backend aponta:")
    print(f"    {_mascarar(url)}")
    print()
    print(f"  >>> ESTE E O BANCO: {nome}")
    print(f"      ({explicacao})")
    print()
    # ⚠️ O `AMBIENTE` aparece, mas com a ressalva colada — ele ja induziu a erro
    # uma vez, por estar ao lado da URL no mesmo arquivo.
    print(f"  AMBIENTE declarado no .env: {os.environ.get('AMBIENTE', '(ausente)')}")
    print("    ^ NAO e prova de nada: esta variavel diz como a API se comporta,")
    print("      nao a qual banco ela se liga. As duas sao independentes.")

    codigo_da_leitura = asyncio.run(_inspecionar(url))

    print()
    print("=" * 70)
    if nome == "DES":
        print("  VEREDITO: e o DES. Seguro para migrar.")
        print("=" * 70)
        print()
        return codigo_da_leitura

    if nome == "PRD":
        print("  *** PARE - E O BANCO DE PRODUCAO. ***")
        print()
        print("  Ha usuarios reais aqui desde 04/08/2026. Nao rode migracao,")
        print("  DELETE nem TRUNCATE sem que isso seja a intencao explicita, e")
        print("  sem backup.")
    else:
        print("  *** PARE - BANCO NAO CATALOGADO. ***")
        print()
        print("  Este host nao e o DES nem o PRD conhecidos. Nao e um resultado")
        print("  inofensivo: e um banco que ninguem sabe qual e. Confira a")
        print("  DATABASE_URL do .env e o catalogo em:")
        print(f"    {CATALOGO}")
    print("=" * 70)
    print()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

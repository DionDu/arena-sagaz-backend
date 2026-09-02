"""TODO texto inserido por uma migracao CABE na coluna que o recebe.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

Em 25/08/2026 a migracao `0013` foi ao DES e caiu na primeira instrucao:

    asyncpg.exceptions.StringDataRightTruncationError:
    value too long for type character varying(40)

O texto `'Havia um lance legal so - nao houve busca'` tem **41** caracteres, e
`no_motivo_parada_busca` e `VARCHAR(40)`. Falhou **por um**.

O DDL transacional do Postgres reverteu tudo e o banco ficou intacto — o custo
foi uma ida ao banco e o susto de ver um traceback de 200 linhas. Mas o mesmo
erro numa migracao maior, ou num banco sem DDL transacional, deixa o schema no
meio do caminho.

⚠️ **Nenhum dos testes existentes pegaria isso**, e nao por descuido: a suite
nao roda contra um Postgres (e trabalho de integracao, e depende de banco). Os
cadeados de `test_migracoes_aditivas.py` conferem a FORMA do comando — que ele
nao e destrutivo, que o sentinela existe. Nenhum confere o CONTEUDO.

Este arquivo fecha esse buraco pelo caminho mais barato: le as migracoes como
texto, aprende os limites nos `CREATE TABLE` e mede os valores dos `INSERT`.
Nao precisa de banco, roda em milissegundos, e pega a classe inteira de erro —
inclusive num `INSERT` que alguem acrescente daqui a um ano.

⚠️ O que ele NAO faz: nao valida tipos, nao confere FKs, nao roda o SQL. Ele
responde uma pergunta so, e responde bem. Um teste que tentasse ser um Postgres
seria pior que nenhum.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# `parents[2]` sobe de tests/unitarios/ ate a raiz do repositorio do backend.
RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "migrations" / "versions"

# Acha `nome_da_coluna VARCHAR(30)` dentro de um CREATE TABLE. O `\s+` tolera o
# alinhamento em colunas que as migracoes do projeto usam.
_COLUNA_TEXTO = re.compile(
    r"^\s*([a-z_][a-z0-9_]*)\s+(?:VARCHAR|CHARACTER\s+VARYING)\s*\(\s*(\d+)\s*\)",
    re.I | re.M,
)

# `CREATE TABLE schema.tabela (` ... ate o `);` que fecha.
_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z_][a-z0-9_.]*)\s*\((.*?)\n\s*\)\s*;?",
    re.I | re.S,
)

# `INSERT INTO schema.tabela (col, col, col) VALUES` ... ate o fim do comando.
_INSERT = re.compile(
    r"INSERT\s+INTO\s+([a-z_][a-z0-9_.]*)\s*\(([^)]*)\)\s*VALUES(.*?)(?:ON\s+CONFLICT|;|\Z)",
    re.I | re.S,
)

# Uma tupla de valores: `(1, 'texto', 'outro')`.
_TUPLA = re.compile(r"\(([^()]*)\)", re.S)


def _limites_por_tabela() -> dict[str, dict[str, int]]:
    """Aprende, de TODAS as migracoes, quanto cabe em cada coluna de texto.

    Le a pasta inteira, e nao so o arquivo em teste: uma tabela criada na `0012`
    recebe `INSERT` na `0013`, e sem o mapa completo o teste nao teria como
    saber o limite.

    ⚠️ Um `ALTER TABLE ... ALTER COLUMN ... TYPE VARCHAR(n)` mudaria o limite e
    **nao** e lido aqui. Hoje isso nao existe (e proibido pelo cadeado de
    migracao aditiva); se um dia passar a existir, este mapa fica desatualizado
    em silencio — e e por isso que o aviso esta escrito, e nao subentendido.
    """
    limites: dict[str, dict[str, int]] = {}

    for arquivo in sorted(PASTA.glob("*.py")):
        fonte = arquivo.read_text(encoding="utf-8")
        for tabela, corpo in _CREATE_TABLE.findall(fonte):
            alvo = limites.setdefault(tabela.lower(), {})
            for coluna, tamanho in _COLUNA_TEXTO.findall(corpo):
                alvo[coluna.lower()] = int(tamanho)

    return limites


def _valores_da_tupla(bruto: str) -> list[str | None]:
    """Reparte uma tupla de `VALUES` respeitando as aspas.

    `None` para o que nao e literal de texto (numeros, `NULL`, expressoes): o
    teste so tem o que dizer sobre texto.

    Feito a mao porque `split(',')` quebraria em `'Vitoria, ou empate'` — e uma
    virgula dentro de aspas e exatamente o caso que apareceria so em producao.
    """
    valores: list[str | None] = []
    atual: list[str] = []
    dentro_de_aspas = False
    i = 0

    while i < len(bruto):
        caractere = bruto[i]

        if dentro_de_aspas:
            # `''` e a forma de escapar uma aspa simples no SQL padrao.
            if caractere == "'" and i + 1 < len(bruto) and bruto[i + 1] == "'":
                atual.append("'")
                i += 2
                continue
            if caractere == "'":
                dentro_de_aspas = False
                i += 1
                continue
            atual.append(caractere)
            i += 1
            continue

        if caractere == "'":
            dentro_de_aspas = True
            # (!) O que veio ANTES da aspa e separador, nao conteudo: nas
            # migracoes deste projeto os valores sao alinhados em colunas, e a
            # indentacao entrava no texto. Foi assim que a `0011` - correta, e
            # ja rodada em producao - apareceu com 42 caracteres num literal de
            # 36. Descartado aqui.
            atual = [""]
            i += 1
            continue

        if caractere == ",":
            bruto_do_campo = "".join(atual)
            valores.append(bruto_do_campo if _era_texto(bruto_do_campo, atual) else None)
            atual = []
            i += 1
            continue

        # Fora de aspas: numero, NULL, espaco. Guardado para saber se ha texto.
        atual.append(caractere)
        i += 1

    if atual or bruto.strip().endswith(","):
        bruto_do_campo = "".join(atual)
        valores.append(bruto_do_campo if _era_texto(bruto_do_campo, atual) else None)

    return valores


def _era_texto(campo: str, partes: list[str]) -> bool:
    """O campo veio de um literal entre aspas?

    Heuristica simples e suficiente: se o que sobrou, sem espacos, nao e um
    numero nem `NULL`, tratamos como texto. O pior caso e medir o comprimento de
    algo que nao e texto — e isso nunca reprova um `INSERT` correto, porque
    numero e `NULL` sao curtos.
    """
    limpo = campo.strip()
    if not limpo:
        return bool(partes)
    if limpo.upper() in {"NULL", "TRUE", "FALSE", "DEFAULT"}:
        return False
    # Numero (inteiro, decimal, negativo).
    return re.fullmatch(r"-?\d+(\.\d+)?", limpo) is None


def _migracoes() -> list[Path]:
    arquivos = sorted(PASTA.glob("*.py"))
    assert arquivos, f"nenhuma migracao encontrada em {PASTA}"
    return arquivos


@pytest.mark.parametrize("arquivo", _migracoes(), ids=lambda p: p.stem)
def test_todo_texto_inserido_cabe_na_coluna(arquivo: Path):
    """Cada valor de texto de cada `INSERT` cabe no `VARCHAR(n)` da coluna."""
    limites = _limites_por_tabela()
    fonte = arquivo.read_text(encoding="utf-8")

    problemas: list[str] = []

    for tabela, colunas_brutas, corpo in _INSERT.findall(fonte):
        colunas = [c.strip().lower() for c in colunas_brutas.split(",") if c.strip()]
        limites_da_tabela = limites.get(tabela.lower())
        if not limites_da_tabela:
            # Tabela sem coluna de texto conhecida — nada a conferir.
            continue

        for tupla in _TUPLA.findall(corpo):
            valores = _valores_da_tupla(tupla)

            for indice, valor in enumerate(valores):
                if valor is None or indice >= len(colunas):
                    continue
                coluna = colunas[indice]
                limite = limites_da_tabela.get(coluna)
                if limite is None:
                    continue

                # ⚠️ `len()` em Python conta CARACTERES, e `VARCHAR(n)` no
                # Postgres tambem — nao bytes. Um texto acentuado nao ocupa mais
                # do que parece, e trocar um dos dois por bytes daria falso
                # alarme em toda linha com acento.
                if len(valor) > limite:
                    problemas.append(
                        f"{tabela}.{coluna} e VARCHAR({limite}), mas o valor tem "
                        f"{len(valor)} caracteres: {valor!r}"
                    )

    assert not problemas, (
        f"{arquivo.name}: valor nao cabe na coluna\n  " + "\n  ".join(problemas)
    )


def test_o_proprio_teste_enxerga_as_colunas():
    """Sanidade: se os regex pararem de casar, tudo passa e nada e guardado.

    ⚠️ Este e o modo de falha mais provavel de um teste que le SQL como texto:
    alguem muda o estilo de escrita das migracoes, o regex deixa de casar, e o
    teste vira decoracao — verde, silencioso e inutil. Aqui ele e obrigado a
    provar que ainda esta enxergando alguma coisa.
    """
    limites = _limites_por_tabela()

    assert limites, "nenhum CREATE TABLE foi lido - os regex pararam de casar"

    # A coluna que derrubou a 0013, por nome e por tamanho. Se ela sumir daqui,
    # o teste perdeu a visao justamente do caso que o originou.
    dimensao = limites.get("jogo_damas.tb902_motivo_parada_busca", {})
    assert dimensao.get("no_motivo_parada_busca") == 40, (
        "nao enxerguei o VARCHAR(40) que originou este teste; "
        f"o que li foi: {dimensao}"
    )


def test_pega_o_valor_que_derrubou_a_0013():
    """O caso real, com o texto original de 41 caracteres.

    Sem isto, nada prova que o teste REPROVA — os arquivos no repositorio ja
    foram corrigidos, e um teste que so ve casos bons nao guarda nada.
    """
    original = "Havia um lance legal so - nao houve busca"
    assert len(original) == 41, "o texto do caso real mudou de tamanho"

    limites = _limites_por_tabela()
    limite = limites["jogo_damas.tb902_motivo_parada_busca"]["no_motivo_parada_busca"]

    assert len(original) > limite, (
        "o texto que derrubou a migracao no DES deveria estourar o limite, "
        f"mas {len(original)} <= {limite}"
    )

    # E o texto que entrou no lugar dele cabe.
    corrigido = "Lance unico: nao houve busca"
    assert len(corrigido) <= limite

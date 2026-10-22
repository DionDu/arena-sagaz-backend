"""🔒 A MIGRACAO 0033 CORRESPONDE AO `data-model.md` DA SPEC 010 QUE O DONO VALIDOU.

POR QUE ESTE CADEADO EXISTE
---------------------------
O dono valida o `data-model.md`, e nao o codigo do Alembic (a decisao de
09/09/2026, repetida na T003 da spec 010 em 13/10/2026). Entao a garantia de que
a migracao diz o que o documento prometeu precisa ser MECANICA: sem isto, a
validacao viraria um cheque em branco - uma coluna a mais, um tipo trocado ou
um codigo de dimensao diferente chegariam ao banco sem nada acusar.

O irmao `test_migracao_bate_com_data_model.py` faz o mesmo para a spec 009, mas
le o documento de la, que escreve o DDL em SQL. O da spec 010 escreve as tabelas
em MARKDOWN (`| coluna | tipo | restricao |`), por isso a leitura aqui e outra.

O QUE ELE COMPARA (schema `jogo_quatro`, data-model §2)
-------------------------------------------------------
  · as COLUNAS de cada tabela que o documento lista, com nome, tipo e ORDEM (a
    ordem importa: campo importante nao fica no fim, §8b);
  · os NOMES das constraints `ck_quatro_*` que o documento escreve;
  · as LINHAS das tres dimensoes: numero e codigo de cada uma. E o que o app
    manda e o que o banco traduz; um codigo trocado mandaria a jogada ao
    sentinela 9999 em silencio.

⛔ Nunca "ajuste o teste para passar": se ele falhar, ou a migracao divergiu do
que o dono validou (conserta-se a migracao), ou o modelo precisa mudar - e isso
e decisao do dono, com o `data-model.md` mudando primeiro.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.unitarios.leitura_de_migracao import sem_comentarios_sql, sql_do_upgrade

RAIZ = Path(__file__).resolve().parents[2]
DATA_MODEL = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "010-jogo-quatro-em-linha"
    / "data-model.md"
)
MIGRACAO = RAIZ / "migrations" / "versions" / "0033_schema_jogo_quatro.py"
#: As migracoes que so ACRESCENTAM linhas as dimensoes do schema, depois da
#: 0033: as linhas delas contam junto (a 0034 traz os descuidos, §8zzzf).
MIGRACOES_DE_LINHAS = (
    RAIZ / "migrations" / "versions" / "0034_acoes_de_descuido_quatro.py",
)


# ═══════════════════════════════════════════════════════════════════════════
# A leitura do documento
# ═══════════════════════════════════════════════════════════════════════════


def _secao_2(texto: str) -> str:
    """So a §2 do documento (o schema `jogo_quatro`), ate a §3."""
    inicio = texto.index("## 2. Schema `jogo_quatro`")
    fim = texto.index("## 3.", inicio)
    return texto[inicio:fim]


def _blocos_por_tabela(secao: str) -> dict[str, str]:
    """`{tabela: o texto debaixo do titulo dela}`, pelos titulos `#### `.

    Cada tabela do schema tem um titulo `#### \\`jogo_quatro.tbNNN_...\\``; o
    texto vai ate o proximo titulo de mesmo nivel ou maior.
    """
    partes = re.split(r"^#{3,4} ", secao, flags=re.M)
    blocos: dict[str, str] = {}
    for parte in partes:
        m = re.match(r"(?:🆕 )?`(jogo_quatro\.tb\d{3}_[a-z_]+)`", parte)
        if m:
            blocos[m.group(1)] = parte
    return blocos


def _linhas_de_tabela_md(bloco: str, cabecalho: str) -> list[list[str]]:
    """As linhas da tabela markdown cujo cabecalho comeca com [cabecalho].

    Devolve as celulas sem as crases, sem a linha de cabecalho e sem a linha
    de tracos. Lista vazia quando o bloco nao tem essa tabela.
    """
    linhas = bloco.splitlines()
    for i, linha in enumerate(linhas):
        if linha.startswith(cabecalho):
            corpo = []
            for seguinte in linhas[i + 2 :]:
                if not seguinte.startswith("|"):
                    break
                celulas = [c.strip().strip("`") for c in seguinte.strip("|").split("|")]
                corpo.append(celulas)
            return corpo
    return []


def _tipo_base(tipo: str) -> str:
    """`VARCHAR(30)` -> `VARCHAR(30)`; `SMALLINT` -> `SMALLINT` (em caixa alta)."""
    return tipo.strip().upper().replace(" ", "")


@pytest.fixture(scope="module")
def documento() -> dict[str, str]:
    """Os blocos de cada tabela da §2 do documento.

    ⛔ Sem o documento, FALHA (e nao `skip`): sem ele nao ha contra o que
    comparar, e a validacao do dono viraria cheque em branco.
    """
    assert DATA_MODEL.is_file(), f"o data-model.md nao esta em {DATA_MODEL}"
    return _blocos_por_tabela(_secao_2(DATA_MODEL.read_text(encoding="utf-8")))


# ═══════════════════════════════════════════════════════════════════════════
# A leitura da migracao
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def sql() -> str:
    """O SQL do `upgrade()` da 0033 e das que so acrescentam linhas, sem os
    comentarios `--`, um depois do outro."""
    partes = []
    for migracao in (MIGRACAO, *MIGRACOES_DE_LINHAS):
        assert migracao.is_file(), f"a migracao nao esta em {migracao}"
        partes.append(sem_comentarios_sql(sql_do_upgrade(migracao)))
    return "\n".join(partes)


def _colunas_da_migracao(sql: str, tabela: str) -> list[tuple[str, str]]:
    """`[(coluna, tipo)]` do `CREATE TABLE` de [tabela], na ordem.

    Uma coluna e a linha que comeca com um nome `xx_...` seguido do tipo; as
    linhas de `CONSTRAINT` e as continuacoes (`REFERENCES ...`) ficam de fora.
    """
    m = re.search(
        rf"CREATE TABLE {re.escape(tabela)}\s*\((.*?)\n\s*\)\s*$",
        sql,
        flags=re.S | re.M,
    )
    assert m, f"a migracao nao cria {tabela}"
    colunas = []
    for linha in m.group(1).splitlines():
        c = re.match(r"\s*([a-z]{2}_[a-z0-9_]+)\s+([A-Z]+(?:\(\d+\))?)", linha)
        if c:
            colunas.append((c.group(1), _tipo_base(c.group(2))))
    return colunas


def _linhas_do_insert(sql: str, tabela: str) -> list[tuple[int, str]]:
    """`[(numero, codigo)]` dos `INSERT` em [tabela], pelo numero: as duas
    primeiras colunas.

    Todos os `INSERT` contam (a 0033 povoa, a 0034 acrescenta), e a lista sai
    ORDENADA pelo numero: a ordem em que as migracoes os escrevem nao e a do
    documento (o sentinela 9999 veio na 0033, antes das linhas 7 a 9).
    """
    achados = re.findall(
        # Ate o PROXIMO comando: o SQL das chamadas vem junto, sem `;` entre
        # elas, e sem esse limite a leitura engoliria o INSERT seguinte.
        rf"INSERT INTO {re.escape(tabela)}\b.*?VALUES(.*?)(?=\s*(?:CREATE|INSERT)\b|\Z)",
        sql,
        flags=re.S,
    )
    assert achados, f"a migracao nao povoa {tabela}"
    return sorted(
        (int(n), co)
        for valores in achados
        for n, co in re.findall(r"\(\s*(\d+)\s*,\s*'([a-z_]+)'", valores)
    )


# ═══════════════════════════════════════════════════════════════════════════
# Os casos
# ═══════════════════════════════════════════════════════════════════════════

#: As tabelas cujas colunas o documento lista uma a uma. A `tb902` nao entra
#: aqui: o documento diz "mesmas colunas" das damas e lista so as linhas, que
#: sao conferidas no caso das dimensoes.
TABELAS_COM_COLUNAS = (
    "jogo_quatro.tb901_jogada_acao",
    "jogo_quatro.tb903_tipo_lance",
    "jogo_quatro.tb001_partida",
    "jogo_quatro.tb002_jogada",
)

#: As dimensoes, com o cabecalho da tabela de LINHAS no documento.
DIMENSOES = {
    "jogo_quatro.tb901_jogada_acao": "| `nu_acao` | `co_acao`",
    "jogo_quatro.tb902_motivo_parada_busca": "| `nu_motivo_parada_busca`",
    "jogo_quatro.tb903_tipo_lance": "| `nu_tipo_lance` | `co_tipo_lance`",
}


def test_o_documento_tem_as_cinco_tabelas(documento) -> None:
    """Sanidade: a leitura achou as cinco. Sem isto, o resto compararia vazios."""
    assert set(documento) == {
        "jogo_quatro.tb901_jogada_acao",
        "jogo_quatro.tb902_motivo_parada_busca",
        "jogo_quatro.tb903_tipo_lance",
        "jogo_quatro.tb001_partida",
        "jogo_quatro.tb002_jogada",
    }


@pytest.mark.parametrize("tabela", TABELAS_COM_COLUNAS)
def test_as_colunas_batem_NA_ORDEM(tabela: str, documento, sql) -> None:
    """Nome, tipo e posicao de cada coluna, nos dois lados."""
    do_documento = [
        (celulas[0], _tipo_base(celulas[1]))
        for celulas in _linhas_de_tabela_md(documento[tabela], "| coluna | tipo |")
    ]
    assert do_documento, f"o documento nao lista as colunas de {tabela}"
    assert _colunas_da_migracao(sql, tabela) == do_documento


def test_as_constraints_nomeadas_batem(sql) -> None:
    """Os `ck_quatro_*` do documento sao os da migracao, nem mais nem menos."""
    texto = _secao_2(DATA_MODEL.read_text(encoding="utf-8"))
    do_documento = set(re.findall(r"CONSTRAINT (ck_quatro_[a-z_]+)", texto))
    da_migracao = set(re.findall(r"CONSTRAINT (ck_quatro_[a-z_]+)", sql))
    assert do_documento, "o documento nao tem constraint nomeada nenhuma"
    assert da_migracao == do_documento


@pytest.mark.parametrize("tabela", sorted(DIMENSOES))
def test_as_linhas_das_dimensoes_batem(tabela: str, documento, sql) -> None:
    """O numero e o codigo de cada linha, com o sentinela 9999."""
    do_documento = [
        (int(celulas[0]), celulas[1])
        for celulas in _linhas_de_tabela_md(documento[tabela], DIMENSOES[tabela])
    ]
    assert do_documento, f"o documento nao lista as linhas de {tabela}"
    assert (9999, "desconhecido") in do_documento
    assert _linhas_do_insert(sql, tabela) == sorted(do_documento)


# ═══════════════════════════════════════════════════════════════════════════
# A §3 do documento contra a 0035 (T114): os tipos e as medidas do desafio
# ═══════════════════════════════════════════════════════════════════════════
#
# As duas tabelas da §3 (`tb901_tipo_desafio` e `tb902_catalogo_feito`) foram
# ratificadas pelo dono com os nomes de lá (T003, §8zzz). A migração tem de
# trazer exatamente as mesmas linhas, na mesma ordem de colunas; uma letra a
# mais num `co_` seria um tipo que o job não acha, sem erro nenhum.

MIGRACAO_DO_DESAFIO = RAIZ / "migrations" / "versions" / "0035_desafio_quatro.py"

#: Os dois tipos que fecham no meio (§8zzzr item 9, 22/10/2026): moram na §3.1.1
#: do documento, que este leitor junta à §3.1, e numa migração própria.
MIGRACAO_DO_MEIO = RAIZ / "migrations" / "versions" / "0037_tipos_quatro_meio.py"


def _linhas_md_da_secao_3(subsecao: str) -> list[list[str]]:
    """As linhas de dados da tabela markdown da subseção `3.1` ou `3.2`.

    Cada célula sai sem espaços e sem as crases (os ids vêm entre crases).
    """
    texto = DATA_MODEL.read_text(encoding="utf-8")
    inicio = texto.index(f"### {subsecao} ")
    fim = texto.index("\n### ", inicio + 1)
    linhas = []
    for linha in texto[inicio:fim].splitlines():
        # Linha de dados: começa com `|` e a 1ª célula é um número.
        celulas = [c.strip().strip("`") for c in linha.strip().strip("|").split("|")]
        if linha.startswith("|") and celulas[0].isdigit():
            linhas.append(celulas)
    return linhas


def _tuplas_do_insert(tabela: str, migracao=MIGRACAO_DO_DESAFIO) -> list[list[str]]:
    """As tuplas do `INSERT INTO desafio.<tabela>` da [migracao], como texto."""
    fonte = migracao.read_text(encoding="utf-8")
    corpo = re.search(rf"INSERT INTO desafio\.{tabela}.*?VALUES(.*?)\"\"\"", fonte, re.S)
    assert corpo, f"a {migracao.name} não tem o INSERT de {tabela}"
    tuplas = []
    for tupla in re.findall(r"\(\s*(\d+,[^()]*?)\)", corpo.group(1), re.S):
        tuplas.append([v.strip().strip("'") for v in tupla.split(",")])
    return tuplas


@pytest.mark.parametrize(
    "subsecao, tabela",
    [("3.1", "tb901_tipo_desafio"), ("3.2", "tb902_catalogo_feito")],
)
def test_a_0035_traz_as_linhas_da_secao_3(subsecao: str, tabela: str) -> None:
    documento = _linhas_md_da_secao_3(subsecao)
    migracao = _tuplas_do_insert(tabela)
    if subsecao == "3.1":
        # A §3.1 inclui a §3.1.1: os dois da 0037, depois dos dez da 0035.
        migracao += _tuplas_do_insert(tabela, MIGRACAO_DO_MEIO)
    # Controle: os dez tipos da T003 e os dois da §8zzzr, e as sete medidas.
    assert len(documento) == {"3.1": 12, "3.2": 7}[subsecao]
    assert migracao == documento, (
        f"a 0035 diverge do data-model §{subsecao}:\n  migração: {migracao}\n"
        f"  documento: {documento}"
    )

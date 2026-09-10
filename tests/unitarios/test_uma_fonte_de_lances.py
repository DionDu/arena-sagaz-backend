"""🔒 CADEADO 9 — HA UMA FONTE DE LANCES, E ELA E `partida` (RF-DES-187, SC-025).

═══════════════════════════════════════════════════════════════════════════
O QUE ELE PEGA
═══════════════════════════════════════════════════════════════════════════

Uma coluna de lances que nasca **fora do schema `partida`**.

⚠️ **A resolucao E uma partida** (RF-DES-186): os lances sobem pelo log que o
aplicativo ja envia hoje, com `co_modo = 'desafio'` e `ic_pontua = FALSE`.
⛔ **Nao ha log de lances proprio do desafio**, e o replay do desafio e o replay
de uma partida.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE UMA SEGUNDA FONTE SERIA CARA — E POR QUE ELA E TENTADORA
═══════════════════════════════════════════════════════════════════════════

E tentadora porque parece simples: uma coluna `js_lances` em `tb003_resolucao`
resolveria o replay do desafio em uma linha, sem `JOIN` nenhum.

E cara porque jogaria fora, **de graca**, quatro coisas que ja estao em producao:

  1. o **replay**, com a linha do tempo e o poder "voltar jogada";
  2. a **extensao por jogo** (`jogo_pontinhos.tb002_jogada`, `jogo_damas`…);
  3. a **auditoria pelo arbitro**, que re-executa a fita;
  4. o registro de **poder na jogada cancelada**.

⛔ E criaria o pior tipo de defeito: duas verdades sobre a mesma partida, que
divergem no dia em que uma delas for gravada e a outra nao — sem que nada acuse.

═══════════════════════════════════════════════════════════════════════════
⚠️ A LEITURA E COM `ast`, E NAO COM REGEX SOBRE O ARQUIVO
═══════════════════════════════════════════════════════════════════════════

Pelo mesmo motivo de sempre neste projeto: o SQL das migracoes e escrito com
f-strings e strings adjacentes, e um regex de texto **ja perdeu comandos
inteiros** — duas vezes, em 09/09/2026. O historico esta em
`leitura_de_migracao.py`, e sao **cinco** ocorrencias da mesma especie.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.unitarios.leitura_de_migracao import sql_da_migracao

RAIZ = Path(__file__).resolve().parents[2]
MIGRACOES = RAIZ / "migrations" / "versions"

#: O schema que **pode** guardar lances.
SCHEMA_DA_VERDADE = "partida"

#: Os schemas que estendem a jogada — 1:1 com `partida.tb002_jogada`.
#:
#: ⚠️ Eles guardam o lance **daquele jogo** (`co_aresta`, `co_lance`), e isso nao
#: e uma segunda fonte: a linha deles **nao existe** sem a jogada generica (a
#: chave primaria e a FK para ela). Sao a mesma fita, com o detalhe do jogo.
SCHEMAS_DE_EXTENSAO = frozenset({"jogo_pontinhos", "jogo_velha", "jogo_damas"})

#: O que parece coluna de lance.
#:
#: ⚠️ `co_aresta` e `co_lance` sao os nomes reais das extensoes; `js_lances`,
#: `ar_lances` e `co_jogada` sao as formas que uma segunda fonte assumiria se
#: alguem a escrevesse — e sao justamente as tentadoras.
PADROES_DE_LANCE = (
    r"\bco_aresta\b",
    r"\bco_lance\b",
    r"\bjs_lances\b",
    r"\bar_lances\b",
    r"\bco_jogada\b",
    r"\bjs_jogadas\b",
    r"\bjs_fita\b",
)

#: As colunas que **parecem** e nao sao.
#:
#: ⚠️ `js_solucao` guarda o **gabarito** do desafio, e nao os lances de ninguem:
#: ele e escrito pelo job na geracao, e nunca por uma partida. ⛔ Ele nao pode
#: virar fonte de replay — o Raio-X do sujeito `desafio` o serve como solucao de
#: referencia, que e outra coisa (RF-DES-078a).
EXCECOES_CONHECIDAS = {
    "desafio.tb001_desafio": {
        "js_solucao": (
            "e o GABARITO, escrito pelo job na geracao. Nao e a fita de "
            "ninguem, e nao vira replay: o sujeito `desafio` do Raio-X o serve "
            "como solucao de REFERENCIA, e ela nao disputa o quadro."
        ),
        "js_posicao_inicial": (
            "e a POSICAO DE PARTIDA do desafio — a preparacao, e nao a partida. "
            "No Pontinhos ela e uma sequencia de tracos porque a posse de uma "
            "caixa e historico; ainda assim, ela descreve de onde a fita COMECA, "
            "e nao o que alguem jogou."
        ),
    }
}


def _colunas_por_tabela() -> dict[str, list[str]]:
    """`{schema.tabela: [linha do DDL, ...]}` de tudo o que as migracoes criam.

    ⚠️ Guarda as **linhas** do `CREATE TABLE`, e nao so os nomes: o cadeado
    procura padroes dentro delas, e um nome extraido perderia o `JSONB` ao lado
    que ajuda a explicar a falha.
    """
    por_tabela: dict[str, list[str]] = {}
    for arquivo in sorted(MIGRACOES.glob("0*.py")):
        sql = sql_da_migracao(arquivo)
        for bloco in re.finditer(
            r"CREATE TABLE\s+(\w+\.\w+)\s*\((.*?)\n\s*\)", sql, re.S
        ):
            tabela, corpo = bloco.group(1), bloco.group(2)
            por_tabela.setdefault(tabela, []).extend(
                linha.strip() for linha in corpo.splitlines() if linha.strip()
            )
    return por_tabela


def test_a_varredura_encontra_alguma_coisa():
    """⚠️ **Nada a varrer e FALHA.**

    Um cadeado que nao acha o que conferir fica verde e cego. Este caso quebra
    **antes** do principal, e a mensagem diz onde olhar.
    """
    tabelas = _colunas_por_tabela()
    assert tabelas, (
        "a varredura das migracoes nao encontrou tabela nenhuma. ⛔ O leitor "
        "quebrou — veja `leitura_de_migracao.sql_da_migracao`."
    )
    # E ela enxerga, de fato, as colunas de lance que **devem** existir.
    assert any(
        "co_aresta" in " ".join(linhas)
        for tabela, linhas in tabelas.items()
        if tabela.startswith("jogo_pontinhos.")
    ), "a varredura nao viu `co_aresta` no Pontinhos. ⛔ O leitor quebrou."


def test_nenhuma_coluna_de_lance_fora_de_partida():
    """🔒 O cadeado.

    ⛔ Uma coluna de lances fora de `partida` (e das extensoes 1:1 dela) e uma
    **segunda fonte da verdade** sobre a mesma partida. Ela divergiria no dia em
    que uma das duas fosse gravada e a outra nao — sem que nada acusasse.
    """
    achados: list[str] = []
    for tabela, linhas in _colunas_por_tabela().items():
        schema = tabela.split(".")[0]
        if schema == SCHEMA_DA_VERDADE or schema in SCHEMAS_DE_EXTENSAO:
            continue
        excecoes = EXCECOES_CONHECIDAS.get(tabela, {})
        for linha in linhas:
            for padrao in PADROES_DE_LANCE:
                if re.search(padrao, linha) and not any(
                    coluna in linha for coluna in excecoes
                ):
                    achados.append(f"{tabela}: {linha}")

    assert not achados, (
        "coluna(s) de lance fora do schema `partida`:\n  "
        + "\n  ".join(achados)
        + "\n\n⚠️ A resolucao E uma partida (RF-DES-186): os lances sobem pelo "
        "log que o aplicativo ja envia. Uma segunda fonte joga fora, de graca, o "
        "replay, a extensao por jogo, a auditoria pelo arbitro e o registro de "
        "poder na jogada cancelada."
    )


def test_as_extensoes_de_jogada_dependem_da_jogada_generica():
    """⚠️ E isto que faz delas **a mesma fita**, e nao uma segunda.

    A chave primaria de cada extensao **e** a FK para `partida.tb002_jogada`: a
    linha nao existe sem a jogada generica. Se alguem trocar isso por um `id`
    proprio, a extensao passa a poder viver sozinha — e vira a segunda fonte que
    este cadeado existe para impedir.
    """
    por_tabela = _colunas_por_tabela()
    extensoes = [
        (tabela, linhas)
        for tabela, linhas in por_tabela.items()
        if tabela.split(".")[0] in SCHEMAS_DE_EXTENSAO
        and tabela.endswith("tb002_jogada")
    ]
    assert extensoes, "nenhuma extensao de jogada encontrada. ⛔ Leitor quebrado."

    for tabela, linhas in extensoes:
        cabeca = " ".join(linhas[:3])
        assert "PRIMARY KEY" in cabeca and "partida.tb002_jogada" in cabeca, (
            f"{tabela}: a chave primaria deixou de ser a FK para "
            "`partida.tb002_jogada`. ⛔ A extensao passa a poder existir sem a "
            "jogada generica, e vira uma segunda fonte de lances."
        )


def test_as_excecoes_estao_explicadas():
    """⚠️ Excecao sem motivo escrito e a porta por onde a proxima entra.

    Cada coluna listada em `EXCECOES_CONHECIDAS` carrega a frase que explica por
    que ela **parece** lance e nao e — e e essa frase que impede a lista de
    crescer por conveniencia.
    """
    for tabela, colunas in EXCECOES_CONHECIDAS.items():
        for coluna, motivo in colunas.items():
            assert len(motivo) > 40, f"{tabela}.{coluna} sem motivo de verdade"

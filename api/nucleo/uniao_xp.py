"""ONDE O XP MORA — a declaracao que o cadeado 7 confere (RF-DES-182, T047).

═══════════════════════════════════════════════════════════════════════════
O PROBLEMA, EM UMA FRASE
═══════════════════════════════════════════════════════════════════════════

Ate 09/2026 havia **uma** tabela de XP no projeto: `partida.tb003_xp_partida`.
Com o Desafio do Dia entra a **segunda**, `desafio_dia.tb004_xp_desafio` — e o
XP de uma pessoa deixa de estar num lugar so.

Quem somar o XP total precisa somar as duas. E a terceira, quando vier (um
torneio, uma temporada), precisara entrar nessa soma **sem que ninguem se
lembre** de que ela existe.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE UMA LISTA DECLARADA, SE O PROJETO PROIBE LISTA ESCRITA A MAO
═══════════════════════════════════════════════════════════════════════════

A proibicao e contra cadeado que **acha** que sabe o que existe — o
`contrato_hash_test.dart` ficando verde e cego, a lista de telas que esqueceu um
jogo. O padrao aqui e o oposto, e a diferenca esta em quem e a **realidade**:

    esta lista  → o CONTRATO: o que a uniao de XP cobre
    a varredura → a REALIDADE: o que existe nas migracoes

O cadeado falha quando a realidade tem algo que o contrato nao tem. Uma tabela
nova de XP que nasca sem entrar aqui **quebra o CI** — e o conserto e uma linha,
tomada com a decisao consciente de que aquele XP entra (ou nao) na soma.

⛔ **O contrario nao acontece**: nada aqui e usado para "descobrir" tabelas. Se
esta lista fosse a fonte, uma tabela esquecida ficaria invisivel, que e
exatamente o defeito que o cadeado existe para pegar.

═══════════════════════════════════════════════════════════════════════════
⚠️ A VIEW DE UNIAO NAO E ENTREGA DESTA SPEC — E O CADEADO E, ASSIM MESMO
═══════════════════════════════════════════════════════════════════════════

Somar as duas tabelas numa VIEW e trabalho de quando alguem precisar do total.
O **cadeado**, porem, nasce com a **segunda** tabela, que e agora: escrito depois
da terceira, ele chega tarde por definicao — e a terceira ja teria ficado de fora
de uma soma que ninguem sabia estar incompleta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class FonteDeXp:
    """Uma tabela que guarda XP de uma pessoa.

    Atributos:
        tabela: o nome qualificado, `schema.tabela`.
        coluna_xp: onde o valor esta. ⚠️ **Os nomes diferem** — `nu_xp` na
            partida, `vr_xp` no desafio — porque um e inteiro e o outro tem casas
            decimais, e o prefixo do projeto (`nu_`/`vr_`) diz isso. Uma uniao que
            assumisse o mesmo nome nos dois falharia na primeira consulta.
        coluna_usuario: por onde a soma agrupa.
        de_por_que: a frase que explica esta fonte para quem a ler daqui a um ano.
    """

    tabela: str
    coluna_xp: str
    coluna_usuario: str
    de_por_que: str


#: As fontes de XP que a uniao cobre.
#:
#: ⚠️ **Tabela nova de XP entra AQUI, ou o CI quebra.** E o ponto inteiro do
#: cadeado 7: nao existe caminho em que ela seja criada e a soma continue verde.
FONTES: Mapping[str, FonteDeXp] = {
    "partida.tb003_xp_partida": FonteDeXp(
        tabela="partida.tb003_xp_partida",
        coluna_xp="nu_xp",
        coluna_usuario="id_usuario",
        de_por_que=(
            "O XP das partidas comuns, desde a spec 006. ⚠️ So conta o de "
            "partida que pontua (`ic_pontua`); partida de desafio nao entra por "
            "aqui, e e por isso que a segunda tabela existe."
        ),
    ),
    "desafio_dia.tb004_xp_desafio": FonteDeXp(
        tabela="desafio_dia.tb004_xp_desafio",
        coluna_xp="vr_xp",
        coluna_usuario="id_usuario",
        de_por_que=(
            "O XP do Desafio do Dia, aberto parcela a parcela. ⚠️ `vr_xp` e "
            "`NUMERIC`, e nao inteiro: as parcelas tem casas decimais, e "
            "arredondar cada uma faria a soma nao bater com o total."
        ),
    ),
}


#: O que a varredura procura: qualquer tabela cujo nome contenha `_xp_`.
#:
#: ⚠️ **O padrao e sobre o NOME**, e nao sobre o conteudo, porque nao ha como
#: perguntar a uma coluna se ela guarda XP. A convencao do projeto e forte o
#: bastante para isso funcionar: `tb003_xp_partida`, `tb004_xp_desafio`,
#: `tb902_tipo_xp`.
#:
#: ⚠️ As **dimensoes** (`tb9NN_`) sao excluidas: `tb902_tipo_xp` e uma lista de
#: tipos, e nao XP de pessoa nenhuma. A regra do prefixo `tb9` ja as separa em
#: todo o projeto.
PADRAO_DE_NOME = "_xp_"
PREFIXO_DE_DIMENSAO = "tb9"


def e_fonte_de_xp(tabela: str) -> bool:
    """Este nome de tabela parece guardar XP de uma pessoa?

    Args:
        tabela: `schema.tabela`.

    Returns:
        `True` quando ela deve estar na uniao.

    ⚠️ **Dimensao nao e fonte.** `desafio_dia.tb901_tipo_xp_desafio` casa com o
    padrao e **nao** guarda XP: e a lista de tipos. O prefixo `tb9` a separa, e
    essa e a mesma convencao que o resto do projeto usa.
    """
    nome = tabela.split(".")[-1]
    if nome.startswith(PREFIXO_DE_DIMENSAO):
        return False
    return PADRAO_DE_NOME in nome


def faltantes(tabelas_encontradas: set[str]) -> set[str]:
    """As tabelas de XP que existem e **nao estao** na uniao.

    Args:
        tabelas_encontradas: o que a varredura achou nas migracoes.

    Returns:
        As que ficaram de fora — vazio quando esta tudo coberto.
    """
    return {t for t in tabelas_encontradas if e_fonte_de_xp(t)} - set(FONTES)

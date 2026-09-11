"""AS RECEITAS DE CADA TIPO DE DESAFIO (T034).

═══════════════════════════════════════════════════════════════════════════
TIPO x FORMA DE CHEGADA — E ISSO CONFUNDIU A SPEC POR SEMANAS
═══════════════════════════════════════════════════════════════════════════

**O tipo e a IDENTIDADE** do desafio: e ele que da a frase, o rodizio (para nao
cair o mesmo tipo dois dias seguidos) e o agrupamento na curadoria.

**A forma de chegada e COMO SE JULGA**, e ela e **uma so** — a conjuncao de
clausulas. Dez tipos diferentes usam hoje a mesma forma.

⚠️ Foi por confundir os dois que *"o lance unico"* e *"final da base"* pareceram,
por um tempo, nao ter forma propria: eles sao **tipos**, e a linha de chegada
deles e a comum.

Uma **receita** e o que liga um ao outro: dado o tipo e os parametros do dia, ela
monta o `js_chegada`, a chave de i18n do enunciado e os valores que entram na
frase.

═══════════════════════════════════════════════════════════════════════════
⛔ TIPO SEM RECEITA NAO E PUBLICAVEL — E E ASSIM QUE TEM DE SER
═══════════════════════════════════════════════════════════════════════════

E a regra 2 do contrato dos vetores, vista deste lado. Um tipo publicado sem
receita produziria um desafio cuja linha de chegada ninguem escreveu — e o
julgamento devolveria "nao cumpriu" para todo mundo, **sem erro nenhum**.

⚠️ E a receita nao basta sozinha: o gerador tambem exige **vetor de verificacao**
para o tipo (RF-DES-198). Duas portas, e as duas fecham a mesma falha silenciosa
por caminhos diferentes — a receita garante que existe regra, o vetor garante que
os dois lados a leem igual.

═══════════════════════════════════════════════════════════════════════════
⚠️ PARAMETRO NOVO E `INSERT`, NUNCA CODIGO (SC-027)
═══════════════════════════════════════════════════════════════════════════

Trocar `4` por `6` caixas no mesmo tipo **nao toca `.arb`, nao toca codigo e nao
muda `co_versao_minima`**. E por isso que os numeros sao argumento da receita, e
nao literais espalhados por ela.

O que **ainda exige versao nova do aplicativo** e a chave `.arb` do enunciado: uma
chave desconhecida cai na tela de atualizar. Por isso a chave e parte da receita —
acrescentar um tipo e, por definicao, acrescentar texto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

#: A versao do formato de `js_chegada` que as receitas emitem.
VERSAO_CHEGADA = 1


class TipoSemReceita(ValueError):
    """O tipo nao tem receita — e por isso nao e publicavel.

    ⚠️ Falha alto de proposito. A alternativa (devolver uma chegada vazia) daria
    um desafio que ninguem consegue cumprir, e o log ficaria limpo.
    """


@dataclass(frozen=True, slots=True)
class Receita:
    """Como um tipo vira desafio.

    Atributos:
        nu_tipo_desafio: o numero da dimensao `tb901_tipo_desafio`.
        co_tipo_desafio: o codigo, para leitura humana e para os vetores.
        co_jogo: de que jogo este tipo e.
        co_chave_objetivo: a chave de i18n do enunciado. ⛔ **Nunca a frase**: ela
            viajaria num idioma so.
        montar: `(parametros) -> js_chegada`.
        valores_da_frase: `(parametros, personagem) -> js_objetivo`, os valores
            que entram nos espacos da frase.
        moldes: posicoes de partida de onde este tipo costuma sair. Vazio quer
            dizer "gere a partir do inicio do jogo".

    ⚠️ **Por que MOLDES existem, e a medida que os justifica.** O gerador ingenuo
    parte do tabuleiro vazio (ou da posicao inicial) e joga lances aleatorios ate
    chegar a algo interessante. Isso funciona no Pontinhos, e ⛔ **nao funciona
    nas damas**: medido em 09/09/2026, tres tentativas de gerar *"coroe uma dama
    em 6 lances"* a partir de 40 lances aleatorios deram **zero** candidatos em
    35 segundos — coroar exige atravessar o tabuleiro, e uma abertura aleatoria
    quase nunca deixa uma peca perto da oitava fileira com caminho livre.

    Um molde e uma posicao **de onde o objetivo e alcancavel**, escrita a mao e
    validada pelo motor. O gerador sorteia um molde e o **varia** com poucos
    lances legais antes de procurar a solucao — e e a variacao que impede a fila
    de repetir a mesma posicao todo dia.

    ⚠️ Molde **nao e** o desafio pronto: se a variacao destruir o objetivo, o
    gerador simplesmente nao acha solucao e tenta outra. O molde e ponto de
    partida, nunca garantia.
    """

    nu_tipo_desafio: int
    co_tipo_desafio: str
    co_jogo: str
    co_chave_objetivo: str
    montar: Callable[[Mapping[str, Any]], dict[str, Any]]
    valores_da_frase: Callable[[Mapping[str, Any], str], dict[str, Any]]
    moldes: tuple[str, ...] = ()


def _medida(chave: str, comparador: str, valor: Any) -> dict[str, Any]:
    """Uma clausula de medida, no formato que o avaliador le."""
    return {
        "tipo": "medida",
        "chave": chave,
        "comparador": comparador,
        "valor": valor,
    }


# ═══════════════════════════════════════════════════════════════════════════
# As receitas
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Sao quatro, e nao dez, e isso esta declarado.** As outras seis entram
# quando tiverem receita E vetor — nesta ordem, e nunca uma sem a outra.

RECEITAS: dict[str, Receita] = {
    "pontinhos_fechar_caixas": Receita(
        nu_tipo_desafio=1,
        co_tipo_desafio="pontinhos_fechar_caixas",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoFecharCaixasEmTurnos",
        # "Feche N caixas em T turnos": a janela e de TURNOS, e nao de lances,
        # porque quem fecha caixa joga de novo — quatro caixas em quatro lances
        # seguidos sao um turno so.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "turnos_do_jogador", "n": p["turnos"]},
            "clausulas": [_medida("caixas_fechadas", "maior_ou_igual", p["caixas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "caixas": p["caixas"],
            "turnos": p["turnos"],
            "personagem": personagem,
        },
    ),
    "pontinhos_chegar_ao_placar": Receita(
        nu_tipo_desafio=4,
        co_tipo_desafio="pontinhos_chegar_ao_placar",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoChegarAoPlacar",
        # Sem limite de turnos: o que importa e o placar no fim.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [_medida("caixas_fechadas", "maior_ou_igual", p["caixas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "caixas": p["caixas"],
            "personagem": personagem,
        },
    ),
    "damas_coroar": Receita(
        nu_tipo_desafio=6,
        co_tipo_desafio="damas_coroar",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoCoroarEmLances",
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "lances_do_jogador", "n": p["lances"]},
            "clausulas": [_medida("damas_coroadas", "maior_ou_igual", p["damas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "damas": p["damas"],
            "lances": p["lances"],
            "personagem": personagem,
        },
        # Finais em que uma branca esta a poucos passos da oitava fileira, com
        # pretas suficientes para a partida nao acabar antes.
        #
        # ⚠️ **Os tres primeiros foram desenhados a mao; os 158 seguintes foram
        # MEDIDOS** por `scripts/cacar_moldes_damas.py` em 11/09/2026 (300
        # candidatas) — o Sagaz jogou os dois lados a partir de cada um, nas
        # quatro modalidades, com o mesmo orcamento do gerador. Cada comentario
        # diz em que lance o objetivo caiu, na media dos regulamentos.
        #
        # ⛔ **Dez moldes aprovados pelo script foram REMOVIDOS depois**, mais um
        # dos quatro fundadores: eles entregavam o objetivo **no primeiro lance**.
        # ⚠️ A medicao nao pegava porque **o Sagaz joga a PARTIDA, e nao o
        # DESAFIO** — coroar de cara costuma ser mau lance, entao ele escolhia
        # outra coisa e a medicao anotava "objetivo no lance 3"; so que quem joga
        # o desafio nao esta jogando para vencer, esta cumprindo a tarefa.
        #
        # ⛔ Quem guarda isso agora e `job/moldes_de_damas.py`, na peneira do
        # script **e** no cadeado `tests/unitarios/test_moldes_de_damas.py` — a
        # pergunta e direta ("ha lance legal que cumpre o objetivo agora?") e nao
        # custa um no de busca.
        moldes=(
            # ── Os fundadores que SOBRARAM, escritos a mao em 09/09/2026 ────
            #
            # ⚠️ Eram quatro; o segundo saiu em 11/09 por coroar no primeiro
            # lance (`10x1` nas quatro modalidades).
            "W:W9,23,27:B5,12,20",
            "W:W13,25,30:B8,17,22",
            "W:W14,26,31:B7,18,24",
            # ── Medidos em 11/09/2026 pela caçada de 300 candidatas ─────────
            #
            # ⚠️ **Os 20 da primeira caçada estão AQUI DENTRO**, e não foram
            # perdidos: aquela rodada mediu as 30 primeiras candidatas desta
            # mesma sequência, então esta lista é superconjunto dela —
            # conferido FEN a FEN antes da troca.
            "W:W9,18,21:B14,19,24",  # 4/4 — objetivo no lance 9.0
            "W:W10,17,19:B14,18,23",  # 4/4 — objetivo no lance 9.0
            "W:W12,25,28:B13,15,17",  # 4/4 — objetivo no lance 8.5
            "W:W10,27,28:B15,17,24",  # 4/4 — objetivo no lance 8.5
            "W:W10,21,25:B16,17,22",  # 4/4 — objetivo no lance 8.5
            "W:W9,23,29:B16,18,24",  # 4/4 — objetivo no lance 8.0
            "W:W9,20,24:B13,17,23",  # 4/4 — objetivo no lance 8.0
            "W:W9,17,23:B14,15,19",  # 4/4 — objetivo no lance 8.0
            "W:W6,23,25:B13,14,19",  # 4/4 — objetivo no lance 8.0
            "W:W12,23,32:B13,15,16",  # 4/4 — objetivo no lance 8.0
            "W:W11,23,24:B18,19,20",  # 4/4 — objetivo no lance 8.0
            "W:W11,18,30:B15,16,21",  # 4/4 — objetivo no lance 8.0
            "W:W11,17,32:B14,15,18",  # 4/4 — objetivo no lance 8.0
            "W:W10,26,27:B18,22,23",  # 4/4 — objetivo no lance 8.0
            "W:W10,21,31:B17,19,24",  # 4/4 — objetivo no lance 8.0
            "W:W11,21,22:B15,16,20",  # 4/4 — objetivo no lance 7.5
            "W:W10,26,28:B16,19,20",  # 4/4 — objetivo no lance 7.5
            "W:W10,23,26:B19,20,21",  # 4/4 — objetivo no lance 7.5
            "W:W12,24,25:B14,20,22",  # 4/4 — objetivo no lance 7.0
            "W:W12,22,27:B15,19,21",  # 4/4 — objetivo no lance 7.0
            "W:W11,28,32:B15,17,19",  # 4/4 — objetivo no lance 7.0
            "W:W11,26,29:B13,18,24",  # 4/4 — objetivo no lance 7.0
            "W:W10,28,29:B15,20,22",  # 4/4 — objetivo no lance 7.0
            "W:W10,26,30:B13,19,20",  # 4/4 — objetivo no lance 7.0
            "W:W10,24,28:B18,20,21",  # 4/4 — objetivo no lance 7.0
            "W:W9,22,26:B13,14,18",  # 4/4 — objetivo no lance 6.5
            "W:W9,18,31:B13,15,19",  # 4/4 — objetivo no lance 6.5
            "W:W7,17,23:B15,18,24",  # 4/4 — objetivo no lance 6.5
            "W:W12,24,27:B13,15,19",  # 4/4 — objetivo no lance 6.5
            "W:W12,20,29:B13,16,18",  # 4/4 — objetivo no lance 6.5
            "W:W12,20,27:B13,15,19",  # 4/4 — objetivo no lance 6.5
            "W:W12,20,24:B17,19,22",  # 4/4 — objetivo no lance 6.5
            "W:W11,19,26:B16,20,22",  # 4/4 — objetivo no lance 6.5
            "W:W11,18,27:B14,21,23",  # 4/4 — objetivo no lance 6.5
            "W:W10,25,28:B16,21,22",  # 4/4 — objetivo no lance 6.5
            "W:W10,17,24:B14,15,20",  # 4/4 — objetivo no lance 6.5
            "W:W9,27,30:B14,18,20",  # 4/4 — objetivo no lance 6.0
            "W:W9,23,28:B18,19,20",  # 4/4 — objetivo no lance 6.0
            "W:W9,19,27:B16,18,22",  # 4/4 — objetivo no lance 6.0
            "W:W9,18,28:B16,20,22",  # 4/4 — objetivo no lance 6.0
            "W:W6,17,23:B14,19,22",  # 4/4 — objetivo no lance 6.0
            "W:W5,22,29:B14,17,19",  # 4/4 — objetivo no lance 6.0
            "W:W12,25,30:B14,22,23",  # 4/4 — objetivo no lance 6.0
            "W:W11,24,29:B18,19,20",  # 4/4 — objetivo no lance 6.0
            "W:W11,17,25:B18,19,20",  # 4/4 — objetivo no lance 6.0
            "W:W10,17,27:B13,19,21",  # 4/4 — objetivo no lance 6.0
            "W:W9,22,32:B15,19,24",  # 4/4 — objetivo no lance 5.5
            "W:W9,22,24:B13,15,23",  # 4/4 — objetivo no lance 5.5
            "W:W9,18,25:B15,16,23",  # 4/4 — objetivo no lance 5.5
            "W:W9,17,28:B21,22,23",  # 4/4 — objetivo no lance 5.5
            "W:W7,23,26:B15,16,22",  # 4/4 — objetivo no lance 5.5
            "W:W6,22,31:B16,17,21",  # 4/4 — objetivo no lance 5.5
            "W:W5,22,31:B14,17,18",  # 4/4 — objetivo no lance 5.5
            "W:W5,20,22:B14,16,18",  # 4/4 — objetivo no lance 5.5
            "W:W12,17,31:B13,15,21",  # 4/4 — objetivo no lance 5.5
            "W:W11,26,32:B13,22,23",  # 4/4 — objetivo no lance 5.5
            "W:W11,17,18:B14,19,24",  # 4/4 — objetivo no lance 5.5
            "W:W10,18,20:B17,21,22",  # 4/4 — objetivo no lance 5.5
            "W:W9,27,30:B18,20,22",  # 4/4 — objetivo no lance 5.0
            "W:W9,25,28:B13,17,21",  # 4/4 — objetivo no lance 5.0
            "W:W9,25,26:B14,20,22",  # 4/4 — objetivo no lance 5.0
            "W:W9,21,31:B15,17,23",  # 4/4 — objetivo no lance 5.0
            "W:W9,21,26:B15,16,22",  # 4/4 — objetivo no lance 5.0
            "W:W9,19,32:B15,16,18",  # 4/4 — objetivo no lance 5.0
            "W:W9,18,22:B13,17,21",  # 4/4 — objetivo no lance 5.0
            "W:W9,17,19:B13,16,18",  # 4/4 — objetivo no lance 5.0
            "W:W8,23,25:B13,14,19",  # 4/4 — objetivo no lance 5.0
            "W:W7,20,21:B13,16,19",  # 4/4 — objetivo no lance 5.0
            "W:W7,18,32:B14,15,22",  # 4/4 — objetivo no lance 5.0
            "W:W6,21,22:B13,14,18",  # 4/4 — objetivo no lance 5.0
            "W:W6,19,31:B16,21,22",  # 4/4 — objetivo no lance 5.0
            "W:W5,21,24:B17,19,23",  # 4/4 — objetivo no lance 5.0
            "W:W5,19,28:B13,16,17",  # 4/4 — objetivo no lance 5.0
            "W:W5,18,31:B13,15,20",  # 4/4 — objetivo no lance 5.0
            "W:W12,26,27:B17,20,22",  # 4/4 — objetivo no lance 5.0
            "W:W12,21,24:B17,22,23",  # 4/4 — objetivo no lance 5.0
            "W:W12,19,31:B15,18,22",  # 4/4 — objetivo no lance 5.0
            "W:W12,18,28:B13,14,15",  # 4/4 — objetivo no lance 5.0
            "W:W12,18,27:B20,22,24",  # 4/4 — objetivo no lance 5.0
            "W:W12,18,23:B15,17,19",  # 4/4 — objetivo no lance 5.0
            "W:W12,17,31:B14,18,22",  # 4/4 — objetivo no lance 5.0
            "W:W12,17,18:B14,22,24",  # 4/4 — objetivo no lance 5.0
            "W:W11,21,30:B13,19,23",  # 4/4 — objetivo no lance 5.0
            "W:W11,19,29:B16,18,20",  # 4/4 — objetivo no lance 5.0
            "W:W11,19,26:B20,22,24",  # 4/4 — objetivo no lance 5.0
            "W:W11,19,22:B16,17,21",  # 4/4 — objetivo no lance 5.0
            "W:W11,18,28:B13,14,17",  # 4/4 — objetivo no lance 5.0
            "W:W11,17,24:B15,18,21",  # 4/4 — objetivo no lance 5.0
            "W:W10,19,28:B14,16,17",  # 4/4 — objetivo no lance 5.0
            "W:W10,19,26:B14,17,23",  # 4/4 — objetivo no lance 5.0
            "W:W10,17,26:B15,20,23",  # 4/4 — objetivo no lance 5.0
            "W:W9,17,20:B19,21,23",  # 4/4 — objetivo no lance 4.5
            "W:W8,21,27:B15,19,23",  # 4/4 — objetivo no lance 4.5
            "W:W8,18,31:B13,14,15",  # 4/4 — objetivo no lance 4.5
            "W:W7,17,18:B15,19,23",  # 4/4 — objetivo no lance 4.5
            "W:W6,20,27:B19,23,24",  # 4/4 — objetivo no lance 4.5
            "W:W5,20,26:B14,16,19",  # 4/4 — objetivo no lance 4.5
            "W:W5,19,27:B15,16,20",  # 4/4 — objetivo no lance 4.5
            "W:W12,20,24:B14,17,22",  # 4/4 — objetivo no lance 4.5
            "W:W12,18,31:B19,21,22",  # 4/4 — objetivo no lance 4.5
            "W:W11,28,32:B15,18,21",  # 4/4 — objetivo no lance 4.5
            "W:W10,24,27:B15,19,20",  # 4/4 — objetivo no lance 4.5
            "W:W10,24,25:B18,21,22",  # 4/4 — objetivo no lance 4.5
            "W:W10,23,26:B16,20,24",  # 4/4 — objetivo no lance 4.5
            "W:W10,20,30:B18,19,22",  # 4/4 — objetivo no lance 4.5
            "W:W10,17,25:B16,18,24",  # 4/4 — objetivo no lance 4.5
            "W:W9,23,31:B13,15,17",  # 4/4 — objetivo no lance 4.0
            "W:W9,22,30:B15,19,23",  # 4/4 — objetivo no lance 4.0
            "W:W9,20,28:B15,18,19",  # 4/4 — objetivo no lance 4.0
            "W:W8,28,31:B18,21,24",  # 4/4 — objetivo no lance 4.0
            "W:W7,27,31:B18,21,24",  # 4/4 — objetivo no lance 4.0
            "W:W6,19,27:B15,22,23",  # 4/4 — objetivo no lance 4.0
            "W:W5,28,31:B16,17,24",  # 4/4 — objetivo no lance 4.0
            "W:W5,17,22:B16,18,23",  # 4/4 — objetivo no lance 4.0
            "W:W12,29,32:B14,17,22",  # 4/4 — objetivo no lance 4.0
            "W:W12,19,28:B14,18,21",  # 4/4 — objetivo no lance 4.0
            "W:W11,21,29:B18,20,24",  # 4/4 — objetivo no lance 4.0
            "W:W9,22,28:B15,16,23",  # 4/4 — objetivo no lance 3.5
            "W:W8,22,30:B18,20,21",  # 4/4 — objetivo no lance 3.5
            "W:W8,18,29:B14,15,23",  # 4/4 — objetivo no lance 3.5
            "W:W7,18,24:B13,15,21",  # 4/4 — objetivo no lance 3.5
            "W:W7,18,21:B14,20,22",  # 4/4 — objetivo no lance 3.5
            "W:W7,17,25:B14,18,24",  # 4/4 — objetivo no lance 3.5
            "W:W6,18,26:B15,20,22",  # 4/4 — objetivo no lance 3.5
            "W:W6,17,30:B13,14,15",  # 4/4 — objetivo no lance 3.5
            "W:W5,23,31:B19,21,22",  # 4/4 — objetivo no lance 3.5
            "W:W12,27,32:B13,16,19",  # 4/4 — objetivo no lance 3.5
            "W:W12,23,24:B13,17,21",  # 4/4 — objetivo no lance 3.5
            "W:W12,17,22:B13,15,19",  # 4/4 — objetivo no lance 3.5
            "W:W11,30,31:B16,18,20",  # 4/4 — objetivo no lance 3.5
            "W:W8,27,32:B19,21,24",  # 4/4 — objetivo no lance 3.0
            "W:W8,26,32:B16,18,23",  # 4/4 — objetivo no lance 3.0
            "W:W8,23,28:B16,18,20",  # 4/4 — objetivo no lance 3.0
            "W:W8,19,24:B16,21,23",  # 4/4 — objetivo no lance 3.0
            "W:W8,17,18:B14,19,21",  # 4/4 — objetivo no lance 3.0
            "W:W7,26,32:B15,22,23",  # 4/4 — objetivo no lance 3.0
            "W:W7,25,31:B14,17,22",  # 4/4 — objetivo no lance 3.0
            "W:W7,22,29:B13,18,19",  # 4/4 — objetivo no lance 3.0
            "W:W7,21,31:B16,17,19",  # 4/4 — objetivo no lance 3.0
            "W:W7,21,27:B13,22,24",  # 4/4 — objetivo no lance 3.0
            "W:W7,17,29:B14,19,23",  # 4/4 — objetivo no lance 3.0
            "W:W12,29,31:B20,21,22",  # 4/4 — objetivo no lance 3.0
            "W:W12,27,31:B18,20,24",  # 4/4 — objetivo no lance 3.0
            "W:W12,20,24:B14,15,21",  # 4/4 — objetivo no lance 3.0
            "W:W12,17,31:B19,20,21",  # 4/4 — objetivo no lance 3.0
            "W:W11,19,29:B13,18,21",  # 4/4 — objetivo no lance 3.0
            "W:W10,26,29:B16,18,20",  # 4/4 — objetivo no lance 3.0
            "W:W9,17,18:B14,23,24",  # 3/4 — objetivo no lance 9.7
            "W:W12,29,31:B13,17,22",  # 3/4 — objetivo no lance 7.7
            "W:W12,25,31:B21,22,23",  # 3/4 — objetivo no lance 7.7
            "W:W9,21,30:B17,19,23",  # 3/4 — objetivo no lance 6.3
            "W:W9,19,26:B15,20,21",  # 3/4 — objetivo no lance 6.3
            "W:W9,27,32:B17,20,24",  # 3/4 — objetivo no lance 5.0
            "W:W9,31,32:B13,14,15",  # 3/4 — objetivo no lance 4.3
            "W:W10,27,29:B13,18,21",  # 3/4 — objetivo no lance 3.7
            "W:W5,27,30:B13,22,24",  # 3/4 — objetivo no lance 3.0
            "W:W10,25,28:B16,19,24",  # 3/4 — objetivo no lance 3.0
            "W:W10,21,30:B13,20,23",  # 3/4 — objetivo no lance 3.0
        ),
    ),
    "damas_capturar_multipla": Receita(
        nu_tipo_desafio=8,
        co_tipo_desafio="damas_capturar_multipla",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoCapturaMultipla",
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "lances_do_jogador", "n": p["lances"]},
            "clausulas": [_medida("maior_captura", "maior_ou_igual", p["pecas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "pecas": p["pecas"],
            "lances": p["lances"],
            "personagem": personagem,
        },
        # Posicoes com material suficiente para uma captura encadeada aparecer
        # depois de um ou dois lances.
        #
        # ⚠️ **Este tipo resiste a geracao automatica, e o motivo e o jogo, nao a
        # ferramenta.** A caçada de 11/09/2026 mediu **295** posicoes sinteticas e
        # aprovou **oito** (2,7%): 185 nunca cumpriram dentro do teto e 73 ja
        # nasciam com a captura dupla armada. Coroar aprovou 167 de 300.
        #
        # ⛔ **E TRES dos quatro fundadores sairam**, por medicao: eles ja tinham
        # a cadeia armada no primeiro lance, nas quatro modalidades — o desafio
        # duraria um toque. Ver `job/moldes_de_damas.py`.
        #
        # A razao e que **capturar duas em sequencia e um objetivo ADVERSARIAL**:
        # um Sagaz do outro lado nao concede captura encadeada, e a captura
        # obrigatoria das damas e justamente o que ele usa para nao conceder. Ou
        # a posicao ja tem a cadeia armada — e ai o desafio dura um lance — ou
        # ela nunca se forma. Coroar nao tem esse problema: o adversario pode
        # atrapalhar, mas nao pode proibir que uma pedra avance.
        moldes=(
            # ── O fundador que SOBROU, escrito a mao em 09/09/2026 ──────────
            #
            # ⛔ Eram quatro: os outros tres ja tinham a captura dupla armada no
            # primeiro lance, nas quatro modalidades.
            "W:W25,29,31:B13,17,21,2",
            # ── Medidos em 11/09/2026 pela caçada de 295 candidatas ─────────
            #
            # ⚠️ **Oito de 295, e os oito servem às QUATRO modalidades no lance 3.**
            # A primeira caçada, de 30 candidatas, achara um — e este um está
            # aqui dentro, medido de novo.
            "W:W27,29,32:B18,19,22,26",  # 4/4 — objetivo no lance 3.0
            "W:W26,29,31:B9,14,17,19",  # 4/4 — objetivo no lance 3.0
            "W:W26,29,31:B14,17,18,19",  # 4/4 — objetivo no lance 3.0
            "W:W26,27,30:B10,15,18,19",  # 4/4 — objetivo no lance 3.0
            "W:W25,29,32:B17,18,21,26",  # 4/4 — objetivo no lance 3.0
            "W:W25,29,31:B16,17,18,21",  # 4/4 — objetivo no lance 3.0
            "W:W25,28,30:B9,13,17,18",  # 4/4 — objetivo no lance 3.0
            "W:W25,26,29:B9,14,17,18",  # 4/4 — objetivo no lance 3.0
        ),
    ),
}


def receita_de(co_tipo_desafio: str) -> Receita:
    """A receita de um tipo. Falha alto se ele nao tiver uma.

    Raises:
        TipoSemReceita: sempre que o tipo nao estiver em [RECEITAS].
    """
    if co_tipo_desafio not in RECEITAS:
        raise TipoSemReceita(
            f"o tipo {co_tipo_desafio!r} nao tem receita. ⛔ Tipo sem receita nao "
            "e publicavel: o desafio sairia com uma linha de chegada que ninguem "
            "escreveu, e o julgamento devolveria 'nao cumpriu' para todo mundo. "
            f"Os que tem receita hoje: {sorted(RECEITAS)}"
        )
    return RECEITAS[co_tipo_desafio]


def tipos_do_jogo(co_jogo: str) -> list[str]:
    """Os tipos publicaveis daquele jogo, em ordem estavel.

    ⚠️ Ordem estavel importa: e ela que faz o rodizio ser reproduzivel, e um
    rodizio que muda de ordem a cada execucao publicaria o mesmo tipo dois dias
    seguidos de vez em quando.
    """
    return sorted(
        codigo for codigo, receita in RECEITAS.items() if receita.co_jogo == co_jogo
    )

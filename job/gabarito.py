"""O GABARITO de um desafio — `js_solucao` (RF-DES-196, T032).

═══════════════════════════════════════════════════════════════════════════
⛔ O GABARITO NAO JULGA NINGUEM
═══════════════════════════════════════════════════════════════════════════

A pessoa e julgada pelas **clausulas** de `js_chegada`, contra os lances que ela
jogou. Julgar por comparacao com o gabarito daria a *"feche 4 caixas"* uma
resposta certa so — que ela nao tem.

O gabarito serve a **tres** coisas, e nenhuma delas e julgar:

  1. a linha de referencia do quadro do dia;
  2. o gabarito animado de D+1;
  3. ⚠️ **a prova de que o desafio TEM solucao** — se o job nao achou uma, o
     desafio nao e publicado.

═══════════════════════════════════════════════════════════════════════════
⚠️ O VOCABULARIO E O DO LOG, E ISSO E O QUE FAZ O REPLAY EXISTIR
═══════════════════════════════════════════════════════════════════════════

Cada lance sai no mesmo formato de `jogo_pontinhos.tb002_jogada.co_aresta` e de
`jogo_damas.tb002_jogada.co_lance`. E isso que permite ao gabarito animado usar
**o mesmo tocador de replay** da partida, sem um segundo caminho de codigo.

⚠️ Um formato proprio aqui obrigaria a escrever um segundo tocador — e dois
caminhos para a mesma coisa e como as tres telas de fim de partida divergiram.

═══════════════════════════════════════════════════════════════════════════
⚠️ A BUSCA E SEMPRE DO SAGAZ (RF-DES-019a)
═══════════════════════════════════════════════════════════════════════════

E o **unico nivel reproduzivel**: os outros tres tem `epsilon` — jogam errado de
proposito, com sorteio. Um gabarito gerado pela Cacau seria diferente a cada
execucao, e "a solucao de referencia" deixaria de ser uma referencia.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from motores.nucleo.chegada import LinhaDeChegada
from motores.nucleo.medidor_por_fita import CUMPRIU

#: A versao do formato de `js_solucao`.
VERSAO = 1

#: De onde a solucao saiu. Vocabulario fechado, e por enquanto tem um valor so.
#:
#: ⚠️ Ele existe desde ja porque o dia em que um gabarito vier de outra fonte
#: (uma base de finais, um oraculo, a mao de alguem) e o dia em que sera preciso
#: saber quais desafios antigos vieram de onde — e ai o campo teria de nascer
#: nulo em todas as linhas ja gravadas.
ORIGEM_BUSCA_SAGAZ = "busca_sagaz"


class SemSolucao(ValueError):
    """O job nao encontrou solucao para o candidato.

    ⚠️ **Nao e erro: e resposta.** Um candidato sem solucao simplesmente nao vai
    ao ar — o gerador o descarta e tenta outro. Publicar um desafio insoluvel
    seria pior que nao publicar nenhum.
    """


def montar(
    lances: Sequence[Mapping[str, Any]],
    *,
    lance_chave: int,
    co_origem: str = ORIGEM_BUSCA_SAGAZ,
) -> dict[str, Any]:
    """Monta `js_solucao` a partir da fita que resolve o desafio.

    Args:
        lances: a fita, cada item `{"n", "jogador", "lance"}` — o vocabulario do
            log. ⚠️ Ela inclui os lances do **adversario**: sem eles a sequencia
            nao e reproduzivel, e o replay mostraria a pessoa jogando sozinha.
            ⚠️ **Um item pode trazer `fen`**, a posicao depois daquele lance; ela
            vira a lista `posicoes`, que o painel de curadoria desenha.
        lance_chave: qual lance decide. E o que o Raio-X destaca.
        co_origem: de onde a solucao veio.

    Raises:
        SemSolucao: se a fita estiver vazia.
        ValueError: se `lance_chave` apontar para fora da fita.
    """
    if not lances:
        raise SemSolucao("gabarito sem lance nenhum nao e gabarito")
    if not 1 <= lance_chave <= len(lances):
        raise ValueError(
            f"lance_chave {lance_chave} fora da fita de {len(lances)} lances"
        )

    js_solucao: dict[str, Any] = {
        "versao": VERSAO,
        "lances": [
            # ⚠️ `co_acao` so entra quando existe — ela e o motivo do lance
            # (`cnn_epsilon_aleatorio` e um erro de proposito), e o motor das
            # damas ainda nao a informa.
            {
                "n": n,
                "jogador": lance["jogador"],
                "lance": lance["lance"],
                **({"co_acao": lance["co_acao"]} if lance.get("co_acao") else {}),
            }
            for n, lance in enumerate(lances, start=1)
        ],
        "lance_chave": lance_chave,
        "co_origem": co_origem,
    }

    # ── ⚠️ AS POSICOES, quando o jogo tem uma por lance ──────────────────────
    #
    # ⚠️ **Aditivo de proposito, e por isso nao houve migracao:** `js_solucao` e
    # `JSONB`, e a chave nova nasce ausente nas linhas ja gravadas. Quem le
    # precisa aguentar as duas formas — o painel desenha a sequencia quando ha
    # `posicoes` e cai na lista de lances quando nao ha.
    #
    # ⛔ **A chave so aparece quando TODOS os lances trouxeram posicao.** Uma
    # sequencia com buraco seria pior que nenhuma: o painel desenharia um salto
    # como se fosse um lance, e quem estivesse curando aprovaria uma solucao que
    # nao existe.
    posicoes = [
        {"n": n, "fen": lance["fen"]}
        for n, lance in enumerate(lances, start=1)
        if lance.get("fen")
    ]
    if len(posicoes) == len(lances):
        js_solucao["posicoes"] = posicoes

    return js_solucao


def nu_lances_solucao(js_solucao: Mapping[str, Any]) -> int:
    """O tamanho da solucao, que vira **coluna** em `tb001_desafio`.

    ⚠️ **Duplicado de proposito.** E o unico campo do gabarito pelo qual o job
    filtra e ordena candidatos (*"os que se resolvem em ate 4 lances"*), e um
    indice dentro de JSONB para isso custaria mais que a coluna.

    ⚠️ E como e duplicacao, ela precisa de guarda: quem grava confere que a coluna
    bate com o JSON, e o teste desta tarefa faz isso.
    """
    return len(js_solucao["lances"])


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ `lance_chave_padrao` FOI REMOVIDA em 11/09/2026 — era codigo morto
# ═══════════════════════════════════════════════════════════════════════════
#
# Ela prometia descobrir o lance da virada perguntando "a partir de quando o
# objetivo vale?", e ninguem a chamava: o gerador ja recebe o numero pronto do
# julgamento (`gerador.py`, `julgamento.nu_lance_cumpre_desafio or numero`).
#
# ⚠️ **A prova de que nunca foi exercitada estava nela mesma:** a docstring
# declarava um parametro `(quantos) -> Julgamento` e o corpo chamava a funcao
# **sem argumento nenhum**. Uma unica execucao teria levantado `TypeError`.
#
# ⛔ **Codigo morto com docstring divergente e pior que codigo morto**: quem
# precisasse do lance chave um dia leria a docstring, escreveria o chamador
# conforme ela, e descobriria a divergencia em producao.
#
# ⚠️ Ela apareceu numa varredura por funcoes publicas **sem uma unica mencao nos
# testes** — a mesma varredura que nasceu do defeito de `tentativa_com_motor`,
# que aplicava o nivel errado aos dois lados do tabuleiro por meses.


def conferir(js_solucao: Mapping[str, Any], *, nu_lances_gravado: int) -> None:
    """A coluna bate com o JSON?

    ⚠️ Duplicacao sem guarda envelhece torta: alguem regrava o gabarito e esquece
    a coluna, e a curadoria passa a filtrar por um numero que nao descreve mais
    nada.

    Raises:
        ValueError: quando divergem, ou quando o formato nao e o esperado.
    """
    if js_solucao.get("versao") != VERSAO:
        raise ValueError(
            f"js_solucao versao {js_solucao.get('versao')!r}; esperada {VERSAO}"
        )
    if not js_solucao.get("lances"):
        raise ValueError("js_solucao sem lances")

    calculado = nu_lances_solucao(js_solucao)
    if calculado != nu_lances_gravado:
        raise ValueError(
            f"nu_lances_solucao gravado ({nu_lances_gravado}) nao bate com o "
            f"gabarito ({calculado} lances). ⛔ Nao publique este desafio."
        )

    chave = js_solucao.get("lance_chave")
    if not isinstance(chave, int) or not 1 <= chave <= calculado:
        raise ValueError(
            f"lance_chave {chave!r} fora da fita de {calculado} lances"
        )

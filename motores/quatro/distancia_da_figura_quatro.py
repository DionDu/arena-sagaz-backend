"""A DISTANCIA de uma figura no tabuleiro do Quatro (T147/T148 da spec 010).

Quantas casas ainda precisam ser ocupadas para um desenho da clausula `figura`
existir no tabuleiro, no melhor lugar. E a conta que o gerador usa para o prazo
do "Forme a figura" (`M = distancia + folga`, `job/figuras_quatro.py`) e a que o
perseguidor usa para escolher o lance (`perseguir_objetivo_quatro.py`).

⚠️ **Mora em `motores/`, e nao no catalogo do job**, porque o perseguidor e do
motor e `motores/` nao importa nada de `job/` (o job e quem usa o motor, nunca o
contrario). O catalogo (`job/figuras_quatro.py`) delega para ca.

O que conta como uma casa a ocupar, em cada lugar onde a figura cabe sem
conflito de cor:

- as `X` vazias (pecas da pessoa que faltam);
- as `O` vazias (a peca que o adversario precisa por ali);
- os **apoios**: as casas vazias, fora da figura, embaixo de uma peca dela na
  mesma coluna (com gravidade, a peca so para em cima de outra).

⚠️ E uma medida do trabalho, e nao uma prova de que a figura e alcancavel: o
adversario pode tapar uma casa.
"""

from __future__ import annotations

from typing import Sequence

from motores.quatro import contrato_quatro
from motores.quatro.motor_quatro import TabuleiroQuatro


def colunas(desenho: Sequence[str]) -> list[str]:
    """O desenho lido por coluna, cada uma de CIMA para BAIXO."""
    return ["".join(linha[j] for linha in desenho) for j in range(len(desenho[0]))]


def desenhos(desenho: Sequence[str], espelhar: bool) -> list[tuple[str, ...]]:
    """O desenho, e o espelho dele (esquerda para a direita) quando vale."""
    saida = [tuple(desenho)]
    if espelhar:
        # `linha[::-1]` e a linha de tras para a frente: o espelho horizontal.
        saida.append(tuple(linha[::-1] for linha in desenho))
    return saida


def custo_do_lugar(
    desenho: Sequence[str],
    tabuleiro: TabuleiroQuatro,
    quem: int,
    coluna_esquerda: int,
    linha_de_baixo: int,
) -> int | None:
    """Quantas casas faltam para a figura existir NESTE lugar; `None` = conflito.

    `coluna_esquerda` e `linha_de_baixo` sao as do tabuleiro (1-based, a linha 1
    no chao) onde fica o canto de baixo e da esquerda da figura. [quem] e o
    dono dos `X` (`+1`/`-1`).
    """
    altura = len(desenho)
    custo = 0
    for j, coluna in enumerate(colunas(desenho)):
        c = coluna_esquerda + j
        # A linha do tabuleiro de cada casa da coluna da figura: a de cima
        # (indice 0) e a mais alta.
        linha_de = {i: linha_de_baixo + (altura - 1 - i) for i in range(altura)}
        casas_da_figura = set()
        topo_com_peca = None
        for i, simbolo in enumerate(coluna):
            linha = linha_de[i]
            dono = tabuleiro.peca((c, linha))
            if simbolo == "X":
                if dono == -quem:
                    return None
                custo += dono == 0
            elif simbolo == "O":
                if dono == quem:
                    return None
                custo += dono == 0
            elif simbolo == "_":
                if dono != 0:
                    return None
            if simbolo in "XO":
                casas_da_figura.add(linha)
                topo_com_peca = linha if topo_com_peca is None else max(topo_com_peca, linha)
        # Os apoios: toda casa vazia abaixo da peca mais alta da coluna que nao
        # e casa da figura (as da figura ja foram contadas acima).
        if topo_com_peca is not None:
            custo += sum(
                1
                for linha in range(1, topo_com_peca)
                if linha not in casas_da_figura and tabuleiro.peca((c, linha)) == 0
            )
    return custo


def custos(
    desenho: Sequence[str],
    espelhar: bool,
    tabuleiro: TabuleiroQuatro,
    dimensoes: contrato_quatro.DimensoesQuatro,
    quem: int,
) -> list[int]:
    """O custo de CADA lugar onde o [desenho] cabe sem conflito, com os `X` de [quem].

    Vazio quando a figura nao cabe em lugar nenhum. ⚠️ Um lugar por posicao do
    canto da figura (e por espelho, quando vale): o mesmo conjunto de casas pode
    aparecer duas vezes numa figura simetrica com `espelhar`, e quem soma os
    custos (o perseguidor) aceita isso.
    """
    saida: list[int] = []
    for d in desenhos(desenho, espelhar):
        largura, altura = len(d[0]), len(d)
        for coluna_esquerda in range(1, dimensoes.largura - largura + 2):
            for linha_de_baixo in range(1, dimensoes.altura - altura + 2):
                custo = custo_do_lugar(d, tabuleiro, quem, coluna_esquerda, linha_de_baixo)
                if custo is not None:
                    saida.append(custo)
    return saida


def distancia(
    desenho: Sequence[str],
    espelhar: bool,
    tabuleiro: TabuleiroQuatro,
    dimensoes: contrato_quatro.DimensoesQuatro,
    quem: int,
) -> int | None:
    """A menor distancia do [desenho] no [tabuleiro], com os `X` de [quem].

    Returns:
        O menor custo entre todos os lugares sem conflito ([custos]), ou `None`
        quando a figura nao cabe em lugar nenhum sem conflito - ela nunca mais
        pode ser formada nesta partida.

    ⚠️ Zero quer dizer que a figura JA esta no tabuleiro. ⚠️ [quem] vem
    explicito, e nao da vez do tabuleiro: o perseguidor mede o tabuleiro DEPOIS
    do lance da pessoa, quando a vez ja e do adversario.
    """
    todos = custos(desenho, espelhar, tabuleiro, dimensoes, quem)
    return min(todos) if todos else None

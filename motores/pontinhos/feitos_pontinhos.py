"""As MEDIDAS que uma partida de Pontinhos produz (T029).

⚠️ **Feito e medida, nunca XP** (RF-DES-170). Este arquivo devolve
`caixas_fechadas = 4`; jamais `+28 XP`. Quem converte medida em pontos e a
**colecao** que agrupa o desafio, e ela mora noutra camada.

⚠️ **E aqui nao ha regra de Pontinhos.** Quem sabe quando uma caixa fecha e o
motor (`motor_pontinhos.EstadoPontinhos`), que e cópia byte-idêntica do
laboratório. Este arquivo so **le** o placar que o motor calculou e o traduz para
as chaves do catálogo do hub.

⚠️ **As chaves sao as do catálogo, e nao inventadas aqui**: `caixas_fechadas`,
`caixas_do_adversario`, `lances_do_jogador`. Uma chave a mais que o catálogo nao
conheça viraria uma medida que ninguém pontua e ninguém mostra — e o cadeado 4
existe para que isso nao aconteça em silêncio.
"""

from __future__ import annotations

from .motor_pontinhos import EstadoPontinhos

#: Quantas caixas o tabuleiro `pequeno` tem, no total.
#:
#: E o denominador de *"fechou tudo"*, e o que a T030 usa para saber se uma
#: chegada encerra a partida: exigir 12 de 12 nao deixa lance por jogar; exigir
#: 4 de 12 deixa 8 caixas em aberto.
CAIXAS_DO_TABULEIRO_PEQUENO = 12


def medir(
    antes: EstadoPontinhos,
    depois: EstadoPontinhos,
    *,
    jogador: int,
    lances_do_jogador: int,
) -> dict[str, float]:
    """As medidas do trecho entre `antes` e `depois`, do ponto de vista de `jogador`.

    Args:
        antes: o estado no inicio da janela — normalmente a posição inicial do
            desafio.
        depois: o estado no fim da janela.
        jogador: `+1` ou `-1`, na convenção do log de partidas.
        lances_do_jogador: quantos lances daquele jogador entraram na janela.

    Returns:
        Um dicionário de chave do catálogo para número.

    ⚠️ **A medida e do TRECHO, nao do tabuleiro.** Um desafio comeca de uma
    posição que já tem caixas fechadas; contar o placar absoluto premiaria a
    pessoa pelas caixas que o gerador fechou antes de ela chegar. Por isso a
    conta e sempre `depois - antes`.
    """
    adversario = -jogador
    placar_antes = antes.placar
    placar_depois = depois.placar

    return {
        "caixas_fechadas": placar_depois[jogador] - placar_antes[jogador],
        "caixas_do_adversario": (
            placar_depois[adversario] - placar_antes[adversario]
        ),
        "lances_do_jogador": lances_do_jogador,
    }

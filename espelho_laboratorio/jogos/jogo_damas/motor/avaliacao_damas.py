"""Avaliação escrita à mão: quanto vale uma posição, sem saber como ela termina.

O papel desta peça
------------------
A busca precisa parar em algum lugar. Aos 14 lances à frente o jogo raramente
acabou — então o motor olha o tabuleiro e precisa dar uma **nota** a ele, sem
saber o final. Essa nota é a avaliação, e ela é o olho do motor:

> A busca é a capacidade de **calcular**. A avaliação é a capacidade de
> **julgar**. Um motor com busca profunda e avaliação ruim é um contador rápido
> que não sabe o que está contando.

Por que esta versão é deliberadamente modesta
---------------------------------------------
Ela é o **piso de comparação**, não a resposta final. A etapa 7 do plano troca
estas regrinhas por notas *aprendidas* de milhares de partidas (as tabelas de
padrões), e o critério para aquele ramo se pagar é ganhar desta aqui por pelo
menos 100 Elo. Uma avaliação manual caprichada demais atrapalharia a medição —
e ajuste manual de peso é poço sem fundo, porque cada regra nova exige reajustar
todas as outras.

Então aqui vale o essencial e nada mais: material, avanço, borda, grande
diagonal e fileira de fundo. Cada peso tem um comentário dizendo **por que** ele
existe, para que a etapa 7 tenha contra o que comparar.

Convenção de sinal
------------------
`avaliar` devolve a nota **do ponto de vista de quem tem a vez** — positivo é
bom para quem vai jogar. É a convenção que a busca *negamax* espera, e ela evita
o erro mais comum de motor de jogo: um sinal trocado num nível ímpar da árvore,
que faz o motor jogar contra si mesmo em metade das posições.
"""
from __future__ import annotations

from dataclasses import dataclass

from jogos.jogo_damas.motor.tabuleiro_damas import (
    GRANDE_DIAGONAL,
    LADO,
    N_CASAS,
    CASAS_DE_COROACAO,
    Cor,
    Peca,
    Tabuleiro,
    linha_coluna,
)

VITORIA = 1_000_000
"""Nota de uma posição ganha. Muito acima de qualquer soma de peças.

Precisa ser grande o bastante para que nenhuma vantagem posicional imaginável
chegue perto — senão o motor troca um mate garantido por três pedras.
"""


@dataclass(frozen=True)
class PesosAvaliacao:
    """Os pesos da avaliação manual, em centésimos de pedra.

    A unidade é a **pedra = 100**. É a convenção de motores de tabuleiro, e ela
    existe para os ajustes finos caberem em números inteiros: "+12" quer dizer
    "doze centésimos de pedra", que é um ajuste fino de verdade.
    """

    pedra: int = 100
    """A unidade de conta."""

    dama: int = 300
    """Uma dama vale ~3 pedras.

    Não é exato — em final de jogo ela vale muito mais, no meio-jogo menos. Um
    valor único é aproximação grosseira **de propósito**: refinar isso à mão é
    o começo do poço sem fundo que a etapa 7 existe para evitar.
    """

    avanco_por_fileira: int = 6
    """Prêmio por cada fileira que uma pedra já avançou.

    Sem isto o motor não tem motivo nenhum para avançar: material igual, nota
    igual, e ele fica embaralhando. É o empurrão mínimo em direção à coroação.
    Vale só para pedra — dama já vai e volta.
    """

    coluna_de_borda: int = 8
    """Prêmio por estar na coluna 0 ou 7.

    Peça encostada na borda **não pode ser capturada**: não existe casa do outro
    lado para o adversário pousar. É a vantagem posicional mais barata de
    calcular em damas e uma das mais reais.
    """

    grande_diagonal: int = 12
    """Prêmio por ocupar a grande diagonal (as 8 casas de 4 a 29).

    É a diagonal mais longa do tabuleiro — quem a domina alcança mais casas com
    menos peças. A mesma diagonal aparece no art. 100 das Regras Oficiais, que
    declara empate certos finais com a dama solitária nela.
    """

    fileira_de_fundo: int = 10
    """Prêmio por manter peça na PRÓPRIA fileira inicial.

    Peça no fundo não faz nada de ofensivo, mas fecha a casa onde o adversário
    coroaria. Trocar isso cedo demais é erro clássico de iniciante — e de motor
    que só conta material.
    """


PESOS_PADRAO = PesosAvaliacao()


def _pontuar_lado(tabuleiro: Tabuleiro, cor: Cor, pesos: PesosAvaliacao) -> int:
    """Soma tudo o que uma cor tem a favor, em centésimos de pedra."""
    e_branca = cor is Cor.BRANCAS
    pedra_da_cor = Peca.PEDRA_BRANCA if e_branca else Peca.PEDRA_PRETA
    dama_da_cor = Peca.DAMA_BRANCA if e_branca else Peca.DAMA_PRETA
    # A fileira de fundo de uma cor é a fileira de coroação da OUTRA — é para lá
    # que o adversário está indo, e é por isso que segurá-la vale alguma coisa.
    fundo = CASAS_DE_COROACAO[Cor.PRETAS if e_branca else Cor.BRANCAS]

    total = 0
    for casa in range(1, N_CASAS + 1):
        conteudo = tabuleiro.ler(casa)
        if conteudo is not pedra_da_cor and conteudo is not dama_da_cor:
            continue

        linha, coluna = linha_coluna(casa)

        if conteudo is pedra_da_cor:
            total += pesos.pedra
            # Quanto a pedra já andou em direção à coroação. Brancas sobem
            # (linha diminui), pretas descem — daí a conta espelhada.
            avancou = (LADO - 1 - linha) if e_branca else linha
            total += avancou * pesos.avanco_por_fileira
            if casa in fundo:
                total += pesos.fileira_de_fundo
        else:
            total += pesos.dama

        if coluna == 0 or coluna == LADO - 1:
            total += pesos.coluna_de_borda
        if casa in GRANDE_DIAGONAL:
            total += pesos.grande_diagonal

    return total


def avaliar(tabuleiro: Tabuleiro, pesos: PesosAvaliacao = PESOS_PADRAO) -> int:
    """A nota da posição, **do ponto de vista de quem tem a vez**.

    Positivo é bom para quem vai jogar; negativo, ruim. Zero é equilíbrio.

    Esta função **não** sabe se a partida acabou — quem descobre isso é a busca,
    ao ver que não sobrou lance legal. Aqui só se julga o material e a forma.
    """
    absoluto = (
        _pontuar_lado(tabuleiro, Cor.BRANCAS, pesos)
        - _pontuar_lado(tabuleiro, Cor.PRETAS, pesos)
    )
    return absoluto if tabuleiro.vez is Cor.BRANCAS else -absoluto


def avaliar_absoluto(tabuleiro: Tabuleiro, pesos: PesosAvaliacao = PESOS_PADRAO) -> int:
    """A nota **sempre do ponto de vista das brancas**, para relatório e figura.

    Existe separada porque a convenção da busca (ponto de vista de quem joga)
    confunde na hora de ler um log: a mesma posição troca de sinal conforme a
    vez. Para mostrar a uma pessoa, um referencial fixo é mais honesto.
    """
    return (
        _pontuar_lado(tabuleiro, Cor.BRANCAS, pesos)
        - _pontuar_lado(tabuleiro, Cor.PRETAS, pesos)
    )


def explicar(tabuleiro: Tabuleiro, pesos: PesosAvaliacao = PESOS_PADRAO) -> dict[str, int]:
    """Decompõe a nota em parcelas, para depurar e para desenhar.

    Devolve o saldo (brancas menos pretas) de cada componente. É a versão manual
    do que, na etapa 7, virará o mapa de calor das tabelas de padrões: sem
    conseguir ver *de onde vem* a nota, ajustar avaliação é chute.
    """
    def parcela(pesos_isolados: PesosAvaliacao) -> int:
        return (
            _pontuar_lado(tabuleiro, Cor.BRANCAS, pesos_isolados)
            - _pontuar_lado(tabuleiro, Cor.PRETAS, pesos_isolados)
        )

    zerado = PesosAvaliacao(0, 0, 0, 0, 0, 0)
    return {
        "material": parcela(PesosAvaliacao(pedra=pesos.pedra, dama=pesos.dama,
                                           avanco_por_fileira=0, coluna_de_borda=0,
                                           grande_diagonal=0, fileira_de_fundo=0)),
        "avanco": parcela(PesosAvaliacao(0, 0, pesos.avanco_por_fileira, 0, 0, 0)),
        "borda": parcela(PesosAvaliacao(0, 0, 0, pesos.coluna_de_borda, 0, 0)),
        "grande_diagonal": parcela(PesosAvaliacao(0, 0, 0, 0, pesos.grande_diagonal, 0)),
        "fileira_de_fundo": parcela(PesosAvaliacao(0, 0, 0, 0, 0, pesos.fileira_de_fundo)),
        "total": parcela(pesos) if pesos != zerado else 0,
    }

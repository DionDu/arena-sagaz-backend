"""A outra forma de escrever uma casa: ``a1``, ``h8`` — e como ela vira 1..32.

Por que existem duas numerações
-------------------------------
O motor inteiro fala em **números de casa** (1 a 32), porque é o que cabe num
vetor e o que o FEN de damas usa. Mas o mundo do jogo escreve casa como no
xadrez: uma letra de coluna e um número de fileira, ``a1`` a ``h8``. É assim que
estão escritos os regulamentos da FMJD, as tabelas de sorteio de abertura e
praticamente toda literatura de damas russas e brasileiras.

Traduzir entre as duas é uma conta de duas linhas — mas é uma conta que, feita
errada, **espelha o tabuleiro** e transforma cada abertura oficial numa abertura
inventada, sem que nada dê erro. Por isso ela mora aqui, num só lugar, com o
teste que a prende à posição inicial publicada no art. 9.4 da FMJD.

O que amarra a conta (e por que ela não pode ser "quase certa")
---------------------------------------------------------------
Duas frases do regulamento decidem tudo:

- **art. 9.2** — "a letra ``a`` designa a coluna mais à esquerda para quem joga
  de brancas; a fileira 1 é a mais próxima de quem joga de brancas".
- **art. 9.4** — a posição inicial escrita casa por casa: brancas em
  ``a1, a3, b2, c1, c3, d2, e1, e3, f2, g1, g3, h2``; pretas em
  ``a7, b6, b8, c7, d6, d8, e7, f6, f8, g7, h6, h8``.

A nossa numeração conta as casas escuras da esquerda para a direita, de cima
para baixo, com a **fileira 0 no topo** (onde ficam as pretas). Logo:

    linha_nossa  = 8 - fileira_algebrica      (a fileira 1 é a de baixo)
    coluna_nossa = letra - 'a'                (a coluna 'a' é a da esquerda)

Há uma armadilha que a conta resolve sozinha: se alguém trocasse ``a`` por ``h``
(espelhando o tabuleiro), ``a1`` cairia numa casa **clara** — e a função
levantaria erro em vez de devolver um número plausível. A paridade do xadrezado
é a testemunha: ela prova qual das duas orientações é a certa.

A notação abreviada das tabelas de abertura
-------------------------------------------
As tabelas de sorteio da FMJD não escrevem ``a3-b4``: escrevem ``ab4``. O token
tem três caracteres — **coluna de origem**, coluna de destino, fileira de
destino — e omite a fileira de origem, porque ela é dedutível: na posição em que
o lance é jogado só existe uma peça daquela coluna que alcance aquele destino.

Aqui essa dedução é feita **perguntando ao gerador**, nunca reimplementando
regra: pega-se a lista de lances legais e procura-se o único cujo destino é a
casa indicada e cuja origem está na coluna indicada. Se houver zero ou mais de
um, a função levanta erro — porque nesse caso o texto **não** determina o lance,
e adivinhar produziria uma abertura falsa com cara de oficial.
"""
from __future__ import annotations

from jogos.jogo_damas.motor.regras_damas import (
    BRASILEIRAS,
    Lance,
    Regulamento,
    gerar_lances,
)
from jogos.jogo_damas.motor.tabuleiro_damas import (
    CASAS_POR_FILEIRA,
    LADO,
    Tabuleiro,
    linha_coluna,
    numero_da_casa,
)

COLUNAS = "abcdefgh"
"""As oito colunas, da esquerda para a direita **do lado das brancas** (art. 9.2)."""


class NotacaoInvalida(ValueError):
    """O texto não descreve uma casa ou um lance desta posição.

    É um erro e não um `None` de propósito: quem lê uma tabela de aberturas
    oficial prefere parar na linha errada a seguir com uma abertura inventada.
    """


def casa_de_algebrica(texto: str) -> int:
    """``"a1"`` → 29. Levanta `NotacaoInvalida` se a casa for clara ou não existir.

    A recusa das casas claras não é preciosismo: ela é a **prova** de que a
    orientação está certa. Um tabuleiro espelhado faria ``a1`` cair numa casa
    clara, e o erro apareceria aqui em vez de silenciosamente virar outra casa.
    """
    texto = texto.strip().lower()
    if len(texto) != 2 or texto[0] not in COLUNAS or not texto[1].isdigit():
        raise NotacaoInvalida(f"{texto!r} não é uma casa algébrica (a1..h8)")

    fileira = int(texto[1])
    if not 1 <= fileira <= LADO:
        raise NotacaoInvalida(f"{texto!r} está fora do tabuleiro")

    # A fileira 1 é a de baixo para as brancas; a nossa linha 0 é a de cima.
    linha = LADO - fileira
    coluna = COLUNAS.index(texto[0])

    casa = numero_da_casa(linha, coluna)
    if casa is None:
        raise NotacaoInvalida(
            f"{texto!r} é uma casa clara — nenhuma peça pode pisar nela"
        )
    return casa


def algebrica_de_casa(casa: int) -> str:
    """29 → ``"a1"``. O caminho de volta, para escrever posição e lance."""
    if not 1 <= casa <= LADO * LADO // 2:
        raise NotacaoInvalida(f"{casa} não é uma casa jogável (1 a 32)")
    linha, coluna = linha_coluna(casa)
    return f"{COLUNAS[coluna]}{LADO - linha}"


def casa_da_numeracao_portuguesa(casa_do_documento: int) -> int:
    """A casa que o regulamento português chama de `k`, no **nosso** número.

    Duas numerações, e elas não são simplesmente invertidas
    -------------------------------------------------------
    O art. 2.2 da Federação Portuguesa de Damas numera as casas *"beginning from
    the white player's side (lower right corner)"* — a casa 1 fica no canto
    **inferior direito**, e a contagem sobe da direita para a esquerda. A nossa
    corre ao contrário: casa 1 no canto **superior esquerdo**, da esquerda para a
    direita.

    Só isso já sugeriria `33 - k`, e foi o que este projeto registrou por engano
    até 2026-07-29. **Está errado**, e o motivo é o art. 1.2: lá a diagonal longa
    escura começa **à direita** de cada jogador; aqui, à esquerda. Os dois
    tabuleiros são **espelhos horizontais** um do outro, e por isso as casas
    jogáveis caem em colunas de paridade trocada.

    Uma conversão que ignora o espelho quebra a vizinhança: as casas 28 e 23 do
    documento são vizinhas na diagonal, mas `33-28 = 5` e `33-23 = 10` não são —
    ficam a três colunas de distância. Traduzir uma abertura assim produziria
    lances impossíveis sem que nada desse erro.

    A conta certa
    -------------
    Espelha-se a coluna (`c → 7-c`) e mantém-se a fileira. Em números, isso
    equivale a inverter a **ordem das fileiras** preservando a posição dentro de
    cada uma::

        b = (k - 1) % 4                 # a posição dentro da fileira, 0 a 3
        nossa = 29 - k + 2*b + 1        # …e a fileira lida de trás para frente

    O teste `test_notacao_algebrica_damas.py` não confia nesta fórmula: ele a
    confere **casa a casa contra a geometria**, exigindo que casas vizinhas lá
    continuem vizinhas aqui.

    >>> casa_da_numeracao_portuguesa(32)     # o canto do Rio, lá
    4
    >>> casa_da_numeracao_portuguesa(1)      # o outro canto do Rio
    29
    """
    if not 1 <= casa_do_documento <= LADO * LADO // 2:
        raise NotacaoInvalida(
            f"{casa_do_documento} não é casa da numeração portuguesa (1 a 32)"
        )
    # Onde a casa está no tabuleiro DELES: a fileira conta de baixo para cima…
    fileira_de_baixo = (casa_do_documento - 1) // CASAS_POR_FILEIRA
    posicao_na_fileira = (casa_do_documento - 1) % CASAS_POR_FILEIRA
    # …e a nossa linha 0 é a de cima, então a fileira se inverte.
    linha = LADO - 1 - fileira_de_baixo
    # A posição dentro da fileira **não** se inverte: o espelho horizontal
    # (coluna c → 7-c) e a contagem da direita para a esquerda do documento se
    # cancelam, e o que sobra é a nossa contagem da esquerda para a direita.
    casa = numero_da_casa(linha, _COLUNA_JOGAVEL[linha % 2][posicao_na_fileira])
    assert casa is not None, "coluna jogável nunca é clara — ver `_COLUNA_JOGAVEL`"
    return casa


# Em que colunas ficam as casas jogáveis de cada fileira do NOSSO tabuleiro. Nas
# linhas pares (0, 2, 4, 6) são as ímpares; nas ímpares, as pares. É a mesma
# informação que `numero_da_casa` já tem — escrita aqui porque a conversão acima
# precisa ir no sentido contrário, da posição-na-fileira para a coluna.
_COLUNA_JOGAVEL = ((1, 3, 5, 7), (0, 2, 4, 6))


def coluna_de_algebrica(letra: str) -> int:
    """``"a"`` → 0. A coluna sozinha, que é o que a notação abreviada dá."""
    letra = letra.strip().lower()
    if letra not in COLUNAS:
        raise NotacaoInvalida(f"{letra!r} não é uma coluna (a..h)")
    return COLUNAS.index(letra)


def interpretar_lance_abreviado(
    tabuleiro: Tabuleiro,
    token: str,
    regulamento: Regulamento = BRASILEIRAS,
) -> Lance:
    """``"ab4"`` → o lance legal desta posição que sai da coluna ``a`` e chega em ``b4``.

    Como a dedução é feita
    ----------------------
    Nenhuma regra é reescrita aqui. Pede-se ao gerador **os lances legais desta
    posição** e filtra-se por duas condições que o token dá:

    1. o destino do lance é exatamente a casa escrita (``b4``);
    2. a peça saiu de uma casa da coluna escrita (``a``).

    Se sobrar exatamente um lance, é ele. Se sobrar zero, o token não descreve
    lance nenhum aqui — pode ser sorteio de posição (``a1-d4``), pode ser um erro
    de leitura da tabela, pode ser um lance que a modalidade proíbe. Se sobrar
    mais de um, o texto é **ambíguo** nesta posição.

    Nos dois casos ruins a função levanta `NotacaoInvalida`, e quem chama decide
    o que fazer — o extrator de aberturas, por exemplo, descarta a linha inteira
    e registra o motivo, em vez de escolher um dos candidatos.

    Args:
        tabuleiro: a posição **antes** do lance (é ela que resolve a ambiguidade).
        token: três caracteres, no formato ``<coluna origem><casa destino>``.
        regulamento: a modalidade. Muda o conjunto de lances legais — e portanto
            pode mudar a resposta, ou fazer o mesmo token deixar de existir.
    """
    token = token.strip().lower()
    if len(token) != 3:
        raise NotacaoInvalida(
            f"{token!r} não é notação abreviada de lance (esperado 3 caracteres, "
            f"como 'ab4')"
        )

    coluna_de_origem = coluna_de_algebrica(token[0])
    destino = casa_de_algebrica(token[1:])

    candidatos = [
        lance
        for lance in gerar_lances(tabuleiro, regulamento)
        if lance.destino == destino
        and linha_coluna(lance.origem)[1] == coluna_de_origem
    ]

    if not candidatos:
        raise NotacaoInvalida(
            f"{token!r} não corresponde a nenhum lance legal nesta posição"
        )
    if len(candidatos) > 1:
        quais = ", ".join(str(lance) for lance in candidatos)
        raise NotacaoInvalida(
            f"{token!r} é ambíguo nesta posição — servem {quais}"
        )
    return candidatos[0]

"""O CATALOGO DE FIGURAS do "Forme a figura" (T147 da spec 010, §8zzzr).

═══════════════════════════════════════════════════════════════════════════
A FIGURA E DADO, E NAO CODIGO
═══════════════════════════════════════════════════════════════════════════

Cada figura e um `desenho`: linhas do tabuleiro **de cima para baixo**, cada
letra uma coluna, com os quatro simbolos da clausula `figura`
(`motores/nucleo/chegada.py`):

    X  peca da pessoa       O  peca do adversario
    _  casa vazia           .  qualquer coisa (a casa nao e da figura)

Uma figura nova e uma linha a mais em [FIGURAS_QUATRO], e nenhuma linha de
codigo: o desenho viaja dentro da linha de chegada publicada, e o aplicativo o
julga e o desenha sem versao nova (o mesmo principio do Bloco Y).

═══════════════════════════════════════════════════════════════════════════
O QUE O CATALOGO RECUSA ([recusas]), E POR QUE CADA UMA
═══════════════════════════════════════════════════════════════════════════

1. **Fora do formato** (simbolo estranho, linhas de tamanhos diferentes, sem
   `X`): a mesma leitura do juiz, `ClausulaDeFigura.de_dado`.
2. **Nao fica de pe com a gravidade**: uma casa `_` (vazia) ABAIXO de uma peca na
   mesma coluna. Peca nao flutua; essa figura nunca existe.
3. **Nao cabe** no tabuleiro da modalidade.
4. **Uma linha de `alinhar` pecas da pessoa** (quatro, no tradicional): forma-la
   seria vencer a partida, e o desafio voltaria a fechar no fim.
5. **A ultima peca de alguma coluna e do adversario** (o `O` no topo da coluna).
   So o lance da PESSOA fecha a conta do juiz; se a ultima casa a encher fosse
   do adversario, a figura poderia se completar num lance dele depois do prazo,
   e quem a "formou" nao cumpriria (historico do backend, 2026-10-23, decisao 6).

═══════════════════════════════════════════════════════════════════════════
A DISTANCIA ([distancia]), QUE VIRA O PRAZO
═══════════════════════════════════════════════════════════════════════════

O prazo do desafio e `M = distancia + folga` (`editorial.parametros_efetivos`):
um M fixo ora sobraria, ora faltaria, conforme a posicao. A distancia e, entre
todos os lugares onde a figura cabe sem conflito de cor, o menor numero de
casas que ainda precisam ser ocupadas para ela existir:

- as `X` vazias (pecas da pessoa que faltam);
- as `O` vazias (a peca que o adversario precisa por ali - a pessoa tem de
  leva-lo a isso, e conta como trabalho);
- os **apoios**: as casas vazias, fora da figura, que ficam embaixo de uma peca
  dela na mesma coluna (com gravidade, a peca so para em cima de outra).

⚠️ E uma medida do trabalho, e nao uma prova de que a figura e alcancavel: o
adversario pode tapar uma casa. Quem diz se e alcancavel e o gabarito; quem diz
se e dificil e a regua (T148).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from motores.nucleo.chegada import ChegadaInvalida, ClausulaDeFigura
from motores.quatro import contrato_quatro
from motores.quatro import distancia_da_figura_quatro as distancia_mod
from motores.quatro.motor_quatro import TabuleiroQuatro

#: A chave da figura nos parametros publicados (o nome no catalogo). Mora aqui,
#: e nao no editorial, porque a receita (`tipos_de_desafio.py`) tambem a le, e o
#: editorial ja importa as receitas.
CHAVE_FIGURA = "figura"

#: A chave do CODIGO da figura no enunciado (`js_objetivo`), que o app traduz
#: para o nome no idioma da pessoa (T152, `DECISOES-do-dono.md` §8zzzw).
#: ⚠️ **O codigo E o nome do catalogo** (`z`, `igual`, `i_longo`): ele ja e o
#: identificador estavel da figura. ⛔ Por isso um nome do catalogo nao se
#: renomeia - o app que conhece `igual` deixaria de achar o nome dela.
#: (Em `js_objetivo` a chave `figura` ja e o DESENHO, desde a T149.)
CHAVE_CODIGO_DA_FIGURA = "codigo_figura"

#: A folga da variante: `M = distancia + folga`. E o botao da dificuldade, no
#: lugar de um M fixo (a proposta §2, recusa 6).
CHAVE_FOLGA_DA_FIGURA = "folga"

#: As folgas que o editorial mede (a proposta: "a folga de 1 a 3").
FOLGAS_DA_FIGURA = (1, 2, 3)

#: A menor distancia aceita. ⚠️ Zero e a figura ja formada na posicao; um e a
#: figura que se forma num lance so (a proposta §2, recusa 5).
DISTANCIA_MINIMA_DA_FIGURA = 2

#: A maior distancia aceita: uma figura longe demais pediria um prazo em que a
#: partida inteira caberia, e o desafio deixaria de fechar no meio. ✅ **Sondada
#: na T148** (23/10/2026, `scripts/sondar_distancia_das_figuras_quatro.py`, 1.722
#: posicoes distintas com 10 a 16 lances jogados): a faixa de 2 a 6 aceita de
#: 41% (o V grande) a 98% (o "c") das posicoes, e nenhuma figura fica sem lugar.
#: ⚠️ As distancias curtas (2 a 4) quase sempre se resolvem em menos de 5 lances
#: e caem no piso de 9 meios-lances do gerador - que e o certo: e o desafio
#: "resolvido em 10 segundos" que o dono recusou.
DISTANCIA_MAXIMA_DA_FIGURA = 6

#: A familia de cada figura no catalogo (a proposta, "Primeiro lote"): as sete
#: que vao a regua para comparar as familias, os dois CONTROLES (os faceis, que
#: todos tem de cumprir com folga larga: se nao cumprem, quem falhou foi a
#: medicao) e o TETO (se ninguem as forma, a figura e dificil demais para o 7 x 6).
#: O `terceiro_lote` (27/10/2026) e a exclamacao, pedida pelo dono ao ver a
#: grade da T150 (DECISOES §8zzzu).
FAMILIAS = ("lote", "controle", "teto", "segundo_lote", "terceiro_lote")


@dataclass(frozen=True, slots=True)
class FiguraQuatro:
    """Uma figura do catalogo.

    Atributos:
        nome: a chave do catalogo, que vai nos parametros publicados.
        desenho: as linhas, de cima para baixo.
        espelhar: se o espelho da esquerda para a direita tambem vale. ⚠️ Nas
            letras nao (o "z" espelhado e um "s"); nas formas simetricas tanto
            faz, e fica `False` para a clausula publicada dizer exatamente o
            desenho.
        familia: uma de [FAMILIAS].
    """

    nome: str
    desenho: tuple[str, ...]
    espelhar: bool
    familia: str

    def clausula(self) -> dict[str, Any]:
        """A clausula `figura` da linha de chegada, como ela vai ao banco."""
        return {"tipo": "figura", "desenho": list(self.desenho), "espelhar": self.espelhar}


def _figura(nome: str, desenho: list[str], familia: str, espelhar: bool = False) -> FiguraQuatro:
    return FiguraQuatro(nome=nome, desenho=tuple(desenho), espelhar=espelhar, familia=familia)


#: O catalogo. Cada desenho, como fica no tabuleiro (`·` = fora da figura):
#:
#:     T            +            z            =            losango
#:     X X X        · X ·        X X ·        X X          · X ·
#:     · X ·        X X X        · X X        · ·          X O X
#:     · X ·        · X ·                     X X          · X ·
#:
#:     c (abraco)   i (o pingo)  quadrado     L            V grande       xis
#:     X X          X                         X ·          X · · · X      X · X
#:     X O          O            X X          X ·          · X · X ·      · X ·
#:     X X          X            X X          X X          · · X · ·      X · X
#:                  X
#:
#:     ⊥            piramide     u            v            escada
#:     · X ·        · X ·        X · X        X · X        · · X
#:     · X ·        X X X        X X X        · X ·        · X X
#:     X X X                                               X X ·
#:
#:     n (ponte)    i longo      = sanduiche    !  (exclamacao)
#:     X X X        X            X X            X
#:     X O X        O            O O            X
#:                  X            X X            X
#:                  X                           O
#:                  X                           X
#:
#: ⚠️ A exclamacao e o i longo de cabeca para baixo, e o ponto e separado da
#: haste por uma peca do ADVERSARIO, e nao por "qualquer coisa" (`.`): com a
#: peca da pessoa ali a coluna viraria uma torre de 4 (vitoria) antes de a
#: figura fechar, e o desafio nunca se cumpriria por esse caminho
#: (DECISOES §8zzzu item 3).
#:
#: ⚠️ O "T" tem 5 pecas (a barra de 3 e a haste de 2, §8zzzr item 2), e o
#: triangulo saiu por decisao do dono. O "u" vale oco ou cheio (o miolo `.`
#: aceita qualquer coisa, §8zzzr item 4).
#:
#: ⚠️ O SEGUNDO LOTE (23/10/2026) sao as oito figuras validas da proposta que o
#: primeiro lote deixou para depois. O dono pediu as dezenove numa medicao so
#: (DECISOES §8zzzs): o primeiro lote nao foi limite tecnico, foi escolha de
#: planejamento.
FIGURAS_QUATRO: dict[str, FiguraQuatro] = {
    f.nome: f
    for f in (
        # O primeiro lote: as familias misturadas para a regua comparar.
        _figura("t", ["XXX", ".X.", ".X."], "lote"),
        _figura("mais", [".X.", "XXX", ".X."], "lote"),
        _figura("z", ["XX.", ".XX"], "lote"),
        _figura("igual", ["XX", "..", "XX"], "lote"),
        _figura("losango", [".X.", "XOX", ".X."], "lote"),
        _figura("c", ["XX", "XO", "XX"], "lote"),
        _figura("i", ["X", "O", "X", "X"], "lote"),
        # Os controles.
        _figura("quadrado", ["XX", "XX"], "controle"),
        _figura("l", ["X.", "X.", "XX"], "controle"),
        # O teto.
        _figura("v_grande", ["X...X", ".X.X.", "..X.."], "teto"),
        _figura("xis", ["X.X", ".X.", "X.X"], "teto"),
        # O segundo lote: as figuras validas da proposta ainda nao medidas.
        _figura("t_invertido", [".X.", ".X.", "XXX"], "segundo_lote"),
        _figura("piramide", [".X.", "XXX"], "segundo_lote"),
        _figura("u", ["X.X", "XXX"], "segundo_lote"),
        _figura("v", ["X.X", ".X."], "segundo_lote"),
        _figura("escada", ["..X", ".XX", "XX."], "segundo_lote"),
        _figura("n", ["XXX", "XOX"], "segundo_lote"),
        _figura("i_longo", ["X", "O", "X", "X", "X"], "segundo_lote"),
        _figura("igual_sanduiche", ["XX", "OO", "XX"], "segundo_lote"),
        # O terceiro lote: a exclamacao, pedida pelo dono (27/10/2026).
        _figura("exclamacao", ["X", "X", "X", "O", "X"], "terceiro_lote"),
    )
}


# ═══════════════════════════════════════════════════════════════════════════
# As contas da proposta (§2, "As figuras, uma a uma")
# ═══════════════════════════════════════════════════════════════════════════


#: O desenho lido por coluna, cada uma de CIMA para BAIXO (a funcao mora no
#: modulo do motor; este nome continua valendo para as contas de cima).
colunas = distancia_mod.colunas


def pecas(desenho: tuple[str, ...]) -> tuple[int, int]:
    """Quantas casas `X` e quantas `O` a figura tem."""
    todas = "".join(desenho)
    return todas.count("X"), todas.count("O")


def apoios_desde_o_chao(desenho: tuple[str, ...]) -> int:
    """Os apoios que a figura pede quando a linha de baixo dela esta no chao.

    Um apoio e uma casa `.` com uma peca da figura (`X` ou `O`) acima dela na
    mesma coluna: fora da figura, mas precisa estar ocupada para a peca de cima
    nao cair. Os bracos do T, por exemplo, pedem duas casas cada.
    """
    total = 0
    for coluna in colunas(desenho):
        # `find` acha a primeira peca de cima para baixo; tudo abaixo dela que
        # seja `.` e apoio. Sem peca na coluna, `find` devolve -1 e nada conta.
        topo = min((i for i in (coluna.find("X"), coluna.find("O")) if i >= 0), default=None)
        if topo is not None:
            total += coluna[topo:].count(".")
    return total


def maior_linha_da_pessoa(desenho: tuple[str, ...]) -> int:
    """A maior sequencia de `X` seguidos, nas quatro direcoes de uma linha."""
    altura, largura = len(desenho), len(desenho[0])
    maior = 0
    for passo_linha, passo_coluna in ((0, 1), (1, 0), (1, 1), (1, -1)):
        for i in range(altura):
            for j in range(largura):
                corrida = 0
                li, cj = i, j
                while 0 <= li < altura and 0 <= cj < largura and desenho[li][cj] == "X":
                    corrida += 1
                    li, cj = li + passo_linha, cj + passo_coluna
                maior = max(maior, corrida)
    return maior


def lugares(desenho: tuple[str, ...], dimensoes: contrato_quatro.DimensoesQuatro) -> int:
    """Em quantas posicoes a caixa da figura cabe no tabuleiro vazio."""
    sobra_na_largura = dimensoes.largura - len(desenho[0]) + 1
    sobra_na_altura = dimensoes.altura - len(desenho) + 1
    return max(sobra_na_largura, 0) * max(sobra_na_altura, 0)


def recusas(figura: FiguraQuatro, dimensoes: contrato_quatro.DimensoesQuatro) -> list[str]:
    """Por que a [figura] nao pode ir ao catalogo. Vazio = pode.

    As cinco recusas do cabecalho, cada uma com o motivo legivel.
    """
    try:
        ClausulaDeFigura.de_dado(figura.clausula())
    except ChegadaInvalida as erro:
        # Fora do formato, as contas abaixo nao fariam sentido.
        return [f"fora do formato: {erro}"]

    motivos: list[str] = []
    desenho = figura.desenho
    for j, coluna in enumerate(colunas(desenho), start=1):
        ja_viu_peca = False
        for simbolo in coluna:
            if simbolo in "XO":
                ja_viu_peca = True
            elif simbolo == "_" and ja_viu_peca:
                motivos.append(f"a coluna {j} tem casa vazia embaixo de uma peca")
                break
        topo = next((s for s in coluna if s in "XO"), None)
        if topo == "O":
            motivos.append(f"a ultima peca da coluna {j} e do adversario")
    if len(desenho[0]) > dimensoes.largura or len(desenho) > dimensoes.altura:
        motivos.append(
            f"nao cabe no {dimensoes.largura} x {dimensoes.altura}: "
            f"{len(desenho[0])} x {len(desenho)}"
        )
    if maior_linha_da_pessoa(desenho) >= dimensoes.alinhar:
        motivos.append(
            f"tem {dimensoes.alinhar} pecas da pessoa em linha: forma-la e vencer"
        )
    return motivos


# ═══════════════════════════════════════════════════════════════════════════
# A distancia numa posicao
# ═══════════════════════════════════════════════════════════════════════════


def _desenhos(figura: FiguraQuatro) -> list[tuple[str, ...]]:
    """O desenho, e o espelho dele quando a figura aceita."""
    return distancia_mod.desenhos(figura.desenho, figura.espelhar)


def distancia(
    figura: FiguraQuatro,
    tabuleiro: TabuleiroQuatro,
    dimensoes: contrato_quatro.DimensoesQuatro,
    quem: int | None = None,
) -> int | None:
    """A menor distancia da [figura] no [tabuleiro], com os `X` de [quem].

    [quem] ausente = quem tem a vez (a pessoa, na posicao publicada). A conta
    mora em `motores/quatro/distancia_da_figura_quatro.py`, porque o perseguidor
    do motor tambem a usa (T148).

    Returns:
        O menor custo entre todos os lugares sem conflito (ver o cabecalho), ou
        `None` quando a figura nao cabe em lugar nenhum sem conflito - ela nunca
        mais pode ser formada nesta partida.

    ⚠️ Zero quer dizer que a figura JA esta no tabuleiro.
    """
    return distancia_mod.distancia(
        figura.desenho,
        figura.espelhar,
        tabuleiro,
        dimensoes,
        tabuleiro.vez if quem is None else quem,
    )

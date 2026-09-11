"""O ESPELHO: a mesma posicao de damas, com as cores trocadas (T049p).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ISTO EXISTE — DUAS EXIGENCIAS QUE BRIGAVAM
═══════════════════════════════════════════════════════════════════════════

Em 11/09/2026 o dono relatou que, no painel, ele aparecia jogando **de vermelho,
com as pecas no topo** — contra a regra canonica do projeto (*"o humano e o
Jogador 1, azul"*). A causa estava no preparo: o molde tem as **brancas** a
jogar, e cada lance de variacao troca o lado; com **um** lance, quem resolve o
desafio passava a ser as pretas.

A primeira correcao foi obvia e **errada**: tornar a variacao **par** (dois
lances). Ela resolveu o lado e quebrou o resto, na mesma execucao:

  · ⛔ **2026-09-11 ficou SEM DESAFIO** — `damas_capturar_multipla` descartou
    nove posicoes seguidas por *"o objetivo cai no lance 1"* e nao sobrou
    candidato nenhum;
  · ⛔ **as damas viraram desafios de dois lances** — todas as tres linhas da
    fila sairam com `nu_lances_solucao = 3` (tres **meios**-lances), e o dono
    escreveu: *"o usuario entra pra resolver um desafio e nao joga praticamente
    nada. Consegue resolve-los em uns 10 segundos e sai do App?"*.

⚠️ **O motivo e um so: o preparo CONSOME a distancia ate o objetivo.** Os moldes
foram cacados como posicoes a ~3 lances do objetivo; gastar dois deles em
variacao deixa o desafio a um lance — ou a zero, e ai ele e descartado.

═══════════════════════════════════════════════════════════════════════════
A SAIDA: VARIAR UM LANCE, E ESPELHAR
═══════════════════════════════════════════════════════════════════════════

O espelho gira o tabuleiro 180 graus e troca as cores. A posicao resultante e
**a mesma tarefa**, vista do outro lado — e com o lado a jogar tambem trocado.
Entao um lance de variacao (que preserva a distancia ao objetivo) seguido do
espelho devolve uma posicao com as **brancas** a jogar.

⚠️ **Isto so funciona porque as damas sao simetricas sob essa transformacao:** a
pedra anda para frente, a dama anda na diagonal, a captura e por salto — nenhuma
regra distingue "cima" de "baixo" que a troca de cor nao desfaca. Medido nas
quatro modalidades em 11/09/2026: o numero de lances legais e identico dos dois
lados do espelho, e ha cadeado.

⛔ **Nao vale para todo jogo.** No Pontinhos nao ha o que espelhar (a posicao ja
sai com `vez_de: 1`), e num jogo com regras assimetricas por cor isto estaria
errado — por isso o modulo tem o nome do jogo, e nao um nome generico.

═══════════════════════════════════════════════════════════════════════════
A ARITMETICA
═══════════════════════════════════════════════════════════════════════════

As casas jogaveis sao numeradas de 1 a 32, da esquerda para a direita e de cima
para baixo (⚠️ a numeracao e a do motor — ver `tabuleiro_damas.py`). Girar o
tabuleiro 180 graus inverte essa lista inteira, entao a casa `n` vira `33 - n`.

⚠️ **E a casa escura continua escura**: a rotacao leva `(linha, coluna)` para
`(7 - linha, 7 - coluna)`, e `(7-l) + (7-c) = 14 - (l+c)` tem a mesma paridade
que `l + c`. Sem isso a FEN espelhada descreveria pecas em casas que nao
existem.
"""

from __future__ import annotations

#: Quantas casas jogaveis o tabuleiro tem. A soma `casa + espelho` e sempre
#: `LADO + 1` — 33 num tabuleiro de 32 casas.
CASAS_JOGAVEIS = 32


def _casas(campo: str) -> list[str]:
    """As casas de um campo da FEN (`W25,26,29` -> `["25", "26", "29"]`).

    ⚠️ O primeiro caractere e a cor do campo, e nao uma casa.
    """
    return [x.strip() for x in campo[1:].split(",") if x.strip()]


def espelhar_casa(casa: str) -> str:
    """`"25"` vira `"8"`; `"K31"` vira `"K2"`.

    ⚠️ **O `K` viaja junto.** Uma dama espelhada continua dama — perder o `K`
    aqui transformaria a posicao noutra, ⛔ igualmente legal e silenciosamente
    diferente, que e a pior especie de defeito que esta feature ja teve.
    """
    bruto = casa.strip().upper()
    e_dama = bruto.startswith("K")
    numero = int(bruto.lstrip("K"))
    if not 1 <= numero <= CASAS_JOGAVEIS:
        raise ValueError(f"casa fora do tabuleiro: {casa!r}")
    return ("K" if e_dama else "") + str(CASAS_JOGAVEIS + 1 - numero)


def espelhar_fen(fen: str) -> str:
    """A mesma posicao, girada 180 graus e com as cores trocadas.

    Args:
        fen: `"B:W25,26,29:B16,17,18,21"` — lado a jogar, brancas, pretas.

    Returns:
        A FEN espelhada, com as casas **ordenadas** por numero.

    Raises:
        ValueError: FEN malformada ou casa fora de 1..32.

    ⚠️ **As casas saem ordenadas de proposito.** Duas FENs que descrevem a mesma
    posicao com as casas em ordens diferentes sao textos diferentes — e a
    unicidade do desafio (T049i) compara **texto**. Sem a ordenacao, a mesma
    posicao poderia ser publicada duas vezes sem que a pergunta de repeticao
    percebesse.
    """
    partes = fen.split(":")
    if len(partes) != 3:
        raise ValueError(f"FEN malformada: {fen!r}")
    lado, brancas, pretas = partes

    def virar(campo: str) -> list[str]:
        casas = [espelhar_casa(c) for c in _casas(campo)]
        return sorted(casas, key=lambda c: int(c.lstrip("K")))

    # ⚠️ As pretas viram brancas e vice-versa — e isso e o proprio ponto: o
    # solucionador continua sendo o mesmo lado do tabuleiro, mas agora ele e o
    # jogador 1 (azul), que e o que o aplicativo mostra.
    novas_brancas = virar(pretas)
    novas_pretas = virar(brancas)
    novo_lado = "W" if lado.strip().upper().startswith("B") else "B"

    return f"{novo_lado}:W{','.join(novas_brancas)}:B{','.join(novas_pretas)}"


def com_as_brancas_a_jogar(fen: str) -> str:
    """A posicao como o desafio a publica: sempre com as brancas a jogar.

    Espelha quando preciso, e devolve intacta quando ja esta certa.

    ⚠️ **E esta a funcao que o gerador chama**, e nao `espelhar_fen` direto: a
    decisao *"precisa espelhar?"* mora num lugar so. Espalhada por quem chama,
    ela viraria um `if` esquecido no dia em que um tipo novo de damas entrar.
    """
    return fen if fen.strip().upper().startswith("W") else espelhar_fen(fen)

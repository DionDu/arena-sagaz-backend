"""Quem resolve um desafio de coroacao joga para COROAR, e nao para vencer.

⚠️ **Nao e "jogar bem", e jogar PARA ESTE OBJETIVO** — a mesma distincao do
`motores/pontinhos/cadeia_longa.py`. O Sagaz no lugar deste solucionador usaria a
primeira dama para dominar a partida, que e como se ganha, e e o oposto do que o
desafio pede quando o alvo sao duas coroacoes.

⛔ **A pergunta e do dono, e nasceu de um defeito real** (18/09/2026): *"sera que
o Coroar 2 Damas nao esta morrendo porque o personagem, apos coroar a primeira
dama, prefere jogar com a primeira dama coroada ao inves de tentar coroar a
segunda?"*. `damas_coroar` nao tem entrada em `gerador.SOLUCIONADOR_POR_TIPO`,
entao o objetivo do desafio nunca entrou na escolha do lance — nem na regua, nem
na pescaria dos moldes.

⚠️ **O efeito e real e pequeno**, e esta medido: em 300 posicoes
(`scripts/medir_perseguir_vs_vencer.py`, 18/09/2026) este solucionador achou 6
moldes de duas damas contra 3 do Sagaz, mantendo 94 dos 99 de uma dama. ⛔ Por
isso ele **ainda nao esta ligado em `SOLUCIONADOR_POR_TIPO`**: o mapa e por TIPO,
e ligar aqui mataria a escada do X=1, que hoje funciona. Ele existe para a
pescaria poder procurar moldes com ele, que e a medicao que decide se vale mudar
a estrutura.

⚠️ **E ele NAO tem nivel** — joga igual para a Cacau e para o Magno. E a mesma
limitacao declarada do solucionador do Pontinhos, e e a razao pela qual, se um
dia ele entrar em producao, tera de enxergar mais longe conforme o nivel.
"""

from __future__ import annotations

from typing import Any

#: Peso do material contra o de uma fileira de avanco.
#:
#: ⛔ **Este numero e a licao inteira do experimento de 18/09/2026.** A primeira
#: versao do solucionador ordenava os lances de forma lexicografica — coroacoes,
#: depois avanco, material em ULTIMO —, entao qualquer casa ganha valia mais que
#: a peca que ela custava. Resultado: ele entregava material, a partida acabava
#: antes do objetivo, e coroava UMA dama em 51 das 163 posicoes em que o Sagaz
#: coroava nas 163. ⚠️ Um solucionador que perde para o motor no objetivo FACIL
#: nao mede nada sobre o dificil.
PESO_DA_PECA = 10

#: Peso de uma coroacao ja conquistada. Alto o bastante para nunca ser trocado
#: por material: coroar e o objetivo, e nao uma vantagem entre outras.
PESO_DA_DAMA = 100


def _campos(fen: str) -> tuple[str, list[str], list[str]]:
    """Quebra a FEN em `(lado_a_jogar, brancas, pretas)`.

    ⚠️ **O primeiro campo e o LADO A JOGAR, e nao uma cor de peca** — `B:W...:B...`
    quer dizer "pretas jogam".
    """
    lado, brancas, pretas = fen.split(":")
    partir = lambda campo: [x for x in campo[1:].split(",") if x.strip()]
    return lado, partir(brancas), partir(pretas)


def _indice_de_quem_joga(fen: str) -> int:
    """O indice de `_campos` das pecas de quem esta a jogar (1 brancas, 2 pretas).

    ⚠️ **E "quem joga", e nao "as brancas"**: a posicao publicada de um desafio de
    damas sai com as pretas a jogar, e e delas que o desafio fala.
    """
    return 1 if _campos(fen)[0].upper().startswith("W") else 2


def _fileiras_ate_coroar(casa: str, sou_branco: bool) -> int:
    """Quantas fileiras faltam para esta pedra coroar. Dama devolve 0.

    ⚠️ As casas vao de 1 a 32, quatro por fileira. As brancas coroam em 1..4 (a
    fileira 0) e as pretas em 29..32 (a fileira 7) - a conta das pretas e o
    espelho da das brancas.
    """
    if casa.upper().startswith("K"):
        return 0
    numero = int(casa.upper().lstrip("K"))
    fileira = (numero - 1) // 4
    return fileira if sou_branco else 7 - fileira


def nota_da_posicao(fen: str, indice_meu: int) -> int:
    """Quanto esta posicao serve ao objetivo de COROAR, para o lado `indice_meu`.

    A conta soma tres coisas, e a ordem de grandeza entre elas e o que faz o
    solucionador funcionar:

      * cada dama ja conquistada vale `PESO_DA_DAMA`;
      * cada peca viva vale `PESO_DA_PECA`, porque peca entregue nao coroa;
      * cada fileira que falta as **duas** pedras mais adiantadas desconta 1.

    ⚠️ **Sao as DUAS mais adiantadas, e nao a melhor.** Premiar so a primeira faria
    o solucionador empurrar sempre a mesma pedra e abandonar a segunda - que e
    exatamente o defeito que ele existe para corrigir no motor.
    """
    minhas = _campos(fen)[indice_meu]
    sou_branco = indice_meu == 1
    damas = sum(1 for casa in minhas if casa.upper().startswith("K"))
    pedras = sorted(
        _fileiras_ate_coroar(casa, sou_branco)
        for casa in minhas
        if not casa.upper().startswith("K")
    )
    distancia = sum(pedras[:2])
    return PESO_DA_DAMA * damas + PESO_DA_PECA * len(minhas) - distancia


def _aplicar(arbitro: Any, estado: Any, lance: str) -> Any:
    """Aplica o lance pelo arbitro, ou pelo proprio estado se ele nao souber.

    ⚠️ O mesmo fallback de `job/regua.py`: nem toda ponta que chama um
    solucionador entrega um objeto com `aplicar`.
    """
    if hasattr(arbitro, "aplicar"):
        return arbitro.aplicar(estado, lance)
    return estado.com_lance(lance)


def _pior_perda(arbitro: Any, depois: Any, indice_meu: int) -> int:
    """Quantas pecas minhas o adversario leva na melhor captura dele?

    ⛔ **Nas damas a captura e OBRIGATORIA**, entao entregar peca nao e um risco
    que o adversario talvez aceite - e um lance que ele sera forcado a fazer.
    ⚠️ E um unico meio-lance de antecipacao, e nao uma busca: o que se quer e so
    impedir que o solucionador pague material para avancar uma casa.
    """
    try:
        legais = arbitro.lances_legais(depois)
    except Exception:  # noqa: BLE001 — posicao terminal nao tem lance legal
        return 0
    minhas_agora = len(_campos(depois.fen)[indice_meu])
    pior = 0
    for lance in legais:
        try:
            resposta = _aplicar(arbitro, depois, lance)
        except Exception:  # noqa: BLE001
            continue
        pior = max(pior, minhas_agora - len(_campos(resposta.fen)[indice_meu]))
    return pior


def lance_de_quem_persegue_a_coroacao(arbitro: Any, estado: Any) -> str:
    """O lance de quem quer COROAR, e nao de quem quer vencer.

    ⚠️ **A assinatura e a de `SOLUCIONADOR_POR_TIPO`** (`(arbitro, estado) -> str`),
    para que ligar este solucionador um dia seja uma linha, e nao uma adaptacao.

    ⚠️ **O lado sai do proprio estado**, e nao de um parametro: o solucionador so e
    chamado na vez de quem resolve, entao `estado.vez_de` ja e o lado certo.
    """
    indice_meu = _indice_de_quem_joga(estado.fen)
    legais = arbitro.lances_legais(estado)
    if not legais:
        raise ValueError("nao ha lance legal nesta posicao")

    def nota(lance: str) -> int:
        depois = _aplicar(arbitro, estado, lance)
        return nota_da_posicao(depois.fen, indice_meu) - PESO_DA_PECA * _pior_perda(
            arbitro, depois, indice_meu
        )

    return max(legais, key=nota)

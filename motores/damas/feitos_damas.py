"""As MEDIDAS que uma partida de damas produz (T029).

⚠️ **Feito e medida, nunca XP.** E ⚠️ **nao ha regra de damas aqui**: quem valida
lance e o motor, cópia byte-idêntica do laboratório. Este arquivo conta o que
aconteceu enquanto a fita era reproduzida.

═══════════════════════════════════════════════════════════════════════════
AS DUAS MEDIDAS DE CAPTURA, E POR QUE SAO DUAS
═══════════════════════════════════════════════════════════════════════════

`capturas_extras` soma, na partida inteira, as peças **alem da primeira** de cada
lance. ⚠️ Uma captura simples paga **zero**, e isso e regra de produto, nao
descuido: capturar e **obrigatorio** nas damas, e premiar uma captura simples
seria premiar o cumprimento da regra.

`maior_captura` e o melhor lance **isolado**. Comer tres de uma vez exige
enxergar a combinação inteira antes de mover; comer tres em tres lances nao e a
mesma proeza — e por isso as duas medidas existem separadas, com as mesmas
definições do aplicativo (`estado_partida_damas.dart`).
"""

from __future__ import annotations

from .motor_damas import EstadoDamas, MotorDamas


def _pecas(fen: str, lado: int) -> int:
    """Quantas peças um lado tem na FEN.

    A FEN tem a forma `W:W21,22,K27:B1,2,K10`: o prefixo diz de quem e a vez, e as
    duas listas sao as peças de cada cor. O `K` marca dama, e nao entra na
    contagem de quantidade — uma dama e uma peça.

    Args:
        lado: `+1` para as brancas, `-1` para as pretas.
    """
    partes = fen.split(":")
    # `partes[0]` e a vez; `partes[1]` as brancas; `partes[2]` as pretas.
    bruto = partes[1] if lado == 1 else partes[2]
    corpo = bruto[1:]  # tira o `W`/`B` inicial
    if not corpo:
        return 0
    return len([casa for casa in corpo.split(",") if casa])


def _damas(fen: str, lado: int) -> int:
    """Quantas DAMAS (peças coroadas) um lado tem."""
    partes = fen.split(":")
    bruto = partes[1] if lado == 1 else partes[2]
    return bruto.count("K")


def medir(
    motor: MotorDamas,
    inicial: EstadoDamas,
    fita: list[str],
    *,
    jogador: int,
) -> dict[str, float]:
    """Reproduz a fita com o motor e mede os feitos de `jogador`.

    Args:
        motor: o motor da modalidade — quem valida cada lance.
        inicial: a posição de partida do desafio.
        fita: os lances, na ordem, no vocabulário do log (`5-1`, `27x18x11`).
        jogador: `+1` (brancas) ou `-1` (pretas).

    Raises:
        ValueError: se algum lance for ilegal. ⚠️ Isso e **dado invalido**, e quem
            chama precisa distinguir de "nao cumpriu" — sao coisas diferentes
            (D-05).

    ⚠️ **O numero de capturas sai da FORMA do lance**, e nao de um campo: `27x18x11`
    come duas peças, e cada `x` e uma captura. E o mesmo vocabulário do log, e
    ler dali evita um segundo caminho por onde a contagem poderia divergir.
    """
    estado = inicial
    coroadas = 0
    capturas_extras = 0
    maior_captura = 0
    lances_do_jogador = 0

    for lance in fita:
        # ── ⛔ DE QUEM E ESTE LANCE? ─────────────────────────────────────────
        #
        # ⚠️ **A fita de um desafio inclui os lances do ADVERSARIO**, e e preciso
        # que inclua: sem eles a sequencia nao e reproduzivel e o replay mostraria
        # a pessoa jogando sozinha (`gabarito.montar` diz isso com todas as
        # letras).
        #
        # ⛔ **Ate 11/09/2026 este laco contava todos os lances como se fossem do
        # jogador**, sob um comentario que afirmava o contrario — *"a fita de um
        # desafio e do jogador do desafio"*. Nao e, e nunca foi.
        #
        # **O que isso publicou**, achado pelo dono na primeira fila curada:
        # `a98bb871`, objetivo *"capture 2 pecas"*, com esta solucao:
        #
        #     1. 15x6      (jogador  1)  — a pessoa captura UMA
        #     2. 2x9x18    (jogador -1)  — o ADVERSARIO captura duas
        #     3. 11-8      (jogador  1)  — a pessoa joga qualquer coisa
        #
        # ⚠️ **O objetivo foi cumprido pelo adversario**, e o desafio saiu bem
        # formado: posicao legal, gabarito, regua medida, XP calculado. A pessoa
        # so precisava fazer um lance qualquer depois.
        #
        # ⚠️ **`estado.vez_de` e a fonte**, e nao um campo do lance: a fita aqui e
        # uma lista de **strings** (`27x18x11`), sem dono declarado. Quem sabe de
        # quem e a vez e o motor, e nas damas ela alterna a cada lance — inclusive
        # depois de uma captura encadeada, que e **um** lance.
        antes = estado
        de_quem = antes.vez_de
        estado = motor.aplicar(estado, lance)

        if de_quem != jogador:
            # ⛔ Lance do adversario: nao entra em medida nenhuma do jogador. E
            # isso vale para TODAS elas — `lances_do_jogador` tambem estava
            # contando o dobro, e ele normaliza o XP (`co_sobre:
            # lances_da_solucao`).
            continue

        lances_do_jogador += 1

        capturas = lance.count("x")
        maior_captura = max(maior_captura, capturas)
        if capturas > 1:
            capturas_extras += capturas - 1

        # Coroou quando o lado ganhou uma dama a mais do que tinha.
        #
        # ⚠️ Esta medida ja estava certa antes da correcao, por acidente feliz:
        # ela pergunta pelas damas **de `jogador`**, entao um lance do adversario
        # nunca a incrementava. ⛔ Mas ficar certo por acidente nao e ficar
        # protegido — e ela agora esta dentro do mesmo guarda das outras.
        if _damas(estado.fen, jogador) > _damas(antes.fen, jogador):
            coroadas += 1

    veredito = motor.veredito(estado)
    venceu = veredito.acabou and veredito.vencedor == jogador
    empatou = veredito.acabou and veredito.vencedor is None

    return {
        "damas_coroadas": coroadas,
        "capturas_extras": capturas_extras,
        "maior_captura": maior_captura,
        "material_restante": _pecas(estado.fen, jogador),
        "material_do_adversario": _pecas(estado.fen, -jogador),
        "lances_do_jogador": lances_do_jogador,
        # ⚠️ Marcos: `1` ou `0`, e nao `True`/`False`. A coluna `vr_medida` do
        # extrato de XP e numérica, e um booleano ali obrigaria quem lê a saber
        # que aquela chave e diferente das outras.
        "vitoria": 1 if venceu else 0,
        "empate": 1 if empatou else 0,
    }

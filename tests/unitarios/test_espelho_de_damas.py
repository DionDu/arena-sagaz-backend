"""T049p - o ESPELHO: a mesma posicao de damas, vista do outro lado.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

O espelho existe para que **quem resolve o desafio seja sempre o jogador 1**
(azul, pecas embaixo), sem gastar os lances de variacao que sustentam a
dificuldade. Ele so e legitimo porque as damas sao simetricas sob rotacao de 180
graus com troca de cor — e ⛔ **"simetrico" e afirmacao sobre o motor, nao sobre
a aritmetica**: quem garante isso e o teste que pergunta ao motor.

⚠️ **Um espelho errado nao levanta excecao.** Ele produz uma posicao legal e
**outra**, com outro numero de lances, outra distancia ate o objetivo e outra
dificuldade — e o desafio sairia bem formado, com gabarito e regua, descrevendo
uma tarefa que ninguem projetou.
"""

from __future__ import annotations

import pytest

from job.espelho_de_damas import (
    com_as_brancas_a_jogar,
    com_o_adversario_a_jogar,
    espelhar_casa,
    espelhar_fen,
)
from job.moldes_de_damas import MODALIDADES
from job.tipos_de_desafio import receita_de
from motores.damas.motor_damas import EstadoDamas, MotorDamas

#: Posicoes de verdade, tiradas da fila do `des`.
#:
#: ⚠️ **Dado de producao, e nao exemplo inventado** — sao as FENs que o job
#: publicou em 11/09/2026, e e por isso que elas provam alguma coisa.
POSICOES = (
    "B:W25,26,29:B16,17,18,21",
    "B:W11,17,32:B13,23",
    "B:W5,27,30:B14,18,20",
    "W:W10,18,21:B17,20",
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. A aritmetica
# ═══════════════════════════════════════════════════════════════════════════


def test_a_casa_espelhada_soma_33_com_a_original() -> None:
    """Girar o tabuleiro inverte a lista de 32 casas: `n` vira `33 - n`."""
    for casa in range(1, 33):
        assert int(espelhar_casa(str(casa))) == 33 - casa


def test_a_DAMA_continua_dama_do_outro_lado() -> None:
    """🔒 ⛔ Perder o `K` daria uma posicao legal e silenciosamente diferente.

    Uma dama vale muito mais que uma pedra; um espelho que a rebaixasse mudaria
    a tarefa sem que nada no job reclamasse.
    """
    assert espelhar_casa("K31") == "K2"
    assert espelhar_casa("k31") == "K2"


@pytest.mark.parametrize("casa", ["0", "33", "-1", "K99"])
def test_casa_FORA_do_tabuleiro_falha_alto(casa) -> None:
    """⚠️ Falhar alto, e nao devolver algo plausivel."""
    with pytest.raises(ValueError):
        espelhar_casa(casa)


def test_espelhar_DUAS_vezes_devolve_a_posicao_original() -> None:
    """🔒 A involucao: girar duas vezes e nao girar.

    ⚠️ Este caso pega a especie de erro mais provavel aqui — trocar `33 - n` por
    `32 - n`, ou esquecer de trocar o lado a jogar. Qualquer um dos dois quebra a
    ida e volta.
    """
    for fen in POSICOES:
        assert espelhar_fen(espelhar_fen(fen)) == _normalizar(fen)


def _normalizar(fen: str) -> str:
    """A mesma FEN com as casas ordenadas, que e como o espelho as devolve."""
    lado, brancas, pretas = fen.split(":")
    ordenar = lambda campo: ",".join(
        sorted(
            [x for x in campo[1:].split(",") if x],
            key=lambda c: int(c.upper().lstrip("K")),
        )
    )
    return f"{lado}:W{ordenar(brancas)}:B{ordenar(pretas)}"


# ═══════════════════════════════════════════════════════════════════════════
# 2. ⛔ O MOTOR concorda que e a mesma posicao
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("co_modalidade", MODALIDADES)
def test_o_espelho_tem_os_MESMOS_lances_legais_nas_quatro_modalidades(
    co_modalidade,
) -> None:
    """🔒 ⛔ A afirmacao que sustenta o espelho inteiro, feita ao motor.

    ⚠️ **Nas quatro**, porque as regras diferem: na anglo a dama nao voa e a
    coroacao encerra o lance; na portuguesa vale a Lei da Qualidade. Se alguma
    delas distinguisse "cima" de "baixo" de um jeito que a troca de cor nao
    desfizesse, o espelho estaria errado **so naquela** — e o desafio sairia
    torto num dia de cada quatro, que e a frequencia que este projeto ja viu
    esconder um defeito por semanas.
    """
    motor = MotorDamas(co_modalidade)
    for fen in POSICOES:
        original = EstadoDamas(co_modalidade=co_modalidade, fen_inicial=fen)
        refletida = EstadoDamas(
            co_modalidade=co_modalidade, fen_inicial=espelhar_fen(fen)
        )
        assert len(motor.lances_legais(original)) == len(
            motor.lances_legais(refletida)
        ), (
            f"{co_modalidade}: {fen} tem "
            f"{len(motor.lances_legais(original))} lances e o espelho tem "
            f"{len(motor.lances_legais(refletida))}. ⛔ Se os numeros divergem, "
            "nao e a mesma posicao — e o espelho nao pode ser usado."
        )


@pytest.mark.parametrize("co_modalidade", MODALIDADES)
def test_o_espelho_de_todo_MOLDE_continua_jogavel(co_modalidade) -> None:
    """🔒 O espelho aplicado ao acervo inteiro, e nao a quatro exemplos.

    ⚠️ São 170 moldes; um erro que so aparecesse numa configuracao rara de pecas
    (uma dama na fileira de coroacao, por exemplo) escaparia de uma amostra
    pequena.
    """
    motor = MotorDamas(co_modalidade)
    for co_tipo in ("damas_coroar", "damas_capturar_multipla"):
        for fen in receita_de(co_tipo).moldes:
            refletida = espelhar_fen(fen)
            estado = EstadoDamas(
                co_modalidade=co_modalidade, fen_inicial=refletida
            )
            assert motor.lances_legais(estado), (
                f"{fen} espelhada ({refletida}) ficou sem lance legal em "
                f"{co_modalidade}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# 3. A porta que o gerador usa
# ═══════════════════════════════════════════════════════════════════════════


def test_com_as_brancas_a_jogar_NAO_mexe_no_que_ja_esta_certo() -> None:
    """⚠️ Espelhar por espelhar seria trocar a tarefa sem motivo."""
    ja_certa = "W:W10,18,21:B17,20"
    assert com_as_brancas_a_jogar(ja_certa) == ja_certa


def test_com_as_brancas_a_jogar_VIRA_o_que_esta_invertido() -> None:
    """🔒 O caso que existe por causa do relato do dono.

    *"No App eu sou sempre as pecas e arestas azuis. Nas damas o humano sempre
    joga com as pecas iniciando na parte de baixo do tabuleiro, nao no topo."*
    """
    assert com_as_brancas_a_jogar("B:W25,26,29:B16,17,18,21").startswith("W:")


# ═══════════════════════════════════════════════════════════════════════════
# 🔒 ⛔ O LADO DO JOGADOR — o defeito de 16/09/2026
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **O `damas_sobreviver` foi publicado ao avesso por dias.** O acervo dele e
# pescado com `--desvantagem` (o jogador atras), e o que chegava ao painel tinha
# o jogador **a frente em 89%** das vezes. O dono leu a fila antes de qualquer
# medicao: *"Mesmo os desafios de sobreviver contra o Magno, comecam com estados
# de tabuleiro onde o Magno esta totalmente fragilizado"*.
#
# ⚠️ **Nenhuma revisao de codigo pegaria**, e e isso que estes cadeados guardam: o
# acervo, o espelho e a regua faziam cada um o que prometiam. O defeito morava na
# COMPOSICAO — um lance impar troca a vez, e o espelho troca o lado — e so
# aparecia no unico tipo cuja semantica e assimetrica.


def test_com_o_adversario_a_jogar_TROCA_a_vez() -> None:
    """🔒 A vez passa ao outro lado, nos dois sentidos."""
    assert com_o_adversario_a_jogar("W:W25,26:B7,8").startswith("B:")
    assert com_o_adversario_a_jogar("B:W25,26:B7,8").startswith("W:")


def test_com_o_adversario_a_jogar_NAO_MEXE_nas_pecas() -> None:
    """🔒 ⛔ E o que a separa do espelho: nenhuma peca sai do lugar.

    ⚠️ Se um dia alguem "unificar" esta funcao com `espelhar_fen` por elas
    parecerem a mesma coisa, este caso cai — e as duas fazem o **contrario** uma
    da outra (ver a docstring de `com_o_adversario_a_jogar`).
    """
    fen = "W:WK2,12,19:B1,3,4,5"
    virada = com_o_adversario_a_jogar(fen)
    assert virada.split(":")[1:] == fen.split(":")[1:]


def test_o_espelho_e_a_troca_de_vez_sao_OPOSTOS() -> None:
    """🔒 ⛔ A confusao que causou o defeito, travada num caso.

    Partindo da mesma posicao, as duas devolvem as **brancas** com conjuntos de
    pecas diferentes: o espelho entrega ao jogador 1 as pecas do adversario; a
    troca de vez mantem cada um com as suas.
    """
    fen = "B:W25,26,29:B16,17,18,21"
    assert espelhar_fen(fen).startswith("W:")
    assert com_o_adversario_a_jogar(fen).startswith("W:")
    # ⚠️ As brancas do espelho sao as antigas PRETAS (quatro pecas); as da troca
    # de vez continuam sendo as antigas brancas (tres).
    assert len(espelhar_fen(fen).split(":")[1].lstrip("W").split(",")) == 4
    assert len(com_o_adversario_a_jogar(fen).split(":")[1].lstrip("W").split(",")) == 3


def _pecas_por_lado(fen: str) -> tuple[int, int]:
    """(pecas das brancas, pecas das pretas) — as brancas sao sempre o jogador."""
    _, brancas, pretas = fen.split(":")
    return (
        len([c for c in brancas[1:].split(",") if c]),
        len([c for c in pretas[1:].split(",") if c]),
    )


def test_o_PREPARO_preserva_o_lado_do_jogador_no_sobreviver() -> None:
    """🔒 ⛔ O cadeado que vale por todos: o `sobreviver` sai em DESVANTAGEM.

    ⚠️ **O numero nao e arbitrario nem generoso.** O acervo tem o jogador 2,8
    pecas atras; antes da correcao o publicado tinha **+2,3**, e em 89% das
    posicoes o jogador tinha mais pecas. Exigir apenas *"saldo negativo"* ja
    separa o certo do errado por 5 pecas de folga.

    ⚠️ E a pergunta *"o jogador tem mais pecas?"* e a que o dono fez olhando a
    tela, sem medir nada — por isso ela e o cadeado, e nao a media.
    """
    import random

    from job.gerador import _preparar_damas

    moldes = receita_de("damas_sobreviver").moldes
    assert moldes, "o acervo do sobreviver nao pode estar vazio"

    com_mais_pecas = 0
    saldo = 0
    quantas = 120
    for semente in range(quantas):
        sorteio = random.Random(semente)
        publicada = _preparar_damas(sorteio, 8, moldes=moldes).fen
        # ⛔ Quem resolve e sempre o jogador 1 — se isto quebrar, o resto do
        # teste estaria medindo o lado errado e passaria por acidente.
        assert publicada.upper().startswith("W:")
        jogador, adversario = _pecas_por_lado(publicada)
        saldo += jogador - adversario
        if jogador > adversario:
            com_mais_pecas += 1

    assert saldo / quantas < 0, "o jogador do `sobreviver` tem de ficar ATRAS"
    assert com_mais_pecas == 0, (
        f"{com_mais_pecas} de {quantas} posicoes publicadas dao VANTAGEM ao "
        "jogador — o espelho voltou a trocar o lado"
    )


@pytest.mark.parametrize(
    "co_tipo",
    ["damas_coroar", "damas_capturar_multipla", "damas_sacrificio", "damas_sobreviver"],
)
def test_o_PREPARO_entrega_sempre_as_brancas_a_jogar(co_tipo: str) -> None:
    """🔒 A regra canonica do app, nos quatro tipos: o humano e o Jogador 1.

    ⚠️ Vale a pena repetir por tipo mesmo com o teste acima: o caminho novo
    (passar a vez) so roda quando a variacao e impar, e um tipo que amanha peca
    preparo diferente cairia no outro ramo sem ninguem perceber.
    """
    import random

    from job.gerador import _preparar_damas

    moldes = receita_de(co_tipo).moldes
    if not moldes:
        pytest.skip(f"{co_tipo} nao usa molde")
    for semente in range(30):
        publicada = _preparar_damas(random.Random(semente), 8, moldes=moldes).fen
        assert publicada.upper().startswith("W:")

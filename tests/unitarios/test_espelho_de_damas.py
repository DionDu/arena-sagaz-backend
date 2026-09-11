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

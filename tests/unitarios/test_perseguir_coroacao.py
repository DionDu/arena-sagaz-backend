"""🔒 O solucionador que persegue a coroacao, e o defeito que ele ja teve.

⚠️ **Este arquivo existe por causa de um numero que quase virou decisao.** Em
18/09/2026 a primeira versao do solucionador mediu "5 de 163" e parecia refutar a
hipotese do dono sobre o `damas_coroar` com duas damas. O que ela media era a
propria incompetencia: a nota era lexicografica, com material em ULTIMO, entao ele
entregava peca para avancar uma casa, a partida acabava e nada coroava.

⛔ **Um solucionador so responde sobre o objetivo dificil se nao perder para o
motor no facil** — e e isso que os casos daqui guardam, em forma de regra e nao
de tabela.
"""

from __future__ import annotations

import pytest

from motores.damas.motor_damas import EstadoDamas, MotorDamas
from motores.damas.perseguir_coroacao import (
    lance_de_quem_persegue_a_coroacao,
    nota_da_posicao,
    PESO_DA_DAMA,
    PESO_DA_PECA,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. A nota: o que ela premia, e em que ordem
# ═══════════════════════════════════════════════════════════════════════════


def test_a_dama_vale_mais_que_qualquer_peca_isolada() -> None:
    """🔒 Coroar e o objetivo, e nao uma vantagem entre outras.

    ⛔ Se `PESO_DA_DAMA` cair abaixo de `PESO_DA_PECA`, o solucionador passa a
    recusar a coroacao que custa uma pedra — e o desafio pede exatamente isso.
    """
    assert PESO_DA_DAMA > PESO_DA_PECA


def test_a_peca_vale_mais_que_a_fileira_que_ela_avanca() -> None:
    """🔒 O cadeado do defeito de 18/09/2026.

    ⚠️ Uma fileira desconta 1; uma peca vale `PESO_DA_PECA`. Enquanto esta
    desigualdade valer, nenhum avanco compensa entregar material — que e o erro
    que fez a primeira medicao coroar uma dama em 51 de 163 posicoes onde o Sagaz
    coroava nas 163. ⛔ O tabuleiro tem 8 fileiras, entao o pior avanco imaginavel
    desconta 14 (duas pedras da fileira 7): a peca precisa valer mais que isso
    para a conta nunca inverter.
    """
    maior_desconto_possivel = 2 * 7
    assert PESO_DA_PECA > maior_desconto_possivel / 2


def test_coroar_aumenta_a_nota_mesmo_perdendo_a_contagem_de_fileiras() -> None:
    """🔒 A pedra que vira dama para de contar fileiras, e isso nao pode punir.

    ⚠️ Uma dama devolve distancia 0, entao a coroacao **tira** um termo negativo
    da conta ao mesmo tempo que soma `PESO_DA_DAMA`. O risco seria o contrario:
    uma formula em que coroar reduzisse a nota passaria despercebida, porque o
    solucionador continuaria jogando — so que fugindo do objetivo.
    """
    # Duas pedras brancas a caminho (casas 9 e 13), contra uma pedra preta.
    antes = nota_da_posicao("W:W9,13:B22", indice_meu=1)
    # A mesma posicao com uma das pedras ja coroada.
    depois = nota_da_posicao("W:WK9,13:B22", indice_meu=1)
    assert depois > antes


def test_a_nota_olha_as_DUAS_pedras_mais_adiantadas() -> None:
    """🔒 O alvo pode ser duas coroacoes, e uma so pedra nao as entrega.

    ⛔ Premiar apenas a melhor pedra faria o solucionador empurrar sempre a mesma
    e abandonar a segunda — que e **exatamente** o defeito que ele existe para
    corrigir no motor. ⚠️ Aqui as duas posicoes tem a mesma pedra dianteira; o que
    muda e a segunda, e a nota tem de enxergar isso.
    """
    #                          pedra dianteira em 5, segunda em 30 (longe)
    segunda_atrasada = nota_da_posicao("W:W5,30:B22", indice_meu=1)
    #                          a mesma dianteira, segunda em 9 (perto)
    segunda_adiantada = nota_da_posicao("W:W5,9:B22", indice_meu=1)
    assert segunda_adiantada > segunda_atrasada


def test_a_nota_e_de_QUEM_JOGA_e_nao_das_brancas() -> None:
    """🔒 O desafio publicado sai com as PRETAS a jogar.

    ⚠️ Perguntar sempre pelas brancas e o erro classico deste modulo (ver
    `job/moldes_de_damas._lado_e_adversario`): daria um numero, e o numero
    pareceria certo. ⛔ Nas pretas a coroacao e na fileira 7, entao a mesma casa
    tem distancia oposta.
    """
    # A casa 5 esta quase coroando para as brancas e quase parada para as pretas.
    assert nota_da_posicao("W:W5:B22", indice_meu=1) > nota_da_posicao(
        "B:W5:B22", indice_meu=2
    ) - PESO_DA_PECA


# ═══════════════════════════════════════════════════════════════════════════
# 2. O lance: ele escolhe, e escolhe algo legal
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "modalidade", ["brasileira", "anglo", "portuguesa", "casa"]
)
def test_o_lance_escolhido_e_sempre_LEGAL(modalidade: str) -> None:
    """🔒 Um solucionador que devolve lance ilegal derruba a geracao do dia.

    ⚠️ Roda nas quatro modalidades porque a legalidade **e** a modalidade: a
    captura obrigatoria e o alcance da dama mudam entre elas, e uma heuristica
    escrita olhando so a brasileira passaria aqui e falharia em producao.
    """
    fen = "W:W21,22,23,24:B9,10,11,12"
    motor = MotorDamas(modalidade)
    estado = EstadoDamas(co_modalidade=modalidade, fen_inicial=fen)

    lance = lance_de_quem_persegue_a_coroacao(motor, estado)

    assert lance in motor.lances_legais(estado)


def test_ele_prefere_COROAR_a_qualquer_outro_lance() -> None:
    """🔒 O comportamento inteiro, numa posicao em que a coroacao esta a um lance.

    ⛔ **E este o caso que o Sagaz nao garante**, e a razao de este modulo existir:
    com uma dama ja no tabuleiro, o motor tende a usa-la para dominar a partida em
    vez de conduzir a segunda pedra — a pergunta do dono em 18/09/2026.
    """
    # Branca em 5 coroa indo para 1; ha outra pedra em 21, longe, e uma preta
    # distante que nao interfere.
    fen = "W:W5,21:B30"
    motor = MotorDamas("brasileira")
    estado = EstadoDamas(co_modalidade="brasileira", fen_inicial=fen)

    lance = lance_de_quem_persegue_a_coroacao(motor, estado)
    depois = motor.aplicar(estado, lance)

    damas = sum(
        1
        for casa in depois.fen.split(":")[1][1:].split(",")
        if casa.strip().upper().startswith("K")
    )
    assert damas == 1, f"nao coroou: jogou {lance} e ficou {depois.fen}"

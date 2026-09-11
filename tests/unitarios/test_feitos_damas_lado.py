"""⛔ Os feitos das damas são do JOGADOR, e não do tabuleiro (T049t).

═══════════════════════════════════════════════════════════════════════════
⚠️ O DEFEITO QUE ESTE ARQUIVO GUARDA
═══════════════════════════════════════════════════════════════════════════

Em 11/09/2026 o dono curou a primeira fila de verdade e escreveu:

> *"Desafio apenas em 3 lances e quem capturou 2 peças foi o adversário e não o
> humano."*

Ele estava certo, e o desafio `a98bb871` estava publicado no `des`:

    objetivo: capture 2 peças
    1. 15x6      (jogador  1)  — a pessoa captura UMA
    2. 2x9x18    (jogador -1)  — o ADVERSÁRIO captura duas
    3. 11-8      (jogador  1)  — a pessoa joga qualquer coisa

⛔ **O medidor contava todos os lances da fita como se fossem do jogador**, e
`maior_captura` saía 2 — a do adversário. A pessoa só precisava fazer um lance
qualquer depois para "fechar".

⚠️ **E o comentário no código afirmava o contrário do que o código fazia:** *"a
fita de um desafio é do jogador do desafio"*. Não é, e nunca foi — ela inclui os
lances do adversário **de propósito**, senão a sequência não é reproduzível.

⚠️ **Por que a suíte inteira passava:** os 12 vetores de verificação tinham fitas
de **um lance só**. Nenhum exercitava um lance do adversário. O 13º vetor
(`D8-o-adversario-captura-duas-nao-cumpre`) fecha esse buraco no contrato; este
arquivo fecha no medidor.
"""

from __future__ import annotations

import pytest

from motores.damas.feitos_damas import medir
from motores.damas.motor_damas import EstadoDamas, MotorDamas

#: A posição e a fita exatas do desafio que foi publicado com o defeito.
FEN_DE_PRODUCAO = "W:W7,11,14,15:B2,5,10"
FITA_DE_PRODUCAO = ["15x6", "2x9x18", "11-8"]


@pytest.fixture
def bancada():
    """Motor e estado inicial da posição de produção."""
    motor = MotorDamas("casa")
    return motor, EstadoDamas(co_modalidade="casa", fen_inicial=FEN_DE_PRODUCAO)


def test_a_captura_do_ADVERSARIO_nao_entra_na_maior_captura(bancada) -> None:
    """🔒 ⛔ O caso de produção, com o número que o defeito produzia.

    A pessoa capturou **uma** peça; o adversário capturou duas. `maior_captura`
    tem de ser **1**, e era 2.
    """
    motor, inicial = bancada
    feitos = medir(motor, inicial, FITA_DE_PRODUCAO, jogador=1)
    assert feitos["maior_captura"] == 1, (
        "a captura dupla é do adversário (lance 2, jogador -1) e não pode contar "
        "para o objetivo da pessoa"
    )


def test_LANCES_DO_JOGADOR_conta_so_os_dele(bancada) -> None:
    """🔒 ⚠️ Ele **normaliza o XP**, e por isso o erro não era cosmético.

    `tb003_feito_desafio` guarda uma medida com `co_sobre: lances_da_solucao`.
    Contando os dois lados, a fração saía sobre um denominador dobrado — e o XP
    de todo desafio de damas estava calculado sobre um número que não existe.
    """
    motor, inicial = bancada
    feitos = medir(motor, inicial, FITA_DE_PRODUCAO, jogador=1)
    assert feitos["lances_do_jogador"] == 2, "são três lances na fita, dois dela"


def test_o_mesmo_vale_para_quem_joga_de_PRETAS(bancada) -> None:
    """🔒 O controle: medindo o outro lado, os números se invertem.

    ⚠️ Sem este caso, um medidor que simplesmente **ignorasse** o segundo lance
    (em vez de atribuí-lo ao dono certo) passaria nos dois testes de cima. Aqui
    ele falha: quem joga de pretas capturou duas, e `maior_captura` tem de ser 2.
    """
    motor, inicial = bancada
    feitos = medir(motor, inicial, FITA_DE_PRODUCAO, jogador=-1)
    assert feitos["maior_captura"] == 2
    assert feitos["lances_do_jogador"] == 1


def test_capturas_EXTRAS_tambem_sao_so_do_jogador(bancada) -> None:
    """🔒 A terceira medida que o laço alimentava sem olhar de quem era o lance."""
    motor, inicial = bancada
    assert medir(motor, inicial, FITA_DE_PRODUCAO, jogador=1)["capturas_extras"] == 0
    assert medir(motor, inicial, FITA_DE_PRODUCAO, jogador=-1)["capturas_extras"] == 1


def test_COROAR_do_adversario_nunca_contou_e_continua_sem_contar() -> None:
    """🔒 A medida que já estava certa — **por acidente**, e agora por construção.

    ⚠️ `damas_coroadas` compara as damas **de `jogador`** antes e depois, então um
    lance do adversário nunca a incrementava. ⛔ Mas estar certo por acidente não
    é estar protegido: se alguém trocasse a comparação por "apareceu uma dama no
    tabuleiro", o defeito nasceria de novo, e sem este caso ninguém veria.
    """
    motor = MotorDamas("brasileira")
    # As pretas estão a um passo de coroar (casa 29 é fileira de coroação delas);
    # quem resolve o desafio é o branco.
    inicial = EstadoDamas(co_modalidade="brasileira", fen_inicial="W:W14:B25")
    feitos = medir(motor, inicial, ["14-10", "25-29"], jogador=1)
    assert feitos["damas_coroadas"] == 0, (
        "quem coroou foi o adversário; para o jogador do desafio isso é zero"
    )
    assert medir(motor, inicial, ["14-10", "25-29"], jogador=-1)["damas_coroadas"] == 1

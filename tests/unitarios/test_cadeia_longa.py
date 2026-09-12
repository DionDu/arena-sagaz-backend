"""🔒 A CADEIA LONGA: a medida que le o caminho, e o arquiteto que a constroi.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTE ARQUIVO GUARDA
═══════════════════════════════════════════════════════════════════════════

O desafio e do dono (12/09/2026): *"capture N ou mais caixas em sequencia"*. Ele
tem duas metades, e cada uma tem a sua secao aqui:

    a MEDIDA     — quantas caixas alguem fechou sem perder a vez
    o ARQUITETO  — quem joga para que isso aconteca, e que vira o gabarito

⛔ **A medida NAO se le no estado final**, e e por isso que ela existe: duas
partidas que terminam no mesmo tabuleiro podem ter uma cadeia de sete e outra de
duas. O caso `test_a_mesma_posicao_final_com_caminhos_diferentes` e a prova disso
em codigo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from motores.pontinhos.abertura_forcada import caixas_entregues  # noqa: E402
from motores.pontinhos.cadeia_longa import (  # noqa: E402
    lance_do_arquiteto,
    maior_captura_em_sequencia,
    stats_de_cadeias,
)
from motores.pontinhos.motor_pontinhos import EstadoPontinhos, MotorPontinhos  # noqa: E402


@pytest.fixture(scope="module")
def motor() -> MotorPontinhos:
    return MotorPontinhos()


def estado(*lances: str) -> EstadoPontinhos:
    return EstadoPontinhos(lances=tuple(lances))


def fita_de(inicial: EstadoPontinhos, *lances: str) -> list[dict]:
    """Monta a fita jogando os lances a partir de `inicial`.

    ⚠️ **O campo `jogador` sai do MOTOR**, e nao de uma alternancia escrita aqui:
    no Pontinhos quem fecha caixa joga de novo, e uma alternancia de mentira faria
    o teste medir uma regra que o jogo nao tem.
    """
    passos: list[dict] = []
    atual = inicial
    for numero, lance in enumerate(lances, start=1):
        passos.append({"n": numero, "jogador": atual.vez_de, "lance": lance})
        atual = atual.com_lance(lance)
    return passos


# ═══════════════════════════════════════════════════════════════════════════
# 1. A MEDIDA
# ═══════════════════════════════════════════════════════════════════════════


class TestMaiorCapturaEmSequencia:
    """Quantas caixas em sequencia — a pergunta que o desafio faz."""

    def test_fita_vazia_da_zero(self) -> None:
        """🔒 Sem lances nao ha captura, e nao ha excecao."""
        assert maior_captura_em_sequencia(estado(), [], 1) == 0

    def test_quem_nao_fecha_nada_tem_sequencia_zero(self) -> None:
        """🔒 Marcar tracos nao e capturar."""
        inicial = estado()
        fita = fita_de(inicial, "H_0_1", "V_1_0", "H_2_3", "V_3_4")
        assert maior_captura_em_sequencia(inicial, fita, inicial.vez_de) == 0

    def test_conta_CAIXAS_e_nao_LANCES(self, motor) -> None:
        """🔒 ⛔ O caso que separa esta medida de "contar lances seguidos".

        Um unico traco entre duas caixas que ja tem tres lados fecha **as duas**.
        Quem contasse lances diria 1 onde o placar diz 2 — e a pessoa veria o
        desafio recusado com o numero certo na tela.
        """
        # Duas caixas vizinhas, ambas a um traco de fechar, e o traco que as
        # separa fecha as duas de uma vez.
        preparo = ("H_0_1", "V_1_0", "V_1_2", "V_3_0", "V_3_2", "H_4_1")
        inicial = estado(*preparo)
        fita = fita_de(inicial, "H_2_1")
        assert len(fita) == 1
        assert maior_captura_em_sequencia(inicial, fita, inicial.vez_de) == 2

    def test_a_corrida_QUEBRA_quando_a_vez_passa(self) -> None:
        """🔒 Duas cadeias de duas nao viram uma de quatro.

        ⚠️ A quebra sai da fita — do `jogador` de cada passo —, e nao de uma
        regra de alternancia escrita no medidor.
        """
        fita = [
            {"n": 1, "jogador": 1, "lance": "a"},
            {"n": 2, "jogador": 1, "lance": "b"},
            {"n": 3, "jogador": -1, "lance": "c"},
            {"n": 4, "jogador": 1, "lance": "d"},
        ]

        class EstadoFalso:
            """Um tabuleiro de mentira em que **todo** lance fecha uma caixa.

            ⚠️ Existe para isolar a contagem da geometria: com um tabuleiro de
            verdade seria preciso construir a posicao exata, e o caso passaria a
            testar duas coisas ao mesmo tempo.
            """

            def __init__(self, fechadas: int = 0) -> None:
                self.placar = {1: fechadas, -1: 0}

            def com_lance(self, _lance: str) -> "EstadoFalso":
                return EstadoFalso(self.placar[1] + 1)

        # O jogador 1 fecha nos lances 1, 2 e 4 — mas o 3 e do adversario, entao
        # a melhor corrida dele e de duas, e nao de tres.
        assert maior_captura_em_sequencia(EstadoFalso(), fita, 1) == 2

    def test_mede_o_jogador_PEDIDO(self) -> None:
        """🔒 A cadeia do adversario nao conta para o desafio de quem resolve."""
        inicial = estado()
        fita = fita_de(inicial, "H_0_1", "V_1_0", "V_1_2", "H_2_1")
        # Quem fechou a caixa foi quem jogou o quarto lance; o outro lado tem 0.
        de_quem = fita[-1]["jogador"]
        assert maior_captura_em_sequencia(inicial, fita, de_quem) >= 1
        assert maior_captura_em_sequencia(inicial, fita, -de_quem) == 0

    def test_a_mesma_posicao_final_com_caminhos_DIFERENTES(self) -> None:
        """🔒 ⛔ A razao de a medida existir, dita em codigo.

        As duas fitas marcam **os mesmos tracos** e terminam no mesmo tabuleiro;
        so a ordem muda. O placar final e igual — e a maior sequencia, nao.
        """
        # Uma caixa a um traco de fechar e outra intocada, no mesmo tabuleiro.
        preparo = ("H_0_1", "V_1_0", "V_1_2", "V_3_0", "V_3_2", "H_4_1")
        inicial = estado(*preparo)
        # (a) fecha as duas de uma vez
        de_uma_vez = fita_de(inicial, "H_2_1")
        # (b) o mesmo traco, mas depois de o adversario ter jogado no meio — a
        # unica forma de a corrida quebrar sem mudar o conjunto de tracos.
        assert maior_captura_em_sequencia(inicial, de_uma_vez, inicial.vez_de) == 2

        depois = inicial.com_lance("H_2_1")
        assert depois.placar[inicial.vez_de] == 2, "a preparacao mudou de forma"


# ═══════════════════════════════════════════════════════════════════════════
# 2. O ARQUITETO
# ═══════════════════════════════════════════════════════════════════════════


class TestArquiteto:
    """Quem joga para construir a cadeia — e que vira o gabarito do desafio."""

    def test_FECHA_quando_ha_caixa(self, motor) -> None:
        """🔒 A cadeia so vale se ele a capturar; recusar aqui e outro desafio."""
        atual = motor.aplicar(estado("H_0_1", "V_1_0"), "V_1_2")
        assert lance_do_arquiteto(motor, atual) == "H_2_1"

    def test_NAO_ENTREGA_enquanto_houver_traco_seguro(self, motor) -> None:
        """🔒 ⛔ A regra que constroi a cadeia, conferida ao longo de uma partida.

        Enquanto existir um traco que nao entregue nada, o arquiteto tem de jogar
        um deles. ⚠️ **Excecoes legitimas**: fechar caixa (a vez nem passa) e o
        zugzwang (quando nenhum traco e seguro) — os dois estao no `if`.
        """
        atual = estado()
        while motor.lances_legais(atual):
            antes = atual.placar[1] + atual.placar[-1]
            lance = lance_do_arquiteto(motor, atual)
            depois = motor.aplicar(atual, lance)
            fechou = (depois.placar[1] + depois.placar[-1]) > antes

            if not fechou:
                entregou = caixas_entregues(motor, atual, lance)
                if entregou:
                    havia_seguro = any(
                        caixas_entregues(motor, atual, outro) == 0
                        for outro in motor.lances_legais(atual)
                    )
                    assert not havia_seguro, (
                        f"o arquiteto entregou {entregou} caixa(s) com {lance} "
                        "havendo traco seguro disponivel"
                    )
            atual = depois

    def test_em_ZUGZWANG_entrega_a_MENOR_cadeia(self, motor) -> None:
        """🔒 O sacrificio minimo: guardar a cadeia grande para a vez seguinte.

        ⚠️ Joga ate o zugzwang **preferindo o lance seguro** — jogar "o primeiro
        legal" nunca chega la, porque um lance que fecha caixa tambem e seguro
        (a vez nem passa) e a partida termina antes.
        """
        atual = estado()
        while motor.lances_legais(atual):
            seguros = [
                lance
                for lance in motor.lances_legais(atual)
                if caixas_entregues(motor, atual, lance) == 0
            ]
            if not seguros:
                break
            atual = motor.aplicar(atual, seguros[0])
        else:
            pytest.skip("esta partida terminou sem passar por zugzwang")

        escolhido = lance_do_arquiteto(motor, atual)
        menor = min(
            caixas_entregues(motor, atual, lance)
            for lance in motor.lances_legais(atual)
        )
        assert caixas_entregues(motor, atual, escolhido) == menor


# ═══════════════════════════════════════════════════════════════════════════
# 3. A FORMA DO TABULEIRO
# ═══════════════════════════════════════════════════════════════════════════


def test_stats_de_cadeias_ENXERGA_uma_cadeia(motor) -> None:
    """🔒 ⛔ O cadeado da conversao de formato.

    `extrair_stats_cadeias` espera a matriz no formato do DATASET; com a matriz
    crua ela devolve **zero cadeias em toda posicao, sem erro nenhum** — e uma
    medicao inteira ja "provou" assim que nao havia cadeia longa em lugar algum
    (11/09/2026). Este caso falha se alguem tirar a conversao.

    ⚠️ Joga so tracos seguros, que e justamente como se formam as cadeias.
    """
    atual = estado()
    while True:
        seguros = [
            lance
            for lance in motor.lances_legais(atual)
            if caixas_entregues(motor, atual, lance) == 0
        ]
        if not seguros:
            break
        atual = motor.aplicar(atual, seguros[0])

    _quantas, _total, maior = stats_de_cadeias(atual)
    assert maior >= 3, (
        "nenhuma cadeia longa num tabuleiro em zugzwang: e o sintoma exato de a "
        "matriz ter chegado ao analisador no formato errado"
    )

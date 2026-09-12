"""🔒 O jogador GULOSO, que é a metade da conta `D > G`.

═══════════════════════════════════════════════════════════════════════════
⚠️ O DESENHO DO DONO, 11/09/2026
═══════════════════════════════════════════════════════════════════════════

> *"1. Entregamos um estado para o usuário com caixas a capturar. Se ele capturar
> de forma gulosa ele fecha o jogo com 5 caixas. 2. Se capturar usando double
> dealing ele fecha o jogo com 7 caixas. 3. Neste exemplo o desafio seria:
> capture 7 ou mais caixas."*

⚠️ **É o desenho que dispensa o filtro de erro do adversário**: a dificuldade
deixa de depender dele e passa a vir da escolha de quem resolve. O objetivo
exclui a solução ingênua **por construção**.

⛔ **E o guloso tem de ser o próprio Magno com uma única diferença** — quando há
caixa, ele pega. Um "jogador ruim" genérico jogaria pior em tudo, e `D - G`
mediria *"não sabe jogar"* em vez de *"não sabe fazer double dealing"*.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from job import semente as semente_mod  # noqa: E402
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402
from motores.pontinhos.guloso import (  # noqa: E402
    caixas_do_guloso,
    lance_que_mais_fecha,
)
from motores.pontinhos.motor_pontinhos import EstadoPontinhos, MotorPontinhos  # noqa: E402
from motores.pontinhos.politica import JogadorPontinhos  # noqa: E402


@pytest.fixture(scope="module")
def motor() -> MotorPontinhos:
    return MotorPontinhos()


@pytest.fixture(scope="module")
def politica(motor: MotorPontinhos) -> JogadorPontinhos:
    return JogadorPontinhos(motor)


def estado(*lances: str) -> EstadoPontinhos:
    return EstadoPontinhos(lances=tuple(lances))


class TestLanceQueMaisFecha:
    """Qual caixa o guloso pega — e por que ele não pega a primeira que vê."""

    def test_no_tabuleiro_vazio_nao_ha_o_que_fechar(self, motor) -> None:
        """🔒 Devolve `None`, e aí quem escolhe é a política."""
        assert lance_que_mais_fecha(motor, estado()) is None

    def test_acha_o_lance_que_fecha(self, motor) -> None:
        """🔒 Com uma caixa a um lado de fechar, ele encontra o traço."""
        atual = motor.aplicar(estado("H_0_1", "V_1_0"), "V_1_2")
        achado = lance_que_mais_fecha(motor, atual)
        assert achado == "H_2_1"

    def test_prefere_fechar_DUAS_a_fechar_uma(self, motor) -> None:
        """🔒 ⚠️ Senão a comparação mediria desatenção, e não recusa.

        Um traço entre duas caixas que já têm três lados fecha **as duas** de uma
        vez. Um guloso que pegasse a primeira que visse seria burro de um jeito
        diferente do que o desafio quer medir — e `D - G` ficaria inflado por um
        descuido que nada tem a ver com o *double dealing*.
        """
        # Duas caixas vizinhas (0,0) e (1,0), ambas a um traço de fechar, e o
        # traço que as separa fecha as duas.
        atual = estado()
        for lance in ("H_0_1", "V_1_0", "V_1_2", "V_3_0", "V_3_2", "H_4_1"):
            atual = motor.aplicar(atual, lance)
        antes = atual.placar[1] + atual.placar[-1]
        escolhido = lance_que_mais_fecha(motor, atual)
        depois = motor.aplicar(atual, escolhido)
        assert (depois.placar[1] + depois.placar[-1]) - antes == 2


class TestCaixasDoGuloso:
    """A conta de `G`."""

    def test_joga_a_partida_ATE_O_FIM(self, motor, politica) -> None:
        """🔒 `G` é o placar final, e não um placar parcial.

        ⚠️ O objetivo do desafio tem janela de **partida inteira**
        (`chegar_ao_placar`), então comparar em qualquer outro ponto compararia
        outra coisa.
        """
        total = caixas_do_guloso(
            politica,
            motor,
            estado(),
            1,
            nivel=NivelDeMotor.SAGAZ,
            nivel_do_adversario=NivelDeMotor.SAGAZ,
            semente_do_lance=semente_mod.semente_do_lance,
            nu_semente=42,
        )
        outro = caixas_do_guloso(
            politica,
            motor,
            estado(),
            -1,
            nivel=NivelDeMotor.SAGAZ,
            nivel_do_adversario=NivelDeMotor.SAGAZ,
            semente_do_lance=semente_mod.semente_do_lance,
            nu_semente=42,
        )
        # O tabuleiro 4x3 tem 12 caixas, e todas acabam fechadas por alguém.
        assert total + outro == 12

    def test_o_resultado_e_REPRODUZIVEL(self, motor, politica) -> None:
        """🔒 ⛔ Sem isto, o enunciado publicado deixaria de valer.

        O número do enunciado (*"capture N ou mais"*) é `G + k`. Se `G` mudasse
        entre duas execuções, o job recalcularia outro `N` para **o mesmo
        desafio** — e o que está publicado no aparelho de alguém não muda.
        """
        args = dict(
            nivel=NivelDeMotor.SAGAZ,
            nivel_do_adversario=NivelDeMotor.CACAU,
            semente_do_lance=semente_mod.semente_do_lance,
            nu_semente=20260911,
        )
        inicial = estado("H_0_1", "V_1_0", "H_2_3", "V_3_4")
        primeiro = caixas_do_guloso(politica, motor, inicial, inicial.vez_de, **args)
        segundo = caixas_do_guloso(politica, motor, inicial, inicial.vez_de, **args)
        assert primeiro == segundo

    def test_a_SEMENTE_muda_o_resultado_do_adversario_fraco(
        self, motor, politica
    ) -> None:
        """🔒 ⚠️ O controle do teste anterior.

        Se o resultado fosse igual com **qualquer** semente, o teste de
        reprodutibilidade estaria passando por não haver acaso nenhum — e não
        provaria nada. Com a Cacau (que erra de propósito em 80% dos lances) duas
        sementes diferentes têm de poder divergir.
        """
        args = dict(
            nivel=NivelDeMotor.SAGAZ,
            nivel_do_adversario=NivelDeMotor.CACAU,
            semente_do_lance=semente_mod.semente_do_lance,
        )
        inicial = estado("H_0_1", "V_1_0")
        resultados = {
            caixas_do_guloso(
                politica, motor, inicial, inicial.vez_de, nu_semente=n, **args
            )
            for n in range(1, 12)
        }
        assert len(resultados) > 1, "com a Cacau, sementes diferentes têm de divergir"

    def test_o_guloso_NUNCA_recusa_uma_caixa(self, motor, politica) -> None:
        """🔒 ⛔ A propriedade que define o guloso, conferida lance a lance.

        Reproduz a mesma partida do guloso e verifica que, em toda posição em que
        havia caixa para fechar **na vez dele**, ele fechou.
        """
        inicial = estado("H_0_1", "V_1_0", "H_2_3")
        jogador = inicial.vez_de

        # Repete a lógica do módulo, guardando as decisões para conferir.
        atual, numero, recusas = inicial, 1, 0
        while motor.lances_legais(atual):
            fecha = lance_que_mais_fecha(motor, atual) if atual.vez_de == jogador else None
            if fecha is not None:
                antes = atual.placar[jogador]
                atual = motor.aplicar(atual, fecha)
                if atual.placar[jogador] <= antes:
                    recusas += 1
            else:
                atual = motor.aplicar(
                    atual,
                    politica.escolher_lance(
                        atual,
                        NivelDeMotor.SAGAZ,
                        semente=semente_mod.semente_do_lance(7, numero),
                    ),
                )
            numero += 1

        assert recusas == 0

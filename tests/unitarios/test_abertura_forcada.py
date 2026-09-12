"""🔒 ⛔ O desafio não pode depender de o adversário jogar mal.

═══════════════════════════════════════════════════════════════════════════
⚠️ A REGRA, E DE ONDE ELA VEIO
═══════════════════════════════════════════════════════════════════════════

O dono, em 11/09/2026, depois de curar a primeira fila de verdade:

> *"O problema não é o adversário abrir a cadeia, o problema é quando ele abre a
> cadeia sendo que há diversos outros traços que nem entregariam caixa de graça.
> O 'entregar' cadeia em um desafio deveria ser meio que forçado: eu humano cedo
> 2 caixas para a CPU e o obrigo a abrir a cadeia."*

⚠️ **Abrir cadeia não é erro** — é como o Jogo dos Pontinhos termina. Medido nas
partidas reais do `prd` (120 partidas): das 195 cadeias de 3+ caixas abertas,
**146 eram forçadas** e 49 tinham alternativa segura. São essas 49 que produzem
desafio ruim.

⛔ **O caso que originou a regra** é o `V_1_4` do desafio `d5af2ae1`: havia
`V_7_0` e `H_8_1` entregando **zero** caixas, e a rede escolheu um que entregava
**seis**. ⚠️ E não foi o epsilon — o `co_acao` era `cnn_argmax_absoluto`, ou seja,
o adversário jogou o que considerou o **melhor** lance.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from motores.pontinhos.abertura_forcada import (  # noqa: E402
    caixas_entregues,
    dependeu_de_erro,
    lance_seguro,
)
from motores.pontinhos.motor_pontinhos import EstadoPontinhos, MotorPontinhos  # noqa: E402


@pytest.fixture(scope="module")
def motor() -> MotorPontinhos:
    """O motor serve só de árbitro aqui — regras, sem busca."""
    return MotorPontinhos()


def estado(*lances: str) -> EstadoPontinhos:
    """Um tabuleiro com estes traços marcados, na ordem."""
    return EstadoPontinhos(lances=tuple(lances))


def ate_o_zugzwang(motor: MotorPontinhos) -> EstadoPontinhos:
    """Joga preferindo o lance SEGURO, até chegar a uma posição sem nenhum.

    ⚠️ **Jogar "o primeiro lance legal" nunca chega a zugzwang**, e descobrir isso
    foi o que este arquivo ensinou: sempre sobra algum traço solto, e um lance que
    **fecha caixa** também conta como seguro (a vez nem passa). A posição sem
    saída só aparece quando os dois lados **evitam** entregar — que é como gente
    joga, e é o que faz o tabuleiro encher até só restarem traços de cadeia.

    ⛔ Isto não é uma política de jogo de verdade (ninguém usa isto para escolher
    lance): é o caminho mais curto para uma posição que existe em toda partida
    real. Medido no `prd`: 105 de 120 partidas passam por uma.
    """
    atual = estado()
    while True:
        seguro = lance_seguro(motor, atual)
        if seguro is None:
            return atual
        atual = motor.aplicar(atual, seguro)


def fechar_uma_caixa(motor: MotorPontinhos) -> tuple[EstadoPontinhos, str]:
    """Uma posição em que existe um traço que FECHA caixa, e qual é ele.

    ⚠️ Montada jogando de verdade, e não escrita à mão: os rótulos do tabuleiro
    4x3 seguem as coordenadas da matriz do motor, e uma sequência inventada à mão
    tem grande chance de ser ilegal — o teste falharia por um motivo que não é o
    que ele investiga.
    """
    atual = estado()
    for lance in ("H_0_1", "V_1_0", "V_1_2"):
        atual = motor.aplicar(atual, lance)
    # Agora `H_2_1` fecha a caixa de cima à esquerda.
    return atual, "H_2_1"


class TestCaixasEntregues:
    """Quanto o adversário leva de graça depois de um lance."""

    def test_o_primeiro_lance_do_jogo_nao_entrega_nada(self, motor) -> None:
        """🔒 Tabuleiro vazio: nenhum traço deixa caixa a um passo de fechar."""
        assert caixas_entregues(motor, estado(), "H_0_1") == 0

    def test_FECHAR_caixa_nao_e_entregar(self, motor) -> None:
        """🔒 ⚠️ Quem fecha joga de novo — a vez nem chega ao outro lado.

        ⛔ Sem este caso, **todo** lance que fecha caixa seria contado como
        entrega, e a regra recusaria justamente os melhores desafios.
        """
        posicao, lance_que_fecha = fechar_uma_caixa(motor)
        assert caixas_entregues(motor, posicao, lance_que_fecha) == 0

    def test_o_lance_que_deixa_a_caixa_pronta_ENTREGA(self, motor) -> None:
        """🔒 O contrário: fechar a terceira aresta de uma caixa a dá de presente."""
        atual = motor.aplicar(estado("H_0_1", "V_1_0"), "V_1_2")
        # A caixa está com três lados; qualquer lance que passe a vez a entrega.
        assert caixas_entregues(motor, atual, "H_0_3") >= 1


class TestLanceSeguro:
    """A pergunta que a regra faz: **existia** alternativa?"""

    def test_no_comeco_do_jogo_existe_lance_seguro(self, motor) -> None:
        """🔒 E ele é devolvido pelo rótulo, não como `True`.

        ⚠️ Quem recusa um desafio precisa poder dizer **qual** era a alternativa;
        sem isso a recusa vira um "não" sem argumento.
        """
        achado = lance_seguro(motor, estado())
        assert achado in motor.lances_legais(estado())

    def test_devolve_None_quando_TODOS_entregam(self, motor) -> None:
        """🔒 ⚠️ É a definição operacional de zugzwang — e o desafio legítimo.

        Com os dois lados evitando entregar, o tabuleiro enche até restarem só
        traços de cadeia. Aí não há mais para onde correr, e é **esse** o momento
        em que abrir deixa de ser erro.
        """
        posicao = ate_o_zugzwang(motor)
        assert lance_seguro(motor, posicao) is None
        assert motor.lances_legais(posicao), "a partida não podia ter acabado"
        # E, de fato, todo traço que resta entrega alguma coisa.
        assert all(
            caixas_entregues(motor, posicao, lance) >= 1
            for lance in motor.lances_legais(posicao)
        )


class TestDependeuDeErro:
    """⛔ A regra completa, aplicada a uma fita de gabarito."""

    def test_fita_sem_lance_do_adversario_passa(self, motor) -> None:
        """🔒 Só os lances do OUTRO são julgados."""
        fita = [{"n": 1, "jogador": 1, "lance": "H_0_1"}]
        assert dependeu_de_erro(motor, estado(), fita, jogador=1) is None

    def test_recusa_quando_o_adversario_entregou_tendo_saida(self, motor) -> None:
        """🔒 ⛔ O caso que a regra existe para pegar.

        Monta-se uma posição em que uma caixa está com três lados (portanto há
        traço que entrega) **e** ainda sobra tabuleiro livre (portanto há traço
        que não entrega). O adversário joga o que entrega.
        """
        inicial = motor.aplicar(estado("H_0_1", "V_1_0"), "V_1_2")
        # Confere a montagem: tem de haver as duas coisas na mesma posição.
        assert lance_seguro(motor, inicial) is not None
        entrega = next(
            lance
            for lance in motor.lances_legais(inicial)
            if caixas_entregues(motor, inicial, lance) >= 1
        )

        fita = [{"n": 1, "jogador": -1, "lance": entrega}]
        motivo = dependeu_de_erro(motor, inicial, fita, jogador=1)
        assert motivo is not None
        assert entrega in motivo, "o motivo tem de nomear o lance recusado"

    def test_aceita_quando_o_adversario_NAO_tinha_saida(self, motor) -> None:
        """🔒 ✅ O zugzwang — o desafio legítimo, que não pode ser recusado.

        ⚠️ É o caso mais importante do arquivo: uma regra que recusasse também
        este esvaziaria a fila e mataria justamente o *double-cross*, que é a
        jogada que o dono quer premiar.
        """
        posicao = ate_o_zugzwang(motor)
        forcado = motor.lances_legais(posicao)[0]
        assert caixas_entregues(motor, posicao, forcado) >= 1, "ele entrega mesmo"
        fita = [{"n": 1, "jogador": -1, "lance": forcado}]
        assert dependeu_de_erro(motor, posicao, fita, jogador=1) is None

    def test_o_lance_do_JOGADOR_nunca_e_recusado(self, motor) -> None:
        """🔒 ⚠️ Quem resolve o desafio pode — e deve — ceder caixas.

        ⛔ Julgar os dois lados recusaria exatamente a jogada que o dono descreveu:
        *"eu humano cedo 2 caixas para a CPU e o obrigo a abrir a cadeia"*. É o
        mesmo erro de lado que já derrubou o medidor de feitos das damas neste
        mesmo dia.
        """
        inicial = motor.aplicar(estado("H_0_1", "V_1_0"), "V_1_2")
        entrega = next(
            lance
            for lance in motor.lances_legais(inicial)
            if caixas_entregues(motor, inicial, lance) >= 1
        )
        fita = [{"n": 1, "jogador": 1, "lance": entrega}]
        assert dependeu_de_erro(motor, inicial, fita, jogador=1) is None

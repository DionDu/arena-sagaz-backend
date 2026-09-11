"""T049g - os MOLDES de damas, e o que um erro de transcricao faria calado.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE — E A DATA IMPORTA
═══════════════════════════════════════════════════════════════════════════

Ate 11/09/2026 os moldes eram **oito**, escritos a mao. Depois da cacada de 300
candidatas sao **170**, colados de uma saida de script. A mudanca de escala muda
a especie de defeito que se pode esperar:

  · ⛔ **uma FEN trocada por engano continua sendo uma posicao legal** — e
    simplesmente OUTRA. O gerador partiria dela, acharia solucao, mediria a regua
    e publicaria. Nada erraria;
  · ⛔ **um molde TRIVIAL publica um desafio de um lance.** Ja aconteceu: dois
    candidatos passaram na peneira (que roda so na brasileira) com a portuguesa
    cumprindo no **lance 1**, e ⚠️ nada no log acusaria — o desafio sairia bem
    formado, um dia de cada quatro.

Por isso os cadeados daqui perguntam pela **posicao**, e nao pelo texto. Eles sao
baratos de proposito: so geracao de lances, ⛔ **sem busca** — a peneira com
Sagaz e trabalho de `scripts/cacar_moldes_damas.py`, que leva horas e nao cabe
numa suite.
"""

from __future__ import annotations

import pytest

from job.moldes_de_damas import MODALIDADES, moldes_triviais
from job.tipos_de_desafio import receita_de
from motores.damas.motor_damas import EstadoDamas, MotorDamas

#: Os dois tipos de damas que usam molde.
TIPOS = ("damas_coroar", "damas_capturar_multipla")

#: Piso de moldes por tipo.
#:
#: ⚠️ **Nao e numero de enfeite:** a fila publica um desafio de damas a cada dois
#: dias, rodiziando quatro modalidades sobre os MESMOS moldes. Com meia duzia, a
#: mesma posicao volta dentro de um mes — foi o que aconteceu no `des` com quatro
#: moldes, e e a razao de T049g existir. Este piso pega a exclusao acidental de um
#: pedaco da lista, que e o acidente provavel num arquivo de 170 linhas de dado.
PISO_DE_MOLDES = {"damas_coroar": 100, "damas_capturar_multipla": 8}


def moldes(co_tipo: str) -> tuple[str, ...]:
    """Os moldes daquele tipo, como o gerador os ve."""
    return tuple(receita_de(co_tipo).moldes)


# ═══════════════════════════════════════════════════════════════════════════
# 1. A transcricao
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("co_tipo", TIPOS)
def test_os_moldes_sao_DISTINTOS_dentro_do_tipo(co_tipo) -> None:
    """Molde repetido nao quebra nada — so **desperdica variedade**, calado.

    ⚠️ E o desperdicio e o problema que T049g veio resolver: o gerador sorteia um
    molde por dia, e uma FEN duplicada dobra a chance daquela posicao sair.
    """
    lista = moldes(co_tipo)
    repetidos = {fen for fen in lista if lista.count(fen) > 1}
    assert not repetidos, f"{co_tipo} tem molde(s) repetido(s): {repetidos}"


def test_nenhum_molde_APARECE_NOS_DOIS_tipos() -> None:
    """A mesma posicao servindo a dois objetivos seria suspeita.

    Os dois tipos pedem coisas diferentes (coroar uma pedra x capturar duas em
    sequencia), e as candidatas sao geradas por funcoes diferentes. Uma FEN nos
    dois lados quase certamente e erro de colagem entre as duas listas.
    """
    coroar = set(moldes("damas_coroar"))
    capturar = set(moldes("damas_capturar_multipla"))
    assert not (coroar & capturar), f"FEN nos dois tipos: {coroar & capturar}"


@pytest.mark.parametrize("co_tipo", TIPOS)
def test_ha_moldes_SUFICIENTES_para_a_fila_nao_repetir(co_tipo) -> None:
    """🔒 O piso que pega um pedaco da lista apagado por acidente.

    ⚠️ **Com quatro moldes a fila repetiu a mesma FEN em sete dias no `des`** (com
    sementes diferentes), e foi esse relato que abriu T049g.
    """
    assert len(moldes(co_tipo)) >= PISO_DE_MOLDES[co_tipo], (
        f"{co_tipo} tem {len(moldes(co_tipo))} moldes, e o piso e "
        f"{PISO_DE_MOLDES[co_tipo]}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. Toda FEN descreve uma posicao jogavel
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("co_tipo", TIPOS)
@pytest.mark.parametrize("co_modalidade", MODALIDADES)
def test_todo_molde_e_POSICAO_LEGAL_com_as_brancas_a_jogar(
    co_tipo, co_modalidade
) -> None:
    """🔒 A FEN carrega ate o motor, nas quatro modalidades, e tem lance.

    ⛔ **Uma posicao sem lance legal para as brancas e partida acabada**, e o
    gerador a descartaria em silencio — o dia viraria "sem candidato", e quem
    investigasse procuraria defeito no gerador, nao na lista de moldes.

    ⚠️ A FEN tambem tem de **sobreviver a ida e volta**: o motor a reescreve, e
    uma casa fora de 1..32 ou repetida se perderia aqui.
    """
    motor = MotorDamas(co_modalidade)
    for fen in moldes(co_tipo):
        estado = EstadoDamas(co_modalidade=co_modalidade, fen_inicial=fen)
        assert estado.fen.startswith("W:"), f"{fen}: nao e a vez das brancas"
        assert motor.lances_legais(estado), (
            f"{fen}: nenhum lance legal para as brancas em {co_modalidade} — "
            "isto e partida acabada, e o gerador descartaria o dia calado"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. ⛔ Nenhum molde entrega o objetivo no primeiro lance
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("co_tipo", TIPOS)
def test_nenhum_molde_ENTREGA_o_objetivo_no_primeiro_lance(co_tipo) -> None:
    """🔒 ⛔ O cadeado que 13 moldes reprovaram em 11/09/2026.

    ⚠️ **A cacada media com o Sagaz JOGANDO A PARTIDA, e nao resolvendo o
    desafio.** Ele nao coroa de cara porque coroar de cara costuma ser mau lance —
    uma pedra que avanca sozinha e capturada na resposta. Entao a medicao dizia
    *"objetivo no lance 3"* em posicoes onde **qualquer pessoa cumpre no lance 1**:
    quem joga o desafio nao esta jogando para vencer, esta cumprindo a tarefa.

    Reprovaram **10 dos 171** moldes de coroar e **3 dos 12** de captura — estes
    tres eram fundadores escritos a mao em 09/09, e os outros dez tinham passado
    pela peneira do Sagaz.

    ⛔ **O desafio sairia bem formado**: posicao legal, solucao achada, regua
    medida, XP calculado — e resolvido no primeiro toque, sem nada no log acusar.

    ⚠️ A pergunta mora em `job/moldes_de_damas.py`, e **nao aqui**: o script da
    cacada faz a mesma pergunta na peneira, e duas copias do criterio divergiriam
    — no dia em que discordassem, quem estivesse errado mandaria.
    """
    triviais = moldes_triviais(moldes(co_tipo), co_tipo)
    assert not triviais, (
        f"{co_tipo}: {len(triviais)} molde(s) entregam o objetivo no primeiro "
        f"lance — {triviais}"
    )


def test_o_verificador_ENXERGA_um_molde_trivial() -> None:
    """🔒 O controle negativo: sem ele o caso acima poderia ser decoracao.

    A FEN abaixo e um dos fundadores **removidos** em 11/09/2026 — as brancas
    capturam duas pretas de uma vez, no primeiro lance, nas quatro modalidades.
    Se um dia ela deixar de ser acusada, o verificador parou de verificar.
    """
    trivial = "W:W27,28,31:B15,19,23,4"
    achados = moldes_triviais([trivial], "damas_capturar_multipla")
    assert trivial in achados
    assert len(achados[trivial]) == len(MODALIDADES)

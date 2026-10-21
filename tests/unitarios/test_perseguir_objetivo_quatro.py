"""O perseguidor do objetivo do Quatro (`motores/quatro/perseguir_objetivo_quatro.py`).

T124c da spec 010, defeito 1. ⚠️ Ele ainda NAO esta ligado em
`gerador.SOLUCIONADOR_POR_TIPO`: estes casos travam os quatro passos e a mistura
do nivel, e a decisao de ligar sai da medicao pareada
(`scripts/medir_perseguir_vs_vencer_quatro.py`).

As posicoes partem da mesma base dos vetores de verificacao (`s3 s3 s4 s4`):

    linha 2   . . O O . . .
    linha 1   . . X X . . .
              1 2 3 4 5 6 7
"""

from __future__ import annotations

import random

import pytest

from job import posicoes_de_autoplay_quatro as acervo_mod
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR
from motores.nucleo.papeis import NivelDeMotor
from motores.quatro import perseguir_objetivo_quatro as perseguir
from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro

MOTOR = MotorQuatro("tradicional")
BASE = ["s3", "s3", "s4", "s4"]

#: "Vencer, so" (a chegada da virada) e "vencer pela diagonal".
SO_VENCER = RECEITAS["quatro_virada"].montar({})
DIAGONAL = RECEITAS_FORA_DO_AR["quatro_vencer_diagonal"].montar({})


def _desafio(co_tipo: str, chegada: dict) -> perseguir.Desafio:
    return perseguir.desafio_de(MOTOR, co_tipo, BASE, chegada)


def _nunca() -> str:
    raise AssertionError("o lance do nivel nao devia ter sido pedido")


# ─────────────────────────────────────────────────────────────────────────────
# Passos 1 e 2: cumprir agora, e nao acabar do jeito errado
# ─────────────────────────────────────────────────────────────────────────────


def test_o_lance_que_cumpre_agora_e_jogado() -> None:
    # Depois de s5 (X) e s2 (O), o X tem 3, 4 e 5 embaixo: s6 vence.
    desafio = _desafio("quatro_virada", SO_VENCER)
    agora, lances = perseguir.candidatos(MOTOR, desafio, ["s5", "s2"])
    assert agora == "s6"
    assert lances == ["s6"]


def test_a_vitoria_do_JEITO_ERRADO_sai_da_lista() -> None:
    """⛔ Num desafio de diagonal, vencer pela horizontal e perder o desafio."""
    desafio = _desafio("quatro_vencer_diagonal", DIAGONAL)
    agora, lances = perseguir.candidatos(MOTOR, desafio, ["s5", "s2"])
    assert agora is None
    assert "s6" not in lances
    assert lances, "sobrou lance para jogar"


def test_no_sem_o_meio_a_coluna_central_nao_e_lance() -> None:
    chegada = RECEITAS_FORA_DO_AR["quatro_sem_o_meio"].montar({})
    desafio = _desafio("quatro_sem_o_meio", chegada)
    _, lances = perseguir.candidatos(MOTOR, desafio, [])
    assert "s4" not in lances


# ─────────────────────────────────────────────────────────────────────────────
# Passo 3: nunca deixar a vitoria pronta para o adversario (posicoes reais)
# ─────────────────────────────────────────────────────────────────────────────


def _posicoes_do_acervo(quantas: int) -> list[tuple[str, ...]]:
    sorteio = random.Random(7)
    return [
        tuple(
            acervo_mod.sortear(
                sorteio, co_modalidade="tradicional", minimo=10, maximo=20
            ).lances
        )
        for _ in range(quantas)
    ]


@pytest.mark.parametrize("iniciais", _posicoes_do_acervo(25))
def test_quando_ha_lance_seguro_nenhum_candidato_entrega_a_vitoria(iniciais) -> None:
    desafio = perseguir.desafio_de(MOTOR, "quatro_virada", iniciais, SO_VENCER)
    estado = EstadoQuatro("tradicional", iniciais)
    legais = MOTOR.lances_legais(estado)
    seguros = [
        l
        for l in legais
        if not perseguir._vitoria_imediata(MOTOR, estado.com_lance(l), -desafio.pessoa)
    ]
    agora, lances = perseguir.candidatos(MOTOR, desafio, [])
    if agora is not None or not seguros:
        return
    for lance in lances:
        assert not perseguir._vitoria_imediata(
            MOTOR, estado.com_lance(lance), -desafio.pessoa
        ), f"{lance} deixa o adversario vencer em {''.join(iniciais)}"


def test_ha_posicao_em_que_o_passo_3_tira_lance() -> None:
    """Sem isto, o caso acima passaria por vacuidade."""
    tirou = 0
    for iniciais in _posicoes_do_acervo(25):
        desafio = perseguir.desafio_de(MOTOR, "quatro_virada", iniciais, SO_VENCER)
        agora, lances = perseguir.candidatos(MOTOR, desafio, [])
        legais = MOTOR.lances_legais(EstadoQuatro("tradicional", iniciais))
        tirou += agora is None and len(lances) < len(legais)
    assert tirou > 0


# ─────────────────────────────────────────────────────────────────────────────
# O nivel (a mistura) e a prova
# ─────────────────────────────────────────────────────────────────────────────


def test_o_magno_sempre_persegue_e_nao_pede_o_lance_do_nivel_sem_prova() -> None:
    desafio = _desafio("quatro_vencer_diagonal", DIAGONAL)
    lance = perseguir.lance_de_quem_persegue(
        MOTOR,
        desafio,
        [],
        nivel=NivelDeMotor.SAGAZ,
        sorteio=random.Random(1),
        lance_do_nivel=_nunca,
    )
    assert lance in MOTOR.lances_legais(EstadoQuatro("tradicional", tuple(BASE)))


def test_a_cacau_joga_o_lance_do_nivel_quando_o_sorteio_manda() -> None:
    # Um sorteio cujo 1o numero fica acima de 0,25: a Cacau nao persegue.
    class Sorteio(random.Random):
        def random(self) -> float:
            return 0.99

    desafio = _desafio("quatro_vencer_diagonal", DIAGONAL)
    lance = perseguir.lance_de_quem_persegue(
        MOTOR,
        desafio,
        [],
        nivel=NivelDeMotor.CACAU,
        sorteio=Sorteio(),
        lance_do_nivel=lambda: "s1",
    )
    assert lance == "s1"


def test_os_niveis_perseguem_mais_a_cada_degrau() -> None:
    p = perseguir.PROBABILIDADE_DE_PERSEGUIR
    ordem = [NivelDeMotor.CACAU, NivelDeMotor.PITA, NivelDeMotor.TEX, NivelDeMotor.SAGAZ]
    assert [p[n] for n in ordem] == sorted(p[n] for n in ordem)
    assert p[NivelDeMotor.SAGAZ] == 1.0


def test_com_vitoria_provada_o_lance_e_um_dos_que_vencem() -> None:
    """A v2: entre os lances que a busca prova vencedores, nunca sai outro."""
    desafio = _desafio("quatro_vencer_diagonal", DIAGONAL)
    estado = EstadoQuatro("tradicional", tuple(BASE))
    vencedores = {"s2"}

    def prova(depois: EstadoQuatro) -> int | None:
        # O lance que levou a [depois] e o ultimo da sequencia.
        return desafio.pessoa if depois.lances[-1] in vencedores else None

    lance = perseguir.lance_de_quem_persegue(
        MOTOR,
        desafio,
        [],
        nivel=NivelDeMotor.SAGAZ,
        sorteio=random.Random(1),
        lance_do_nivel=_nunca,
        prova=prova,
    )
    assert lance == "s2"
    assert lance in MOTOR.lances_legais(estado)


def test_sem_vitoria_provada_joga_o_lance_do_nivel_se_ele_nao_perde() -> None:
    desafio = _desafio("quatro_vencer_diagonal", DIAGONAL)
    lance = perseguir.lance_de_quem_persegue(
        MOTOR,
        desafio,
        [],
        nivel=NivelDeMotor.SAGAZ,
        sorteio=random.Random(1),
        lance_do_nivel=lambda: "s5",
        prova=lambda depois: None,
    )
    assert lance == "s5"


def test_o_lance_do_nivel_que_nao_persegue_sai_CRU_com_o_erro_dele() -> None:
    """⛔ v3 (21/10/2026): o ramo que nao persegue nao passa pelos filtros.

    A v2 filtrava tambem este lance, e a regua mostrou a Cacau resolvendo 0,40 a
    0,80 (teto 0,20): os filtros sao competencia. Aqui o lance do nivel e a
    vitoria do JEITO ERRADO num desafio de diagonal - e ele tem de sair igual.
    """

    class Sorteio(random.Random):
        def random(self) -> float:
            return 0.99

    desafio = _desafio("quatro_vencer_diagonal", DIAGONAL)
    lance = perseguir.lance_de_quem_persegue(
        MOTOR,
        desafio,
        ["s5", "s2"],
        nivel=NivelDeMotor.CACAU,
        sorteio=Sorteio(),
        lance_do_nivel=lambda: "s6",
    )
    assert lance == "s6"

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
# ⚠️ A diagonal subiu ao ar na T124c: a receita sai de onde ela estiver.
DIAGONAL = {**RECEITAS, **RECEITAS_FORA_DO_AR}["quatro_vencer_diagonal"].montar({})


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
    # No ar desde 22/10/2026 (T124c): a receita mora em `RECEITAS`.
    chegada = RECEITAS["quatro_sem_o_meio"].montar({})
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


# ─────────────────────────────────────────────────────────────────────────────
# O "Encoste N em ate M" (T143, 22/10/2026): fecha no meio, e nao pede vencer
# ─────────────────────────────────────────────────────────────────────────────

#: O jogador 1 com a vez e duas pecas SOLTAS no chao, nas colunas 1 e 3 (o 2
#: tem duas na coluna 7). So o s2 junta as duas de uma vez: 3 encostadas. Os
#: lances colados (s1, s3, s4) dao 2; s5, s6 e s7 nao encostam em nada.
BASE_ENCOSTE = ["s1", "s7", "s3", "s7"]

#: Alvo 6 em 5 lances (E = 0, M = 5, k = 1): o 1o lance nunca cumpre sozinho.
# No ar desde 22/10/2026 (T143): a receita mora em `RECEITAS`.
ENCOSTE = RECEITAS["quatro_encoste"].montar({"lances": 5, "pecas": 6})


def _desafio_encoste() -> perseguir.Desafio:
    return perseguir.desafio_de(MOTOR, "quatro_encoste", BASE_ENCOSTE, ENCOSTE)


def test_no_encoste_juntar_a_peca_solta_vale_MAIS_que_jogar_colado() -> None:
    desafio = _desafio_encoste()

    def nota(lance: str) -> float:
        estado = EstadoQuatro("tradicional", tuple(BASE_ENCOSTE) + (lance,))
        return perseguir.nota_do_objetivo(MOTOR, MOTOR.tabuleiro(estado), desafio)

    # Os numeros por extenso: 3 encostadas, 2 e 0 (100 por peca, e o `comum`
    # desempata dentro de cada degrau).
    assert nota("s2") > max(nota("s1"), nota("s3"), nota("s4"))
    assert min(nota("s1"), nota("s3"), nota("s4")) > max(nota("s5"), nota("s6"))


def test_no_encoste_o_magno_persegue_SEM_esperar_vitoria_provada() -> None:
    """⛔ No "Vença com N encostadas", sem vitoria provada o perseguidor joga o
    lance do nivel (o caso logo acima, com a diagonal). No "Encoste" vencer nao
    e o objetivo: ele escolhe pela nota, e nem pede o lance do nivel."""
    lance = perseguir.lance_de_quem_persegue(
        MOTOR,
        _desafio_encoste(),
        [],
        nivel=NivelDeMotor.SAGAZ,
        sorteio=random.Random(1),
        lance_do_nivel=_nunca,
        prova=lambda depois: None,
    )
    assert lance == "s2"


def test_no_encoste_o_lance_PROVADO_perdido_sai_mesmo_sendo_o_melhor() -> None:
    desafio = _desafio_encoste()

    def prova(depois: EstadoQuatro) -> int | None:
        # O s2 (o melhor pela nota) entrega a partida; os outros, nada provado.
        return -desafio.pessoa if depois.lances[-1] == "s2" else None

    lance = perseguir.lance_de_quem_persegue(
        MOTOR,
        desafio,
        [],
        nivel=NivelDeMotor.SAGAZ,
        sorteio=random.Random(1),
        lance_do_nivel=_nunca,
        prova=prova,
    )
    # O que sobra de melhor e jogar colado (2 encostadas), e nao o s2.
    assert lance in {"s1", "s3", "s4"}


# ─────────────────────────────────────────────────────────────────────────────
# O "Forme a figura" (T148, 23/10/2026): fecha no meio, e a nota e a distancia
# ─────────────────────────────────────────────────────────────────────────────

#: O quadrado, prazo 5. A receita mora em `RECEITAS` desde a T150 (27/10/2026).
QUADRADO = RECEITAS["quatro_figura"].montar({"figura": "quadrado", "lances": 5})

#: O jogador 1 com a vez, tres pecas do quadrado no canto esquerdo:
#:
#:     linha 2   X . . . . O .
#:     linha 1   X X . . . O O
#:               1 2 3 4 5 6 7
#:
#: So o s2 fecha o quadrado (a casa (2, 2)), e nenhum lance vence a partida.
BASE_QUASE_QUADRADO = ["s1", "s7", "s2", "s6", "s1", "s6"]


def _desafio_figura(base: list[str]) -> perseguir.Desafio:
    return perseguir.desafio_de(MOTOR, "quatro_figura", base, QUADRADO)


def _nota_da_figura(desafio: perseguir.Desafio, lances: tuple[str, ...]) -> float:
    estado = EstadoQuatro("tradicional", lances)
    return perseguir._potencial_da_figura(MOTOR, MOTOR.tabuleiro(estado), desafio)


def test_na_figura_o_lance_que_FORMA_e_jogado_com_a_grade_ao_juiz() -> None:
    """⛔ Sem a grade, o `avaliar` recusa a chegada com `figura`: o passo 1
    quebraria em vez de achar o lance. Com ela, o s2 fecha o quadrado."""
    agora, lances = perseguir.candidatos(MOTOR, _desafio_figura(BASE_QUASE_QUADRADO), [])
    assert agora == "s2"
    assert lances == ["s2"]


def test_na_figura_o_magno_persegue_sem_pedir_o_lance_do_nivel() -> None:
    """O "Forme a figura" fecha no meio (`FECHAM_NO_MEIO`): sem vitoria provada a
    vista, ele escolhe pela nota, e nem pede o lance do nivel."""
    assert "quatro_figura" in perseguir.FECHAM_NO_MEIO
    # Duas pecas no chao (colunas 1 e 2): o quadrado fica a 2 casas, e so s1 e
    # s2 o deixam a 1.
    base = ["s1", "s7", "s2", "s7"]
    lance = perseguir.lance_de_quem_persegue(
        MOTOR,
        _desafio_figura(base),
        [],
        nivel=NivelDeMotor.SAGAZ,
        sorteio=random.Random(1),
        lance_do_nivel=_nunca,
        prova=lambda depois: None,
    )
    assert lance in {"s1", "s2"}


def test_na_figura_a_PROVA_nao_e_consultada() -> None:
    """⚠️ Na figura a prova tirava quase todo lance que constroi (o controle de
    23/10/2026: 20-23 de 30 com ela, 23-25 sem). Quem chama ainda a passa; o
    perseguidor a ignora neste tipo."""
    assert "quatro_figura" in perseguir.TIPOS_SEM_A_PROVA

    def prova(depois: EstadoQuatro) -> int | None:
        raise AssertionError("a prova nao devia ter sido consultada na figura")

    base = ["s1", "s7", "s2", "s7"]
    lance = perseguir.lance_de_quem_persegue(
        MOTOR,
        _desafio_figura(base),
        [],
        nivel=NivelDeMotor.SAGAZ,
        sorteio=random.Random(1),
        lance_do_nivel=_nunca,
        prova=prova,
    )
    assert lance in {"s1", "s2"}


def test_a_nota_da_figura_SOMA_os_lugares_e_nao_so_o_mais_perto() -> None:
    """Duas pecas soltas valem mais que uma: o quadrado fica a 3 casas nos dois
    tabuleiros, mas no segundo ha mais lugares a 3 (o da coluna 4 tambem)."""
    desafio = _desafio_figura(["s1", "s7"])
    uma = _nota_da_figura(desafio, ("s1", "s7"))
    duas = _nota_da_figura(desafio, ("s1", "s7", "s4", "s7"))
    assert duas > uma


def test_a_nota_da_figura_conta_o_BLOQUEIO_da_vitoria_pronta() -> None:
    """⚠️ O adversario bloqueia toda vitoria pronta da pessoa. Com tres X no chao
    (colunas 1 a 3) e a casa (4, 1) livre, o bloqueio cai ali; se o quadrado
    precisasse dela, a nota ja o mede tapado.

        linha 2   . . . . . . O
        linha 1   X X X . . . O     (o 2 tem a vez, e vai bloquear em s4)
    """
    desafio = _desafio_figura(["s1", "s7", "s2", "s7"])
    lances = ("s1", "s7", "s2", "s7", "s3")
    tabuleiro = MOTOR.tabuleiro(EstadoQuatro("tradicional", lances))
    depois_do_bloqueio = MOTOR.tabuleiro(EstadoQuatro("tradicional", lances + ("s4",)))
    assert perseguir._potencial_da_figura(MOTOR, tabuleiro, desafio) == (
        perseguir._soma_dos_lugares(MOTOR, depois_do_bloqueio, desafio)
    )
    # E o bloqueio MUDA a nota (senao o caso nao mede nada): a peca do 2 em
    # (4, 1) tira os lugares do quadrado que passam por ela.
    assert perseguir._soma_dos_lugares(MOTOR, tabuleiro, desafio) != (
        perseguir._soma_dos_lugares(MOTOR, depois_do_bloqueio, desafio)
    )


def test_sem_vitoria_pronta_a_nota_da_figura_e_a_do_tabuleiro_de_agora() -> None:
    desafio = _desafio_figura(["s1", "s7"])
    tabuleiro = MOTOR.tabuleiro(EstadoQuatro("tradicional", ("s1", "s7", "s2", "s7")))
    assert perseguir._potencial_da_figura(MOTOR, tabuleiro, desafio) == (
        perseguir._soma_dos_lugares(MOTOR, tabuleiro, desafio)
    )


def test_com_DUAS_vitorias_prontas_o_bloqueio_nao_entra_na_nota() -> None:
    """Tres X no chao nas colunas 2 a 4: a pessoa vence em s1 e em s5, e o
    adversario so tapa uma. A nota e a do tabuleiro de agora."""
    desafio = _desafio_figura(["s2", "s7"])
    tabuleiro = MOTOR.tabuleiro(EstadoQuatro("tradicional", ("s2", "s7", "s3", "s7", "s4")))
    assert perseguir._potencial_da_figura(MOTOR, tabuleiro, desafio) == (
        perseguir._soma_dos_lugares(MOTOR, tabuleiro, desafio)
    )

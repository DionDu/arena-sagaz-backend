"""T032/T033 - o gabarito e a semente.

Duas pecas pequenas com uma coisa em comum: as duas guardam **duplicacoes
deliberadas**, e duplicacao sem guarda envelhece torta.

  · `nu_lances_solucao` e coluna E tamanho do JSON;
  · `nu_semente` tem faixa no `CHECK` do banco E em `validar()`.
"""

from __future__ import annotations

import pytest

from job.gabarito import (
    ORIGEM_BUSCA_SAGAZ,
    SemSolucao,
    conferir,
    montar,
    nu_lances_solucao,
)
from job.semente import (
    SEMENTE_MAXIMA,
    SEMENTE_MINIMA,
    SementeInvalida,
    semente_do_lance,
    sortear,
    validar,
)

FITA = [
    {"n": 1, "jogador": 1, "lance": "H_2_1"},
    {"n": 2, "jogador": 1, "lance": "H_4_1"},
    {"n": 3, "jogador": 1, "lance": "H_6_1"},
    {"n": 4, "jogador": 1, "lance": "H_8_1"},
]


# ═══════════════════════════════════════════════════════════════════════════
# O gabarito
# ═══════════════════════════════════════════════════════════════════════════


def test_o_gabarito_sai_no_vocabulario_do_log() -> None:
    """E o que permite ao gabarito animado usar o MESMO tocador de replay.

    Um formato proprio aqui obrigaria a escrever um segundo tocador — e dois
    caminhos para a mesma coisa e como as tres telas de fim de partida
    divergiram.
    """
    solucao = montar(FITA, lance_chave=4)
    assert solucao["versao"] == 1
    assert solucao["co_origem"] == ORIGEM_BUSCA_SAGAZ
    assert [l["lance"] for l in solucao["lances"]] == [l["lance"] for l in FITA]
    assert all({"n", "jogador", "lance"} == set(l) for l in solucao["lances"])


def test_o_gabarito_renumera_a_fita() -> None:
    """`n` sai de 1 a N, mesmo que a fita de origem viesse com outra contagem.

    A fita pode chegar de um trecho maior; o gabarito e um documento fechado, e
    um `n` que comecasse em 7 faria o replay procurar seis lances que nao existem.
    """
    deslocada = [dict(l, n=l["n"] + 6) for l in FITA]
    solucao = montar(deslocada, lance_chave=1)
    assert [l["n"] for l in solucao["lances"]] == [1, 2, 3, 4]


def test_gabarito_vazio_e_SemSolucao() -> None:
    """⚠️ Nao e erro, e resposta: o candidato simplesmente nao vai ao ar."""
    with pytest.raises(SemSolucao):
        montar([], lance_chave=1)


def test_lance_chave_fora_da_fita_e_recusado() -> None:
    """O Raio-X destacaria um lance que nao existe."""
    with pytest.raises(ValueError):
        montar(FITA, lance_chave=9)


def test_a_coluna_bate_com_o_json() -> None:
    """🔒 A guarda da duplicacao deliberada.

    `nu_lances_solucao` e coluna porque e por ela que o job filtra candidatos
    (*"os que se resolvem em ate 4 lances"*). Alguem que regrave o gabarito e
    esqueca a coluna faz a curadoria filtrar por um numero que nao descreve mais
    nada — e nada acusaria.
    """
    solucao = montar(FITA, lance_chave=4)
    assert nu_lances_solucao(solucao) == 4
    conferir(solucao, nu_lances_gravado=4)

    with pytest.raises(ValueError, match="nu_lances_solucao"):
        conferir(solucao, nu_lances_gravado=3)


def test_gabarito_de_versao_desconhecida_e_recusado() -> None:
    solucao = dict(montar(FITA, lance_chave=1))
    solucao["versao"] = 99
    with pytest.raises(ValueError, match="versao"):
        conferir(solucao, nu_lances_gravado=4)


# ═══════════════════════════════════════════════════════════════════════════
# A semente
# ═══════════════════════════════════════════════════════════════════════════


def test_a_semente_derivada_e_REPRODUZIVEL() -> None:
    """⚠️ Derivada, e nao sorteada — e e isso que torna a calibracao auditavel.

    Rodar a regua de novo meses depois da os mesmos numeros, e um desafio
    contestado pode ser reauditado. Um `random.randint()` tornaria isso
    impossivel.
    """
    identificador = "9f1c2e40-7b3a-4d18-9a52-0c6e5b1d8a77"
    assert sortear(id_desafio=identificador) == sortear(id_desafio=identificador)


def test_desafios_diferentes_recebem_sementes_diferentes() -> None:
    """Se nao, todos os desafios do dia teriam o mesmo adversario."""
    sementes = {sortear(id_desafio=f"desafio-{i}") for i in range(200)}
    assert len(sementes) == 200


def test_a_semente_cabe_na_faixa_do_CHECK() -> None:
    """A faixa de 32 bits **sem o zero** — a mesma do `ck006_semente`."""
    for i in range(500):
        semente = sortear(id_desafio=f"x{i}")
        assert SEMENTE_MINIMA <= semente <= SEMENTE_MAXIMA


@pytest.mark.parametrize("fora", [0, -1, SEMENTE_MAXIMA + 1, 1.5, True, "7"])
def test_semente_fora_da_faixa_falha_ALTO(fora) -> None:
    """⚠️ O erro aponta para quem gerou o numero, e nao para um INSERT tres
    camadas abaixo que falhou sem contexto."""
    with pytest.raises(SementeInvalida):
        validar(fora)


def test_a_semente_do_lance_e_deterministica() -> None:
    assert semente_do_lance(2087461933, 3) == semente_do_lance(2087461933, 3)


def test_lances_VIZINHOS_nao_recebem_sementes_vizinhas() -> None:
    """🔒 A razao de a conta ser um hash, e nao `semente + lance`.

    Geradores lineares — o `Random` do Dart e um deles — produzem primeiros
    valores parecidos a partir de sementes parecidas. Somar faria o adversario
    ficar repetitivo de um jeito que se percebe jogando, e nenhum teste de
    igualdade acusaria.
    """
    base = 2087461933
    sementes = [semente_do_lance(base, n) for n in range(1, 11)]
    # Nenhuma repetida...
    assert len(set(sementes)) == 10
    # ...e nenhum par consecutivo perto um do outro. O limiar e generoso de
    # propósito: o que se quer excluir e a vizinhanca literal da soma.
    for anterior, seguinte in zip(sementes, sementes[1:]):
        assert abs(anterior - seguinte) > 1000, (
            f"{anterior} e {seguinte} sao vizinhos demais"
        )


def test_a_semente_do_lance_comeca_no_lance_1() -> None:
    """Lance zero nao existe: a numeracao do log comeca em 1."""
    with pytest.raises(SementeInvalida):
        semente_do_lance(2087461933, 0)


def test_a_semente_do_lance_tambem_cabe_na_faixa() -> None:
    """Ela vai para o motor, que a passa ao gerador — fora da faixa, quebra la."""
    for n in range(1, 200):
        assert SEMENTE_MINIMA <= semente_do_lance(7, n) <= SEMENTE_MAXIMA

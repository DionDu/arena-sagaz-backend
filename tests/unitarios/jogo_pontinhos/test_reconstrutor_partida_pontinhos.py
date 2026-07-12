"""Prova que o tabuleiro reconstruído é IDÊNTICO ao que era gravado no banco.

Este arquivo é a justificativa técnica da migração 0006. Ela remove
`ar_tabuleiro_antes`/`ar_tabuleiro_apos` de `jogo_pontinhos.tb002_jogada` apostando
que as matrizes são deriváveis da sequência de arestas. Se essa aposta estiver
errada, o dataset de treino da CNN é corrompido em silêncio — e não há volta,
porque o dado original terá sido descartado.

Então o teste central (`test_reconstrucao_e_identica_ao_jogo_real`) joga partidas
completas, guarda as matrizes EXATAMENTE como o app as gravaria, joga fora tudo
menos as arestas, reconstrói e compara **byte a byte**.
"""
from __future__ import annotations

import random

import numpy as np
import pytest

from gerador_dados.jogo_pontinhos.reconstrutor_partida_pontinhos import (
    PartidaInconsistenteError,
    reconstruir_partida,
)
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro


def _jogar_partida_completa(
    co_variante: str, semente: int
) -> tuple[list[tuple[int, str, int]], list[np.ndarray], list[np.ndarray], list[int]]:
    """Joga uma partida inteira (lances aleatórios) e devolve o que o APP gravaria.

    Devolve `(jogadas, matrizes_antes, matrizes_apos, caixas)` — ou seja, a mesma
    informação que ia para o banco ANTES da migração 0006. As matrizes aqui são a
    VERDADE contra a qual a reconstrução será comparada.
    """
    rng = random.Random(semente)
    estado = EstadoTabuleiro.de_tamanho(co_variante)

    jogadas: list[tuple[int, str, int]] = []
    antes: list[np.ndarray] = []
    apos: list[np.ndarray] = []
    caixas: list[int] = []

    jogador = 1  # J1 começa; ±1 são os valores contratuais da matriz da CNN.
    nu_ordem = 1
    while not estado.esta_terminal():
        aresta = rng.choice(estado.tracos_disponiveis())

        antes.append(estado.matriz.copy())
        fechadas = estado.aplicar_traco(aresta, jogador)
        apos.append(estado.matriz.copy())

        jogadas.append((nu_ordem, aresta, jogador))
        caixas.append(fechadas)
        nu_ordem += 1

        # Regra do jogo: quem fecha caixa joga de novo.
        if fechadas == 0:
            jogador = -jogador

    return jogadas, antes, apos, caixas


@pytest.mark.parametrize("co_variante", ["pequeno", "medio", "grande"])
@pytest.mark.parametrize("semente", [1, 7, 42, 2026])
def test_reconstrucao_e_identica_ao_jogo_real(co_variante: str, semente: int) -> None:
    """O CHEQUE QUE AUTORIZA A MIGRAÇÃO: reconstruído == gravado, byte a byte."""
    jogadas, antes, apos, caixas = _jogar_partida_completa(co_variante, semente)

    # Agora simulamos o banco DEPOIS da 0006: só as arestas sobreviveram.
    reconstruidas = reconstruir_partida(co_variante, jogadas)

    assert len(reconstruidas) == len(jogadas)
    for i, r in enumerate(reconstruidas):
        assert np.array_equal(r.tabuleiro_antes, antes[i]), (
            f"lance {i + 1}: tabuleiro ANTES divergiu"
        )
        assert np.array_equal(r.tabuleiro_apos, apos[i]), (
            f"lance {i + 1}: tabuleiro APÓS divergiu"
        )
        # As caixas fechadas também são derivadas — conferem com o que o app contou.
        assert r.nu_caixas_fechadas == caixas[i]


def test_ordem_embaralhada_no_banco_nao_atrapalha() -> None:
    """O SELECT pode devolver as linhas em qualquer ordem — nós ordenamos."""
    jogadas, _, apos, _ = _jogar_partida_completa("pequeno", semente=3)

    embaralhadas = list(jogadas)
    random.Random(0).shuffle(embaralhadas)

    reconstruidas = reconstruir_partida("pequeno", embaralhadas)

    assert [r.nu_ordem for r in reconstruidas] == list(range(1, len(jogadas) + 1))
    assert np.array_equal(reconstruidas[-1].tabuleiro_apos, apos[-1])


def test_partida_parcial_reconstroi(  # partida abandonada é caso legítimo
) -> None:
    """Partida ABANDONADA (co_status='abandonada') tem só os primeiros lances —
    e isso é perfeitamente reconstruível, desde que as ordens sejam contíguas."""
    jogadas, _, apos, _ = _jogar_partida_completa("pequeno", semente=5)
    parcial = jogadas[:6]

    reconstruidas = reconstruir_partida("pequeno", parcial)

    assert len(reconstruidas) == 6
    assert not np.array_equal(reconstruidas[-1].tabuleiro_apos, apos[-1])


# ── A validação de integridade: o dado ruim TEM que aparecer ─────────────────


def test_jogada_faltando_e_recusada() -> None:
    """O cenário mais perigoso: um lance não chegou à nuvem.

    Sem as matrizes gravadas, nada denunciaria isso — a reconstrução produziria um
    tabuleiro plausível PORÉM ERRADO, que entraria calado no treino da CNN. A
    contiguidade das ordens é a única testemunha de que a partida está inteira.
    """
    jogadas, _, _, _ = _jogar_partida_completa("pequeno", semente=9)
    sem_o_terceiro = [j for j in jogadas if j[0] != 3]

    with pytest.raises(PartidaInconsistenteError, match="faltam as ordens"):
        reconstruir_partida("pequeno", sem_o_terceiro)


def test_aresta_repetida_e_recusada() -> None:
    """Duas jogadas no mesmo traço: partida impossível."""
    jogadas, _, _, _ = _jogar_partida_completa("pequeno", semente=11)
    # Faz o lance 2 repetir o traço do lance 1 (ordens seguem contíguas).
    adulteradas = list(jogadas[:4])
    adulteradas[1] = (2, adulteradas[0][1], -1)

    with pytest.raises(PartidaInconsistenteError, match="já está ocupado"):
        reconstruir_partida("pequeno", adulteradas)


def test_aresta_inexistente_no_tabuleiro_e_recusada() -> None:
    """Aresta de um tabuleiro GRANDE numa partida PEQUENA.

    É por isto que `co_aresta` continua sendo TEXTO e não um índice numérico: o
    índice seria ambíguo entre variantes, e um erro destes passaria despercebido.
    """
    with pytest.raises(PartidaInconsistenteError, match="não existe no tabuleiro"):
        reconstruir_partida("pequeno", [(1, "H_12_9", 1)])


def test_jogador_fora_do_contrato_e_recusado() -> None:
    """±1 é contratual (é o que vai para a matriz da CNN). Um 2 corromperia o tensor."""
    with pytest.raises(PartidaInconsistenteError, match="esperado \\+1 ou -1"):
        reconstruir_partida("pequeno", [(1, "H_0_1", 2)])


def test_variante_desconhecida_e_recusada() -> None:
    with pytest.raises(PartidaInconsistenteError, match="Variante"):
        reconstruir_partida("gigante", [(1, "H_0_1", 1)])


def test_partida_sem_jogadas_e_recusada() -> None:
    with pytest.raises(PartidaInconsistenteError, match="sem nenhuma jogada"):
        reconstruir_partida("pequeno", [])

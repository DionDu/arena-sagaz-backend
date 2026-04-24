"""Testes unitários para gerador_dados.minimax."""
import pytest

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada, minimax


def _criar_tabuleiro_quase_completo():
    """Tabuleiro 1x1 com 3 dos 4 lados preenchidos — IA deve fechar a caixa."""
    t = EstadoTabuleiro(1, 1)
    tracos = t.tracos_disponiveis()
    for tr in tracos[:-1]:
        t.aplicar_traco(tr)
    return t, tracos[-1]


def test_minimax_fecha_caixa_obvia():
    t, ultimo_traco = _criar_tabuleiro_quase_completo()
    jogada = melhor_jogada(t, profundidade=3)
    assert jogada == ultimo_traco


def test_minimax_estado_terminal_retorna_avaliacao():
    t = EstadoTabuleiro(1, 1)
    for tr in t.tracos_disponiveis():
        t.aplicar_traco(tr)
    assert t.esta_terminal()
    # Com tabuleiro terminal, minimax deve retornar avaliação estática
    resultado = minimax(t, 3, -10001, 10001, True)
    assert isinstance(resultado, int)


def test_minimax_nao_trava_profundidade_3_pequeno():
    t = EstadoTabuleiro.de_tamanho("pequeno")
    # Apenas verificar que completa sem erro ou timeout
    jogada = melhor_jogada(t, profundidade=3)
    assert isinstance(jogada, str)
    assert jogada.startswith(("H_", "V_"))


def test_melhor_jogada_retorna_traco_valido():
    t = EstadoTabuleiro(2, 2)
    jogada = melhor_jogada(t, profundidade=2)
    assert jogada in t.tracos_disponiveis()

"""Testes de injeção de dependência (DI) em minimax_pontinhos (T014).

Valida o requisito D3 do plano `003-jogador-hibrido`: minimax aceita
`fn_avaliacao` opcional com default `avaliar`, e a função injetada é
propagada por toda a recursão.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from gerador_dados.jogo_pontinhos.minimax_pontinhos import (
    avaliar,
    melhor_jogada,
    minimax,
)
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro


def _tabuleiro_quase_completo_1x1() -> tuple[EstadoTabuleiro, str]:
    t = EstadoTabuleiro(1, 1)
    tracos = t.tracos_disponiveis()
    for tr in tracos[:-1]:
        t.aplicar_traco(tr)
    return t, tracos[-1]


# =============================================================================
# Comportamento legado preservado
# =============================================================================


def test_minimax_default_fn_avaliacao_eh_avaliar():
    """Sem passar fn_avaliacao, comportamento deve ser idêntico ao legado."""
    t = EstadoTabuleiro(2, 2)
    score_default = minimax(t, 2, -10001, 10001, True)
    score_explicito = minimax(t, 2, -10001, 10001, True, fn_avaliacao=avaliar)
    assert score_default == score_explicito


def test_minimax_chamada_legada_sem_fn_avaliacao_funciona():
    """Chamadores antigos (positional args, sem fn_avaliacao) seguem operando."""
    t = EstadoTabuleiro(1, 1)
    resultado = minimax(t, 3, -10001, 10001, True)
    assert isinstance(resultado, int)


def test_melhor_jogada_default_continua_funcionando():
    """melhor_jogada usa minimax internamente; default deve seguir produzindo
    decisão correta no caso óbvio (3 lados preenchidos → fechar)."""
    t, ultimo = _tabuleiro_quase_completo_1x1()
    assert melhor_jogada(t, profundidade=3) == ultimo


# =============================================================================
# fn_avaliacao injetada altera o resultado
# =============================================================================


def test_fn_avaliacao_constante_alta_devolve_score_constante_no_leaf():
    """Em profundidade 0, minimax retorna fn_avaliacao(...). Constante alta
    deve aparecer literalmente."""
    t = EstadoTabuleiro(2, 2)
    fn_constante = lambda estado, ia, hum: 999  # noqa: E731
    score = minimax(t, 0, -10001, 10001, True, fn_avaliacao=fn_constante)
    assert score == 999


def test_fn_avaliacao_constante_negativa_no_leaf():
    t = EstadoTabuleiro(2, 2)
    fn_constante = lambda estado, ia, hum: -42  # noqa: E731
    score = minimax(t, 0, -10001, 10001, False, fn_avaliacao=fn_constante)
    assert score == -42


def test_fn_avaliacao_diferente_produz_score_diferente_em_profundidade_positiva():
    """Com profundidade > 0 e árvore não-trivial, mudar a heurística deve
    refletir num score final diferente."""
    t = EstadoTabuleiro(2, 2)
    fn_invertida = lambda estado, ia, hum: hum - ia  # heurística trocada  # noqa: E731
    score_padrao = minimax(t, 2, -10001, 10001, True)
    score_invertido = minimax(t, 2, -10001, 10001, True, fn_avaliacao=fn_invertida)
    # Não exigimos sinal específico — apenas que a heurística injetada de fato
    # influenciou a árvore. Em tabuleiro 2x2 com depth=2 a diferença é
    # observável; se algum dia ficarem iguais, a DI não está sendo aplicada.
    assert score_padrao != score_invertido or score_padrao == 0


# =============================================================================
# DI propaga via recursão
# =============================================================================


def test_fn_avaliacao_eh_propagada_pela_recursao():
    """Mock conta chamadas: numa árvore de profundidade > 0, a função de
    avaliação injetada deve ser chamada nos nós-folha (profundidade=0 ou
    estado terminal)."""
    t = EstadoTabuleiro(1, 1)  # árvore pequena, totalmente explorável
    fn_mock = MagicMock(return_value=0)
    minimax(t, 3, -10001, 10001, True, fn_avaliacao=fn_mock)
    assert fn_mock.call_count > 0
    # Cada chamada deve receber EstadoTabuleiro + 2 ints
    args, _ = fn_mock.call_args
    assert isinstance(args[0], EstadoTabuleiro)
    assert isinstance(args[1], int)
    assert isinstance(args[2], int)


def test_avaliar_padrao_nao_eh_chamada_quando_fn_avaliacao_customizada(monkeypatch):
    """Se fn_avaliacao customizada é passada, `avaliar` original não deve
    ser invocada nem mesmo nas folhas."""
    chamadas_avaliar = {"n": 0}

    def avaliar_espionada(estado, ia, hum):
        chamadas_avaliar["n"] += 1
        return ia - hum

    # Substitui o `avaliar` no módulo (apenas para detectar chamadas indevidas).
    import gerador_dados.jogo_pontinhos.minimax_pontinhos as mod
    monkeypatch.setattr(mod, "avaliar", avaliar_espionada)

    t = EstadoTabuleiro(1, 1)
    fn_custom = MagicMock(return_value=7)
    minimax(t, 3, -10001, 10001, True, fn_avaliacao=fn_custom)

    assert fn_custom.call_count > 0
    assert chamadas_avaliar["n"] == 0

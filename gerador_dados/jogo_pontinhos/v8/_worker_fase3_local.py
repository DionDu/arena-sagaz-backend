"""
Worker de Minimax Bitboard — Fase 3, execução local (multiprocessing Windows/spawn).

Definido em módulo separado para ser picklável pelo multiprocessing no Windows.
Ambos os bug fixes do Bitboard de Maio/2026 estão aplicados e NÃO devem ser
revertidos:

  Bug 1 — Caixas Pré-Fechadas (Falsos Positivos):
    Ao contar caixas completadas por uma jogada, verificar que a caixa
    NÃO estava fechada antes:
        CORRETO:  closed = sum(1 for bm in EDGE_BOXES[i]
                                if new_e & bm == bm and edges & bm != bm)
        ERRADO:   closed = sum(1 for bm in EDGE_BOXES[i] if new_e & bm == bm)

  Bug 2 — Offsets na Poda Alpha-Beta Incremental:
    O Bitboard retorna scores *incrementais* (não absolutos). Ao chamar a
    subárvore após capturar 'closed' caixas, os limites alpha/beta DEVEM
    ser ajustados com offset de -closed (maximizando) ou +closed (minimizando):
        CORRETO (max, mesma vez):
            val = closed + solve_minimax_bitboard(
                new_e, depth-1, alpha - closed, beta - closed, True, tt)
        ERRADO (repassa alpha/beta puro — poda prematura, escolhe jogadas perdedoras):
            val = closed + solve_minimax_bitboard(
                new_e, depth-1, alpha, beta, True, tt)
"""
import random

import numpy as np


# ---------------------------------------------------------------------------
# Tabelas do Bitboard (construídas uma vez por processo worker)
# ---------------------------------------------------------------------------

def _build_tables():
    h, w = 9, 7
    edge_to_bit = {}
    bit_to_label = {}
    bit_idx = 0
    for r in range(h):
        for c in range(w):
            if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
                edge_to_bit[(r, c)] = bit_idx
                bit_to_label[bit_idx] = f'H_{r}_{c}' if r % 2 == 0 else f'V_{r}_{c}'
                bit_idx += 1

    n_edges = bit_idx  # 31
    all_mask = (1 << n_edges) - 1

    box_masks = []
    for r in range(1, h, 2):
        for c in range(1, w, 2):
            mask = (
                (1 << edge_to_bit[(r - 1, c)])
                | (1 << edge_to_bit[(r + 1, c)])
                | (1 << edge_to_bit[(r, c - 1)])
                | (1 << edge_to_bit[(r, c + 1)])
            )
            box_masks.append(mask)

    edge_boxes = [
        tuple(bm for bm in box_masks if bm & (1 << b))
        for b in range(n_edges)
    ]

    return n_edges, all_mask, edge_boxes, bit_to_label


N_EDGES, ALL_MASK, EDGE_BOXES, BIT_TO_LABEL = _build_tables()


# ---------------------------------------------------------------------------
# Minimax + Alpha-Beta + Transposition Table
# ---------------------------------------------------------------------------

def solve_minimax_bitboard(edges, depth, alpha, beta, maximizing, tt):
    """
    Minimax com Alpha-Beta e Tabela de Transposição. Scores INCREMENTAIS.

    Bug Fix 1: 'edges & bm != bm' exclui caixas pré-fechadas ao contar.
    Bug Fix 2: offset alpha/beta por 'closed' na recursão incremental.
    """
    if depth == 0 or edges == ALL_MASK:
        return 0

    tt_key = (edges, depth, maximizing)
    if tt_key in tt:
        flag, val = tt[tt_key]
        if flag == 0:                   # EXACT
            return val
        if flag == 1 and val >= beta:   # LOWERBOUND
            return val
        if flag == 2 and val <= alpha:  # UPPERBOUND
            return val

    moves = []
    for i in range(N_EDGES):
        if not (edges & (1 << i)):
            ne = edges | (1 << i)
            # Bug Fix 1: conta APENAS caixas fechadas por ESTA jogada
            closed = sum(
                1 for bm in EDGE_BOXES[i]
                if ne & bm == bm and edges & bm != bm
            )
            moves.append((i, closed))
    moves.sort(key=lambda x: x[1], reverse=True)

    orig_alpha = alpha
    orig_beta = beta
    best_val = -10000 if maximizing else 10000

    for bit, closed in moves:
        new_e = edges | (1 << bit)
        if maximizing:
            if closed > 0:
                # Bug Fix 2: jogador mantém a vez — offset alpha/beta por closed
                val = closed + solve_minimax_bitboard(
                    new_e, depth - 1, alpha - closed, beta - closed, True, tt
                )
            else:
                val = solve_minimax_bitboard(new_e, depth - 1, alpha, beta, False, tt)
            best_val = max(best_val, val)
            alpha = max(alpha, best_val)
        else:
            if closed > 0:
                # Bug Fix 2: adversário captura — offset invertido
                val = -closed + solve_minimax_bitboard(
                    new_e, depth - 1, alpha + closed, beta + closed, False, tt
                )
            else:
                val = solve_minimax_bitboard(new_e, depth - 1, alpha, beta, True, tt)
            best_val = min(best_val, val)
            beta = min(beta, best_val)
        if beta <= alpha:
            break

    # TT flags: 0=EXACT, 1=LOWERBOUND, 2=UPPERBOUND
    if maximizing:
        flag = 2 if best_val <= orig_alpha else (1 if best_val >= beta else 0)
    else:
        flag = 1 if best_val >= orig_beta else (2 if best_val <= alpha else 0)
    tt[tt_key] = (flag, best_val)
    return best_val


# ---------------------------------------------------------------------------
# Função de entrada do worker (picklável para multiprocessing spawn)
# ---------------------------------------------------------------------------

def processar_estado(args):
    """
    Calcula melhor_jogada e scores Minimax para um único estado do jogo.

    Parâmetro:
        args: (estado_bytes: bytes, depth: int)
            - estado_bytes: 63 bytes (matriz 9×7 codificada como int8)
            - depth: profundidade Minimax (DEPTH_PADRAO=11 ou DEPTH_ADAPTATIVO=20)

    Retorna:
        (estado_bytes, depth, melhor_jogada: str, scores: list[float])
            - scores: 31 floats; -1e9 para arestas já ocupadas.

    Definido no módulo (não em __main__) para ser picklável no Windows spawn.
    """
    estado_bytes, depth = args

    # Decodifica matriz 9×7 → bitboard
    mat = np.frombuffer(estado_bytes, dtype=np.int8).reshape(9, 7)
    edges = 0
    idx = 0
    for r in range(9):
        for c in range(7):
            if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
                if mat[r, c] == 9:
                    edges |= (1 << idx)
                idx += 1

    # TT reiniciada por estado (não compartilhar entre tabuleiros)
    tt = {}
    scores = np.full(N_EDGES, -1_000_000_000.0, dtype=np.float32)

    for i in range(N_EDGES):
        if not (edges & (1 << i)):
            new_e = edges | (1 << i)
            # Bug Fix 1: conta apenas caixas fechadas por esta jogada
            closed = sum(
                1 for bm in EDGE_BOXES[i]
                if new_e & bm == bm and edges & bm != bm
            )
            if closed > 0:
                res = closed + solve_minimax_bitboard(
                    new_e, depth - 1, -10001, 10001, True, tt
                )
            else:
                res = solve_minimax_bitboard(
                    new_e, depth - 1, -10001, 10001, False, tt
                )
            scores[i] = float(res)

    validos = [i for i, s in enumerate(scores) if s > -1e8]
    if not validos:
        melhor_rotulo = ''
    else:
        max_s = max(scores[i] for i in validos)
        best_idx = random.choice([i for i in validos if scores[i] == max_s])
        melhor_rotulo = BIT_TO_LABEL[best_idx]

    return (estado_bytes, depth, melhor_rotulo, scores.tolist())

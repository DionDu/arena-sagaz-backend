"""V5 Local engine — Minimax bitboard solver para geração de dataset (sem Spark, sem closure_lut).

Este módulo é importado pelo notebook ``Otimizacao_Topologia_Rede_V5_Local.ipynb``
e por cada worker spawnado pelo ``multiprocessing.Pool``. Ele tem que ser um
arquivo ``.py`` (não pode ser definido em célula do notebook), porque o
spawn no Windows precisa importar o módulo do worker para deserializar a
função alvo.

Diferenças relevantes em relação ao engine embutido nas versões V3/V4/V5:

* Sem ``closure_lut``: a versão V4 alocava ``np.zeros((n, 1<<n))``, ou seja
  ``31 × 2³¹ = 66 GB`` de memória virtual por worker, mesmo só preenchendo
  ~0,05% das entradas. O LUT cobria menos estados do que o fallback
  encontrava na prática, então a otimização era prejuízo líquido.
* ``_closures_fast`` virou um cálculo direto (3-4 testes de máscara). É barato.
* Tabelas (``edge_boxes``, ``box_masks`` etc.) são montadas uma vez por worker
  no ``init_worker`` e ficam em globais do processo.
"""

from __future__ import annotations

import json
import random
from typing import Any

import numpy as np


# Estado por worker preenchido em ``init_worker``.
_TBL: dict[str, Any] = {}


def build_topology_tables(rows: int, cols: int):
    """Constrói tabelas de bitboard a partir do shape do tabuleiro."""
    h = 2 * rows + 1
    w = 2 * cols + 1
    edge_to_bit: dict[tuple[int, int], int] = {}
    bit_to_rc: dict[int, tuple[int, int]] = {}
    bit_to_label: dict[int, str] = {}
    bit_idx = 0
    for r in range(h):
        for c in range(w):
            if r % 2 == 0 and c % 2 == 1:
                edge_to_bit[(r, c)] = bit_idx
                bit_to_rc[bit_idx] = (r, c)
                bit_to_label[bit_idx] = f"H_{r}_{c}"
                bit_idx += 1
            elif r % 2 == 1 and c % 2 == 0:
                edge_to_bit[(r, c)] = bit_idx
                bit_to_rc[bit_idx] = (r, c)
                bit_to_label[bit_idx] = f"V_{r}_{c}"
                bit_idx += 1
    n = bit_idx
    all_mask = (1 << n) - 1
    box_masks = []
    for r in range(1, h, 2):
        for c in range(1, w, 2):
            t = edge_to_bit[(r - 1, c)]
            b = edge_to_bit[(r + 1, c)]
            l = edge_to_bit[(r, c - 1)]
            rr = edge_to_bit[(r, c + 1)]
            box_masks.append((1 << t) | (1 << b) | (1 << l) | (1 << rr))
    edge_boxes = [tuple(bm for bm in box_masks if bm & (1 << i)) for i in range(n)]
    labels = [bit_to_label[i] for i in range(n)]
    return n, all_mask, edge_boxes, labels, bit_to_rc, box_masks


def _closures_fast(edges: int, i: int, edge_boxes) -> int:
    new = edges | (1 << i)
    return sum(1 for bm in edge_boxes[i] if (new & bm) == bm)


def _ordered_moves(edges: int, n_edges: int, edge_boxes, killer_moves):
    killers = []
    good = []
    normal = []
    for i in range(n_edges):
        if edges & (1 << i):
            continue
        cl = _closures_fast(edges, i, edge_boxes)
        if killer_moves and i in killer_moves:
            killers.append((i, cl) if cl > 0 else i)
        elif cl > 0:
            good.append((i, cl))
        else:
            normal.append(i)
    good.sort(key=lambda x: x[1], reverse=True)
    return killers, good, normal


def deep_evaluate(
    edges: int,
    depth: int,
    alpha: int,
    beta: int,
    maximizing: bool,
    n_edges: int,
    all_mask: int,
    edge_boxes,
    tt: dict,
    killer_moves: set | None = None,
):
    if depth == 0 or edges == all_mask:
        return 0
    key = (edges, depth, maximizing)
    cached = tt.get(key)
    if cached:
        f, v, cached_depth = cached
        if cached_depth >= depth:
            if f == 0:
                return v
            if f == 1 and v >= beta:
                return v
            if f == 2 and v <= alpha:
                return v
            if f == 1:
                alpha = max(alpha, v)
            elif f == 2:
                beta = min(beta, v)

    killers, good, normal = _ordered_moves(edges, n_edges, edge_boxes, killer_moves)
    orig_alpha = alpha
    best_move = None

    if maximizing:
        best = -10000
        for move_info in killers:
            move = move_info[0] if isinstance(move_info, tuple) else move_info
            cl = move_info[1] if isinstance(move_info, tuple) else _closures_fast(edges, move, edge_boxes)
            child = deep_evaluate(edges | (1 << move), depth - 1, alpha - cl, beta - cl,
                                   True, n_edges, all_mask, edge_boxes, tt, killer_moves)
            score = cl + child
            if score > best:
                best = score
                best_move = move
            alpha = max(alpha, best)
            if beta <= alpha:
                break
        if beta > alpha:
            for move, cl in good:
                child = deep_evaluate(edges | (1 << move), depth - 1, alpha - cl, beta - cl,
                                       True, n_edges, all_mask, edge_boxes, tt, killer_moves)
                score = cl + child
                if score > best:
                    best = score
                    best_move = move
                alpha = max(alpha, best)
                if beta <= alpha:
                    break
        if beta > alpha:
            for move in normal:
                child = deep_evaluate(edges | (1 << move), depth - 1, alpha, beta,
                                       False, n_edges, all_mask, edge_boxes, tt, killer_moves)
                if child > best:
                    best = child
                    best_move = move
                alpha = max(alpha, best)
                if beta <= alpha:
                    break
    else:
        best = 10000
        for move_info in killers:
            move = move_info[0] if isinstance(move_info, tuple) else move_info
            cl = move_info[1] if isinstance(move_info, tuple) else _closures_fast(edges, move, edge_boxes)
            child = deep_evaluate(edges | (1 << move), depth - 1, alpha + cl, beta + cl,
                                   False, n_edges, all_mask, edge_boxes, tt, killer_moves)
            score = -cl + child
            if score < best:
                best = score
                best_move = move
            beta = min(beta, best)
            if beta <= alpha:
                break
        if beta > alpha:
            for move, cl in good:
                child = deep_evaluate(edges | (1 << move), depth - 1, alpha + cl, beta + cl,
                                       False, n_edges, all_mask, edge_boxes, tt, killer_moves)
                score = -cl + child
                if score < best:
                    best = score
                    best_move = move
                beta = min(beta, best)
                if beta <= alpha:
                    break
        if beta > alpha:
            for move in normal:
                child = deep_evaluate(edges | (1 << move), depth - 1, alpha, beta,
                                       True, n_edges, all_mask, edge_boxes, tt, killer_moves)
                if child < best:
                    best = child
                    best_move = move
                beta = min(beta, best)
                if beta <= alpha:
                    break

    flag = 2 if best <= orig_alpha else (1 if best >= beta else 0)
    tt[key] = (flag, best, depth)
    if killer_moves is not None and best_move is not None and best_move not in killer_moves:
        killer_moves.add(best_move)
        if len(killer_moves) > 4:
            killer_moves.pop()
    return best


def compute_all_scores(edges: int, depth: int, n_edges: int, all_mask: int, edge_boxes):
    tt: dict = {}
    killer_moves: set = set()
    scores: dict[int, int] = {}
    for i in range(n_edges):
        if edges & (1 << i):
            continue
        cl = _closures_fast(edges, i, edge_boxes)
        new = edges | (1 << i)
        child = deep_evaluate(new, depth - 1, -10001, 10001, cl > 0,
                              n_edges, all_mask, edge_boxes, tt, killer_moves)
        scores[i] = cl + child if cl > 0 else child
    return scores


def get_optimal_configuration(edges, depth, n_edges, all_mask, edge_boxes, labels):
    bit_scores = compute_all_scores(edges, depth, n_edges, all_mask, edge_boxes)
    label_scores = {labels[b]: v for b, v in bit_scores.items()}
    best_val = max(bit_scores.values())
    best_label = labels[random.choice([b for b, v in bit_scores.items() if v == best_val])]
    return best_label, label_scores


def edges_to_matrix(edges, rows, cols, n_edges, bit_to_rc, box_masks):
    h, w = 2 * rows + 1, 2 * cols + 1
    mat = np.zeros((h, w), dtype=np.int8)
    for r in range(0, h, 2):
        for c in range(0, w, 2):
            mat[r, c] = 8
    for i in range(n_edges):
        if edges & (1 << i):
            r, c = bit_to_rc[i]
            mat[r, c] = 9
    for bm in box_masks:
        if (edges & bm) == bm:
            bits = [bit_to_rc[b] for b in range(n_edges) if bm & (1 << b)]
            ar = sum(rc[0] for rc in bits) // 4
            ac = sum(rc[1] for rc in bits) // 4
            if ar % 2 == 1 and ac % 2 == 1:
                mat[ar, ac] = 1
    return mat


# ---------------------------------------------------------------------------
# Sampler
# ---------------------------------------------------------------------------

STRAT_MODES = [0, 1, 2, 3]
MODE_NAMES = {0: "uniform", 1: "sim_l1", 2: "sim_l2", 3: "sim_l3"}


def _autoplay_edges_bounded(gen_depth: int, n_edges: int, all_mask: int, edge_boxes,
                             target_lo: int, target_hi: int):
    """Autoplay com target em numero ABSOLUTO de tracos (nao fracao).

    Usado pelo loop por cota (PRD §4.1.3): cada (gen_mode, bucket) sorteia um
    target dentro do bucket, evitando o off-by-one de converter para fracao.
    """
    target = random.randint(target_lo, target_hi)
    edges = 0
    maximizing = True
    while bin(edges).count("1") < target and edges != all_mask:
        tt: dict = {}
        killer_moves: set = set()
        best_score = -99999 if maximizing else 99999
        best_moves: list[int] = []
        for i in range(n_edges):
            if edges & (1 << i):
                continue
            cl = _closures_fast(edges, i, edge_boxes)
            new = edges | (1 << i)
            child = deep_evaluate(
                new, gen_depth - 1, -10001, 10001,
                (not maximizing) if cl == 0 else maximizing,
                n_edges, all_mask, edge_boxes, tt, killer_moves,
            )
            score = cl + child if maximizing else -cl + child
            cond = score > best_score if maximizing else score < best_score
            if cond:
                best_score = score
                best_moves = [i]
            elif score == best_score:
                best_moves.append(i)
        if not best_moves:
            break
        best_move = random.choice(best_moves)
        cl = _closures_fast(edges, best_move, edge_boxes)
        edges |= 1 << best_move
        if cl == 0:
            maximizing = not maximizing
    return edges


def generate_topology_forced(n_edges: int, all_mask: int, edge_boxes,
                              gen_mode: int, target_lo: int, target_hi: int):
    """Gera topologia com gen_mode forcado e #tracos alvo no intervalo [lo, hi].

    Usado pelo loop por cota: a celula (gen_mode, bucket) decide ambos
    parametros antes de chamar.
    """
    if gen_mode == 0:
        qty = random.randint(target_lo, target_hi)
        idx = list(range(n_edges))
        random.shuffle(idx)
        edges = 0
        for i in idx[:qty]:
            edges |= 1 << i
        return edges
    if gen_mode in (1, 2, 3):
        return _autoplay_edges_bounded(gen_mode, n_edges, all_mask, edge_boxes,
                                         target_lo, target_hi)
    raise ValueError(f"gen_mode invalido: {gen_mode}")


# ---------------------------------------------------------------------------
# Worker pool API
# ---------------------------------------------------------------------------

def init_worker(rows: int, cols: int, depth: int, seed_base: int | None = None):
    """Inicializador chamado uma vez por processo do Pool.

    Constroi as tabelas (uma vez por worker) e fixa seed derivada do PID
    para evitar que workers gerem sequencias identicas.
    """
    n, mask, eboxes, labels, brc, bms = build_topology_tables(rows, cols)
    _TBL["rows"] = rows
    _TBL["cols"] = cols
    _TBL["depth"] = depth
    _TBL["n"] = n
    _TBL["mask"] = mask
    _TBL["eboxes"] = eboxes
    _TBL["labels"] = labels
    _TBL["brc"] = brc
    _TBL["bms"] = bms
    if seed_base is not None:
        import os
        random.seed(seed_base + os.getpid())
        np.random.seed((seed_base + os.getpid()) & 0xFFFFFFFF)


def gen_one_sample_quota(args: tuple[int, int, int]):
    """Gera UMA amostra com gen_mode forcado e #tracos no bucket [lo, hi].

    args = (gen_mode, bucket_lo, bucket_hi).

    Tenta ate 20 vezes produzir um estado cujo numero efetivo de tracos cai
    dentro do bucket (a busca minimax pode terminar antes do target em casos
    raros). Retorna ``(mat_bytes, shape, best_link, scores_json, mode, n_tracos)``
    ou ``None`` se as 20 tentativas falharem.
    """
    gen_mode, lo, hi = args
    n = _TBL["n"]
    mask = _TBL["mask"]
    eboxes = _TBL["eboxes"]
    labels = _TBL["labels"]
    brc = _TBL["brc"]
    bms = _TBL["bms"]
    rows = _TBL["rows"]
    cols = _TBL["cols"]
    depth = _TBL["depth"]
    for _attempt in range(20):
        try:
            edges = generate_topology_forced(n, mask, eboxes, gen_mode, lo, hi)
            if edges == mask:
                continue
            n_tracos = bin(edges).count("1")
            if not (lo <= n_tracos <= hi):
                continue
            best, scores = get_optimal_configuration(edges, depth, n, mask, eboxes, labels)
            mat = edges_to_matrix(edges, rows, cols, n, brc, bms)
            return mat.tobytes(), mat.shape, best, json.dumps(scores), int(gen_mode), int(n_tracos)
        except Exception:
            pass
    return None

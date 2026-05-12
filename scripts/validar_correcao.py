"""
Validacao da correcao: TT somente com entradas EXACT.

Testa se o algoritmo bitboard com TT EXACT-only produz os mesmos
resultados que o Original (minimax_pontinhos.py) e que o bitboard sem TT.
"""
import sys
import numpy as np
import time

sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    todos_labels_canonicos,
    TAMANHOS,
)
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

LINHAS, COLUNAS = TAMANHOS["pequeno"]
LABELS = todos_labels_canonicos(LINHAS, COLUNAS)

# Montar bitboard
h, w = 9, 7
edge_to_bit = {}
bit_to_label = {}
bit_idx = 0
for r in range(h):
    for c in range(w):
        if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
            edge_to_bit[(r, c)] = bit_idx
            bit_to_label[bit_idx] = f"H_{r}_{c}" if r % 2 == 0 else f"V_{r}_{c}"
            bit_idx += 1

n_edges = bit_idx
all_mask = (1 << n_edges) - 1

box_masks = []
for r in range(1, h, 2):
    for c in range(1, w, 2):
        mask = (1 << edge_to_bit[(r-1, c)]) | (1 << edge_to_bit[(r+1, c)]) | \
               (1 << edge_to_bit[(r, c-1)]) | (1 << edge_to_bit[(r, c+1)])
        box_masks.append(mask)

edge_boxes = [tuple(bm for bm in box_masks if bm & (1 << b)) for b in range(n_edges)]


# ======================================================================
# VERSAO CORRIGIDA: TT com EXACT-only
# ======================================================================
def solve_exact_tt(edges, depth, alpha, beta, maximizing, tt):
    if depth == 0 or edges == all_mask:
        return 0

    tt_key = (edges, depth, maximizing)
    if tt_key in tt:
        return tt[tt_key]   # Somente valores EXACT sao armazenados

    moves = []
    for i in range(n_edges):
        if not (edges & (1 << i)):
            closed = sum(1 for bm in edge_boxes[i] if (edges | (1 << i)) & bm == bm)
            moves.append((i, closed))
    moves.sort(key=lambda x: x[1], reverse=True)

    orig_alpha = alpha
    best_val = -10000 if maximizing else 10000

    for bit, closed in moves:
        new_e = edges | (1 << bit)
        if maximizing:
            val = (closed + solve_exact_tt(new_e, depth-1, alpha, beta, True, tt)) if closed > 0 else \
                  solve_exact_tt(new_e, depth-1, alpha, beta, False, tt)
            best_val = max(best_val, val)
            alpha = max(alpha, best_val)
        else:
            val = (-closed + solve_exact_tt(new_e, depth-1, alpha, beta, False, tt)) if closed > 0 else \
                  solve_exact_tt(new_e, depth-1, alpha, beta, True, tt)
            best_val = min(best_val, val)
            beta = min(beta, best_val)
        if beta <= alpha:
            break

    # Armazena somente se o valor e EXACT (nao foi constrangido pela janela)
    if best_val > orig_alpha and best_val < beta:
        tt[tt_key] = best_val

    return best_val


def scores_exact_tt(edges):
    tt = {}
    scores = np.full(31, -1e9, dtype=np.float32)
    for i in range(31):
        if not (edges & (1 << i)):
            closed = sum(1 for bm in edge_boxes[i] if (edges | (1 << i)) & bm == bm)
            new_e = edges | (1 << i)
            res = (closed + solve_exact_tt(new_e, 6, -10001, 10001, True, tt)) if closed > 0 else \
                  solve_exact_tt(new_e, 6, -10001, 10001, False, tt)
            scores[i] = float(res)
    return scores


# ======================================================================
# TESTAR: indice 10 (caso do bug), + amostras diversas
# ======================================================================
ARQUIVO = r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz"
d = np.load(ARQUIVO)
estados = d["estados"]
qtd_tracos = d["qtd_tracos"]
n = estados.shape[0]

print("=" * 80)
print("VALIDACAO DA CORRECAO: TT EXACT-only")
print("=" * 80)

# Caso do bug: indice 10
print("\n--- Indice 10 (caso do bug confirmado) ---")
mat = estados[10]
edges = 0
for r in range(9):
    for c in range(7):
        if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
            if mat[r, c] == 9:
                edges |= (1 << edge_to_bit[(r, c)])

# Corrigido
t0 = time.time()
scores_fix = scores_exact_tt(edges)
dt_fix = time.time() - t0

# Original (referencia)
estado = EstadoTabuleiro(LINHAS, COLUNAS)
for r in range(9):
    for c in range(7):
        val = int(mat[r, c])
        if val == 9 or val == 1:
            estado.matriz[r, c] = 1

t0 = time.time()
scores_orig = _scores_de_todas_jogadas(estado, 7)
dt_orig = time.time() - t0

# Comparar
divergencias = 0
for i, label in enumerate(LABELS):
    fix_val = scores_fix[i]
    orig_val = scores_orig.get(label, -1e9)
    if orig_val == -1e9 and fix_val == -1e9:
        continue
    if abs(fix_val - orig_val) > 0.01:
        divergencias += 1
        print(f"  DIFF [{i}] {label}: fix={fix_val:+.0f}, orig={orig_val:+.0f}")

if divergencias == 0:
    print(f"  OK! Zero divergencias (tempo fix={dt_fix:.2f}s, orig={dt_orig:.2f}s)")
else:
    print(f"  FALHOU: {divergencias} divergencias")

# Jogadas especificas do Gemini
for label in ["H_2_1", "V_7_2", "V_7_4"]:
    idx_l = LABELS.index(label)
    orig_val = scores_orig.get(label, -1e9)
    fix_val = scores_fix[idx_l]
    npz_val = d["score_melhor_jogada"][10][idx_l]
    status = "OK (corrigido!)" if abs(fix_val - orig_val) < 0.01 else "AINDA DIVERGE"
    print(f"  {label}: NPZ_antigo={npz_val:+.0f}, fix={fix_val:+.0f}, orig={orig_val:+.0f} -> {status}")

# Agora testar em uma amostra ampla (100 estados com >= 10 tracos)
print("\n--- Varredura de validacao (100 amostras com >= 10 tracos) ---")
np.random.seed(42)
candidatos = np.where(qtd_tracos >= 10)[0]
indices = np.random.choice(candidatos, size=min(100, len(candidatos)), replace=False)

total_ok = 0
total_div = 0
tempo_fix_total = 0
tempo_orig_total = 0

for idx in sorted(indices):
    mat = estados[idx]
    qt = int(qtd_tracos[idx])

    # Bitboard
    edges = 0
    for r in range(9):
        for c in range(7):
            if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
                if mat[r, c] == 9:
                    edges |= (1 << edge_to_bit[(r, c)])

    # Fix
    t0 = time.time()
    scores_fix = scores_exact_tt(edges)
    tempo_fix_total += time.time() - t0

    # Original
    estado = EstadoTabuleiro(LINHAS, COLUNAS)
    for r in range(9):
        for c in range(7):
            val = int(mat[r, c])
            if val == 9 or val == 1:
                estado.matriz[r, c] = 1

    t0 = time.time()
    scores_orig = _scores_de_todas_jogadas(estado, 7)
    tempo_orig_total += time.time() - t0

    # Comparar
    ok = True
    for i, label in enumerate(LABELS):
        fix_val = scores_fix[i]
        orig_val = scores_orig.get(label, -1e9)
        if orig_val == -1e9 and fix_val == -1e9:
            continue
        if abs(fix_val - orig_val) > 0.01:
            ok = False
            break

    if ok:
        total_ok += 1
    else:
        total_div += 1
        print(f"  DIVERGENCIA em idx={idx}, qtd_tracos={qt}")

print(f"\nResultado: {total_ok} OK, {total_div} divergencias")
print(f"Tempo total fix (TT EXACT):   {tempo_fix_total:.1f}s")
print(f"Tempo total original:          {tempo_orig_total:.1f}s")
print(f"Speedup fix vs original:       {tempo_orig_total / tempo_fix_total:.2f}x")

if total_div == 0:
    print("\n>>> CORRECAO VALIDADA! TT EXACT-only produz resultados identicos ao Original. <<<")
else:
    print(f"\n>>> ATENCAO: {total_div} divergencias encontradas. A correcao NAO e suficiente. <<<")

d.close()

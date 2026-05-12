"""
Investigacao da divergencia entre o Minimax Bitboard (Databricks) e o
Minimax Original (minimax_pontinhos.py).

O problema EXATO: no Databricks, quando o MINIMIZADOR fecha caixa(s), o
score e atualizado com "-closed", mas no original a contagem de caixas do
humano e incrementada corretamente.

Vamos reproduzir o algoritmo do Databricks localmente e comparar.
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
LABELS_CANONICOS = todos_labels_canonicos(LINHAS, COLUNAS)

# ======================================================================
# REPRODUZIR O ALGORITMO BITBOARD DO DATABRICKS EXATAMENTE
# ======================================================================
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

# Verificar mapeamento de labels
print("Verificacao do mapeamento bitboard -> labels:")
for i in range(n_edges):
    label_bit = bit_to_label[i]
    label_can = LABELS_CANONICOS[i]
    match = "OK" if label_bit == label_can else "DIFF"
    if match != "OK":
        print(f"  bit {i}: bitboard={label_bit}, canonico={label_can} [{match}]")
print(f"  Todos os {n_edges} labels conferem: {all(bit_to_label[i] == LABELS_CANONICOS[i] for i in range(n_edges))}")
print()

# MINIMAX DO DATABRICKS (copia exata do notebook)
def solve_minimax_databricks(edges, depth, alpha, beta, maximizing, tt):
    if depth == 0 or edges == all_mask:
        return 0

    tt_key = (edges, depth, maximizing)
    if tt_key in tt:
        flag, val = tt[tt_key]
        if flag == 0: return val
        if flag == 1 and val >= beta: return val
        if flag == 2 and val <= alpha: return val

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
            val = (closed + solve_minimax_databricks(new_e, depth-1, alpha, beta, True, tt)) if closed > 0 else \
                  solve_minimax_databricks(new_e, depth-1, alpha, beta, False, tt)
            best_val = max(best_val, val)
            alpha = max(alpha, best_val)
        else:
            val = (-closed + solve_minimax_databricks(new_e, depth-1, alpha, beta, False, tt)) if closed > 0 else \
                  solve_minimax_databricks(new_e, depth-1, alpha, beta, True, tt)
            best_val = min(best_val, val)
            beta = min(beta, best_val)
        if beta <= alpha: break

    tt[tt_key] = (0 if best_val > orig_alpha and best_val < beta else (1 if best_val >= beta else 2), best_val)
    return best_val


# MINIMAX DO DATABRICKS SEM TT (para isolar efeito da TT)
def solve_minimax_databricks_no_tt(edges, depth, alpha, beta, maximizing):
    if depth == 0 or edges == all_mask:
        return 0

    moves = []
    for i in range(n_edges):
        if not (edges & (1 << i)):
            closed = sum(1 for bm in edge_boxes[i] if (edges | (1 << i)) & bm == bm)
            moves.append((i, closed))
    moves.sort(key=lambda x: x[1], reverse=True)

    best_val = -10000 if maximizing else 10000

    for bit, closed in moves:
        new_e = edges | (1 << bit)
        if maximizing:
            val = (closed + solve_minimax_databricks_no_tt(new_e, depth-1, alpha, beta, True)) if closed > 0 else \
                  solve_minimax_databricks_no_tt(new_e, depth-1, alpha, beta, False)
            best_val = max(best_val, val)
            alpha = max(alpha, best_val)
        else:
            val = (-closed + solve_minimax_databricks_no_tt(new_e, depth-1, alpha, beta, False)) if closed > 0 else \
                  solve_minimax_databricks_no_tt(new_e, depth-1, alpha, beta, True)
            best_val = min(best_val, val)
            beta = min(beta, best_val)
        if beta <= alpha: break

    return best_val


# ======================================================================
# TESTAR NO INDICE 10
# ======================================================================
d = np.load(r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz")
mat = d["estados"][10]

# Converter para bitboard
edges = 0
for r in range(9):
    for c in range(7):
        if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
            if mat[r, c] == 9:
                edges |= (1 << edge_to_bit[(r, c)])

print("=" * 80)
print("INDICE 10 - Comparacao de 3 implementacoes")
print("=" * 80)
print(f"Bitboard edges = {bin(edges)}")
print()

# 1. Databricks COM TT
print("1. DATABRICKS (COM TT):")
tt = {}
scores_db = np.full(31, -1e9, dtype=np.float32)
for i in range(31):
    if not (edges & (1 << i)):
        closed = sum(1 for bm in edge_boxes[i] if (edges | (1 << i)) & bm == bm)
        new_e = edges | (1 << i)
        res = (closed + solve_minimax_databricks(new_e, 6, -10001, 10001, True, tt)) if closed > 0 else \
              solve_minimax_databricks(new_e, 6, -10001, 10001, False, tt)
        scores_db[i] = float(res)

# 2. Databricks SEM TT
print("2. DATABRICKS (SEM TT):")
scores_db_no_tt = np.full(31, -1e9, dtype=np.float32)
for i in range(31):
    if not (edges & (1 << i)):
        closed = sum(1 for bm in edge_boxes[i] if (edges | (1 << i)) & bm == bm)
        new_e = edges | (1 << i)
        res = (closed + solve_minimax_databricks_no_tt(new_e, 6, -10001, 10001, True)) if closed > 0 else \
              solve_minimax_databricks_no_tt(new_e, 6, -10001, 10001, False)
        scores_db_no_tt[i] = float(res)

# 3. Original (minimax_pontinhos.py)
print("3. ORIGINAL (minimax_pontinhos.py):")
estado = EstadoTabuleiro(LINHAS, COLUNAS)
for r in range(9):
    for c in range(7):
        val = int(mat[r, c])
        if val == 9:
            estado.matriz[r, c] = 1
        elif val == 1:
            estado.matriz[r, c] = 1

scores_orig = _scores_de_todas_jogadas(estado, 7)

print()
print("COMPARACAO COMPLETA:")
print(f"{'Idx':>3} {'Label':<6} {'NPZ':>5} {'DB+TT':>6} {'DB-TT':>6} {'Orig':>6} {'DB+TT=Orig':>12} {'DB-TT=Orig':>12}")
print("-" * 70)

for i in range(31):
    label = LABELS_CANONICOS[i]
    npz_val = d["score_melhor_jogada"][10][i]
    db_val = scores_db[i]
    db_no_tt_val = scores_db_no_tt[i]
    orig_val = scores_orig.get(label, -1e9)

    if npz_val == -1e9 and db_val == -1e9 and orig_val == -1e9:
        continue

    db_ok = "OK" if abs(db_val - (orig_val if orig_val != -1e9 else -1e9)) < 0.01 else "DIFF"
    db_no_tt_ok = "OK" if abs(db_no_tt_val - (orig_val if orig_val != -1e9 else -1e9)) < 0.01 else "DIFF"
    npz_eq_db = "OK" if abs(npz_val - db_val) < 0.01 else "DIFF"

    print(f"{i:3d} {label:<6} {npz_val:+5.0f} {db_val:+6.0f} {db_no_tt_val:+6.0f} {orig_val:+6.0f}   {db_ok:>10}   {db_no_tt_ok:>10}   NPZ=DB:{npz_eq_db}")

print()

# Identificar divergencias
diffs_tt = []
diffs_no_tt = []
for i in range(31):
    label = LABELS_CANONICOS[i]
    db_val = scores_db[i]
    db_no_tt_val = scores_db_no_tt[i]
    orig_val = scores_orig.get(label, -1e9)
    if orig_val == -1e9:
        continue
    if abs(db_val - orig_val) > 0.01:
        diffs_tt.append((i, label, db_val, orig_val))
    if abs(db_no_tt_val - orig_val) > 0.01:
        diffs_no_tt.append((i, label, db_no_tt_val, orig_val))

print("=" * 80)
print("DIAGNOSTICO:")
print("=" * 80)

if diffs_tt:
    print(f"\nDatabricks COM TT: {len(diffs_tt)} divergencias vs Original:")
    for i, lb, db, orig in diffs_tt:
        print(f"  [{i}] {lb}: DB+TT={db:+.0f}, Orig={orig:+.0f}")
else:
    print("\nDatabricks COM TT: ZERO divergencias")

if diffs_no_tt:
    print(f"\nDatabricks SEM TT: {len(diffs_no_tt)} divergencias vs Original:")
    for i, lb, db, orig in diffs_no_tt:
        print(f"  [{i}] {lb}: DB-TT={db:+.0f}, Orig={orig:+.0f}")
else:
    print("\nDatabricks SEM TT: ZERO divergencias")

# Se TT causa o problema, e a TT sem TT nao, o bug e na TT
if diffs_tt and not diffs_no_tt:
    print("\n>>> BUG CONFIRMADO: A Transposition Table esta causando resultados incorretos!")
    print(">>> O algoritmo base (sem TT) esta correto, mas a TT com bounds esta corrompendo scores.")
elif diffs_tt and diffs_no_tt:
    print("\n>>> BUG no algoritmo BASE (nao relacionado a TT)!")
elif not diffs_tt and not diffs_no_tt:
    print("\n>>> Nenhuma divergencia - o bug nao se reproduz nesta amostra")

d.close()

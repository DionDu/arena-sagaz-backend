"""Teste de velocidade e exatidao com TT bounds completos para MIN e MAX."""
import sys, numpy as np, time
sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import todos_labels_canonicos, TAMANHOS

LINHAS, COLUNAS = TAMANHOS["pequeno"]
LABELS = todos_labels_canonicos(LINHAS, COLUNAS)

h, w = 9, 7
edge_to_bit, bit_idx = {}, 0
for r in range(h):
    for c in range(w):
        if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
            edge_to_bit[(r,c)] = bit_idx; bit_idx += 1
n_edges = bit_idx; all_mask = (1 << n_edges) - 1
box_masks = []
for r in range(1,h,2):
    for c in range(1,w,2):
        mask = (1<<edge_to_bit[(r-1,c)])|(1<<edge_to_bit[(r+1,c)])|(1<<edge_to_bit[(r,c-1)])|(1<<edge_to_bit[(r,c+1)])
        box_masks.append(mask)
edge_boxes = [tuple(bm for bm in box_masks if bm&(1<<b)) for b in range(n_edges)]

def solve_pure(edges, depth, maximizing):
    """Gabarito absoluto"""
    if depth == 0 or edges == all_mask: return 0
    bv = -10000 if maximizing else 10000
    for i in range(n_edges):
        if not (edges & (1 << i)):
            ne = edges | (1 << i)
            cl = sum(1 for bm in edge_boxes[i] if ne & bm == bm and edges & bm != bm)
            if maximizing:
                v = (cl + solve_pure(ne, depth-1, True)) if cl > 0 else solve_pure(ne, depth-1, False)
                bv = max(bv, v)
            else:
                v = (-cl + solve_pure(ne, depth-1, False)) if cl > 0 else solve_pure(ne, depth-1, True)
                bv = min(bv, v)
    return bv

def solve_ab_fixed_tt(edges, depth, alpha, beta, maximizing, tt):
    if depth == 0 or edges == all_mask: return 0
    
    tt_key = (edges, depth, maximizing)
    if tt_key in tt:
        flag, val = tt[tt_key]
        if flag == 0: return val
        if flag == 1 and val >= beta: return val
        if flag == 2 and val <= alpha: return val

    moves = []
    for i in range(n_edges):
        if not (edges & (1 << i)):
            ne = edges | (1 << i)
            cl = sum(1 for bm in edge_boxes[i] if ne & bm == bm and edges & bm != bm)
            moves.append((i, cl))
    moves.sort(key=lambda x: x[1], reverse=True)
    
    orig_alpha = alpha
    orig_beta = beta
    best_val = -10000 if maximizing else 10000
    
    for bit, cl in moves:
        ne = edges | (1 << bit)
        if maximizing:
            v = (cl + solve_ab_fixed_tt(ne, depth-1, alpha - cl, beta - cl, True, tt)) if cl > 0 else \
                solve_ab_fixed_tt(ne, depth-1, alpha, beta, False, tt)
            best_val = max(best_val, v); alpha = max(alpha, best_val)
        else:
            v = (-cl + solve_ab_fixed_tt(ne, depth-1, alpha + cl, beta + cl, False, tt)) if cl > 0 else \
                solve_ab_fixed_tt(ne, depth-1, alpha, beta, True, tt)
            best_val = min(best_val, v); beta = min(beta, best_val)
        if beta <= alpha: break

    # Bounds corretamente orientados por jogador
    if maximizing:
        if best_val <= orig_alpha: flag = 2 # UPPERBOUND
        elif best_val >= beta: flag = 1 # LOWERBOUND
        else: flag = 0 # EXACT
    else:
        if best_val >= orig_beta: flag = 1 # LOWERBOUND
        elif best_val <= alpha: flag = 2 # UPPERBOUND
        else: flag = 0 # EXACT

    tt[tt_key] = (flag, best_val)

    return best_val

d = np.load(r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz")
estados = d["estados"]; qtd = d["qtd_tracos"]
np.random.seed(42)
cands = np.where(qtd >= 10)[0]
indices = np.random.choice(cands, size=min(100, len(cands)), replace=False)

div = 0; t0 = time.time()
for idx in sorted(indices):
    mat = estados[idx]
    edges = 0
    for r in range(9):
        for c in range(7):
            if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
                if mat[r,c] == 9: edges |= (1 << edge_to_bit[(r,c)])

    scores_bb = np.full(31, -1e9, dtype=np.float32)
    scores_pure = np.full(31, -1e9, dtype=np.float32)
    
    for i in range(31):
        if not (edges & (1 << i)):
            ne = edges | (1 << i)
            cl = sum(1 for bm in edge_boxes[i] if ne & bm == bm and edges & bm != bm)
            
            # Pure (lentidao garantida para bater)
            p = (cl + solve_pure(ne, 6, True)) if cl > 0 else solve_pure(ne, 6, False)
            scores_pure[i] = float(p)
            
            # TT Otimizada
            tt = {}
            a = (cl + solve_ab_fixed_tt(ne, 6, -10001, 10001, True, tt)) if cl > 0 else \
                 solve_ab_fixed_tt(ne, 6, -10001, 10001, False, tt)
            scores_bb[i] = float(a)

    for i in range(31):
        if abs(scores_bb[i] - scores_pure[i]) > 0.01:
            div += 1
            print(f"  DIVERGENCIA idx={idx}: [{i}] {LABELS[i]}: AB={scores_bb[i]:+.0f}, Pure={scores_pure[i]:+.0f}")
            break

dt = time.time() - t0
print(f"Alpha-beta COM TT CORRETA: {100-div}/100 OK, {div} div, tempo={dt:.1f}s")
d.close()

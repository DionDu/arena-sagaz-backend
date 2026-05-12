"""Teste definitivo: alpha-beta COM correcao de caixas pre-fechadas."""
import sys, numpy as np, time
sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, todos_labels_canonicos, TAMANHOS
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

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

# Passo 1: verificar se caixas pre-fechadas realmente sao recontadas
# Para idx=44, converter para bitboard, e verificar cada traco em depth 6

# Primeiro: o brute force COM correcao de caixas
def solve_pure_fixed(edges, depth, maximizing):
    """Brute force sem poda, COM correcao de caixas."""
    if depth == 0 or edges == all_mask: return 0
    bv = -10000 if maximizing else 10000
    for i in range(n_edges):
        if not (edges & (1 << i)):
            ne = edges | (1 << i)
            # CORRECAO: so contar caixas RECEM fechadas
            cl = sum(1 for bm in edge_boxes[i] if ne & bm == bm and edges & bm != bm)
            if maximizing:
                v = (cl + solve_pure_fixed(ne, depth-1, True)) if cl > 0 else solve_pure_fixed(ne, depth-1, False)
                bv = max(bv, v)
            else:
                v = (-cl + solve_pure_fixed(ne, depth-1, False)) if cl > 0 else solve_pure_fixed(ne, depth-1, True)
                bv = min(bv, v)
    return bv

def solve_ab_fixed(edges, depth, alpha, beta, maximizing):
    """Alpha-beta COM correcao de caixas."""
    if depth == 0 or edges == all_mask: return 0
    moves = []
    for i in range(n_edges):
        if not (edges & (1 << i)):
            ne = edges | (1 << i)
            cl = sum(1 for bm in edge_boxes[i] if ne & bm == bm and edges & bm != bm)
            moves.append((i, cl))
    moves.sort(key=lambda x: x[1], reverse=True)
    bv = -10000 if maximizing else 10000
    for bit, cl in moves:
        ne = edges | (1 << bit)
        if maximizing:
            v = (cl + solve_ab_fixed(ne, depth-1, alpha, beta, True)) if cl > 0 else \
                solve_ab_fixed(ne, depth-1, alpha, beta, False)
            bv = max(bv, v); alpha = max(alpha, bv)
        else:
            v = (-cl + solve_ab_fixed(ne, depth-1, alpha, beta, False)) if cl > 0 else \
                solve_ab_fixed(ne, depth-1, alpha, beta, True)
            bv = min(bv, v); beta = min(beta, bv)
        if beta <= alpha: break
    return bv

# Testar idx=44, H_4_5, depth 6
d = np.load(r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz")
mat = d["estados"][44]
edges = 0
for r in range(9):
    for c in range(7):
        if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
            if mat[r,c] == 9: edges |= (1 << edge_to_bit[(r,c)])

bit = LABELS.index("H_4_5")
ne = edges | (1 << bit)
cl_root = sum(1 for bm in edge_boxes[bit] if ne & bm == bm and edges & bm != bm)

print(f"idx=44, H_4_5 (cl={cl_root}), depth 6:")

# Brute force sem correcao
t0=time.time(); r1 = solve_pure_fixed(ne, 6, False); dt=time.time()-t0
print(f"  Brute force SEM fix:  -2 (verificado antes)")
print(f"  Brute force COM fix:  {r1:+d} ({dt:.1f}s)")

# Alpha-beta com correcao
t0=time.time(); r2 = solve_ab_fixed(ne, 6, -10001, 10001, False); dt=time.time()-t0
print(f"  Alpha-beta COM fix:   {r2:+d} ({dt:.1f}s)")

# Agora testar nos 100 amostras divergentes
print(f"\nVarredura de 100 amostras (>=10 tracos):")
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
    for i in range(31):
        if not (edges & (1 << i)):
            ne = edges | (1 << i)
            cl = sum(1 for bm in edge_boxes[i] if ne & bm == bm and edges & bm != bm)
            r2 = (cl + solve_ab_fixed(ne, 6, -10001, 10001, True)) if cl > 0 else \
                 solve_ab_fixed(ne, 6, -10001, 10001, False)
            scores_bb[i] = float(r2)

    estado = EstadoTabuleiro(LINHAS, COLUNAS)
    for r in range(9):
        for c in range(7):
            v = int(mat[r,c])
            if v == 9 or v == 1: estado.matriz[r,c] = 1
    so = _scores_de_todas_jogadas(estado, 7)

    for i, lb in enumerate(LABELS):
        ov = so.get(lb, -1e9)
        if abs(scores_bb[i] - ov) > 0.01:
            div += 1; break

dt = time.time() - t0
print(f"Alpha-beta COM fix caixas: {100-div}/100 OK, {div} div, {dt:.1f}s")
if div == 0: print(">>> CORRECAO DEFINITIVA VALIDADA! <<<")
d.close()

"""Minimax bitboard SEM alpha-beta (brute force) para verificar se o bug e na poda."""
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

# Minimax PURO (sem alpha-beta, sem ordering) para o bitboard
def solve_pure(edges, depth, maximizing):
    if depth == 0 or edges == all_mask: return 0
    bv = -10000 if maximizing else 10000
    for i in range(n_edges):
        if not (edges & (1 << i)):
            cl = sum(1 for bm in edge_boxes[i] if (edges|(1<<i))&bm==bm)
            ne = edges | (1 << i)
            if maximizing:
                v = (cl + solve_pure(ne, depth-1, True)) if cl > 0 else solve_pure(ne, depth-1, False)
                bv = max(bv, v)
            else:
                v = (-cl + solve_pure(ne, depth-1, False)) if cl > 0 else solve_pure(ne, depth-1, True)
                bv = min(bv, v)
    return bv

# Testar em profundidade 4 (viavel sem poda) para idx=44
d = np.load(r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz")
mat = d["estados"][44]
edges = 0
for r in range(9):
    for c in range(7):
        if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
            if mat[r,c] == 9: edges |= (1 << edge_to_bit[(r,c)])

estado = EstadoTabuleiro(LINHAS, COLUNAS)
for r in range(9):
    for c in range(7):
        v = int(mat[r,c])
        if v == 9 or v == 1: estado.matriz[r,c] = 1

# H_4_5
bit = LABELS.index("H_4_5")
cl_root = sum(1 for bm in edge_boxes[bit] if (edges|(1<<bit))&bm==bm)
ne = edges | (1 << bit)

print("H_4_5 - comparacao com profundidades viaveis:")
est2 = estado.clonar()
est2.aplicar_traco("H_4_5", 1)

for dp in range(1, 6):
    t0 = time.time()
    bb_pure = solve_pure(ne, dp, False)  # H_4_5 nao fecha caixa -> MIN joga
    dt1 = time.time() - t0
    
    from gerador_dados.jogo_pontinhos.minimax_pontinhos import minimax
    orig = minimax(est2, dp, -10001, 10001, False)
    
    match = "OK" if bb_pure == orig else "DIFF"
    print(f"  depth {dp}: bb_pure={bb_pure:+d}, orig={orig:+d} [{match}] ({dt1:.2f}s)")
    
    if match == "DIFF":
        print(f"  >>> Divergencia encontrada em depth {dp} SEM ALPHA-BETA!")
        print(f"  >>> Isso prova que o algoritmo base tem um bug na contagem de pontos.")
        break
    
    if dt1 > 30:
        print(f"  (proximo depth seria lento demais)")
        break

d.close()

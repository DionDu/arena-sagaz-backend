"""
CORRECAO DEFINITIVA: o bitboard re-conta caixas pre-fechadas na recursao.

A condicao correta para contar caixas fechadas por um novo traco e:
  closed = sum(1 for bm in edge_boxes[i]
               if (edges | (1<<i)) & bm == bm   # 4 lados completos DEPOIS
               and edges & bm != bm)              # MAS nao antes

Isso precisa estar em TODOS os 3 lugares:
1. No move ordering dentro de solve
2. Na avaliacao dentro de solve  
3. Na chamada da raiz
"""
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
            edge_to_bit[(r,c)] = bit_idx
            bit_idx += 1
n_edges = bit_idx
all_mask = (1 << n_edges) - 1
box_masks = []
for r in range(1,h,2):
    for c in range(1,w,2):
        mask = (1<<edge_to_bit[(r-1,c)])|(1<<edge_to_bit[(r+1,c)])|(1<<edge_to_bit[(r,c-1)])|(1<<edge_to_bit[(r,c+1)])
        box_masks.append(mask)
edge_boxes = [tuple(bm for bm in box_masks if bm&(1<<b)) for b in range(n_edges)]

def count_closed(edges, bit):
    """Conta caixas RECEM-FECHADAS pelo bit (exclui caixas ja fechadas)."""
    new_e = edges | (1 << bit)
    return sum(1 for bm in edge_boxes[bit]
               if new_e & bm == bm      # 4 lados completos depois
               and edges & bm != bm)     # nao estava completa antes

def solve_v2(edges, depth, alpha, beta, maximizing):
    if depth == 0 or edges == all_mask: return 0
    moves = []
    for i in range(n_edges):
        if not (edges & (1 << i)):
            cl = count_closed(edges, i)
            moves.append((i, cl))
    moves.sort(key=lambda x: x[1], reverse=True)
    bv = -10000 if maximizing else 10000
    for bit, cl in moves:
        ne = edges | (1 << bit)
        if maximizing:
            v = (cl + solve_v2(ne, depth-1, alpha, beta, True)) if cl > 0 else \
                solve_v2(ne, depth-1, alpha, beta, False)
            bv = max(bv, v); alpha = max(alpha, bv)
        else:
            v = (-cl + solve_v2(ne, depth-1, alpha, beta, False)) if cl > 0 else \
                solve_v2(ne, depth-1, alpha, beta, True)
            bv = min(bv, v); beta = min(beta, bv)
        if beta <= alpha: break
    return bv

# TESTE em 100 amostras
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

    # Bitboard corrigido
    scores_bb = np.full(31, -1e9, dtype=np.float32)
    for i in range(31):
        if not (edges & (1 << i)):
            cl = count_closed(edges, i)
            ne = edges | (1 << i)
            r2 = (cl + solve_v2(ne, 6, -10001, 10001, True)) if cl > 0 else \
                 solve_v2(ne, 6, -10001, 10001, False)
            scores_bb[i] = float(r2)

    # Original
    estado = EstadoTabuleiro(LINHAS, COLUNAS)
    for r in range(9):
        for c in range(7):
            v = int(mat[r,c])
            if v == 9 or v == 1: estado.matriz[r,c] = 1
    so = _scores_de_todas_jogadas(estado, 7)

    for i, lb in enumerate(LABELS):
        ov = so.get(lb, -1e9)
        if abs(scores_bb[i] - ov) > 0.01:
            div += 1
            print(f"  DIVERGENCIA idx={idx}, qt={int(qtd[idx])}: [{i}] {lb}: bb={scores_bb[i]:+.0f}, orig={ov:+.0f}")
            break

dt = time.time() - t0
print(f"\nBitboard V2 (sem TT, com fix caixas): {100-div}/100 OK, {div} div, {dt:.1f}s")
if div == 0:
    print(">>> CORRECAO V2 VALIDADA! <<<")
d.close()

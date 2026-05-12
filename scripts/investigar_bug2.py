"""
BUG #2: O bitboard NAO rastreia caixas pre-fechadas.

No original (minimax_pontinhos.py), quando um traco fecha uma caixa,
_verificar_caixas checa se _caixa_fechada() E se o interior da caixa
ainda esta vazio (== 0). Se ja esta marcada (!=0), nao re-conta.

No bitboard, a verificacao e: (edges | novo_bit) & box_mask == box_mask
Isso so verifica se os 4 lados estao preenchidos. Se os 4 lados JA estavam
preenchidos ANTES (caixa pre-fechada no estado inicial), adicionar um 5o
traco adjacente nao fecha NENHUMA nova caixa, mas o bitboard pode contar
uma caixa adjacente como "fechada" se essa outra caixa compartilha lados
com a pre-fechada.

A solucao: o bitboard precisa descontar caixas que JA ESTAVAM fechadas
antes do movimento.
"""
import sys, numpy as np
sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")

# O bitboard conta caixas fechadas como:
# closed = sum(1 for bm in edge_boxes[i] if (edges | (1<<i)) & bm == bm)
#
# A correcao e:
# closed = sum(1 for bm in edge_boxes[i] if (edges | (1<<i)) & bm == bm and edges & bm != bm)
#                                                                          ^^^^^^^^^^^^^^^^^^^^
#                                          so conta se NAO ESTAVA ja fechada antes

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, todos_labels_canonicos, TAMANHOS
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

LINHAS, COLUNAS = TAMANHOS["pequeno"]
LABELS = todos_labels_canonicos(LINHAS, COLUNAS)

h, w = 9, 7
edge_to_bit, bit_to_label, bit_idx = {}, {}, 0
for r in range(h):
    for c in range(w):
        if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
            edge_to_bit[(r,c)] = bit_idx
            bit_to_label[bit_idx] = f"H_{r}_{c}" if r%2==0 else f"V_{r}_{c}"
            bit_idx += 1
n_edges = bit_idx
all_mask = (1 << n_edges) - 1
box_masks = []
for r in range(1,h,2):
    for c in range(1,w,2):
        mask = (1<<edge_to_bit[(r-1,c)])|(1<<edge_to_bit[(r+1,c)])|(1<<edge_to_bit[(r,c-1)])|(1<<edge_to_bit[(r,c+1)])
        box_masks.append(mask)
edge_boxes = [tuple(bm for bm in box_masks if bm&(1<<b)) for b in range(n_edges)]

# VERSAO CORRIGIDA do Minimax bitboard
def solve_fixed(edges, depth, alpha, beta, maximizing):
    if depth == 0 or edges == all_mask: return 0
    moves = []
    for i in range(n_edges):
        if not (edges & (1 << i)):
            # CORRECAO: so contar caixas que NAO estavam fechadas antes
            closed = sum(1 for bm in edge_boxes[i]
                        if (edges | (1 << i)) & bm == bm  # fecha agora
                        and edges & bm != bm)              # NAO estava fechada antes
            moves.append((i, closed))
    moves.sort(key=lambda x: x[1], reverse=True)
    bv = -10000 if maximizing else 10000
    for bit, closed in moves:
        ne = edges | (1 << bit)
        if maximizing:
            v = (closed + solve_fixed(ne, depth-1, alpha, beta, True)) if closed > 0 else \
                solve_fixed(ne, depth-1, alpha, beta, False)
            bv = max(bv, v); alpha = max(alpha, bv)
        else:
            v = (-closed + solve_fixed(ne, depth-1, alpha, beta, False)) if closed > 0 else \
                solve_fixed(ne, depth-1, alpha, beta, True)
            bv = min(bv, v); beta = min(beta, bv)
        if beta <= alpha: break
    return bv

def scores_fixed(edges):
    scores = np.full(31, -1e9, dtype=np.float32)
    for i in range(31):
        if not (edges & (1 << i)):
            closed = sum(1 for bm in edge_boxes[i]
                        if (edges | (1 << i)) & bm == bm
                        and edges & bm != bm)
            ne = edges | (1 << i)
            r2 = (closed + solve_fixed(ne, 6, -10001, 10001, True)) if closed > 0 else \
                 solve_fixed(ne, 6, -10001, 10001, False)
            scores[i] = float(r2)
    return scores

# TESTE: 100 amostras com >= 10 tracos
import time
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
    sc = scores_fixed(edges)
    estado = EstadoTabuleiro(LINHAS, COLUNAS)
    for r in range(9):
        for c in range(7):
            v = int(mat[r,c])
            if v == 9 or v == 1: estado.matriz[r,c] = 1
    so = _scores_de_todas_jogadas(estado, 7)
    for i, lb in enumerate(LABELS):
        ov = so.get(lb, -1e9)
        if abs(sc[i] - ov) > 0.01:
            div += 1
            print(f"  DIVERGENCIA idx={idx}: [{i}] {lb}: fix={sc[i]:+.0f}, orig={ov:+.0f}")
            break

dt = time.time() - t0
print(f"\nBitboard CORRIGIDO (sem TT): {100-div}/100 OK, {div} div, {dt:.1f}s")

if div == 0:
    print(">>> CORRECAO VALIDADA! O bug era a re-contagem de caixas pre-fechadas. <<<")
d.close()

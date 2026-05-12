"""Comparacao jogada-a-jogada entre bitboard e original em profundidades 1-4."""
import sys, numpy as np
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

def solve_bb(edges, depth, alpha, beta, maximizing):
    if depth==0 or edges==all_mask: return 0
    moves=[]
    for i in range(n_edges):
        if not(edges&(1<<i)):
            cl=sum(1 for bm in edge_boxes[i] if (edges|(1<<i))&bm==bm)
            moves.append((i,cl))
    moves.sort(key=lambda x:x[1],reverse=True)
    bv=-10000 if maximizing else 10000
    for bit,cl in moves:
        ne=edges|(1<<bit)
        if maximizing:
            v=(cl+solve_bb(ne,depth-1,alpha,beta,True)) if cl>0 else solve_bb(ne,depth-1,alpha,beta,False)
            bv=max(bv,v); alpha=max(alpha,bv)
        else:
            v=(-cl+solve_bb(ne,depth-1,alpha,beta,False)) if cl>0 else solve_bb(ne,depth-1,alpha,beta,True)
            bv=min(bv,v); beta=min(beta,bv)
        if beta<=alpha: break
    return bv

# Caso divergente: idx=44
d=np.load(r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz")
mat=d["estados"][44]

edges=0
for r in range(9):
    for c in range(7):
        if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
            if mat[r,c]==9: edges|=(1<<edge_to_bit[(r,c)])

estado=EstadoTabuleiro(LINHAS,COLUNAS)
for r in range(9):
    for c in range(7):
        v=int(mat[r,c])
        if v==9 or v==1: estado.matriz[r,c]=1

print("Comparacao por profundidade para idx=44:")
for dp in range(1,8):
    so=_scores_de_todas_jogadas(estado,dp)
    diverge=False
    for i in range(31):
        lb=LABELS[i]
        if not(edges&(1<<i)):
            cl=sum(1 for bm in edge_boxes[i] if (edges|(1<<i))&bm==bm)
            ne=edges|(1<<i)
            bb=(cl+solve_bb(ne,dp-1,-10001,10001,True)) if cl>0 else solve_bb(ne,dp-1,-10001,10001,False)
            ov=so.get(lb,-1e9)
            if abs(bb-ov)>0.01:
                if not diverge:
                    print(f"\n  Depth {dp}: DIVERGE")
                    diverge=True
                print(f"    [{i}] {lb}: bb={bb:+.0f}, orig={ov:+.0f}, diff={bb-ov:+.0f}")
    if not diverge:
        print(f"  Depth {dp}: OK")
    if diverge:
        break

# Se diverge em depth X, olhar o move ordering
print("\n\nComparacao de move ordering no Original vs Bitboard:")
disp_orig = estado.tracos_disponiveis()
print(f"Original tracos_disponiveis (ordem): {disp_orig}")

# No original, o move ordering e: tracos_bons (fecha caixa) + tracos_normais
# No bitboard, o move ordering e: sort by closed desc
# Isso PODE dar ordens diferentes quando ha empates!

# Verificar: para o estado atual, quais tracos fecham caixas?
for lb in disp_orig:
    est2=estado.clonar()
    f=est2.aplicar_traco(lb, 1)
    est2.desfazer_traco(lb)
    
    i=LABELS.index(lb)
    cl_bb=sum(1 for bm in edge_boxes[i] if (edges|(1<<i))&bm==bm)
    
    if f != cl_bb:
        print(f"  {lb}: orig fecha={f}, bb fecha={cl_bb} *** DIFERENTE! ***")
    elif f > 0:
        print(f"  {lb}: fecha={f} (ambos concordam)")

d.close()

"""Trace detalhado: comparar arvore do bitboard vs original passo a passo para H_4_5 depth 6."""
import sys, numpy as np
sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, todos_labels_canonicos, TAMANHOS
from gerador_dados.jogo_pontinhos.minimax_pontinhos import minimax

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

def solve_bb_trace(edges, depth, alpha, beta, maximizing, indent=0):
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
        lb=LABELS[bit]
        if maximizing:
            v=(cl+solve_bb_trace(ne,depth-1,alpha,beta,True,indent+1)) if cl>0 else solve_bb_trace(ne,depth-1,alpha,beta,False,indent+1)
            if indent < 2:
                print(f"{'  '*indent}MAX d={depth} {lb}: cl={cl}, v={v:+d}, bv={bv:+d}")
            bv=max(bv,v); alpha=max(alpha,bv)
        else:
            v=(-cl+solve_bb_trace(ne,depth-1,alpha,beta,False,indent+1)) if cl>0 else solve_bb_trace(ne,depth-1,alpha,beta,True,indent+1)
            if indent < 2:
                print(f"{'  '*indent}MIN d={depth} {lb}: cl={cl}, v={v:+d}, bv={bv:+d}")
            bv=min(bv,v); beta=min(beta,bv)
        if beta<=alpha:
            if indent < 2: print(f"{'  '*indent}  PRUNE")
            break
    return bv

# idx=44, jogada H_4_5 (bit 16)
d=np.load(r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz")
mat=d["estados"][44]

edges=0
for r in range(9):
    for c in range(7):
        if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
            if mat[r,c]==9: edges|=(1<<edge_to_bit[(r,c)])

bit_h45 = LABELS.index("H_4_5")
cl_h45 = sum(1 for bm in edge_boxes[bit_h45] if (edges|(1<<bit_h45))&bm==bm)
ne_h45 = edges | (1 << bit_h45)

print(f"H_4_5: cl={cl_h45}, jogada do MAX")
print("=== BITBOARD TRACE (depth 5 apos H_4_5) ===")
# H_4_5 nao fecha caixa (cl=0), entao e a vez do MIN com depth 5
val_bb = solve_bb_trace(ne_h45, 5, -10001, 10001, False)
print(f"\nResultado bitboard: {val_bb:+d}")

# Agora o original
print("\n=== ORIGINAL TRACE ===")
estado=EstadoTabuleiro(LINHAS,COLUNAS)
for r in range(9):
    for c in range(7):
        v=int(mat[r,c])
        if v==9 or v==1: estado.matriz[r,c]=1

fechadas = estado.aplicar_traco("H_4_5", 1)
print(f"H_4_5: fecha={fechadas}")

# Chamar minimax no estado apos H_4_5
val_orig = minimax(estado, 5, -10001, 10001, False)
print(f"Resultado original: {val_orig:+d}")

# Comparar tracos disponiveis apos H_4_5
disp = estado.tracos_disponiveis()
print(f"\nTracos disponiveis apos H_4_5 (original): {len(disp)}")

# No bitboard, quais estao disponiveis?
disp_bb = [i for i in range(31) if not(ne_h45&(1<<i))]
disp_bb_labels = [LABELS[i] for i in disp_bb]
print(f"Tracos disponiveis apos H_4_5 (bitboard): {len(disp_bb)}")

if sorted(disp) != sorted(disp_bb_labels):
    print("*** DIFEREM! ***")
    print(f"  Orig: {sorted(disp)}")
    print(f"  BB:   {sorted(disp_bb_labels)}")
    print(f"  Extras no BB: {set(disp_bb_labels) - set(disp)}")
    print(f"  Faltam no BB: {set(disp) - set(disp_bb_labels)}")

# Verificar contagem de caixas para cada traco disponivel
print("\nContagem de caixas por traco (apos H_4_5):")
for lb in sorted(disp):
    i = LABELS.index(lb)
    cl_bb = sum(1 for bm in edge_boxes[i] if (ne_h45|(1<<i))&bm==bm)
    est2 = estado.clonar()
    f_orig = est2.aplicar_traco(lb, -1)  # MIN joga
    est2.desfazer_traco(lb)
    if cl_bb != f_orig:
        print(f"  {lb}: bb={cl_bb}, orig={f_orig} *** DIFERENTE! ***")

d.close()

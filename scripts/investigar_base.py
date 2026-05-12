"""Investigar divergencia no bitboard SEM TT - encontrar exatamente onde diverge."""
import sys, numpy as np
sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")
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

def solve_no_tt(edges, depth, alpha, beta, maximizing):
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
            v=(cl+solve_no_tt(ne,depth-1,alpha,beta,True)) if cl>0 else solve_no_tt(ne,depth-1,alpha,beta,False)
            bv=max(bv,v); alpha=max(alpha,bv)
        else:
            v=(-cl+solve_no_tt(ne,depth-1,alpha,beta,False)) if cl>0 else solve_no_tt(ne,depth-1,alpha,beta,True)
            bv=min(bv,v); beta=min(beta,bv)
        if beta<=alpha: break
    return bv

# Encontrar primeiro caso divergente
d=np.load(r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz")
estados=d["estados"]; qtd=d["qtd_tracos"]
np.random.seed(42)
cands=np.where(qtd>=10)[0]
indices=np.random.choice(cands,size=100,replace=False)

for idx in sorted(indices):
    mat=estados[idx]; qt=int(qtd[idx])
    edges=0
    for r in range(9):
        for c in range(7):
            if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
                if mat[r,c]==9: edges|=(1<<edge_to_bit[(r,c)])

    # Bitboard sem TT
    sc_bb=np.full(31,-1e9,dtype=np.float32)
    for i in range(31):
        if not(edges&(1<<i)):
            cl=sum(1 for bm in edge_boxes[i] if (edges|(1<<i))&bm==bm)
            ne=edges|(1<<i)
            r2=(cl+solve_no_tt(ne,6,-10001,10001,True)) if cl>0 else solve_no_tt(ne,6,-10001,10001,False)
            sc_bb[i]=float(r2)

    # Original
    estado=EstadoTabuleiro(LINHAS,COLUNAS)
    for r in range(9):
        for c in range(7):
            v=int(mat[r,c])
            if v==9 or v==1: estado.matriz[r,c]=1
    so=_scores_de_todas_jogadas(estado,7)

    tem_div=False
    for i,lb in enumerate(LABELS):
        ov=so.get(lb,-1e9)
        if abs(sc_bb[i]-ov)>0.01:
            if not tem_div:
                print(f"\nDIVERGENCIA idx={idx}, qtd={qt}")
                print(f"Matriz:\n{mat}")
                tem_div=True
            print(f"  [{i}] {lb}: bitboard={sc_bb[i]:+.0f}, orig={ov:+.0f}")

    if tem_div:
        # Verificar: os tracos disponiveis sao os mesmos?
        disp_bb = [i for i in range(31) if not(edges&(1<<i))]
        disp_orig = estado.tracos_disponiveis()
        disp_orig_idx = [LABELS.index(l) for l in disp_orig]
        if sorted(disp_bb) != sorted(disp_orig_idx):
            print(f"  TRACOS DIFERENTES! bb={sorted(disp_bb)}, orig={sorted(disp_orig_idx)}")
        else:
            print(f"  Tracos disponiveis: IDENTICOS ({len(disp_bb)} tracos)")

        # Teste com profundidade menor para isolar
        for dp in [1,2,3]:
            so_dp = _scores_de_todas_jogadas(estado, dp)
            for i,lb in enumerate(LABELS):
                if not(edges&(1<<i)):
                    ne=edges|(1<<i)
                    cl=sum(1 for bm in edge_boxes[i] if ne&bm==bm)
                    r2=(cl+solve_no_tt(ne,dp-1,-10001,10001,True)) if cl>0 else solve_no_tt(ne,dp-1,-10001,10001,False)
                    ov=so_dp.get(lb, -1e9)
                    if abs(r2-ov)>0.01:
                        print(f"  Diverge ja em depth={dp}! [{i}] {lb}: bb={r2:+.0f}, orig={ov:+.0f}")
                        break
            else:
                continue
            break
        break  # So analisar o primeiro caso
d.close()

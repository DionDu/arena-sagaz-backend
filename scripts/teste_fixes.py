"""Teste rapido: TT fresca por jogada da raiz vs sem TT vs original."""
import sys, numpy as np, time
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

def solve_tt(edges, depth, alpha, beta, maximizing, tt):
    if depth==0 or edges==all_mask: return 0
    k=(edges,depth,maximizing)
    if k in tt:
        f,v=tt[k]
        if f==0: return v
        if f==1 and v>=beta: return v
        if f==2 and v<=alpha: return v
    moves=[]
    for i in range(n_edges):
        if not(edges&(1<<i)):
            cl=sum(1 for bm in edge_boxes[i] if (edges|(1<<i))&bm==bm)
            moves.append((i,cl))
    moves.sort(key=lambda x:x[1],reverse=True)
    oa=alpha; bv=-10000 if maximizing else 10000
    for bit,cl in moves:
        ne=edges|(1<<bit)
        if maximizing:
            v=(cl+solve_tt(ne,depth-1,alpha,beta,True,tt)) if cl>0 else solve_tt(ne,depth-1,alpha,beta,False,tt)
            bv=max(bv,v); alpha=max(alpha,bv)
        else:
            v=(-cl+solve_tt(ne,depth-1,alpha,beta,False,tt)) if cl>0 else solve_tt(ne,depth-1,alpha,beta,True,tt)
            bv=min(bv,v); beta=min(beta,bv)
        if beta<=alpha: break
    tt[k]=(0 if bv>oa and bv<beta else (1 if bv>=beta else 2),bv)
    return bv

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

def scores_per_root_tt(edges):
    """TT fresca por jogada da raiz."""
    scores=np.full(31,-1e9,dtype=np.float32)
    for i in range(31):
        if not(edges&(1<<i)):
            tt={}  # TT FRESCA para cada jogada da raiz
            cl=sum(1 for bm in edge_boxes[i] if (edges|(1<<i))&bm==bm)
            ne=edges|(1<<i)
            r=(cl+solve_tt(ne,6,-10001,10001,True,tt)) if cl>0 else solve_tt(ne,6,-10001,10001,False,tt)
            scores[i]=float(r)
    return scores

def scores_no_tt(edges):
    """Sem TT."""
    scores=np.full(31,-1e9,dtype=np.float32)
    for i in range(31):
        if not(edges&(1<<i)):
            cl=sum(1 for bm in edge_boxes[i] if (edges|(1<<i))&bm==bm)
            ne=edges|(1<<i)
            r=(cl+solve_no_tt(ne,6,-10001,10001,True)) if cl>0 else solve_no_tt(ne,6,-10001,10001,False)
            scores[i]=float(r)
    return scores

# Testar
ARQUIVO = r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz"
d=np.load(ARQUIVO); estados=d["estados"]; qtd=d["qtd_tracos"]
np.random.seed(42)
cands=np.where(qtd>=10)[0]
indices=np.random.choice(cands,size=min(100,len(cands)),replace=False)

for nome, func in [("PER_ROOT_TT", scores_per_root_tt), ("NO_TT", scores_no_tt)]:
    div=0; t0=time.time()
    for idx in sorted(indices):
        mat=estados[idx]
        edges=0
        for r in range(9):
            for c in range(7):
                if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
                    if mat[r,c]==9: edges|=(1<<edge_to_bit[(r,c)])
        sc=func(edges)
        estado=EstadoTabuleiro(LINHAS,COLUNAS)
        for r in range(9):
            for c in range(7):
                v=int(mat[r,c])
                if v==9 or v==1: estado.matriz[r,c]=1
        so=_scores_de_todas_jogadas(estado,7)
        for i,lb in enumerate(LABELS):
            ov=so.get(lb,-1e9)
            if abs(sc[i]-ov)>0.01: div+=1; break
    dt=time.time()-t0
    print(f"{nome}: {100-div}/100 OK, {div} div, {dt:.1f}s")
d.close()

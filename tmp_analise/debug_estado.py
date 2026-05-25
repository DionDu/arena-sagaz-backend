import sys
sys.path.insert(0, '.')
import numpy as np
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

d = np.load("dados/profundidade_minimax_11_v7_adaptativo/dataset_pequeno_0066.npz", allow_pickle=False)
idx = 3569
smj  = d["score_melhor_jogada"][idx]
sj   = d["score_jogada"][idx]
dmj  = int(d["depth_melhor_jogada"][idx])
dj   = int(d["depth_jogada"][idx])
mj   = str(d["melhor_jogada"][idx])
labels = [str(s) for s in d["labels_canonicos"]]
qtd  = int(d["qtd_tracos"][idx])

avail_smj = [(labels[i], float(smj[i])) for i in range(31) if smj[i] > -1e8]
avail_sj  = [(labels[i], float( sj[i])) for i in range(31) if  sj[i] > -1e8]

print("=== Estado idx=%d ===" % idx)
print("depth_melhor_jogada=%d  depth_jogada=%d  qtd_tracos=%d" % (dmj, dj, qtd))
print("melhor_jogada=%r" % mj)
print("score_melhor_jogada == score_jogada? %s" % np.allclose(smj, sj))
print("n_avail smj=%d  sj=%d" % (len(avail_smj), len(avail_sj)))
print("score_melhor_jogada:", avail_smj[:8])
print("score_jogada:       ", avail_sj[:8])

M = d["estados"][idx]
print("\nMatriz crua (9x7):")
for r in range(9):
    print(" ", [int(M[r,c]) for c in range(7)])

# Reconstruir estado metodo 1 (meu script: 9->1)
e1 = EstadoTabuleiro(4, 3)
for r in range(9):
    for c in range(7):
        if int(M[r, c]) == 9:
            e1.matriz[r, c] = 1

# Reconstruir estado metodo 2 (calcular_scores_v7: mat.copy(), edges=9)
e2 = EstadoTabuleiro(4, 3)
e2.matriz = M.copy()

tracos1 = e1.tracos_disponiveis()
tracos2 = e2.tracos_disponiveis()
print("\nSame tracos? %s  (n=%d)" % (set(tracos1)==set(tracos2), len(tracos1)))

# Comparar com depth pequeno para ser rapido
DEPTH_FAST = 3
s1 = _scores_de_todas_jogadas(e1, DEPTH_FAST)
s2 = _scores_de_todas_jogadas(e2, DEPTH_FAST)
diffs = [(t, s1[t], s2[t]) for t in tracos1 if s1[t] != s2[t]]
print("Diffs metodo1 vs metodo2 (depth=%d): %d" % (DEPTH_FAST, len(diffs)))
for t, a, b in diffs[:5]:
    print("  %s: m1=%d m2=%d" % (t, a, b))

# Agora comparar metodo2 com NPZ
print("\nComparacao metodo2 vs NPZ score_melhor_jogada (depth=%d):" % DEPTH_FAST)
for t in sorted(tracos2)[:6]:
    i = labels.index(t)
    print("  %s: ref_d3=%s  npz_d%d=%.1f" % (t, s2[t], dmj, smj[i]))

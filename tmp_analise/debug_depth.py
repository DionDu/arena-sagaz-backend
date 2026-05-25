"""Verifica se score_melhor_jogada = scores de profundidade 6 ou 11."""
import sys
sys.path.insert(0, '.')
import numpy as np
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

d = np.load("dados/profundidade_minimax_11_v7_adaptativo/dataset_pequeno_0066.npz", allow_pickle=False)
idx = 3569
smj   = d["score_melhor_jogada"][idx]
dmj   = int(d["depth_melhor_jogada"][idx])
dj    = int(d["depth_jogada"][idx])
labels = [str(s) for s in d["labels_canonicos"]]

M = d["estados"][idx]
estado = EstadoTabuleiro(4, 3)
estado.matriz = M.copy()  # exatamente como calcular_scores_v7

tracos = estado.tracos_disponiveis()
print(f"depth_melhor_jogada={dmj}  depth_jogada={dj}  n_movs={len(tracos)}")

# Comparar depth=6 vs depth=11
import time
t0 = time.time()
s6 = _scores_de_todas_jogadas(estado, 6)
print(f"depth=6  ({time.time()-t0:.1f}s)")

t0 = time.time()
s11 = _scores_de_todas_jogadas(estado, 11)
print(f"depth=11 ({time.time()-t0:.1f}s)")

print("\nComparacao (label, npz, d6, d11):")
for t in sorted(tracos):
    i = labels.index(t)
    marker = ""
    if smj[i] != s6[t] and smj[i] != s11[t]:
        marker = " <-- NPZ DIFERE DE AMBOS"
    elif smj[i] == s6[t] and smj[i] != s11[t]:
        marker = " <-- NPZ = d6"
    elif smj[i] == s11[t] and smj[i] != s6[t]:
        marker = " <-- NPZ = d11"
    print(f"  {t:12s}: npz={smj[i]:6.1f}  d6={s6[t]:4d}  d11={s11[t]:4d}{marker}")

npz_eq_d6  = sum(1 for t in tracos if smj[labels.index(t)] == s6[t])
npz_eq_d11 = sum(1 for t in tracos if smj[labels.index(t)] == s11[t])
print(f"\nNPZ == d6:  {npz_eq_d6}/{len(tracos)}")
print(f"NPZ == d11: {npz_eq_d11}/{len(tracos)}")

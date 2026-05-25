"""Verifica sistematicamente: score_melhor_jogada == score_jogada nos NPZ?"""
import sys
sys.path.insert(0, '.')
import numpy as np
from pathlib import Path

DIR = Path("dados/profundidade_minimax_11_v7_adaptativo")

def e_original(p):
    n = p.stem
    return not (n.endswith('_refH') or n.endswith('_refV') or n.endswith('_r180'))

npzs = sorted(p for p in DIR.glob("*.npz") if e_original(p))

total_estados = 0
iguais = 0  # score_melhor_jogada == score_jogada
dj_counts = {}  # distribucao de depth_jogada

rng = np.random.default_rng(123)
amostra_erros = []

for p in npzs:
    d = np.load(p, allow_pickle=False)
    smj = d["score_melhor_jogada"]  # (N,31)
    sj  = d["score_jogada"]          # (N,31)
    dmj = d["depth_melhor_jogada"]   # (N,)
    dj  = d["depth_jogada"]          # (N,)

    N = smj.shape[0]
    total_estados += N
    for i in range(N):
        dep_mj = int(dmj[i])
        dep_j  = int(dj[i])
        dj_counts[dep_j] = dj_counts.get(dep_j, 0) + 1
        if np.allclose(smj[i], sj[i]):
            iguais += 1
        elif dep_mj >= 20 and len(amostra_erros) < 5:
            # Estado depth=20 onde smj != sj (esperado: Fase3 atualizou)
            amostra_erros.append((p.name, i, dep_mj, dep_j))

print(f"Total estados originais: {total_estados:,}")
print(f"score_melhor_jogada == score_jogada: {iguais:,} ({100*iguais/total_estados:.1f}%)")
print(f"  -- diferentes: {total_estados-iguais:,} ({100*(total_estados-iguais)/total_estados:.1f}%)")
print()
print("Distribuicao depth_jogada (Phase 1 adaptativa):")
for dep in sorted(dj_counts):
    print(f"  depth_jogada={dep:2d}: {dj_counts[dep]:8,d}")
print()
print("Exemplos depth=20 onde smj != sj (esperado):")
for nome, i, dmj, dj in amostra_erros[:5]:
    print(f"  {nome} idx={i} depth_melhor={dmj} depth_jogada={dj}")

"""Analise profunda e precisa da hipotese de convergência.

Hipótese do usuário: smj==sj em 55.3% dos estados é normal porque
no final de partida (poucos traços livres) qualquer profundidade
dá o mesmo score.

Este script verifica isso sistematicamente:
1. Distribui smj==sj e smj!=sj por qtd_tracos
2. Para estados smj==sj com qtd_tracos < 15 (muitos traços livres),
   verifica se depth=depth_jogada+1 já muda o score (convergência real = não muda)
"""
import sys
sys.path.insert(0, '.')
import numpy as np
from pathlib import Path
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

DIR = Path("dados/profundidade_minimax_11_v7_adaptativo")

def e_original(p):
    n = p.stem
    return not (n.endswith('_refH') or n.endswith('_refV') or n.endswith('_r180'))

def reconstruir(M):
    e = EstadoTabuleiro(4, 3)
    e.matriz = M.copy()   # igual ao calcular_scores_v7
    return e

# ---- Fase 1: Distribuição qtd_tracos por grupo ----
print("=== FASE 1: Distribuição qtd_tracos para smj==sj vs smj!=sj ===\n")

iguais_por_qt  = {}   # qtd_tracos -> count de smj==sj
dif_por_qt     = {}   # qtd_tracos -> count de smj!=sj

npzs = sorted(p for p in DIR.glob("*.npz") if e_original(p))
for p in npzs:
    d = np.load(p, allow_pickle=False)
    smj = d["score_melhor_jogada"]
    sj  = d["score_jogada"]
    qt  = d["qtd_tracos"]
    dmj = d["depth_melhor_jogada"]
    N = smj.shape[0]
    for i in range(N):
        q = int(qt[i])
        dep = int(dmj[i])
        igual = np.allclose(smj[i], sj[i])
        if dep == 11:  # apenas estados nao atualizados para 20
            if igual:
                iguais_por_qt[q] = iguais_por_qt.get(q, 0) + 1
            else:
                dif_por_qt[q]   = dif_por_qt.get(q, 0) + 1

todos_qt = sorted(set(list(iguais_por_qt.keys()) + list(dif_por_qt.keys())))
print(f"  {'qt':>4}  {'smj==sj':>9}  {'smj!=sj':>9}  {'%igual':>7}  {'livres':>6}")
print("  " + "-" * 50)
for qt in todos_qt:
    ig  = iguais_por_qt.get(qt, 0)
    dif = dif_por_qt.get(qt, 0)
    tot = ig + dif
    pct = 100*ig/tot if tot else 0
    livres = 31 - qt
    marker = " <-- SUSPEITO (muitos livres)" if livres > 11 and pct > 0 else ""
    print(f"  {qt:>4}  {ig:>9,d}  {dif:>9,d}  {pct:>6.1f}%  {livres:>6}{marker}")

# ---- Fase 2: Teste de convergência para estados suspeitos ----
print("\n=== FASE 2: Verificação de convergência em estados com muitos traços livres ===\n")
print("Para estados smj==sj com qtd_tracos <= 14 (>= 17 tracas livres):")
print("Computa depth=depth_jogada vs depth=depth_jogada+2. Se diferem = sem convergencia.\n")

rng = np.random.default_rng(99)
suspeitos = []
for p in npzs:
    d = np.load(p, allow_pickle=False)
    smj = d["score_melhor_jogada"]
    sj  = d["score_jogada"]
    qt  = d["qtd_tracos"]
    dj  = d["depth_jogada"]
    dmj = d["depth_melhor_jogada"]
    N = smj.shape[0]
    for i in range(N):
        q  = int(qt[i])
        dj_i = int(dj[i])
        dmj_i = int(dmj[i])
        if dmj_i == 11 and q <= 14 and np.allclose(smj[i], sj[i]):
            suspeitos.append((str(p), i, q, dj_i))
    if len(suspeitos) >= 200:
        break

rng.shuffle(suspeitos)
amostra = suspeitos[:10]
print(f"Total de estados suspeitos encontrados: {len(suspeitos):,}")
print(f"Testando {len(amostra)} amostras...\n")

import time
convergentes = 0
divergentes  = 0

for caminho, idx, qt, dj_val in amostra:
    d = np.load(caminho, allow_pickle=False)
    M    = d["estados"][idx]
    smj  = d["score_melhor_jogada"][idx]
    labels = [str(s) for s in d["labels_canonicos"]]
    label_to_idx = {l: i for i, l in enumerate(labels)}

    estado = reconstruir(M)
    tracos = estado.tracos_disponiveis()
    if not tracos:
        continue

    # Referencia em depth=dj_val (o mesmo que sj)
    t0 = time.time()
    ref_dj = _scores_de_todas_jogadas(estado, dj_val)
    # Referencia em depth=dj_val+2 (ligeiramente maior)
    ref_dj2 = _scores_de_todas_jogadas(estado, dj_val + 2)
    elapsed = time.time() - t0

    # Contar tracos onde dj e dj+2 diferem
    n_dif = sum(1 for t in tracos if ref_dj[t] != ref_dj2[t])
    converge_superficial = (n_dif == 0)

    # Verificar: smj bate com dj?
    smj_eq_dj = all(
        abs(float(smj[label_to_idx[t]]) - float(ref_dj[t])) < 0.01
        for t in tracos
    )

    status = "CONVERGENTE (dj=dj+2)" if converge_superficial else f"DIVERGENTE ({n_dif}/{len(tracos)} diferem)"
    fase2_ok = "smj==dj" if smj_eq_dj else "smj!=dj (?)"
    print(f"  {Path(caminho).name} idx={idx} qt={qt} dj={dj_val}  {status}  {fase2_ok}  ({elapsed:.1f}s)")

    if converge_superficial:
        convergentes += 1
    else:
        divergentes += 1

print(f"\nResultado: {convergentes} convergentes, {divergentes} divergentes de {len(amostra)} amostras")
print("Convergente = dj e dj+2 dão o mesmo score para todos os traços")
print("Se DIVERGENTE, Phase 2 com p=11 teria dado scores DIFERENTES dos atuais")

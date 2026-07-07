"""
Levantamento: quantos estados dos NPZs aumentados (refH/refV/r180)
ja existem exatamente nos 419 NPZs originais.
Resultado global e segmentado por qtd_tracos.
"""
import glob
import os
import sys
import time
from collections import defaultdict

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DIR_NPZ = os.path.join(ROOT, 'dados', 'profundidade_minimax_11_adaptativo')
SUFIXOS = ('_refH', '_refV', '_r180')

todos = sorted(glob.glob(os.path.join(DIR_NPZ, 'dataset_pequeno_*.npz')))
originais  = [f for f in todos if not any(os.path.splitext(os.path.basename(f))[0].endswith(s) for s in SUFIXOS)]
aumentados = [f for f in todos if     any(os.path.splitext(os.path.basename(f))[0].endswith(s) for s in SUFIXOS)]

print(f'Originais : {len(originais)}')
print(f'Aumentados: {len(aumentados)}')
print()

# ── 1. Indexar todos os estados originais ─────────────────────────────────────
print('Carregando estados originais...', flush=True)
t0 = time.time()

# set global e index por qtd_tracos
orig_global: set = set()
orig_por_tracos: dict[int, set] = defaultdict(set)

for arq in originais:
    dados = np.load(arq, allow_pickle=True)
    estados = dados['estados']           # (N, 9, 7) int8
    tracos  = dados['qtd_tracos'].astype(np.int32)
    for i in range(len(estados)):
        eb = estados[i].tobytes()
        orig_global.add(eb)
        orig_por_tracos[int(tracos[i])].add(eb)

n_orig_total = sum(len(s) for s in orig_por_tracos.values())
print(f'  Amostras originais carregadas : {n_orig_total:,}')
print(f'  Estados unicos nos originais  : {len(orig_global):,}')
print(f'  Tempo: {time.time()-t0:.1f}s')
print()

# ── 2. Verificar aumentados ────────────────────────────────────────────────────
print('Verificando aumentados...', flush=True)
t0 = time.time()

total_aug       = 0
dup_global      = 0
total_por_t: dict[int, int] = defaultdict(int)
dup_por_t:   dict[int, int] = defaultdict(int)

for arq in aumentados:
    dados = np.load(arq, allow_pickle=True)
    estados = dados['estados']
    tracos  = dados['qtd_tracos'].astype(np.int32)
    for i in range(len(estados)):
        eb = estados[i].tobytes()
        t  = int(tracos[i])
        total_aug += 1
        total_por_t[t] += 1
        if eb in orig_global:
            dup_global += 1
            dup_por_t[t] += 1

print(f'  Tempo: {time.time()-t0:.1f}s')
print()

# ── 3. Resultados ─────────────────────────────────────────────────────────────
print('=' * 65)
print(f'RESULTADO GLOBAL')
print(f'  Amostras aumentadas : {total_aug:,}')
print(f'  Já existiam orig.   : {dup_global:,}  ({dup_global/total_aug*100:.2f}%)')
print(f'  Novas (nao orig.)   : {total_aug - dup_global:,}  ({(total_aug-dup_global)/total_aug*100:.2f}%)')
print()
print('=' * 65)
print(f'{"Tracos":>7}  {"Aug total":>12}  {"Dup orig":>12}  {"% dup":>8}  {"% novo":>8}')
print('-' * 65)
for t in sorted(total_por_t.keys()):
    tot = total_por_t[t]
    dup = dup_por_t.get(t, 0)
    pct_dup  = dup / tot * 100 if tot else 0
    pct_novo = (tot - dup) / tot * 100 if tot else 0
    print(f'{t:>7}  {tot:>12,}  {dup:>12,}  {pct_dup:>7.1f}%  {pct_novo:>7.1f}%')
print('=' * 65)

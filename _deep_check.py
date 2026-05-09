import numpy as np, glob, os, sys, random
sys.path.insert(0, '.')
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, todos_labels_canonicos
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

labels = todos_labels_canonicos(4, 3)
label_to_idx = {l: i for i, l in enumerate(labels)}

# Recarrega o estado 2 do primeiro NPZ V5 consolidado
arq = sorted(glob.glob('dados/profundidade_minmax_9/*.npz'))[0]
print('Arquivo:', arq); sys.stdout.flush()
d = np.load(arq, allow_pickle=True)

i = 2
m = d['estados'][i]
s = d['scores'][i]
gm = d['generation_mode'][i]
rotulo = d['rotulos'][i]
n_arestas = int(((m[::2,1::2]==9).sum() + (m[1::2,::2]==9).sum()))
print(f'estado idx={i} gen_mode={gm} rotulo={rotulo} arestas_preenchidas={n_arestas}')
print('matriz:')
print(m); sys.stdout.flush()

print('Top 8 scores armazenados (NPZ):')
ord_npz = np.argsort(-s)[:8]
for j in ord_npz:
    print(f'   {labels[j]}: {s[j]:.4f}')
print(); sys.stdout.flush()

print('Recalculando Minimax(p=9) com minimax_pontinhos.py ...')
sys.stdout.flush()
st = EstadoTabuleiro.de_tamanho('pequeno')
st.matriz = m.copy().astype(np.int8)
sc = _scores_de_todas_jogadas(st, 9)
sc_sorted = sorted(sc.items(), key=lambda x: -x[1])
print('Top 8 scores recalculados:')
for lab, v in sc_sorted[:8]:
    print(f'   {lab}: {v:.4f}')
print(); sys.stdout.flush()

print('Comparacao item-a-item:')
print(f'   {"label":7s} {"NPZ":>10s} {"recalc":>10s} {"delta":>10s}')
for lab in sorted(sc.keys(), key=lambda l: -sc[l]):
    j = label_to_idx[lab]
    ds = s[j] - sc[lab]
    print(f'   {lab:7s} {s[j]:10.4f} {sc[lab]:10.4f} {ds:10.4f}')
sys.stdout.flush()

print()
print('=== Taxa de divergencia em amostragem maior ===')
sys.stdout.flush()

random.seed(42)
total = 0
divergentes = 0
det_divergentes = []
e_all = d['estados']
s_all = d['scores']
arestas_all = ((e_all[:, ::2, 1::2] == 9).sum(axis=(1,2)) + (e_all[:, 1::2, ::2] == 9).sum(axis=(1,2)))

# 30 estados aleatorios entre 12-22 tracos
indices = [k for k in range(len(e_all)) if 12 <= arestas_all[k] <= 22]
random.shuffle(indices)
for k in indices[:30]:
    m = e_all[k]
    s = s_all[k]
    st = EstadoTabuleiro.de_tamanho('pequeno')
    st.matriz = m.copy().astype(np.int8)
    sc = _scores_de_todas_jogadas(st, 9)
    if not sc:
        continue
    max_npz = s.max()
    topo_npz = sorted([labels[j] for j in range(31) if abs(s[j]-max_npz) < 1e-4])
    max_calc = max(sc.values())
    topo_calc = sorted([t for t,v in sc.items() if abs(v-max_calc) < 1e-9])
    total += 1
    if set(topo_npz) != set(topo_calc):
        divergentes += 1
        if len(det_divergentes) < 5:
            det_divergentes.append((k, int(arestas_all[k]), topo_npz, topo_calc, max_npz, max_calc))
    if total % 5 == 0:
        print(f'   parcial {total}/30 — div={divergentes}'); sys.stdout.flush()

print(f'Divergencias em estados V5 (12-22 tracos): {divergentes}/{total}')
for k, n, tn, tc, mn, mc in det_divergentes:
    print(f'   estado {k} ({n} tracos): NPZ_top={tn} (max={mn:.2f})  CALC_top={tc} (max={mc:.2f})')
sys.stdout.flush()

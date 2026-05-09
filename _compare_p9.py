"""Compara scores armazenados no NPZ (gerados com p=9) vs minimax_pontinhos.py em p=9.
Para ser justo desta vez: mesma profundidade nos dois lados.
"""
import numpy as np, glob, os, sys, random, time
sys.path.insert(0, '.')
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, todos_labels_canonicos
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

labels = todos_labels_canonicos(4, 3)
label_to_idx = {l: i for i, l in enumerate(labels)}

DEPTH = 9
N_PER_DATASET = 8  # p=9 e demorado; mais que isso vira teste eterno

def teste(nome, dir_npz, n_estados=N_PER_DATASET):
    print(f'\n=== {nome} | recalc p={DEPTH} (mesma profundidade que NPZ) ===')
    sys.stdout.flush()
    arq = sorted(glob.glob(os.path.join(dir_npz, '*.npz')))[0]
    d = np.load(arq, allow_pickle=True)
    e_all = d['estados']
    s_all = d['scores']
    arestas_all = ((e_all[:, ::2, 1::2] == 9).sum(axis=(1,2)) + (e_all[:, 1::2, ::2] == 9).sum(axis=(1,2)))

    # Pegar alguns estados de cada faixa para diversidade
    random.seed(42)
    estados_alvo = []
    for faixa_lo, faixa_hi in [(8, 12), (13, 17), (18, 22), (23, 26)]:
        cand = [k for k in range(len(e_all)) if faixa_lo <= arestas_all[k] <= faixa_hi]
        random.shuffle(cand)
        estados_alvo.extend(cand[:n_estados // 4 + 1])
    estados_alvo = estados_alvo[:n_estados]

    div_argmax = 0
    div_score = 0
    total = 0
    detalhes = []

    for k in estados_alvo:
        m = e_all[k]
        s = s_all[k]
        st = EstadoTabuleiro.de_tamanho('pequeno')
        st.matriz = m.copy().astype(np.int8)

        t0 = time.time()
        try:
            sc_calc = _scores_de_todas_jogadas(st, DEPTH)
        except Exception as ex:
            print(f'   estado {k}: erro {ex}')
            continue
        elapsed = time.time() - t0
        if not sc_calc:
            continue

        max_npz = s.max()
        topo_npz = sorted([labels[j] for j in range(31) if abs(s[j]-max_npz) < 1e-4])
        max_calc = max(sc_calc.values())
        topo_calc = sorted([t for t,v in sc_calc.items() if abs(v-max_calc) < 1e-9])

        score_top_recalc = sc_calc.get(topo_npz[0], None) if topo_npz else None

        total += 1
        argmax_div = (set(topo_npz) != set(topo_calc))
        score_div = score_top_recalc is None or abs(max_npz - score_top_recalc) > 0.5

        if argmax_div: div_argmax += 1
        if score_div: div_score += 1

        marker = ''
        if argmax_div: marker += ' ARGMAX_DIFF'
        elif score_div: marker += ' SCORE_DIFF'
        else: marker += ' OK'

        print(f'   [{total}/{len(estados_alvo)}] estado {k} ({int(arestas_all[k])} traços, t={elapsed:.1f}s):{marker}')
        print(f'         NPZ_top={topo_npz} score={max_npz:.1f}')
        print(f'         CALC_top={topo_calc} score_top_NPZ_no_recalc={score_top_recalc}')
        sys.stdout.flush()

        if argmax_div and len(detalhes) < 5:
            detalhes.append((k, int(arestas_all[k]), topo_npz, topo_calc, max_npz, score_top_recalc))

    print(f'\n  RESULTADO {nome}:')
    print(f'    argmax_divergente = {div_argmax}/{total} ({100*div_argmax/total:.1f}%)')
    print(f'    score_divergente  = {div_score}/{total} ({100*div_score/total:.1f}%)')
    sys.stdout.flush()
    return div_argmax, div_score, total

teste('V4_legado', 'dados/profundidade_minmax_9_desbalanceado')
teste('V5_consolidado', 'dados/profundidade_minmax_9')

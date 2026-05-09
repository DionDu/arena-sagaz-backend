import numpy as np, glob, os, sys, random
sys.path.insert(0, '.')
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, todos_labels_canonicos
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

labels = todos_labels_canonicos(4, 3)
label_to_idx = {l: i for i, l in enumerate(labels)}

# Para acelerar, usar profundidade=7 (que ainda eh forte) — se houver divergencia
# ja eh sintoma forte. p=9 demora demais.
DEPTH = 7

def teste(nome, dir_npz, n_estados=20):
    print(f'\n=== {nome} ({dir_npz}) | testando p={DEPTH} contra minimax_pontinhos.py ===')
    sys.stdout.flush()
    arq = sorted(glob.glob(os.path.join(dir_npz, '*.npz')))[0]
    d = np.load(arq, allow_pickle=True)
    e_all = d['estados']
    s_all = d['scores']
    arestas_all = ((e_all[:, ::2, 1::2] == 9).sum(axis=(1,2)) + (e_all[:, 1::2, ::2] == 9).sum(axis=(1,2)))

    random.seed(42)
    indices = [k for k in range(len(e_all)) if 12 <= arestas_all[k] <= 22]
    random.shuffle(indices)
    indices = indices[:n_estados]

    total = 0
    div_argmax = 0
    div_score = 0
    detalhes = []

    for k in indices:
        m = e_all[k]
        s = s_all[k]
        st = EstadoTabuleiro.de_tamanho('pequeno')
        st.matriz = m.copy().astype(np.int8)
        try:
            sc_calc = _scores_de_todas_jogadas(st, DEPTH)
        except Exception as ex:
            print(f'   estado {k}: erro {ex}')
            continue
        if not sc_calc:
            continue

        max_npz = s.max()
        topo_npz = sorted([labels[j] for j in range(31) if abs(s[j]-max_npz) < 1e-4])
        max_calc = max(sc_calc.values())
        topo_calc = sorted([t for t,v in sc_calc.items() if abs(v-max_calc) < 1e-9])

        # Tambem comparar score do top NPZ com recalculo
        score_top_npz = max_npz
        score_top_npz_no_recalc = sc_calc.get(topo_npz[0], None) if topo_npz else None

        total += 1
        argmax_div = (set(topo_npz) != set(topo_calc))
        score_div = score_top_npz_no_recalc is None or abs(score_top_npz - score_top_npz_no_recalc) > 0.5

        if argmax_div: div_argmax += 1
        if score_div: div_score += 1

        if (argmax_div or score_div) and len(detalhes) < 4:
            detalhes.append((k, int(arestas_all[k]), topo_npz, topo_calc,
                             score_top_npz, score_top_npz_no_recalc))

        if total % 5 == 0:
            print(f'   {total}/{n_estados}: argmax_div={div_argmax}, score_div={div_score}')
            sys.stdout.flush()

    print(f'\n  RESULTADO {nome}: argmax_div={div_argmax}/{total} ({100*div_argmax/total:.1f}%), score_div={div_score}/{total} ({100*div_score/total:.1f}%)')
    for k, n, tn, tc, sn, sc in detalhes:
        print(f'    estado {k} ({n} tracos): NPZ_top={tn} score_NPZ={sn:.1f} | CALC_top={tc} score_NPZ_no_recalc={sc:.1f}')
    sys.stdout.flush()
    return div_argmax, div_score, total

# Testar V4 e V5
teste('V4_legado (344k, sem balanceamento)', 'dados/profundidade_minmax_9_desbalanceado', n_estados=20)
teste('V5_consolidado (500k, balanceado)', 'dados/profundidade_minmax_9', n_estados=20)

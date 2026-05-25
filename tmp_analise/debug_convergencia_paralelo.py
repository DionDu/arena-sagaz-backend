"""Teste decisivo paralelo: smj vs p=7 e p=11 — ProcessPoolExecutor 14 workers.
Windows exige if __name__ == '__main__' para multiprocessing (spawn, nao fork).
"""
import sys
sys.path.insert(0, '.')
import numpy as np
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import time

DIR = Path("dados/profundidade_minimax_11_v7_adaptativo")
N_WORKERS = 14


def _worker_score(args):
    """Top-level (picklavel): calcula _scores_de_todas_jogadas para estado+profundidade."""
    import sys
    sys.path.insert(0, '.')
    import numpy as np
    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
    from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas
    M_flat, shape, depth = args
    M = np.frombuffer(M_flat, dtype=np.int8).reshape(shape)
    estado = EstadoTabuleiro(4, 3)
    estado.matriz = M.copy()
    ref = _scores_de_todas_jogadas(estado, depth)
    tracos = estado.tracos_disponiveis()
    return depth, ref, tracos


def e_original(p):
    n = p.stem
    return not (n.endswith('_refH') or n.endswith('_refV') or n.endswith('_r180'))


def score_bate(smj_vetor, ref_dict, labels):
    label_to_idx = {l: i for i, l in enumerate(labels)}
    for t, v in ref_dict.items():
        i = label_to_idx.get(t)
        if i is None:
            continue
        if abs(float(smj_vetor[i]) - float(v)) > 0.01:
            return False
    return True


if __name__ == '__main__':
    # =========================================================
    # Parte 1: Estado específico, depths 6-11 em PARALELO
    # =========================================================
    print("=== ESTADO ESPECIFICO (dataset_pequeno_0066.npz idx=3569) ===", flush=True)
    d = np.load(str(DIR / "dataset_pequeno_0066.npz"), allow_pickle=False)
    IDX = 3569
    M0 = d["estados"][IDX]
    smj0 = d["score_melhor_jogada"][IDX]
    labels0 = [str(s) for s in d["labels_canonicos"]]
    dj0  = int(d["depth_jogada"][IDX])
    dmj0 = int(d["depth_melhor_jogada"][IDX])
    qt0  = int(d["qtd_tracos"][IDX])

    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
    e_tmp = EstadoTabuleiro(4, 3)
    e_tmp.matriz = M0.copy()
    n_movs = len(e_tmp.tracos_disponiveis())
    print(f"qtd_tracos={qt0} dj={dj0} dmj={dmj0} movs={n_movs}", flush=True)

    depths_p1 = [6, 7, 8, 9, 10, 11]
    M0_flat  = M0.tobytes()
    M0_shape = M0.shape
    results_p1 = {}

    t0 = time.time()
    with ProcessPoolExecutor(max_workers=len(depths_p1)) as ex:
        futs = {ex.submit(_worker_score, (M0_flat, M0_shape, dep)): dep for dep in depths_p1}
        for fut in as_completed(futs):
            dep, ref, tracos = fut.result()
            lbl_idx = {l: i for i, l in enumerate(labels0)}
            difs = [t for t in tracos if abs(float(smj0[lbl_idx[t]]) - float(ref[t])) > 0.01]
            bate = len(difs) == 0
            results_p1[dep] = (bate, difs, ref, tracos)
            print(f"  p={dep:2d}: smj_bate? {'SIM' if bate else 'NAO':3s}  diffs={len(difs):2d}/{len(tracos)}", flush=True)

    print(f"Parte 1 concluida em {time.time()-t0:.1f}s", flush=True)
    for dep in sorted(results_p1):
        bate, difs, ref, tracos = results_p1[dep]
        if not bate:
            lbl_idx = {l: i for i, l in enumerate(labels0)}
            for t in difs[:5]:
                print(f"    p={dep} {t}: npz={float(smj0[lbl_idx[t]]):.0f} ref={float(ref[t]):.0f}", flush=True)

    # =========================================================
    # Parte 2: 8 amostras smj==sj + scores nao-zero, p=7 e p=11
    # =========================================================
    print("\n=== AMOSTRA: smj==sj, qt=9-12, dmj=11, scores NAO-ZERO ===", flush=True)

    rng = np.random.default_rng(77)
    candidatos = []
    npzs = sorted(p for p in DIR.glob("*.npz") if e_original(p))
    for p in npzs[:10]:
        d2 = np.load(p, allow_pickle=False)
        smj_all = d2["score_melhor_jogada"]
        sj_all  = d2["score_jogada"]
        qt_all  = d2["qtd_tracos"]
        dmj_all = d2["depth_melhor_jogada"]
        labs    = [str(s) for s in d2["labels_canonicos"]]
        N = smj_all.shape[0]
        for i in range(N):
            qt  = int(qt_all[i])
            dmj = int(dmj_all[i])
            if not (9 <= qt <= 12 and dmj == 11):
                continue
            if not np.allclose(smj_all[i], sj_all[i]):
                continue
            avail = [float(smj_all[i][j]) for j in range(len(labs)) if smj_all[i][j] > -1e8]
            if avail and any(abs(v) > 0.01 for v in avail):
                candidatos.append((str(p), i, qt, int(d2["depth_jogada"][i])))

    rng.shuffle(candidatos)
    amostra = candidatos[:8]
    print(f"Candidatos: {len(candidatos)}  Testando: {len(amostra)}", flush=True)

    # Coletar matrizes para as amostras
    amostra_data = {}
    for caminho, idx2, qt, dj_val in amostra:
        d3 = np.load(caminho, allow_pickle=False)
        M2 = d3["estados"][idx2]
        amostra_data[(caminho, idx2)] = {
            "M_flat": M2.tobytes(), "shape": M2.shape,
            "smj": d3["score_melhor_jogada"][idx2].copy(),
            "labels": [str(s) for s in d3["labels_canonicos"]],
            "qt": qt, "dj": dj_val,
        }

    # Submeter 16 tarefas (8 estados x 2 depths) de uma vez
    tasks_p2 = []
    for caminho, idx2, qt, dj_val in amostra:
        info = amostra_data[(caminho, idx2)]
        for dep in [7, 11]:
            tasks_p2.append((caminho, idx2, dep, info["M_flat"], info["shape"]))

    print(f"Submetendo {len(tasks_p2)} tarefas com {N_WORKERS} workers...\n", flush=True)
    resultados = {}
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=N_WORKERS) as ex:
        futs2 = {}
        for caminho, idx2, dep, M_flat, shape in tasks_p2:
            fut = ex.submit(_worker_score, (M_flat, shape, dep))
            futs2[fut] = (caminho, idx2, dep)
        for fut in as_completed(futs2):
            caminho, idx2, dep = futs2[fut]
            _, ref, tracos = fut.result()
            resultados[(caminho, idx2, dep)] = (ref, tracos)
            print(f"  OK: {Path(caminho).name} idx={idx2} p={dep}", flush=True)

    print(f"\nTodas as tarefas concluidas em {time.time()-t0:.1f}s\n", flush=True)

    # Consolidar resultados
    p7_ok = 0; p11_ok = 0
    for caminho, idx2, qt, dj_val in amostra:
        info = amostra_data[(caminho, idx2)]
        smj2    = info["smj"]
        labels2 = info["labels"]
        lbl_idx2 = {l: i for i, l in enumerate(labels2)}

        ref7,  tr7  = resultados.get((caminho, idx2, 7),  ({}, []))
        ref11, tr11 = resultados.get((caminho, idx2, 11), ({}, []))

        bate7  = score_bate(smj2, ref7,  labels2)
        bate11 = score_bate(smj2, ref11, labels2)
        if bate7:  p7_ok  += 1
        if bate11: p11_ok += 1

        avail_nz = [
            (t, float(smj2[lbl_idx2[t]]), float(ref7.get(t, 0)), float(ref11.get(t, 0)))
            for t in tr7 if abs(float(smj2[lbl_idx2[t]])) > 0.01
        ]
        print(f"  {Path(caminho).name} idx={idx2} qt={qt} dj={dj_val}")
        print(f"    smj==p7? {'SIM' if bate7 else 'NAO'}  smj==p11? {'SIM' if bate11 else 'NAO'}")
        for t, s_npz, s7, s11 in avail_nz[:4]:
            print(f"    {t}: npz={s_npz:.0f}  p7={s7:.0f}  p11={s11:.0f}")

    print(f"\nSUMARIO: smj==p7 em {p7_ok}/{len(amostra)}, smj==p11 em {p11_ok}/{len(amostra)}", flush=True)
    print("Se smj==p7 >> smj==p11 -> dados sao de p=7, NAO de p=11")
    print("Se smj==p11 em todos  -> dados sao corretos em p=11 (convergencia)")

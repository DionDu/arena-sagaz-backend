"""Verificação dos NPZ recém-gerados pelo Databricks (fase3_rerotulacao).

Compara score_melhor_jogada e melhor_jogada contra o Minimax Python de referência
(_scores_de_todas_jogadas) nos dois arquivos presentes em dados/profundidade_minimax_11_adaptativo/.

Testa:
  - Estados com depth_melhor_jogada=11  (~25 amostras por arquivo)
  - Estados com depth_melhor_jogada=20  (~5 amostras por arquivo, arestas_livres <= 15)

Usa ProcessPoolExecutor(14 workers) para paralelismo.
Windows: requer if __name__ == '__main__' (spawn, não fork).
"""
import sys
sys.path.insert(0, '.')
import numpy as np
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import time

DIR = Path("dados/profundidade_minimax_11_adaptativo")
N_WORKERS = 14
TOLERANCIA = 0.05  # diferença máxima tolerável nos scores


def _worker_score(args):
    """Top-level picklável: calcula _scores_de_todas_jogadas para um estado+profundidade."""
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


def verificar_arquivo(path, n_p11=25, n_p20=5, seed=42):
    """Retorna dict com amostras a verificar."""
    rng = np.random.default_rng(seed)
    d = np.load(path, allow_pickle=False)

    dmj   = d["depth_melhor_jogada"].astype(np.int32)
    qt    = d["qtd_tracos"].astype(np.int32)
    smj   = d["score_melhor_jogada"]
    mj    = d["melhor_jogada"]
    labs  = [str(s) for s in d["labels_canonicos"]]
    ests  = d["estados"]

    amostras = []

    # Amostras p=11
    idx_p11 = np.where(dmj == 11)[0]
    pick11 = rng.choice(idx_p11, size=min(n_p11, len(idx_p11)), replace=False)
    for i in pick11:
        amostras.append((str(path), int(i), int(dmj[i]), ests[i].tobytes(), ests[i].shape,
                         smj[i].copy(), mj[i], labs))

    # Amostras p=20 com arestas_livres <= 15 (mais rápidas de verificar)
    idx_p20 = np.where((dmj == 20) & (qt >= 16))[0]  # arestas_livres = 31-qt <= 15
    if len(idx_p20) > 0:
        pick20 = rng.choice(idx_p20, size=min(n_p20, len(idx_p20)), replace=False)
        for i in pick20:
            amostras.append((str(path), int(i), int(dmj[i]), ests[i].tobytes(), ests[i].shape,
                             smj[i].copy(), mj[i], labs))

    print(f"  {path.name}: {len(idx_p11)} estados p=11, {len(idx_p20)} estados p=20 (arestas<=15)")
    print(f"    Amostras selecionadas: {len(pick11)} p=11, "
          f"{min(n_p20, len(idx_p20)) if len(idx_p20) > 0 else 0} p=20")
    return amostras


def score_bate(smj_npz, ref_dict, labels):
    label_to_idx = {l: i for i, l in enumerate(labels)}
    diffs = []
    for t, v in ref_dict.items():
        i = label_to_idx.get(t)
        if i is None:
            continue
        if abs(float(smj_npz[i]) - float(v)) > TOLERANCIA:
            diffs.append((t, float(smj_npz[i]), float(v)))
    return len(diffs) == 0, diffs


if __name__ == "__main__":
    npzs = sorted(DIR.glob("dataset_pequeno_*.npz"))
    print(f"Arquivos encontrados: {[p.name for p in npzs]}")
    print()

    # ── Coleta amostras dos dois arquivos ────────────────────────────────────
    print("=== COLETA DE AMOSTRAS ===")
    todas_amostras = []
    for i, p in enumerate(npzs):
        todas_amostras.extend(verificar_arquivo(p, n_p11=25, n_p20=5, seed=42 + i))

    n_p11_total = sum(1 for a in todas_amostras if a[2] == 11)
    n_p20_total = sum(1 for a in todas_amostras if a[2] == 20)
    print(f"\nTotal de tarefas: {len(todas_amostras)} "
          f"({n_p11_total} p=11, {n_p20_total} p=20)")

    # ── Execução paralela ────────────────────────────────────────────────────
    print(f"\n=== VERIFICAÇÃO PARALELA ({N_WORKERS} workers) ===")
    resultados = {}
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=N_WORKERS) as ex:
        futs = {}
        for cam, idx, dep, M_flat, shape, smj, mj, labs in todas_amostras:
            fut = ex.submit(_worker_score, (M_flat, shape, dep))
            futs[fut] = (cam, idx, dep, smj, mj, labs)

        for fut in as_completed(futs):
            cam, idx, dep, smj, mj, labs = futs[fut]
            try:
                _, ref, tracos = fut.result()
                bate, diffs = score_bate(smj, ref, labs)
                resultados[(cam, idx, dep)] = (bate, diffs, ref, tracos, mj, labs)
                status = "OK" if bate else f"FALHA ({len(diffs)} diffs)"
                print(f"  [{status}] {Path(cam).name} idx={idx} p={dep} "
                      f"({31 - sum(1 for v in smj if v < -1e8)} movs disponíveis)")
            except Exception as e:
                resultados[(cam, idx, dep)] = (False, [str(e)], {}, [], mj, labs)
                print(f"  [ERRO] {Path(cam).name} idx={idx} p={dep}: {e}")

    print(f"\nTempo total: {time.time() - t0:.1f}s")

    # ── Relatório por profundidade ───────────────────────────────────────────
    print("\n=== RELATÓRIO FINAL ===")
    ok11 = falha11 = ok20 = falha20 = 0

    for (cam, idx, dep), (bate, diffs, ref, tracos, mj_npz, labs) in sorted(resultados.items()):
        if dep == 11:
            if bate:
                ok11 += 1
            else:
                falha11 += 1
                print(f"\n  FALHA p=11: {Path(cam).name} idx={idx}")
                for t, s_npz, s_ref in diffs[:4]:
                    print(f"    {t}: npz={s_npz:.1f}  ref={s_ref:.1f}")
        else:
            if bate:
                ok20 += 1
            else:
                falha20 += 1
                print(f"\n  FALHA p=20: {Path(cam).name} idx={idx}")
                for t, s_npz, s_ref in diffs[:4]:
                    print(f"    {t}: npz={s_npz:.1f}  ref={s_ref:.1f}")

    print(f"\n  p=11: {ok11} OK / {falha11} FALHA  (de {ok11+falha11})")
    print(f"  p=20: {ok20} OK / {falha20} FALHA  (de {ok20+falha20})")

    # ── Verifica melhor_jogada vs argmax ─────────────────────────────────────
    print("\n=== CONSISTÊNCIA melhor_jogada vs argmax(score_melhor_jogada) ===")
    mj_incon = 0
    for (cam, idx, dep), (bate, diffs, ref, tracos, mj_npz, labs) in resultados.items():
        d = np.load(cam, allow_pickle=False)
        smj_row = d["score_melhor_jogada"][idx]
        validos = [i for i, v in enumerate(smj_row) if v > -1e8]
        if not validos:
            continue
        max_s = max(smj_row[i] for i in validos)
        candidatos = [labs[i] for i in validos if smj_row[i] == max_s]
        if str(mj_npz) not in candidatos:
            print(f"  INCONS {Path(cam).name} idx={idx}: mj='{mj_npz}' mas argmax={candidatos}")
            mj_incon += 1
    if mj_incon == 0:
        print("  Todas as melhor_jogada batem com o argmax dos scores — OK")
    else:
        print(f"  {mj_incon} inconsistências encontradas")

    total_ok = ok11 + ok20
    total_falha = falha11 + falha20
    total = total_ok + total_falha
    print(f"\n{'PASSOU' if total_falha == 0 else 'FALHOU'}: {total_ok}/{total} verificações corretas")

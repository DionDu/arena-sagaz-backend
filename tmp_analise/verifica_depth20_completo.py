"""Verificação definitiva para estados com depth_melhor_jogada=20.

Estratégia tri-verificada:
  A = score_melhor_jogada do NPZ (Databricks, depth=20)
  B = _scores_de_todas_jogadas(estado, arestas_livres)  — ground-truth: jogo completo
  C = _scores_de_todas_jogadas(estado, 11)              — truncado: prova que depth=11 daria errado

Se A ≈ B  →  Databricks está correto para depth=20.
Se A ≠ C  →  depth=11 seria insuficiente (confirma que usar depth>11 importa).

Usa estados com depth=20 e arestas_livres=17 (máximo no dataset, estrutural:
estados com 20+ arestas livres não formam cadeias longas suficientes para prof_min>11).
"""
import sys
sys.path.insert(0, '.')
import numpy as np
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import time

DIR = Path("dados/profundidade_minimax_11_adaptativo")
N_WORKERS = 6  # 3 estados × 2 profundidades = 6 tarefas


def _worker_score(args):
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
    return depth, ref


if __name__ == "__main__":
    # ── Coleta os estados com depth=20 e arestas_livres=17 (máximo disponível) ──
    amostras = []
    for p in sorted(DIR.glob("dataset_pequeno_*.npz")):
        d = np.load(p, allow_pickle=False)
        dmj   = d["depth_melhor_jogada"].astype(np.int32)
        qt    = d["qtd_tracos"].astype(np.int32)
        livres = 31 - qt
        idxs = np.where((dmj == 20) & (livres == 17))[0]
        for i in idxs:
            amostras.append({
                "arquivo": str(p),
                "idx": int(i),
                "livres": int(livres[i]),
                "M_flat": d["estados"][i].tobytes(),
                "shape": d["estados"][i].shape,
                "smj_npz": d["score_melhor_jogada"][i].copy(),
                "mj_npz": str(d["melhor_jogada"][i]),
                "labels": [str(s) for s in d["labels_canonicos"]],
            })

    if not amostras:
        print("ATENÇÃO: Nenhum estado com depth=20 e arestas_livres=17 encontrado.")
        print("O dataset nos 2 NPZs disponíveis tem depth=20 apenas com 12-17 arestas livres.")
        sys.exit(0)

    print(f"Estados encontrados: {len(amostras)} com depth=20 e exatamente 17 arestas livres")
    for a in amostras:
        print(f"  {Path(a['arquivo']).name} idx={a['idx']}: {a['livres']} arestas livres")

    # ── Submete: cada estado × 2 profundidades (17 e 11) ────────────────────────
    tasks = []
    for a in amostras:
        for dep in [17, 11]:
            tasks.append((a["arquivo"], a["idx"], dep, a["M_flat"], a["shape"]))

    print(f"\nSubmetendo {len(tasks)} tarefas ({N_WORKERS} workers)...")
    print("AVISO: profundidade=17 com 17 movimentos restantes pode levar vários minutos.")
    print()

    resultados = {}
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=N_WORKERS) as ex:
        futs = {
            ex.submit(_worker_score, (M_flat, shape, dep)): (cam, idx, dep)
            for cam, idx, dep, M_flat, shape in tasks
        }
        for fut in as_completed(futs):
            cam, idx, dep = futs[fut]
            try:
                depth, ref = fut.result()
                resultados[(cam, idx, dep)] = ref
                print(f"  OK: {Path(cam).name} idx={idx} p={dep} "
                      f"({time.time()-t0:.0f}s decorridos)", flush=True)
            except Exception as e:
                resultados[(cam, idx, dep)] = None
                print(f"  ERRO: {Path(cam).name} idx={idx} p={dep}: {e}", flush=True)

    print(f"\nTodas as tarefas concluídas em {time.time()-t0:.1f}s")

    # ── Relatório tri-verificado ─────────────────────────────────────────────────
    print("\n" + "="*70)
    print("RELATÓRIO TRI-VERIFICADO (A=Databricks/p=20, B=ref/p=17, C=ref/p=11)")
    print("="*70)

    TOLERANCIA = 0.05
    for a in amostras:
        cam   = a["arquivo"]
        idx   = a["idx"]
        smj   = a["smj_npz"]
        mj    = a["mj_npz"]
        labs  = a["labels"]
        lbl_i = {l: i for i, l in enumerate(labs)}

        ref17 = resultados.get((cam, idx, 17))
        ref11 = resultados.get((cam, idx, 11))

        print(f"\n{'-'*60}")
        print(f"Arquivo: {Path(cam).name}  idx={idx}  arestas_livres={a['livres']}")
        print(f"melhor_jogada NPZ (A): '{mj}'")

        # Traços disponíveis (score > -1e8 no NPZ)
        disponiveis = [l for l in labs if smj[lbl_i[l]] > -1e8]
        print(f"Traços disponíveis: {len(disponiveis)}")

        if ref17 is None or ref11 is None:
            print("  ERRO: alguma referência não computou.")
            continue

        # Cabeçalho da tabela
        print(f"\n{'Traco':<8} {'A (npz/p=20)':>13} {'B (ref/p=17)':>13} "
              f"{'C (ref/p=11)':>13} {'A=B':>5} {'A!=C':>6}")
        print("-" * 59)

        a_eq_b_count = 0
        a_neq_c_count = 0
        total = 0

        for t in disponiveis:
            i = lbl_i[t]
            a_val = float(smj[i])
            b_val = float(ref17.get(t, float('nan')))
            c_val = float(ref11.get(t, float('nan')))
            a_eq_b = abs(a_val - b_val) <= TOLERANCIA if not np.isnan(b_val) else False
            a_neq_c = abs(a_val - c_val) > TOLERANCIA if not np.isnan(c_val) else True
            a_eq_b_count += int(a_eq_b)
            a_neq_c_count += int(a_neq_c)
            total += 1
            marker = "" if a_eq_b else " ← DIFF"
            print(f"{t:<8} {a_val:>13.1f} {b_val:>13.1f} {c_val:>13.1f} "
                  f"{'SIM':>5} {'SIM' if a_neq_c else 'NAO':>6}{marker}")

        print()
        print(f"A=B  (Databricks correto): {a_eq_b_count}/{total}")
        print(f"A!=C (depth>11 importa) : {a_neq_c_count}/{total}")

        # Melhor jogada segundo cada fonte
        if ref17:
            max17 = max(ref17.values())
            mj_b = [t for t, v in ref17.items() if v == max17]
        else:
            mj_b = ["?"]
        if ref11:
            max11 = max(ref11.values())
            mj_c = [t for t, v in ref11.items() if v == max11]
        else:
            mj_c = ["?"]

        print(f"\nMelhor jogada  A(npz)='{mj}'  B(p=17)={mj_b}  C(p=11)={mj_c}")
        if mj in mj_b:
            print("  => melhor_jogada correta (A bate B)")
        else:
            print(f"  => DISCORDANCIA: NPZ diz '{mj}', referencia p=17 diz {mj_b}")

    print("\n" + "="*70)

"""Valida score_melhor_jogada dos NPZs contra Minimax de referencia.

Para cada nivel de profundidade (11-20), amostra N_POR_DEPTH estados e
verifica se os scores gravados batem com _scores_de_todas_jogadas() do
minimax_pontinhos.py.

Paralelizado com ProcessPoolExecutor (Ryzen 7 5700X — 8c/16t).

Uso:
    .venv\Scripts\python -u tmp_analise\validar_scores_minimax.py
"""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

DIR_NPZ = Path("dados/profundidade_minimax_11_v7_adaptativo")
N_POR_DEPTH = 5
SEED = 42
TOLERANCIA = 1e-4
N_WORKERS = min(14, os.cpu_count() or 8)   # deixa 2 threads livres

# ---------------------------------------------------------------------------
# Necessario para pickling no multiprocessing (top-level)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent.parent))


def _e_original(nome: str) -> bool:
    return not (nome.endswith('_refH') or nome.endswith('_refV') or nome.endswith('_r180'))


def _reconstruir_estado(M: np.ndarray):
    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
    estado = EstadoTabuleiro(4, 3)
    for r in range(9):
        for c in range(7):
            if int(M[r, c]) == 9:
                estado.matriz[r, c] = 1
    return estado


def _validar_um(task: tuple) -> dict:
    """Worker executado em processo separado. Retorna dict com resultado."""
    num, dep, caminho_str, idx = task
    caminho = Path(caminho_str)

    from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

    t_ini = time.time()

    d = np.load(caminho, allow_pickle=False)
    M = d['estados'][idx]
    depth = int(d['depth_melhor_jogada'][idx])
    mj_npz = str(d['melhor_jogada'][idx])
    scores_npz = d['score_melhor_jogada'][idx]
    labels = [str(s) for s in d['labels_canonicos']]
    label_to_idx = {lbl: i for i, lbl in enumerate(labels)}

    estado = _reconstruir_estado(M)
    tracos = estado.tracos_disponiveis()

    if not tracos:
        return {
            'num': num, 'dep': dep, 'arquivo': caminho.name, 'idx': idx,
            'n_tracos': 0, 'erros': [], 'terminal': True,
            'elapsed': time.time() - t_ini,
        }

    ref_scores = _scores_de_todas_jogadas(estado, depth)

    erros: list[str] = []

    for traco in tracos:
        idx_label = label_to_idx.get(traco)
        if idx_label is None:
            erros.append(f"label '{traco}' nao em labels_canonicos")
            continue
        s_npz = float(scores_npz[idx_label])
        s_ref = float(ref_scores[traco])
        if abs(s_npz - s_ref) > TOLERANCIA:
            erros.append(f"'{traco}': npz={s_npz:.4f} ref={s_ref} (diff={abs(s_npz-s_ref):.4f})")

    if mj_npz:
        mj_ref_max = max(ref_scores.values())
        mj_npz_score = ref_scores.get(mj_npz)
        if mj_npz_score is None:
            erros.append(f"melhor_jogada='{mj_npz}' nao disponivel no estado")
        elif abs(float(mj_npz_score) - float(mj_ref_max)) > TOLERANCIA:
            erros.append(f"melhor_jogada='{mj_npz}' score={mj_npz_score} mas max={mj_ref_max}")

    return {
        'num': num, 'dep': dep, 'arquivo': caminho.name, 'idx': idx,
        'n_tracos': len(tracos), 'erros': erros, 'terminal': False,
        'elapsed': time.time() - t_ini,
    }


# ---------------------------------------------------------------------------
# Indexacao
# ---------------------------------------------------------------------------

def separar_por_depth(dir_npz: Path) -> dict[int, list[tuple[str, int]]]:
    index: dict[int, list[tuple[str, int]]] = {d: [] for d in range(11, 21)}
    npzs = sorted(p for p in dir_npz.glob("*.npz") if _e_original(p.stem))
    total = len(npzs)
    print(f"  Indexando {total} NPZ originais...", flush=True)
    for i, p in enumerate(npzs):
        d = np.load(p, allow_pickle=False)
        for idx, dep in enumerate(d['depth_melhor_jogada']):
            dep_int = int(dep)
            if 11 <= dep_int <= 20:
                index[dep_int].append((str(p), idx))
        if (i + 1) % 30 == 0 or i == total - 1:
            print(f"    {i + 1}/{total} NPZ indexados...", flush=True)
    return index


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def validar() -> None:
    rng = np.random.default_rng(SEED)
    t0 = time.time()

    print("=" * 72)
    print("VALIDAÇÃO: score_melhor_jogada vs Minimax de referência")
    print(f"Workers: {N_WORKERS} | Amostras/depth: {N_POR_DEPTH}")
    print("=" * 72)
    print()

    print("[1/3] Construindo índice...")
    index = separar_por_depth(DIR_NPZ)
    print(f"  Pronto em {time.time() - t0:.1f}s\n")

    print("  Distribuição:")
    for dep in range(11, 21):
        print(f"    depth={dep:2d}: {len(index[dep]):7,d} estados")
    print()

    print("[2/3] Selecionando amostras...")
    tasks: list[tuple] = []
    for dep in range(11, 21):
        pool = index[dep]
        if not pool:
            print(f"  depth={dep}: NENHUM estado — pulando")
            continue
        n = min(N_POR_DEPTH, len(pool))
        escolhidos = rng.choice(len(pool), size=n, replace=False)
        for k in escolhidos:
            caminho_str, idx = pool[k]
            tasks.append((len(tasks) + 1, dep, caminho_str, idx))
    print(f"  {len(tasks)} estados selecionados\n")

    print("[3/3] Validando em paralelo...\n")
    header = f"  {'#':>3}  {'dep':>3}  {'arquivo':40}  {'idx':>5}  {'mv':>4}  {'tempo':>7}  resultado"
    print(header)
    print("  " + "-" * 80)

    resultados: dict[int, dict] = {dep: {'ok': 0, 'erros': 0, 'msgs': []} for dep in range(11, 21)}
    total_ok = 0
    total_erros = 0
    concluidos = 0
    total = len(tasks)

    with ProcessPoolExecutor(max_workers=N_WORKERS) as ex:
        futures = {ex.submit(_validar_um, t): t for t in tasks}
        for fut in as_completed(futures):
            r = fut.result()
            dep = r['dep']
            concluidos += 1

            if r['terminal']:
                status = "TERMINAL (sem movs)"
                print(f"  {r['num']:>3}  {dep:>3}  {r['arquivo']:40}  {r['idx']:>5}  {'--':>4}  {r['elapsed']:>6.1f}s  {status}", flush=True)
                continue

            if r['erros']:
                status = f"ERRO ({len(r['erros'])})"
                resultados[dep]['erros'] += 1
                resultados[dep]['msgs'].extend(r['erros'][:3])
                total_erros += 1
            else:
                status = "OK"
                resultados[dep]['ok'] += 1
                total_ok += 1

            print(
                f"  {r['num']:>3}  {dep:>3}  {r['arquivo']:40}  {r['idx']:>5}"
                f"  {r['n_tracos']:>4}  {r['elapsed']:>6.1f}s  {status}"
                f"  [{concluidos}/{total}]",
                flush=True,
            )
            if r['erros']:
                for msg in r['erros'][:4]:
                    print(f"         >> {msg}", flush=True)

    print()
    print("=" * 72)
    print("SUMÁRIO FINAL")
    print("=" * 72)
    print(f"  {'dep':>3}  {'OK':>4}  {'ERROS':>6}  status")
    print("  " + "-" * 38)
    for dep in range(11, 21):
        ok = resultados[dep]['ok']
        erros = resultados[dep]['erros']
        if ok == 0 and erros == 0:
            linha_status = "SEM AMOSTRAS"
        elif erros == 0:
            linha_status = "TUDO OK"
        else:
            linha_status = "!! DIVERGENCIA"
        print(f"  {dep:>3}  {ok:>4}  {erros:>6}  {linha_status}")
        for msg in resultados[dep]['msgs'][:2]:
            print(f"         >> {msg}")
    print("  " + "-" * 38)
    print(f"  TOTAL: {total_ok} OK, {total_erros} com erros | {time.time() - t0:.0f}s total")
    print()
    if total_erros == 0 and total_ok > 0:
        print("  RESULTADO: APROVADO — todos os scores batem com o Minimax.")
    elif total_erros > 0:
        print("  RESULTADO: REPROVADO — divergências encontradas.")
    else:
        print("  RESULTADO: indeterminado (nenhum estado não-terminal validado).")
    print("=" * 72)


if __name__ == '__main__':
    validar()

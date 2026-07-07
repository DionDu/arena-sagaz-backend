"""Mineração de falhas por self-play, julgada pelo ORÁCULO (itens 1 e 2 do plano).

A CNN joga contra uma POPULAÇÃO diversa de adversários (Minimax descuidado com ε e
profundidade variados + aleatório + aberturas aleatórias). O oráculo (tablebase
exata) julga CADA lance da CNN em O(1): regret = melhor_valor − valor_do_lance.
Coleta TODO lance com regret>0 — esses são os estados realistas onde a CNN erra.

Saída (NPZ incremental, dedup por posição/bitmask), pronta para virar base de
re-treino: o rótulo é o VETOR `score_melhor_jogada` exato do oráculo (não o argmax).

  saidas/<run-id>/falhas_selfplay.npz  campos:
    bitmask, matriz_antes(N,9,7), score_melhor_jogada(N,31), qtd_tracos, regret,
    valor_otimo, decisivo, classe_cnn, traco_cnn, traco_otimo, n_visto
  saidas/<run-id>/resumo.json  (estatísticas agregadas)

Retomável: processa seeds em blocos; progresso.json guarda o próximo seed.
"""
from __future__ import annotations

import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

_RAIZ = Path(__file__).resolve().parents[3]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (  # noqa: E402
    EstadoTabuleiro, todos_labels_canonicos,
)
from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.adversarios_pontinhos import (  # noqa: E402
    agente_minimax_descuidado, agente_aleatorio, classificar_traco,
)
from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.arena_pontinhos import (  # noqa: E402
    jogar_partida_instrumentada,
)
from gerador_dados.jogo_pontinhos.oraculo_tablebase_pontinhos import (  # noqa: E402
    construir_mapeamento, carregar, scores_de_todas_jogadas_exato, matriz_para_bitmask,
)

# população de adversários (variedade => cobertura de estados realistas)
_PROFS = [1, 2, 3, 4]
_EPS = [0.10, 0.25, 0.40]
_ABERTURAS = [2, 4, 6, 8]

_W = {}


def _adversario_do_seed(seed: int):
    """Escolhe (adversário, abertura_k, ref_eh_j1) de forma determinística pelo seed."""
    if seed % 11 == 0:                      # ~9% totalmente aleatórios (cauda)
        adv = agente_aleatorio()
    else:
        prof = _PROFS[seed % len(_PROFS)]
        eps = _EPS[(seed // 4) % len(_EPS)]
        adv = agente_minimax_descuidado(prof, eps_descuido=eps, t_max_descuido=17)
    abertura = _ABERTURAS[(seed // 3) % len(_ABERTURAS)]
    return adv, abertura, (seed % 2 == 0)


def _worker_init(cfg):
    from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import _cnn_agent_fn
    labels = todos_labels_canonicos(4, 3)
    _W["labels"] = labels
    _W["idx"] = {l: i for i, l in enumerate(labels)}
    _W["ref"] = _cnn_agent_fn(cfg["modelo"], labels)
    _W["val"] = carregar(cfg["tablebase"], mmap=True)
    _, edge_rc, n_edges, ebm, ebc, _bm = construir_mapeamento(4, 3)
    _W.update(edge_rc=edge_rc, n_edges=n_edges, ebm=ebm, ebc=ebc, cfg=cfg)


def _worker(seed: int):
    cfg = _W["cfg"]; idx = _W["idx"]; labels = _W["labels"]
    val = _W["val"]; edge_rc = _W["edge_rc"]; n_edges = _W["n_edges"]
    ebm = _W["ebm"]; ebc = _W["ebc"]
    adv, abertura, ref_j1 = _adversario_do_seed(seed)
    r = jogar_partida_instrumentada(_W["ref"], adv, ref_eh_jogador1=ref_j1,
                                    tamanho="pequeno", seed=seed,
                                    lances_abertura_aleatorios=abertura)
    ref_val = r.ref_valor_matriz
    falhas = []
    n_lances = 0
    for lance in r.lances_da_referencia():
        m = lance.matriz_antes
        s = matriz_para_bitmask(m, 4, 3, edge_rc)
        sc = scores_de_todas_jogadas_exato(val, s, n_edges, ebm, ebc)  # {edge_idx: q}
        e_cnn = idx.get(lance.traco)
        if not sc or e_cnn not in sc:
            continue
        n_lances += 1
        q_cnn = sc[e_cnn]
        q_ot = max(sc.values())
        regret = q_ot - q_cnn
        if regret <= 0:
            continue
        interior = m[1::2, 1::2]
        diff = int((interior == ref_val).sum()) - int((interior == -ref_val).sum())
        vec = np.full(31, -1e9, np.float32)
        for e, q in sc.items():
            vec[e] = q
        est = EstadoTabuleiro.de_tamanho("pequeno"); est.matriz = m.copy()
        falhas.append(dict(
            bitmask=int(s), matriz_antes=m.astype(np.int8),
            score_melhor_jogada=vec, qtd_tracos=int(bin(s).count("1")),
            regret=int(regret), valor_otimo=int(diff + q_ot),
            decisivo=bool((diff + q_ot >= 0) and (diff + q_cnn < 0)),
            classe_cnn=classificar_traco(est, lance.traco),
            traco_cnn=lance.traco, traco_otimo=labels[max(sc, key=lambda e: sc[e])]))
    return seed, n_lances, falhas


def _salvar(saida: Path, acervo: dict):
    if not acervo:
        return
    recs = list(acervo.values())
    arrs = dict(
        bitmask=np.array([r["bitmask"] for r in recs], np.int64),
        matriz_antes=np.stack([r["matriz_antes"] for r in recs]),
        score_melhor_jogada=np.stack([r["score_melhor_jogada"] for r in recs]),
        qtd_tracos=np.array([r["qtd_tracos"] for r in recs], np.int8),
        regret=np.array([r["regret"] for r in recs], np.int16),
        valor_otimo=np.array([r["valor_otimo"] for r in recs], np.int16),
        decisivo=np.array([r["decisivo"] for r in recs], bool),
        classe_cnn=np.array([r["classe_cnn"] for r in recs], "<U7"),
        traco_cnn=np.array([r["traco_cnn"] for r in recs], "<U5"),
        traco_otimo=np.array([r["traco_otimo"] for r in recs], "<U5"),
        n_visto=np.array([r["n_visto"] for r in recs], np.int32),
    )
    tmp = saida.parent / (saida.stem + "_tmp.npz")   # precisa terminar em .npz (np acrescenta senão)
    np.savez_compressed(tmp, **arrs)
    os.replace(tmp, saida)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="modelos/pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_8p3M.tflite")
    ap.add_argument("--tablebase", default="dados/oraculo_pontinhos/tablebase_pequeno_4x3.npy")
    ap.add_argument("--partidas", type=int, default=20000)
    ap.add_argument("--seed-base", type=int, default=0)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--bloco", type=int, default=2000)
    ap.add_argument("--run-id", default="selfplay_v1")
    args = ap.parse_args()

    base = Path(__file__).resolve().parent / "saidas" / args.run_id
    base.mkdir(parents=True, exist_ok=True)
    npz_path = base / "falhas_selfplay.npz"
    prog_path = base / "progresso.json"

    acervo: dict[int, dict] = {}
    seed_ini = args.seed_base
    n_jogos = n_lances = 0
    if prog_path.exists():
        prog = json.loads(prog_path.read_text())
        seed_ini = prog["proximo_seed"]; n_jogos = prog["n_jogos"]; n_lances = prog["n_lances"]
        if npz_path.exists():
            z = np.load(npz_path, allow_pickle=True)
            for i in range(z["bitmask"].shape[0]):
                acervo[int(z["bitmask"][i])] = dict(
                    bitmask=int(z["bitmask"][i]), matriz_antes=z["matriz_antes"][i],
                    score_melhor_jogada=z["score_melhor_jogada"][i],
                    qtd_tracos=int(z["qtd_tracos"][i]), regret=int(z["regret"][i]),
                    valor_otimo=int(z["valor_otimo"][i]), decisivo=bool(z["decisivo"][i]),
                    classe_cnn=str(z["classe_cnn"][i]), traco_cnn=str(z["traco_cnn"][i]),
                    traco_otimo=str(z["traco_otimo"][i]), n_visto=int(z["n_visto"][i]))
        print(f"Retomando: {len(acervo)} falhas distintas, {n_jogos} jogos, próximo seed {seed_ini}", flush=True)

    seed_fim = args.seed_base + args.partidas
    print(f"Self-play minerado | modelo {Path(args.modelo).name} | seeds [{seed_ini},{seed_fim}) "
          f"| {args.workers} workers", flush=True)
    t0 = time.perf_counter()
    try:
        for chunk_ini in range(seed_ini, seed_fim, args.bloco):
            chunk = list(range(chunk_ini, min(chunk_ini + args.bloco, seed_fim)))
            with ProcessPoolExecutor(max_workers=args.workers,
                                     initializer=_worker_init, initargs=(vars(args),)) as ex:
                for seed, nl, falhas in ex.map(_worker, chunk, chunksize=16):
                    n_jogos += 1; n_lances += nl
                    for f in falhas:
                        b = f["bitmask"]
                        if b in acervo:
                            acervo[b]["n_visto"] += 1
                        else:
                            f["n_visto"] = 1
                            acervo[b] = f
            _salvar(npz_path, acervo)
            prog_path.write_text(json.dumps(dict(
                proximo_seed=chunk[-1] + 1, n_jogos=n_jogos, n_lances=n_lances)))
            taxa = n_jogos / (time.perf_counter() - t0)
            print(f"  [{n_jogos}/{args.partidas}] jogos | {len(acervo)} falhas distintas "
                  f"({n_lances} lances julgados) | {taxa:.1f} jogos/s", flush=True)
    except KeyboardInterrupt:
        print("\n!! Interrompido — salvando.", flush=True)
        _salvar(npz_path, acervo)

    # resumo
    recs = list(acervo.values())
    print(f"\n==== RESUMO ====\nJogos: {n_jogos} | lances CNN julgados: {n_lances}")
    print(f"Falhas DISTINTAS (regret>0): {len(recs)}")
    if recs:
        regs = np.array([r["regret"] for r in recs])
        print(f"  regret: media {regs.mean():.2f} | max {regs.max()} | "
              f">=2: {(regs>=2).sum()} | decisivas (vira p/ derrota): {sum(r['decisivo'] for r in recs)}")
        print("  por classe do lance da CNN:", dict(Counter(r["classe_cnn"] for r in recs)))
        fb = Counter(r["qtd_tracos"] for r in recs)
        print("  por qtd_tracos (t):", {k: fb[k] for k in sorted(fb)})
    print(f"NPZ: {npz_path}")


if __name__ == "__main__":
    main()

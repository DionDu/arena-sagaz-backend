"""Constroi um NPZ de REFINAMENTO (schema v2-a3) a partir das falhas NOVAS do
self-play (saidas/<run>/falhas_novas.npz): para cada estado calcula canais,
escalares de cadeias e rotulo via as MESMAS funcoes da base; rotulo de treino =
score_melhor_jogada EXATO do oraculo. Aplica augmentacao por simetria 4x.

Uso:
  python -m ...construir_npz_refinamento_pontinhos --falhas <falhas_novas.npz> \
      --num 1 --saida-dir dados/profundidade_oraculo_exato
Gera: dados/profundidade_oraculo_exato/refinamento_oraculo_001.npz
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_RAIZ = Path(__file__).resolve().parents[3]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import todos_labels_canonicos
from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import _para_dominio_dataset
from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import (
    extrair_canais, extrair_stats_cadeias, NOMES_CANAIS,
)
from gerador_dados.jogo_pontinhos.permutacoes_simetria_pontinhos import aplicar_simetria


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--falhas", required=True)
    ap.add_argument("--num", type=int, default=1)
    ap.add_argument("--saida-dir", default="dados/profundidade_oraculo_exato")
    args = ap.parse_args()

    z = np.load(args.falhas, allow_pickle=True)
    matrizes = z["matriz_antes"]                       # (N,9,7) ao vivo {-1,0,1,8}
    score = z["score_melhor_jogada"].astype(np.float32)  # (N,31) oraculo exato
    qt = z["qtd_tracos"].astype(np.int8)
    N = matrizes.shape[0]
    print(f"{N} estados-falha novos -> construindo refinamento {args.num}", flush=True)

    labels = todos_labels_canonicos(4, 3)
    LAB = np.array(labels, dtype="<U5")
    rng = np.random.default_rng(20260531 + args.num)

    estados = np.zeros((N, 9, 7), np.int8)
    canais = np.zeros((N, 4, 3, 12), np.int8)
    qcl = np.zeros(N, np.int8); tcl = np.zeros(N, np.int8); mcl = np.zeros(N, np.int8)
    for i in range(N):
        mds = _para_dominio_dataset(matrizes[i])
        estados[i] = mds.astype(np.int8)
        canais[i] = extrair_canais(mds).astype(np.int8)
        q, t, m = extrair_stats_cadeias(mds)
        qcl[i], tcl[i], mcl[i] = q, t, m

    # melhor_jogada: aleatorio entre os lances OTIMOS legais (illegais = -1e9)
    is_max = score == score.max(axis=1, keepdims=True)
    ruido = np.where(is_max, rng.random(score.shape), -1.0)
    mj = LAB[np.argmax(ruido, axis=1)].astype("<U5")
    depth = (31 - qt.astype(np.int64)).astype(np.int8)

    base = dict(
        estados=estados, qtd_tracos=qt,
        score_jogada=score.copy(),               # metadata (nao se treina nisso)
        depth_jogada=depth.copy(), depth_geracao=depth.copy(),
        melhor_jogada=mj, score_melhor_jogada=score, depth_melhor_jogada=depth,
        canais=canais, qtd_cadeias_longas=qcl,
        total_caixas_cadeias_longas=tcl, tamanho_max_cadeia_longa=mcl,
        labels_canonicos=LAB, nomes_canais=np.array(NOMES_CANAIS, dtype="<U32"),
    )

    # augmentacao 4x (id, refH, refV, r180)
    variantes = [aplicar_simetria(base, s) for s in (0, 1, 2, 3)]
    POR_LINHA = [k for k in base if k not in ("labels_canonicos", "nomes_canais")]
    out = {k: np.concatenate([v[k] for v in variantes], axis=0) for k in POR_LINHA}
    out["labels_canonicos"] = base["labels_canonicos"]
    out["nomes_canais"] = base["nomes_canais"]

    # dedup (posicoes auto-simetricas geram copias identicas)
    key = np.ascontiguousarray(out["estados"].reshape(out["estados"].shape[0], -1))
    view = key.view(np.dtype((np.void, key.shape[1])))
    _, uniq = np.unique(view, return_index=True)
    uniq = np.sort(uniq)
    for k in POR_LINHA:
        out[k] = out[k][uniq]
    print(f"  4x simetria: {4*N} -> {len(uniq)} apos dedup", flush=True)

    saida = Path(args.saida_dir) / f"refinamento_oraculo_{args.num:03d}.npz"
    saida.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(saida, **out)
    print(f"  salvo: {saida} ({saida.stat().st_size/1e6:.1f} MB)", flush=True)

    # ---- validacao do schema/dominio ----
    print("\n=== validacao ===")
    print("  campos:", sorted(out.keys()))
    print("  estados dominio:", np.unique(out["estados"]).tolist(), "(esperado subset {0,1,8,9})")
    print("  canais dominio:", np.unique(out["canais"]).tolist(), "(esperado {0,1})")
    sv = out["score_melhor_jogada"]; v = sv[sv > -1e8]
    print(f"  score_melhor_jogada validos: min {v.min():.0f} max {v.max():.0f}")
    print(f"  shapes: estados {out['estados'].shape} canais {out['canais'].shape} "
          f"score {out['score_melhor_jogada'].shape}")
    # melhor_jogada e sempre legal/otima?
    idx = {l: i for i, l in enumerate(labels)}
    mji = np.array([idx[m] for m in out["melhor_jogada"]])
    s2 = out["score_melhor_jogada"]
    ok = np.isclose(s2[np.arange(len(mji)), mji],
                    np.where(s2 > -1e8, s2, -np.inf).max(1))
    print(f"  melhor_jogada e otima em {ok.mean()*100:.2f}% das linhas")


if __name__ == "__main__":
    main()

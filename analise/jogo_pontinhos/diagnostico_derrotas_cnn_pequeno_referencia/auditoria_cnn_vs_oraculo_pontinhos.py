"""Auditoria EXATA da CNN contra o oraculo, sobre TODA a base.

O `score_melhor_jogada` da base do oraculo JA e o vetor exato de cada lance. Entao
basta rodar a CNN sobre cada estado e comparar o argmax (restrito aos lances legais)
com o otimo: regret = melhor_valor - valor_do_lance_escolhido_pela_CNN.

regret == 0  -> CNN jogou um lance OTIMO (mesmo que doe caixas: sacrificio correto).
regret  > 0  -> FALHA real da CNN (joga um lance subotimo). Coletadas para mineracao.

Saidas em saidas/auditoria_oraculo/:
  - resumo por arestas_livres (OMA verdadeiro por fase)
  - falhas.npz (estados/canais/score/qtd_tracos/regret das posicoes com regret>0)
"""
import argparse
import glob
import os
import sys
import time
from collections import defaultdict

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="modelos/pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_8p3M.tflite")
    ap.add_argument("--base", default="dados/profundidade_oraculo_exato")
    ap.add_argument("--batch", type=int, default=8192)
    ap.add_argument("--saida", default="analise/jogo_pontinhos/diagnostico_derrotas_cnn_pequeno_referencia/saidas/auditoria_oraculo")
    ap.add_argument("--guardar-falhas", type=int, default=300000, help="Max de estados com regret>0 a guardar p/ mineracao.")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.base, "*.npz")))
    print(f"{len(files)} arquivos | modelo: {os.path.basename(args.modelo)} | batch {args.batch}", flush=True)

    interp = tflite.Interpreter(model_path=args.modelo)
    in_idx = interp.get_input_details()[0]["index"]
    out_idx = interp.get_output_details()[0]["index"]
    B = args.batch
    interp.resize_tensor_input(in_idx, [B, 4, 3, 12]); interp.allocate_tensors()

    def cnn_probs(Xb):
        n = Xb.shape[0]
        if n < B:
            Xb = np.concatenate([Xb, np.zeros((B - n, 4, 3, 12), np.float32)], 0)
        interp.set_tensor(in_idx, Xb); interp.invoke()
        return interp.get_tensor(out_idx)[:n]

    MAXAR = 31
    cnt = np.zeros(MAXAR + 1, np.int64)
    err = np.zeros(MAXAR + 1, np.int64)
    reg_sum = np.zeros(MAXAR + 1, np.int64)
    reg_hist = defaultdict(int)
    tot = errtot = 0
    fail_buf = {k: [] for k in ("estados", "canais", "score_melhor_jogada", "qtd_tracos", "regret")}
    n_fail_guardadas = 0
    t0 = time.perf_counter()

    for fi, f in enumerate(files, 1):
        z = np.load(f, allow_pickle=True)
        canais = z["canais"]; S = z["score_melhor_jogada"].astype(np.float32)
        qt = z["qtd_tracos"].astype(np.int64); est = z["estados"]
        N = qt.shape[0]; ar = 31 - qt
        legal = S > -1e8
        for st in range(0, N, B):
            sl = slice(st, min(st + B, N))
            Xb = canais[sl].astype(np.float32)
            probs = cnn_probs(Xb)
            lg = legal[sl]
            masked = np.where(lg, probs, -1.0)
            arg = masked.argmax(1)
            Ss = S[sl]
            qopt = np.where(lg, Ss, -1e9).max(1)
            qcnn = Ss[np.arange(Ss.shape[0]), arg]
            regret = np.rint(qopt - qcnn).astype(np.int64)
            arb = ar[sl]
            np.add.at(cnt, arb, 1)
            np.add.at(err, arb, (regret > 0).astype(np.int64))
            np.add.at(reg_sum, arb, regret)
            for rv in np.unique(regret):
                reg_hist[int(rv)] += int((regret == rv).sum())
            tot += regret.shape[0]; errtot += int((regret > 0).sum())
            if n_fail_guardadas < args.guardar_falhas:
                fmask = regret > 0
                if fmask.any():
                    take = np.where(fmask)[0]
                    if n_fail_guardadas + take.size > args.guardar_falhas:
                        take = take[: args.guardar_falhas - n_fail_guardadas]
                    fail_buf["estados"].append(est[sl][take])
                    fail_buf["canais"].append(canais[sl][take])
                    fail_buf["score_melhor_jogada"].append(Ss[take])
                    fail_buf["qtd_tracos"].append(qt[sl][take])
                    fail_buf["regret"].append(regret[take])
                    n_fail_guardadas += take.size
        if fi % 20 == 0 or fi == len(files):
            print(f"  [{fi}/{len(files)}] {tot:,} estados | falhas {errtot:,} "
                  f"({errtot/tot*100:.3f}%) | {time.perf_counter()-t0:.0f}s", flush=True)

    print("\n================ OMA VERDADEIRO (CNN vs oraculo, base inteira) ================")
    print(f"Estados auditados: {tot:,}")
    print(f"  regret == 0 (lance otimo): {tot-errtot:,} ({(tot-errtot)/tot*100:.3f}%)  <- OMA verdadeiro")
    print(f"  regret  > 0 (FALHA real):  {errtot:,} ({errtot/tot*100:.3f}%)")
    print(f"  regret medio (todos):      {sum(k*v for k,v in reg_hist.items())/tot:.4f} caixas")
    print("\nHistograma de regret (so onde >0):")
    for r in sorted(reg_hist):
        if r > 0:
            print(f"  regret={r:+d}: {reg_hist[r]:,}")
    print("\nOMA verdadeiro por ARESTAS LIVRES (= 31 - qtd_tracos):")
    print(f"  {'ar':>3} {'estados':>10} {'%falha':>8} {'regret_medio':>13}")
    for a in range(MAXAR, -1, -1):
        if cnt[a]:
            print(f"  {a:>3} {cnt[a]:>10,} {err[a]/cnt[a]*100:>7.3f}% {reg_sum[a]/cnt[a]:>12.4f}")

    os.makedirs(args.saida, exist_ok=True)
    if n_fail_guardadas:
        out = {k: np.concatenate(v, 0) for k, v in fail_buf.items()}
        np.savez_compressed(os.path.join(args.saida, "falhas.npz"), **out)
        print(f"\nFalhas guardadas p/ mineracao: {n_fail_guardadas:,} -> {args.saida}/falhas.npz")
        rg = out["regret"]; qtf = out["qtd_tracos"]
        print(f"  faixa de regret nas falhas: {rg.min()}..{rg.max()} | qtd_tracos das falhas: "
              f"min {qtf.min()} mediana {int(np.median(qtf))} max {qtf.max()}")


if __name__ == "__main__":
    main()

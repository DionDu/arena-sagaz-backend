"""Aprofunda a análise dos 505 erros 'ERRO_DEVERIA_CAPTURAR':

- Distribuição por número da jogada (1..31).
- Distribuição por posição/label da aresta correta vs jogada pela CNN.
- Distribuição por nº de caixas grau-3 disponíveis no estado.
- Distribuição por nº de traços já preenchidos.
- Distribuição por aresta jogada vs aresta correta — heatmap textual.
- Distribuição por simetria (linha 1 vs 7, coluna 0 vs 6) → detectar viés posicional.

Saída: tabelas no console + um arquivo CSV com cada erro classificado.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analisa_grau3_minimax import (  # noqa: E402
    FASE_NOMES,
    LABEL_TO_IDX,
    LABELS_CANONICOS,
    POS_CAIXAS,
    arestas_que_fecham_grau3,
    fase_do_estado,
    grau,
)
from analisa_misses_cnn import parse_md  # noqa: E402

RX_JOGADA_NUM = re.compile(r"jogada(\d+)")


def _resolver_minimax(args):
    mat_partida_bytes, prof = args
    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
    from gerador_dados.jogo_pontinhos.minimax_pontinhos import (
        _scores_de_todas_jogadas,
    )
    mat = np.frombuffer(mat_partida_bytes, dtype=np.int8).reshape(9, 7).copy()
    est = EstadoTabuleiro(4, 3)
    est.matriz = mat
    return _scores_de_todas_jogadas(est, prof)


def jogada_num(path: Path) -> int:
    m = RX_JOGADA_NUM.search(path.name)
    return int(m.group(1)) if m else -1


def n_tracos_preenchidos(mat_treino: np.ndarray) -> int:
    n = 0
    for r in range(9):
        for c in range(7):
            if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
                if mat_treino[r, c] == 9:
                    n += 1
    return n


def main():
    import concurrent.futures as cf
    import time

    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", nargs="?", default=None)
    ap.add_argument("--profundidade", type=int, default=7)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if args.pasta:
        pasta = Path(args.pasta)
    else:
        base = (Path(__file__).resolve().parent.parent
                / "visualizacoes" / "avaliacao_partidas")
        pasta = sorted(p for p in base.iterdir() if p.is_dir())[-1]

    print(f"Pasta: {pasta}")
    arquivos = sorted(pasta.rglob("*.md"))
    eventos = []
    for arq in arquivos:
        try:
            ev = parse_md(arq)
        except Exception:
            continue
        if ev["traco_cnn_idx"] is None:
            continue
        eventos.append(ev)
    print(f"Eventos validos: {len(eventos)}")

    payloads = [
        (ev["mat_partida"].astype(np.int8).tobytes(), args.profundidade)
        for ev in eventos
    ]
    print(f"Rodando Minimax(p={args.profundidade}) em {args.workers} workers...")
    t0 = time.perf_counter()
    resultados_mm = [None] * len(payloads)
    with cf.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, sc in enumerate(ex.map(_resolver_minimax, payloads, chunksize=8)):
            resultados_mm[i] = sc
    print(f"Minimax pronto em {time.perf_counter()-t0:.0f}s")

    # Filtra somente os erros reais
    erros = []
    for ev, scores in zip(eventos, resultados_mm):
        if scores is None:
            continue
        traco_cnn = ev["traco_cnn"]
        sc_max = max(scores.values())
        otimas = {k for k, v in scores.items() if v == sc_max}
        arestas_grau3 = {LABELS_CANONICOS[i] for i in arestas_que_fecham_grau3(ev["mat_treino"])}
        if traco_cnn in otimas:
            continue  # CNN_OTIMA
        if not (arestas_grau3 & otimas):
            continue  # SAC_OK_OUTRA — não é erro de captura
        # ERRO_DEVERIA_CAPTURAR
        erros.append({
            "ev": ev,
            "otimas": otimas,
            "grau3": arestas_grau3,
            "sc_cnn": scores.get(traco_cnn),
            "sc_max": sc_max,
        })

    print(f"\nTotal de ERRO_DEVERIA_CAPTURAR: {len(erros)}")

    # ----------------- Análise 1: distribuição por nº jogada -----------------
    por_jogada = Counter(jogada_num(e["ev"]["path"]) for e in erros)
    por_tracos = Counter(n_tracos_preenchidos(e["ev"]["mat_treino"]) for e in erros)
    print("\nDistribuicao por numero de tracos preenchidos no estado:")
    for n in sorted(por_tracos):
        print(f"  {n:>3} tracos: {por_tracos[n]:>4} erros")

    print("\nDistribuicao por jogada (ordem na partida):")
    for j in sorted(por_jogada):
        print(f"  jogada {j:>3}: {por_jogada[j]:>4} erros")

    # ----------------- Análise 2: aresta correta vs aresta jogada ------------
    # Quais arestas a CNN deveria ter jogado mas não jogou
    cnt_correta = Counter()
    cnt_cnn = Counter()
    pares = Counter()  # (correta, cnn) -> n
    for e in erros:
        # Arestas grau-3 que tambem sao otimas
        deveria = sorted(e["grau3"] & e["otimas"])
        cnn_jog = e["ev"]["traco_cnn"]
        for a in deveria:
            cnt_correta[a] += 1
        cnt_cnn[cnn_jog] += 1
        # Par (primeira ótima, jogada cnn)
        pares[(deveria[0] if deveria else "?", cnn_jog)] += 1

    print("\nTop arestas que a CNN DEVERIA ter jogado (mas nao jogou):")
    for a, n in cnt_correta.most_common(15):
        print(f"  {a:<10} {n:>4}")

    print("\nTop arestas que a CNN JOGOU NO LUGAR:")
    for a, n in cnt_cnn.most_common(15):
        print(f"  {a:<10} {n:>4}")

    print("\nTop pares (deveria_jogar -> jogou):")
    for (correta, cnn), n in pares.most_common(15):
        print(f"  {correta:<10} -> {cnn:<10}  {n:>4}")

    # ----------------- Análise 3: nº de caixas grau-3 disponíveis ------------
    cnt_n_grau3 = Counter()
    for e in erros:
        m = e["ev"]["mat_treino"]
        n3 = sum(1 for (r, c) in POS_CAIXAS if m[r, c] != 1 and grau(m, r, c) == 3)
        cnt_n_grau3[n3] += 1
    print("\nDistribuicao por nº de caixas grau-3 disponiveis no estado de erro:")
    for n in sorted(cnt_n_grau3):
        print(f"  {n} caixa(s) grau-3: {cnt_n_grau3[n]:>4} erros")

    # ----------------- Análise 4: simetria (lado direito vs esquerdo) --------
    # Tabuleiro 4×3: colunas 0,2,4,6 (4 colunas de pontos), arestas H em 1,3,5
    # e arestas V em 0,2,4,6. Vamos ver lado L (col<3) vs R (col>=4).
    cnt_lado_correto = Counter()
    cnt_lado_cnn = Counter()
    for e in erros:
        deveria = sorted(e["grau3"] & e["otimas"])
        for a in deveria:
            _, _, c = a.split("_")
            cnt_lado_correto["L" if int(c) < 3 else ("M" if int(c) == 3 else "R")] += 1
        cnn = e["ev"]["traco_cnn"]
        _, _, c = cnn.split("_")
        cnt_lado_cnn["L" if int(c) < 3 else ("M" if int(c) == 3 else "R")] += 1

    print("\nLado da aresta CORRETA (que a CNN deveria jogar):")
    for k in ("L", "M", "R"):
        print(f"  {k}: {cnt_lado_correto[k]:>4}")
    print("Lado da aresta JOGADA pela CNN:")
    for k in ("L", "M", "R"):
        print(f"  {k}: {cnt_lado_cnn[k]:>4}")

    # ----------------- CSV ---------------------------------------------------
    saida_csv = pasta / "erros_deveria_capturar.csv"
    with open(saida_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arquivo", "adversario", "n_tracos", "jogada_num",
                    "fase", "n_grau3", "aresta_cnn", "score_cnn",
                    "arestas_corretas", "score_otimo"])
        for e in erros:
            ev = e["ev"]
            m = ev["mat_treino"]
            n3 = sum(1 for (r, c) in POS_CAIXAS if m[r, c] != 1 and grau(m, r, c) == 3)
            f_ = fase_do_estado(m)
            deveria = sorted(e["grau3"] & e["otimas"])
            w.writerow([
                ev["path"].name, ev["adversario"], n_tracos_preenchidos(m),
                jogada_num(ev["path"]), FASE_NOMES[f_], n3,
                ev["traco_cnn"], e["sc_cnn"], "|".join(deveria), e["sc_max"]
            ])
    print(f"\nCSV salvo em: {saida_csv}")


if __name__ == "__main__":
    main()

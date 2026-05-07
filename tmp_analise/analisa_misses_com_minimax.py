"""Análise refinada: para cada caixa perdida, comparar a jogada da CNN com
o que o Minimax(p=9) recomendaria naquele estado exato.

Classifica cada evento em:
  - CNN_OTIMA: a CNN escolheu uma jogada que o Minimax considera ótima
                (=> a "caixa perdida" foi sacrifício correto, não erro real)
  - SACRIFICIO_INCORRETO: o Minimax mandaria capturar grau-3, mas CNN não.
                           Ou: o Minimax recomenda outra jogada (não a CNN
                           e não a captura).
  - VARIAÇÕES: ver subtipo no relatório

Permite usar pool de processos para paralelizar Minimax.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

# Silencia TF/Keras (não usamos aqui, mas evita poluição se importado).
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

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
    sacrificio_aplicavel,
    simular_captura_gulosa,
)
from analisa_misses_cnn import (  # noqa: E402
    normalizar_para_encoding_treino,
    parse_md,
)


# --------------------------------------------------------------------------
# Avaliação Minimax sob demanda — em processo separado para paralelismo
# --------------------------------------------------------------------------
def _resolver_minimax(args):
    """Worker: roda Minimax sobre um estado e retorna {label: score}."""
    mat_partida_bytes, prof = args
    # Importação dentro do worker para evitar fork issues em Windows.
    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
    from gerador_dados.jogo_pontinhos.minimax_pontinhos import (
        _scores_de_todas_jogadas,
    )
    mat = np.frombuffer(mat_partida_bytes, dtype=np.int8).reshape(9, 7).copy()
    # Para o Minimax, qualquer aresta preenchida é "preenchida". O dono não
    # importa para a árvore do jogo (Minimax assume turno do jogador maximizador).
    # O sinal +/-1 só conta quando o estado_terminal mede o saldo.
    # Para reaproveitar o motor, eu replicio a matriz tal como está
    # (encoding partida) — o Minimax aceita qualquer não-zero como ocupado.
    est = EstadoTabuleiro(4, 3)
    est.matriz = mat
    scores = _scores_de_todas_jogadas(est, prof)
    return scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", nargs="?", default=None,
                    help="Pasta da execução (default: mais recente)")
    ap.add_argument("--profundidade", type=int, default=7,
                    help="Profundidade do Minimax para o oráculo (default: 7)")
    ap.add_argument("--workers", type=int, default=8,
                    help="Workers paralelos (default: 8)")
    ap.add_argument("--limite", type=int, default=None,
                    help="Avalia apenas N estados (debug)")
    args = ap.parse_args()

    if args.pasta:
        pasta = Path(args.pasta)
    else:
        base = (Path(__file__).resolve().parent.parent
                / "visualizacoes" / "avaliacao_partidas")
        execs = sorted(p for p in base.iterdir() if p.is_dir())
        pasta = execs[-1]
    print(f"Pasta:       {pasta}")
    print(f"Profundidade Minimax: {args.profundidade}")
    print(f"Workers:     {args.workers}")

    arquivos = sorted(pasta.rglob("*.md"))
    if args.limite:
        arquivos = arquivos[: args.limite]
    print(f"Eventos:     {len(arquivos)}")

    # Parseia tudo primeiro (rápido) e prepara payloads p/ Minimax.
    eventos = []
    for arq in arquivos:
        try:
            ev = parse_md(arq)
        except Exception:
            continue
        if ev["traco_cnn_idx"] is None:
            continue
        # Para o Minimax precisamos do encoding partida cru (mat_partida).
        eventos.append(ev)

    print(f"Eventos válidos: {len(eventos)}")
    payloads = [
        (ev["mat_partida"].astype(np.int8).tobytes(), args.profundidade)
        for ev in eventos
    ]

    # Roda Minimax em paralelo
    print(f"Rodando Minimax(p={args.profundidade}) em {args.workers} workers...")
    t0 = time.perf_counter()
    resultados_mm = [None] * len(payloads)
    with cf.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, sc in enumerate(ex.map(_resolver_minimax, payloads, chunksize=8)):
            resultados_mm[i] = sc
            if (i + 1) % 50 == 0:
                dt = time.perf_counter() - t0
                print(f"   {i+1}/{len(payloads)}  ({dt:.0f}s)")
    dt = time.perf_counter() - t0
    print(f"Minimax pronto em {dt:.0f}s")

    # ----------------------------------------------------------
    # Classificação
    # ----------------------------------------------------------
    # Subcategorias do erro:
    #   CNN_OTIMA               — a jogada da CNN está entre as ótimas do Minimax
    #   SAC_OK_OUTRA            — Minimax recomenda sacrifício mas em outra aresta
    #                              que não a da CNN (a CNN sacrificou no lugar errado)
    #   ERRO_DEVERIA_CAPTURAR   — Minimax recomenda capturar grau-3, CNN não capturou
    #   INCONCLUSIVO            — empate: tanto capturar quanto não-capturar são
    #                              ótimos no Minimax; CNN escolheu não-capturar e
    #                              isso também é ótimo (cai em CNN_OTIMA na prática,
    #                              mas se quisermos separar)
    contadores = defaultdict(lambda: defaultdict(int))  # fase -> categoria -> n
    contadores_adv = defaultdict(lambda: defaultdict(int))
    diferencas_score = defaultdict(list)  # categoria -> deltas

    exemplos = defaultdict(list)

    for ev, scores in zip(eventos, resultados_mm):
        if scores is None:
            continue
        mat_treino = ev["mat_treino"]
        f = fase_do_estado(mat_treino)
        adv = ev["adversario"]
        traco_cnn = ev["traco_cnn"]
        sc_cnn = scores.get(traco_cnn)
        sc_max = max(scores.values())
        # Tolerância: empates exatos (Minimax retorna inteiros).
        otimas = {k for k, v in scores.items() if v == sc_max}

        arestas_grau3 = {LABELS_CANONICOS[i] for i in arestas_que_fecham_grau3(mat_treino)}
        captura_otima = bool(arestas_grau3 & otimas)

        if traco_cnn in otimas:
            cat = "CNN_OTIMA"
        elif captura_otima:
            cat = "ERRO_DEVERIA_CAPTURAR"
        else:
            # Minimax não recomenda capturar; recomenda outra jogada não-grau3
            # mas a CNN também escolheu não-capturar — só errou QUAL.
            cat = "SAC_OK_OUTRA"

        contadores[f][cat] += 1
        contadores_adv[adv][cat] += 1
        delta = sc_max - (sc_cnn if sc_cnn is not None else sc_max)
        diferencas_score[cat].append(float(delta))

        if len(exemplos[cat]) < 3:
            exemplos[cat].append((ev, scores, sc_cnn, otimas, arestas_grau3))

    # ----------------------------------------------------------
    # Relatório
    # ----------------------------------------------------------
    cats = ["CNN_OTIMA", "SAC_OK_OUTRA", "ERRO_DEVERIA_CAPTURAR"]
    print()
    print("=" * 100)
    print(f"COMPARAÇÃO COM ORÁCULO Minimax(p={args.profundidade}) — caixas perdidas pela CNN")
    print("=" * 100)
    hdr = f'{"Fase":<22}{"Total":>8}'
    for c in cats:
        hdr += f'{c:>26}'
    print(hdr)
    print("-" * len(hdr))
    for f in (0, 1, 2, 3):
        total_f = sum(contadores[f].values())
        linha = f'{FASE_NOMES[f]:<22}{total_f:>8}'
        for c in cats:
            linha += f'{contadores[f][c]:>26}'
        print(linha)
    tot = sum(sum(contadores[f].values()) for f in (0, 1, 2, 3))
    linha = f'{"TOTAL":<22}{tot:>8}'
    for c in cats:
        n = sum(contadores[f][c] for f in (0, 1, 2, 3))
        linha += f'{n:>26}'
    print(linha)

    print()
    print("Por adversário × categoria")
    print("-" * len(hdr))
    hdr2 = f'{"Adversário":<20}{"Total":>8}'
    for c in cats:
        hdr2 += f'{c:>26}'
    print(hdr2)
    for adv in sorted(contadores_adv):
        total_adv = sum(contadores_adv[adv].values())
        linha = f'{adv:<20}{total_adv:>8}'
        for c in cats:
            linha += f'{contadores_adv[adv][c]:>26}'
        print(linha)

    print()
    print("Delta-score (Minimax_otimo - jogada_CNN) por categoria:")
    for c in cats:
        ds = diferencas_score[c]
        if not ds:
            continue
        arr = np.array(ds)
        print(f"  {c:<26}  n={len(arr):>5}  min={arr.min():>4.0f}  "
              f"mediana={np.median(arr):>5.1f}  máx={arr.max():>4.0f}  "
              f"#delta=0={int((arr==0).sum())}")

    # Exemplos
    print()
    for c in cats:
        exs = exemplos[c]
        if not exs:
            continue
        print()
        print("=" * 96)
        print(f"Exemplos da categoria {c}")
        print("=" * 96)
        for (ev, sc, sc_cnn, otimas, gr3) in exs:
            f = fase_do_estado(ev["mat_treino"])
            print(f"\n  {ev['path'].name}  fase={FASE_NOMES[f]}  adv={ev['adversario']}")
            print(f"    aresta CNN: {ev['traco_cnn']}  score Minimax={sc_cnn}")
            print(f"    arestas ótimas Minimax: {sorted(otimas)}  "
                  f"score={max(sc.values())}")
            print(f"    arestas grau-3 disponíveis: {sorted(gr3)}")


if __name__ == "__main__":
    main()

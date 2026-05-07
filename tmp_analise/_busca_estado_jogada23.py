"""Roda várias seeds para encontrar uma partida CNN-primeiro vs Minimax(p=1)
em que a CNN, na jogada 23 (t=22), produz divergência moderada (d=2 caixas)
sob oráculo p=5 — replicando o caso do PNG suspeito.

Para cada seed que match, salva a matriz e roda também p=7 e p=9 para ver se
mantém o veredito de "CNN errou por 2 caixas" ou se é horizon effect."""
from __future__ import annotations
import os, sys, random
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))

import numpy as np
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro, todos_labels_canonicos,
)
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas
from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import (
    _cnn_agent_fn, _minimax_agent_fn,
)

MODELO = "modelos/pontinhos_pequeno_profundidade_9.tflite"
TAMANHO = "pequeno"
PROF_ADV = 1
T_ALVO = 22
N_SEEDS = 30


def _contar_tracos(matriz):
    # Posições de aresta: (par, ímpar) e (ímpar, par). Vértices = (par, par);
    # caixas = (ímpar, ímpar). Traço preenchido = qualquer valor != 0.
    interior_h = matriz[0::2, 1::2]   # arestas horizontais
    interior_v = matriz[1::2, 0::2]   # arestas verticais
    return int((interior_h != 0).sum() + (interior_v != 0).sum())


labels = todos_labels_canonicos(4, 3)
cnn = _cnn_agent_fn(MODELO, labels)
adv = _minimax_agent_fn(PROF_ADV)

casos_encontrados = []

for seed in range(N_SEEDS):
    random.seed(seed)
    estado = EstadoTabuleiro.de_tamanho(TAMANHO)
    turno_cnn = 1
    turno_corrente = 1
    valor = {1: 1, 2: -1}
    numero_jogada = 0
    while not estado.esta_terminal():
        numero_jogada += 1
        n_tracos = _contar_tracos(estado.matriz)
        eh_vez_cnn = (turno_corrente == turno_cnn)
        if eh_vez_cnn and n_tracos == T_ALVO:
            # Achou o estado!
            scores_p5 = _scores_de_todas_jogadas(estado, 5)
            jogada_cnn = cnn(estado)
            max_p5 = max(scores_p5.values())
            score_cnn_p5 = scores_p5.get(jogada_cnn, max_p5)
            delta_p5 = max_p5 - score_cnn_p5
            if numero_jogada == 23 and n_tracos == 22:  # foco no caso do PNG
                # Match candidato — calcula também p=7 e p=9
                scores_p7 = _scores_de_todas_jogadas(estado, 7)
                scores_p9 = _scores_de_todas_jogadas(estado, 9)
                max_p7 = max(scores_p7.values())
                max_p9 = max(scores_p9.values())
                delta_p7 = max_p7 - scores_p7.get(jogada_cnn, max_p7)
                delta_p9 = max_p9 - scores_p9.get(jogada_cnn, max_p9)
                otimas_p5 = [t for t, s in scores_p5.items() if s == max_p5]
                otimas_p7 = [t for t, s in scores_p7.items() if s == max_p7]
                otimas_p9 = [t for t, s in scores_p9.items() if s == max_p9]
                casos_encontrados.append({
                    "seed": seed, "matriz": estado.matriz.copy(),
                    "jogada_cnn": jogada_cnn,
                    "delta_p5": delta_p5, "delta_p7": delta_p7, "delta_p9": delta_p9,
                    "otimas_p5": otimas_p5, "otimas_p7": otimas_p7, "otimas_p9": otimas_p9,
                    "score_cnn_p5": score_cnn_p5,
                    "score_cnn_p7": scores_p7.get(jogada_cnn),
                    "score_cnn_p9": scores_p9.get(jogada_cnn),
                    "max_p5": max_p5, "max_p7": max_p7, "max_p9": max_p9,
                    "scores_p5": scores_p5, "scores_p9": scores_p9,
                })
                print(f"seed={seed}: MATCH! delta_p5={delta_p5} delta_p7={delta_p7} delta_p9={delta_p9}")
            break  # estado em t=22 tratado, próxima seed
        if eh_vez_cnn:
            jog = cnn(estado)
        else:
            jog = adv(estado)
        cx = estado.aplicar_traco(jog, valor[turno_corrente])
        if cx == 0:
            turno_corrente = 3 - turno_corrente

print(f"\n{len(casos_encontrados)} caso(s) compatível(eis) com PNG (jogada 23, t=22, d=2 sob p=5):")
for c in casos_encontrados[:5]:
    print(f"\n--- seed={c['seed']} ---")
    print(c["matriz"])
    print(f"jogada_cnn={c['jogada_cnn']}  score_cnn_p5={c['score_cnn_p5']}  max_p5={c['max_p5']}  Δ_p5={c['delta_p5']}")
    print(f"                          score_cnn_p7={c['score_cnn_p7']}  max_p7={c['max_p7']}  Δ_p7={c['delta_p7']}")
    print(f"                          score_cnn_p9={c['score_cnn_p9']}  max_p9={c['max_p9']}  Δ_p9={c['delta_p9']}")
    print(f"otimas_p5: {c['otimas_p5']}")
    print(f"otimas_p7: {c['otimas_p7']}")
    print(f"otimas_p9: {c['otimas_p9']}")
    # Top 5 jogadas por p9
    rank9 = sorted(c["scores_p9"].items(), key=lambda kv: kv[1], reverse=True)
    print("ranking p=9 (top 8):")
    for t, s in rank9[:8]:
        marca = []
        if t == c["jogada_cnn"]: marca.append("CNN")
        if t in c["otimas_p9"]: marca.append("ÓTIMA_p9")
        if t in c["otimas_p5"]: marca.append("ótima_p5")
        m = " ".join(marca)
        print(f"  {t}: {s:+d}  {m}")

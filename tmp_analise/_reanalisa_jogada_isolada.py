"""Reanálise pontual de UMA jogada específica.

Reproduz a partida CNN vs Minimax(p_adv) determinística até atingir o estado
desejado (n_tracos_antes), depois roda Minimax(p_oraculo) — geralmente p=9 —
sobre esse estado para comparar com o que o oráculo p=5/p=7 (usado no run
principal) sugeriu.

Uso:
    py tmp_analise/_reanalisa_jogada_isolada.py \
        --modelo modelos/pontinhos_pequeno.tflite \
        --tamanho pequeno \
        --partida-idx 0 --cnn-primeiro \
        --adversario-prof 1 \
        --t-alvo 22 --jogada-alvo 23 \
        --profundidade-oraculo 9
"""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro, todos_labels_canonicos,
)
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas
from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import (
    _cnn_agent_fn, _minimax_agent_fn,
)


def _contar_tracos(matriz):
    interior_h = matriz[0::2, 1::2]
    interior_v = matriz[1::2, 0::2]
    return int((interior_h == 8).sum() + (interior_v == 8).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--tamanho", default="pequeno")
    ap.add_argument("--partida-idx", type=int, default=0)
    ap.add_argument("--cnn-primeiro", action="store_true")
    ap.add_argument("--adversario-prof", type=int, default=1)
    ap.add_argument("--t-alvo", type=int, required=True,
                    help="número de traços ANTES da jogada da CNN que queremos analisar")
    ap.add_argument("--jogada-alvo", type=int, default=None,
                    help="opcional: número sequencial da jogada (apenas para conferência)")
    ap.add_argument("--profundidade-oraculo", type=int, nargs="+", default=[5, 7, 9])
    args = ap.parse_args()

    labels = (
        todos_labels_canonicos(4, 3) if args.tamanho == "pequeno"
        else todos_labels_canonicos(5, 4)
    )
    cnn = _cnn_agent_fn(args.modelo, labels)
    adv = _minimax_agent_fn(args.adversario_prof)

    # Seed para reproduzibilidade do tie-breaking do Minimax(p_adv).
    # No analisa_divergencia_estrategica.py NÃO há seed, então a partida não
    # é determinística no run real. Aqui a gente roda múltiplas seeds e
    # mostra o resultado para a primeira em que conseguimos atingir t=alvo.
    import random as _rnd

    estado = EstadoTabuleiro.de_tamanho(args.tamanho)
    turno_cnn = 1 if args.cnn_primeiro else 2
    turno_corrente = 1
    valor = {1: 1, 2: -1}
    numero_jogada = 0

    # Reproduz a partida ATÉ chegar no estado em que a CNN está prestes a
    # decidir e t == args.t_alvo.
    while not estado.esta_terminal():
        numero_jogada += 1
        n_tracos = _contar_tracos(estado.matriz)
        eh_vez_cnn = (turno_corrente == turno_cnn)

        if eh_vez_cnn and n_tracos == args.t_alvo:
            break  # achamos o estado

        if eh_vez_cnn:
            jogada = cnn(estado)
        else:
            jogada = adv(estado)

        caixas = estado.aplicar_traco(jogada, valor[turno_corrente])
        if caixas == 0:
            turno_corrente = 3 - turno_corrente

    if estado.esta_terminal():
        print(f"Partida acabou ANTES de atingir t={args.t_alvo}. Abortando.")
        return

    n_tracos = _contar_tracos(estado.matriz)
    print(f"Estado atingido: jogada {numero_jogada}, t={n_tracos}, "
          f"vez_da_CNN={turno_corrente == turno_cnn}")
    print()

    if args.jogada_alvo is not None and numero_jogada != args.jogada_alvo:
        print(f"AVISO: jogada sequencial obtida ({numero_jogada}) "
              f"!= jogada-alvo declarada ({args.jogada_alvo})")
        print()

    # Mostra a matriz pra conferência
    print("Matriz expandida (1 e -1 são caixas; 8/9 são traços; 0 = não-jogado):")
    print(estado.matriz)
    print()

    # CNN escolhe agora
    jogada_cnn = cnn(estado)
    print(f"Jogada da CNN: {jogada_cnn}")
    print()

    # Para cada profundidade do oráculo, calcula scores
    for prof in args.profundidade_oraculo:
        print(f"=== Minimax(p={prof}) ===")
        scores = _scores_de_todas_jogadas(estado, prof)
        max_score = max(scores.values())
        otimas = [t for t, s in scores.items() if s == max_score]
        score_cnn = scores.get(jogada_cnn)
        delta = max_score - score_cnn

        # Top-5 jogadas por score
        ranking = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        print(f"  Score MAX = {max_score} caixas (jogadas ótimas: {otimas})")
        print(f"  Score da jogada CNN ({jogada_cnn}) = {score_cnn} → Δ = {delta} caixas")
        print(f"  Ranking (top 8):")
        for t, s in ranking[:8]:
            marca = ""
            if t == jogada_cnn: marca += " ←CNN"
            if t in otimas:     marca += " ←ÓTIMA"
            print(f"    {t}: {s:+d}{marca}")
        print()


if __name__ == "__main__":
    main()

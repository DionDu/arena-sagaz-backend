"""Analisa o estado da jogada 23 da partida 0 (PNG suspeito) usando a matriz
que o usuário reconstituiu visualmente do PNG.

A matriz original do PNG, conforme leitura do usuário (8=ponto, 1=traço marcado
ou caixa marcada, 0=vazio):

  [8 1 8 0 8 1 8]   <- linha 0
  [1 1 1 0 0 0 0]   <- linha 1
  [8 1 8 0 8 1 8]
  [1 1 1 0 1 1 1]
  [8 1 8 0 8 1 8]
  [1 1 1 0 1 1 1]
  [8 1 8 0 8 1 8]
  [0 0 0 0 1 1 1]   <- aresta H_6_3 NÃO marcada
  [8 0 8 1 8 1 8]   <- linha 8

Convenções do EstadoTabuleiro:
  - vértice (par,par)        : valor 0 ou 8 (irrelevante para o motor; convenção 0)
  - aresta H (par,ímpar)     : valor 0 = livre, ±1 = marcada
  - aresta V (ímpar,par)     : valor 0 = livre, ±1 = marcada
  - caixa (ímpar,ímpar)      : valor 0 = aberta, ±1 = fechada
  - quem marcou: o valor (+1 ou -1) só importa para contagem final; o motor
    Minimax avalia "saldo de caixas" do jogador da vez como maximizador.

Como o usuário codificou tudo como 1, vou simplesmente colocar 1 em toda
posição que ele marcou como 1 (incluindo caixas fechadas). Para o ângulo
contagem, isso faz com que **o jogador 1 esteja com TODAS as caixas
fechadas até agora**, e o oponente com 0. O motor Minimax NÃO usa essa
informação para decidir — ele só olha o ESTADO de arestas-livres + caixas-
abertas e calcula saldo futuro a partir do jogador-da-vez.

Então o resultado do Minimax sobre este estado é independente de quem
marcou cada caixa fechada — só depende do estado geométrico do tabuleiro
e de quem é a vez.
"""
from __future__ import annotations
import os, sys
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))

import numpy as np
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro, todos_labels_canonicos,
)
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas


# Matriz reconstruída do PNG jogada023_t22_d2_moderada.
# Substitui 8 por 0 nos vértices (irrelevantes ao motor).
MATRIZ_PNG = np.array([
    [0, 1, 0, 0, 0, 1, 0],
    [1, 1, 1, 0, 0, 0, 0],
    [0, 1, 0, 0, 0, 1, 0],
    [1, 1, 1, 0, 1, 1, 1],
    [0, 1, 0, 0, 0, 1, 0],
    [1, 1, 1, 0, 1, 1, 1],
    [0, 1, 0, 0, 0, 1, 0],
    [0, 0, 0, 0, 1, 1, 1],
    [0, 0, 0, 1, 0, 1, 0],
], dtype=np.int8)


def main():
    # Sanity: contar traços e caixas fechadas
    arestas_h = MATRIZ_PNG[0::2, 1::2]   # (par, ímpar) — 5x3
    arestas_v = MATRIZ_PNG[1::2, 0::2]   # (ímpar, par) — 4x4
    caixas    = MATRIZ_PNG[1::2, 1::2]   # (ímpar, ímpar) — 4x3

    n_arestas = int((arestas_h != 0).sum() + (arestas_v != 0).sum())
    n_caixas  = int((caixas != 0).sum())
    print(f"Arestas marcadas: {n_arestas}")
    print(f"Caixas fechadas:  {n_caixas}")
    print(f"Caixas abertas:   {12 - n_caixas}")
    print()

    # Constrói EstadoTabuleiro
    estado = EstadoTabuleiro.de_tamanho("pequeno")
    estado.matriz = MATRIZ_PNG.copy()

    # Lista jogadas disponíveis
    disponiveis = estado.tracos_disponiveis()
    print(f"Jogadas disponíveis ({len(disponiveis)}): {disponiveis}")
    print()

    # Profundidade do oráculo: 31 - 22 = 9 traços livres -> p=9 perfeito
    # (na verdade p=9 explora 9 plies, suficiente pra ver até o fim).
    print("=== Minimax(p=9) — perfeito até o fim ===")
    scores_p9 = _scores_de_todas_jogadas(estado, 9)
    max_s = max(scores_p9.values())
    otimas = [t for t, s in scores_p9.items() if s == max_s]
    print(f"  Score MAX = {max_s} (jogadas ótimas: {otimas})")
    ranking = sorted(scores_p9.items(), key=lambda kv: kv[1], reverse=True)
    for t, s in ranking:
        marca = ""
        if t == "H_0_3": marca += " <-CNN_jogou"
        if t == "H_2_3": marca += " <-PNG_diz_otima"
        if t in otimas:  marca += " <-OTIMA_p9"
        print(f"    {t}: {s:+d}{marca}")
    print()

    # Para conferência cruzada, p=5 e p=7 também
    for prof in (5, 7):
        print(f"=== Minimax(p={prof}) ===")
        sc = _scores_de_todas_jogadas(estado, prof)
        m = max(sc.values())
        ots = [t for t, s in sc.items() if s == m]
        print(f"  Score MAX = {m} (otimas p={prof}: {ots})")
        s_h03 = sc.get("H_0_3"); s_h23 = sc.get("H_2_3")
        print(f"  H_0_3 (CNN) = {s_h03:+d}   H_2_3 (PNG) = {s_h23:+d}")
        print()


if __name__ == "__main__":
    main()

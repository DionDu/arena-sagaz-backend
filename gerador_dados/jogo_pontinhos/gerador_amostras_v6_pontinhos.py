"""Workers para o notebook ``Geracao_Amostras_v6.ipynb``.

Este modulo concentra as funcoes invocadas pelos workers do
``ProcessPoolExecutor``. Mantemos o codigo aqui (e nao no proprio notebook)
porque o ``multiprocessing`` no Windows usa ``spawn`` e precisa importar
funcoes de modulos top-level para reidrata-las nos processos filho.

Pipeline em 2 fases:
- Fase 1 (``gerar_amostra``): produz UM estado de tabuleiro ja em formato
  neutro ``{0, 1, 8, 9}`` (contrato §contexto_1_geracao_dataset). Modo
  ``MODO_ALEATORIO`` (5% das amostras) sorteia K tracos aleatorios; modo
  ``MODO_AUTOPLAY`` (95%) roda Minimax(p) x Minimax(p) ate atingir K tracos.
- Fase 2 (``calcular_scores``): para um estado neutro ja gerado, calcula via
  Minimax(profundidade=7) o vetor de scores das 31 jogadas canonicas e o
  rotulo da melhor jogada (argmax com desempate aleatorio).
"""
from __future__ import annotations

import random as _random
from typing import Tuple

import numpy as np

from gerador_dados.jogo_pontinhos.minimax_pontinhos import (
    melhor_jogada,
    melhor_jogada_com_scores,
)
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    todos_labels_canonicos,
)


LINHAS = 4
COLUNAS = 3
ALTURA = 2 * LINHAS + 1   # 9
LARGURA = 2 * COLUNAS + 1  # 7

LABELS_CANONICOS: list[str] = todos_labels_canonicos(LINHAS, COLUNAS)
INDICE_LABEL: dict[str, int] = {lab: i for i, lab in enumerate(LABELS_CANONICOS)}
N_LABELS = len(LABELS_CANONICOS)

SCORE_INDISPONIVEL = -1_000_000_000.0  # = -1e9 (jogadas invalidas)

MODO_ALEATORIO = 0
MODO_AUTOPLAY = 3


def matriz_para_neutro(mat_live: np.ndarray) -> np.ndarray:
    """Converte uma matriz live para o formato neutro do contrato.

    O contrato (``contexto_1_geracao_dataset``) exige dominio ``{0, 1, 8, 9}``:
    pontos fixos em ``8``, caixas fechadas em ``1``, tracos preenchidos em ``9``,
    vazio em ``0`` — sem distincao de jogador.

    A conversao e por POSICAO (par/impar), NAO por valor da celula. Isso evita
    a ambiguidade de uma celula valer ``+1`` por ser traco do J1 ou por ser
    caixa fechada.
    """
    out = np.zeros((ALTURA, LARGURA), dtype=np.int8)
    for r in range(ALTURA):
        for c in range(LARGURA):
            v = mat_live[r, c]
            if r % 2 == 0 and c % 2 == 0:
                out[r, c] = 8
            elif r % 2 == 1 and c % 2 == 1:
                out[r, c] = 1 if v != 0 else 0
            else:
                out[r, c] = 9 if v != 0 else 0
    return out


def _gerar_aleatorio(num_tracos: int, rng: np.random.Generator) -> np.ndarray:
    estado = EstadoTabuleiro(LINHAS, COLUNAS)
    disponiveis = estado.tracos_disponiveis()
    idxs = rng.choice(len(disponiveis), size=num_tracos, replace=False)
    for i in idxs:
        estado.aplicar_traco(disponiveis[int(i)], jogador=1)
    return matriz_para_neutro(estado.matriz)


def _gerar_autoplay(num_tracos_alvo: int, profundidade: int,
                    rng: np.random.Generator) -> np.ndarray:
    """Roda Minimax(p) x Minimax(p) ate o tabuleiro ter ``num_tracos_alvo`` tracos.

    A simetria do Minimax (`_caixa_fechada` so olha ``!= 0``) permite chamar
    ``melhor_jogada`` para os dois lados; basta aplicar com o ``jogador``
    correto (+1 / -1) para preservar a contagem de turnos. Se a partida
    terminar antes do alvo (raro para K pequeno), refaz.
    """
    while True:
        estado = EstadoTabuleiro(LINHAS, COLUNAS)
        # Sincroniza o random.choice de empate dentro do minimax_pontinhos
        _random.seed(int(rng.integers(0, 2**31 - 1)))
        jogador = 1
        tracos_jogados = 0
        terminou_cedo = False
        while tracos_jogados < num_tracos_alvo:
            if estado.esta_terminal():
                terminou_cedo = True
                break
            label = melhor_jogada(estado, profundidade=profundidade)
            fechadas = estado.aplicar_traco(label, jogador=jogador)
            tracos_jogados += 1
            if fechadas == 0:
                jogador = -jogador
        if not terminou_cedo:
            return matriz_para_neutro(estado.matriz)


def gerar_amostra(args: Tuple[int, int, int, int, int]) -> Tuple[bytes, int, int]:
    """Worker da Fase 1. Retorna ``(estado_neutro_bytes, generation_mode, K)``.

    ``args = (faixa_min, faixa_max, modo, profundidade_autoplay, seed)``. Sorteia
    K em ``[faixa_min, faixa_max]`` (inclusivo) e gera 1 estado conforme o
    ``modo``. Retornar ``bytes`` (em vez de ``np.ndarray``) economiza memoria
    ao trafegar pelos pipes do multiprocessing.
    """
    faixa_min, faixa_max, modo, profundidade, seed = args
    rng = np.random.default_rng(seed)
    K = int(rng.integers(faixa_min, faixa_max + 1))
    if modo == MODO_ALEATORIO:
        mat = _gerar_aleatorio(K, rng)
    else:
        mat = _gerar_autoplay(K, profundidade, rng)
    return mat.tobytes(), modo, K


def calcular_scores(args: Tuple[bytes, int]) -> Tuple[str, np.ndarray]:
    """Worker da Fase 2. Retorna ``(rotulo, scores_(N_LABELS,)_float32)``.

    ``args = (estado_neutro_bytes, profundidade)``. O ``minimax_pontinhos``
    so checa ``!= 0`` nas celulas, entao a matriz neutra ``{0, 1, 8, 9}`` e
    aceita diretamente sem reconverter para formato live.

    Slots correspondentes a tracos invalidos (ja preenchidos) recebem
    ``SCORE_INDISPONIVEL = -1e9``.
    """
    estado_bytes, profundidade = args
    mat = np.frombuffer(estado_bytes, dtype=np.int8).reshape(ALTURA, LARGURA)

    estado = EstadoTabuleiro(LINHAS, COLUNAS)
    estado.matriz = mat.copy()

    if estado.esta_terminal():
        scores = np.full(N_LABELS, SCORE_INDISPONIVEL, dtype=np.float32)
        return "", scores

    rotulo, scores_dict = melhor_jogada_com_scores(estado, profundidade=profundidade)
    scores = np.full(N_LABELS, SCORE_INDISPONIVEL, dtype=np.float32)
    for label, valor in scores_dict.items():
        scores[INDICE_LABEL[label]] = float(valor)
    return rotulo, scores

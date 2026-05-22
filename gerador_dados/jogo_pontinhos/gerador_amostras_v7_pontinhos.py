"""Workers para o notebook ``Geracao_Amostras_v7_adaptativo.ipynb``.

Pipeline V7 — Diversidade Adaptativa em Cascata (DAC):

- **Fase 1 (`jogar_partida_completa`)**: cada chamada joga UMA partida do
  zero ate o terminal usando Minimax com profundidade adaptativa por tensao
  estrutural e desempate por Boltzmann sampling. A funcao retorna
  EXATAMENTE 30 snapshots (estados a t=1..30; descarta t=0 e t=31).
- **Fase 2 (`calcular_scores_v7`)**: para um estado neutro ja gerado,
  calcula via Minimax(profundidade fixa) o vetor de scores das 31 jogadas
  canonicas e o rotulo da melhor jogada (argmax com desempate aleatorio).

O modulo nao define faixas/quotas — a distribuicao por numero de tracos
emerge naturalmente porque cada partida cobre todos os t∈[1,30].
"""
from __future__ import annotations

import math
import random as _random
from typing import List, Tuple

import numpy as np

from gerador_dados.jogo_pontinhos.minimax_pontinhos import (
    _scores_de_todas_jogadas,
    melhor_jogada_com_scores,
    minimax,
)
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    todos_labels_canonicos,
)


# ============================================================================
# Constantes do jogo (tabuleiro pequeno, 4x3 caixas)
# ============================================================================
LINHAS = 4
COLUNAS = 3
ALTURA = 2 * LINHAS + 1   # 9
LARGURA = 2 * COLUNAS + 1  # 7

LABELS_CANONICOS: list[str] = todos_labels_canonicos(LINHAS, COLUNAS)
INDICE_LABEL: dict[str, int] = {lab: i for i, lab in enumerate(LABELS_CANONICOS)}
N_LABELS = len(LABELS_CANONICOS)  # 31

SCORE_INDISPONIVEL = -1_000_000_000.0   # = -1e9 (jogadas invalidas / nao calculado)
DEPTH_NAO_CALCULADO = 0                  # sentinela para depth_melhor_jogada antes da Fase 2

ESTADOS_POR_PARTIDA = 30  # snapshots emitidos por partida (t=1..30)


# ============================================================================
# Tensao estrutural e profundidade adaptativa
# ============================================================================

def tensao(estado: EstadoTabuleiro) -> float:
    """Retorna τ = 4·c3 + 2·c2 + 0.5·c1.

    `c_k` = numero de caixas com exatamente k lados preenchidos (k∈{1,2,3}).
    Caixas ja fechadas (4 lados) e intactas (0 lados) nao contribuem.

    τ traduz a "pressao estrategica" do tabuleiro: caixas a 3 lados sao
    ameacas imediatas (peso 4), caixas a 2 lados sao decisoes potenciais
    de cadeia (peso 2), caixas a 1 lado sao apenas inicios de estrutura.
    """
    m = estado.matriz
    H, W = m.shape
    c1 = c2 = c3 = 0
    for cr in range(1, H, 2):       # centros de caixa: impar x impar
        for cc in range(1, W, 2):
            if m[cr, cc] != 0:      # caixa ja fechada
                continue
            lados = (
                int(m[cr - 1, cc] != 0)  # lado superior
                + int(m[cr + 1, cc] != 0)  # lado inferior
                + int(m[cr, cc - 1] != 0)  # lado esquerdo
                + int(m[cr, cc + 1] != 0)  # lado direito
            )
            if lados == 1:
                c1 += 1
            elif lados == 2:
                c2 += 1
            elif lados == 3:
                c3 += 1
    return 4.0 * c3 + 2.0 * c2 + 0.5 * c1


def mapear_profundidade(tau: float, p_min: int = 1, p_max: int = 8) -> int:
    """Mapeia τ → profundidade do Minimax: p = clamp(1 + ⌈τ/4⌉, p_min, p_max).

    τ=0 → p=1 (tabuleiro vazio, deliberacao desnecessaria).
    τ≈12 → p=4 (midgame com algumas cadeias formando).
    τ≥28 → p=8 (endgame com varias caixas a 3 lados; saturacao).
    """
    p = 1 + int(math.ceil(tau / 4.0))
    return max(p_min, min(p_max, p))


def temperatura(qtd_tracos: int) -> float:
    """Temperatura T do Boltzmann sampling em funcao do n. de tracos jogados.

    T alta no inicio (explora; suaviza diferencas pequenas entre lances quase
    equivalentes) e baixa no fim (preserva qualidade quando uma jogada e
    claramente vencedora).

    Valores aumentados em 2026-05-22 para retardar saturacao natural do espaco
    de estados: a rodada anterior mostrou queda de 61% -> 54% novos/NPZ ao
    longo de 158 NPZs, o que e saudavel, mas temperaturas mais altas ampliam
    a diversidade de trajetorias e reduzem a taxa de colisao entre rodadas.
    """
    if qtd_tracos < 8:
        return 2.0   # era 1.5 — mais exploracao no opening
    if qtd_tracos < 18:
        return 1.2   # era 0.8 — midgame mais variado
    if qtd_tracos < 26:
        return 0.8   # era 0.5 — endgame ainda explora
    return 0.4       # era 0.2 — ultimas jogadas menos deterministicas


# ============================================================================
# Conversao de matriz live (-1,0,1,8) → neutra (0,1,8,9)
# ============================================================================

def matriz_para_neutro(mat_live: np.ndarray) -> np.ndarray:
    """Converte a matriz "live" (com sinal de jogador) para o formato neutro
    do contrato §contexto_1_geracao_dataset: ``{0, 1, 8, 9}``.

    Conversao por POSICAO (par/impar), NAO por valor: evita ambiguidade entre
    traco do J1 (`+1`) e caixa fechada (`+1`).
    """
    out = np.zeros((ALTURA, LARGURA), dtype=np.int8)
    for r in range(ALTURA):
        for c in range(LARGURA):
            v = mat_live[r, c]
            if r % 2 == 0 and c % 2 == 0:
                out[r, c] = 8                      # ponto fixo
            elif r % 2 == 1 and c % 2 == 1:
                out[r, c] = 1 if v != 0 else 0      # interior de caixa
            else:
                out[r, c] = 9 if v != 0 else 0      # aresta
    return out


# ============================================================================
# Worker da Fase 1 — uma partida completa = 30 snapshots
# ============================================================================

def _vetor_score_jogada(scores_dict: dict[str, int]) -> np.ndarray:
    """Empacota ``{label: score}`` no vetor (31,) float32 com `-1e9` nos
    slots invalidos, na ordem canonica (`LABELS_CANONICOS`).
    """
    vetor = np.full(N_LABELS, SCORE_INDISPONIVEL, dtype=np.float32)
    for label, valor in scores_dict.items():
        vetor[INDICE_LABEL[label]] = float(valor)
    return vetor


def _amostrar_boltzmann(scores_dict: dict[str, int],
                         temperatura_T: float,
                         rng: np.random.Generator) -> str:
    """Sorteia um label proporcionalmente a softmax(score / T).

    Para T pequeno (T→0) tende ao argmax; para T grande (T→∞) tende ao
    uniforme. Estabilidade numerica: subtrai max antes de exponenciar.
    """
    labels = list(scores_dict.keys())
    valores = np.array([scores_dict[l] for l in labels], dtype=np.float64)
    z = valores / max(temperatura_T, 1e-6)
    z -= z.max()
    p = np.exp(z)
    p /= p.sum()
    idx = int(rng.choice(len(labels), p=p))
    return labels[idx]


def jogar_partida_completa(
    seed: int,
) -> List[Tuple[bytes, int, bytes, int, int]]:
    """Joga uma partida do zero ate o terminal, emitindo 30 snapshots.

    Cada snapshot e uma tupla ``(mat_neutra_bytes, qtd_tracos, score_jogada_bytes,
    depth_jogada, depth_geracao)`` correspondente ao estado a t=k para
    k∈[1,30]. A semantica dos campos:

    - ``mat_neutra_bytes``: matriz neutra ``{0,1,8,9}`` em bytes.
    - ``qtd_tracos`` = k (numero de tracos APOS a k-esima jogada).
    - ``score_jogada``: vetor (31,) float32 dos scores Minimax CALCULADOS no
      estado a t=k (decidem a jogada que levara a t=k+1).
    - ``depth_jogada``: profundidade Minimax usada NESTE estado (t=k).
    - ``depth_geracao``: profundidade Minimax usada no ESTADO ANTERIOR
      (t=k-1) — i.e., a profundidade que GEROU este estado. Equivalente a
      ``depth_jogada[k-1]``.

    Estados a t=0 (vazio) e t=31 (terminal) sao DESCARTADOS:
    - t=0 e sempre identico, gravar e desperdicio.
    - t=31 e terminal, nao ha jogada a aprender.
    """
    rng = np.random.default_rng(seed)
    # Sincroniza o `random.choice` interno do Minimax com a seed externa
    _random.seed(int(rng.integers(0, 2**31 - 1)))

    estado = EstadoTabuleiro(LINHAS, COLUNAS)
    snapshots: List[Tuple[bytes, int, bytes, int, int]] = []
    jogador = 1

    # depth_geracao do PRIMEIRO snapshot (t=1) e a profundidade usada no
    # estado vazio (t=0). Como vamos calcula-la na primeira iteracao do
    # loop, inicializamos com `None` e gravamos o snapshot com a depth da
    # iteracao corrente — depth_geracao do snapshot atual = depth_jogada da
    # iteracao anterior.
    depth_iter_anterior: int | None = None

    while not estado.esta_terminal():
        # ----- Estado atual: t = qtd_tracos_atual -----
        n_tracos_atual = N_LABELS - len(estado.tracos_disponiveis())

        tau = tensao(estado)
        p_atual = mapear_profundidade(tau)
        T = temperatura(n_tracos_atual)

        # Calcula scores Minimax com profundidade adaptativa
        scores_dict = _scores_de_todas_jogadas(estado, p_atual)

        # Snapshot do estado ATUAL (que ja existe na arvore — ainda nao
        # aplicamos a jogada deste turno)
        if 1 <= n_tracos_atual <= 30:
            mat_neutra = matriz_para_neutro(estado.matriz)
            score_vetor = _vetor_score_jogada(scores_dict)
            depth_geracao = (
                depth_iter_anterior if depth_iter_anterior is not None else p_atual
            )
            snapshots.append((
                mat_neutra.tobytes(),
                int(n_tracos_atual),
                score_vetor.tobytes(),
                int(p_atual),
                int(depth_geracao),
            ))

        # ----- Boltzmann sampling: escolhe a jogada -----
        label_escolhido = _amostrar_boltzmann(scores_dict, T, rng)

        # ----- Aplica a jogada (transicao para t+1) -----
        fechadas = estado.aplicar_traco(label_escolhido, jogador=jogador)
        if fechadas == 0:
            jogador = -jogador

        # Memoriza profundidade desta iteracao para o `depth_geracao` do
        # proximo snapshot
        depth_iter_anterior = p_atual

    # Sanidade: 30 snapshots por partida (t=1..30). Em raras situacoes
    # (partida que termina antes do tabuleiro completo — improvavel neste
    # jogo) podemos ter menos.
    return snapshots


# ============================================================================
# Worker da Fase 2 — calcula melhor jogada com profundidade fixa
# ============================================================================

def calcular_scores_v7(args: Tuple[bytes, int]) -> Tuple[str, np.ndarray, int]:
    """Recebe ``(estado_neutro_bytes, profundidade)`` e devolve
    ``(rotulo, scores_(31,)_float32, profundidade_usada)``.

    Slots correspondentes a tracos invalidos (ja preenchidos) recebem
    ``SCORE_INDISPONIVEL``. Empates no argmax sao desempatados aleatoriamente
    pela funcao ``melhor_jogada_com_scores`` (usa `random.choice` interno).
    """
    estado_bytes, profundidade = args
    mat = np.frombuffer(estado_bytes, dtype=np.int8).reshape(ALTURA, LARGURA)

    estado = EstadoTabuleiro(LINHAS, COLUNAS)
    estado.matriz = mat.copy()

    if estado.esta_terminal():
        scores = np.full(N_LABELS, SCORE_INDISPONIVEL, dtype=np.float32)
        return "", scores, int(profundidade)

    rotulo, scores_dict = melhor_jogada_com_scores(estado, profundidade=profundidade)
    scores = _vetor_score_jogada(scores_dict)
    return rotulo, scores, int(profundidade)

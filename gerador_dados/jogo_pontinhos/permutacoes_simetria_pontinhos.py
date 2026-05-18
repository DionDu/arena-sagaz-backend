"""Permutacoes de simetria do tabuleiro do Jogo dos Pontinhos (4x3 caixas).

Expoe `aplicar_simetria(d, sym_id)` — transforma um dict NPZ v2-a3 aplicando
uma das 4 simetrias do tabuleiro:

    sym_id=0  identidade     (copia sem alteracao)
    sym_id=1  reflexao H     (coluna c → n_cols−1−c, i.e., esquerda↔direita)
    sym_id=2  reflexao V     (linha r → n_rows−1−r, i.e., cima↔baixo)
    sym_id=3  rotacao 180    (r,c → n_rows−1−r, n_cols−1−c)

Campos TRANSFORMADOS:
    estados             (N, 9, 7) int8    — flip de eixos da matriz crua
    canais              (N, 4, 3, 12) int8 — flip de eixos + troca de slots de aresta:
                            refH:  K=2 (esq) <-> K=3 (dir)
                            refV:  K=0 (topo) <-> K=1 (base)
                            r180:  ambas as trocas
                            K=4..11 sao invariantes (topologia + broadcast global)
    score_melhor_jogada (N, 31) float32   — permutacao dos 31 slots de aresta
    score_jogada        (N, 31) float32   — idem
    melhor_jogada       (N,) U5           — novo rotulo canonico da melhor jogada

Campos PRESERVADOS (copia direta):
    qtd_tracos, depth_jogada, depth_geracao, depth_melhor_jogada,
    labels_canonicos, nomes_canais,
    qtd_cadeias_longas, total_caixas_cadeias_longas, tamanho_max_cadeia_longa

Canal K=11 (paridade_cadeia_longa_impar) e broadcast global — o numero de
cadeias longas e invariante sob reflexoes e rotacoes, e o flip de eixo nao
altera o valor uniforme. Preservado bit-a-bit sem tratamento especial.

Mapeamento de arestas no tabuleiro pequeno (matriz 9x7):
    H_{r}_{c} — aresta horizontal na linha r (par), coluna c (impar)
    V_{r}_{c} — aresta vertical na linha r (impar), coluna c (par)
    refH: c → 6-c   |   refV: r → 8-r   |   r180: r → 8-r, c → 6-c
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np


# ---------------------------------------------------------------------------
# Helpers internos: transformacao de rotulos de aresta
# ---------------------------------------------------------------------------

def _transform_label(lbl: str, sym_id: int) -> str:
    """Transforma o rotulo de aresta (ex: 'H_0_1' -> 'H_0_5' sob refH)."""
    if not lbl or sym_id == 0:
        return lbl
    parts = lbl.split('_')
    edge_type, row, col = parts[0], int(parts[1]), int(parts[2])
    if sym_id == 1:    # refH: coluna j -> 6-j
        col = 6 - col
    elif sym_id == 2:  # refV: linha i -> 8-i
        row = 8 - row
    elif sym_id == 3:  # r180: ambos
        row = 8 - row
        col = 6 - col
    return f'{edge_type}_{row}_{col}'


def _build_permutation(labels_canonicos: np.ndarray, sym_id: int) -> np.ndarray:
    """Constroi vetor de permutacao (31,): perm[i] = novo indice da aresta i.

    scores_new[:, perm[i]] = scores_old[:, i]  para todo i.
    """
    if sym_id == 0:
        return np.arange(len(labels_canonicos), dtype=np.intp)

    labels: List[str] = [
        s.decode('utf-8') if isinstance(s, bytes) else str(s)
        for s in labels_canonicos
    ]
    label_to_idx = {lbl: i for i, lbl in enumerate(labels)}

    perm = np.empty(len(labels), dtype=np.intp)
    for i, lbl in enumerate(labels):
        new_lbl = _transform_label(lbl, sym_id)
        perm[i] = label_to_idx[new_lbl]
    return perm


# ---------------------------------------------------------------------------
# Transformacoes individuais de campos
# ---------------------------------------------------------------------------

def _transform_estados(estados: np.ndarray, sym_id: int) -> np.ndarray:
    """Flip de eixos na matriz crua (N, 9, 7)."""
    if sym_id == 0:
        return estados.copy()
    if sym_id == 1:   # refH: flip colunas
        return estados[:, :, ::-1].copy()
    if sym_id == 2:   # refV: flip linhas
        return estados[:, ::-1, :].copy()
    if sym_id == 3:   # r180: flip ambos
        return estados[:, ::-1, ::-1].copy()
    raise ValueError(f'sym_id invalido: {sym_id}')


def _transform_canais(canais: np.ndarray, sym_id: int) -> np.ndarray:
    """Aplica simetria ao tensor de canais (N, 4, 3, 12).

    Apos o flip espacial dos eixos, os slots de aresta geometrica sao
    trocados para refletir a nova orientacao de cada caixa:
      refH: K=2 (esq) <-> K=3 (dir)   [as colunas foram espelhadas]
      refV: K=0 (topo) <-> K=1 (base) [as linhas foram espelhadas]
      r180: ambas as trocas
    K=4..11 sao invariantes por serem propriedades topologicas ou broadcast.
    """
    if sym_id == 0:
        return canais.copy()

    if sym_id == 1:   # refH: flip axis de colunas (axis=2)
        out = canais[:, :, ::-1, :].copy()
        k2 = out[:, :, :, 2].copy()
        out[:, :, :, 2] = out[:, :, :, 3]
        out[:, :, :, 3] = k2
        return out

    if sym_id == 2:   # refV: flip axis de linhas (axis=1)
        out = canais[:, ::-1, :, :].copy()
        k0 = out[:, :, :, 0].copy()
        out[:, :, :, 0] = out[:, :, :, 1]
        out[:, :, :, 1] = k0
        return out

    if sym_id == 3:   # r180: flip ambos, ambas as trocas
        out = canais[:, ::-1, ::-1, :].copy()
        k0 = out[:, :, :, 0].copy()
        out[:, :, :, 0] = out[:, :, :, 1]
        out[:, :, :, 1] = k0
        k2 = out[:, :, :, 2].copy()
        out[:, :, :, 2] = out[:, :, :, 3]
        out[:, :, :, 3] = k2
        return out

    raise ValueError(f'sym_id invalido: {sym_id}')


def _transform_scores(scores: np.ndarray, perm: np.ndarray) -> np.ndarray:
    """Permuta os 31 slots de score: out[:, perm[i]] = scores[:, i]."""
    out = np.empty_like(scores)
    out[:, perm] = scores
    return out


def _transform_melhor_jogada(
    melhor_jogada: np.ndarray,
    perm: np.ndarray,
    labels_canonicos: np.ndarray,
) -> np.ndarray:
    """Permuta os rotulos de melhor_jogada via perm. Preserva '' intacto."""
    labels: List[str] = [
        s.decode('utf-8') if isinstance(s, bytes) else str(s)
        for s in labels_canonicos
    ]
    label_to_idx = {lbl: i for i, lbl in enumerate(labels)}

    result = melhor_jogada.copy()
    for n in range(len(melhor_jogada)):
        lbl = melhor_jogada[n]
        if isinstance(lbl, bytes):
            lbl = lbl.decode('utf-8')
        lbl = str(lbl)
        if not lbl:
            continue
        idx = label_to_idx[lbl]
        result[n] = labels[perm[idx]]
    return result


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def aplicar_simetria(d: Dict[str, np.ndarray], sym_id: int) -> Dict[str, np.ndarray]:
    """Aplica simetria sym_id ao dict NPZ v2-a3 e retorna novo dict.

    Args:
        d:      dict como retornado por `dict(np.load(path, allow_pickle=False))`.
                Deve conter os campos obrigatorios do schema v2-a3:
                  estados, canais, score_melhor_jogada, score_jogada,
                  melhor_jogada, labels_canonicos.
                Campos opcionais (qtd_tracos, depth_*, nomes_canais,
                qtd_cadeias_longas, total_caixas_cadeias_longas,
                tamanho_max_cadeia_longa) sao copiados se presentes.
        sym_id: 0=identidade, 1=refH, 2=refV, 3=r180.

    Returns:
        Novo dict com mesmos campos e arrays transformados ou copiados.

    Raises:
        ValueError: sym_id fora de {0,1,2,3} ou campo obrigatorio ausente.
    """
    if sym_id not in (0, 1, 2, 3):
        raise ValueError(f'sym_id deve ser 0, 1, 2 ou 3; obtido: {sym_id}')

    campos_obrigatorios = {
        'estados', 'canais', 'score_melhor_jogada', 'score_jogada',
        'melhor_jogada', 'labels_canonicos',
    }
    faltando = campos_obrigatorios - set(d.keys())
    if faltando:
        raise ValueError(f'Campos obrigatorios ausentes: {sorted(faltando)}')

    perm = _build_permutation(d['labels_canonicos'], sym_id)

    out: Dict[str, np.ndarray] = {}

    # Campos transformados
    out['estados'] = _transform_estados(d['estados'], sym_id)
    out['canais'] = _transform_canais(d['canais'], sym_id)
    out['score_melhor_jogada'] = _transform_scores(d['score_melhor_jogada'], perm)
    out['score_jogada'] = _transform_scores(d['score_jogada'], perm)
    out['melhor_jogada'] = _transform_melhor_jogada(
        d['melhor_jogada'], perm, d['labels_canonicos']
    )

    # Campos preservados (copiar se presentes)
    for campo in (
        'qtd_tracos', 'depth_jogada', 'depth_geracao', 'depth_melhor_jogada',
        'labels_canonicos', 'nomes_canais',
        'qtd_cadeias_longas', 'total_caixas_cadeias_longas', 'tamanho_max_cadeia_longa',
    ):
        if campo in d:
            out[campo] = d[campo].copy()

    return out


__all__ = ['aplicar_simetria']

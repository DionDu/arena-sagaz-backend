"""Oráculo EXATO do Jogo dos Pontinhos por *tablebase* (análise retrógrada).

Resolve o jogo POR COMPLETO num tamanho pequeno: para CADA configuração possível
de arestas (subconjunto dos `n` traços), calcula o **valor exato** do jogo sob
jogo ótimo de ambos os lados — o diferencial futuro de caixas (mover − adversário),
contando só caixas fechadas dali para frente. Depois, consultar o valor de
qualquer posição é um **lookup O(1)** num array, sem busca.

Convenção idêntica à do `minimax_pontinhos._scores_de_todas_jogadas`:
`valor(S)` = melhor diferencial futuro para o jogador a mover em S; um lance que
fecha caixa MANTÉM o turno (`+caixas + valor(filho)`), um lance que não fecha
PASSA o turno (`-valor(filho)`). Terminal (tabuleiro cheio) = 0.

Estado = bitmask dos traços preenchidos. O bit `i` corresponde ao traço
`todos_labels_canonicos(linhas, colunas)[i]` — a MESMA ordem usada pelo gerador
e pelo treino (índice da classe no tensor). Assim a tabela é um *drop-in* exato
para a forense: `score_de_jogada(S, e) == _scores_de_todas_jogadas(estado)[label_e]`.

Construção do 4×3 (31 arestas): 2^31 ≈ 2,1 bi estados, int8 = 2 GiB em RAM/disco.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    TAMANHOS,
    todos_labels_canonicos,
)


# ----------------------------------------------------------------------------
# Mapeamento aresta <-> caixa (a "física" do jogo, derivada do tabuleiro real).
# ----------------------------------------------------------------------------
def construir_mapeamento(linhas: int, colunas: int):
    """Devolve (labels, edge_rc, n_edges, edge_box_masks, edge_box_counts, box_masks).

    - labels[i]      : label do traço de bit i (ordem canônica).
    - edge_rc[i]     : (r, c) na matriz do traço de bit i.
    - edge_box_masks : (n_edges, 2) int64 — máscaras das até 2 caixas que a aresta
                       i toca (cada máscara = OR dos 4 bits das arestas da caixa).
    - edge_box_counts: (n_edges,) int — quantas caixas a aresta i toca (1 ou 2).
    - box_masks      : (n_boxes,) int64 — máscara das 4 arestas de cada caixa.
    """
    labels = todos_labels_canonicos(linhas, colunas)
    idx = {lbl: i for i, lbl in enumerate(labels)}
    n_edges = len(labels)
    edge_rc = []
    for lbl in labels:
        _t, r_str, c_str = lbl.split("_")
        edge_rc.append((int(r_str), int(c_str)))

    altura = 2 * linhas + 1
    largura = 2 * colunas + 1

    # Cada caixa (centro ímpar,ímpar) tem 4 arestas: cima/baixo (H) e esq/dir (V).
    box_masks_list: list[int] = []
    edge_to_boxes: dict[int, list[int]] = {i: [] for i in range(n_edges)}
    for br in range(1, altura, 2):
        for bc in range(1, largura, 2):
            arestas_lbl = [
                f"H_{br - 1}_{bc}",   # cima
                f"H_{br + 1}_{bc}",   # baixo
                f"V_{br}_{bc - 1}",   # esquerda
                f"V_{br}_{bc + 1}",   # direita
            ]
            bits = [idx[l] for l in arestas_lbl]
            mask = 0
            for b in bits:
                mask |= (1 << b)
            box_id = len(box_masks_list)
            box_masks_list.append(mask)
            for b in bits:
                edge_to_boxes[b].append(mask)

    edge_box_masks = np.zeros((n_edges, 2), dtype=np.int64)
    edge_box_counts = np.zeros(n_edges, dtype=np.int64)
    for e in range(n_edges):
        ms = edge_to_boxes[e]
        edge_box_counts[e] = len(ms)
        for k, m in enumerate(ms):
            edge_box_masks[e, k] = m

    box_masks = np.array(box_masks_list, dtype=np.int64)
    return labels, edge_rc, n_edges, edge_box_masks, edge_box_counts, box_masks


# ----------------------------------------------------------------------------
# Núcleo da DP retrógrada (compilado por Numba). Define em runtime para não
# exigir numba só para CONSULTAR uma tabela já pronta.
# ----------------------------------------------------------------------------
def _nucleo_build():
    from numba import njit  # import tardio

    @njit(cache=True)
    def _build(n_edges, edge_box_masks, edge_box_counts):
        N = np.int64(1) << n_edges
        val = np.empty(N, dtype=np.int8)
        full = N - 1
        val[full] = 0
        s = full - 1
        while s >= 0:
            best = -127
            e = 0
            while e < n_edges:
                bit = np.int64(1) << e
                if (s & bit) == 0:
                    child = s | bit
                    b = 0
                    cnt = edge_box_counts[e]
                    k = 0
                    while k < cnt:
                        m = edge_box_masks[e, k]
                        if (child & m) == m:
                            b += 1
                        k += 1
                    cv = val[child]
                    if b > 0:
                        q = b + cv
                    else:
                        q = -cv
                    if q > best:
                        best = q
                e += 1
            val[s] = best
            s -= 1
        return val

    return _build


def construir_tablebase(tamanho: str = "pequeno", saida: Path | None = None,
                        verboso: bool = True) -> np.ndarray:
    """Constrói a tablebase completa e (opcional) salva em .npy."""
    linhas, colunas = TAMANHOS[tamanho]
    _labels, _rc, n_edges, ebm, ebc, _bm = construir_mapeamento(linhas, colunas)
    if verboso:
        print(f"Construindo tablebase {tamanho} ({linhas}x{colunas}): "
              f"{n_edges} arestas -> 2^{n_edges} = {1 << n_edges:,} estados "
              f"({(1 << n_edges) / 2**30:.2f} GiB int8)", flush=True)
    import time
    t0 = time.perf_counter()
    build = _nucleo_build()
    val = build(np.int64(n_edges), ebm, ebc)
    if verboso:
        print(f"  pronto em {(time.perf_counter() - t0) / 60:.2f} min "
              f"(valor da posição vazia = {int(val[0])})", flush=True)
    if saida is not None:
        saida = Path(saida)
        saida.parent.mkdir(parents=True, exist_ok=True)
        np.save(saida, val)
        if verboso:
            print(f"  salvo: {saida}  ({saida.stat().st_size / 2**30:.2f} GiB)", flush=True)
    return val


# ----------------------------------------------------------------------------
# Consulta (lookup O(1)) + ponte com o EstadoTabuleiro.
# ----------------------------------------------------------------------------
def carregar(path: str | Path, mmap: bool = True) -> np.ndarray:
    """Carrega a tablebase (mmap por padrão — não puxa 2 GB para a RAM de uma vez)."""
    return np.load(str(path), mmap_mode="r" if mmap else None)


def matriz_para_bitmask(matriz: np.ndarray, linhas: int, colunas: int,
                        edge_rc: list[tuple[int, int]] | None = None) -> int:
    """Converte a matriz do EstadoTabuleiro no bitmask de arestas preenchidas."""
    if edge_rc is None:
        _l, edge_rc, _n, _a, _b, _c = construir_mapeamento(linhas, colunas)
    s = 0
    for i, (r, c) in enumerate(edge_rc):
        if matriz[r, c] != 0:
            s |= (1 << i)
    return s


def scores_de_todas_jogadas_exato(val: np.ndarray, s: int, n_edges: int,
                                  edge_box_masks: np.ndarray,
                                  edge_box_counts: np.ndarray) -> dict[int, int]:
    """Q-value EXATO de cada lance disponível em S (índice da aresta -> score).

    Espelha `minimax_pontinhos._scores_de_todas_jogadas`, mas via lookup O(1).
    """
    out: dict[int, int] = {}
    for e in range(n_edges):
        bit = 1 << e
        if s & bit:
            continue
        child = s | bit
        b = 0
        for k in range(int(edge_box_counts[e])):
            m = int(edge_box_masks[e, k])
            if (child & m) == m:
                b += 1
        cv = int(val[child])
        out[e] = (b + cv) if b > 0 else (-cv)
    return out

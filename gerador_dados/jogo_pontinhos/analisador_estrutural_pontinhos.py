"""Analisador estrutural do tabuleiro do Jogo dos Pontinhos.

Modulo responsavel por extrair os 12 canais de entrada da CNN a partir da
matriz crua expandida `(9, 7) int8`. Espelha fielmente o contrato algoritmico
de `specs/004-melhoria-geracao-dados-cnn/contracts/canais_estruturais.md`
(revisao 2026-05-13 — canal 12 adicionado).

Ordem canonica dos canais (mesma de PRD §4.2):

    K=0  aresta_topo
    K=1  aresta_base
    K=2  aresta_esquerda
    K=3  aresta_direita
    K=4  caixa_fechada
    K=5  eh_grau3
    K=6  eh_grau2
    K=7  em_cadeia_curta            (componente de comprimento exatamente 2)
    K=8  em_cadeia_longa            (componente de comprimento >= 3)
    K=9  em_loop                    (todos os nos do componente tem grau 2)
    K=10 em_cadeia_aberta_uma_ponta (exatamente 1 ponta capturavel)
    K=11 paridade_cadeia_longa_impar (broadcast global: 1 se qtd cadeias longas impar)

Dominio dos canais: `{0, 1}` em todas as posicoes.
K=11 e broadcast: todas as 12 celulas do tensor recebem o mesmo valor.
Dominio do estado de entrada (contexto_1_geracao_dataset): `{0, 1, 8, 9}`.

API publica:
    NOMES_CANAIS:        Tuple[str, ...] de 12 entradas, ordem acima.
    extrair_canais(M)    -> np.ndarray  shape (4, 3, 12) int8
    extrair_stats_cadeias(M) -> tuple[int, int, int]
        (qtd_cadeias_longas, total_caixas_cadeias_longas, tamanho_max_cadeia_longa)
"""
from __future__ import annotations

from collections import deque
from typing import Dict, List, Set, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Constantes publicas
# ---------------------------------------------------------------------------

NOMES_CANAIS: Tuple[str, ...] = (
    "aresta_topo",
    "aresta_base",
    "aresta_esquerda",
    "aresta_direita",
    "caixa_fechada",
    "eh_grau3",
    "eh_grau2",
    "em_cadeia_curta",
    "em_cadeia_longa",
    "em_loop",
    "em_cadeia_aberta_uma_ponta",
    "paridade_cadeia_longa_impar",
)
"""Nomes canonicos dos 12 canais. Gravados em `nomes_canais` no NPZ Fase A.3."""

N_LINHAS: int = 4
N_COLUNAS: int = 3
N_CANAIS: int = 12

# ---------------------------------------------------------------------------
# Helpers fundamentais (espelham `canais_estruturais.md` §2)
# ---------------------------------------------------------------------------

def _caixa_fechada(M: np.ndarray, r: int, c: int) -> bool:
    """True se a caixa (r, c) esta fechada. Dataset NUNCA contem -1."""
    return M[2 * r + 1, 2 * c + 1] == 1


def _grau(M: np.ndarray, r: int, c: int) -> int:
    """Grau da caixa (r, c): nro de arestas vizinhas com valor 9. Caixa fechada = 4.

    Nota: cada comparacao retorna `np.bool_`. Em numpy >= 2 (no Windows c/ Python 3.9
    aqui usado), `np.bool_ + np.bool_ == np.bool_` (OR logico, nao soma aritmetica).
    Por isso somamos `int(...)` por termo.
    """
    if int(M[2 * r + 1, 2 * c + 1]) == 1:
        return 4
    return (
        int(M[2 * r, 2 * c + 1] == 9)
        + int(M[2 * r + 2, 2 * c + 1] == 9)
        + int(M[2 * r + 1, 2 * c] == 9)
        + int(M[2 * r + 1, 2 * c + 2] == 9)
    )


def _aresta_livre_entre(M: np.ndarray, a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    """Existe aresta livre (== 0) compartilhada entre as caixas adjacentes a e b?

    Considera apenas pares ortogonalmente vizinhos (compartilham um lado).
    """
    (ra, ca), (rb, cb) = a, b
    if ra == rb and abs(ca - cb) == 1:
        # vizinhos horizontais — aresta vertical entre eles
        c_min = min(ca, cb)
        return M[2 * ra + 1, 2 * c_min + 2] == 0
    if ca == cb and abs(ra - rb) == 1:
        # vizinhos verticais — aresta horizontal entre eles
        r_min = min(ra, rb)
        return M[2 * r_min + 2, 2 * ca + 1] == 0
    return False


def _vizinhas_caixa(r: int, c: int) -> List[Tuple[int, int]]:
    """Lista das caixas ortogonalmente adjacentes a (r, c) dentro do tabuleiro 4x3."""
    cands = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
    return [
        (rr, cc) for (rr, cc) in cands if 0 <= rr < N_LINHAS and 0 <= cc < N_COLUNAS
    ]


# ---------------------------------------------------------------------------
# Helper interno: BFS no grafo dual (compartilhado por extrair_canais e
# extrair_stats_cadeias)
# ---------------------------------------------------------------------------

def _bfs_dual(
    M: np.ndarray,
    grau_de: Dict[Tuple[int, int], int],
    fechada_de: Dict[Tuple[int, int], bool],
) -> Tuple[
    Dict[Tuple[int, int], List[Tuple[int, int]]],
    List[List[Tuple[int, int]]],
]:
    """Constroi o grafo dual e retorna (adj, componentes).

    Nos do grafo dual: caixas abertas com grau 2.
    Arestas: pares de nos adjacentes que compartilham aresta livre.
    """
    nos_grau2: Set[Tuple[int, int]] = {
        rc for rc, g in grau_de.items() if g == 2 and not fechada_de[rc]
    }

    adj: Dict[Tuple[int, int], List[Tuple[int, int]]] = {n: [] for n in nos_grau2}
    for n in nos_grau2:
        for v in _vizinhas_caixa(*n):
            if v in nos_grau2 and _aresta_livre_entre(M, n, v):
                adj[n].append(v)

    visitado: Set[Tuple[int, int]] = set()
    componentes: List[List[Tuple[int, int]]] = []
    for n in nos_grau2:
        if n in visitado:
            continue
        comp: List[Tuple[int, int]] = []
        fila = deque([n])
        visitado.add(n)
        while fila:
            u = fila.popleft()
            comp.append(u)
            for v in adj[u]:
                if v not in visitado:
                    visitado.add(v)
                    fila.append(v)
        componentes.append(comp)

    return adj, componentes


def _eh_cadeia_longa(
    comp: List[Tuple[int, int]],
    adj: Dict[Tuple[int, int], List[Tuple[int, int]]],
) -> bool:
    """True se o componente e uma cadeia longa (comprimento >= 3, nao loop, nao complexa)."""
    if len(comp) < 3:
        return False
    graus_comp = [len(adj[u]) for u in comp]
    eh_loop = all(g == 2 for g in graus_comp)
    eh_complexa = max(graus_comp) >= 3
    return not eh_loop and not eh_complexa


# ---------------------------------------------------------------------------
# Funcao principal: extrair_canais
# ---------------------------------------------------------------------------

def extrair_canais(M: np.ndarray) -> np.ndarray:
    """Extrai o tensor `(4, 3, 12) int8` a partir da matriz crua `(9, 7)`.

    Funcao pura: dado o mesmo `M`, sempre retorna o mesmo tensor (modulo a
    ordem dos elementos). Nao modifica `M`.

    Args:
        M: matriz expandida `(9, 7)` com dominio `{0, 1, 8, 9}`.

    Returns:
        np.ndarray shape `(4, 3, 12)` dtype `int8` com valores em `{0, 1}`.
        K=11 (`paridade_cadeia_longa_impar`) e broadcast: todas as 12 celulas
        recebem o mesmo valor.

    Raises:
        ValueError: se `M.shape != (9, 7)`.
    """
    if M.shape != (9, 7):
        raise ValueError(f"Esperado M.shape == (9, 7), obtido {M.shape!r}")

    canais = np.zeros((N_LINHAS, N_COLUNAS, N_CANAIS), dtype=np.int8)

    # ----- Canais 0..4: arestas geometricas + caixa_fechada -----
    for r in range(N_LINHAS):
        for c in range(N_COLUNAS):
            canais[r, c, 0] = 1 if M[2 * r, 2 * c + 1] == 9 else 0          # aresta_topo
            canais[r, c, 1] = 1 if M[2 * r + 2, 2 * c + 1] == 9 else 0      # aresta_base
            canais[r, c, 2] = 1 if M[2 * r + 1, 2 * c] == 9 else 0          # aresta_esquerda
            canais[r, c, 3] = 1 if M[2 * r + 1, 2 * c + 2] == 9 else 0      # aresta_direita
            canais[r, c, 4] = 1 if M[2 * r + 1, 2 * c + 1] == 1 else 0      # caixa_fechada

    # ----- Canais 5..6: graus 3 e 2 (apenas em caixas abertas) -----
    grau_de: Dict[Tuple[int, int], int] = {}
    fechada_de: Dict[Tuple[int, int], bool] = {}
    for r in range(N_LINHAS):
        for c in range(N_COLUNAS):
            fechada = _caixa_fechada(M, r, c)
            fechada_de[(r, c)] = fechada
            g = _grau(M, r, c)
            grau_de[(r, c)] = g
            if not fechada:
                if g == 3:
                    canais[r, c, 5] = 1
                elif g == 2:
                    canais[r, c, 6] = 1

    # ----- Canais 7..10: cadeias e loops via BFS no grafo dual -----
    adj, componentes = _bfs_dual(M, grau_de, fechada_de)

    # Classificar e marcar cada componente.
    for comp in componentes:
        if not comp:
            continue
        graus_no_componente = {u: len(adj[u]) for u in comp}
        max_grau = max(graus_no_componente.values())

        eh_loop = (
            len(comp) >= 3
            and all(g == 2 for g in graus_no_componente.values())
        )
        # "Cadeia complexa" — ramificacao (grau >= 3 dentro do componente).
        eh_complexa = max_grau >= 3

        if eh_complexa:
            # Marcar tudo como cadeia_longa (canal 8).
            for (r, c) in comp:
                canais[r, c, 8] = 1
        elif eh_loop:
            # Loop fechado.
            for (r, c) in comp:
                canais[r, c, 9] = 1
        else:
            comprimento = len(comp)
            if comprimento == 1:
                # Half-open minimo: caixa grau-2 com exatamente 1 vizinha grau-3
                # via aresta livre. Contamos SEM break para distinguir 1 vs 2 pontas.
                (r0, c0) = comp[0]
                n_abertas = sum(
                    1
                    for v in _vizinhas_caixa(r0, c0)
                    if _aresta_livre_entre(M, (r0, c0), v) and grau_de.get(v, -1) == 3
                )
                if n_abertas == 1:
                    canais[r0, c0, 10] = 1
                continue
            slot = 7 if comprimento == 2 else 8
            for (r, c) in comp:
                canais[r, c, slot] = 1

            # Canal 10: em_cadeia_aberta_uma_ponta.
            pontas = [u for u in comp if graus_no_componente[u] == 1]
            # Apenas cadeias do tipo path tem exatamente 2 pontas.
            if len(pontas) == 2:
                pontas_abertas = _contar_pontas_abertas(M, pontas, adj, grau_de)
                if pontas_abertas == 1:
                    for (r, c) in comp:
                        canais[r, c, 10] = 1
            # Demais topologias nao marcam o canal 10.

    # ----- Canal 11: paridade_cadeia_longa_impar (broadcast global) -----
    n_cadeias_longas = sum(
        1 for comp in componentes if _eh_cadeia_longa(comp, adj)
    )
    paridade_impar = (n_cadeias_longas % 2) == 1
    canais[:, :, 11] = 1 if paridade_impar else 0

    return canais


# ---------------------------------------------------------------------------
# Funcao auxiliar: extrair_stats_cadeias
# ---------------------------------------------------------------------------

def extrair_stats_cadeias(M: np.ndarray) -> Tuple[int, int, int]:
    """Retorna estatisticas de cadeias longas do estado.

    Usa o mesmo grafo dual BFS de `extrair_canais`.

    Args:
        M: matriz expandida `(9, 7)` com dominio `{0, 1, 8, 9}`.

    Returns:
        Tupla `(qtd_cadeias_longas, total_caixas_cadeias_longas, tamanho_max_cadeia_longa)`.
        - qtd_cadeias_longas:        numero de cadeias longas abertas (comprimento >= 3).
        - total_caixas_cadeias_longas: soma dos comprimentos de todas as cadeias longas.
        - tamanho_max_cadeia_longa:  comprimento da maior cadeia longa (0 se nenhuma).

    Raises:
        ValueError: se `M.shape != (9, 7)`.
    """
    if M.shape != (9, 7):
        raise ValueError(f"Esperado M.shape == (9, 7), obtido {M.shape!r}")

    grau_de: Dict[Tuple[int, int], int] = {}
    fechada_de: Dict[Tuple[int, int], bool] = {}
    for r in range(N_LINHAS):
        for c in range(N_COLUNAS):
            fechada_de[(r, c)] = _caixa_fechada(M, r, c)
            grau_de[(r, c)] = _grau(M, r, c)

    adj, componentes = _bfs_dual(M, grau_de, fechada_de)

    qtd = 0
    total = 0
    maximo = 0
    for comp in componentes:
        if _eh_cadeia_longa(comp, adj):
            qtd += 1
            total += len(comp)
            maximo = max(maximo, len(comp))

    return qtd, total, maximo


# ---------------------------------------------------------------------------
# Helper privado de pontas abertas (usado apenas por extrair_canais)
# ---------------------------------------------------------------------------

def _contar_pontas_abertas(
    M: np.ndarray,
    pontas: List[Tuple[int, int]],
    adj: Dict[Tuple[int, int], List[Tuple[int, int]]],
    grau_de: Dict[Tuple[int, int], int],
) -> int:
    """Conta quantas pontas da cadeia sao "abertas" (capturaveis).

    Uma ponta e considerada aberta se alguma aresta livre que sai dela para
    fora do componente leva a uma caixa de grau 3 (definicao de half-open chain
    do Barker & Korf 2012).
    """
    abertas = 0
    for (r, c) in pontas:
        # Vizinhos no grafo dual (dentro do componente).
        vizinhos_dual = set(adj[(r, c)])
        # Examinar cada vizinha ortogonal de (r, c) que NAO esta na adjacencia dual.
        for v in _vizinhas_caixa(r, c):
            if v in vizinhos_dual:
                continue
            # A aresta entre (r, c) e v deve estar livre (== 0) e v deve ter grau 3.
            if _aresta_livre_entre(M, (r, c), v) and grau_de.get(v, -1) == 3:
                abertas += 1
                break  # uma aresta capturavel basta para marcar a ponta
    return abertas


__all__ = [
    "NOMES_CANAIS",
    "N_LINHAS",
    "N_COLUNAS",
    "N_CANAIS",
    "extrair_canais",
    "extrair_stats_cadeias",
]

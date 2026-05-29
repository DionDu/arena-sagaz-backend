#!/usr/bin/env python
"""Script CLI — validacao visual dos 11 canais estruturais (Fase A.2).

Espelha T-A2-004 do tasks.md (FR-C-01..03 do PRD; clarification 2026-05-07
sobre formato dos PNGs).

Para cada estado sorteado, gera **1 PNG** contendo:
  - 1 painel esquerdo: matriz crua `(9, 7)` em paleta de pontos/arestas/caixas.
  - 11 paineis (boxnets `(4, 3)` cada) — um por canal — em paleta categorica
    estavel entre execucoes, com **borda destacada** em caixas onde
    `canal[caixa_fechada] == 1`, titulo do canal acima de cada boxnet
    exatamente igual ao item correspondente em `NOMES_CANAIS`.

Resolucao: 150 DPI (FR-C-02a).

Uso tipico (gate de revisao manual da Fase A.2):

    py scripts/pontinhos/validar_canais_visualmente.py \\
        --diretorio-npz /caminho/para/profundidade_9 \\
        --diretorio-saida out/canais_pngs \\
        --qtd-tracos 14 17 24 29 \\
        --n-amostras 30 \\
        --seed 42

Saida: cria PNGs em `<diretorio-saida>/estado_<NN>_t<TT>.png`.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np

# Permite rodar o script de qualquer diretorio (resolve o backend root).
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import (
    NOMES_CANAIS,
    extrair_canais,
)

# ---------------------------------------------------------------------------
# Paleta categorica estavel por canal (cor fixa entre execucoes — FR-C-02b).
# ---------------------------------------------------------------------------

PALETA_POR_CANAL: List[str] = [
    "#1f77b4",  # 0  aresta_topo                    azul
    "#ff7f0e",  # 1  aresta_base                    laranja
    "#2ca02c",  # 2  aresta_esquerda                verde
    "#d62728",  # 3  aresta_direita                 vermelho
    "#9467bd",  # 4  caixa_fechada                  violeta
    "#8c564b",  # 5  eh_grau3                       marrom
    "#e377c2",  # 6  eh_grau2                       rosa
    "#7f7f7f",  # 7  em_cadeia_curta                cinza
    "#bcbd22",  # 8  em_cadeia_longa                oliva
    "#17becf",  # 9  em_loop                        ciano
    "#000000",  # 10 em_cadeia_aberta_uma_ponta      preto
    "#aec7e8",  # 11 paridade_cadeia_longa_impar     azul-claro
]
assert len(PALETA_POR_CANAL) == len(NOMES_CANAIS) == 12


# ---------------------------------------------------------------------------
# Coleta de amostras
# ---------------------------------------------------------------------------

def _conta_tracos(M: np.ndarray) -> int:
    return int((M == 9).sum())


def coletar_amostras(
    diretorio_npz: str,
    qtd_tracos: List[int],
    n_amostras: int,
    seed: int,
) -> List[Tuple[int, np.ndarray]]:
    """Carrega NPZs do diretorio e seleciona amostras com nro de tracos alvo.

    Distribui `n_amostras` aproximadamente uniformemente entre os valores
    em `qtd_tracos`. Se um valor especifico tiver menos amostras disponiveis
    do que a cota, pega todas e completa com os demais valores.

    Returns:
        Lista de (n_tracos, matriz_crua_9x7).
    """
    rng = np.random.default_rng(seed)
    arquivos = sorted(glob.glob(os.path.join(diretorio_npz, "*.npz")))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum NPZ em {diretorio_npz}")

    pool_por_tracos: dict = {t: [] for t in qtd_tracos}
    for arq in arquivos:
        d = np.load(arq, allow_pickle=True)
        estados = d["estados"]
        for i in range(estados.shape[0]):
            t = _conta_tracos(estados[i])
            if t in pool_por_tracos:
                pool_por_tracos[t].append(estados[i])

    cota_por_t = {t: n_amostras // len(qtd_tracos) for t in qtd_tracos}
    sobras = n_amostras - sum(cota_por_t.values())
    for i in range(sobras):
        cota_por_t[qtd_tracos[i % len(qtd_tracos)]] += 1

    selecionadas: List[Tuple[int, np.ndarray]] = []
    for t, pool in pool_por_tracos.items():
        cota = min(cota_por_t[t], len(pool))
        if cota == 0:
            continue
        idxs = rng.choice(len(pool), size=cota, replace=False)
        for i in idxs:
            selecionadas.append((t, pool[i]))

    rng.shuffle(selecionadas)
    return selecionadas[:n_amostras]


def coletar_amostras_por_canal(
    diretorio_npz: str,
    canais_filtro: List[str],
    n_amostras: int,
    seed: int,
) -> List[Tuple[int, np.ndarray]]:
    """Filtra NPZs por estados onde TODOS os canais em `canais_filtro` tem
    pelo menos uma caixa marcada (valor 1). Sorteia ate `n_amostras`.

    Usa o campo `canais` pre-computado do NPZ quando disponivel; caso contrario
    recalcula via `extrair_canais`.

    Returns:
        Lista de (n_tracos, matriz_crua_9x7).
    """
    nomes_invalidos = [n for n in canais_filtro if n not in NOMES_CANAIS]
    if nomes_invalidos:
        raise ValueError(
            f"Canais desconhecidos: {nomes_invalidos}. "
            f"Canais validos: {list(NOMES_CANAIS)}"
        )
    indices = [NOMES_CANAIS.index(n) for n in canais_filtro]

    rng = np.random.default_rng(seed)
    arquivos = sorted(glob.glob(os.path.join(diretorio_npz, "*.npz")))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum NPZ em {diretorio_npz}")

    pool: List[Tuple[int, np.ndarray]] = []
    n_total = 0
    for arq in arquivos:
        d = np.load(arq, allow_pickle=True)
        estados = d["estados"]
        canais_pre = d["canais"] if "canais" in d else None
        n_total += estados.shape[0]
        for i in range(estados.shape[0]):
            c = canais_pre[i] if canais_pre is not None else extrair_canais(estados[i])
            if all(c[:, :, k].any() for k in indices):
                pool.append((_conta_tracos(estados[i]), estados[i]))

    print(
        f"  Filtro {canais_filtro}: {len(pool)} estados encontrados "
        f"em {n_total} total ({len(arquivos)} arquivos)."
    )
    if not pool:
        raise RuntimeError(
            f"Nenhum estado com todos os canais ativos: {canais_filtro}"
        )

    n = min(n_amostras, len(pool))
    if n < n_amostras:
        print(f"  Aviso: apenas {n} estados disponiveis (pedidos: {n_amostras}).")
    idxs = rng.choice(len(pool), size=n, replace=False)
    return [pool[i] for i in idxs]


# ---------------------------------------------------------------------------
# Renderizacao
# ---------------------------------------------------------------------------

def _desenhar_matriz_crua(ax, M: np.ndarray) -> None:
    """Desenha a matriz expandida (9, 7): pontos fixos, arestas, caixas."""
    h, w = M.shape
    # Fundo branco com grid sutil.
    ax.set_xlim(-0.5, w - 0.5)
    ax.set_ylim(h - 0.5, -0.5)  # invertido para r=0 no topo
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("matriz_crua (9, 7)", fontsize=8)
    for r in range(h):
        for c in range(w):
            v = int(M[r, c])
            if v == 8:
                ax.plot(c, r, "o", color="black", markersize=4)
            elif v == 9:
                ax.plot(c, r, "s", color="#d62728", markersize=6)  # aresta jogada vermelha
            elif v == 1:
                ax.add_patch(
                    __import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle(
                        (c - 0.4, r - 0.4),
                        0.8,
                        0.8,
                        linewidth=0,
                        facecolor="#9467bd",
                        alpha=0.5,
                    )
                )
            # 0 = livre/vazio — nada desenhado.


def _desenhar_boxnet_canal(
    ax,
    canais_estado: np.ndarray,  # (4, 3, 11)
    k: int,
    nome: str,
    cor: str,
) -> None:
    """Desenha um boxnet (4, 3) para o canal `k`. Borda nas caixas fechadas."""
    import matplotlib.patches as patches

    n_linhas, n_colunas, _ = canais_estado.shape
    ax.set_xlim(-0.5, n_colunas - 0.5)
    ax.set_ylim(n_linhas - 0.5, -0.5)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(nome, fontsize=8)

    fechadas = canais_estado[..., 4]  # canal 4 = caixa_fechada
    for r in range(n_linhas):
        for c in range(n_colunas):
            v = int(canais_estado[r, c, k])
            face = cor if v == 1 else "#ffffff"
            edge = "#000000" if int(fechadas[r, c]) == 1 else "#cccccc"
            lw = 2.0 if int(fechadas[r, c]) == 1 else 0.5
            ax.add_patch(
                patches.Rectangle(
                    (c - 0.4, r - 0.4),
                    0.8,
                    0.8,
                    linewidth=lw,
                    edgecolor=edge,
                    facecolor=face,
                )
            )


def renderizar_estado(
    M: np.ndarray,
    canais_estado: np.ndarray,
    n_tracos: int,
    caminho_saida: str,
    dpi: int = 150,
) -> None:
    """Gera um PNG com matriz crua + 12 boxnets para um unico estado."""
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    n_canais = canais_estado.shape[2]  # 12
    n_cols_canais = 4
    n_rows_canais = (n_canais + n_cols_canais - 1) // n_cols_canais  # 3

    fig = plt.figure(figsize=(12, 6))
    gs = fig.add_gridspec(n_rows_canais, n_cols_canais + 1, wspace=0.3, hspace=0.45)

    # Painel esquerdo (matriz crua) ocupa todas as linhas da coluna 0.
    ax_crua = fig.add_subplot(gs[:, 0])
    _desenhar_matriz_crua(ax_crua, M)

    # 12 paineis em grade 3x4 (colunas 1..4).
    for canal_idx in range(n_canais):
        row = canal_idx // n_cols_canais
        col = canal_idx % n_cols_canais + 1
        ax = fig.add_subplot(gs[row, col])
        _desenhar_boxnet_canal(
            ax,
            canais_estado,
            canal_idx,
            NOMES_CANAIS[canal_idx],
            PALETA_POR_CANAL[canal_idx],
        )

    fig.suptitle(f"Validacao visual dos {n_canais} canais — t={n_tracos} tracos", fontsize=11)
    fig.savefig(caminho_saida, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Gera PNGs de validacao visual dos 11 canais.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--diretorio-npz",
        default="dados/profundidade_minimax_11_v7_adaptativo",
        help="Diretorio contendo os NPZs Fase A.2 (ja com `canais`/`nomes_canais`).",
    )
    p.add_argument(
        "--diretorio-saida",
        default="visualizacoes/validacao_canais_pontinhos",
        help="Diretorio onde gravar os PNGs.",
    )
    p.add_argument(
        "--qtd-tracos",
        type=int,
        nargs="+",
        default=[14, 17, 24, 29],
        help=(
            "Lista de valores de nro de tracos a sortear amostras. "
            "Ignorado quando --canais-filtro esta presente."
        ),
    )
    p.add_argument(
        "--canais-filtro",
        type=str,
        nargs="+",
        default=None,
        metavar="CANAL",
        help=(
            "Um ou mais nomes de canais (ex.: em_loop em_cadeia_curta). "
            "Seleciona apenas estados onde TODOS os canais listados possuem "
            "pelo menos uma caixa marcada. Substitui --qtd-tracos."
        ),
    )
    p.add_argument(
        "--n-amostras",
        type=int,
        default=30,
        help="Total de PNGs a gerar.",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed para reprodutibilidade da amostragem.",
    )
    p.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Resolucao dos PNGs (FR-C-02a).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    os.makedirs(args.diretorio_saida, exist_ok=True)

    print(f"Coletando amostras em {args.diretorio_npz}...")
    if args.canais_filtro:
        amostras = coletar_amostras_por_canal(
            args.diretorio_npz,
            args.canais_filtro,
            args.n_amostras,
            args.seed,
        )
    else:
        amostras = coletar_amostras(
            args.diretorio_npz,
            args.qtd_tracos,
            args.n_amostras,
            args.seed,
        )
    print(f"  {len(amostras)} amostras coletadas.")

    for idx, (n_tracos, M) in enumerate(amostras):
        canais_estado = extrair_canais(M)
        nome_arq = f"estado_{idx:03d}_t{n_tracos:02d}.png"
        caminho = os.path.join(args.diretorio_saida, nome_arq)
        renderizar_estado(M, canais_estado, n_tracos, caminho, dpi=args.dpi)
        print(f"  {caminho}")

    print(f"OK: {len(amostras)} PNGs gerados em {args.diretorio_saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

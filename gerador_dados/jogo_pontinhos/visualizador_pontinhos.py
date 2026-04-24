"""Abstração visual: matriz de estado → imagem PNG e relatórios MD."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import numpy as np

from api.nucleo.log import obter_logger

log = obter_logger("gerador_dados.visualizador")

_COR_PONTO = [0, 0, 0]
_COR_VAZIO = [255, 255, 255]
_COR_J1 = [0, 87, 183]
_COR_J2 = [193, 57, 43]

_MAPA_CORES = {
    8: _COR_PONTO,
    0: _COR_VAZIO,
    1: [52, 152, 219],   # Azul genérico: caixa preenchida (sem posse)
    9: [128, 128, 128],  # Cinza: aresta preenchida
    2: [46, 204, 113],   # Verde: melhor próxima jogada (highlight)
}


def _extrair_rc(label: str) -> tuple[int, int] | None:
    if not label or not label.startswith(("H_", "V_")): return None
    partes = label.split("_")
    if len(partes) == 3:
        return int(partes[1]), int(partes[2])
    return None


def _matriz_para_rgb(matriz: np.ndarray, melhor_jogada: str = None) -> np.ndarray:
    h, w = matriz.shape
    m_copia = matriz.copy()
    
    rc = _extrair_rc(melhor_jogada)
    if rc is not None:
        r, c = rc
        if 0 <= r < h and 0 <= c < w and m_copia[r, c] == 0:
            m_copia[r, c] = 2  # highlight
            
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for valor, cor in _MAPA_CORES.items():
        mask = m_copia == valor
        rgb[mask] = cor
    return rgb


def _matriz_para_ascii(matriz: np.ndarray, melhor_jogada: str = None) -> str:
    """Desfaz a matriz de features para um grid visual ASCII (pontos, traços e caixas)."""
    h, w = matriz.shape
    rc_melhor = _extrair_rc(melhor_jogada)
    
    linhas = []
    for r in range(h):
        linha = ""
        for c in range(w):
            val = matriz[r, c]
            is_melhor = rc_melhor is not None and (r, c) == rc_melhor
            
            if r % 2 == 0 and c % 2 == 0:
                # Vértices (pontos)
                linha += "." if val == 8 else " "
            elif r % 2 == 0 and c % 2 != 0:
                # Arestas horizontais
                if is_melhor: linha += "***"
                else: linha += "---" if val == 9 else "   "
            elif r % 2 != 0 and c % 2 == 0:
                # Arestas verticais
                if is_melhor: linha += "*"
                else: linha += "|" if val == 9 else " "
            else:
                # Caixas fechadas (agora agnósticas a jogador)
                if val == 1:
                    linha += " [X]"
                else:
                    linha += "    "
        linhas.append(linha)
    return "\n".join(linhas)


def matriz_para_png(
    matriz: np.ndarray,
    caminho_saida: Path,
    resolucao: int = 200,
    melhor_jogada: str = None,
) -> None:
    """Converte uma matriz de estado em imagem PNG."""
    if matriz.ndim != 2:
        raise ValueError(f"Esperado array 2D, recebido shape {matriz.shape}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    rgb = _matriz_para_rgb(matriz, melhor_jogada)
    fig, ax = plt.subplots(figsize=(resolucao / 100, resolucao / 100), dpi=100)
    ax.imshow(rgb, interpolation="nearest")
    ax.axis("off")
    fig.savefig(caminho_saida, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def lote_para_png(
    matrizes: np.ndarray,
    diretorio_saida: Union[str, Path],
    prefixo: str = "estado",
    resolucao: int = 200,
) -> None:
    """Converte um array de matrizes (N, H, W) em N arquivos PNG numerados."""
    diretorio_saida = Path(diretorio_saida)
    diretorio_saida.mkdir(parents=True, exist_ok=True)
    if matrizes.ndim != 3:
        raise ValueError(f"Esperado array 3D (N, H, W), recebido shape {matrizes.shape}")
    for i, matriz in enumerate(matrizes):
        caminho = diretorio_saida / f"{prefixo}_{i:04d}.png"
        matriz_para_png(matriz, caminho, resolucao=resolucao)


def extrair_e_gerar(caminho_npz: Union[str, Path], diretorio_saida: Union[str, Path], limite: int = 50):
    """Gera arquivos PNG simplificados e MDs bem formatados para amostras de um .npz."""
    caminho_npz = Path(caminho_npz)
    diretorio_saida = Path(diretorio_saida)
    diretorio_saida.mkdir(parents=True, exist_ok=True)
    
    if not caminho_npz.exists():
        log.error(f"Arquivo não encontrado: {caminho_npz}")
        return

    dados = np.load(str(caminho_npz))
    estados = dados["estados"]
    rotulos = dados["rotulos"]
    scores = dados["scores"]
    labels_canonicos = dados["labels_canonicos"]
    
    # Trata retrocompatibilidade (V2 não tinha generation_mode)
    tem_gen_mode = "generation_mode" in dados
    if tem_gen_mode:
        gen_modes = dados["generation_mode"]
    else:
        gen_modes = np.zeros(len(estados), dtype=int)
        
    mapa_modos = {0: "p0 (Aleatorio / Uniforme)", 1: "p1 (AutoPlay Prof. 1)", 2: "p2 (AutoPlay Prof. 2)", 3: "p3 (AutoPlay Prof. 3)"}
    
    qtd = min(len(estados), limite)
    log.info(f"Gerando visualizações para {qtd} amostras em {diretorio_saida}")
    
    for i in range(qtd):
        nome_base = f"tabuleiro_{i:04d}"
        
        modo_str = mapa_modos.get(int(gen_modes[i]), f"p{gen_modes[i]}")
        melhor_jogada = str(rotulos[i])
        
        # 1. Gerar imagem simplificada (com highlight)
        png_path = diretorio_saida / f"{nome_base}.png"
        matriz_para_png(estados[i], png_path, melhor_jogada=melhor_jogada)
        
        # 2. Gerar relatório MD (com highlight)
        md_path = diretorio_saida / f"{nome_base}.md"
        
        matriz_ascii = _matriz_para_ascii(estados[i], melhor_jogada)
        matriz_crua = np.array2string(estados[i], separator=', ')
        
        # Montar a tabela de scores extraída pelo professor (Minimax)
        linhas_scores = []
        for class_idx, label in enumerate(labels_canonicos):
            score_val = scores[i, class_idx]
            score_str = f"{score_val:8.2f}" if score_val > -10000 else "Inválida"
            is_best = "⭐ (Melhor)" if label == melhor_jogada else ""
            linhas_scores.append(f"| {label:^10} | {score_str:^12} | {is_best} |")
            
        tabela_scores = "\n".join(linhas_scores)
        
        conteudo_md = f"""# {nome_base}

## Metadados do Tabuleiro
- **Estratégia de Geração (STRAT_MODES):** `{modo_str}`
- **Melhor Jogada (Rótulo):** `{melhor_jogada}`

## Matriz Crua (NPZ)
Abaixo está exatamente o que a CNN enxerga em `estados`. Note que não existe nenhum valor `-1` (J2) no dataset inteiro.

```text
{matriz_crua}
```

## Visão Física do Tabuleiro

Aqui desfazemos a matriz convolucional em uma representação visual humana.
As arestas marcadas (valor `9`) são exibidas como `---` ou `|`. Os vértices (`8`) são `.`.

```text
{matriz_ascii}
```

## Avaliação Minimax (Professor de Profundidade 7)

Tabela completa com a "percepção de valor" do nosso algoritmo professor para cada traço do jogo:

|  Classe  |    Score    | É a melhor? |
|:--------:|:-----------:|-------------|
{tabela_scores}
"""
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(conteudo_md)

    log.info(f"Processo finalizado com sucesso! Arquivos em: {diretorio_saida}")

if __name__ == "__main__":
    import sys
    # Se rodar direto no terminal, usa os argumentos passados
    if len(sys.argv) > 2:
        arquivo_npz = sys.argv[1]
        pasta_saida = sys.argv[2]
        extrair_e_gerar(arquivo_npz, pasta_saida)
    else:
        print("Como usar: python -m gerador_dados.visualizador <arquivo_npz> <pasta_de_saida>")

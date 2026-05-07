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

# ---------------------------------------------------------------------------
# Visualização no contexto PARTIDA (CNN vs Minimax)
# ---------------------------------------------------------------------------
# As funções `_matriz_para_rgb` / `_matriz_para_ascii` acima são do contexto
# TREINAMENTO (matriz com `1` em qualquer caixa fechada, sem distinção de
# jogador). Numa partida real, a matriz carrega `+1` para o jogador 1 e `-1`
# para o jogador 2 (contrato_codificacao_pontinhos.json — contexto 3).
#
# As funções abaixo renderizam a partir desse encoding e são usadas pelo
# avaliador para gerar as imagens de "caixas perdidas" (momentos em que a
# CNN deixou de fechar uma caixa pronta).

_COR_CNN          = [52, 152, 219]    # azul
_COR_MM           = [231, 76, 60]     # vermelho
_COR_CAIXA_PRONTA = [241, 196, 15]    # amarelo (caixa que a CNN deveria ter fechado)
_COR_TRACO_JOGADO = [46, 204, 113]    # verde (traço efetivamente escolhido pela CNN)
_COR_ARESTA       = [128, 128, 128]   # cinza


def _matriz_partida_para_rgb(
    matriz: np.ndarray,
    cnn_valor: int,
    caixas_prontas: list[tuple[int, int]] | None = None,
    traco_jogado: str | None = None,
) -> np.ndarray:
    """Encoding PARTIDA → RGB. `cnn_valor` ∈ {+1, -1} indica que valor da matriz é da CNN."""
    h, w = matriz.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[:] = _COR_VAZIO

    for r in range(h):
        for c in range(w):
            v = matriz[r, c]
            if r % 2 == 0 and c % 2 == 0:
                rgb[r, c] = _COR_PONTO
            elif r % 2 == 1 and c % 2 == 1:
                if v == cnn_valor:
                    rgb[r, c] = _COR_CNN
                elif v == -cnn_valor:
                    rgb[r, c] = _COR_MM
            else:
                if v != 0:
                    rgb[r, c] = _COR_ARESTA

    if caixas_prontas:
        for (br, bc) in caixas_prontas:
            r, c = 2 * br + 1, 2 * bc + 1
            if 0 <= r < h and 0 <= c < w and matriz[r, c] == 0:
                rgb[r, c] = _COR_CAIXA_PRONTA

    rc = _extrair_rc(traco_jogado) if traco_jogado else None
    if rc is not None:
        r, c = rc
        if 0 <= r < h and 0 <= c < w:
            rgb[r, c] = _COR_TRACO_JOGADO

    return rgb


def _matriz_partida_para_ascii(
    matriz: np.ndarray,
    cnn_valor: int,
    caixas_prontas: list[tuple[int, int]] | None = None,
    traco_jogado: str | None = None,
) -> str:
    """ASCII no contexto PARTIDA — `[C]` = CNN, `[M]` = Minimax, `[?]` = caixa pronta cedida."""
    h, w = matriz.shape
    rc_traco = _extrair_rc(traco_jogado) if traco_jogado else None
    prontas_set = set(caixas_prontas or [])

    linhas = []
    for r in range(h):
        linha = ""
        for c in range(w):
            val = matriz[r, c]
            is_traco = rc_traco is not None and (r, c) == rc_traco

            if r % 2 == 0 and c % 2 == 0:
                linha += "."
            elif r % 2 == 0 and c % 2 == 1:
                if is_traco:   linha += "***"
                elif val != 0: linha += "---"
                else:          linha += "   "
            elif r % 2 == 1 and c % 2 == 0:
                if is_traco:   linha += "*"
                elif val != 0: linha += "|"
                else:          linha += " "
            else:
                br, bc = (r - 1) // 2, (c - 1) // 2
                if val == cnn_valor:    linha += "[C] "
                elif val == -cnn_valor: linha += "[M] "
                elif (br, bc) in prontas_set: linha += "[?] "
                else:                   linha += "    "
        linhas.append(linha)
    return "\n".join(linhas)


def salvar_evento_caixa_perdida(
    evento: dict,
    png_path: Path,
    md_path: Path,
    contexto: dict | None = None,
    resolucao: int = 300,
) -> None:
    """Salva PNG + MD para um evento `caixa perdida` produzido pelo avaliador.

    `evento` deve conter: `matriz_antes`, `cnn_valor_matriz`, `traco_jogado`,
    `caixas_prontas_pos`, `placar_cnn`, `placar_mm`, `numero_jogada`,
    `partida_idx`, `cnn_primeiro` (decoração feita em `_proc_worker_match`).
    """
    matriz         = evento["matriz_antes"]
    cnn_valor      = int(evento["cnn_valor_matriz"])
    caixas_prontas = evento.get("caixas_prontas_pos") or []
    traco          = evento.get("traco_jogado")

    png_path = Path(png_path)
    md_path  = Path(md_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rgb = _matriz_partida_para_rgb(matriz, cnn_valor, caixas_prontas, traco)
    fig, ax = plt.subplots(figsize=(resolucao / 100, resolucao / 100), dpi=100)
    ax.imshow(rgb, interpolation="nearest")
    ax.axis("off")
    fig.savefig(png_path, bbox_inches="tight", pad_inches=0)
    plt.close(fig)

    ascii_repr = _matriz_partida_para_ascii(matriz, cnn_valor, caixas_prontas, traco)
    matriz_crua = np.array2string(matriz, separator=", ")

    placar_cnn   = evento.get("placar_cnn", 0)
    placar_mm    = evento.get("placar_mm", 0)
    n_jogada     = evento.get("numero_jogada", "?")
    partida_idx  = evento.get("partida_idx", "?")
    cnn_primeiro = evento.get("cnn_primeiro")

    contexto = contexto or {}
    adversario = contexto.get("adversario", "?")
    exec_id    = contexto.get("exec_id", "?")

    if cnn_primeiro is True:
        posicao = "Jogador 1 (CNN começou)"
    elif cnn_primeiro is False:
        posicao = "Jogador 2 (Minimax começou)"
    else:
        posicao = "?"

    prontas_str = ", ".join(f"({r},{c})" for r, c in caixas_prontas) or "—"
    n_prontas = len(caixas_prontas)
    plural = "caixas prontas" if n_prontas != 1 else "caixa pronta"

    conteudo = f"""# Caixa perdida — partida {partida_idx}, jogada {n_jogada}

## Contexto
- **Avaliação:** `{exec_id}`
- **Adversário:** `{adversario}`
- **Posição da CNN:** {posicao}
- **Placar parcial (CNN x Minimax):** **{placar_cnn} × {placar_mm}**

## O que aconteceu
A CNN tinha **{n_prontas} {plural}** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `{traco}` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** {prontas_str}
- **Traço jogado pela CNN:** `{traco}`

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG: 🔵 azul = caixas da CNN · 🔴 vermelho = caixas do Minimax · 🟡 amarelo = caixa pronta cedida · 🟢 verde = traço efetivamente jogado.

```text
{ascii_repr}
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.

## Matriz crua (estado ANTES da jogada da CNN)

```text
{matriz_crua}
```
"""
    md_path.write_text(conteudo, encoding="utf-8")


if __name__ == "__main__":
    import sys
    # Se rodar direto no terminal, usa os argumentos passados
    if len(sys.argv) > 2:
        arquivo_npz = sys.argv[1]
        pasta_saida = sys.argv[2]
        extrair_e_gerar(arquivo_npz, pasta_saida)
    else:
        print("Como usar: python -m gerador_dados.visualizador <arquivo_npz> <pasta_de_saida>")

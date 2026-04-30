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

# Paleta da renderização vetorial (estilo "imagem 2" — fundo branco, formas
# proporcionais, números brancos centralizados).
_COR_CNN_HEX           = "#3498DB"  # azul
_COR_MM_HEX            = "#E97132"  # laranja vivo
_COR_VERTICE_HEX       = "#E8E8E8"  # cinza claro do círculo do vértice
_COR_PONTILHADO_HEX    = "#3A3A3A"  # cinza escuro da aresta vazia
_COR_CAIXA_PRONTA_HEX  = "#F1C40F"  # amarelo
_COR_PROXIMA_HEX       = "#2ECC71"  # verde
_COR_REGUA_HEX         = "#3A3A3A"  # cinza escuro dos rótulos das réguas
_COR_NUMERO_ARESTA_HEX = "#FFFFFF"  # números das arestas (sempre brancos)

# Geometria em unidades arbitrárias (`D` = diâmetro do vértice).
# A largura/altura de cada célula da matriz é determinada por estas constantes.
_D_VERTICE = 1.0           # diâmetro do círculo do vértice
_RAZAO_ARESTA = 3.25       # comprimento da aresta = 3.25 × D_VERTICE
_BORDA_CAIXA = 0.05        # 5% da largura da caixa fica em branco (respiro)


def _calcular_pos_celula(idx: int) -> tuple[float, float]:
    """Retorna (inicio, fim) em unidades para a célula da matriz no índice dado.

    Índices pares correspondem a vértices (largura D); índices ímpares a arestas
    (comprimento _RAZAO_ARESTA·D).
    """
    pos = 0.0
    for k in range(idx):
        pos += _RAZAO_ARESTA if k % 2 == 1 else _D_VERTICE
    tamanho = _RAZAO_ARESTA if idx % 2 == 1 else _D_VERTICE
    return pos, pos + tamanho


def _dim_total(n: int) -> float:
    """Comprimento total para n células da matriz (em unidades de D)."""
    return _calcular_pos_celula(n - 1)[1]


def _renderizar_partida_png(
    matriz: np.ndarray,
    cnn_valor: int,
    historico: list[tuple[str, int]],
    caminho_saida: Path,
    caixas_prontas: list[tuple[int, int]] | None = None,
    traco_jogado: str | None = None,
    largura_px: int = 400,
    altura_px: int = 500,
) -> None:
    """Renderiza o estado PARTIDA como desenho vetorial em PNG.

    Layout (estilo "imagem 2"):
    - fundo branco; vértices = círculos cinza claro; arestas vazias = pontilhado fino;
    - arestas marcadas = retângulos sólidos coloridos (azul=CNN, laranja=Minimax)
      com o número da ordem cronológica em branco no centro;
    - caixas fechadas = quadrado interno colorido com respiro branco em volta;
    - caixa pronta cedida = quadrado amarelo; próxima jogada = retângulo verde;
    - réguas com índices da matriz (`r`, `c`) nos quatro lados.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle

    h, w = matriz.shape
    largura_tab = _dim_total(w)
    altura_tab  = _dim_total(h)

    # Margem em volta para acomodar as réguas. Igual em x e y resulta numa razão
    # próxima de 0.8 (= 400/500), mantendo aspect='equal' sem sobrar muito branco.
    margem = 1.5 * _D_VERTICE
    desloc_regua = 0.7 * _D_VERTICE

    dpi = 100
    fig, ax = plt.subplots(
        figsize=(largura_px / dpi, altura_px / dpi),
        dpi=dpi,
    )
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    rc_traco = _extrair_rc(traco_jogado) if traco_jogado else None
    prontas_set = set(caixas_prontas or [])
    numero_da_aresta: dict[tuple[int, int], int] = {}
    for idx, (mv_traco, _mv_turno) in enumerate(historico or []):
        rc = _extrair_rc(mv_traco)
        if rc is not None:
            numero_da_aresta[rc] = idx

    def _cor_jogador(val: int) -> str | None:
        if val == cnn_valor:  return _COR_CNN_HEX
        if val == -cnn_valor: return _COR_MM_HEX
        return None

    # zorder: vértices(1) → pontilhadas(2) → arestas(3) → caixas(4) → próxima(5) → números(6)
    # 1) Vértices (círculos)
    for r in range(0, h, 2):
        for c in range(0, w, 2):
            x0, x1 = _calcular_pos_celula(c)
            y0, y1 = _calcular_pos_celula(r)
            ax.add_patch(Circle(
                ((x0 + x1) / 2, (y0 + y1) / 2),
                radius=_D_VERTICE / 2,
                facecolor=_COR_VERTICE_HEX, edgecolor="none", zorder=1,
            ))

    # 2) Arestas (vazias = pontilhada; marcadas = retângulo sólido)
    for r in range(h):
        for c in range(w):
            is_h = (r % 2 == 0) and (c % 2 == 1)
            is_v = (r % 2 == 1) and (c % 2 == 0)
            if not (is_h or is_v):
                continue
            x0, x1 = _calcular_pos_celula(c)
            y0, y1 = _calcular_pos_celula(r)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            val = matriz[r, c]

            if val == 0:
                if is_h:
                    ax.plot([x0, x1], [cy, cy],
                            color=_COR_PONTILHADO_HEX, linestyle=":",
                            linewidth=1.5, zorder=2, solid_capstyle="round")
                else:
                    ax.plot([cx, cx], [y0, y1],
                            color=_COR_PONTILHADO_HEX, linestyle=":",
                            linewidth=1.5, zorder=2, solid_capstyle="round")
                continue

            cor = _cor_jogador(val)
            if cor is None:
                continue
            ax.add_patch(Rectangle(
                (x0, y0), x1 - x0, y1 - y0,
                facecolor=cor, edgecolor="none", zorder=3,
            ))
            num = numero_da_aresta.get((r, c))
            if num is not None:
                ax.text(cx, cy, str(num),
                        ha="center", va="center",
                        color=_COR_NUMERO_ARESTA_HEX,
                        fontsize=10, fontweight="bold", zorder=6)

    # 3) Caixas (fechadas pelo dono OU prontas/cedidas)
    for r in range(1, h, 2):
        for c in range(1, w, 2):
            x0, x1 = _calcular_pos_celula(c)
            y0, y1 = _calcular_pos_celula(r)
            lado = x1 - x0
            val = matriz[r, c]
            br, bc = (r - 1) // 2, (c - 1) // 2

            cor: str | None
            if val == cnn_valor:    cor = _COR_CNN_HEX
            elif val == -cnn_valor: cor = _COR_MM_HEX
            elif (br, bc) in prontas_set: cor = _COR_CAIXA_PRONTA_HEX
            else:                   cor = None
            if cor is None:
                continue

            margem_int = _BORDA_CAIXA * lado
            ax.add_patch(Rectangle(
                (x0 + margem_int, y0 + margem_int),
                lado - 2 * margem_int,
                lado - 2 * margem_int,
                facecolor=cor, edgecolor="none", zorder=4,
            ))

    # 4) Próxima jogada (retângulo verde sobre a célula da aresta)
    if rc_traco is not None:
        r, c = rc_traco
        if 0 <= r < h and 0 <= c < w:
            x0, x1 = _calcular_pos_celula(c)
            y0, y1 = _calcular_pos_celula(r)
            ax.add_patch(Rectangle(
                (x0, y0), x1 - x0, y1 - y0,
                facecolor=_COR_PROXIMA_HEX, edgecolor="none", zorder=5,
            ))

    # 5) Réguas (índices da matriz nos 4 lados, em cinza escuro)
    fonte_regua = 9
    for c in range(w):
        x0, x1 = _calcular_pos_celula(c)
        cx = (x0 + x1) / 2
        ax.text(cx, -desloc_regua, str(c),
                ha="center", va="center",
                color=_COR_REGUA_HEX, fontsize=fonte_regua)
        ax.text(cx, altura_tab + desloc_regua, str(c),
                ha="center", va="center",
                color=_COR_REGUA_HEX, fontsize=fonte_regua)
    for r in range(h):
        y0, y1 = _calcular_pos_celula(r)
        cy = (y0 + y1) / 2
        ax.text(-desloc_regua, cy, str(r),
                ha="center", va="center",
                color=_COR_REGUA_HEX, fontsize=fonte_regua)
        ax.text(largura_tab + desloc_regua, cy, str(r),
                ha="center", va="center",
                color=_COR_REGUA_HEX, fontsize=fonte_regua)

    ax.set_xlim(-margem, largura_tab + margem)
    ax.set_ylim(altura_tab + margem, -margem)  # invertido: linha 0 no topo
    ax.set_aspect("equal")
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho_saida, dpi=dpi, facecolor="white")
    plt.close(fig)


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
    base_path: Path,
    contexto: dict | None = None,
) -> None:
    """Gera 4 arquivos para um evento `caixa perdida`:

    - `<base_path>.png`  — desenho vetorial 400×500: arestas azuis (CNN) e laranjas (Minimax) com número branco; pontilhado nas arestas vazias; verde para a próxima jogada da CNN
    - `<base_path>.md`   — relatório com placar parcial+final, vencedor, ASCII, matriz crua
    - `<base_path>_norm.npy` — matriz normalizada (contexto PARTIDA), igual ao input da CNN
    - `<base_path>_crua.npy` — matriz crua (encoding partida cru), igual à exibida no MD

    `evento` deve carregar (decoração em `_proc_worker_match`):
    `matriz_antes`, `cnn_valor_matriz`, `traco_jogado`, `caixas_prontas_pos`,
    `placar_cnn`, `placar_mm`, `pontos_finais_cnn`, `pontos_finais_mm`,
    `vencedor_partida`, `numero_jogada`, `partida_idx`, `cnn_primeiro`,
    `historico_jogadas`.
    """
    matriz         = evento["matriz_antes"]
    cnn_valor      = int(evento["cnn_valor_matriz"])
    caixas_prontas = evento.get("caixas_prontas_pos") or []
    traco          = evento.get("traco_jogado")
    historico      = evento.get("historico_jogadas") or []

    base_path = Path(base_path)
    base_path.parent.mkdir(parents=True, exist_ok=True)

    png_path  = base_path.with_suffix(".png")
    md_path   = base_path.with_suffix(".md")
    norm_path = base_path.with_name(base_path.name + "_norm.npy")
    crua_path = base_path.with_name(base_path.name + "_crua.npy")

    # ----------- PNG vetorial (estilo "imagem 2") -----------
    _renderizar_partida_png(
        matriz=matriz,
        cnn_valor=cnn_valor,
        historico=historico,
        caminho_saida=png_path,
        caixas_prontas=caixas_prontas,
        traco_jogado=traco,
    )

    # ----------- NPY (crua + normalizada) -----------
    np.save(crua_path, matriz)
    try:
        from gerador_dados.jogo_pontinhos.contrato_codificacao_pontinhos import (
            CONTEXTO_PARTIDA,
            normalizar_para_cnn,
        )
        matriz_norm = normalizar_para_cnn(matriz, CONTEXTO_PARTIDA)
        np.save(norm_path, matriz_norm)
    except Exception as ex:
        log.warning(f"Falha ao salvar matriz normalizada: {ex}")

    # ----------- MD -----------
    ascii_repr = _matriz_partida_para_ascii(matriz, cnn_valor, caixas_prontas, traco)
    matriz_crua = np.array2string(matriz, separator=", ")

    placar_cnn   = evento.get("placar_cnn", 0)
    placar_mm    = evento.get("placar_mm", 0)
    pf_cnn       = evento.get("pontos_finais_cnn", "?")
    pf_mm        = evento.get("pontos_finais_mm", "?")
    vencedor     = int(evento.get("vencedor_partida", 0))
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

    if vencedor == 1:
        resultado = f"**VITÓRIA da CNN** — placar final {pf_cnn} × {pf_mm}"
    elif vencedor == 2:
        resultado = f"**DERROTA da CNN** — placar final {pf_cnn} × {pf_mm}"
    else:
        resultado = f"**EMPATE** — placar final {pf_cnn} × {pf_mm}"

    prontas_str = ", ".join(f"({r},{c})" for r, c in caixas_prontas) or "—"
    n_prontas = len(caixas_prontas)
    plural = "caixas prontas" if n_prontas != 1 else "caixa pronta"

    # Tabela com a probabilidade que a CNN atribuiu a cada traço, ordenada
    # de forma decrescente. Marca a jogada efetivamente escolhida.
    probs = evento.get("probs_cnn")
    labels_cnn = evento.get("labels_cnn")
    if probs is not None and labels_cnn is not None:
        disponiveis = {
            f"H_{r}_{c}" if r % 2 == 0 else f"V_{r}_{c}"
            for r in range(matriz.shape[0])
            for c in range(matriz.shape[1])
            if (r % 2 == 0) != (c % 2 == 0) and matriz[r, c] == 0
        }
        pares = sorted(
            zip(labels_cnn, [float(p) for p in probs]),
            key=lambda x: -x[1],
        )
        linhas_probs = []
        for label, prob in pares:
            if label == traco:
                marcador = "⭐ (Escolhida)"
            elif label not in disponiveis:
                marcador = "(Indisponível)"
            else:
                marcador = ""
            linhas_probs.append(
                f"| {label:^10} | {prob:>13.6f} | {marcador:<14} |"
            )
        tabela_probs = "\n".join(linhas_probs)
        secao_probs_cnn = f"""

## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
{tabela_probs}
"""
    else:
        secao_probs_cnn = ""

    conteudo = f"""# Caixa perdida — partida {partida_idx}, jogada {n_jogada}

## Contexto
- **Avaliação:** `{exec_id}`
- **Adversário:** `{adversario}`
- **Posição da CNN:** {posicao}

## Placar
- **No momento da decisão:** CNN **{placar_cnn}** × **{placar_mm}** Minimax
- **Final da partida:** CNN **{pf_cnn}** × **{pf_mm}** Minimax
- **Resultado da partida:** {resultado}

## O que aconteceu
A CNN tinha **{n_prontas} {plural}** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `{traco}` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** {prontas_str}
- **Traço jogado pela CNN:** `{traco}` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas fechadas e arestas marcadas pela CNN
- 🟠 laranja = caixas fechadas e arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = aresta que a CNN está prestes a marcar (não numerada, pois ainda não foi aplicada)
- ⚪ círculos cinza-claros = vértices · linhas pontilhadas = arestas ainda não jogadas
- réguas (números cinza-escuros) = índices da matriz `(linha, coluna)` em todos os 4 lados

Cada aresta marcada exibe um número branco no centro: a ordem cronológica em que foi jogada (`0` = primeiro traço da partida; números crescem ao longo da partida).

```text
{ascii_repr}
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.
{secao_probs_cnn}
## Matriz crua (estado ANTES da jogada da CNN)

```text
{matriz_crua}
```

## Arquivos gerados nesta amostra
- `{png_path.name}` — visualização com numeração de arestas
- `{md_path.name}` — este relatório
- `{norm_path.name}` — matriz normalizada (input da CNN, NumPy)
- `{crua_path.name}` — matriz crua (encoding partida bruto, NumPy)
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

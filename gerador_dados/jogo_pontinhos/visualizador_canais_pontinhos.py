"""Visualizador interativo dos 12 canais estruturais enviados à CNN.

Clique nas arestas do tabuleiro para adicioná-las ou removê-las.
A cada alteração os 12 canais são recomputados ao vivo e exibidos
como mini-grids coloridos no painel direito, junto com as
probabilidades da CNN para cada traço disponível.

Uso:
    python -m gerador_dados.jogo_pontinhos.visualizador_canais_pontinhos \\
        --modelo caminho/para/modelo_12ch.tflite

Teclas:
    C   — limpar tabuleiro
    Q   — sair
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Literal

import numpy as np

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import TAMANHOS, todos_labels_canonicos
from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import (
    NOMES_CANAIS,
    extrair_canais,
)
from api.nucleo.log import obter_logger

log = obter_logger("gerador_dados.visualizador_canais")

# ── Tamanho do tabuleiro suportado ────────────────────────────────────────────
_N_LINHAS_CX = 4    # linhas de caixas (tabuleiro "pequeno")
_N_COLUNAS_CX = 3   # colunas de caixas

# ── Janela ────────────────────────────────────────────────────────────────────
_W_BOARD = 390      # painel esquerdo (tabuleiro)
_W_RIGHT = 1010     # painel direito (canais + scores)
_LARGURA = _W_BOARD + _W_RIGHT   # 1400
_ALTURA = 900

# ── Margens do tabuleiro ──────────────────────────────────────────────────────
_MARG_TAB = 46      # margem interna do painel esquerdo
_TITULO_H = 52      # espaço para título + subtítulo no topo do painel esquerdo

# ── Mini-grids dos canais ─────────────────────────────────────────────────────
_CELL_W = 65        # largura de cada célula de caixa dentro da mini-grid
_CELL_H = 50        # altura de cada célula de caixa dentro da mini-grid
_MINI_GRID_W = _N_COLUNAS_CX * _CELL_W   # 195px — área interna da grid
_MINI_GRID_H = _N_LINHAS_CX * _CELL_H    # 200px
_MINI_PAD_H = 15    # padding horizontal à esquerda e direita da mini-grid
_MINI_PAD_TOP = 26  # espaço para título acima da grid
_MINI_PAD_BOT = 6   # padding abaixo da grid
_MINI_W = _MINI_GRID_W + 2 * _MINI_PAD_H   # 225px — largura total da mini-grid
_MINI_H = _MINI_GRID_H + _MINI_PAD_TOP + _MINI_PAD_BOT  # 232px — altura total

_CANAIS_POR_LINHA = 4   # 4 colunas de mini-grids
_CANAIS_LINHAS = 3      # 3 linhas (4×3 = 12 canais)
_MARG_R = 15            # margem interna do painel direito (esq/dir)
_CANAIS_START_Y = 44    # y inicial dos canais no painel direito

# gap horizontal: espaço sobrante entre as 4 mini-grids
_GAP_H = max(
    10,
    (_W_RIGHT - 2 * _MARG_R - _CANAIS_POR_LINHA * _MINI_W) // (_CANAIS_POR_LINHA - 1),
)  # ≈ 30px
_GAP_V = 18             # gap vertical entre linhas de mini-grids

_CANAIS_TOTAL_H = _CANAIS_LINHAS * _MINI_H + (_CANAIS_LINHAS - 1) * _GAP_V  # 736px
_SCORES_START_Y = _CANAIS_START_Y + _CANAIS_TOTAL_H + 14   # ≈ 794px
_SCORES_H = _ALTURA - _SCORES_START_Y - 5                   # ≈ 101px

# ── Cores ─────────────────────────────────────────────────────────────────────
_C_FUNDO = (14, 14, 24)
_C_PAINEL_R = (19, 19, 34)
_C_SEP = (48, 48, 75)
_C_TEXTO = (215, 215, 232)
_C_SUB = (115, 115, 150)
_C_HOVER = (235, 195, 40)
_C_GHOST = (35, 35, 56)
_C_ARESTA = (190, 195, 215)
_C_PONTO = (220, 222, 238)
_C_PROB_TOP = (60, 205, 80)
_C_PROB_2 = (200, 185, 45)
_C_PROB_REST = (70, 135, 205)
_C_GRADE_MINI = (55, 55, 80)
_C_BORDA_EXT = (75, 75, 108)
_C_BORDA_FECHADA = (20, 20, 20)
_C_BORDA_NORMAL = (170, 170, 190)
_C_CELL_VAZIO = (245, 245, 250)
_ESP_TRACO = 7
_ESP_GHOST = 4

# Paleta dos 12 canais (alinhada com scripts/pontinhos/validar_canais_visualmente.py)
_CORES_CANAIS = [
    (31, 119, 180),    # K=0  aresta_topo                azul
    (255, 127, 14),    # K=1  aresta_base               laranja
    (44, 160, 44),     # K=2  aresta_esquerda            verde
    (214, 39, 40),     # K=3  aresta_direita             vermelho
    (148, 103, 189),   # K=4  caixa_fechada              violeta
    (140, 86, 75),     # K=5  eh_grau3                   marrom
    (227, 119, 194),   # K=6  eh_grau2                   rosa
    (127, 127, 127),   # K=7  em_cadeia_curta            cinza
    (188, 189, 34),    # K=8  em_cadeia_longa            oliva
    (23, 190, 207),    # K=9  em_loop                    ciano
    (50, 50, 50),      # K=10 em_cadeia_aberta_uma_ponta escuro
    (174, 199, 232),   # K=11 paridade_cadeia_longa_impar azul-claro
]

# Nomes curtos para caber no espaço da mini-grid
_NOMES_CURTOS = [
    "aresta_topo",
    "aresta_base",
    "aresta_esq.",
    "aresta_dir.",
    "caixa_fech.",
    "grau 3",
    "grau 2",
    "cadeia curta",
    "cadeia longa",
    "em loop",
    "1 ponta aberta",
    "par. cad. longa",
]


# ── Estado do tabuleiro (encoding dataset: {0,1,8,9}) ────────────────────────

class TabuleiroDemos:
    """Tabuleiro editável em encoding de dataset para o visualizador."""

    def __init__(self) -> None:
        h = 2 * _N_LINHAS_CX + 1
        w = 2 * _N_COLUNAS_CX + 1
        self.mat = np.zeros((h, w), dtype=np.int8)
        for r in range(0, h, 2):
            for c in range(0, w, 2):
                self.mat[r, c] = 8

    def toggle_aresta(self, label: str) -> None:
        _, r_s, c_s = label.split("_")
        r, c = int(r_s), int(c_s)
        self.mat[r, c] = 0 if self.mat[r, c] != 0 else 9
        self._atualizar_caixas()

    def _atualizar_caixas(self) -> None:
        h, w = self.mat.shape
        for r in range(1, h, 2):
            for c in range(1, w, 2):
                fechada = (
                    self.mat[r - 1, c] != 0
                    and self.mat[r + 1, c] != 0
                    and self.mat[r, c - 1] != 0
                    and self.mat[r, c + 1] != 0
                )
                self.mat[r, c] = 1 if fechada else 0

    def limpar(self) -> None:
        h, w = self.mat.shape
        self.mat[:] = 0
        for r in range(0, h, 2):
            for c in range(0, w, 2):
                self.mat[r, c] = 8

    def tracos_todos(self) -> list[str]:
        labels = []
        h, w = self.mat.shape
        for r in range(h):
            for c in range(w):
                if r % 2 == 0 and c % 2 == 1:
                    labels.append(f"H_{r}_{c}")
                elif r % 2 == 1 and c % 2 == 0:
                    labels.append(f"V_{r}_{c}")
        return labels

    def tracos_disponiveis(self) -> list[str]:
        disponivel = []
        h, w = self.mat.shape
        for r in range(h):
            for c in range(w):
                if r % 2 == 0 and c % 2 == 1 and self.mat[r, c] == 0:
                    disponivel.append(f"H_{r}_{c}")
                elif r % 2 == 1 and c % 2 == 0 and self.mat[r, c] == 0:
                    disponivel.append(f"V_{r}_{c}")
        return disponivel

    def n_tracos(self) -> int:
        return int((self.mat == 9).sum())

    def n_caixas(self) -> int:
        return int((self.mat == 1).sum())


# ── CNN helpers ───────────────────────────────────────────────────────────────

def _carregar_modelo(caminho: str):
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        import tensorflow.lite as tflite  # type: ignore
    interp = tflite.Interpreter(model_path=caminho)
    interp.allocate_tensors()
    return interp


def _tipo_modelo(interp) -> Literal["1ch", "12ch"]:
    shape = interp.get_input_details()[0]["shape"]
    return "12ch" if len(shape) == 4 and shape[3] == 12 else "1ch"


def _inferir(tab: TabuleiroDemos, interp, tipo: Literal["1ch", "12ch"]) -> dict[str, float]:
    det_ent = interp.get_input_details()
    det_sai = interp.get_output_details()

    if tipo == "12ch":
        entrada = extrair_canais(tab.mat).astype(np.float32)[np.newaxis, ...]  # (1,4,3,12)
    else:
        from gerador_dados.jogo_pontinhos.contrato_codificacao_pontinhos import (
            normalizar_para_cnn, CONTEXTO_TREINO,
        )
        entrada = normalizar_para_cnn(tab.mat, CONTEXTO_TREINO)[np.newaxis, ..., np.newaxis]

    interp.set_tensor(det_ent[0]["index"], entrada)
    interp.invoke()
    saida = interp.get_tensor(det_sai[0]["index"])[0]

    todos = todos_labels_canonicos(_N_LINHAS_CX, _N_COLUNAS_CX)
    idx = {l: i for i, l in enumerate(todos)}
    disponiveis = tab.tracos_disponiveis()
    if not disponiveis:
        return {}
    return {t: float(saida[idx[t]]) for t in disponiveis}


# ── Visualizador ──────────────────────────────────────────────────────────────

class VisualizadorCanais:

    def __init__(self, modelo: str) -> None:
        import pygame
        self.pg = pygame
        self.tab = TabuleiroDemos()
        self.interp = _carregar_modelo(modelo)
        self.tipo = _tipo_modelo(self.interp)
        self.canais: np.ndarray | None = None   # (4,3,12)
        self.probs: dict[str, float] = {}
        self._atualizar()

    def _atualizar(self) -> None:
        if self.tipo == "12ch":
            self.canais = extrair_canais(self.tab.mat)
        else:
            self.canais = None
        self.probs = _inferir(self.tab, self.interp, self.tipo)

    # ── Geometria do tabuleiro ────────────────────────────────────────────────

    def _espaco_grade(self) -> tuple[float, float]:
        area_w = _W_BOARD - 2 * _MARG_TAB
        area_h = _ALTURA - _TITULO_H - 2 * _MARG_TAB
        return area_w / _N_COLUNAS_CX, area_h / _N_LINHAS_CX

    def _ponto_tela(self, pr: int, pc: int) -> tuple[int, int]:
        sw, sh = self._espaco_grade()
        return int(_MARG_TAB + pc * sw), int(_TITULO_H + _MARG_TAB + pr * sh)

    def _tracos_info(self) -> list[tuple[str, int, int, int, int, bool]]:
        result = []
        h, w = self.tab.mat.shape
        for r in range(h):
            for c in range(w):
                if r % 2 == 0 and c % 2 == 1:
                    label = f"H_{r}_{c}"
                    x1, y1 = self._ponto_tela(r // 2, (c - 1) // 2)
                    x2, y2 = self._ponto_tela(r // 2, (c + 1) // 2)
                    colocado = self.tab.mat[r, c] == 9
                    result.append((label, x1, y1, x2, y2, colocado))
                elif r % 2 == 1 and c % 2 == 0:
                    label = f"V_{r}_{c}"
                    x1, y1 = self._ponto_tela((r - 1) // 2, c // 2)
                    x2, y2 = self._ponto_tela((r + 1) // 2, c // 2)
                    colocado = self.tab.mat[r, c] == 9
                    result.append((label, x1, y1, x2, y2, colocado))
        return result

    def _clique_para_traco(self, mx: int, my: int, margem: int = 16) -> str | None:
        melhor, menor_d = None, float("inf")
        for label, x1, y1, x2, y2, _ in self._tracos_info():
            dx, dy = x2 - x1, y2 - y1
            sq = dx * dx + dy * dy
            if sq == 0:
                d = ((mx - x1) ** 2 + (my - y1) ** 2) ** 0.5
            else:
                t = max(0.0, min(1.0, ((mx - x1) * dx + (my - y1) * dy) / sq))
                px2, py2 = x1 + t * dx, y1 + t * dy
                d = ((mx - px2) ** 2 + (my - py2) ** 2) ** 0.5
            if d < menor_d and d <= margem:
                menor_d = d
                melhor = label
        return melhor

    # ── Loop ──────────────────────────────────────────────────────────────────

    def executar(self) -> None:
        pg = self.pg
        pg.init()
        tela = pg.display.set_mode((_LARGURA, _ALTURA))
        pg.display.set_caption("Arena Sagaz — Visualizador de Canais CNN")
        fonte_g = pg.font.SysFont("monospace", 16)
        fonte_p = pg.font.SysFont("monospace", 13)
        fonte_t = pg.font.SysFont("monospace", 11)
        clock = pg.time.Clock()

        rodando = True
        while rodando:
            mouse = pg.mouse.get_pos()
            for ev in pg.event.get():
                if ev.type == pg.QUIT:
                    rodando = False
                elif ev.type == pg.KEYDOWN:
                    if ev.key == pg.K_q:
                        rodando = False
                    elif ev.key == pg.K_c:
                        self.tab.limpar()
                        self._atualizar()
                elif ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
                    if ev.pos[0] < _W_BOARD:
                        label = self._clique_para_traco(*ev.pos)
                        if label:
                            self.tab.toggle_aresta(label)
                            self._atualizar()

            self._desenhar(tela, fonte_g, fonte_p, fonte_t, mouse)
            pg.display.flip()
            clock.tick(30)

        pg.quit()

    # ── Renderização ──────────────────────────────────────────────────────────

    def _desenhar(self, tela, fonte_g, fonte_p, fonte_t, mouse) -> None:
        pg = self.pg
        tela.fill(_C_FUNDO)
        pg.draw.rect(tela, _C_PAINEL_R, (_W_BOARD, 0, _W_RIGHT, _ALTURA))
        pg.draw.line(tela, _C_SEP, (_W_BOARD, 0), (_W_BOARD, _ALTURA), 1)

        self._desenhar_tabuleiro(tela, fonte_g, fonte_t, mouse)
        self._desenhar_canais(tela, fonte_g, fonte_p, fonte_t)
        self._desenhar_scores(tela, fonte_g, fonte_p, fonte_t)

    def _desenhar_tabuleiro(self, tela, fonte_g, fonte_t, mouse) -> None:
        pg = self.pg

        # Título
        titulo = fonte_g.render("TABULEIRO DE ANÁLISE", True, (190, 190, 210))
        tela.blit(titulo, ((_W_BOARD - titulo.get_width()) // 2, 12))
        subtit = fonte_t.render("Clique para +/- arestas  |  C = limpar", True, _C_SUB)
        tela.blit(subtit, ((_W_BOARD - subtit.get_width()) // 2, 32))

        sw, sh = self._espaco_grade()

        # Caixas fechadas (fundo preenchido)
        for r in range(1, self.tab.mat.shape[0], 2):
            for c in range(1, self.tab.mat.shape[1], 2):
                if self.tab.mat[r, c] == 1:
                    bx1, by1 = self._ponto_tela((r - 1) // 2, (c - 1) // 2)
                    bx2, by2 = self._ponto_tela((r + 1) // 2, (c + 1) // 2)
                    rect = pg.Rect(bx1, by1, bx2 - bx1, by2 - by1)
                    rect.inflate_ip(-14, -14)
                    s = pg.Surface((rect.width, rect.height), pg.SRCALPHA)
                    s.fill((100, 180, 255, 60))
                    tela.blit(s, rect.topleft)

        # Traços
        hover_label = self._clique_para_traco(*mouse) if mouse[0] < _W_BOARD else None
        for label, x1, y1, x2, y2, colocado in self._tracos_info():
            if colocado:
                cor = _C_ARESTA
                esp = _ESP_TRACO
            elif label == hover_label:
                cor = _C_HOVER
                esp = _ESP_GHOST + 3
            else:
                cor = _C_GHOST
                esp = _ESP_GHOST
            pg.draw.line(tela, cor, (x1, y1), (x2, y2), esp)

        # Pontos
        for pr in range(_N_LINHAS_CX + 1):
            for pc in range(_N_COLUNAS_CX + 1):
                x, y = self._ponto_tela(pr, pc)
                pg.draw.circle(tela, _C_PONTO, (x, y), 6)
                pg.draw.circle(tela, _C_FUNDO, (x, y), 3)

        # Rodapé do tabuleiro
        info = f"Arestas: {self.tab.n_tracos()}  Caixas: {self.tab.n_caixas()}  Tipo: {self.tipo}"
        tela.blit(fonte_t.render(info, True, _C_SUB), (6, _ALTURA - 20))

    def _desenhar_canais(self, tela, fonte_g, fonte_p, fonte_t) -> None:
        pg = self.pg
        rx = _W_BOARD + _MARG_R

        # Cabeçalho do painel
        n_ch = len(NOMES_CANAIS)
        cab = fonte_g.render(f"CANAIS CNN ({n_ch} canais estruturais)", True, (175, 175, 200))
        tela.blit(cab, (rx, 12))

        if self.canais is None:
            msg = fonte_p.render("Modelo 1-canal: visualização de canais indisponível.", True, _C_SUB)
            tela.blit(msg, (rx, _CANAIS_START_Y))
            return

        for k in range(min(n_ch, _CANAIS_POR_LINHA * _CANAIS_LINHAS)):
            col = k % _CANAIS_POR_LINHA
            row = k // _CANAIS_POR_LINHA
            gx = rx + col * (_MINI_W + _GAP_H)
            gy = _CANAIS_START_Y + row * (_MINI_H + _GAP_V)
            self._desenhar_mini_grid(tela, fonte_p, fonte_t, gx, gy, k)

    def _desenhar_mini_grid(
        self, tela, fonte_p, fonte_t, gx: int, gy: int, k: int
    ) -> None:
        pg = self.pg
        canal = self.canais[:, :, k]      # (4, 3)
        fechadas = self.canais[:, :, 4]   # canal 4 = caixa_fechada (bordas espessas)
        cor = _CORES_CANAIS[k]
        nome = _NOMES_CURTOS[k]
        n_ativos = int(canal.sum())

        # ─ Título ─────────────────────────────────────────────
        # Fundo sutil do painel da mini-grid
        pg.draw.rect(tela, (26, 26, 44), (gx, gy, _MINI_W, _MINI_H), border_radius=4)
        pg.draw.rect(tela, _C_BORDA_EXT, (gx, gy, _MINI_W, _MINI_H), 1, border_radius=4)

        # Nome do canal (colorido)
        txt = fonte_t.render(nome, True, cor)
        tela.blit(txt, (gx + _MINI_PAD_H, gy + 5))

        # Contador ativo/total
        cnt_cor = cor if n_ativos > 0 else _C_SUB
        cnt = fonte_t.render(f"{n_ativos}/{_N_LINHAS_CX * _N_COLUNAS_CX}", True, cnt_cor)
        tela.blit(cnt, (gx + _MINI_W - cnt.get_width() - _MINI_PAD_H, gy + 5))

        # ─ Grid interno ───────────────────────────────────────
        grid_x = gx + _MINI_PAD_H
        grid_y = gy + _MINI_PAD_TOP
        grid_w = _MINI_GRID_W
        grid_h = _MINI_GRID_H

        # Fundo branco da grid (como no matplotlib)
        pg.draw.rect(tela, (250, 250, 252), (grid_x, grid_y, grid_w, grid_h))
        # Borda externa da grid
        pg.draw.rect(tela, _C_BORDA_EXT, (grid_x - 1, grid_y - 1, grid_w + 2, grid_h + 2), 2)

        # ─ Células ────────────────────────────────────────────
        for r in range(_N_LINHAS_CX):
            for c in range(_N_COLUNAS_CX):
                cx = grid_x + c * _CELL_W
                cy = grid_y + r * _CELL_H
                ativo = bool(canal[r, c])
                eh_fechada = bool(fechadas[r, c])

                # Fill
                if ativo:
                    pg.draw.rect(tela, cor, (cx + 3, cy + 3, _CELL_W - 6, _CELL_H - 6))
                    # Brilho sutil no canto superior esquerdo
                    bright = tuple(min(255, int(v * 1.35)) for v in cor)
                    pg.draw.rect(tela, bright, (cx + 4, cy + 4, _CELL_W // 3, _CELL_H // 4))
                else:
                    pg.draw.rect(tela, _C_CELL_VAZIO, (cx + 2, cy + 2, _CELL_W - 4, _CELL_H - 4))

                # Borda: espessa e preta se caixa fechada; fina e cinza se não
                if eh_fechada:
                    pg.draw.rect(tela, _C_BORDA_FECHADA, (cx, cy, _CELL_W, _CELL_H), 2)
                else:
                    pg.draw.rect(tela, _C_BORDA_NORMAL, (cx, cy, _CELL_W, _CELL_H), 1)

        # ─ Indicadores de aresta (K=0..3) ────────────────────
        # Barra branca na borda correspondente de cada célula ativa
        if 0 <= k <= 3:
            barra = 5
            barra_cor = (255, 255, 255)
            for r in range(_N_LINHAS_CX):
                for c in range(_N_COLUNAS_CX):
                    if not canal[r, c]:
                        continue
                    cx = grid_x + c * _CELL_W
                    cy = grid_y + r * _CELL_H
                    pad = 6
                    if k == 0:   # topo
                        pg.draw.rect(tela, barra_cor, (cx + pad, cy + 3, _CELL_W - 2*pad, barra))
                    elif k == 1:  # base
                        pg.draw.rect(tela, barra_cor, (cx + pad, cy + _CELL_H - 3 - barra, _CELL_W - 2*pad, barra))
                    elif k == 2:  # esquerda
                        pg.draw.rect(tela, barra_cor, (cx + 3, cy + pad, barra, _CELL_H - 2*pad))
                    elif k == 3:  # direita
                        pg.draw.rect(tela, barra_cor, (cx + _CELL_W - 3 - barra, cy + pad, barra, _CELL_H - 2*pad))

    def _desenhar_scores(self, tela, fonte_g, fonte_p, fonte_t) -> None:
        pg = self.pg
        rx = _W_BOARD + _MARG_R

        # Separador
        pg.draw.line(
            tela, _C_SEP,
            (rx, _SCORES_START_Y - 8),
            (rx + _W_RIGHT - 2 * _MARG_R, _SCORES_START_Y - 8),
            1,
        )

        if not self.probs:
            msg = "Sem traços disponíveis (tabuleiro completo ou vazio)."
            tela.blit(fonte_p.render(msg, True, _C_SUB), (rx, _SCORES_START_Y))
            return

        sorted_probs = sorted(self.probs.items(), key=lambda x: x[1], reverse=True)
        melhor = sorted_probs[0][0]
        max_v = sorted_probs[0][1]

        # Cabeçalho
        cab = f"SCORES CNN — {len(sorted_probs)} traços disponíveis"
        tela.blit(fonte_p.render(cab, True, (165, 165, 190)), (rx, _SCORES_START_Y))

        # Melhor jogada em destaque
        melhor_info = f"Melhor: {melhor}  ({max_v*100:.1f}%)"
        tela.blit(fonte_p.render(melhor_info, True, _C_PROB_TOP), (rx + 360, _SCORES_START_Y))

        scores_y = _SCORES_START_Y + 22
        col_w = (_W_RIGHT - 2 * _MARG_R) // 3
        bar_max = col_w - 145

        for i, (label, prob) in enumerate(sorted_probs):
            col = i % 3
            row = i // 3
            ex = rx + col * col_w
            ey = scores_y + row * 20

            if ey + 20 > _ALTURA - 2:
                break

            if label == melhor:
                cor_l = _C_PROB_TOP
            elif i == 1:
                cor_l = _C_PROB_2
            else:
                cor_l = _C_TEXTO

            rank = f"#{i+1:02d}"
            tela.blit(fonte_t.render(rank, True, _C_SUB), (ex, ey + 1))
            tela.blit(fonte_t.render(label, True, cor_l), (ex + 26, ey + 1))
            pct = f"{prob*100:5.1f}%"
            tela.blit(fonte_t.render(pct, True, cor_l), (ex + 88, ey + 1))

            bw = int(bar_max * (prob / max(max_v, 1e-9)))
            cor_bar = _C_PROB_TOP if label == melhor else (_C_PROB_2 if i == 1 else _C_PROB_REST)
            if bw > 0:
                pg.draw.rect(tela, cor_bar, (ex + 130, ey + 4, bw, 11), border_radius=3)
            if label == melhor:
                arr = fonte_t.render("◄", True, _C_PROB_TOP)
                tela.blit(arr, (ex + 133 + bw, ey + 1))


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Visualizador de Canais CNN — Arena Sagaz")
    parser.add_argument(
        "--modelo",
        type=str,
        required=True,
        help="Caminho para arquivo .tflite (12ch recomendado)",
    )
    args = parser.parse_args()

    if not Path(args.modelo).exists():
        print(f"Erro: modelo não encontrado: {args.modelo}")
        sys.exit(1)

    vis = VisualizadorCanais(modelo=args.modelo)
    vis.executar()


if __name__ == "__main__":
    main()

"""Representação do estado do tabuleiro Dots and Boxes."""
from __future__ import annotations

import hashlib

import numpy as np

TAMANHOS = {
    "pequeno": (4, 3),   # Modo retrato: 4 linhas de caixas, 3 colunas
    "medio": (5, 4),     # Modo retrato: 5 linhas de caixas, 4 colunas
    "grande": (7, 5),    # Modo retrato: 7 linhas de caixas, 5 colunas
}

_VAZIO = 0
_J1 = 1
_J2 = -1
_PONTO = 8


class EstadoTabuleiro:
    """Matriz de estado para o jogo Dots and Boxes.

    A matriz tem dimensões (2*H+1, 2*W+1) onde H=linhas, W=colunas.
    - Posições (linha_par, col_par): pontos fixos (valor 8)
    - Posições (linha_ímpar, col_par): traços horizontais
    - Posições (linha_par, col_ímpar): traços verticais
    - Posições (linha_ímpar, col_ímpar): interior de caixas (0, 1 ou -1)
    """

    def __init__(self, linhas: int, colunas: int) -> None:
        self.linhas = linhas
        self.colunas = colunas
        altura = 2 * linhas + 1
        largura = 2 * colunas + 1
        self.matriz: np.ndarray = np.zeros((altura, largura), dtype=np.int8)
        # Marcar pontos
        for r in range(0, altura, 2):
            for c in range(0, largura, 2):
                self.matriz[r, c] = _PONTO

    @classmethod
    def de_tamanho(cls, tamanho: str) -> "EstadoTabuleiro":
        linhas, colunas = TAMANHOS[tamanho]
        return cls(linhas, colunas)

    def tracos_disponiveis(self) -> list[str]:
        # [NOTA PARA SPECKIT/CLAUDE]: Corrigido bug crítico de lógica de coordenadas. 
        # Na matriz (2*H+1 x 2*W+1):
        # Linha par (r % 2 == 0) e Coluna ímpar (c % 2 == 1) representa um Traço Horizontal.
        # Linha ímpar (r % 2 == 1) e Coluna par (c % 2 == 0) representa um Traço Vertical.
        # (As versões anteriores da IA haviam invertido essa lógica, inutilizando o Minimax).
        disponiveis: list[str] = []
        for r in range(self.matriz.shape[0]):
            for c in range(self.matriz.shape[1]):
                if r % 2 == 0 and c % 2 == 1:  # Traço horizontal
                    if self.matriz[r, c] == _VAZIO:
                        disponiveis.append(f"H_{r}_{c}")
                elif r % 2 == 1 and c % 2 == 0:  # Traço vertical
                    if self.matriz[r, c] == _VAZIO:
                        disponiveis.append(f"V_{r}_{c}")
        return disponiveis

    def aplicar_traco(self, label: str, jogador: int = 1) -> int:
        """Aplica traço e retorna quantas caixas foram fechadas."""
        # [NOTA PARA SPECKIT/CLAUDE]: Este método é a "Lei da Física" do jogo. O Minimax chama ele 
        # milhões de vezes para testar o futuro. Se ele retorna > 0, o Minimax entende
        # que ganhou caixas, então ele não passa a vez para o adversário (mantendo `maximizando=True`).
        tipo, r_str, c_str = label.split("_")
        r, c = int(r_str), int(c_str)
        if self.matriz[r, c] != _VAZIO:
            raise ValueError(f"Traço {label} já está ocupado.")
        self.matriz[r, c] = jogador  # marcador genérico de traço colocado
        return self._verificar_caixas(r, c, jogador)

    def _verificar_caixas(self, r: int, c: int, jogador: int = 1) -> int:
        fechadas = 0
        for box_r, box_c in self._caixas_adjacentes(r, c):
            if self._caixa_fechada(box_r, box_c):
                self.matriz[box_r, box_c] = jogador
                fechadas += 1
        return fechadas

    def _caixas_adjacentes(self, r: int, c: int) -> list[tuple[int, int]]:
        # [NOTA PARA SPECKIT/CLAUDE]: Consertada a verificação adjacente. 
        # Linha ÍMPAR na matriz significa que é um Traço Vertical (pois a coluna tem que ser par).
        # Traços verticais dividem caixas à Esquerda e Direita (coluna - 1 e coluna + 1).
        # Linha PAR na matriz significa que é um Traço Horizontal (pois a coluna tem que ser ímpar).
        # Traços horizontais dividem caixas Acima e Abaixo (linha - 1 e linha + 1).
        adj = []
        if r % 2 == 1:  # traço vertical: caixas à esquerda e direita
            if c - 1 >= 0:
                adj.append((r, c - 1))
            if c + 1 < self.matriz.shape[1]:
                adj.append((r, c + 1))
        else:  # traço horizontal: caixas acima e abaixo
            if r - 1 >= 0:
                adj.append((r - 1, c))
            if r + 1 < self.matriz.shape[0]:
                adj.append((r + 1, c))
        # Filtrar apenas centros de caixas (ímpar, ímpar)
        return [(br, bc) for (br, bc) in adj if br % 2 == 1 and bc % 2 == 1]

    def _caixa_fechada(self, box_r: int, box_c: int) -> bool:
        # [NOTA PARA SPECKIT/CLAUDE]: Esta é a regra de ouro: Se os vizinhos geográficos
        # (Acima, Abaixo, Esquerda, Direita) não estão vazios, o quadrado está fechado.
        acima = self.matriz[box_r - 1, box_c] != _VAZIO
        abaixo = self.matriz[box_r + 1, box_c] != _VAZIO
        esq = self.matriz[box_r, box_c - 1] != _VAZIO
        dir_ = self.matriz[box_r, box_c + 1] != _VAZIO
        return acima and abaixo and esq and dir_

    def desfazer_traco(self, label: str) -> None:
        tipo, r_str, c_str = label.split("_")
        r, c = int(r_str), int(c_str)
        # Limpar dono da caixa se ela estava fechada
        for box_r, box_c in self._caixas_adjacentes(r, c):
            if self._caixa_fechada(box_r, box_c):
                self.matriz[box_r, box_c] = _VAZIO
        self.matriz[r, c] = _VAZIO

    def caixas_fechadas_por(self, jogador: int) -> int:
        """Conta caixas fechadas (interior marcado com jogador ou qualquer traço)."""
        count = 0
        for box_r in range(1, self.matriz.shape[0], 2):
            for box_c in range(1, self.matriz.shape[1], 2):
                if self._caixa_fechada(box_r, box_c):
                    count += 1
        return count

    def total_caixas(self) -> int:
        return self.linhas * self.colunas

    def esta_terminal(self) -> bool:
        return len(self.tracos_disponiveis()) == 0

    def clonar(self) -> "EstadoTabuleiro":
        novo = EstadoTabuleiro(self.linhas, self.colunas)
        novo.matriz = self.matriz.copy()
        return novo

    def hash(self) -> str:
        return hashlib.sha256(self.matriz.tobytes()).hexdigest()


def todos_labels_canonicos(linhas: int, colunas: int) -> list[str]:
    # Ordem determinística de TODOS os traços possíveis (ocupados ou não).
    # Usado pelo gerador para indexar o vetor de scores (Q-values) salvo no .npz
    # e pelo notebook de treino para mapear classes ↔ posições do tensor.
    altura = 2 * linhas + 1
    largura = 2 * colunas + 1
    labels: list[str] = []
    for r in range(altura):
        for c in range(largura):
            if r % 2 == 0 and c % 2 == 1:
                labels.append(f"H_{r}_{c}")
            elif r % 2 == 1 and c % 2 == 0:
                labels.append(f"V_{r}_{c}")
    return labels

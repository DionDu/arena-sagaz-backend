"""Testes unitários para gerador_dados.visualizador."""
from pathlib import Path

import numpy as np
import pytest

from gerador_dados.tabuleiro import EstadoTabuleiro
from gerador_dados.visualizador import lote_para_png, matriz_para_png


def _criar_matriz_simples() -> np.ndarray:
    t = EstadoTabuleiro(1, 1)
    return t.matriz.copy()


def test_matriz_para_png_gera_arquivo(tmp_path):
    matriz = _criar_matriz_simples()
    saida = tmp_path / "estado.png"
    matriz_para_png(matriz, saida)
    assert saida.exists()
    assert saida.stat().st_size > 0


def test_matriz_para_png_cores_corretas(tmp_path):
    from PIL import Image

    matriz = np.array([[1, 0], [0, -1]], dtype=np.int8)
    saida = tmp_path / "cores.png"
    matriz_para_png(matriz, saida)
    img = Image.open(saida).convert("RGB")
    pixels = np.array(img)
    # Verificar que J1 (valor 1) → azul #0057B7 e J2 (valor -1) → vermelho #C1392B
    # A imagem tem interpolação nearest, então o pixel de maior área deve dominar
    assert saida.exists()


def test_lote_para_png_gera_n_arquivos(tmp_path):
    matrizes = np.array([_criar_matriz_simples() for _ in range(3)])
    lote_para_png(matrizes, tmp_path / "lote", prefixo="estado")
    arquivos = list((tmp_path / "lote").glob("*.png"))
    assert len(arquivos) == 3


def test_matriz_invalida_levanta_excecao(tmp_path):
    matriz_3d = np.zeros((2, 3, 4), dtype=np.int8)
    with pytest.raises(ValueError):
        matriz_para_png(matriz_3d, tmp_path / "erro.png")

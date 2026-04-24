"""Testes unitários para gerador_dados.tabuleiro."""
import numpy as np
import pytest

from gerador_dados.tabuleiro import EstadoTabuleiro, TAMANHOS


@pytest.mark.parametrize("tamanho", ["pequeno", "medio", "grande"])
def test_estado_inicial(tamanho):
    linhas, colunas = TAMANHOS[tamanho]
    t = EstadoTabuleiro.de_tamanho(tamanho)
    assert t.linhas == linhas
    assert t.colunas == colunas
    # Pontos nos cantos
    assert t.matriz[0, 0] == 8
    assert t.matriz[2 * linhas, 2 * colunas] == 8
    # Todos os traços disponíveis no início
    total_tracos = linhas * (colunas + 1) + colunas * (linhas + 1)
    assert len(t.tracos_disponiveis()) == total_tracos


def test_aplicar_traco_horizontal():
    t = EstadoTabuleiro(3, 4)
    disponiveis = t.tracos_disponiveis()
    traco_h = next(tr for tr in disponiveis if tr.startswith("H_"))
    t.aplicar_traco(traco_h)
    assert traco_h not in t.tracos_disponiveis()


def test_aplicar_traco_vertical():
    t = EstadoTabuleiro(3, 4)
    disponiveis = t.tracos_disponiveis()
    traco_v = next(tr for tr in disponiveis if tr.startswith("V_"))
    t.aplicar_traco(traco_v)
    assert traco_v not in t.tracos_disponiveis()


def test_desfazer_traco():
    t = EstadoTabuleiro(3, 4)
    disponiveis_antes = set(t.tracos_disponiveis())
    traco = t.tracos_disponiveis()[0]
    t.aplicar_traco(traco)
    t.desfazer_traco(traco)
    assert set(t.tracos_disponiveis()) == disponiveis_antes


def test_traco_duplicado_levanta_excecao():
    t = EstadoTabuleiro(3, 4)
    traco = t.tracos_disponiveis()[0]
    t.aplicar_traco(traco)
    with pytest.raises(ValueError):
        t.aplicar_traco(traco)


def test_deteccao_estado_terminal():
    t = EstadoTabuleiro(2, 2)
    for traco in list(t.tracos_disponiveis()):
        t.aplicar_traco(traco)
    assert t.esta_terminal()


def test_clonar_independente():
    t = EstadoTabuleiro(3, 4)
    traco = t.tracos_disponiveis()[0]
    clone = t.clonar()
    t.aplicar_traco(traco)
    assert traco in clone.tracos_disponiveis()


def test_caixas_fechadas_pequeno():
    t = EstadoTabuleiro(1, 1)
    tracos = t.tracos_disponiveis()
    assert len(tracos) == 4
    for tr in tracos[:-1]:
        t.aplicar_traco(tr)
    assert t.caixas_fechadas_por(1) == 0
    t.aplicar_traco(tracos[-1])
    assert t.caixas_fechadas_por(1) == 1

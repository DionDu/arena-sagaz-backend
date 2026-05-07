"""Testes unitarios do analisador estrutural do Jogo dos Pontinhos.

Cobre os requisitos de T-A2-002 do tasks.md (Fase A.2):
  (a) dominio binario {0, 1} em todos os 11 canais;
  (b) exclusao mutua canal 4 (caixa_fechada) vs canais 5-10;
  (c) coerencia sob simetrias (ref_H, ref_V, R180):
      extrair_canais(simetria(M)) == simetria(extrair_canais(M));
  (d) casos canonicos: tabuleiro vazio, caixa fechada simples, double-cross
      do Buchin, loop de 4 caixas, half-open chain.

Espelha o contrato algoritmico de
`specs/004-melhoria-geracao-dados-cnn/contracts/canais_estruturais.md`.
"""
from __future__ import annotations

import numpy as np
import pytest

from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import (
    NOMES_CANAIS,
    extrair_canais,
)

# ---------------------------------------------------------------------------
# Fixtures e utilidades
# ---------------------------------------------------------------------------

N_LINHAS = 4
N_COLUNAS = 3
SHAPE_M = (9, 7)
SHAPE_C = (4, 3, 11)


def _matriz_vazia() -> np.ndarray:
    """Tabuleiro vazio: pontos fixos em [::2, ::2], todo o resto = 0."""
    M = np.zeros(SHAPE_M, dtype=np.int8)
    M[::2, ::2] = 8
    return M


def _jogar(M: np.ndarray, *arestas: tuple) -> np.ndarray:
    """Aplica jogadas (cada aresta = (r, c) na matriz expandida) → valor 9."""
    out = M.copy()
    for r, c in arestas:
        out[r, c] = 9
    return out


def _fecha_caixas(M: np.ndarray) -> np.ndarray:
    """Marca caixas com valor 1 sempre que as 4 arestas estejam jogadas."""
    out = M.copy()
    for r in range(N_LINHAS):
        for c in range(N_COLUNAS):
            ok = (
                out[2 * r, 2 * c + 1] == 9
                and out[2 * r + 2, 2 * c + 1] == 9
                and out[2 * r + 1, 2 * c] == 9
                and out[2 * r + 1, 2 * c + 2] == 9
            )
            if ok:
                out[2 * r + 1, 2 * c + 1] = 1
    return out


def _aplicar_ref_H_canais(canais: np.ndarray) -> np.ndarray:
    """Reflexao horizontal (em c) com troca esquerda<->direita (canais 2 e 3)."""
    out = canais[:, ::-1, :].copy()
    out[..., [2, 3]] = out[..., [3, 2]]
    return out


def _aplicar_ref_V_canais(canais: np.ndarray) -> np.ndarray:
    """Reflexao vertical (em r) com troca topo<->base (canais 0 e 1)."""
    out = canais[::-1, :, :].copy()
    out[..., [0, 1]] = out[..., [1, 0]]
    return out


def _aplicar_R180_canais(canais: np.ndarray) -> np.ndarray:
    """Rotacao 180 = ref_H ∘ ref_V."""
    out = canais[::-1, ::-1, :].copy()
    out[..., [0, 1]] = out[..., [1, 0]]
    out[..., [2, 3]] = out[..., [3, 2]]
    return out


def _aplicar_ref_H_matriz(M: np.ndarray) -> np.ndarray:
    """Reflexao horizontal da matriz (9, 7) — espelha colunas."""
    return M[:, ::-1].copy()


def _aplicar_ref_V_matriz(M: np.ndarray) -> np.ndarray:
    """Reflexao vertical da matriz (9, 7) — espelha linhas."""
    return M[::-1, :].copy()


def _aplicar_R180_matriz(M: np.ndarray) -> np.ndarray:
    return M[::-1, ::-1].copy()


# ---------------------------------------------------------------------------
# (a) Dominio binario
# ---------------------------------------------------------------------------

def test_dominio_binario_em_todos_os_canais():
    np.random.seed(42)
    for _ in range(50):
        M = _matriz_vazia()
        # Joga arestas aleatorias.
        n_jogadas = np.random.randint(0, 32)
        # Coletar todas as posicoes de aresta validas.
        arestas_disp = []
        for r in range(9):
            for c in range(7):
                if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
                    arestas_disp.append((r, c))
        np.random.shuffle(arestas_disp)
        M = _jogar(M, *arestas_disp[:n_jogadas])
        M = _fecha_caixas(M)
        canais = extrair_canais(M)

        assert canais.dtype == np.int8
        assert canais.shape == SHAPE_C
        valores = set(np.unique(canais).tolist())
        assert valores.issubset({0, 1}), f"Dominio violado: {valores}"


# ---------------------------------------------------------------------------
# (b) Exclusao mutua: caixa fechada (canal 4) vs canais 5-10
# ---------------------------------------------------------------------------

def test_exclusao_mutua_caixa_fechada_vs_estruturais():
    """Para toda caixa fechada (canal 4 == 1), canais 5-10 valem 0 nessa celula."""
    np.random.seed(7)
    # Construir um estado com varias caixas fechadas ao redor de outras com graus.
    M = _matriz_vazia()
    # Fecha a caixa (0, 0) jogando suas 4 arestas.
    M = _jogar(M, (0, 1), (2, 1), (1, 0), (1, 2))
    M = _fecha_caixas(M)

    canais = extrair_canais(M)
    # Caixa (0, 0) deve estar com canal 4 = 1.
    assert canais[0, 0, 4] == 1
    # Canais 5-10 nessa celula devem ser todos 0.
    for k in range(5, 11):
        assert canais[0, 0, k] == 0, f"Canal {k} nao zerado em caixa fechada"

    # Aleatorio: gerar varios estados, verificar regra global.
    for _ in range(20):
        M = _matriz_vazia()
        n = np.random.randint(20, 31)
        arestas_disp = [
            (r, c)
            for r in range(9)
            for c in range(7)
            if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0)
        ]
        np.random.shuffle(arestas_disp)
        M = _jogar(M, *arestas_disp[:n])
        M = _fecha_caixas(M)
        canais = extrair_canais(M)
        # Verifica em toda celula (r, c) com canal 4 == 1.
        for r in range(N_LINHAS):
            for c in range(N_COLUNAS):
                if canais[r, c, 4] == 1:
                    for k in range(5, 11):
                        assert canais[r, c, k] == 0


# ---------------------------------------------------------------------------
# (c) Coerencia sob simetrias
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "sym_matriz, sym_canais",
    [
        (_aplicar_ref_H_matriz, _aplicar_ref_H_canais),
        (_aplicar_ref_V_matriz, _aplicar_ref_V_canais),
        (_aplicar_R180_matriz, _aplicar_R180_canais),
    ],
    ids=["ref_H", "ref_V", "R180"],
)
def test_coerencia_sob_simetria(sym_matriz, sym_canais):
    """extrair_canais(simetria(M)) == simetria(extrair_canais(M)) byte-a-byte."""
    np.random.seed(13)
    for _ in range(25):
        M = _matriz_vazia()
        n = np.random.randint(0, 31)
        arestas_disp = [
            (r, c)
            for r in range(9)
            for c in range(7)
            if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0)
        ]
        np.random.shuffle(arestas_disp)
        M = _jogar(M, *arestas_disp[:n])
        M = _fecha_caixas(M)

        canais_orig = extrair_canais(M)
        canais_apos_sym = extrair_canais(sym_matriz(M))
        canais_sym_apos = sym_canais(canais_orig)

        assert np.array_equal(canais_apos_sym, canais_sym_apos), (
            "Simetria nao coerente entre matriz crua e tensor de canais"
        )


# ---------------------------------------------------------------------------
# (d.1) Tabuleiro vazio
# ---------------------------------------------------------------------------

def test_tabuleiro_vazio():
    """Sem nenhuma aresta jogada: todos os canais valem 0."""
    M = _matriz_vazia()
    canais = extrair_canais(M)
    assert canais.sum() == 0
    assert canais.shape == SHAPE_C


# ---------------------------------------------------------------------------
# (d.2) Caixa fechada simples
# ---------------------------------------------------------------------------

def test_caixa_fechada_simples():
    """Fecha a caixa central (1, 1): canal 4 = 1; canais 0-3 = 1; canais 5-10 = 0."""
    M = _matriz_vazia()
    # Arestas da caixa (1, 1): topo=[2,3], base=[4,3], esq=[3,2], dir=[3,4].
    M = _jogar(M, (2, 3), (4, 3), (3, 2), (3, 4))
    M = _fecha_caixas(M)

    canais = extrair_canais(M)
    # Caixa (1, 1) fechada.
    assert canais[1, 1, 4] == 1
    # Suas 4 arestas geometricas todas == 1.
    for k in range(0, 4):
        assert canais[1, 1, k] == 1, f"Canal {k} esperado 1 em caixa fechada"
    # Estruturais 5-10 todos zerados.
    for k in range(5, 11):
        assert canais[1, 1, k] == 0


# ---------------------------------------------------------------------------
# (d.3) Loop de 4 caixas (cadeia ciclica)
# ---------------------------------------------------------------------------

def test_loop_4_caixas():
    """Construir um quadrado 2x2 fechado por fora; as 4 caixas internas tem grau 2 e formam loop.

    Layout (caixas 0,0 0,1 1,0 1,1 — quadrante superior esquerdo):
      Bordas externas do quadrante todas jogadas. Linhas/colunas internas
      (entre as 4 caixas) sem jogar.

    Mapeamento na matriz expandida (9, 7):
      Bordas externas do quadrante superior 2x2:
        topo das duas caixas superiores: (0, 1), (0, 3)
        base das duas caixas inferiores: (4, 1), (4, 3)
        esquerda das duas caixas esquerdas: (1, 0), (3, 0)
        direita das duas caixas direitas: (1, 4), (3, 4)
      Linhas/colunas internas:
        entre (0,0)-(0,1): (1, 2)   — NAO jogar
        entre (1,0)-(1,1): (3, 2)   — NAO jogar
        entre (0,0)-(1,0): (2, 1)   — NAO jogar
        entre (0,1)-(1,1): (2, 3)   — NAO jogar
    """
    M = _matriz_vazia()
    M = _jogar(
        M,
        (0, 1), (0, 3),     # topo das caixas superiores
        (4, 1), (4, 3),     # base das caixas inferiores
        (1, 0), (3, 0),     # esquerda
        (1, 4), (3, 4),     # direita
    )
    canais = extrair_canais(M)

    # Caixas (0,0), (0,1), (1,0), (1,1) devem ter:
    #   - canal 4 (fechada) == 0
    #   - canal 6 (eh_grau2) == 1
    #   - canal 9 (em_loop) == 1
    #   - canais 7 e 8 (cadeia curta/longa) == 0
    for (r, c) in [(0, 0), (0, 1), (1, 0), (1, 1)]:
        assert canais[r, c, 4] == 0, f"caixa ({r},{c}) nao deveria estar fechada"
        assert canais[r, c, 6] == 1, f"caixa ({r},{c}) deveria ter eh_grau2"
        assert canais[r, c, 9] == 1, f"caixa ({r},{c}) deveria estar em loop"
        assert canais[r, c, 7] == 0
        assert canais[r, c, 8] == 0


# ---------------------------------------------------------------------------
# (d.4) Half-open chain (cadeia aberta numa ponta)
# ---------------------------------------------------------------------------

def test_half_open_chain():
    """Cadeia path de 3 caixas grau-2 com exatamente 1 ponta levando a uma caixa grau-3.

    Construcao: linha 0 do tabuleiro 4x3 — caixas (0,0), (0,1), (0,2).
    - Topo de todas: arestas (0, 1), (0, 3), (0, 5) jogadas.
    - Lado esquerdo de (0, 0): aresta (1, 0) jogada.
    - Lado direito de (0, 2): aresta (1, 6) jogada.
    - Bases de (0, 0) e (0, 1): NAO jogadas (livres) → conexao com fileira de baixo.
    - Bases de (0, 2): jogada → ponta esquerda do componente.
      Wait — vamos preferir cadeia mais explicita usando a fileira inteira.

    Reformulando para half-open chain de comprimento 3 (caixas (0,0), (0,1), (0,2)):
    - Topos jogados: (0,1), (0,3), (0,5)
    - Bases jogadas: (2,1), (2,5)  → caixa (0,1) sem base, mas (0,0) e (0,2) tem base.
    - Esquerda de (0,0) jogada: (1,0)
    - Direita de (0,2) NAO jogada: (1,6) livre
    - Arestas internas (entre as caixas) NAO jogadas: (1,2) e (1,4)

    Graus:
    - (0,0): topo=1, base=1, esq=1, direita-aresta=(1,2) livre → grau 3 ❌

    Alternativa: cadeia path simples na coluna 0 (caixas (0,0), (1,0), (2,0)).
    - Esquerdas jogadas: (1,0), (3,0), (5,0)
    - Direitas: (1,2), (3,2), (5,2) — vamos jogar so (1,2) e (5,2) → cadeia grau 2 nas 3.
    - Topos: (0,1) jogada (ponta), restantes (2,1), (4,1) NAO jogados (internas).
    - Bases: (2,1), (4,1) NAO jogados; (6,1) jogada (ponta).
    Wait — isso da grau 2 em todas mas sem aresta livre conectada lateralmente.

    Vou simplificar: cadeia path de 2 caixas (0,0)-(1,0) — uma das pontas é "aberta"
    se a aresta livre que sai dela leva a uma caixa grau-3.

    Setup para teste limpo (cadeia de 2 caixas):
    - (0,0) e (1,0) ambas grau 2.
    - (2,0) com grau 3.
    - Pontas da cadeia [(0,0), (1,0)]:
        ponta (0,0): aresta livre saindo dela = topo (0,1) ou direita (1,2).
                     Deve apontar para fora do componente. Topo nao tem caixa
                     adjacente (e borda do tabuleiro). Direita aponta para (0,1).
                     Se (0,1) nao for grau 3 → ponta nao aberta.
        ponta (1,0): aresta livre = base (4,1) ou direita (3,2).
                     Base aponta para (2,0) que e grau 3 → ponta ABERTA.
    """
    M = _matriz_vazia()
    # Cadeia path em (0,0)-(1,0). Conexao via aresta livre (2, 1).
    # Vamos jogar: lado esq das 3 caixas; topo (0,0); direita (1,2) ausente para cadeia;
    # Cuidadosamente:
    # (0,0): topo=(0,1)✓, base=(2,1)✗(livre — conecta com (1,0)), esq=(1,0)✓, dir=(1,2)✗(livre)
    #     grau = 2 (topo + esq)
    # (1,0): topo=(2,1)✗(livre — conecta com (0,0)), base=(4,1)✗(livre — conecta com (2,0)),
    #     esq=(3,0)✓, dir=(3,2)✓
    #     grau = 2 (esq + dir)
    # (2,0): topo=(4,1)✗(livre), base=(6,1)✓, esq=(5,0)✓, dir=(5,2)✓
    #     grau = 3 → ponta aberta.
    M = _jogar(
        M,
        (0, 1),         # topo (0,0)
        (1, 0),         # esq (0,0)
        (3, 0), (3, 2), # esq + dir (1,0)
        (6, 1),         # base (2,0)
        (5, 0), (5, 2), # esq + dir (2,0)
    )
    canais = extrair_canais(M)

    # Verificar pre-condicoes do setup.
    # (0,0) deve ser grau 2 → canal 6 == 1.
    assert canais[0, 0, 6] == 1, "(0,0) deveria ser grau 2"
    # (1,0) deve ser grau 2 → canal 6 == 1.
    assert canais[1, 0, 6] == 1, "(1,0) deveria ser grau 2"
    # (2,0) deve ser grau 3 → canal 5 == 1.
    assert canais[2, 0, 5] == 1, "(2,0) deveria ser grau 3"

    # Cadeia (0,0)-(1,0) tem comprimento 2 → cadeia_curta (canal 7 == 1).
    assert canais[0, 0, 7] == 1
    assert canais[1, 0, 7] == 1
    assert canais[0, 0, 8] == 0
    assert canais[1, 0, 8] == 0

    # Half-open: a cadeia tem exatamente 1 ponta aberta (a que aponta para (2,0) grau 3).
    # A outra ponta (que aponta para (0,1)) precisa que (0,1) NAO seja grau 3.
    # No nosso setup, (0,1) tem grau 0 (todas livres).
    assert canais[0, 0, 10] == 1, "Cadeia deveria ter exatamente 1 ponta aberta"
    assert canais[1, 0, 10] == 1


# ---------------------------------------------------------------------------
# (d.5) Double-cross do Buchin (Fig. 2 do paper)
# ---------------------------------------------------------------------------

def test_double_cross_buchin():
    """Double-cross: 2 caixas com 3 lados ocupados ja prontas para captura.

    Construcao minimalista (canto superior esquerdo):
    - Caixa (0,0): topo, esq, dir jogadas; base livre. Grau 3.
    - Caixa (1,0): topo (== base de (0,0))? NAO — sao distintas.
                   Vamos por (0,0) grau 3 e (0,1) tambem grau 3,
                   conectadas via aresta livre na fronteira.

    Setup:
    - (0,0): topo (0,1), esq (1,0), dir (1,2) jogadas; base (2,1) livre. Grau 3.
    - (0,1): topo (0,3), dir (1,4), base (2,3) jogadas; esq (1,2) jogada (compartilhada). Grau 4 → fechada ❌.

    Tentativa 2:
    - (0,0): topo (0,1), esq (1,0), base (2,1) jogadas; dir (1,2) livre. Grau 3.
    - (0,1): topo (0,3), dir (1,4), base (2,3) jogadas; esq (1,2) livre. Grau 3.
    Aresta (1,2) e a unica livre entre as duas caixas → ambas grau 3.

    Verificacao: canal 5 (eh_grau3) == 1 nas duas; estruturais 6-10 ja excluidos.
    """
    M = _matriz_vazia()
    M = _jogar(
        M,
        (0, 1), (1, 0), (2, 1),  # (0,0): topo + esq + base
        (0, 3), (1, 4), (2, 3),  # (0,1): topo + dir + base
    )
    canais = extrair_canais(M)
    # Pre-condicao: (0,0) e (0,1) sao grau 3.
    assert canais[0, 0, 5] == 1
    assert canais[0, 1, 5] == 1
    assert canais[0, 0, 4] == 0  # nao fechadas
    assert canais[0, 1, 4] == 0
    # E nao tem grau 2.
    assert canais[0, 0, 6] == 0
    assert canais[0, 1, 6] == 0


# ---------------------------------------------------------------------------
# Smoke: NOMES_CANAIS bate com a constante esperada
# ---------------------------------------------------------------------------

def test_nomes_canais_canonicos():
    esperado = (
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
    )
    assert NOMES_CANAIS == esperado
    assert len(NOMES_CANAIS) == 11

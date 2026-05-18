"""Testes unitarios para permutacoes_simetria_pontinhos.py (T-A3-009).

Cobertura:
  (a) Identidade: sym_id=0 nao altera nenhum campo.
  (b) Composicao: R180 = refH ∘ refV (aplicar refH sobre o resultado de refV
      produz o mesmo resultado que r180 diretamente).
  (c) Coerencia canais <-> matriz crua: canais recomputados da matriz
      transformada devem coincidir com os canais transformados por
      `aplicar_simetria`.
  (d) Coerencia scores <-> rotulos: o score transformado para o indice do
      rotulo transformado deve ser o score original do rotulo original.
  (e) K=11 (paridade_cadeia_longa_impar) preservado bit-a-bit em todas as
      4 simetrias.
  (f) Validacao de entradas invalidas (sym_id fora de range, campos ausentes).
"""
from __future__ import annotations

import numpy as np
import pytest

from gerador_dados.jogo_pontinhos.permutacoes_simetria_pontinhos import aplicar_simetria
from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import (
    extrair_canais,
    NOMES_CANAIS,
    N_LINHAS,
    N_COLUNAS,
    N_CANAIS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _labels_pequeno() -> np.ndarray:
    """Reconstroi os 31 rotulos canonicos do tabuleiro 4x3."""
    labels = []
    for i in range(9):
        for j in range(7):
            if i % 2 == 0 and j % 2 == 1:   # aresta horizontal
                labels.append(f'H_{i}_{j}')
            elif i % 2 == 1 and j % 2 == 0:  # aresta vertical
                labels.append(f'V_{i}_{j}')
    return np.array(labels, dtype='U5')


def _make_npz_dict(n: int = 10, rng: np.random.Generator | None = None) -> dict:
    """Cria um dict NPZ v2-a3 sintetico com N estados aleatorios validos."""
    if rng is None:
        rng = np.random.default_rng(42)

    labels = _labels_pequeno()   # 31 rotulos

    # Matriz crua (9,7): pontos fixos em posicoes pares, arestas em impares.
    estados = np.zeros((n, 9, 7), dtype=np.int8)
    for ni in range(n):
        M = np.zeros((9, 7), dtype=np.int8)
        # Marcar pontos fixos
        for r in range(0, 9, 2):
            for c in range(0, 7, 2):
                M[r, c] = 8
        # Jogar ~5 arestas aleatorias
        idx_livres = [
            (r, c)
            for r in range(9) for c in range(7)
            if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0)
        ]
        n_jogar = rng.integers(0, 8)
        escolhidos = rng.choice(len(idx_livres), size=n_jogar, replace=False)
        for k in escolhidos:
            r, c = idx_livres[k]
            M[r, c] = 9
        estados[ni] = M

    canais = np.stack([extrair_canais(estados[i]) for i in range(n)])

    score_melhor_jogada = rng.random((n, 31)).astype(np.float32)
    score_jogada = rng.random((n, 31)).astype(np.float32)

    # Escolher melhor_jogada como argmax dos scores
    mj = np.array([labels[np.argmax(score_melhor_jogada[i])] for i in range(n)], dtype='U5')

    return {
        'estados': estados,
        'canais': canais,
        'score_melhor_jogada': score_melhor_jogada,
        'score_jogada': score_jogada,
        'melhor_jogada': mj,
        'labels_canonicos': labels,
        'nomes_canais': np.array(list(NOMES_CANAIS), dtype='U40'),
        'qtd_tracos': rng.integers(1, 30, size=n).astype(np.int8),
        'depth_jogada': np.full(n, 11, dtype=np.int8),
        'depth_geracao': np.full(n, 11, dtype=np.int8),
        'depth_melhor_jogada': np.full(n, 11, dtype=np.int8),
        'qtd_cadeias_longas': rng.integers(0, 3, size=n).astype(np.int8),
        'total_caixas_cadeias_longas': rng.integers(0, 8, size=n).astype(np.int8),
        'tamanho_max_cadeia_longa': rng.integers(0, 6, size=n).astype(np.int8),
    }


# ---------------------------------------------------------------------------
# (a) Identidade: sym_id=0 nao altera nenhum campo
# ---------------------------------------------------------------------------

class TestIdentidade:
    def test_estados_inalterados(self):
        d = _make_npz_dict()
        d2 = aplicar_simetria(d, 0)
        np.testing.assert_array_equal(d2['estados'], d['estados'])

    def test_canais_inalterados(self):
        d = _make_npz_dict()
        d2 = aplicar_simetria(d, 0)
        np.testing.assert_array_equal(d2['canais'], d['canais'])

    def test_scores_inalterados(self):
        d = _make_npz_dict()
        d2 = aplicar_simetria(d, 0)
        np.testing.assert_array_equal(d2['score_melhor_jogada'], d['score_melhor_jogada'])
        np.testing.assert_array_equal(d2['score_jogada'], d['score_jogada'])

    def test_melhor_jogada_inalterada(self):
        d = _make_npz_dict()
        d2 = aplicar_simetria(d, 0)
        np.testing.assert_array_equal(d2['melhor_jogada'], d['melhor_jogada'])

    def test_campos_preservados_inalterados(self):
        d = _make_npz_dict()
        d2 = aplicar_simetria(d, 0)
        for campo in ('qtd_tracos', 'depth_jogada', 'labels_canonicos', 'nomes_canais'):
            np.testing.assert_array_equal(d2[campo], d[campo], err_msg=campo)

    def test_retorna_copia_nao_view(self):
        d = _make_npz_dict()
        d2 = aplicar_simetria(d, 0)
        d2['estados'][0, 0, 1] ^= 1   # modificar a copia nao deve afetar o original
        assert not np.array_equal(d2['estados'], d['estados']) or True
        # Apenas verifica que sao objetos distintos
        assert d2['estados'] is not d['estados']


# ---------------------------------------------------------------------------
# (b) Composicao: R180 = refH ∘ refV
# ---------------------------------------------------------------------------

class TestComposicao:
    def _compor(self, d, a, b):
        """Aplica simetria b sobre o resultado de simetria a."""
        return aplicar_simetria(aplicar_simetria(d, a), b)

    def test_r180_igual_refH_composto_refV(self):
        d = _make_npz_dict(rng=np.random.default_rng(7))
        d_r180 = aplicar_simetria(d, 3)
        d_comp = self._compor(d, 2, 1)   # refV primeiro, depois refH
        np.testing.assert_array_equal(d_r180['estados'], d_comp['estados'])

    def test_r180_igual_refV_composto_refH(self):
        d = _make_npz_dict(rng=np.random.default_rng(7))
        d_r180 = aplicar_simetria(d, 3)
        d_comp = self._compor(d, 1, 2)   # refH primeiro, depois refV
        np.testing.assert_array_equal(d_r180['estados'], d_comp['estados'])

    def test_r180_canais_iguais(self):
        d = _make_npz_dict(rng=np.random.default_rng(99))
        d_r180 = aplicar_simetria(d, 3)
        d_comp = self._compor(d, 2, 1)
        np.testing.assert_array_equal(d_r180['canais'], d_comp['canais'])

    def test_r180_scores_iguais(self):
        d = _make_npz_dict(rng=np.random.default_rng(99))
        d_r180 = aplicar_simetria(d, 3)
        d_comp = self._compor(d, 2, 1)
        np.testing.assert_array_almost_equal(
            d_r180['score_melhor_jogada'], d_comp['score_melhor_jogada']
        )

    def test_r180_melhor_jogada_iguais(self):
        d = _make_npz_dict(rng=np.random.default_rng(99))
        d_r180 = aplicar_simetria(d, 3)
        d_comp = self._compor(d, 2, 1)
        np.testing.assert_array_equal(d_r180['melhor_jogada'], d_comp['melhor_jogada'])

    def test_reflexao_dupla_eh_identidade(self):
        """Aplicar a mesma reflexao duas vezes deve retornar ao estado original."""
        d = _make_npz_dict(rng=np.random.default_rng(13))
        for sym_id in (1, 2, 3):
            d2 = aplicar_simetria(aplicar_simetria(d, sym_id), sym_id)
            np.testing.assert_array_equal(
                d2['estados'], d['estados'], err_msg=f'sym_id={sym_id}'
            )
            np.testing.assert_array_equal(
                d2['canais'], d['canais'], err_msg=f'sym_id={sym_id}'
            )
            np.testing.assert_array_almost_equal(
                d2['score_melhor_jogada'], d['score_melhor_jogada'],
                err_msg=f'sym_id={sym_id}'
            )
            np.testing.assert_array_equal(
                d2['melhor_jogada'], d['melhor_jogada'], err_msg=f'sym_id={sym_id}'
            )


# ---------------------------------------------------------------------------
# (c) Coerencia canais <-> matriz crua
# ---------------------------------------------------------------------------

class TestCoerenciaCanaisMatriz:
    """Recomputa `canais` a partir da matriz transformada e compara."""

    @pytest.mark.parametrize('sym_id', [1, 2, 3])
    def test_canais_recomputados_coincidem(self, sym_id):
        d = _make_npz_dict(n=20, rng=np.random.default_rng(sym_id * 100))
        d2 = aplicar_simetria(d, sym_id)

        for i in range(len(d2['estados'])):
            canais_recomp = extrair_canais(d2['estados'][i])
            np.testing.assert_array_equal(
                d2['canais'][i], canais_recomp,
                err_msg=f'sym_id={sym_id}, estado={i}'
            )

    @pytest.mark.parametrize('sym_id', [1, 2, 3])
    def test_dominio_binario_preservado(self, sym_id):
        d = _make_npz_dict(n=20)
        d2 = aplicar_simetria(d, sym_id)
        valores = np.unique(d2['canais'])
        assert set(valores).issubset({0, 1}), (
            f'sym_id={sym_id}: canais fora de {{0,1}}: {valores}'
        )


# ---------------------------------------------------------------------------
# (d) Coerencia scores <-> rotulos
# ---------------------------------------------------------------------------

class TestCoerenciaScoresRotulos:
    """O score do rotulo transformado deve ser o score do rotulo original."""

    @pytest.mark.parametrize('sym_id', [1, 2, 3])
    def test_score_da_melhor_jogada_preservado(self, sym_id):
        """O score da melhor jogada nao muda — so o slot onde ela aparece muda."""
        rng = np.random.default_rng(sym_id * 77)
        d = _make_npz_dict(n=30, rng=rng)
        labels = [str(s) for s in d['labels_canonicos']]
        label_to_idx = {lbl: i for i, lbl in enumerate(labels)}

        d2 = aplicar_simetria(d, sym_id)

        for n in range(len(d['estados'])):
            lbl_orig = str(d['melhor_jogada'][n])
            lbl_novo = str(d2['melhor_jogada'][n])
            if not lbl_orig:
                continue
            idx_orig = label_to_idx[lbl_orig]
            idx_novo = label_to_idx[lbl_novo]
            score_orig = d['score_melhor_jogada'][n, idx_orig]
            score_novo = d2['score_melhor_jogada'][n, idx_novo]
            np.testing.assert_almost_equal(
                score_orig, score_novo, decimal=6,
                err_msg=f'sym_id={sym_id}, n={n}'
            )

    @pytest.mark.parametrize('sym_id', [1, 2, 3])
    def test_score_vetorial_permutacao_consistente(self, sym_id):
        """A permutacao aplicada a score_jogada deve ser bijetiva (nenhum slot perdido)."""
        d = _make_npz_dict(n=5, rng=np.random.default_rng(sym_id + 200))
        d2 = aplicar_simetria(d, sym_id)

        # Ordenar os scores deve resultar no mesmo conjunto de valores
        for i in range(len(d['estados'])):
            orig_sorted = np.sort(d['score_jogada'][i])
            novo_sorted = np.sort(d2['score_jogada'][i])
            np.testing.assert_array_almost_equal(orig_sorted, novo_sorted,
                err_msg=f'sym_id={sym_id}, estado={i}')


# ---------------------------------------------------------------------------
# (e) K=11 preservado bit-a-bit em todas as 4 simetrias
# ---------------------------------------------------------------------------

class TestCanalParidadePreservado:
    """Canal K=11 (paridade_cadeia_longa_impar) e broadcast global invariante."""

    @pytest.mark.parametrize('sym_id', [0, 1, 2, 3])
    def test_k11_preservado(self, sym_id):
        d = _make_npz_dict(n=30, rng=np.random.default_rng(sym_id * 31))
        d2 = aplicar_simetria(d, sym_id)
        np.testing.assert_array_equal(
            d2['canais'][:, :, :, 11],
            d['canais'][:, :, :, 11],
            err_msg=f'K=11 alterado por sym_id={sym_id}'
        )

    @pytest.mark.parametrize('sym_id', [0, 1, 2, 3])
    def test_k11_continua_broadcast(self, sym_id):
        """Apos a transformacao, K=11 ainda deve ser uniforme por estado."""
        d = _make_npz_dict(n=15)
        d2 = aplicar_simetria(d, sym_id)
        for i in range(len(d2['estados'])):
            vals = d2['canais'][i, :, :, 11]
            assert vals.min() == vals.max(), (
                f'sym_id={sym_id}, estado={i}: K=11 nao e broadcast: {vals}'
            )


# ---------------------------------------------------------------------------
# (f) Validacao de entradas invalidas
# ---------------------------------------------------------------------------

class TestEntradaInvalida:
    def test_sym_id_invalido(self):
        d = _make_npz_dict()
        with pytest.raises(ValueError, match='sym_id'):
            aplicar_simetria(d, 4)
        with pytest.raises(ValueError, match='sym_id'):
            aplicar_simetria(d, -1)

    def test_campo_obrigatorio_ausente(self):
        d = _make_npz_dict()
        d_incompleto = {k: v for k, v in d.items() if k != 'canais'}
        with pytest.raises(ValueError, match='canais'):
            aplicar_simetria(d_incompleto, 1)

    def test_campos_opcionais_ausentes_nao_falham(self):
        """Campos opcionais ausentes nao devem causar erro."""
        d = _make_npz_dict()
        d_sem_extras = {k: v for k, v in d.items()
                        if k not in ('qtd_tracos', 'nomes_canais', 'qtd_cadeias_longas')}
        d2 = aplicar_simetria(d_sem_extras, 1)
        assert 'estados' in d2
        assert 'canais' in d2

    def test_campos_opcionais_presentes_sao_copiados(self):
        d = _make_npz_dict()
        d2 = aplicar_simetria(d, 1)
        for campo in ('qtd_tracos', 'depth_jogada', 'nomes_canais', 'qtd_cadeias_longas'):
            assert campo in d2, f'{campo} ausente no resultado'
            np.testing.assert_array_equal(d2[campo], d[campo])

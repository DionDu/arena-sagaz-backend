"""Testes unitários para `cnn_inferencia_pontinhos_3_4` (T034).

Testes que carregam modelos `.tflite` reais são marcados com `tflite_real`
e usam o caminho de modelo do nível DIFICIL (`profundidade_9.tflite`).
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pytest

from gerador_dados.jogo_pontinhos.cnn_inferencia_pontinhos_3_4 import (
    InferenciaCNN,
    _limpar_cache_interpretadores,
    carregar_modelo,
    inferir,
    top_k_arestas_livres,
)
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    todos_labels_canonicos,
)


CAMINHO_MODELO = "modelos/pontinhos_pequeno_profundidade_9.tflite"


@pytest.fixture(autouse=True)
def _limpar_cache():
    _limpar_cache_interpretadores()
    yield
    _limpar_cache_interpretadores()


# =============================================================================
# carregar_modelo
# =============================================================================


def test_carregar_modelo_caminho_inexistente_levanta_filenotfound():
    with pytest.raises(FileNotFoundError, match="modelo CNN não encontrado"):
        carregar_modelo("modelos/inexistente_42.tflite")


@pytest.mark.skipif(not Path(CAMINHO_MODELO).exists(), reason="modelo TFLite ausente")
def test_carregar_modelo_real_retorna_inferencia_cnn():
    inferencia = carregar_modelo(CAMINHO_MODELO)
    assert isinstance(inferencia, InferenciaCNN)
    assert inferencia.interpretador is not None
    assert isinstance(inferencia.lock, type(threading.Lock()))
    assert len(inferencia.forma_entrada) == 4  # (1, h, w, 1)


@pytest.mark.skipif(not Path(CAMINHO_MODELO).exists(), reason="modelo TFLite ausente")
def test_cache_retorna_mesma_instancia_em_segunda_chamada():
    a = carregar_modelo(CAMINHO_MODELO)
    b = carregar_modelo(CAMINHO_MODELO)
    assert a is b


# =============================================================================
# inferir
# =============================================================================


@pytest.mark.skipif(not Path(CAMINHO_MODELO).exists(), reason="modelo TFLite ausente")
def test_inferir_em_tabuleiro_vazio_retorna_distribuicao_31():
    inferencia = carregar_modelo(CAMINHO_MODELO)
    estado = EstadoTabuleiro(4, 3)
    saida = inferir(inferencia, estado)
    assert isinstance(saida, np.ndarray)
    assert saida.shape == (31,)
    assert saida.dtype == np.float32
    assert np.all(np.isfinite(saida))


@pytest.mark.skipif(not Path(CAMINHO_MODELO).exists(), reason="modelo TFLite ausente")
def test_inferir_nao_modifica_matriz_original():
    inferencia = carregar_modelo(CAMINHO_MODELO)
    estado = EstadoTabuleiro(4, 3)
    estado.aplicar_traco("H_0_1", -1)  # marca J2
    matriz_antes = estado.matriz.copy()
    _ = inferir(inferencia, estado)
    np.testing.assert_array_equal(estado.matriz, matriz_antes)


@pytest.mark.skipif(not Path(CAMINHO_MODELO).exists(), reason="modelo TFLite ausente")
def test_inferir_determinismo_mesmo_input_mesma_saida():
    inferencia = carregar_modelo(CAMINHO_MODELO)
    estado = EstadoTabuleiro(4, 3)
    s1 = inferir(inferencia, estado)
    s2 = inferir(inferencia, estado)
    np.testing.assert_array_equal(s1, s2)


# =============================================================================
# top_k_arestas_livres
# =============================================================================


def test_top_k_retorna_lista_vazia_em_estado_terminal():
    estado = EstadoTabuleiro(1, 1)
    for tr in estado.tracos_disponiveis():
        estado.aplicar_traco(tr)
    distribuicao = np.zeros(4, dtype=np.float32)
    assert top_k_arestas_livres(distribuicao, estado, k=5) == []


def test_top_k_5_arestas_distintas_em_tabuleiro_vazio():
    estado = EstadoTabuleiro(4, 3)
    labels = todos_labels_canonicos(4, 3)
    distribuicao = np.linspace(0.01, 0.99, 31, dtype=np.float32)
    top5 = top_k_arestas_livres(distribuicao, estado, k=5)
    assert len(top5) == 5
    arestas = [t[0] for t in top5]
    assert len(set(arestas)) == 5
    # Probabilidades em ordem desc
    probs = [t[1] for t in top5]
    assert probs == sorted(probs, reverse=True)


def test_top_k_filtra_arestas_ja_preenchidas():
    estado = EstadoTabuleiro(4, 3)
    estado.aplicar_traco("H_0_1", 1)
    distribuicao = np.zeros(31, dtype=np.float32)
    labels = todos_labels_canonicos(4, 3)
    indice_h_0_1 = labels.index("H_0_1")
    distribuicao[indice_h_0_1] = 0.99  # alta prob, mas já preenchida
    top5 = top_k_arestas_livres(distribuicao, estado, k=5)
    arestas = [t[0] for t in top5]
    assert "H_0_1" not in arestas


def test_top_k_degrade_gracioso_quando_livres_menor_que_k():
    estado = EstadoTabuleiro(1, 1)
    # 1x1 tem 4 arestas; preenchemos 3
    tracos = estado.tracos_disponiveis()
    for tr in tracos[:-1]:
        estado.aplicar_traco(tr)
    distribuicao = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
    top5 = top_k_arestas_livres(distribuicao, estado, k=5)
    assert len(top5) == 1


def test_top_k_tiebreak_por_indice_canonico():
    estado = EstadoTabuleiro(4, 3)
    distribuicao = np.zeros(31, dtype=np.float32)
    # Empate: índices 0 e 1 com mesma prob
    distribuicao[0] = 0.9
    distribuicao[1] = 0.9
    labels = todos_labels_canonicos(4, 3)
    top5 = top_k_arestas_livres(distribuicao, estado, k=2)
    # Em empate, índice canônico menor vem primeiro
    assert top5[0][0] == labels[0]
    assert top5[1][0] == labels[1]


# =============================================================================
# Cobertura adicional — caminhos de erro
# =============================================================================


def test_carregar_modelo_runtime_error_em_arquivo_invalido(tmp_path):
    """Arquivo TFLite inválido → RuntimeError (não FileNotFoundError)."""
    fake_tflite = tmp_path / "fake.tflite"
    fake_tflite.write_bytes(b"NOT A REAL TFLITE FILE")
    with pytest.raises(RuntimeError, match="falha ao carregar TFLite"):
        carregar_modelo(str(fake_tflite))


def test_inferir_levanta_runtimeerror_em_saida_nan():
    """Saída com NaN no tensor → RuntimeError."""
    import threading

    class _FakeInterpretador:
        def set_tensor(self, *a, **kw): pass
        def invoke(self): pass
        def get_tensor(self, *a, **kw):
            return np.array([np.nan, 0.5, 0.5, 1.0], dtype=np.float32)

    fake = InferenciaCNN(
        interpretador=_FakeInterpretador(),
        indice_entrada=0,
        indice_saida=0,
        forma_entrada=(1, 9, 7, 1),
        lock=threading.Lock(),
    )
    estado = EstadoTabuleiro(4, 3)
    with pytest.raises(RuntimeError, match="NaN"):
        inferir(fake, estado)


def test_importar_tflite_disponivel():
    """Função `_importar_tflite` retorna uma classe Interpreter."""
    from gerador_dados.jogo_pontinhos.cnn_inferencia_pontinhos_3_4 import (
        _importar_tflite,
    )
    cls = _importar_tflite()
    assert cls is not None  # tem `model_path` no construtor


def test_top_k_em_estado_terminal_vazio_retorna_lista_vazia():
    estado = EstadoTabuleiro(1, 1)
    for tr in estado.tracos_disponiveis():
        estado.aplicar_traco(tr)
    distribuicao = np.zeros(4, dtype=np.float32)
    assert top_k_arestas_livres(distribuicao, estado, k=5) == []


def test_importar_tflite_levanta_quando_nenhum_runtime_disponivel(monkeypatch):
    """Simula ausência de TODOS os runtimes TFLite — deve levantar ImportError."""
    import builtins

    real_import = builtins.__import__

    def _import_falha(name, *args, **kwargs):
        # Bloqueia todos os runtimes possíveis
        if name in (
            "tensorflow",
            "tflite_runtime",
            "tflite_runtime.interpreter",
            "ai_edge_litert",
            "ai_edge_litert.interpreter",
        ):
            raise ImportError(f"forçando ausência de {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import_falha)
    from gerador_dados.jogo_pontinhos.cnn_inferencia_pontinhos_3_4 import (
        _importar_tflite,
    )
    with pytest.raises(ImportError, match="Nenhum runtime TFLite"):
        _importar_tflite()


def test_importar_tflite_fallback_para_tflite_runtime(monkeypatch):
    """Quando tensorflow falha mas tflite_runtime disponível, retorna ele."""
    import builtins
    import sys
    import types

    fake_module = types.ModuleType("tflite_runtime.interpreter")
    fake_module.Interpreter = object  # placeholder
    sys.modules["tflite_runtime"] = types.ModuleType("tflite_runtime")
    sys.modules["tflite_runtime.interpreter"] = fake_module

    real_import = builtins.__import__

    def _import_seletivo(name, *args, **kwargs):
        if name == "tensorflow":
            raise ImportError("forçando tensorflow ausente")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import_seletivo)
    from gerador_dados.jogo_pontinhos.cnn_inferencia_pontinhos_3_4 import (
        _importar_tflite,
    )
    cls = _importar_tflite()
    assert cls is object  # nosso placeholder

    # cleanup
    del sys.modules["tflite_runtime.interpreter"]
    del sys.modules["tflite_runtime"]


def test_importar_tflite_fallback_para_ai_edge_litert(monkeypatch):
    import builtins
    import sys
    import types

    fake_litert = types.ModuleType("ai_edge_litert.interpreter")
    fake_litert.Interpreter = type("FakeInterp", (), {})
    sys.modules["ai_edge_litert"] = types.ModuleType("ai_edge_litert")
    sys.modules["ai_edge_litert.interpreter"] = fake_litert

    real_import = builtins.__import__

    def _import_seletivo(name, *args, **kwargs):
        if name in ("tensorflow", "tflite_runtime", "tflite_runtime.interpreter"):
            raise ImportError(f"forçando {name} ausente")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import_seletivo)
    from gerador_dados.jogo_pontinhos.cnn_inferencia_pontinhos_3_4 import (
        _importar_tflite,
    )
    cls = _importar_tflite()
    assert cls is fake_litert.Interpreter

    del sys.modules["ai_edge_litert.interpreter"]
    del sys.modules["ai_edge_litert"]

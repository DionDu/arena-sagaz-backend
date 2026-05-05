"""Inferência TFLite isolada para o agente `ia-pontinhos-3-4`.

Mantém um cache module-level de `InferenciaCNN` (interpretador TFLite +
metadados) por caminho de modelo, protegido por lock. A normalização do
tensor segue o contrato `contexto_3_partidas_ao_vivo` declarado em
`contrato_codificacao_pontinhos.json`.

O import do runtime TFLite é **preguiçoso**: só ocorre dentro de
`carregar_modelo`. Isso permite que testes que injetam mocks de
`InferenciaCNN` rodem em ambientes sem TFLite instalado.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np

from gerador_dados.jogo_pontinhos.contrato_codificacao_pontinhos import (
    CONTEXTO_PARTIDA,
    normalizar_para_cnn,
)
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    todos_labels_canonicos,
)


@dataclass
class InferenciaCNN:
    """Interpretador TFLite + metadados pré-calculados para inferência rápida."""

    interpretador: Any
    indice_entrada: int
    indice_saida: int
    forma_entrada: tuple[int, ...]
    lock: threading.Lock


_cache_interpretadores: dict[str, InferenciaCNN] = {}
_lock_cache = threading.Lock()


def _importar_tflite() -> Any:
    """Tenta importar um runtime TFLite disponível.

    Ordem: `tensorflow.lite` → `tflite_runtime.interpreter` → `ai_edge_litert`.
    Retorna o módulo `Interpreter` correspondente. ImportError caso nenhum
    esteja instalado.
    """
    try:
        import tensorflow as tf  # type: ignore[import-not-found]
        return tf.lite.Interpreter
    except ImportError:
        pass
    try:
        from tflite_runtime.interpreter import Interpreter  # type: ignore[import-not-found]
        return Interpreter
    except ImportError:
        pass
    try:
        from ai_edge_litert.interpreter import Interpreter  # type: ignore[import-not-found]
        return Interpreter
    except ImportError:
        pass
    raise ImportError(
        "Nenhum runtime TFLite disponível. Instale 'tensorflow', "
        "'tflite-runtime' ou 'ai-edge-litert' para inferência da CNN."
    )


def carregar_modelo(caminho_tflite: str) -> InferenciaCNN:
    """Carrega (ou retorna do cache) o interpretador TFLite para o caminho dado.

    Cache thread-safe: na 2ª chamada com o mesmo caminho retorna a mesma
    instância. Cada instância tem seu próprio `Lock` para serializar
    `set_tensor → invoke → get_tensor`.

    Raises:
        FileNotFoundError: se `caminho_tflite` não existe.
        RuntimeError: se TFLite falhar ao carregar/alocar tensores.
        ImportError: se nenhum runtime TFLite estiver disponível (ver
            `_importar_tflite`).
    """
    caminho_abs = os.path.abspath(caminho_tflite)
    with _lock_cache:
        cached = _cache_interpretadores.get(caminho_abs)
        if cached is not None:
            return cached

    if not os.path.exists(caminho_abs):
        raise FileNotFoundError(
            f"modelo CNN não encontrado em {caminho_tflite}"
        )

    InterpreterCls = _importar_tflite()
    try:
        interp = InterpreterCls(model_path=caminho_abs)
        interp.allocate_tensors()
    except Exception as e:
        raise RuntimeError(
            f"falha ao carregar TFLite em {caminho_tflite}: {e}"
        ) from e

    detalhes_entrada = interp.get_input_details()[0]
    detalhes_saida = interp.get_output_details()[0]
    inferencia = InferenciaCNN(
        interpretador=interp,
        indice_entrada=detalhes_entrada["index"],
        indice_saida=detalhes_saida["index"],
        forma_entrada=tuple(detalhes_entrada["shape"]),
        lock=threading.Lock(),
    )

    with _lock_cache:
        _cache_interpretadores.setdefault(caminho_abs, inferencia)
        return _cache_interpretadores[caminho_abs]


def _preparar_tensor(estado: EstadoTabuleiro, forma_entrada: tuple[int, ...]) -> np.ndarray:
    """Aplica normalização do contexto 3 e retorna tensor float32 com a forma
    esperada pelo modelo (tipicamente `(1, h, w, 1)`)."""
    normalizado = normalizar_para_cnn(estado.matriz, CONTEXTO_PARTIDA)
    valores = np.unique(normalizado)
    assert set(valores.tolist()).issubset({0.0, 1.0}), (
        "violação de contrato: tensor contém valores fora de {0, 1}"
    )
    return normalizado.reshape(forma_entrada).astype(np.float32)


def inferir(inferencia: InferenciaCNN, estado: EstadoTabuleiro) -> np.ndarray:
    """Executa inferência da CNN sobre `estado` e devolve a distribuição (31,)."""
    tensor = _preparar_tensor(estado, inferencia.forma_entrada)
    with inferencia.lock:
        inferencia.interpretador.set_tensor(inferencia.indice_entrada, tensor)
        inferencia.interpretador.invoke()
        saida = inferencia.interpretador.get_tensor(inferencia.indice_saida)
    distribuicao = np.asarray(saida, dtype=np.float32).reshape(-1)
    if not np.all(np.isfinite(distribuicao)):
        raise RuntimeError(
            "saída da CNN contém NaN ou inf — modelo possivelmente corrompido"
        )
    return distribuicao


def top_k_arestas_livres(
    distribuicao: np.ndarray, estado: EstadoTabuleiro, k: int = 5
) -> list[tuple[str, float]]:
    """Retorna `[(label, prob), ...]` ordenado por probabilidade desc, apenas
    arestas livres no `estado`. Tie-break: menor índice canônico. Se o número
    de livres for menor que `k`, devolve todas (degrade gracioso)."""
    livres = estado.tracos_disponiveis()
    if not livres:
        return []
    labels = todos_labels_canonicos(estado.linhas, estado.colunas)
    indice_label = {lab: i for i, lab in enumerate(labels)}

    candidatos: list[tuple[str, float, int]] = [
        (lab, float(distribuicao[indice_label[lab]]), indice_label[lab])
        for lab in livres
    ]
    # ordenação: prob desc, depois índice canônico asc
    candidatos.sort(key=lambda triple: (-triple[1], triple[2]))
    return [(lab, prob) for (lab, prob, _idx) in candidatos[:k]]


def _limpar_cache_interpretadores() -> None:
    """Uso interno e testes — limpa o cache module-level."""
    with _lock_cache:
        _cache_interpretadores.clear()

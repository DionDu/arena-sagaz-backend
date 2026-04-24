"""Helper mínimo para carregar e aplicar o contrato de codificação da CNN do Pontinhos.

IMPORTANTE: este módulo é para uso EXCLUSIVO do código Python do backend
(simulador, avaliador, testes). Notebooks (Databricks e Colab) NÃO devem
importar este módulo — eles carregam o JSON inline com json.load() e
aplicam as regras no próprio notebook, conforme o snippet documentado
em contrato_codificacao_pontinhos.json → snippet_de_uso_para_notebooks.

A fonte da verdade é o JSON irmão (contrato_codificacao_pontinhos.json).
Este módulo apenas implementa o carregador e o aplicador em Python puro,
seguindo estritamente as regras declaradas no JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

_CAMINHO_JSON = Path(__file__).parent / "contrato_codificacao_pontinhos.json"
_CACHE: dict[str, Any] | None = None

CONTEXTO_GERACAO = "contexto_1_geracao_dataset"
CONTEXTO_TREINO = "contexto_2_treinamento_cnn"
CONTEXTO_PARTIDA = "contexto_3_partidas_ao_vivo"


def carregar_contrato() -> dict[str, Any]:
    """Carrega o JSON do contrato (cacheado). Retorna o dict bruto."""
    global _CACHE
    if _CACHE is None:
        with open(_CAMINHO_JSON, encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def normalizar_para_cnn(mat: np.ndarray, contexto: str) -> np.ndarray:
    """Aplica as regras de normalização do contexto sobre uma CÓPIA da matriz.

    Sempre retorna um np.ndarray float32 novo (a matriz original não é modificada).
    Para o contexto de geração (onde `aplica_normalizacao_antes_do_modelo=False`),
    retorna uma cópia float32 sem transformação.
    """
    contrato = carregar_contrato()
    ctx = contrato["tres_contextos_de_uso"][contexto]
    out = mat.astype(np.float32).copy()
    for regra in ctx.get("regras_de_normalizacao_a_aplicar", []):
        out[out == regra["substituir_valor"]] = regra["por_valor"]
    return out

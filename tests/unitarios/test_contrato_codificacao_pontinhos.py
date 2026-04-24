"""Testes do contrato de codificação da CNN do Pontinhos.

Este arquivo é OBRIGATÓRIO no CI. Falhas aqui travam o merge.

Cobre:
  1. Estrutura/consistência do JSON.
  2. Sincronização de hash entre a cópia backend e a cópia frontend.
  3. Domínio dos valores no NPZ de amostra (contexto_1_geracao_dataset).
  4. Domínio do tensor após normalização (contexto_2 e contexto_3).
  5. Que o helper Python aplica EXATAMENTE as regras declaradas no JSON.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from gerador_dados.contrato_codificacao_pontinhos import (
    CONTEXTO_GERACAO,
    CONTEXTO_PARTIDA,
    CONTEXTO_TREINO,
    carregar_contrato,
    normalizar_para_cnn,
)

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
JSON_BACKEND = RAIZ_BACKEND / "gerador_dados" / "contrato_codificacao_pontinhos.json"
JSON_FRONTEND = (
    RAIZ_BACKEND.parent
    / "arena-sagaz-frontend"
    / "assets"
    / "jogos"
    / "pontinhos"
    / "contrato_codificacao_pontinhos.json"
)
DIR_DADOS = RAIZ_BACKEND / "dados"


# ---------------------------------------------------------------------------
# 1. Estrutura/consistência do JSON
# ---------------------------------------------------------------------------

def test_json_carrega_e_tem_chaves_obrigatorias():
    contrato = carregar_contrato()
    for chave in (
        "versao",
        "sobre_este_arquivo",
        "tres_contextos_de_uso",
        "invariante_final_do_tensor_da_cnn",
        "dimensoes_por_tamanho",
    ):
        assert chave in contrato, f"chave ausente no JSON: {chave}"


def test_json_declara_os_tres_contextos():
    ctxs = carregar_contrato()["tres_contextos_de_uso"]
    assert CONTEXTO_GERACAO in ctxs
    assert CONTEXTO_TREINO in ctxs
    assert CONTEXTO_PARTIDA in ctxs


def test_contexto_geracao_nao_normaliza():
    ctx = carregar_contrato()["tres_contextos_de_uso"][CONTEXTO_GERACAO]
    assert ctx["aplica_normalizacao_antes_do_modelo"] is False
    assert "regras_de_normalizacao_a_aplicar" not in ctx


def test_contextos_treino_e_partida_declaram_dominio_final_01():
    contrato = carregar_contrato()
    for ctx_nome in (CONTEXTO_TREINO, CONTEXTO_PARTIDA):
        ctx = contrato["tres_contextos_de_uso"][ctx_nome]
        assert ctx["aplica_normalizacao_antes_do_modelo"] is True
        assert ctx["dominio_apos_normalizacao"] == [0, 1], ctx_nome


# ---------------------------------------------------------------------------
# 2. Sincronização backend ↔ frontend (hash idêntico)
# ---------------------------------------------------------------------------

def _hash(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


@pytest.mark.skipif(
    not JSON_FRONTEND.exists(),
    reason=f"Cópia frontend não encontrada em {JSON_FRONTEND}. Copie o JSON do backend para lá.",
)
def test_hash_backend_igual_ao_frontend():
    h_backend = _hash(JSON_BACKEND)
    h_frontend = _hash(JSON_FRONTEND)
    assert h_backend == h_frontend, (
        "DRIFT DETECTADO — contrato_codificacao_pontinhos.json diverge entre backend e frontend.\n"
        f"  backend:  {JSON_BACKEND} (sha256={h_backend})\n"
        f"  frontend: {JSON_FRONTEND} (sha256={h_frontend})\n"
        "Copie a fonte da verdade (backend) para o frontend e commit os dois juntos."
    )


# ---------------------------------------------------------------------------
# 3. NPZ de amostra — domínio de valores
# ---------------------------------------------------------------------------

def _primeiro_npz_disponivel() -> Path | None:
    if not DIR_DADOS.exists():
        return None
    npzs = sorted(DIR_DADOS.glob("dataset_pequeno_*.npz"))
    return npzs[0] if npzs else None


@pytest.mark.skipif(
    _primeiro_npz_disponivel() is None,
    reason="Nenhum NPZ de amostra em dados/ — pule se rodando em ambiente limpo.",
)
def test_npz_amostra_em_dominio_declarado():
    """Valida que o NPZ de amostra está no domínio {0, 1, 8, 9} (contexto 1)."""
    caminho = _primeiro_npz_disponivel()
    dados = np.load(caminho)
    chave_estado = "estados" if "estados" in dados.files else dados.files[0]
    valores = np.unique(dados[chave_estado])
    dominio_esperado = set(
        carregar_contrato()["tres_contextos_de_uso"][CONTEXTO_GERACAO][
            "formato_matriz_produzida"
        ]["dominio_completo"]
    )
    fora = set(int(v) for v in valores) - dominio_esperado
    assert not fora, (
        f"NPZ {caminho.name} contém valores {fora} fora do domínio {dominio_esperado} "
        "do contexto_1_geracao_dataset."
    )


# ---------------------------------------------------------------------------
# 4. Normalização produz tensor em {0, 1} nos contextos 2 e 3
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("contexto,matriz_entrada", [
    (CONTEXTO_TREINO, np.array([[0, 1, 8, 9, 0, 1]], dtype=np.int8)),
    (CONTEXTO_PARTIDA, np.array([[0, 1, -1, 8, 0, 1]], dtype=np.int8)),
    (CONTEXTO_PARTIDA, np.array([[0, 1, -1, 8, 9, 1]], dtype=np.int8)),
])
def test_normalizacao_colapsa_para_0_e_1(contexto, matriz_entrada):
    saida = normalizar_para_cnn(matriz_entrada, contexto)
    assert saida.dtype == np.float32
    dominio = set(np.unique(saida).tolist())
    assert dominio.issubset({0.0, 1.0}), (
        f"Contexto {contexto} retornou valores {dominio} — esperado ⊆ {{0.0, 1.0}}."
    )


def test_normalizacao_partida_nao_modifica_matriz_original():
    """Matriz da partida NUNCA pode ser modificada in-place — corromperia o jogo."""
    mat = np.array([[0, 1, -1, 8]], dtype=np.int8)
    copia_antes = mat.copy()
    _ = normalizar_para_cnn(mat, CONTEXTO_PARTIDA)
    assert np.array_equal(mat, copia_antes), (
        "normalizar_para_cnn modificou a matriz original — deve operar sobre cópia."
    )


# ---------------------------------------------------------------------------
# 5. Helper Python aplica EXATAMENTE as regras do JSON
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("contexto", [CONTEXTO_TREINO, CONTEXTO_PARTIDA])
def test_helper_aplica_todas_as_regras_declaradas(contexto):
    """Reaplica manualmente as regras do JSON e compara com a saída do helper."""
    contrato = carregar_contrato()
    regras = contrato["tres_contextos_de_uso"][contexto]["regras_de_normalizacao_a_aplicar"]

    # Matriz com TODOS os valores mencionados em todas as regras
    valores_regrados = [r["substituir_valor"] for r in regras]
    mat = np.array([valores_regrados + [0, 1]], dtype=np.int8)

    saida_helper = normalizar_para_cnn(mat, contexto)

    # Aplicar manualmente para comparar
    esperado = mat.astype(np.float32).copy()
    for r in regras:
        esperado[esperado == r["substituir_valor"]] = r["por_valor"]

    assert np.array_equal(saida_helper, esperado), (
        f"Helper divergiu das regras declaradas para contexto {contexto}."
    )

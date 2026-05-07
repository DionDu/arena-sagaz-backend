"""CLI para geração de dataset de treinamento Dots and Boxes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada_com_scores
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, TAMANHOS, todos_labels_canonicos

DIRETORIO_DADOS = Path("dados")
TAMANHO_LOTE = 5000

# Sentinela usado nos slots de jogadas indisponíveis (já preenchidas). Após o
# softmax/normalização no notebook de treino, vira ~0 e é mascarado da loss.
SCORE_INDISPONIVEL = -1e9


def _hash_estado(matriz: np.ndarray) -> str:
    return hashlib.sha256(matriz.tobytes()).hexdigest()


def _carregar_checkpoint(tamanho: str) -> dict:
    caminho = DIRETORIO_DADOS / f"checkpoint_{tamanho}.json"
    if caminho.exists():
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _salvar_checkpoint(tamanho: str, dados: dict) -> None:
    DIRETORIO_DADOS.mkdir(exist_ok=True)
    caminho = DIRETORIO_DADOS / f"checkpoint_{tamanho}.json"
    dados["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def _gerar_estado_aleatorio(linhas: int, colunas: int) -> EstadoTabuleiro:
    estado = EstadoTabuleiro(linhas, colunas)
    tracos = estado.tracos_disponiveis()
    total = len(tracos)
    # [NOTA PARA SPECKIT/CLAUDE]: Corrigido problema de lentidão drástica (fator de ramificação infinito).
    # O gerador antes enchia no máximo 50% dos traços (de 0 a total // 2), forçando o Minimax
    # a calcular sempre tabuleiros vazios. Agora ele preenche aleatoriamente de 15% a 85% do
    # tabuleiro, permitindo que a IA aprenda muito mais cenários de midgame/endgame e 
    # rodando exponencialmente mais rápido.
    min_fill = int(total * 0.15)
    max_fill = int(total * 0.85)
    qtd = random.randint(min_fill, max_fill)
    random.shuffle(tracos)
    for tr in tracos[:qtd]:
        if tr in estado.tracos_disponiveis():
            # Traços são sempre marcados como 9 (aresta preenchida, sem ownership).
            # A distinção 1/-1 é mantida apenas para caixas fechadas (feito internamente
            # por aplicar_traco quando os 4 lados de uma caixa são preenchidos).
            estado.aplicar_traco(tr, 9)
    return estado


def _log_progresso(gerados: int, total: int, inicio: float) -> None:
    decorrido = time.time() - inicio
    porcentagem = gerados / total * 100
    estimativa = (decorrido / gerados * (total - gerados)) if gerados > 0 else 0
    entrada = {
        "registros_gerados": gerados,
        "total_alvo": total,
        "porcentagem": round(porcentagem, 2),
        "tempo_decorrido_s": round(decorrido, 2),
        "estimativa_restante_s": round(estimativa, 2),
    }
    print(json.dumps(entrada, ensure_ascii=False))


def _vetor_scores(scores_dict: dict[str, int], indice_label: dict[str, int], n_labels: int) -> np.ndarray:
    vetor = np.full(n_labels, SCORE_INDISPONIVEL, dtype=np.float32)
    for label, valor in scores_dict.items():
        vetor[indice_label[label]] = float(valor)
    return vetor


def gerar(tamanho: str, total: int, profundidade: int, retomar: bool) -> None:
    linhas, colunas = TAMANHOS[tamanho]
    DIRETORIO_DADOS.mkdir(exist_ok=True)

    labels_canonicos = todos_labels_canonicos(linhas, colunas)
    indice_label = {lab: i for i, lab in enumerate(labels_canonicos)}
    n_labels = len(labels_canonicos)

    checkpoint = _carregar_checkpoint(tamanho) if retomar else {}
    total_gerado = checkpoint.get("total_gerado", 0)
    ultimo_lote = checkpoint.get("ultimo_lote", 0)
    hashes_vistos: set[str] = set()

    if not checkpoint:
        checkpoint = {
            "tamanho": tamanho,
            "total_alvo": total,
            "total_gerado": 0,
            "ultimo_lote": 0,
            "profundidade_minimax": profundidade,
            "iniciado_em": datetime.now(timezone.utc).isoformat(),
        }

    inicio = time.time()
    estados_lote: list[np.ndarray] = []
    rotulos_lote: list[str] = []
    scores_lote: list[np.ndarray] = []
    indices_lote: list[int] = []

    _encerrar = False

    def _sinal(sig, frame):
        nonlocal _encerrar
        _encerrar = True
        print("\nInterrupção recebida — salvando checkpoint parcial...")

    signal.signal(signal.SIGINT, _sinal)

    # [NOTA PARA SPECKIT/CLAUDE]: Alterado para paralelismo com ProcessPoolExecutor.
    # O Python original em single-thread travava a CPU em 7% (1/16 de 100%), gerando um grande
    # gargalo temporal (Explosão Combinatória do Minimax).
    # Com multiprocessing o processo vai a 85~90% da CPU diminuindo o tempo de 21h para <2h.
    # A frequência do log foi diminuída de 1000 para 50 para feedback mais rápido ao usuário.
    import concurrent.futures
    import multiprocessing
    max_workers = max(1, multiprocessing.cpu_count() - 2)

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futuros = {}

        while total_gerado < total and not _encerrar:
            while len(futuros) < max_workers * 2 and not _encerrar:
                estado = _gerar_estado_aleatorio(linhas, colunas)
                if estado.esta_terminal():
                    continue
                h = _hash_estado(estado.matriz)
                if h in hashes_vistos:
                    continue
                hashes_vistos.add(h)

                futuro = executor.submit(melhor_jogada_com_scores, estado, profundidade)
                futuros[futuro] = estado

            if not futuros:
                break

            done, _ = concurrent.futures.wait(
                futuros.keys(), return_when=concurrent.futures.FIRST_COMPLETED
            )

            for futuro in done:
                estado = futuros.pop(futuro)
                if _encerrar:
                    continue
                try:
                    rotulo, scores_dict = futuro.result()
                    estados_lote.append(estado.matriz.copy())
                    rotulos_lote.append(rotulo)
                    scores_lote.append(_vetor_scores(scores_dict, indice_label, n_labels))
                    indices_lote.append(total_gerado)
                    total_gerado += 1

                    if total_gerado % 10 == 0:
                        _log_progresso(total_gerado, total, inicio)

                    if len(estados_lote) >= TAMANHO_LOTE:
                        ultimo_lote += 1
                        caminho_lote = DIRETORIO_DADOS / f"dataset_{tamanho}_{ultimo_lote:04d}.npz"
                        np.savez_compressed(
                            caminho_lote,
                            estados=np.array(estados_lote, dtype=np.int8),
                            rotulos=np.array(rotulos_lote, dtype=str),
                            scores=np.array(scores_lote, dtype=np.float32),
                            indices=np.array(indices_lote, dtype=np.int32),
                            labels_canonicos=np.array(labels_canonicos, dtype=str),
                        )
                        estados_lote.clear()
                        rotulos_lote.clear()
                        scores_lote.clear()
                        indices_lote.clear()

                        checkpoint["total_gerado"] = total_gerado
                        checkpoint["ultimo_lote"] = ultimo_lote
                        _salvar_checkpoint(tamanho, checkpoint)
                        print(f"Lote {ultimo_lote:04d} salvo — {total_gerado}/{total} registros.")
                except ValueError:
                    pass

        if _encerrar:
            for f in futuros.keys():
                f.cancel()

    if estados_lote and not _encerrar:
        ultimo_lote += 1
        caminho_lote = DIRETORIO_DADOS / f"dataset_{tamanho}_{ultimo_lote:04d}.npz"
        np.savez_compressed(
            caminho_lote,
            estados=np.array(estados_lote, dtype=np.int8),
            rotulos=np.array(rotulos_lote, dtype=str),
            scores=np.array(scores_lote, dtype=np.float32),
            indices=np.array(indices_lote, dtype=np.int32),
            labels_canonicos=np.array(labels_canonicos, dtype=str),
        )
        checkpoint["total_gerado"] = total_gerado
        checkpoint["ultimo_lote"] = ultimo_lote
        _salvar_checkpoint(tamanho, checkpoint)

    _log_progresso(total_gerado, total, inicio)
    print(f"Geração concluída: {total_gerado} registros em {ultimo_lote} lotes.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gerador de dataset Dots and Boxes")
    parser.add_argument("--tamanho", choices=["pequeno", "medio", "grande"], required=True)
    parser.add_argument("--total", type=int, required=True)
    parser.add_argument("--profundidade", type=int, default=7)
    parser.add_argument("--retomar", action="store_true")
    args = parser.parse_args()
    gerar(args.tamanho, args.total, args.profundidade, args.retomar)


if __name__ == "__main__":
    main()

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


# =============================================================================
# Builders de estados canônicos para os testes do agente ia-pontinhos-3-4
# =============================================================================
#
# Estes builders produzem matrizes 3x4 (4 linhas × 3 colunas, shape (9,7)) com
# estruturas conhecidas (corrente curta/longa, ciclo de 4/6/8/10, ramificada,
# mistura) para servir como fonte da verdade dos 40+ estados de teste exigidos
# por `test_correntes_pontinhos_3_4.py` (T020 e T027).
#
# Domínio das matrizes: {-1, 0, 1, 8} — domínio de partida (contrato contexto 3
# de `contrato_codificacao_pontinhos.json`). NUNCA usar 9 aqui.
#
# Cada builder devolve um `EstadoTabuleiro` já populado e nunca lança em
# variantes 0..4. Para validar visualmente cada estado, rode o script de
# geração do MD em `tests/unitarios/jogo_pontinhos/fixtures_correntes_pontinhos_3_4.md`
# (ver T005).

from typing import Literal as _Literal

_LINHAS_PEQUENO = 4
_COLUNAS_PEQUENO = 3
_ALTURA_MAT = 2 * _LINHAS_PEQUENO + 1   # 9
_LARGURA_MAT = 2 * _COLUNAS_PEQUENO + 1  # 7


def _marker_para_variante(variante: int) -> int:
    # Alterna +1 (jogador 1) e -1 (jogador 2) para cobrir todo o domínio
    # de partida {-1, 0, 1, 8} ao longo das 5 variantes de cada tipo.
    return 1 if variante % 2 == 0 else -1


def _matriz_3_4_zerada() -> np.ndarray:
    matriz = np.zeros((_ALTURA_MAT, _LARGURA_MAT), dtype=np.int8)
    for r in range(0, _ALTURA_MAT, 2):
        for c in range(0, _LARGURA_MAT, 2):
            matriz[r, c] = 8
    return matriz


def _arestas_da_caixa(br: int, bc: int) -> list[tuple[int, int]]:
    return [(br - 1, bc), (br + 1, bc), (br, bc - 1), (br, bc + 1)]


def _aresta_entre(c1: tuple[int, int], c2: tuple[int, int]) -> tuple[int, int] | None:
    br1, bc1 = c1
    br2, bc2 = c2
    if br1 == br2 and abs(bc1 - bc2) == 2:
        return (br1, (bc1 + bc2) // 2)
    if bc1 == bc2 and abs(br1 - br2) == 2:
        return ((br1 + br2) // 2, bc1)
    return None


def _aresta_e_borda_tabuleiro(ar: tuple[int, int], caixa: tuple[int, int]) -> bool:
    br, bc = caixa
    ar_r, ar_c = ar
    if ar_r == br - 1:
        return ar_r == 0
    if ar_r == br + 1:
        return ar_r == _ALTURA_MAT - 1
    if ar_c == bc - 1:
        return ar_c == 0
    if ar_c == bc + 1:
        return ar_c == _LARGURA_MAT - 1
    return False


def _escolher_aresta_externa(
    caixa: tuple[int, int], excluidas: set[tuple[int, int]]
) -> tuple[int, int]:
    candidatos = [a for a in _arestas_da_caixa(*caixa) if a not in excluidas]
    borda = [a for a in candidatos if _aresta_e_borda_tabuleiro(a, caixa)]
    if borda:
        return borda[0]
    return candidatos[0]


def _construir_corrente_aberta(
    caixas_seq: list[tuple[int, int]], marker: int
) -> np.ndarray:
    matriz = _matriz_3_4_zerada()
    n = len(caixas_seq)

    arestas_internas: set[tuple[int, int]] = set()
    for i in range(n - 1):
        ar = _aresta_entre(caixas_seq[i], caixas_seq[i + 1])
        if ar is None:
            raise ValueError(
                f"caixas {caixas_seq[i]} e {caixas_seq[i+1]} não são adjacentes"
            )
        arestas_internas.add(ar)

    arestas_externas: set[tuple[int, int]] = set()
    if n == 1:
        c = caixas_seq[0]
        arestas_externas.add(_escolher_aresta_externa(c, arestas_externas))
        arestas_externas.add(_escolher_aresta_externa(c, arestas_externas))
    else:
        for ponta in (caixas_seq[0], caixas_seq[-1]):
            ext = _escolher_aresta_externa(ponta, arestas_internas | arestas_externas)
            arestas_externas.add(ext)

    arestas_livres = arestas_internas | arestas_externas

    for c in caixas_seq:
        for ar in _arestas_da_caixa(*c):
            if ar not in arestas_livres:
                matriz[ar] = marker

    return matriz


def _construir_ciclo_caixas(
    caixas_perimetro: list[tuple[int, int]],
    caixas_internas_fechadas: list[tuple[int, int]],
    marker: int,
) -> np.ndarray:
    matriz = _matriz_3_4_zerada()
    n = len(caixas_perimetro)

    arestas_do_ciclo: set[tuple[int, int]] = set()
    for i in range(n):
        c1 = caixas_perimetro[i]
        c2 = caixas_perimetro[(i + 1) % n]
        ar = _aresta_entre(c1, c2)
        if ar is None:
            raise ValueError(f"caixas {c1} e {c2} não são adjacentes no ciclo")
        arestas_do_ciclo.add(ar)

    a_preencher: set[tuple[int, int]] = set()
    for c in caixas_perimetro:
        for ar in _arestas_da_caixa(*c):
            if ar not in arestas_do_ciclo:
                a_preencher.add(ar)
    for c in caixas_internas_fechadas:
        for ar in _arestas_da_caixa(*c):
            a_preencher.add(ar)

    for ar in a_preencher:
        matriz[ar] = marker
    for c in caixas_internas_fechadas:
        matriz[c] = marker

    return matriz


def _envelopar(matriz: np.ndarray) -> EstadoTabuleiro:
    estado = EstadoTabuleiro(_LINHAS_PEQUENO, _COLUNAS_PEQUENO)
    estado.matriz = matriz
    return estado


def construir_estado_corrente_curta(variante: int) -> EstadoTabuleiro:
    """Tabuleiro 3x4 com uma corrente curta (1 ou 2 caixas grau-2)."""
    if variante not in (0, 1, 2, 3, 4):
        raise ValueError(f"variante deve estar em 0..4, recebido {variante}")
    marker = _marker_para_variante(variante)

    if variante == 0:
        seq = [(1, 1)]                      # 1 caixa, canto sup-esq
    elif variante == 1:
        seq = [(1, 1), (1, 3)]              # 2 caixas horizontais (linha do topo)
    elif variante == 2:
        seq = [(1, 1), (3, 1)]              # 2 caixas verticais (coluna esquerda)
    elif variante == 3:
        seq = [(7, 5)]                      # 1 caixa, canto inf-dir
    else:  # 4
        seq = [(5, 3), (5, 5)]              # 2 caixas horizontais (meio-direita)

    return _envelopar(_construir_corrente_aberta(seq, marker))


def construir_estado_corrente_longa(variante: int) -> EstadoTabuleiro:
    """Tabuleiro 3x4 com uma corrente longa (3 a 7 caixas grau-2 conectadas)."""
    if variante not in (0, 1, 2, 3, 4):
        raise ValueError(f"variante deve estar em 0..4, recebido {variante}")
    marker = _marker_para_variante(variante)

    if variante == 0:
        seq = [(1, 1), (1, 3), (1, 5)]                                   # 3 hor.
    elif variante == 1:
        seq = [(1, 1), (3, 1), (5, 1), (7, 1)]                           # 4 vert.
    elif variante == 2:
        seq = [(1, 1), (3, 1), (5, 1), (5, 3), (5, 5)]                   # 5 em L
    elif variante == 3:
        seq = [(1, 1), (1, 3), (3, 3), (3, 5), (5, 5), (7, 5)]           # 6 em S
    else:  # 4
        seq = [(1, 1), (3, 1), (3, 3), (5, 3), (5, 5), (7, 5), (7, 3)]   # 7 em zigue-zague

    return _envelopar(_construir_corrente_aberta(seq, marker))


def construir_estado_ciclo(
    tamanho: _Literal[4, 6, 8, 10], variante: int
) -> EstadoTabuleiro:
    """Tabuleiro 3x4 com um ciclo do tamanho especificado (4, 6, 8 ou 10 caixas)."""
    if tamanho not in (4, 6, 8, 10):
        raise ValueError(f"tamanho deve ser 4, 6, 8 ou 10, recebido {tamanho}")
    if variante not in (0, 1, 2, 3, 4):
        raise ValueError(f"variante deve estar em 0..4, recebido {variante}")
    marker = _marker_para_variante(variante)

    if tamanho == 4:
        # Bloco 2x2: 5 posições possíveis em tabuleiro 3x4 (4 linhas × 3 colunas).
        cantos_2x2 = [(1, 1), (1, 3), (3, 1), (5, 1), (5, 3)]
        br, bc = cantos_2x2[variante]
        perimetro = [(br, bc), (br, bc + 2), (br + 2, bc + 2), (br + 2, bc)]
        internas: list[tuple[int, int]] = []
    elif tamanho == 6:
        if variante == 0:
            perimetro = [(1, 1), (1, 3), (1, 5), (3, 5), (3, 3), (3, 1)]
            internas = []
        elif variante == 1:
            perimetro = [(3, 1), (3, 3), (3, 5), (5, 5), (5, 3), (5, 1)]
            internas = []
        elif variante == 2:
            perimetro = [(5, 1), (5, 3), (5, 5), (7, 5), (7, 3), (7, 1)]
            internas = []
        elif variante == 3:
            # bloco 3x2 esquerdo (3 linhas × 2 colunas)
            perimetro = [(1, 1), (1, 3), (3, 3), (5, 3), (5, 1), (3, 1)]
            internas = []
        else:  # 4
            perimetro = [(1, 3), (1, 5), (3, 5), (5, 5), (5, 3), (3, 3)]
            internas = []
    elif tamanho == 8:
        # Anel 3x3 sem o centro. 2 posições verticais possíveis (topo/baixo).
        # 5 variantes: 0,2,4 = topo; 1,3 = baixo.
        if variante in (0, 2, 4):
            perimetro = [
                (1, 1), (1, 3), (1, 5),
                (3, 5), (5, 5), (5, 3),
                (5, 1), (3, 1),
            ]
            internas = [(3, 3)]
        else:  # 1, 3
            perimetro = [
                (3, 1), (3, 3), (3, 5),
                (5, 5), (7, 5), (7, 3),
                (7, 1), (5, 1),
            ]
            internas = [(5, 3)]
    else:  # tamanho == 10
        # Anel 4x3 sem os 2 centros. Apenas uma topologia possível;
        # 5 variantes alternam apenas o marker (jogador).
        perimetro = [
            (1, 1), (1, 3), (1, 5),
            (3, 5), (5, 5), (7, 5),
            (7, 3), (7, 1), (5, 1), (3, 1),
        ]
        internas = [(3, 3), (5, 3)]

    return _envelopar(_construir_ciclo_caixas(perimetro, internas, marker))


def construir_estado_ramificada(variante: int) -> EstadoTabuleiro:
    """Tabuleiro 3x4 com uma estrutura ramificada (nó de grau > 2 no grafo dual).

    A "central" é uma caixa pivô (grau 0 ou 1 no jogo) ligada por arestas livres
    a 3+ caixas grau-2 (as "pontas"). Estas estruturas NÃO devem disparar
    double-dealing.
    """
    if variante not in (0, 1, 2, 3, 4):
        raise ValueError(f"variante deve estar em 0..4, recebido {variante}")
    marker = _marker_para_variante(variante)

    if variante == 0:
        central = (3, 3)
        pontas = [(1, 3), (3, 1), (3, 5)]
    elif variante == 1:
        central = (3, 3)
        pontas = [(1, 3), (5, 3), (3, 1), (3, 5)]
    elif variante == 2:
        central = (5, 3)
        pontas = [(3, 3), (5, 1), (5, 5)]
    elif variante == 3:
        central = (3, 1)
        pontas = [(1, 1), (5, 1), (3, 3)]
    else:  # 4
        central = (5, 3)
        pontas = [(3, 3), (5, 1), (5, 5), (7, 3)]

    matriz = _matriz_3_4_zerada()

    # Para cada ponta: precisa ficar grau 2 (2 arestas livres). Uma das livres é
    # a aresta compartilhada com a central; a outra é uma aresta externa
    # (preferindo borda).
    arestas_livres: set[tuple[int, int]] = set()
    for ponta in pontas:
        ar_pivo = _aresta_entre(ponta, central)
        if ar_pivo is None:
            raise ValueError(f"ponta {ponta} não é adjacente à central {central}")
        arestas_livres.add(ar_pivo)
        ar_externa = _escolher_aresta_externa(ponta, arestas_livres)
        arestas_livres.add(ar_externa)

    # Preencher arestas das pontas que não estão livres
    for ponta in pontas:
        for ar in _arestas_da_caixa(*ponta):
            if ar not in arestas_livres:
                matriz[ar] = marker
    # Arestas da central: TODAS ligadas às pontas ficam livres; as restantes
    # (não compartilhadas com pontas) também ficam livres → central tem grau 0
    # ou 1 e não é grau-2 (não vira parte da estrutura de captura).

    return _envelopar(matriz)


def construir_estado_mistura(variante: int) -> EstadoTabuleiro:
    """Tabuleiro 3x4 com múltiplas estruturas distintas no mesmo estado.

    Cada variante combina dois tipos diferentes (corrente + ciclo, ou duas
    correntes, etc.) em regiões disjuntas do tabuleiro.
    """
    if variante not in (0, 1, 2, 3, 4):
        raise ValueError(f"variante deve estar em 0..4, recebido {variante}")
    marker = _marker_para_variante(variante)

    matriz = _matriz_3_4_zerada()

    if variante == 0:
        # Corrente curta (2 caixas, topo) + ciclo de 4 (canto inf-esq)
        m1 = _construir_corrente_aberta([(1, 3), (1, 5)], marker)
        m2 = _construir_ciclo_caixas(
            [(5, 1), (5, 3), (7, 3), (7, 1)], [], marker
        )
    elif variante == 1:
        # Corrente longa (3 caixas, linha 3) + corrente curta (1 caixa, topo)
        m1 = _construir_corrente_aberta([(3, 1), (3, 3), (3, 5)], marker)
        m2 = _construir_corrente_aberta([(1, 5)], marker)
    elif variante == 2:
        # Ciclo de 4 (topo-esq) + corrente curta (2 caixas, fundo)
        m1 = _construir_ciclo_caixas(
            [(1, 1), (1, 3), (3, 3), (3, 1)], [], marker
        )
        m2 = _construir_corrente_aberta([(7, 3), (7, 5)], marker)
    elif variante == 3:
        # Duas correntes longas paralelas (linha 1 e linha 7)
        m1 = _construir_corrente_aberta([(1, 1), (1, 3), (1, 5)], marker)
        m2 = _construir_corrente_aberta([(7, 1), (7, 3), (7, 5)], marker)
    else:  # 4
        # Corrente longa (4 caixas em coluna) + ciclo de 4 no canto inf-dir
        m1 = _construir_corrente_aberta([(1, 1), (3, 1), (5, 1), (7, 1)], marker)
        m2 = _construir_ciclo_caixas(
            [(5, 3), (5, 5), (7, 5), (7, 3)], [], marker
        )

    # Combinar matrizes: para cada posição, OR lógico das marcações.
    # Se as estruturas são disjuntas (sem caixas em comum), a soma direta
    # funciona — pontos fixos (8) coincidem em ambas.
    matriz_final = _matriz_3_4_zerada()
    for r in range(_ALTURA_MAT):
        for c in range(_LARGURA_MAT):
            v1 = m1[r, c]
            v2 = m2[r, c]
            # Pontos fixos: já em matriz_final; arestas/caixas: pegar a não-zero
            if r % 2 == 0 and c % 2 == 0:
                continue
            if v1 != 0 and v2 != 0 and v1 != v2:
                matriz_final[r, c] = v1  # prioridade arbitrária, ambos válidos
            elif v1 != 0:
                matriz_final[r, c] = v1
            elif v2 != 0:
                matriz_final[r, c] = v2

    return _envelopar(matriz_final)


if __name__ == "__main__":
    main()

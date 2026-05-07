"""Análise de divergência estratégica CNN vs Minimax(p=9).

Cada PNG salvo em `tmp_analise/retratos_divergencia/...` vem acompanhado de
um `.npy` (matriz crua do EstadoTabuleiro logo antes da jogada da CNN) e um
`.json` com metadados (jogada CNN, jogada ótima, delta, profundidade do
oráculo, partida_idx, cnn_primeiro, número da jogada, n_grau3_disponivel).
Use o helper `_reanalisa_jogada_isolada.py` (modo --npy) para alimentar
qualquer profundidade de Minimax sobre o mesmo estado e checar se a
divergência detectada se mantém ou some com mais profundidade.

Cada partida usa um **seed determinístico** derivado de (partida_idx,
cnn_primeiro), de modo que a mesma combinação sempre gera a mesma
trajetória — mesmo em execução paralela com workers.

Diferença em relação aos outros analisadores:

- `analisa_misses_cnn.py` e `analisa_misses_com_minimax.py` só olham eventos
  de "caixa-perdida" (onde havia grau-3 disponível e a CNN não fechou).
  Esses scripts diagnosticam falhas TÁTICAS de fim de jogo.

- ESTE script joga partidas completas CNN vs Minimax(p_adv) e, para CADA
  jogada da CNN (com ou sem grau-3 disponível), consulta o oráculo
  Minimax(p=9) no mesmo estado e mede o Δ-score entre a jogada da CNN e
  a jogada ótima. Captura também ERROS ESTRATÉGICOS de meio de jogo
  (decisões de paridade/controle de cadeias) que os scripts existentes
  não enxergam.

Saída:

  * `tmp_analise/RELATORIO_DIVERGENCIA_ESTRATEGICA.md` com:
      - Distribuição de divergências por nº de traços (histograma).
      - Δ-score médio/mediano por faixa de jogada.
      - Cruzamento partidas-perdidas × divergência fatal precoce
        (jogada ≤ 25) vs tardia (≥ 28).
      - Decisão sugerida X1 / X2 / X3 (Cenário definido na Seção 2.4 do PRD
        `specs/004-melhoria-geracao-dados-cnn/PRD.md`).
  * CSV com todas as divergências em
    `tmp_analise/divergencias_estrategicas.csv` para análises ad-hoc.

Uso:

    python -m tmp_analise.analisa_divergencia_estrategica \\
        --modelo modelos/pontinhos_pequeno.tflite \\
        --tamanho pequeno \\
        --partidas 200 \\
        --profundidades 3 5 6 \\
        --oraculo 9 \\
        --workers 4

NOTA: a análise é cara — 200 partidas × 4 profundidades adversárias × ~15
jogadas/partida da CNN × Minimax(p=9) ≈ 12 mil chamadas Minimax(p=9). Em
4 workers gira em ~10–20 min para tabuleiro 4×3.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import os
import pickle
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# Silencia TF/Keras (CNN é carregada nos workers).
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

# raiz do repo no path
_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))


# ---------------------------------------------------------------------------
# Limiares de classificação (alinhados com a Seção 2.4 do PRD)
# ---------------------------------------------------------------------------

# Δ-score = (score Minimax da jogada ótima) - (score Minimax da jogada da CNN).
# Como o score Minimax é "saldo de caixas" (ver minimax_pontinhos.avaliar),
# Δ-score é em unidades de caixas.
DELTA_INOCUA_MAX  = 1   # CNN escolheu jogada quase tão boa (≤ 1 caixa de gap)
DELTA_MODERADA_MAX = 3  # gap de 2–3 caixas: divergência detectável

# Critério de "fase":
#   abertura = traços ∈ [0,  9]
#   meio     = traços ∈ [10, 24]   (onde estratégia de paridade decide)
#   transição= traços ∈ [25, 27]
#   fim      = traços ∈ [28, 30]   (onde a tática de captura domina)
# n_edges total = 31 (4×3 board)
LIMITE_MEIO_DE_JOGO = 25   # ≤25 traços = decisão pertence ao meio
LIMITE_FIM_DE_JOGO  = 28   # ≥28 traços = decisão é puramente tática


# ---------------------------------------------------------------------------
# Estruturas de dados — uma divergência detectada por jogada da CNN
# ---------------------------------------------------------------------------

@dataclass
class Divergencia:
    partida_idx: int
    adversario: str           # "Minimax(p=3)", etc.
    cnn_primeiro: bool
    numero_jogada: int        # numeração sequencial da jogada na partida (1-indexed)
    n_tracos_antes: int       # nº de traços já preenchidos antes da jogada
    jogada_cnn: str           # label canônico
    jogada_otima: str         # uma das melhores segundo Minimax(p=oraculo)
    score_cnn: int            # Q-value Minimax da jogada da CNN
    score_otimo: int          # Q-value Minimax da jogada ótima
    delta: int                # score_otimo - score_cnn (≥ 0)
    cnn_jogou_otima: bool     # True se delta == 0 (jogada da CNN está empatada com a ótima)
    n_grau3_disponivel: int   # nº de caixas grau-3 antes da jogada
    fase: str                 # "abertura" | "meio" | "transicao" | "fim"
    classe_delta: str         # "inocua" | "moderada" | "fatal"
    retrato_path: str | None = None  # caminho relativo do PNG (se gerado)

    @property
    def chave_csv(self) -> dict:
        return {
            "partida_idx": self.partida_idx,
            "adversario": self.adversario,
            "cnn_primeiro": int(self.cnn_primeiro),
            "numero_jogada": self.numero_jogada,
            "n_tracos_antes": self.n_tracos_antes,
            "jogada_cnn": self.jogada_cnn,
            "jogada_otima": self.jogada_otima,
            "score_cnn": self.score_cnn,
            "score_otimo": self.score_otimo,
            "delta": self.delta,
            "cnn_jogou_otima": int(self.cnn_jogou_otima),
            "n_grau3_disponivel": self.n_grau3_disponivel,
            "fase": self.fase,
            "classe_delta": self.classe_delta,
            "retrato_path": self.retrato_path or "",
        }


@dataclass
class ResultadoPartida:
    partida_idx: int
    adversario: str
    cnn_primeiro: bool
    pontos_cnn: int
    pontos_mm: int
    vencedor: str             # "cnn" | "mm" | "empate"
    divergencias: list[Divergencia] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers básicos
# ---------------------------------------------------------------------------

def _classe_delta(delta: int) -> str:
    if delta <= DELTA_INOCUA_MAX:
        return "inocua"
    if delta <= DELTA_MODERADA_MAX:
        return "moderada"
    return "fatal"


def _fase_por_n_tracos(n_tracos: int) -> str:
    if n_tracos <= 9:
        return "abertura"
    if n_tracos < LIMITE_MEIO_DE_JOGO:
        return "meio"
    if n_tracos < LIMITE_FIM_DE_JOGO:
        return "transicao"
    return "fim"


def _contar_grau3(matriz: np.ndarray) -> int:
    """Nº de caixas (ímpar, ímpar) com 3 arestas vizinhas preenchidas."""
    h, w = matriz.shape
    linhas = (h - 1) // 2
    colunas = (w - 1) // 2
    n = 0
    for r in range(linhas):
        for c in range(colunas):
            if matriz[2*r+1, 2*c+1] != 0:
                continue
            preenchidas = (
                int(matriz[2*r,   2*c+1] != 0) +
                int(matriz[2*r+2, 2*c+1] != 0) +
                int(matriz[2*r+1, 2*c  ] != 0) +
                int(matriz[2*r+1, 2*c+2] != 0)
            )
            if preenchidas == 3:
                n += 1
    return n


def _contar_tracos(matriz: np.ndarray) -> int:
    """Conta arestas (posições não-vértice) preenchidas."""
    h, w = matriz.shape
    n = 0
    for r in range(h):
        for c in range(w):
            if r % 2 == 0 and c % 2 == 0:
                continue   # vértice fixo
            if r % 2 == 1 and c % 2 == 1:
                continue   # caixa
            if matriz[r, c] != 0:
                n += 1
    return n


# ---------------------------------------------------------------------------
# Renderização de retratos PNG por jogada
# ---------------------------------------------------------------------------

# Cores no contexto PARTIDA (encoding {-1, 0, +1, 8})
_RGB_PONTO       = (0, 0, 0)
_RGB_VAZIO       = (245, 245, 245)
_RGB_CNN         = (0, 87, 183)        # azul Arena Sagaz
_RGB_MM          = (193, 57, 43)       # vermelho terra
_RGB_ARESTA      = (90, 90, 90)
_RGB_JOGADA_CNN  = (255, 165, 0)       # laranja: jogada que a CNN/MM fez
_RGB_JOGADA_OTIM = (46, 204, 113)      # verde: jogada ótima (max-score)
_RGB_JOGADA_PIOR = (139, 69, 19)       # marrom: piores jogadas (min-score)


def _label_para_pos(label: str | None, h: int, w: int) -> tuple[int, int] | None:
    if not label:
        return None
    m = re.match(r"^[HV]_(\d+)_(\d+)$", label)
    if not m:
        return None
    r, c = int(m.group(1)), int(m.group(2))
    if 0 <= r < h and 0 <= c < w:
        return r, c
    return None


def _matriz_partida_para_rgb(
    matriz: np.ndarray,
    cnn_valor: int,
    jogada_cnn: str | None = None,
    jogada_otima: str | None = None,
    *,
    jogadas_otimas: list[str] | None = None,
    jogadas_piores: list[str] | None = None,
) -> np.ndarray:
    """Encoding partida → RGB com destaque opcional para jogadas-alvo.

    Ordem de pintura (cor mais alta sobrescreve mais baixa):
      base → ARESTA → PIORES (marrom) → ÓTIMAS (verde) → JOGADA_FEITA (laranja)

    Permite tanto destaque por label único (jogada_cnn / jogada_otima)
    quanto por listas (jogadas_otimas / jogadas_piores), usadas no PNG do MM.
    """
    h, w = matriz.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[:] = _RGB_VAZIO
    for r in range(h):
        for c in range(w):
            v = matriz[r, c]
            if r % 2 == 0 and c % 2 == 0:
                rgb[r, c] = _RGB_PONTO
            elif r % 2 == 1 and c % 2 == 1:
                if v == cnn_valor:
                    rgb[r, c] = _RGB_CNN
                elif v == -cnn_valor:
                    rgb[r, c] = _RGB_MM
            else:
                if v != 0:
                    rgb[r, c] = _RGB_ARESTA

    def _pintar(label: str | None, cor: tuple[int, int, int]) -> None:
        pos = _label_para_pos(label, h, w)
        if pos is not None:
            rgb[pos[0], pos[1]] = cor

    # 1. piores (marrom) primeiro — para que verde sobrescreva caso uma
    #    posição esteja simultaneamente em min e max (acontece quando todos
    #    empatam: pintamos tudo verde por convenção).
    for lbl in (jogadas_piores or []):
        _pintar(lbl, _RGB_JOGADA_PIOR)
    # 2. ótimas (verde)
    for lbl in (jogadas_otimas or []):
        _pintar(lbl, _RGB_JOGADA_OTIM)
    _pintar(jogada_otima, _RGB_JOGADA_OTIM)
    # 3. jogada feita (laranja) por último — sempre vence
    _pintar(jogada_cnn, _RGB_JOGADA_CNN)
    return rgb


def _salvar_retrato_jogada(
    matriz_antes: np.ndarray,
    cnn_valor: int,
    jogada_cnn: str,
    jogada_otima: str,
    delta: int,
    classe_delta: str,
    n_tracos_antes: int,
    fase: str,
    titulo_extra: str,
    caminho_saida: Path,
    *,
    partida_idx: int | None = None,
    cnn_primeiro: bool | None = None,
    adversario: str | None = None,
    numero_jogada: int | None = None,
    prof_oraculo: int | None = None,
    n_grau3_disponivel: int | None = None,
) -> None:
    """Renderiza um PNG com 2 painéis: jogada feita vs jogada ótima.

    - Painel esquerdo: estado antes + aresta JOGADA pela CNN destacada (laranja).
    - Painel direito:  estado antes + aresta ÓTIMA do oráculo destacada (verde).
    Quando delta=0 os dois painéis ficam visualmente equivalentes.

    Cria a pasta `caminho_saida.parent` automaticamente.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rgb_cnn = _matriz_partida_para_rgb(
        matriz_antes, cnn_valor, jogada_cnn=jogada_cnn, jogada_otima=None,
    )
    rgb_otim = _matriz_partida_para_rgb(
        matriz_antes, cnn_valor, jogada_cnn=None, jogada_otima=jogada_otima,
    )

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(6, 3.2), dpi=110)
    axes[0].imshow(rgb_cnn, interpolation="nearest")
    axes[0].axis("off")
    axes[0].set_title(f"CNN jogou: {jogada_cnn}", fontsize=9)
    axes[1].imshow(rgb_otim, interpolation="nearest")
    axes[1].axis("off")
    axes[1].set_title(f"Ótima: {jogada_otima}", fontsize=9)

    suptitulo = (
        f"{titulo_extra} | traços={n_tracos_antes} ({fase}) | "
        f"Δ={delta} ({classe_delta})"
    )
    fig.suptitle(suptitulo, fontsize=10)
    fig.tight_layout()
    # Sem bbox_inches="tight" → dimensão final = figsize × dpi (fixa).
    # Garante PNGs CNN e MM com EXATAMENTE o mesmo tamanho em pixels.
    fig.savefig(caminho_saida)
    plt.close(fig)

    # Salva também a matriz crua (NPY) e os metadados (JSON) ao lado do PNG.
    # Permite reanalisar a jogada off-line sem precisar replay da partida.
    npy_path = caminho_saida.with_suffix(".npy")
    json_path = caminho_saida.with_suffix(".json")
    np.save(npy_path, matriz_antes)
    metadados = {
        "schema": 1,
        "matriz_antes_npy": npy_path.name,
        "encoding": "matriz crua do EstadoTabuleiro (caixas: jogador=±1; arestas: ±1; vértices: 0)",
        "cnn_valor": int(cnn_valor),
        "jogada_cnn": jogada_cnn,
        "jogada_otima": jogada_otima,
        "delta": int(delta),
        "classe_delta": classe_delta,
        "n_tracos_antes": int(n_tracos_antes),
        "fase": fase,
        "titulo_extra": titulo_extra,
        "partida_idx": partida_idx,
        "cnn_primeiro": cnn_primeiro,
        "adversario": adversario,
        "numero_jogada": numero_jogada,
        "prof_oraculo": prof_oraculo,
        "n_grau3_disponivel": n_grau3_disponivel,
    }
    with open(json_path, "w", encoding="utf-8") as fp:
        json.dump(metadados, fp, ensure_ascii=False, indent=2)


def _salvar_retrato_jogada_mm(
    matriz_antes: np.ndarray,
    cnn_valor: int,
    jogada_mm: str,
    scores_mm: dict[str, int],
    score_max: int,
    score_min: int,
    jogadas_otimas: list[str],
    jogadas_piores: list[str],
    prof_mm: int,
    n_tracos_antes: int,
    fase: str,
    titulo_extra: str,
    caminho_saida: Path,
    *,
    partida_idx: int | None = None,
    cnn_primeiro: bool | None = None,
    adversario: str | None = None,
    numero_jogada: int | None = None,
    n_grau3_disponivel: int | None = None,
) -> None:
    """Renderiza PNG da jogada do Minimax (perspectiva DELE):

    - Painel esquerdo: estado antes + aresta JOGADA pelo MM destacada (laranja).
      Título: "Minimax p=X jogou: <label>"
    - Painel direito:  estado antes + TODAS as jogadas de score_max em verde
      e TODAS as jogadas de score_min em marrom. Quando max==min (empate
      total — comum em p=1), pinta tudo verde.
      Título: "score max=A | score min=B"

    Profundidade usada para max/min é a MESMA do MM (não a do oráculo) — o
    PNG mostra o que o MM efetivamente "viu" ao decidir.

    Salva também NPY (matriz crua) e JSON com todos os scores.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Empate total → pintamos como se TUDO fosse ótimo (não há piores reais).
    if score_max == score_min:
        otimas_render = list(scores_mm.keys())
        piores_render: list[str] = []
    else:
        otimas_render = list(jogadas_otimas)
        piores_render = list(jogadas_piores)

    rgb_jogada = _matriz_partida_para_rgb(
        matriz_antes, cnn_valor, jogada_cnn=jogada_mm,
    )
    rgb_scores = _matriz_partida_para_rgb(
        matriz_antes, cnn_valor,
        jogadas_otimas=otimas_render,
        jogadas_piores=piores_render,
    )

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(6, 3.2), dpi=110)
    axes[0].imshow(rgb_jogada, interpolation="nearest")
    axes[0].axis("off")
    axes[0].set_title(f"Minimax p={prof_mm} jogou: {jogada_mm}", fontsize=9)
    axes[1].imshow(rgb_scores, interpolation="nearest")
    axes[1].axis("off")
    axes[1].set_title(f"score max={score_max:+d} | score min={score_min:+d}", fontsize=9)

    suptitulo = f"{titulo_extra} | traços={n_tracos_antes} ({fase})"
    fig.suptitle(suptitulo, fontsize=10)
    fig.tight_layout()
    # Sem bbox_inches="tight" → dimensão final = figsize × dpi (fixa).
    # Garante PNGs CNN e MM com EXATAMENTE o mesmo tamanho em pixels.
    fig.savefig(caminho_saida)
    plt.close(fig)

    npy_path = caminho_saida.with_suffix(".npy")
    json_path = caminho_saida.with_suffix(".json")
    np.save(npy_path, matriz_antes)
    metadados = {
        "schema": 1,
        "tipo": "jogada_mm",
        "matriz_antes_npy": npy_path.name,
        "encoding": "matriz crua do EstadoTabuleiro (caixas: jogador=±1; arestas: ±1; vértices: 0)",
        "cnn_valor": int(cnn_valor),
        "jogada_mm": jogada_mm,
        "scores_mm": {k: int(v) for k, v in scores_mm.items()},
        "score_max": int(score_max),
        "score_min": int(score_min),
        "jogadas_otimas": list(jogadas_otimas),
        "jogadas_piores": list(jogadas_piores),
        "prof_mm": int(prof_mm),
        "n_tracos_antes": int(n_tracos_antes),
        "fase": fase,
        "titulo_extra": titulo_extra,
        "partida_idx": partida_idx,
        "cnn_primeiro": cnn_primeiro,
        "adversario": adversario,
        "numero_jogada": numero_jogada,
        "n_grau3_disponivel": n_grau3_disponivel,
    }
    with open(json_path, "w", encoding="utf-8") as fp:
        json.dump(metadados, fp, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Worker: roda 1 partida CNN vs Minimax(p_adv) registrando divergências
# ---------------------------------------------------------------------------

# Globais por processo — inicializadas em _proc_init para amortizar carga TFLite
_PROC_CNN = None
_PROC_AGENTE_ADV = None
_PROC_LABELS = None
_PROC_ORACULO = None              # int (modo fixo) ou tuple[(min_livres, prof), ...] (adaptativo)
_PROC_TAMANHO = None
_PROC_PASTA_RETRATOS = None       # Path ou None — se setado, salva PNG por jogada da CNN
_PROC_PROF_ADV = None             # int — profundidade do MM adversário (para PNG do MM)


# Política adaptativa: dado um número de traços LIVRES (não jogados ainda) na
# matriz, devolve a profundidade do oráculo. Calibrada para 4×3 (31 traços
# totais).  Garante p=9 sempre que ainda há ≥ 0 e ≤ 17 livres (meio crítico
# até o fim), p=7 na abertura tardia (18-25), p=5 na abertura inicial (≥ 26).
# Buckets ordenados do MAIS livre para o MENOS livre.
_TABELA_ORACULO_ADAPTATIVO = (
    (26, 5),  # livres ≥ 26  → p=5
    (18, 7),  # livres ≥ 18  → p=7
    (0,  9),  # livres ≥ 0   → p=9
)


def _profundidade_oraculo_para_estado(n_tracos_livres: int) -> int:
    """Retorna profundidade do oráculo. _PROC_ORACULO pode ser int (fixo) ou
    tuple[(min_livres, prof), ...] (adaptativo)."""
    if isinstance(_PROC_ORACULO, int):
        return _PROC_ORACULO
    for min_livres, prof in _PROC_ORACULO:
        if n_tracos_livres >= min_livres:
            return prof
    return _PROC_ORACULO[-1][1]


def _proc_init(caminho_modelo, tamanho, prof_adv, prof_oraculo, pasta_retratos):
    """Carrega CNN + Minimax adversário UMA VEZ por processo-worker.
    `prof_oraculo` pode ser int (fixo) ou tuple de buckets (adaptativo)."""
    global _PROC_CNN, _PROC_AGENTE_ADV, _PROC_LABELS, _PROC_ORACULO, _PROC_TAMANHO
    global _PROC_PASTA_RETRATOS, _PROC_PROF_ADV
    from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import (
        _cnn_agent_fn, _minimax_agent_fn,
    )
    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import todos_labels_canonicos

    _PROC_LABELS = (
        todos_labels_canonicos(4, 3) if tamanho == "pequeno"
        else todos_labels_canonicos(5, 4)
    )
    _PROC_CNN = _cnn_agent_fn(caminho_modelo, _PROC_LABELS)
    _PROC_AGENTE_ADV = _minimax_agent_fn(prof_adv)
    _PROC_PROF_ADV = prof_adv
    _PROC_ORACULO = prof_oraculo
    _PROC_TAMANHO = tamanho
    _PROC_PASTA_RETRATOS = Path(pasta_retratos) if pasta_retratos else None


def _slug_adversario(nome: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", nome).strip("_")


def _jogar_partida_com_divergencias(args):
    """Joga UMA partida CNN vs Minimax(p_adv) e registra divergências da CNN."""
    partida_idx, cnn_primeiro, adversario_nome = args

    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
    from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

    # Seed determinística por (partida_idx, cnn_primeiro). Garante que o
    # tie-breaking do Minimax adversário é reproduzível — cada PNG/NPY salvo
    # corresponde a uma trajetória que pode ser replicada off-line passando
    # exatamente este seed.
    import random
    seed_reproduzivel = (partida_idx * 2) + (1 if cnn_primeiro else 0)
    random.seed(seed_reproduzivel)

    estado = EstadoTabuleiro.de_tamanho(_PROC_TAMANHO)
    turno_cnn = 1 if cnn_primeiro else 2  # turno_id da CNN
    turno_corrente = 1
    valor_matriz = {1: 1, 2: -1}
    cnn_valor = valor_matriz[turno_cnn]   # +1 ou -1, ponto de vista da CNN

    divergencias: list[Divergencia] = []
    numero_jogada = 0

    # Pasta para retratos desta partida (se ativado)
    pasta_partida: Path | None = None
    if _PROC_PASTA_RETRATOS is not None:
        slug = _slug_adversario(adversario_nome)
        pos = "cnn1" if cnn_primeiro else "cnn2"
        pasta_partida = (
            _PROC_PASTA_RETRATOS / slug / f"{pos}_partida{partida_idx:04d}"
        )

    while not estado.esta_terminal():
        numero_jogada += 1

        if turno_corrente == turno_cnn:
            # Antes da CNN jogar, calcula Minimax(p=oraculo) — com TODOS os scores.
            # ATENÇÃO: o Minimax assume que o jogador da vez é o "maximizador"
            # (sempre joga com valor 1). Como o motor é simétrico em sinal, isso
            # reflete corretamente a perspectiva do jogador da vez,
            # independente de qual cor ele está usando na matriz.
            #
            # Profundidade do oráculo é ADAPTATIVA: profundidades baixas no
            # início do jogo (onde a árvore explode) e p=9 (perfeita) no meio
            # crítico em diante (onde p=9 é factível e onde divergências
            # importam mais para a classificação X1/X2/X3).
            n_tracos_antes = _contar_tracos(estado.matriz)
            n_tracos_livres = len(_PROC_LABELS) - n_tracos_antes
            prof_oraculo = _profundidade_oraculo_para_estado(n_tracos_livres)
            scores_oraculo = _scores_de_todas_jogadas(estado, prof_oraculo)
            score_max = max(scores_oraculo.values())

            n_grau3 = _contar_grau3(estado.matriz)
            matriz_antes = estado.matriz.copy() if pasta_partida is not None else None

            jogada_cnn = _PROC_CNN(estado)
            score_cnn = scores_oraculo.get(jogada_cnn, score_max)
            delta = int(score_max - score_cnn)

            jogada_otima = next(
                (t for t, s in scores_oraculo.items() if s == score_max),
                jogada_cnn,
            )
            classe = _classe_delta(delta)
            fase = _fase_por_n_tracos(n_tracos_antes)
            retrato_path = None
            if pasta_partida is not None:
                nome_arq = (
                    f"jogada{numero_jogada:03d}_cnn_t{n_tracos_antes:02d}"
                    f"_d{delta}_{classe}.png"
                )
                caminho = pasta_partida / nome_arq
                titulo = f"part {partida_idx} jog {numero_jogada} ({adversario_nome})"
                _salvar_retrato_jogada(
                    matriz_antes=matriz_antes,
                    cnn_valor=cnn_valor,
                    jogada_cnn=jogada_cnn,
                    jogada_otima=jogada_otima,
                    delta=delta,
                    classe_delta=classe,
                    n_tracos_antes=n_tracos_antes,
                    fase=fase,
                    titulo_extra=titulo,
                    caminho_saida=caminho,
                    partida_idx=partida_idx,
                    cnn_primeiro=cnn_primeiro,
                    adversario=adversario_nome,
                    numero_jogada=numero_jogada,
                    prof_oraculo=prof_oraculo,
                    n_grau3_disponivel=n_grau3,
                )
                # Caminho relativo à pasta-mãe dos retratos para o relatório
                try:
                    retrato_path = str(
                        caminho.relative_to(_PROC_PASTA_RETRATOS)
                    ).replace("\\", "/")
                except ValueError:
                    retrato_path = str(caminho)

            div = Divergencia(
                partida_idx=partida_idx,
                adversario=adversario_nome,
                cnn_primeiro=cnn_primeiro,
                numero_jogada=numero_jogada,
                n_tracos_antes=n_tracos_antes,
                jogada_cnn=jogada_cnn,
                jogada_otima=jogada_otima,
                score_cnn=int(score_cnn),
                score_otimo=int(score_max),
                delta=delta,
                cnn_jogou_otima=(delta == 0),
                n_grau3_disponivel=n_grau3,
                fase=fase,
                classe_delta=classe,
                retrato_path=retrato_path,
            )
            divergencias.append(div)

            caixas = estado.aplicar_traco(jogada_cnn, valor_matriz[turno_corrente])
        else:
            # Vez do Minimax adversário. Quando geramos retratos, calculamos
            # _scores_de_todas_jogadas com a profundidade DELE (não a do
            # oráculo) e escolhemos uma das ótimas com tie-break aleatório
            # determinístico — equivalente a chamar _PROC_AGENTE_ADV mas com
            # acesso à tabela inteira para pintar verde/marrom.
            n_tracos_mm = _contar_tracos(estado.matriz)
            fase_mm = _fase_por_n_tracos(n_tracos_mm)
            n_grau3_mm = _contar_grau3(estado.matriz)
            if pasta_partida is not None:
                matriz_antes_mm = estado.matriz.copy()
                scores_mm = _scores_de_todas_jogadas(estado, _PROC_PROF_ADV)
                score_max_mm = max(scores_mm.values())
                score_min_mm = min(scores_mm.values())
                jogadas_otimas_mm = sorted(
                    [t for t, s in scores_mm.items() if s == score_max_mm]
                )
                jogadas_piores_mm = sorted(
                    [t for t, s in scores_mm.items() if s == score_min_mm]
                )
                jogada_adv = random.choice(jogadas_otimas_mm)
                nome_arq_mm = (
                    f"jogada{numero_jogada:03d}_mm_t{n_tracos_mm:02d}.png"
                )
                caminho_mm = pasta_partida / nome_arq_mm
                titulo_mm = (
                    f"part {partida_idx} jog {numero_jogada} ({adversario_nome})"
                )
                _salvar_retrato_jogada_mm(
                    matriz_antes=matriz_antes_mm,
                    cnn_valor=cnn_valor,
                    jogada_mm=jogada_adv,
                    scores_mm=scores_mm,
                    score_max=score_max_mm,
                    score_min=score_min_mm,
                    jogadas_otimas=jogadas_otimas_mm,
                    jogadas_piores=jogadas_piores_mm,
                    prof_mm=_PROC_PROF_ADV,
                    n_tracos_antes=n_tracos_mm,
                    fase=fase_mm,
                    titulo_extra=titulo_mm,
                    caminho_saida=caminho_mm,
                    partida_idx=partida_idx,
                    cnn_primeiro=cnn_primeiro,
                    adversario=adversario_nome,
                    numero_jogada=numero_jogada,
                    n_grau3_disponivel=n_grau3_mm,
                )
            else:
                jogada_adv = _PROC_AGENTE_ADV(estado)
            caixas = estado.aplicar_traco(jogada_adv, valor_matriz[turno_corrente])

        if caixas == 0:
            turno_corrente = 3 - turno_corrente

    interior = estado.matriz[1::2, 1::2]
    p1 = int((interior == 1).sum())
    p2 = int((interior == -1).sum())
    if cnn_primeiro:
        pontos_cnn, pontos_mm = p1, p2
    else:
        pontos_cnn, pontos_mm = p2, p1

    if pontos_cnn > pontos_mm:
        venc = "cnn"
    elif pontos_mm > pontos_cnn:
        venc = "mm"
    else:
        venc = "empate"

    return ResultadoPartida(
        partida_idx=partida_idx,
        adversario=adversario_nome,
        cnn_primeiro=cnn_primeiro,
        pontos_cnn=pontos_cnn,
        pontos_mm=pontos_mm,
        vencedor=venc,
        divergencias=divergencias,
    )


# ---------------------------------------------------------------------------
# Coletor: para cada profundidade adversária, joga N partidas em paralelo
# ---------------------------------------------------------------------------

def coletar_partidas(
    caminho_modelo: str,
    tamanho: str,
    prof_adv: int,
    prof_oraculo: int,
    n_partidas: int,
    workers: int,
    pasta_retratos: Path | None = None,
    progresso_a_cada: int = 10,
) -> list[ResultadoPartida]:
    """Joga `n_partidas` CNN vs Minimax(p=prof_adv), metade com CNN como
    primeiro e metade como segundo. Retorna lista de ResultadoPartida.
    """
    metade = n_partidas // 2
    nome_adv = f"Minimax(p={prof_adv})"
    tasks: list[tuple[int, bool, str]] = []
    for i in range(metade):
        tasks.append((i, True, nome_adv))
    for i in range(metade):
        tasks.append((1000 + i, False, nome_adv))

    resultados: list[ResultadoPartida] = []
    t0 = time.perf_counter()
    total = len(tasks)
    pasta_str = str(pasta_retratos) if pasta_retratos else None
    with cf.ProcessPoolExecutor(
        max_workers=workers,
        initializer=_proc_init,
        initargs=(caminho_modelo, tamanho, prof_adv, prof_oraculo, pasta_str),
    ) as ex:
        futures = [ex.submit(_jogar_partida_com_divergencias, t) for t in tasks]
        for i, fut in enumerate(cf.as_completed(futures), 1):
            resultados.append(fut.result())
            dt = time.perf_counter() - t0
            # Print compacto a cada partida concluída (com ETA por extrapolação
            # do tempo médio observado até agora).
            ritmo = dt / i if i else 0.0
            restantes = total - i
            eta_s = ritmo * restantes
            barra_pct = 100 * i / total
            print(
                f"  [{nome_adv}] {i:3d}/{total} ({barra_pct:5.1f}%)  "
                f"decorrido {dt:6.0f}s  ritmo {ritmo:5.1f}s/partida  "
                f"ETA {eta_s/60:5.1f}min",
                flush=True,
            )
    return resultados


# ---------------------------------------------------------------------------
# Sumarização e relatório
# ---------------------------------------------------------------------------

def _sumarizar_por_adversario(
    resultados_por_adv: dict[str, list[ResultadoPartida]],
) -> dict:
    """Agrega métricas globais e por adversário."""
    sumario = {}
    for adv, partidas in resultados_por_adv.items():
        n_partidas = len(partidas)
        vit_cnn = sum(1 for p in partidas if p.vencedor == "cnn")
        derr_cnn = sum(1 for p in partidas if p.vencedor == "mm")
        emp = n_partidas - vit_cnn - derr_cnn

        # Divergências da CNN nesta condição
        divs = [d for p in partidas for d in p.divergencias]
        n_divs = len(divs)
        n_inoc = sum(1 for d in divs if d.classe_delta == "inocua")
        n_mod  = sum(1 for d in divs if d.classe_delta == "moderada")
        n_fat  = sum(1 for d in divs if d.classe_delta == "fatal")

        # Divergências fatais por fase
        n_fat_meio = sum(
            1 for d in divs
            if d.classe_delta == "fatal" and d.n_tracos_antes < LIMITE_MEIO_DE_JOGO
        )
        n_fat_trans = sum(
            1 for d in divs
            if d.classe_delta == "fatal"
            and LIMITE_MEIO_DE_JOGO <= d.n_tracos_antes < LIMITE_FIM_DE_JOGO
        )
        n_fat_fim = sum(
            1 for d in divs
            if d.classe_delta == "fatal" and d.n_tracos_antes >= LIMITE_FIM_DE_JOGO
        )

        # Para cada partida perdida, há divergência fatal em fase ≤ meio?
        partidas_perdidas = [p for p in partidas if p.vencedor == "mm"]
        n_perd = len(partidas_perdidas)
        n_perd_com_fatal_precoce = sum(
            1 for p in partidas_perdidas
            if any(
                d.classe_delta == "fatal" and d.n_tracos_antes <= LIMITE_MEIO_DE_JOGO
                for d in p.divergencias
            )
        )
        n_perd_com_fatal_tardia_apenas = sum(
            1 for p in partidas_perdidas
            if (
                any(d.classe_delta == "fatal" for d in p.divergencias)
                and not any(
                    d.classe_delta == "fatal"
                    and d.n_tracos_antes <= LIMITE_MEIO_DE_JOGO
                    for d in p.divergencias
                )
            )
        )
        n_perd_sem_fatal = sum(
            1 for p in partidas_perdidas
            if not any(d.classe_delta == "fatal" for d in p.divergencias)
        )

        # Divergências fatais por partida (média)
        fatais_por_partida = [
            sum(1 for d in p.divergencias if d.classe_delta == "fatal")
            for p in partidas
        ]

        sumario[adv] = {
            "n_partidas": n_partidas,
            "vitorias_cnn": vit_cnn,
            "derrotas_cnn": derr_cnn,
            "empates": emp,
            "pct_vitorias": 100 * vit_cnn / n_partidas if n_partidas else 0.0,
            "n_divergencias": n_divs,
            "n_inocua": n_inoc,
            "n_moderada": n_mod,
            "n_fatal": n_fat,
            "n_fatal_meio": n_fat_meio,
            "n_fatal_transicao": n_fat_trans,
            "n_fatal_fim": n_fat_fim,
            "n_perdidas": n_perd,
            "n_perdidas_com_fatal_precoce": n_perd_com_fatal_precoce,
            "n_perdidas_com_fatal_tardia_apenas": n_perd_com_fatal_tardia_apenas,
            "n_perdidas_sem_fatal": n_perd_sem_fatal,
            "fatais_por_partida_media": (
                float(np.mean(fatais_por_partida)) if fatais_por_partida else 0.0
            ),
            "fatais_por_partida_p95": (
                float(np.percentile(fatais_por_partida, 95))
                if fatais_por_partida else 0.0
            ),
        }
    return sumario


def _classificar_cenario(sumario: dict) -> tuple[str, str]:
    """Avalia o cenário X1/X2/X3 considerando só Minimax(p=5/6) (que é onde
    a Categoria B se manifesta com mais força)."""
    advs_chave = [a for a in sumario if "p=5" in a or "p=6" in a]
    if not advs_chave:
        # fallback: usa todos
        advs_chave = list(sumario.keys())

    # Razão (perdidas com fatal precoce) / (todas perdidas) — média entre p=5/6
    razoes = []
    for a in advs_chave:
        s = sumario[a]
        if s["n_perdidas"] == 0:
            continue
        razoes.append(s["n_perdidas_com_fatal_precoce"] / s["n_perdidas"])
    razao_media = float(np.mean(razoes)) if razoes else 0.0

    limite_meio = LIMITE_MEIO_DE_JOGO
    if razao_media < 0.10:
        return (
            "X1",
            f"Categoria B desprezível: apenas {razao_media:.0%} das partidas "
            f"perdidas têm divergência fatal em fase de meio de jogo "
            f"(<= {limite_meio} traços). "
            "Fases A+B+C devem ser suficientes; Fase D opcional.",
        )
    if razao_media > 0.30:
        return (
            "X2",
            f"Categoria B dominante: {razao_media:.0%} das partidas perdidas "
            "têm divergência fatal precoce. Fase D é OBRIGATÓRIA — canais "
            "estruturais `em_cadeia_*`/`em_loop`/`em_cadeia_aberta_uma_ponta` "
            "atacam diretamente esse modo de falha.",
        )
    return (
        "X3",
        f"Cenário misto: {razao_media:.0%} das partidas perdidas com "
        "divergência fatal precoce. Manter plano completo (A→D); calibrar "
        "expectativas: Fases A+B+C atacam ~50% do gap, Fase D ataca a outra metade.",
    )


def _histograma_por_traco(divs: list[Divergencia]) -> list[tuple[int, int, int, int]]:
    """Retorna [(n_tracos, total, fatais, moderadas)]."""
    bucket = defaultdict(lambda: {"total": 0, "fatal": 0, "moderada": 0})
    for d in divs:
        bucket[d.n_tracos_antes]["total"] += 1
        if d.classe_delta == "fatal":
            bucket[d.n_tracos_antes]["fatal"] += 1
        elif d.classe_delta == "moderada":
            bucket[d.n_tracos_antes]["moderada"] += 1
    return [
        (n, b["total"], b["fatal"], b["moderada"])
        for n, b in sorted(bucket.items())
    ]


def _top_pares_divergentes(divs: list[Divergencia], n: int = 10) -> list[tuple]:
    """Top-N pares (jogada_otima → jogada_cnn) com Δ ≥ 2."""
    cnt = Counter()
    for d in divs:
        if d.delta >= 2:
            cnt[(d.jogada_otima, d.jogada_cnn, d.fase)] += 1
    return cnt.most_common(n)


def gerar_relatorio_md(
    resultados_por_adv: dict[str, list[ResultadoPartida]],
    sumario: dict,
    cenario: str,
    parecer: str,
    parametros: dict,
    saida: Path,
) -> None:
    todas_divs = [
        d for partidas in resultados_por_adv.values()
        for p in partidas
        for d in p.divergencias
    ]

    linhas: list[str] = []
    A = linhas.append

    A("# Relatório de divergência estratégica — CNN vs Minimax")
    A("")
    A(f"**Modelo:** `{parametros['modelo']}`  ")
    A(f"**Tamanho:** `{parametros['tamanho']}`  ")
    A(f"**Oráculo:** Minimax(p={parametros['oraculo']})  ")
    A(f"**Adversários:** {', '.join(parametros['adversarios'])}  ")
    A(f"**Partidas por adversário:** {parametros['partidas']}  ")
    A(f"**Workers:** {parametros['workers']}  ")
    A(f"**Tempo total de execução:** {parametros['tempo_total_s']:.0f}s")
    if parametros.get("pasta_retratos"):
        A(f"**Retratos PNG:** `{parametros['pasta_retratos']}`")
    A("")
    A("Diferença em relação ao `RELATORIO_ERROS_CNN.md`: ")
    A("aquele só captura erros TÁTICOS (não fechou caixa grau-3 disponível). ")
    A("ESTE captura também erros ESTRATÉGICOS de meio de jogo, comparando ")
    A("a jogada da CNN com a melhor jogada Minimax em **todas** as posições, ")
    A("não só nas que tinham caixa-pronta.")
    A("")

    # ----------------- Sumário por adversário ----------------------------
    A("## 1. Sumário por adversário")
    A("")
    A("| Adversário | Partidas | Vit. CNN | % Vitórias | Divergências | Fatais | Fatais/partida (média) |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for adv in sorted(sumario):
        s = sumario[adv]
        A(
            f"| {adv} | {s['n_partidas']} | {s['vitorias_cnn']} | "
            f"{s['pct_vitorias']:.1f}% | {s['n_divergencias']} | "
            f"{s['n_fatal']} | {s['fatais_por_partida_media']:.2f} |"
        )
    A("")

    # ----------------- Distribuição de divergências por fase ------------
    A("## 2. Distribuição de divergências por fase de jogo")
    A("")
    A("Limiares de Δ-score (caixas):")
    A(f"- **Inócua:** Δ ≤ {DELTA_INOCUA_MAX} (CNN escolheu jogada quase tão boa)")
    A(f"- **Moderada:** {DELTA_INOCUA_MAX+1} ≤ Δ ≤ {DELTA_MODERADA_MAX}")
    A(f"- **Fatal:** Δ ≥ {DELTA_MODERADA_MAX+1}")
    A("")
    A("Fases (por nº de traços já jogados antes da decisão):")
    A("- **abertura:** 0–9")
    A(f"- **meio:** 10–{LIMITE_MEIO_DE_JOGO-1}  *(decisões de paridade/controle de cadeias)*")
    A(f"- **transicao:** {LIMITE_MEIO_DE_JOGO}–{LIMITE_FIM_DE_JOGO-1}")
    A(f"- **fim:** {LIMITE_FIM_DE_JOGO}–30  *(tática de captura grau-3)*")
    A("")
    A("| Adversário | Fatais (meio) | Fatais (transição) | Fatais (fim) |")
    A("|---|---:|---:|---:|")
    for adv in sorted(sumario):
        s = sumario[adv]
        A(f"| {adv} | {s['n_fatal_meio']} | {s['n_fatal_transicao']} | {s['n_fatal_fim']} |")
    A("")

    # ----------------- Cruzamento perdidas × erro precoce/tardio --------
    A("## 3. Cruzamento — partidas perdidas pela CNN × tipo de erro")
    A("")
    A("Para cada partida perdida pela CNN, classificamos:")
    A(f"- **Fatal precoce:** existe divergência fatal em jogada com ≤ {LIMITE_MEIO_DE_JOGO} traços (= erro estratégico de meio).")
    A(f"- **Fatal apenas tardia:** divergência fatal só aparece com ≥ {LIMITE_MEIO_DE_JOGO+1} traços (= erro tático puro).")
    A("- **Sem fatal:** nenhuma divergência fatal — CNN perdeu por acúmulo de divergências moderadas ou pelo adversário ter jogado bem.")
    A("")
    A("| Adversário | Perdidas | Fatal precoce | Fatal apenas tardia | Sem fatal | % precoce |")
    A("|---|---:|---:|---:|---:|---:|")
    for adv in sorted(sumario):
        s = sumario[adv]
        razao = (
            100 * s["n_perdidas_com_fatal_precoce"] / s["n_perdidas"]
            if s["n_perdidas"] else 0.0
        )
        A(
            f"| {adv} | {s['n_perdidas']} | "
            f"{s['n_perdidas_com_fatal_precoce']} | "
            f"{s['n_perdidas_com_fatal_tardia_apenas']} | "
            f"{s['n_perdidas_sem_fatal']} | {razao:.1f}% |"
        )
    A("")

    # ----------------- Histograma por nº de traços ---------------------
    A("## 4. Histograma de divergências por nº de traços")
    A("")
    A("| Traços antes | Total divergências | Fatais | Moderadas |")
    A("|---:|---:|---:|---:|")
    for n_tracos, total, fatal, mod in _histograma_por_traco(todas_divs):
        A(f"| {n_tracos} | {total} | {fatal} | {mod} |")
    A("")

    # ----------------- Top pares jogada_otima → jogada_cnn -------------
    A("## 5. Top pares 'jogada ótima → jogada CNN' (Δ ≥ 2)")
    A("")
    A("Útil para identificar padrões sistêmicos onde a CNN escolhe a aresta errada.")
    A("")
    A("| Jogada ótima | Jogada CNN | Fase | N |")
    A("|---|---|---|---:|")
    for (otima, cnn, fase), n in _top_pares_divergentes(todas_divs, n=15):
        A(f"| {otima} | {cnn} | {fase} | {n} |")
    A("")

    # ----------------- Exemplos visuais de divergências fatais ---------
    fatais = [d for d in todas_divs if d.classe_delta == "fatal" and d.retrato_path]
    if fatais:
        # Prioriza fatais precoces (meio de jogo) — sinal forte da Categoria B
        fatais_precoces = [d for d in fatais if d.n_tracos_antes <= LIMITE_MEIO_DE_JOGO]
        fatais_outras = [d for d in fatais if d.n_tracos_antes > LIMITE_MEIO_DE_JOGO]
        # Ordena cada grupo por delta desc (mais grave primeiro), depois por nº de traços
        fatais_precoces.sort(key=lambda d: (-d.delta, d.n_tracos_antes))
        fatais_outras.sort(key=lambda d: (-d.delta, d.n_tracos_antes))
        seleção = fatais_precoces[:8] + fatais_outras[:8]
        if seleção:
            A("## 6. Exemplos visuais de divergências fatais")
            A("")
            A(
                "Cada figura tem 2 painéis: à **esquerda** o estado antes da "
                "jogada com a aresta jogada pela CNN destacada em **laranja**; "
                "à **direita** o mesmo estado com a aresta **ótima** segundo o "
                "oráculo destacada em **verde**. Caixas azuis = CNN; vermelhas "
                "= adversário. Pasta-base dos PNGs = `<pasta_retratos>`."
            )
            A("")
            A(
                "Selecionados os 8 piores Δ-score em fase ≤ meio (primeiros) e os 8 "
                "piores em fase ≥ transição (últimos)."
            )
            A("")
            A("| # | Adversário | Partida | Jogada | Traços | Fase | Δ | CNN→Ótima | Retrato |")
            A("|---:|---|---:|---:|---:|---|---:|---|---|")
            for i, d in enumerate(seleção, 1):
                A(
                    f"| {i} | {d.adversario} | {d.partida_idx} | "
                    f"{d.numero_jogada} | {d.n_tracos_antes} | {d.fase} | "
                    f"{d.delta} | {d.jogada_cnn} → {d.jogada_otima} | "
                    f"`{d.retrato_path}` |"
                )
            A("")
            A(
                "Para visualizar, abra `<pasta_retratos>/<caminho do retrato>` "
                "(ex.: `tmp_analise/retratos_divergencia/Minimax_p_5/cnn1_partida0007/jogada015_t12_d6_fatal.png`)."
            )
            A("")
    elif any(d.retrato_path for d in todas_divs):
        A("## 6. Exemplos visuais de divergências fatais")
        A("")
        A("Nenhuma divergência fatal encontrada — caso ideal.")
        A("")

    # ----------------- Cenário e decisão ------------------------------
    A("## 7. Cenário diagnosticado e parecer")
    A("")
    A(f"**Cenário:** {cenario}")
    A("")
    A(parecer)
    A("")
    A("Critérios (alinhados ao PRD `specs/004-melhoria-geracao-dados-cnn/PRD.md`, Seção 2.4):")
    A("- **X1:** < 10% das partidas perdidas têm divergência fatal precoce → Fases A+B+C suficientes; D opcional.")
    A("- **X2:** > 30% das partidas perdidas têm divergência fatal precoce → Fase D obrigatória.")
    A("- **X3:** 10–30% → manter plano completo, calibrar expectativas.")
    A("")
    A("## 8. Próximos passos")
    A("")
    A("1. Revisar este relatório com o usuário antes de iniciar a Fase A.")
    A("2. Registrar a decisão sobre cenário X1/X2/X3 em `docs/historico_decisoes.md`.")
    A(f"3. Caso o cenário seja X2 com sinais novos não previstos no PRD (ex.: feature estrutural específica que aparece nos top pares acima), revisar Seção 6 do PRD antes de começar a geração de dados.")
    A("4. Re-rodar este script após cada fase (B, C, D) e comparar os números — usar como métrica de acompanhamento da Categoria B.")
    A("")

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text("\n".join(linhas), encoding="utf-8")
    print(f"Relatório escrito em: {saida}")


def gerar_csv_divergencias(
    resultados_por_adv: dict[str, list[ResultadoPartida]],
    saida: Path,
) -> None:
    todas = [
        d.chave_csv
        for partidas in resultados_por_adv.values()
        for p in partidas
        for d in p.divergencias
    ]
    if not todas:
        return
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(todas[0].keys()))
        wr.writeheader()
        wr.writerows(todas)
    print(f"CSV escrito em: {saida} ({len(todas)} linhas)")


# ---------------------------------------------------------------------------
# Checkpoints — persistência de blocos por profundidade
# ---------------------------------------------------------------------------

# Versão do schema de checkpoint. Bumpar quando:
#   - Mudar a estrutura de Divergencia ou ResultadoPartida.
#   - Mudar o formato do payload do pickle.
#   - Mudar a chave de assinatura.
# Schema 2 (atual): pickle agora é um dict {"assinatura": ..., "resultados": ...}
# em vez de uma lista pura. Cada bloco carrega sua PRÓPRIA assinatura,
# eliminando a possibilidade de mistura silenciosa de runs com parâmetros
# diferentes (bug detectado no schema 1, onde meta.json era compartilhado).
_CHECKPOINT_SCHEMA = 2


def _chave_assinatura_run(args) -> dict:
    """Conjunto mínimo de parâmetros que DEVEM bater entre runs para um
    checkpoint ser reutilizável. Mudou modelo, tamanho, oráculo, partidas
    ou retratos? O bloco precisa ser refeito."""
    return {
        "schema": _CHECKPOINT_SCHEMA,
        "modelo": args.modelo,
        "tamanho": args.tamanho,
        "oraculo_modo": args.oraculo_modo,
        "oraculo": args.oraculo if args.oraculo_modo == "fixo" else None,
        "partidas": args.partidas,
        "salvar_retratos": str(args.salvar_retratos) if args.salvar_retratos else None,
    }


def _caminho_pickle_checkpoint(pasta: Path, prof_adv: int) -> Path:
    return pasta / f"resultados_p{prof_adv:02d}.pkl"


def _caminho_meta_checkpoint(pasta: Path) -> Path:
    """Apenas índice informativo (não autoritativo). A assinatura efetiva
    vive dentro de cada pickle de bloco."""
    return pasta / "meta.json"


def _carregar_checkpoint_se_compativel(
    pasta: Path, prof_adv: int, assinatura_atual: dict,
) -> list[ResultadoPartida] | None:
    """Retorna a lista de ResultadoPartida do bloco se houver checkpoint
    válido e compatível com `assinatura_atual`; senão retorna None.
    A assinatura é validada DENTRO de cada pickle (schema 2)."""
    pkl = _caminho_pickle_checkpoint(pasta, prof_adv)
    if not pkl.exists():
        return None
    try:
        with pkl.open("rb") as f:
            payload = pickle.load(f)
    except Exception as e:
        print(
            f"  [checkpoint] falha lendo {pkl.name} ({e}); bloco será recoletado",
            flush=True,
        )
        return None
    # Schema 2: dict com assinatura + resultados. Schema 1 (lista pura) é
    # rejeitado por ser inseguro (não carrega assinatura no próprio arquivo).
    if not isinstance(payload, dict) or "assinatura" not in payload \
            or "resultados" not in payload:
        print(
            f"  [checkpoint] {pkl.name} em formato antigo (schema 1) ou "
            f"inesperado; bloco será recoletado",
            flush=True,
        )
        return None
    if payload["assinatura"] != assinatura_atual:
        print(
            f"  [checkpoint] assinatura do checkpoint p={prof_adv} difere da run "
            f"atual; bloco será recoletado",
            flush=True,
        )
        return None
    dados = payload["resultados"]
    if not isinstance(dados, list):
        print(
            f"  [checkpoint] {pkl.name} com 'resultados' em formato inesperado; "
            f"bloco será recoletado",
            flush=True,
        )
        return None
    return dados


def _salvar_checkpoint(
    pasta: Path,
    prof_adv: int,
    resultados: list[ResultadoPartida],
    assinatura: dict,
) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    pkl = _caminho_pickle_checkpoint(pasta, prof_adv)
    # Escrita atômica: grava em .tmp e renomeia, evita deixar pickle truncado
    # se a máquina cair durante o save.
    payload = {
        "assinatura": assinatura,    # cada bloco carrega sua própria assinatura
        "resultados": resultados,
    }
    tmp = pkl.with_suffix(pkl.suffix + ".tmp")
    with tmp.open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, pkl)
    # meta.json é apenas índice informativo (último bloco salvo + timestamp);
    # a fonte da verdade da assinatura é o próprio pickle de cada bloco.
    meta = _caminho_meta_checkpoint(pasta)
    meta_payload = {
        "assinatura": assinatura,
        "ultimo_bloco_salvo": prof_adv,
        "ts_unix": time.time(),
    }
    meta_tmp = meta.with_suffix(meta.suffix + ".tmp")
    meta_tmp.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")
    os.replace(meta_tmp, meta)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Análise de divergência estratégica CNN vs Minimax(p=oraculo)."
    )
    ap.add_argument("--modelo", required=True, help="Caminho para o .tflite")
    ap.add_argument("--tamanho", default="pequeno", choices=["pequeno", "medio", "grande"])
    ap.add_argument("--partidas", type=int, default=200,
                    help="Partidas por profundidade adversária (metade CNN-primeiro, metade CNN-segundo)")
    ap.add_argument("--profundidades", type=int, nargs="+", default=[3, 5, 6],
                    help="Profundidades dos Minimax adversários. p=1 foi "
                         "descartado em 2026-05-06 (ver historico_decisoes.md): "
                         "sua janela de visão (0 plies do oponente) torna o "
                         "tie-break aleatório dominante e gera ruído.")
    ap.add_argument("--oraculo", type=int, default=9,
                    help="Profundidade do oráculo Minimax (modo fixo). Default 9.")
    ap.add_argument("--oraculo-modo", choices=["fixo", "adaptativo"], default="adaptativo",
                    help="`fixo` usa --oraculo (mesma profundidade em todo o jogo). "
                         "`adaptativo` (padrão) usa p=5 quando livres≥26, p=7 quando "
                         "livres 18-25, p=9 quando livres ≤17. Reduz drasticamente o "
                         "tempo de execução sem comprometer detecção de divergências "
                         "fatais (que ocorrem majoritariamente no meio crítico, onde "
                         "p=9 é mantido).")
    ap.add_argument("--workers", type=int, default=4,
                    help="Processos-worker paralelos")
    ap.add_argument("--saida-md", type=Path,
                    default=_RAIZ / "tmp_analise" / "RELATORIO_DIVERGENCIA_ESTRATEGICA.md")
    ap.add_argument("--saida-csv", type=Path,
                    default=_RAIZ / "tmp_analise" / "divergencias_estrategicas.csv")
    ap.add_argument("--salvar-retratos", type=Path, default=None,
                    help="Pasta para salvar 1 PNG por jogada da CNN. "
                         "Estrutura: <pasta>/<adversario>/<cnn1|cnn2>_partidaNNNN/jogadaNNN_*.png. "
                         "Sem este flag, retratos não são gerados (mais rápido).")
    ap.add_argument("--pasta-checkpoints", type=Path,
                    default=_RAIZ / "tmp_analise" / "checkpoints_divergencia",
                    help="Pasta onde cada bloco (profundidade) é salvo em "
                         "pickle ao concluir. Permite retomar runs interrompidos. "
                         "Default: tmp_analise/checkpoints_divergencia/")
    ap.add_argument("--retomar", action="store_true",
                    help="Se ativo, lê checkpoints existentes em --pasta-checkpoints "
                         "e PULA as profundidades já coletadas (validando que "
                         "modelo, tamanho, oráculo e partidas batem).")
    ap.add_argument("--so-relatorio", action="store_true",
                    help="Não coleta nada: apenas lê checkpoints existentes e gera "
                         "MD/CSV. Útil para regerar o relatório com checkpoints já feitos.")
    args = ap.parse_args()

    # Garante que stdout flushe linha-a-linha (mesmo redirecionado para arquivo).
    try:
        sys.stdout.reconfigure(line_buffering=True)  # Python 3.7+
    except AttributeError:
        pass

    # Resolve modo do oráculo (int fixo ou tabela adaptativa)
    if args.oraculo_modo == "adaptativo":
        prof_oraculo_efetiva = _TABELA_ORACULO_ADAPTATIVO
        descr_oraculo = (
            "ADAPTATIVO: livres >=26 -> p=5 | 18-25 -> p=7 | <=17 -> p=9"
        )
    else:
        prof_oraculo_efetiva = args.oraculo
        descr_oraculo = f"FIXO Minimax(p={args.oraculo})"

    print("=" * 72, flush=True)
    print("ANÁLISE DE DIVERGÊNCIA ESTRATÉGICA", flush=True)
    print("=" * 72, flush=True)
    print(f"Modelo:        {args.modelo}", flush=True)
    print(f"Tamanho:       {args.tamanho}", flush=True)
    print(f"Adversários:   {[f'p={p}' for p in args.profundidades]}", flush=True)
    print(f"Oráculo:       {descr_oraculo}", flush=True)
    print(f"Partidas/prof: {args.partidas}", flush=True)
    print(f"Workers:       {args.workers}", flush=True)
    if args.salvar_retratos:
        print(f"Retratos PNG:  {args.salvar_retratos}", flush=True)
    else:
        print("Retratos PNG:  desativados (use --salvar-retratos PASTA para ativar)", flush=True)
    print(flush=True)

    if args.salvar_retratos is not None:
        args.salvar_retratos.mkdir(parents=True, exist_ok=True)

    args.pasta_checkpoints.mkdir(parents=True, exist_ok=True)
    assinatura = _chave_assinatura_run(args)
    print(f"Checkpoints:   {args.pasta_checkpoints}", flush=True)
    if args.retomar:
        print("               (modo --retomar ativo: blocos compatíveis serão pulados)", flush=True)
    if args.so_relatorio:
        print("               (modo --so-relatorio ativo: nada será coletado)", flush=True)
    print(flush=True)

    t_inicio = time.perf_counter()
    resultados_por_adv: dict[str, list[ResultadoPartida]] = {}
    n_profs = len(args.profundidades)
    for idx_prof, prof in enumerate(args.profundidades, 1):
        nome_adv = f"Minimax(p={prof})"

        # 1. Tenta carregar checkpoint
        if args.retomar or args.so_relatorio:
            cached = _carregar_checkpoint_se_compativel(
                args.pasta_checkpoints, prof, assinatura,
            )
            if cached is not None:
                resultados_por_adv[nome_adv] = cached
                print(
                    f"--- [{idx_prof}/{n_profs}] {nome_adv}: checkpoint carregado "
                    f"({len(cached)} partidas, sem coletar)",
                    flush=True,
                )
                continue
            elif args.so_relatorio:
                print(
                    f"--- [{idx_prof}/{n_profs}] {nome_adv}: SEM checkpoint compatível e "
                    f"--so-relatorio ativo. Bloco será omitido do relatório.",
                    flush=True,
                )
                continue

        # 2. Coleta normal
        print(
            f"--- [{idx_prof}/{n_profs}] Coletando {nome_adv} "
            f"({args.partidas} partidas) ---",
            flush=True,
        )
        resultados_por_adv[nome_adv] = coletar_partidas(
            caminho_modelo=args.modelo,
            tamanho=args.tamanho,
            prof_adv=prof,
            prof_oraculo=prof_oraculo_efetiva,
            n_partidas=args.partidas,
            workers=args.workers,
            pasta_retratos=args.salvar_retratos,
        )

        # 3. Salva checkpoint do bloco (atômico)
        try:
            _salvar_checkpoint(
                args.pasta_checkpoints, prof,
                resultados_por_adv[nome_adv], assinatura,
            )
            print(
                f"  [checkpoint] gravado: {_caminho_pickle_checkpoint(args.pasta_checkpoints, prof).name}",
                flush=True,
            )
        except Exception as e:
            print(
                f"  [checkpoint] AVISO: falha ao gravar checkpoint p={prof}: {e}",
                flush=True,
            )

        # 4. Resumo parcial pós-bloco
        partidas_ate_aqui = sum(len(v) for v in resultados_por_adv.values())
        decorrido = time.perf_counter() - t_inicio
        print(
            f"--- [{idx_prof}/{n_profs}] {nome_adv} concluído. "
            f"Total acumulado: {partidas_ate_aqui} partidas em {decorrido:.0f}s ---",
            flush=True,
        )
        print(flush=True)
    tempo_total = time.perf_counter() - t_inicio
    print(flush=True)
    print(f"Coleta concluída em {tempo_total:.0f}s", flush=True)
    print(flush=True)

    if not resultados_por_adv:
        print(
            "ERRO: nenhuma profundidade foi coletada nem carregada de checkpoint. "
            "Nada para relatar.",
            flush=True,
        )
        return

    sumario = _sumarizar_por_adversario(resultados_por_adv)
    cenario, parecer = _classificar_cenario(sumario)

    def _print_safe(s: str) -> None:
        """Imprime no console substituindo chars não-encodáveis (Windows cp1252)."""
        enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        try:
            print(s)
        except UnicodeEncodeError:
            print(s.encode(enc, errors="replace").decode(enc, errors="replace"))

    _print_safe(f"Cenário diagnosticado: {cenario}")
    _print_safe(parecer)
    print()

    parametros = {
        "modelo": args.modelo,
        "tamanho": args.tamanho,
        "oraculo": args.oraculo,
        "adversarios": [f"p={p}" for p in args.profundidades],
        "partidas": args.partidas,
        "workers": args.workers,
        "tempo_total_s": tempo_total,
        "pasta_retratos": str(args.salvar_retratos) if args.salvar_retratos else None,
    }
    gerar_relatorio_md(
        resultados_por_adv, sumario, cenario, parecer, parametros, args.saida_md,
    )
    gerar_csv_divergencias(resultados_por_adv, args.saida_csv)


if __name__ == "__main__":
    main()

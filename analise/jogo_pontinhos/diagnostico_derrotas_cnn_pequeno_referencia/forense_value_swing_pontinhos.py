"""Forense de value-swing — Pilares 2 e 3.

Para cada lance da REFERÊNCIA numa partida perdida, compara o valor Minimax da
posição (sob jogo ótimo) com o valor do lance que a referência de fato jogou.

Convenção de valor (igual ao `minimax_pontinhos`): o jogador a mover é tratado
como maximizador (+1); o score é o **diferencial futuro de caixas**
(referência − adversário) sob jogo ótimo de ambos a partir daquela posição. O
diferencial FINAL é `placar_atual + score_futuro`.

Definições:
- `regret` = max(scores) − score(lance_jogado)  ≥ 0  (perda em caixas vs o ótimo).
- `valor_otimo` = placar_atual_ref + max(scores)        (melhor desfecho ainda possível).
- `valor_jogado` = placar_atual_ref + score(lance_jogado) (desfecho após o lance, sob jogo ótimo posterior).
- `decisivo` = a referência tinha posição não-perdida (`valor_otimo ≥ 0`) e o
  próprio lance a jogou fora (`valor_jogado < 0`). É a transição que separa
  **sacrifício bom** (valor nunca fica negativo) de **erro real**.

Só roda nas partidas FILTRADAS (derrotas) — é a etapa cara do funil.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas
from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import (
    _para_dominio_dataset,
)
from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import (
    extrair_canais,
    extrair_stats_cadeias,
)
from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.adversarios_pontinhos import (
    classificar_traco,
    particionar_lances,
    qtd_tracos_jogados,
)
from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.arena_pontinhos import (
    ResultadoPartida,
)

# Bins de fase iguais aos do notebook de treino.
_FASE_BINS = [12, 18, 24, 29]
FASE_NOMES = {
    0: "Abertura (0-11)", 1: "1a Metade (12-17)", 2: "2a Metade (18-23)",
    3: "Fase Quente (24-28)", 4: "Final (29-31)",
}


def _fase_de(t: int) -> int:
    return int(np.digitize([t], bins=_FASE_BINS)[0])


@dataclass
class ErroDecisivo:
    """Um lance da referência com diagnóstico de value-swing."""
    seed: int
    numero_jogada: int
    qtd_tracos: int
    fase: int
    fase_nome: str
    traco_cnn: str
    traco_minimax: str
    classificacao_traco_cnn: str      # captura | doacao | segura
    regret: int
    valor_otimo: int
    valor_jogado: int
    decisivo: bool
    qtd_cadeias_longas: int
    tamanho_max_cadeia_longa: int
    havia_lance_safe: bool
    matriz_antes: np.ndarray          # não serializa em tabela; útil p/ visualização

    def para_linha(self) -> dict:
        """Dicionário sem a matriz (para DataFrame/tabela)."""
        d = asdict(self)
        d.pop("matriz_antes", None)
        return d


def _reconstruir_estado(matriz_antes: np.ndarray, tamanho: str) -> EstadoTabuleiro:
    est = EstadoTabuleiro.de_tamanho(tamanho)
    est.matriz = matriz_antes.copy()
    return est


def analisar_partida(
    partida: ResultadoPartida,
    profundidade_forense: int,
    tamanho: str = "pequeno",
    exigir_terminal: bool = True,
) -> list[ErroDecisivo]:
    """Roda a forense de value-swing nos lances da referência.

    Por padrão (`exigir_terminal=True`) só avalia lances onde a busca Minimax
    **alcança o fim do jogo** — isto é, lances_restantes <= profundidade. Só aí
    o valor é EXATO (a `avaliar` do Minimax só é válida no terminal; em corte de
    profundidade ela devolve um diferencial parcial, sem sentido na abertura).
    Esse recorte também é o BARATO: poucos lances restantes => árvore pequena.
    Felizmente é onde moram os erros decisivos (transição p/ o endgame).
    """
    erros: list[ErroDecisivo] = []

    for lance in partida.lances_da_referencia():
        estado = _reconstruir_estado(lance.matriz_antes, tamanho)

        # Recorte de exatidão+custo: pula posições onde a busca não chega ao
        # terminal dentro da profundidade (tipicamente a abertura).
        if exigir_terminal and len(estado.tracos_disponiveis()) > profundidade_forense:
            continue

        # Placar da referência ANTES do lance (caixas já fechadas).
        interior = lance.matriz_antes[1::2, 1::2]
        placar_ref = int((interior == partida.ref_valor_matriz).sum())
        placar_adv = int((interior == -partida.ref_valor_matriz).sum())
        diff_atual = placar_ref - placar_adv

        # Q-values de TODOS os lances (referência = jogador maximizador).
        scores = _scores_de_todas_jogadas(estado, profundidade_forense)
        if lance.traco not in scores:
            continue  # segurança: lance fora do conjunto (não deve ocorrer)
        score_otimo = max(scores.values())
        score_jogado = scores[lance.traco]
        regret = score_otimo - score_jogado

        valor_otimo = diff_atual + score_otimo
        valor_jogado = diff_atual + score_jogado
        decisivo = (valor_otimo >= 0) and (valor_jogado < 0)

        # Só guardamos lances subótimos (regret > 0). Lances ótimos não são erro.
        if regret <= 0:
            continue

        traco_mm = max(scores, key=lambda t: scores[t])
        cls = classificar_traco(estado, lance.traco)
        _, seguras, _ = particionar_lances(estado)

        mat_ds = _para_dominio_dataset(lance.matriz_antes)
        try:
            qtd_cad, _tot, tam_max = extrair_stats_cadeias(mat_ds)
        except Exception:
            qtd_cad, tam_max = -1, -1

        t = qtd_tracos_jogados(estado)
        fase = _fase_de(t)

        erros.append(ErroDecisivo(
            seed=partida.seed,
            numero_jogada=lance.numero_jogada,
            qtd_tracos=t,
            fase=fase,
            fase_nome=FASE_NOMES[fase],
            traco_cnn=lance.traco,
            traco_minimax=traco_mm,
            classificacao_traco_cnn=cls,
            regret=int(regret),
            valor_otimo=int(valor_otimo),
            valor_jogado=int(valor_jogado),
            decisivo=bool(decisivo),
            qtd_cadeias_longas=int(qtd_cad),
            tamanho_max_cadeia_longa=int(tam_max),
            havia_lance_safe=bool(len(seguras) > 0),
            matriz_antes=lance.matriz_antes,
        ))

    return erros


def analisar_lote(
    partidas: list[ResultadoPartida],
    profundidade_forense: int,
    tamanho: str = "pequeno",
    progresso_callback=None,
) -> list[ErroDecisivo]:
    """Roda a forense em todas as partidas perdidas filtradas."""
    todos: list[ErroDecisivo] = []
    for i, p in enumerate(partidas):
        todos.extend(analisar_partida(p, profundidade_forense, tamanho))
        if progresso_callback is not None:
            progresso_callback(i + 1, len(partidas), len(todos))
    return todos

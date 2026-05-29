"""População de adversários e classificação de lances — Pilar 1 (Diversidade).

Sem aleatoriedade, Minimax determinístico × CNN argmax produz uma única partida
repetida. Este módulo fornece:

- `classificar_traco`: rotula um lance como 'captura', 'doacao' ou 'segura'.
- `agente_minimax_descuidado`: Minimax que, na abertura/1ª metade, com
  probabilidade ε, **doa** uma caixa (lance unsafe) mesmo havendo lance seguro —
  imita o humano descuidado, que é justamente o cenário onde a CNN perde.
- `agente_aleatorio`: baseline totalmente aleatório (caso extremo).
- `aplicar_abertura_aleatoria`: espalha as posições iniciais com lances seguros.

Reaproveita a lógica de jogo de `gerador_dados/jogo_pontinhos`.
"""
from __future__ import annotations

import random
from typing import Literal

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    todos_labels_canonicos,
)
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada
from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import (
    _localizar_caixas_prontas,
)

ClasseTraco = Literal["captura", "doacao", "segura"]


def qtd_tracos_jogados(estado: EstadoTabuleiro) -> int:
    """Número de arestas já preenchidas (= índice de fase do jogo, t)."""
    total = len(todos_labels_canonicos(estado.linhas, estado.colunas))
    return total - len(estado.tracos_disponiveis())


def classificar_traco(estado: EstadoTabuleiro, traco: str) -> ClasseTraco:
    """Classifica um lance pelo seu efeito imediato, sem alterar o estado.

    - 'captura': fecha ao menos uma caixa (o jogador mantém o turno).
    - 'doacao' : não fecha, mas cria uma caixa de 3 lados (presente ao adversário).
    - 'segura' : não fecha nem cria caixa de 3 lados.
    """
    prontas_antes = len(_localizar_caixas_prontas(estado.matriz))
    fechadas = estado.aplicar_traco(traco, 1)
    prontas_depois = len(_localizar_caixas_prontas(estado.matriz))
    estado.desfazer_traco(traco)
    if fechadas > 0:
        return "captura"
    if prontas_depois > prontas_antes:
        return "doacao"
    return "segura"


def particionar_lances(
    estado: EstadoTabuleiro,
) -> tuple[list[str], list[str], list[str]]:
    """Devolve (capturas, seguras, doacoes) dos lances disponíveis."""
    capturas, seguras, doacoes = [], [], []
    for t in estado.tracos_disponiveis():
        cls = classificar_traco(estado, t)
        if cls == "captura":
            capturas.append(t)
        elif cls == "segura":
            seguras.append(t)
        else:
            doacoes.append(t)
    return capturas, seguras, doacoes


def agente_minimax_descuidado(
    profundidade: int,
    eps_descuido: float = 0.2,
    t_max_descuido: int = 17,
    rng: random.Random | None = None,
):
    """Agente Minimax que ocasionalmente doa caixas na abertura/1ª metade.

    Em t <= `t_max_descuido`, com probabilidade `eps_descuido`, se existir ao
    mesmo tempo um lance **seguro** (poderia não doar) e um lance de **doação**,
    joga a doação aleatória — manufaturando o erro humano típico. Fora disso,
    joga o Minimax ótimo na `profundidade` dada.

    Mantém o `__name__` informativo para os relatórios.

    `rng` default = módulo `random` global. Como a partida re-semeia
    `random.seed(seed)` no início, as escolhas descuidadas ficam
    **determinísticas por seed** — pré-requisito para retomada reproduzível.
    """
    _rng = rng or random

    def agente(estado: EstadoTabuleiro) -> str:
        if qtd_tracos_jogados(estado) <= t_max_descuido and _rng.random() < eps_descuido:
            capturas, seguras, doacoes = particionar_lances(estado)
            # Descuido só faz sentido quando havia alternativa segura: doar
            # tendo lance seguro é exatamente o "presente" que o humano dá.
            if seguras and doacoes:
                return _rng.choice(doacoes)
        return melhor_jogada(estado, profundidade)

    pct = int(eps_descuido * 100)
    agente.__name__ = f"MinimaxDescuidado(p={profundidade}, eps={pct}%, t<={t_max_descuido})"
    return agente


def agente_aleatorio(rng: random.Random | None = None):
    """Baseline: joga um lance legal qualquer (caso extremo de adversário fraco)."""
    _rng = rng or random.Random()

    def agente(estado: EstadoTabuleiro) -> str:
        return _rng.choice(estado.tracos_disponiveis())

    agente.__name__ = "Aleatorio"
    return agente


def aplicar_abertura_aleatoria(
    estado: EstadoTabuleiro,
    k: int,
    turno_id_inicial: int,
    valor_matriz: dict[int, int],
    rng: random.Random,
) -> int:
    """Joga `k` lances **seguros** aleatórios para espalhar a posição inicial.

    Lances seguros não fecham caixas, então o turno alterna a cada lance. Se
    faltarem lances seguros, para antes de `k`. Retorna o `turno_id` resultante.
    """
    turno_id = turno_id_inicial
    for _ in range(k):
        _, seguras, _ = particionar_lances(estado)
        if not seguras:
            break
        traco = rng.choice(seguras)
        estado.aplicar_traco(traco, valor_matriz[turno_id])
        turno_id = 3 - turno_id  # lance seguro nunca fecha → sempre alterna
    return turno_id

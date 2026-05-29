"""Partida instrumentada e funil de coleta de derrotas — Pilares 4 e 2.

`jogar_partida_instrumentada` registra a **trajetória completa**: a cada lance,
guarda a matriz ANTES, o traço jogado e de quem era a vez. Isso é o insumo da
forense de value-swing (que só roda nas partidas filtradas).

`coletar_derrotas` é o funil: joga em massa (barato) e devolve só as partidas em
que o agente de referência perdeu (ou empatou — opcional).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.adversarios_pontinhos import (
    aplicar_abertura_aleatoria,
)

# Resultado da referência na partida
VITORIA, EMPATE, DERROTA = "vitoria", "empate", "derrota"


@dataclass
class LanceTrajetoria:
    """Um lance gravado da partida."""
    numero_jogada: int
    turno_id: int                 # 1 ou 2 (lógico)
    eh_referencia: bool           # True se quem jogou foi a referência
    matriz_antes: np.ndarray      # estado ANTES do lance (cópia)
    traco: str
    fechadas: int


@dataclass
class ResultadoPartida:
    """Resultado completo de uma partida instrumentada."""
    resultado_ref: str            # VITORIA | EMPATE | DERROTA (da perspectiva da referência)
    placar_ref: int
    placar_adv: int
    ref_eh_jogador1: bool
    ref_valor_matriz: int         # +1 se ref jogou como jogador 1, -1 se jogador 2
    seed: int
    trajetoria: list[LanceTrajetoria] = field(default_factory=list)

    def lances_da_referencia(self) -> list[LanceTrajetoria]:
        return [l for l in self.trajetoria if l.eh_referencia]


def jogar_partida_instrumentada(
    agente_ref,
    agente_adv,
    ref_eh_jogador1: bool,
    tamanho: str = "pequeno",
    seed: int = 0,
    lances_abertura_aleatorios: int = 0,
) -> ResultadoPartida:
    """Joga uma partida gravando a trajetória completa.

    `agente_ref` é o modelo sob diagnóstico; `agente_adv` é o adversário. A
    referência joga como jogador 1 ou 2 conforme `ref_eh_jogador1` (alternamos
    nas coletas para neutralizar a vantagem do primeiro a jogar).
    """
    # Semeia o random GLOBAL pelo seed da partida: torna determinísticos tanto o
    # desempate do Minimax quanto as escolhas do adversário descuidado e a
    # abertura aleatória — pré-requisito para retomada reproduzível.
    random.seed(seed)

    estado = EstadoTabuleiro.de_tamanho(tamanho)
    valor_matriz = {1: 1, 2: -1}
    ref_valor = 1 if ref_eh_jogador1 else -1
    ref_turno = 1 if ref_eh_jogador1 else 2

    turno_id = 1
    if lances_abertura_aleatorios > 0:
        turno_id = aplicar_abertura_aleatoria(
            estado, lances_abertura_aleatorios, turno_id, valor_matriz, random
        )

    trajetoria: list[LanceTrajetoria] = []
    numero = 0
    while not estado.esta_terminal():
        eh_ref = (turno_id == ref_turno)
        agente = agente_ref if eh_ref else agente_adv
        numero += 1

        matriz_antes = estado.matriz.copy()
        traco = agente(estado)
        fechadas = estado.aplicar_traco(traco, valor_matriz[turno_id])

        trajetoria.append(LanceTrajetoria(
            numero_jogada=numero,
            turno_id=turno_id,
            eh_referencia=eh_ref,
            matriz_antes=matriz_antes,
            traco=traco,
            fechadas=fechadas,
        ))

        if fechadas == 0:
            turno_id = 3 - turno_id

    interior = estado.matriz[1::2, 1::2]
    placar_ref = int((interior == ref_valor).sum())
    placar_adv = int((interior == -ref_valor).sum())
    if placar_ref > placar_adv:
        resultado = VITORIA
    elif placar_ref < placar_adv:
        resultado = DERROTA
    else:
        resultado = EMPATE

    return ResultadoPartida(
        resultado_ref=resultado,
        placar_ref=placar_ref,
        placar_adv=placar_adv,
        ref_eh_jogador1=ref_eh_jogador1,
        ref_valor_matriz=ref_valor,
        seed=seed,
        trajetoria=trajetoria,
    )


def coletar_derrotas(
    agente_ref,
    agente_adv,
    n_partidas: int,
    tamanho: str = "pequeno",
    lances_abertura_aleatorios: int = 0,
    incluir_empates: bool = False,
    seed_base: int = 0,
    progresso_callback=None,
) -> tuple[list[ResultadoPartida], dict]:
    """Funil etapas 1–2: joga `n_partidas` e devolve as derrotas da referência.

    Alterna a referência entre jogador 1 e 2 (metade/metade) para neutralizar a
    vantagem do primeiro lance. Retorna (lista_de_derrotas, estatisticas).
    """
    derrotas: list[ResultadoPartida] = []
    contagem = {VITORIA: 0, EMPATE: 0, DERROTA: 0}

    for i in range(n_partidas):
        ref_p1 = (i % 2 == 0)
        r = jogar_partida_instrumentada(
            agente_ref, agente_adv,
            ref_eh_jogador1=ref_p1,
            tamanho=tamanho,
            seed=seed_base + i,
            lances_abertura_aleatorios=lances_abertura_aleatorios,
        )
        contagem[r.resultado_ref] += 1
        if r.resultado_ref == DERROTA or (incluir_empates and r.resultado_ref == EMPATE):
            derrotas.append(r)
        if progresso_callback is not None:
            progresso_callback(i + 1, n_partidas, contagem)

    stats = {
        "n_partidas": n_partidas,
        "vitorias": contagem[VITORIA],
        "empates": contagem[EMPATE],
        "derrotas": contagem[DERROTA],
        "pct_vitorias": contagem[VITORIA] / n_partidas * 100 if n_partidas else 0.0,
        "pct_derrotas": contagem[DERROTA] / n_partidas * 100 if n_partidas else 0.0,
        "coletadas": len(derrotas),
    }
    return derrotas, stats

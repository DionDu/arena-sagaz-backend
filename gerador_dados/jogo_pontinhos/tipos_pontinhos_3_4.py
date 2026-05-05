"""Tipos de dados do agente híbrido `ia-pontinhos-3-4`.

Centraliza enumerações, dataclasses de configuração/resultado e helpers
compartilhados entre `ia_pontinhos_3_4`, `correntes_pontinhos_3_4` e
`cnn_inferencia_pontinhos_3_4`.

Fonte da verdade: `specs/003-jogador-hibrido/data-model.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal
from uuid import UUID

import numpy as np

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro


# =============================================================================
# Enumerações
# =============================================================================


class NivelDificuldade(str, Enum):
    FACIL = "facil"
    MEDIO = "medio"
    DIFICIL = "dificil"
    EXPERT = "expert"


class CodigoSituacao(str, Enum):
    CAPTURA_SEGURA = "captura_segura"
    FINAL_CORRENTE_LONGA = "final_corrente_longa"
    FINAL_CICLO = "final_ciclo"
    TATICA = "tatica"


class CodigoAcao(str, Enum):
    CAPTURA_GULOSA = "captura_gulosa"
    CAPTURA_COMPLETA = "captura_completa"
    SACRIFICIO_DOUBLE_CROSS = "sacrificio_double_cross"
    CNN_E_MINIMAX = "cnn_e_minimax"
    CNN_TIMEOUT = "cnn_timeout"
    ALEATORIA_TIMEOUT = "aleatoria_timeout"


# =============================================================================
# Mapeamento de defaults por nível de dificuldade
# =============================================================================


MAPEAMENTO_NIVEIS: dict[NivelDificuldade, dict[str, object]] = {
    NivelDificuldade.FACIL: {
        "caminho_modelo_cnn": "modelos/pontinhos_pequeno_profundidade_6.tflite",
        "profundidade_minimax": 1,
        "percentual_aleatoriedade": 0.30,
    },
    NivelDificuldade.MEDIO: {
        "caminho_modelo_cnn": "modelos/pontinhos_pequeno_profundidade_7.tflite",
        "profundidade_minimax": 2,
        "percentual_aleatoriedade": 0.15,
    },
    NivelDificuldade.DIFICIL: {
        "caminho_modelo_cnn": "modelos/pontinhos_pequeno_profundidade_9.tflite",
        "profundidade_minimax": 3,
        "percentual_aleatoriedade": 0.05,
    },
    NivelDificuldade.EXPERT: {
        "caminho_modelo_cnn": "modelos/pontinhos_pequeno_profundidade_11.tflite",
        "profundidade_minimax": 3,
        "percentual_aleatoriedade": 0.00,
    },
}


# =============================================================================
# ConfiguracaoAgente
# =============================================================================


@dataclass
class ConfiguracaoAgente:
    nivel_dificuldade: NivelDificuldade = NivelDificuldade.DIFICIL
    caminho_modelo_cnn: str | None = None
    profundidade_minimax: int | None = None
    percentual_aleatoriedade: float | None = None
    seed_aleatoriedade: int | None = None
    verbose: bool = False

    def __post_init__(self) -> None:
        defaults = MAPEAMENTO_NIVEIS[self.nivel_dificuldade]
        if self.caminho_modelo_cnn is None:
            self.caminho_modelo_cnn = defaults["caminho_modelo_cnn"]  # type: ignore[assignment]
        if self.profundidade_minimax is None:
            self.profundidade_minimax = defaults["profundidade_minimax"]  # type: ignore[assignment]
        if self.percentual_aleatoriedade is None:
            self.percentual_aleatoriedade = defaults["percentual_aleatoriedade"]  # type: ignore[assignment]

        if self.profundidade_minimax < 1:
            raise ValueError(
                f"profundidade_minimax deve ser >= 1, recebido {self.profundidade_minimax}"
            )
        if not (0.0 <= self.percentual_aleatoriedade <= 1.0):
            raise ValueError(
                "percentual_aleatoriedade fora de [0.0, 1.0], recebido "
                f"{self.percentual_aleatoriedade}"
            )


# =============================================================================
# MetadadosTurno
# =============================================================================


@dataclass(frozen=True)
class MetadadosTurno:
    id_partida: UUID
    id_jogada: UUID
    id_jogador: UUID
    nu_jogador: int
    ts_jogada: str
    nu_timer_ms: int | None = None

    def __post_init__(self) -> None:
        if self.nu_jogador not in (1, -1):
            raise ValueError(
                f"nu_jogador deve ser 1 ou -1, recebido {self.nu_jogador}"
            )
        if self.nu_timer_ms is not None and self.nu_timer_ms < 0:
            raise ValueError(
                f"nu_timer_ms deve ser >= 0 ou None, recebido {self.nu_timer_ms}"
            )


# =============================================================================
# ResultadoJogada
# =============================================================================


@dataclass
class ResultadoJogada:
    id_partida: UUID
    id_jogada: UUID
    id_jogador: UUID
    nu_jogador: int
    co_situacao: CodigoSituacao
    co_acao: CodigoAcao
    co_aresta: str
    ar_tabuleiro_antes: np.ndarray
    ar_tabuleiro_apos: np.ndarray
    nu_placar_jogador_antes: int
    nu_placar_jogador_apos: int
    ts_jogada: str
    nu_timer_ms: int | None
    nu_tempo_calculo_ms: int

    nu_profundidade_minimax: int | None = None
    ar_score_minimax: np.ndarray | None = None
    ar_probabilidade_cnn: np.ndarray | None = None
    js_extra: dict | None = None


# =============================================================================
# Estrutura (corrente / ciclo / ramificada / isolada)
# =============================================================================


@dataclass(frozen=True)
class Estrutura:
    tipo: Literal["corrente", "ciclo", "ramificada", "isolada"]
    caixas: tuple[tuple[int, int], ...]
    extremidades: tuple[tuple[int, int], ...] = field(default=())

    @property
    def tamanho(self) -> int:
        return len(self.caixas)

    @property
    def eh_corrente_longa(self) -> bool:
        return self.tipo == "corrente" and self.tamanho >= 3


# =============================================================================
# Helpers públicos
# =============================================================================


def array_31_com_nan() -> np.ndarray:
    """Sentinela canônica para arrays opcionais do `ResultadoJogada` (FR-038)."""
    return np.full((31,), np.nan, dtype=np.float32)


def contar_caixas_jogador(estado: EstadoTabuleiro, jogador: int) -> int:
    """Conta caixas fechadas atribuídas ao jogador (+1 ou -1).

    Workaround para o defeito conhecido em `EstadoTabuleiro.caixas_fechadas_por`,
    que não filtra por jogador.
    """
    contagem = 0
    matriz = estado.matriz
    for box_r in range(1, matriz.shape[0], 2):
        for box_c in range(1, matriz.shape[1], 2):
            if matriz[box_r, box_c] == jogador:
                contagem += 1
    return contagem

"""Testes de integração: auto-jogo `ia-pontinhos-3-4` (T043).

Cenários:
(a) auto-jogo agente vs agente — N partidas, todas terminam com 31 arestas
    preenchidas e 12 caixas atribuídas, 0 jogadas inválidas (SC-003, SC-007).
(c) timer apertado — taxa de jogadas P1 (não-timeout) é aceitável.

Exigem TFLite real (modelo `.tflite` em `modelos/`). Saltam se ausente.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from gerador_dados.jogo_pontinhos.cnn_inferencia_pontinhos_3_4 import (
    _limpar_cache_interpretadores,
)
from gerador_dados.jogo_pontinhos.ia_pontinhos_3_4 import escolher_jogada
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import (
    CodigoAcao,
    ConfiguracaoAgente,
    MetadadosTurno,
    NivelDificuldade,
    contar_caixas_jogador,
)


CAMINHO_MODELO = "modelos/pontinhos_pequeno_profundidade_9.tflite"
pytestmark = pytest.mark.skipif(
    not Path(CAMINHO_MODELO).exists(), reason="modelo TFLite ausente"
)


def _md(nu_jogador: int, nu_timer_ms: int | None = None) -> MetadadosTurno:
    return MetadadosTurno(
        id_partida=uuid4(),
        id_jogada=uuid4(),
        id_jogador=uuid4(),
        nu_jogador=nu_jogador,
        ts_jogada=datetime.now(timezone.utc).isoformat(),
        nu_timer_ms=nu_timer_ms,
    )


def _jogar_partida(
    cfg_j1: ConfiguracaoAgente,
    cfg_j2: ConfiguracaoAgente,
    nu_timer_ms: int | None = None,
) -> dict:
    """Joga uma partida 4×3 entre dois agentes; retorna métricas."""
    estado = EstadoTabuleiro.de_tamanho("pequeno")
    jogador_atual = 1
    contador_acoes: dict[CodigoAcao, int] = {}
    jogadas = 0
    while not estado.esta_terminal():
        cfg = cfg_j1 if jogador_atual == 1 else cfg_j2
        md = _md(jogador_atual, nu_timer_ms)
        r = escolher_jogada(estado, cfg, md)
        contador_acoes[r.co_acao] = contador_acoes.get(r.co_acao, 0) + 1
        capturas = estado.aplicar_traco(r.co_aresta, jogador_atual)
        jogadas += 1
        if capturas == 0:
            jogador_atual = -jogador_atual
    caixas_j1 = contar_caixas_jogador(estado, 1)
    caixas_j2 = contar_caixas_jogador(estado, -1)
    arestas_preenchidas = 31 - len(estado.tracos_disponiveis())
    return {
        "caixas_j1": caixas_j1,
        "caixas_j2": caixas_j2,
        "arestas_preenchidas": arestas_preenchidas,
        "jogadas": jogadas,
        "acoes": contador_acoes,
    }


@pytest.fixture(autouse=True)
def _limpar_cache():
    _limpar_cache_interpretadores()
    yield
    _limpar_cache_interpretadores()


# Reduzido para 5 partidas (em CI 100 seria custoso). Testa invariantes
# estruturais — não estatísticas de win-rate (SC-006 fica em validação manual).
@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
def test_auto_jogo_agente_vs_agente_termina_correto(seed):
    cfg_j1 = ConfiguracaoAgente(
        nivel_dificuldade=NivelDificuldade.DIFICIL,
        seed_aleatoriedade=seed,
        percentual_aleatoriedade=0.0,
        profundidade_minimax=1,  # depth=1 para acelerar testes
    )
    cfg_j2 = ConfiguracaoAgente(
        nivel_dificuldade=NivelDificuldade.DIFICIL,
        seed_aleatoriedade=seed + 1000,
        percentual_aleatoriedade=0.0,
        profundidade_minimax=1,
    )
    metricas = _jogar_partida(cfg_j1, cfg_j2)
    assert metricas["arestas_preenchidas"] == 31
    assert metricas["caixas_j1"] + metricas["caixas_j2"] == 12
    # Sem timer, não deve haver fallback de timeout
    assert metricas["acoes"].get(CodigoAcao.CNN_TIMEOUT, 0) == 0
    assert metricas["acoes"].get(CodigoAcao.ALEATORIA_TIMEOUT, 0) == 0


def test_auto_jogo_com_timer_largo_p1_predominante():
    """Timer largo (3000ms) → maioria das jogadas deve ser P1 (não-timeout)."""
    cfg = ConfiguracaoAgente(
        nivel_dificuldade=NivelDificuldade.DIFICIL,
        seed_aleatoriedade=99,
        percentual_aleatoriedade=0.0,
        profundidade_minimax=1,
    )
    metricas = _jogar_partida(cfg, cfg, nu_timer_ms=3000)
    timeouts = (
        metricas["acoes"].get(CodigoAcao.CNN_TIMEOUT, 0)
        + metricas["acoes"].get(CodigoAcao.ALEATORIA_TIMEOUT, 0)
    )
    p1 = metricas["jogadas"] - timeouts
    # Em hardware desktop, depth=1 + 3s deve garantir >= 80% de P1
    assert p1 >= int(metricas["jogadas"] * 0.8)

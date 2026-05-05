"""Testes unitários para tipos_pontinhos_3_4 (T013)."""
from __future__ import annotations

from uuid import uuid4

import numpy as np
import pytest

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import (
    MAPEAMENTO_NIVEIS,
    CodigoAcao,
    CodigoSituacao,
    ConfiguracaoAgente,
    Estrutura,
    MetadadosTurno,
    NivelDificuldade,
    ResultadoJogada,
    array_31_com_nan,
    contar_caixas_jogador,
)


# =============================================================================
# Enumerações e MAPEAMENTO_NIVEIS
# =============================================================================


def test_enums_sao_strings():
    assert NivelDificuldade.FACIL.value == "facil"
    assert CodigoSituacao.CAPTURA_SEGURA.value == "captura_segura"
    assert CodigoAcao.CAPTURA_GULOSA.value == "captura_gulosa"


def test_mapeamento_niveis_cobre_todos_os_niveis():
    for nivel in NivelDificuldade:
        assert nivel in MAPEAMENTO_NIVEIS
        defaults = MAPEAMENTO_NIVEIS[nivel]
        assert "caminho_modelo_cnn" in defaults
        assert "profundidade_minimax" in defaults
        assert "percentual_aleatoriedade" in defaults


# =============================================================================
# ConfiguracaoAgente
# =============================================================================


@pytest.mark.parametrize("nivel", list(NivelDificuldade))
def test_configuracao_agente_deriva_defaults_por_nivel(nivel):
    cfg = ConfiguracaoAgente(nivel_dificuldade=nivel)
    defaults = MAPEAMENTO_NIVEIS[nivel]
    assert cfg.caminho_modelo_cnn == defaults["caminho_modelo_cnn"]
    assert cfg.profundidade_minimax == defaults["profundidade_minimax"]
    assert cfg.percentual_aleatoriedade == defaults["percentual_aleatoriedade"]
    assert cfg.seed_aleatoriedade is None
    assert cfg.verbose is False


def test_configuracao_agente_default_eh_dificil():
    cfg = ConfiguracaoAgente()
    assert cfg.nivel_dificuldade == NivelDificuldade.DIFICIL
    assert cfg.profundidade_minimax == 3
    assert cfg.percentual_aleatoriedade == pytest.approx(0.05)


def test_configuracao_agente_override_granular_mantem_outros_derivados():
    cfg = ConfiguracaoAgente(
        nivel_dificuldade=NivelDificuldade.MEDIO, profundidade_minimax=5
    )
    assert cfg.profundidade_minimax == 5
    assert cfg.caminho_modelo_cnn == MAPEAMENTO_NIVEIS[NivelDificuldade.MEDIO][
        "caminho_modelo_cnn"
    ]
    assert cfg.percentual_aleatoriedade == pytest.approx(0.15)


def test_configuracao_agente_override_caminho_modelo():
    cfg = ConfiguracaoAgente(
        nivel_dificuldade=NivelDificuldade.FACIL,
        caminho_modelo_cnn="modelos/custom.tflite",
    )
    assert cfg.caminho_modelo_cnn == "modelos/custom.tflite"
    assert cfg.profundidade_minimax == 1


def test_configuracao_agente_valueerror_profundidade_zero():
    with pytest.raises(ValueError, match="profundidade_minimax"):
        ConfiguracaoAgente(profundidade_minimax=0)


def test_configuracao_agente_valueerror_profundidade_negativa():
    with pytest.raises(ValueError, match="profundidade_minimax"):
        ConfiguracaoAgente(profundidade_minimax=-1)


def test_configuracao_agente_valueerror_aleatoriedade_negativa():
    with pytest.raises(ValueError, match="percentual_aleatoriedade"):
        ConfiguracaoAgente(percentual_aleatoriedade=-0.01)


def test_configuracao_agente_valueerror_aleatoriedade_acima_de_um():
    with pytest.raises(ValueError, match="percentual_aleatoriedade"):
        ConfiguracaoAgente(percentual_aleatoriedade=1.01)


def test_configuracao_agente_aleatoriedade_zero_e_um_aceitos():
    ConfiguracaoAgente(percentual_aleatoriedade=0.0)
    ConfiguracaoAgente(percentual_aleatoriedade=1.0)


# =============================================================================
# MetadadosTurno
# =============================================================================


def _metadados_validos(**overrides) -> dict:
    base = dict(
        id_partida=uuid4(),
        id_jogada=uuid4(),
        id_jogador=uuid4(),
        nu_jogador=1,
        ts_jogada="2026-05-01T14:23:45-03:00",
    )
    base.update(overrides)
    return base


def test_metadados_turno_valido_sem_timer():
    m = MetadadosTurno(**_metadados_validos())
    assert m.nu_timer_ms is None


def test_metadados_turno_timer_zero_aceito():
    m = MetadadosTurno(**_metadados_validos(nu_timer_ms=0))
    assert m.nu_timer_ms == 0


def test_metadados_turno_timer_positivo_aceito():
    m = MetadadosTurno(**_metadados_validos(nu_timer_ms=500))
    assert m.nu_timer_ms == 500


def test_metadados_turno_valueerror_nu_jogador_invalido():
    with pytest.raises(ValueError, match="nu_jogador"):
        MetadadosTurno(**_metadados_validos(nu_jogador=0))
    with pytest.raises(ValueError, match="nu_jogador"):
        MetadadosTurno(**_metadados_validos(nu_jogador=2))


def test_metadados_turno_valueerror_timer_negativo():
    with pytest.raises(ValueError, match="nu_timer_ms"):
        MetadadosTurno(**_metadados_validos(nu_timer_ms=-1))


def test_metadados_turno_eh_imutavel():
    m = MetadadosTurno(**_metadados_validos())
    with pytest.raises(Exception):  # FrozenInstanceError herda de AttributeError
        m.nu_jogador = -1  # type: ignore[misc]


# =============================================================================
# ResultadoJogada (apenas validação estrutural)
# =============================================================================


def test_resultado_jogada_aceita_campos_minimos():
    estado = EstadoTabuleiro(4, 3)
    matriz = estado.matriz.copy()
    r = ResultadoJogada(
        id_partida=uuid4(),
        id_jogada=uuid4(),
        id_jogador=uuid4(),
        nu_jogador=1,
        co_situacao=CodigoSituacao.CAPTURA_SEGURA,
        co_acao=CodigoAcao.CAPTURA_GULOSA,
        co_aresta="H_0_1",
        ar_tabuleiro_antes=matriz,
        ar_tabuleiro_apos=matriz.copy(),
        nu_placar_jogador_antes=0,
        nu_placar_jogador_apos=1,
        ts_jogada="2026-05-01T14:23:45-03:00",
        nu_timer_ms=None,
        nu_tempo_calculo_ms=12,
    )
    assert r.nu_profundidade_minimax is None
    assert r.ar_score_minimax is None
    assert r.ar_probabilidade_cnn is None
    assert r.js_extra is None


# =============================================================================
# Estrutura
# =============================================================================


def test_estrutura_corrente_longa_propriedades():
    e = Estrutura(
        tipo="corrente",
        caixas=((1, 1), (1, 3), (1, 5)),
        extremidades=((1, 1), (1, 5)),
    )
    assert e.tamanho == 3
    assert e.eh_corrente_longa is True


def test_estrutura_corrente_curta_nao_eh_longa():
    e = Estrutura(tipo="corrente", caixas=((1, 1), (1, 3)), extremidades=((1, 1), (1, 3)))
    assert e.tamanho == 2
    assert e.eh_corrente_longa is False


def test_estrutura_ciclo_nao_eh_corrente_longa():
    e = Estrutura(tipo="ciclo", caixas=((1, 1), (1, 3), (3, 3), (3, 1)))
    assert e.eh_corrente_longa is False
    assert e.tamanho == 4


def test_estrutura_eh_imutavel():
    e = Estrutura(tipo="isolada", caixas=((1, 1),))
    with pytest.raises(Exception):
        e.tipo = "ciclo"  # type: ignore[misc]


# =============================================================================
# Helpers
# =============================================================================


def test_array_31_com_nan_retorna_float32_shape_31_com_nan():
    arr = array_31_com_nan()
    assert arr.dtype == np.float32
    assert arr.shape == (31,)
    assert np.all(np.isnan(arr))


def test_array_31_com_nan_retorna_instancia_nova_a_cada_chamada():
    a = array_31_com_nan()
    b = array_31_com_nan()
    assert a is not b
    a[0] = 1.0
    assert np.isnan(b[0])


def test_contar_caixas_jogador_zero_em_tabuleiro_vazio():
    estado = EstadoTabuleiro(4, 3)
    assert contar_caixas_jogador(estado, 1) == 0
    assert contar_caixas_jogador(estado, -1) == 0


def test_contar_caixas_jogador_conta_atribuicoes_explicitas():
    estado = EstadoTabuleiro(4, 3)
    # Marca duas caixas do J1 e uma do J2 diretamente na matriz interna.
    estado.matriz[1, 1] = 1
    estado.matriz[1, 3] = 1
    estado.matriz[3, 1] = -1
    assert contar_caixas_jogador(estado, 1) == 2
    assert contar_caixas_jogador(estado, -1) == 1

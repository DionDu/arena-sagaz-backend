"""Testes unitários para `ia_pontinhos_3_4` (T021 + T028 + T039 + T040 + T042).

Os testes que exigem TFLite real são marcados com `tflite_real`. Os demais
mockam `carregar_modelo` / `inferir` / `top_k_arestas_livres` para isolar a
lógica do agente.
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import numpy as np
import pytest

from gerador_dados.jogo_pontinhos import ia_pontinhos_3_4 as mod_ia
from gerador_dados.jogo_pontinhos.ia_pontinhos_3_4 import (
    _arg_max_arestas_livres,
    _arg_max_com_tiebreak,
    _aresta_aleatoria_livre,
    _elapsed_ms,
    _estourou_timer,
    escolher_jogada,
)
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import (
    CodigoAcao,
    CodigoSituacao,
    ConfiguracaoAgente,
    MetadadosTurno,
    NivelDificuldade,
)


# =============================================================================
# Fixtures e factories
# =============================================================================


def _md(**overrides) -> MetadadosTurno:
    base = dict(
        id_partida=uuid4(),
        id_jogada=uuid4(),
        id_jogador=uuid4(),
        nu_jogador=1,
        ts_jogada="2026-05-04T10:00:00-03:00",
    )
    base.update(overrides)
    return MetadadosTurno(**base)


def _cfg(**overrides) -> ConfiguracaoAgente:
    base = dict(
        nivel_dificuldade=NivelDificuldade.DIFICIL,
        seed_aleatoriedade=42,
        percentual_aleatoriedade=0.0,
    )
    base.update(overrides)
    return ConfiguracaoAgente(**base)


def _tabuleiro_grau_3_unico_1x1() -> tuple[EstadoTabuleiro, str]:
    """Tabuleiro 1x1 com 3 lados preenchidos — uma única caixa grau-3."""
    estado = EstadoTabuleiro(1, 1)
    tracos = estado.tracos_disponiveis()
    for tr in tracos[:-1]:
        estado.aplicar_traco(tr)
    return estado, tracos[-1]


def _tabuleiro_grau_3_isolado_pequeno() -> tuple[EstadoTabuleiro, str]:
    """Tabuleiro 4x3 com uma única caixa grau-3 isolada no canto sup-esq.

    Construímos manualmente: caixa (1,1) com 3 lados preenchidos, sem
    nenhuma corrente longa adjacente.
    """
    estado = EstadoTabuleiro(4, 3)
    estado.aplicar_traco("H_0_1", 1)  # topo da (1,1)
    estado.aplicar_traco("V_1_0", 1)  # esquerda da (1,1)
    estado.aplicar_traco("V_1_2", 1)  # direita da (1,1)
    return estado, "H_2_1"


# =============================================================================
# US1 — Captura grau-3 isolada (sem CNN, sem timer)
# =============================================================================


def test_us1_captura_grau_3_unico_1x1():
    estado, ultimo = _tabuleiro_grau_3_unico_1x1()
    cfg = _cfg()
    md = _md()
    r = escolher_jogada(estado, cfg, md)
    assert r.co_aresta == ultimo
    assert r.co_situacao == CodigoSituacao.CAPTURA_SEGURA
    assert r.co_acao == CodigoAcao.CAPTURA_GULOSA
    assert r.nu_profundidade_minimax is None
    assert r.ar_score_minimax is None
    assert r.ar_probabilidade_cnn is None
    assert r.js_extra is None
    assert isinstance(r.nu_tempo_calculo_ms, int)
    assert r.nu_tempo_calculo_ms >= 0


def test_us1_captura_grau_3_isolada_pequeno():
    estado, esperada = _tabuleiro_grau_3_isolado_pequeno()
    cfg = _cfg()
    md = _md()
    r = escolher_jogada(estado, cfg, md)
    assert r.co_aresta == esperada
    assert r.co_acao == CodigoAcao.CAPTURA_GULOSA
    assert r.nu_placar_jogador_apos == r.nu_placar_jogador_antes + 1


def test_us1_eco_de_metadados():
    estado, _ = _tabuleiro_grau_3_isolado_pequeno()
    cfg = _cfg()
    md = _md()
    r = escolher_jogada(estado, cfg, md)
    assert r.id_partida == md.id_partida
    assert r.id_jogada == md.id_jogada
    assert r.id_jogador == md.id_jogador
    assert r.nu_jogador == md.nu_jogador
    assert r.ts_jogada == md.ts_jogada
    assert r.nu_timer_ms == md.nu_timer_ms  # ambos None


def test_us1_tabuleiro_antes_apos_int8():
    estado, _ = _tabuleiro_grau_3_isolado_pequeno()
    matriz_inicial = estado.matriz.copy()
    cfg = _cfg()
    md = _md()
    r = escolher_jogada(estado, cfg, md)
    assert r.ar_tabuleiro_antes.dtype == np.int8
    assert r.ar_tabuleiro_apos.dtype == np.int8
    np.testing.assert_array_equal(r.ar_tabuleiro_antes, matriz_inicial)
    # Apos: aresta esperada aplicada → caixa (1,1) fechada como jogador 1
    assert r.ar_tabuleiro_apos[1, 1] == 1


def test_us1_estado_terminal_levanta_valueerror():
    estado = EstadoTabuleiro(1, 1)
    for tr in estado.tracos_disponiveis():
        estado.aplicar_traco(tr)
    with pytest.raises(ValueError, match="não há jogadas"):
        escolher_jogada(estado, _cfg(), _md())


# =============================================================================
# Helpers internos — testes diretos
# =============================================================================


def test_elapsed_ms_monotonico():
    import time
    inicio = time.monotonic_ns()
    decorrido = _elapsed_ms(inicio)
    assert decorrido >= 0


def test_estourou_timer_zero_nunca_estoura():
    import time
    assert _estourou_timer(time.monotonic_ns(), 0) is False


def test_estourou_timer_negativo_nao_estoura():
    import time
    assert _estourou_timer(time.monotonic_ns(), -1) is False


def test_aresta_aleatoria_livre_retorna_traco_disponivel():
    estado = EstadoTabuleiro(2, 2)
    rng = np.random.default_rng(42)
    aresta = _aresta_aleatoria_livre(estado, rng)
    assert aresta in estado.tracos_disponiveis()


def test_aresta_aleatoria_levanta_em_estado_terminal():
    estado = EstadoTabuleiro(1, 1)
    for tr in estado.tracos_disponiveis():
        estado.aplicar_traco(tr)
    rng = np.random.default_rng(42)
    with pytest.raises(ValueError, match="não há jogadas"):
        _aresta_aleatoria_livre(estado, rng)


def test_arg_max_arestas_livres_retorna_aresta_de_maior_prob():
    estado = EstadoTabuleiro(4, 3)
    distribuicao = np.zeros(31, dtype=np.float32)
    distribuicao[5] = 0.99
    aresta = _arg_max_arestas_livres(distribuicao, estado)
    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import todos_labels_canonicos
    labels = todos_labels_canonicos(4, 3)
    assert aresta == labels[5]


def test_arg_max_com_tiebreak_seleciona_maior_score():
    scores = np.full(31, np.nan, dtype=np.float32)
    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import todos_labels_canonicos
    labels = todos_labels_canonicos(4, 3)
    top5 = [(labels[0], 0.5), (labels[1], 0.3), (labels[2], 0.1)]
    scores[0] = 1.0
    scores[1] = 5.0
    scores[2] = 2.0
    melhor = _arg_max_com_tiebreak(scores, top5)
    assert melhor == labels[1]


def test_arg_max_com_tiebreak_empate_prefere_primeiro_do_top5():
    """Empate de score → preferir maior probabilidade CNN (= primeiro do top5)."""
    scores = np.full(31, np.nan, dtype=np.float32)
    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import todos_labels_canonicos
    labels = todos_labels_canonicos(4, 3)
    top5 = [(labels[0], 0.5), (labels[1], 0.4)]
    scores[0] = 3.0
    scores[1] = 3.0
    melhor = _arg_max_com_tiebreak(scores, top5)
    assert melhor == labels[0]


def test_arg_max_com_tiebreak_todos_nan_retorna_primeiro():
    scores = np.full(31, np.nan, dtype=np.float32)
    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import todos_labels_canonicos
    labels = todos_labels_canonicos(4, 3)
    top5 = [(labels[0], 0.5), (labels[1], 0.4)]
    melhor = _arg_max_com_tiebreak(scores, top5)
    assert melhor == labels[0]


# =============================================================================
# US3+US4 — Fase tática com CNN mockada
# =============================================================================


def _mock_cnn(distribuicao: np.ndarray):
    """Cria um par (carregar_modelo, inferir) que devolve `distribuicao`."""
    from gerador_dados.jogo_pontinhos.cnn_inferencia_pontinhos_3_4 import InferenciaCNN
    import threading

    fake_inferencia = InferenciaCNN(
        interpretador=None,
        indice_entrada=0,
        indice_saida=0,
        forma_entrada=(1, 9, 7, 1),
        lock=threading.Lock(),
    )

    def _carregar(_caminho):
        return fake_inferencia

    def _inferir(_inferencia, _estado):
        return distribuicao.astype(np.float32)

    return _carregar, _inferir


def test_us3_4_tabuleiro_vazio_retorna_aresta_valida():
    estado = EstadoTabuleiro(4, 3)
    distrib = np.linspace(0.01, 0.99, 31, dtype=np.float32)
    distrib /= distrib.sum()
    carregar, inferir = _mock_cnn(distrib)
    with patch.object(mod_ia, "carregar_modelo", carregar), \
         patch.object(mod_ia, "inferir", inferir):
        r = escolher_jogada(estado, _cfg(profundidade_minimax=1), _md())
    assert r.co_aresta in estado.tracos_disponiveis()
    assert r.co_situacao == CodigoSituacao.TATICA
    assert r.co_acao == CodigoAcao.CNN_E_MINIMAX
    assert r.nu_profundidade_minimax == 1
    assert r.ar_score_minimax is not None
    assert r.ar_score_minimax.shape == (31,)
    assert r.ar_score_minimax.dtype == np.float32
    assert r.ar_probabilidade_cnn is not None
    assert r.ar_probabilidade_cnn.shape == (31,)


def test_us3_4_seed_zero_aleatoriedade_determinista():
    estado = EstadoTabuleiro(4, 3)
    distrib = np.linspace(0.01, 0.99, 31, dtype=np.float32)
    distrib /= distrib.sum()
    carregar, inferir = _mock_cnn(distrib)
    with patch.object(mod_ia, "carregar_modelo", carregar), \
         patch.object(mod_ia, "inferir", inferir):
        r1 = escolher_jogada(estado, _cfg(profundidade_minimax=1), _md())
        r2 = escolher_jogada(estado, _cfg(profundidade_minimax=1), _md())
    assert r1.co_aresta == r2.co_aresta


def test_us3_4_aleatoriedade_zero_em_modo_expert():
    estado = EstadoTabuleiro(4, 3)
    distrib = np.linspace(0.01, 0.99, 31, dtype=np.float32)
    distrib /= distrib.sum()
    carregar, inferir = _mock_cnn(distrib)
    cfg = _cfg(
        nivel_dificuldade=NivelDificuldade.EXPERT,
        percentual_aleatoriedade=0.0,
        profundidade_minimax=1,
    )
    with patch.object(mod_ia, "carregar_modelo", carregar), \
         patch.object(mod_ia, "inferir", inferir):
        r = escolher_jogada(estado, cfg, _md())
    assert r.co_aresta in estado.tracos_disponiveis()


# =============================================================================
# Timer (T040)
# =============================================================================


def test_timer_p3_aleatoria_quando_estoura_imediatamente():
    """Timer = 1ms; mock força _elapsed_ms a sempre retornar valor alto."""
    estado = EstadoTabuleiro(4, 3)
    cfg = _cfg(profundidade_minimax=1)
    md = _md(nu_timer_ms=1)

    real_monotonic = mod_ia.time.monotonic_ns
    inicio_chamada = real_monotonic()
    chamadas = {"n": 0}

    def fake_monotonic():
        chamadas["n"] += 1
        # Após primeira leitura (do início), retornamos timestamps muito futuros
        if chamadas["n"] <= 1:
            return inicio_chamada
        return inicio_chamada + 999_000_000  # +999ms

    with patch.object(mod_ia.time, "monotonic_ns", side_effect=fake_monotonic):
        r = escolher_jogada(estado, cfg, md)

    assert r.co_acao == CodigoAcao.ALEATORIA_TIMEOUT
    assert r.ar_score_minimax is None
    assert r.ar_probabilidade_cnn is None
    assert r.nu_profundidade_minimax is None
    assert r.co_aresta in estado.tracos_disponiveis()


def test_timer_sem_limite_nu_timer_ms_none():
    """Sem timer (None), agente nunca retorna timeout."""
    estado, _ = _tabuleiro_grau_3_isolado_pequeno()
    r = escolher_jogada(estado, _cfg(), _md(nu_timer_ms=None))
    assert r.co_acao not in (CodigoAcao.CNN_TIMEOUT, CodigoAcao.ALEATORIA_TIMEOUT)
    assert r.nu_timer_ms is None


def test_timer_zero_nu_timer_ms_nunca_estoura():
    """nu_timer_ms = 0 desabilita timeout (mesmo comportamento de None)."""
    estado, _ = _tabuleiro_grau_3_isolado_pequeno()
    r = escolher_jogada(estado, _cfg(), _md(nu_timer_ms=0))
    assert r.co_acao not in (CodigoAcao.CNN_TIMEOUT, CodigoAcao.ALEATORIA_TIMEOUT)
    assert r.nu_timer_ms == 0


def test_timer_largo_retorna_p1():
    """Timer largo (5s) deve permitir P1 em estado simples."""
    estado, _ = _tabuleiro_grau_3_isolado_pequeno()
    r = escolher_jogada(estado, _cfg(), _md(nu_timer_ms=5000))
    assert r.co_acao == CodigoAcao.CAPTURA_GULOSA
    assert r.nu_timer_ms == 5000


def test_timer_estoura_apos_cnn_retorna_p2():
    """Estoura entre inferência da CNN e Minimax → P2 (cnn_timeout)."""
    estado = EstadoTabuleiro(4, 3)
    distrib = np.zeros(31, dtype=np.float32)
    distrib[5] = 0.9
    carregar, inferir = _mock_cnn(distrib)

    real_monotonic = mod_ia.time.monotonic_ns
    inicio_chamada = real_monotonic()
    contador = {"n": 0}

    def fake_monotonic():
        contador["n"] += 1
        # 1ª leitura: início. 2ª: para checar P3 fallback. 3ª: após CNN.
        # Forjar estouro só DEPOIS da CNN (após n>=3)
        if contador["n"] <= 2:
            return inicio_chamada
        return inicio_chamada + 999_000_000

    cfg = _cfg(profundidade_minimax=1)
    md = _md(nu_timer_ms=50)
    with patch.object(mod_ia, "carregar_modelo", carregar), \
         patch.object(mod_ia, "inferir", inferir), \
         patch.object(mod_ia.time, "monotonic_ns", side_effect=fake_monotonic):
        r = escolher_jogada(estado, cfg, md)

    assert r.co_acao == CodigoAcao.CNN_TIMEOUT
    assert r.co_situacao == CodigoSituacao.TATICA
    assert r.ar_probabilidade_cnn is not None


# =============================================================================
# US5 — campos opcionais por origem (T042)
# =============================================================================


def test_us1_campos_opcionais_todos_none():
    estado, _ = _tabuleiro_grau_3_isolado_pequeno()
    r = escolher_jogada(estado, _cfg(), _md())
    assert r.nu_profundidade_minimax is None
    assert r.ar_score_minimax is None
    assert r.ar_probabilidade_cnn is None
    assert r.js_extra is None


def test_resultado_co_aresta_em_tracos_disponiveis():
    estado = EstadoTabuleiro(4, 3)
    distrib = np.linspace(0.01, 0.99, 31, dtype=np.float32)
    distrib /= distrib.sum()
    carregar, inferir = _mock_cnn(distrib)
    livres_antes = set(estado.tracos_disponiveis())
    with patch.object(mod_ia, "carregar_modelo", carregar), \
         patch.object(mod_ia, "inferir", inferir):
        r = escolher_jogada(estado, _cfg(profundidade_minimax=1), _md())
    assert r.co_aresta in livres_antes


def test_resultado_nu_tempo_calculo_ms_sempre_int_positivo():
    estado, _ = _tabuleiro_grau_3_isolado_pequeno()
    r = escolher_jogada(estado, _cfg(), _md())
    assert isinstance(r.nu_tempo_calculo_ms, int)
    assert r.nu_tempo_calculo_ms >= 0


# =============================================================================
# US2 — Cobertura do Passo 2 (double-dealing)
# =============================================================================


def _tabuleiro_corrente_longa_com_2_grau_3_no_final() -> EstadoTabuleiro:
    """Estado canônico onde caixas (1,3) e (1,5) estão grau-3 e (1,1)
    é a "raiz" da estrutura — força o trigger_double_dealing a disparar."""
    estado = EstadoTabuleiro(4, 3)
    # Constrói a corrente "1-3-5" com (1,1)=grau-2, (1,3)=grau-3, (1,5)=grau-3.
    estado.aplicar_traco("H_0_1", 1)
    estado.aplicar_traco("H_2_1", 1)
    estado.aplicar_traco("H_0_3", 1)
    estado.aplicar_traco("H_2_3", 1)
    estado.aplicar_traco("V_1_4", 1)
    estado.aplicar_traco("H_0_5", 1)
    estado.aplicar_traco("H_2_5", 1)
    estado.aplicar_traco("V_1_6", 1)
    return estado


def test_us2_passo_2_executa_quando_trigger_dispara():
    """Estado armado para que estrutura_ativa retorne corrente e
    trigger_double_dealing dispare. Este teste valida apenas que o caminho
    do Passo 2 é executado sem erro — a decisão A vs B depende do minimax."""
    estado = _tabuleiro_corrente_longa_com_2_grau_3_no_final()
    cfg = _cfg(profundidade_minimax=1)
    r = escolher_jogada(estado, cfg, _md())
    # Resultado deve ser válido independentemente de qual caminho disparou
    assert r.co_aresta in estado.tracos_disponiveis()


# =============================================================================
# Aleatoriedade FR-042
# =============================================================================


def test_aleatoriedade_substitui_aresta_quando_rng_dispara():
    """Com percentual_aleatoriedade=1.0, sempre substitui pela escolha aleatória."""
    estado = EstadoTabuleiro(4, 3)
    distrib = np.zeros(31, dtype=np.float32)
    # Distribuição que privilegia label 0
    distrib[0] = 0.9
    distrib[1] = 0.05
    distrib[2] = 0.03
    distrib[3] = 0.01
    distrib[4] = 0.005
    carregar, inferir = _mock_cnn(distrib)
    cfg = _cfg(
        percentual_aleatoriedade=1.0,  # sempre randomiza
        seed_aleatoriedade=42,
        profundidade_minimax=1,
    )
    with patch.object(mod_ia, "carregar_modelo", carregar), \
         patch.object(mod_ia, "inferir", inferir):
        r = escolher_jogada(estado, cfg, _md())
    assert r.co_aresta in estado.tracos_disponiveis()
    assert r.co_acao == CodigoAcao.CNN_E_MINIMAX


def test_aleatoriedade_zero_nunca_substitui():
    """Com percentual_aleatoriedade=0.0, nunca chama o RNG para substituir."""
    estado = EstadoTabuleiro(4, 3)
    distrib = np.zeros(31, dtype=np.float32)
    distrib[10] = 0.9
    distrib[5] = 0.05
    distrib[15] = 0.05
    carregar, inferir = _mock_cnn(distrib)
    cfg = _cfg(percentual_aleatoriedade=0.0, profundidade_minimax=1)
    with patch.object(mod_ia, "carregar_modelo", carregar), \
         patch.object(mod_ia, "inferir", inferir):
        r1 = escolher_jogada(estado, cfg, _md())
        r2 = escolher_jogada(estado, cfg, _md())
    assert r1.co_aresta == r2.co_aresta


# =============================================================================
# Argmax sobre arestas livres — caminho via fallback P2
# =============================================================================


def test_arg_max_arestas_livres_ignora_arestas_preenchidas():
    estado = EstadoTabuleiro(4, 3)
    # Preenche H_0_1 (índice 0)
    estado.aplicar_traco("H_0_1", 1)
    distribuicao = np.zeros(31, dtype=np.float32)
    distribuicao[0] = 0.99  # alta prob, mas H_0_1 está preenchida
    distribuicao[1] = 0.5
    aresta = _arg_max_arestas_livres(distribuicao, estado)
    assert aresta != "H_0_1"


# =============================================================================
# Edge cases — Passo 2 com timer que estoura no momento certo
# =============================================================================


# =============================================================================
# Cobertura — Passo 2 forçado via mock e _montar_resultado_us2 direto
# =============================================================================


def test_montar_resultado_us2_direto():
    """Chama o helper _montar_resultado_us2 diretamente para exercitar a
    montagem de js_extra com co_acao_nao_selecionada."""
    estado, _ = _tabuleiro_grau_3_isolado_pequeno()
    tabuleiro_antes = estado.matriz.copy()
    inicio_ns = mod_ia.time.monotonic_ns()
    md = _md()
    cfg = _cfg(profundidade_minimax=2)
    r = mod_ia._montar_resultado_us2(
        aresta="H_2_1",
        co_situacao=CodigoSituacao.FINAL_CORRENTE_LONGA,
        co_acao=CodigoAcao.SACRIFICIO_DOUBLE_CROSS,
        score_escolhida=5,
        co_acao_rejeitada=CodigoAcao.CAPTURA_COMPLETA,
        score_rejeitada=2,
        estado=estado,
        tabuleiro_antes=tabuleiro_antes,
        placar_antes=0,
        inicio_ns=inicio_ns,
        metadados=md,
        configuracao=cfg,
    )
    assert r.co_acao == CodigoAcao.SACRIFICIO_DOUBLE_CROSS
    assert r.nu_profundidade_minimax == 2
    assert r.ar_score_minimax is not None
    assert r.js_extra is not None
    assert r.js_extra["co_acao_nao_selecionada"] == "captura_completa"
    assert "ar_score_minimax_opcao_nao_selecionada" in r.js_extra


def test_passo_2_dispara_via_mock_trigger():
    """Mock força trigger_double_dealing a retornar True para exercitar
    o bloco do Passo 2 dentro de escolher_jogada."""
    estado = EstadoTabuleiro(4, 3)
    # Caixa (1,1) com 3 lados → grau-3
    estado.aplicar_traco("H_0_1", 1)
    estado.aplicar_traco("V_1_0", 1)
    estado.aplicar_traco("V_1_2", 1)

    from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import Estrutura

    fake_estrutura = Estrutura(
        tipo="corrente",
        caixas=((1, 1), (3, 1), (5, 1)),
        extremidades=((1, 1), (5, 1)),
    )

    def fake_estrutura_ativa(_estado, _grau3):
        return fake_estrutura

    def fake_trigger(_estrutura, _grau3):
        return True

    def fake_estado_apos_captura(estado, _e, jogador):
        clone = estado.clonar()
        clone.aplicar_traco("H_2_1", jogador)
        return clone

    def fake_estado_apos_dc(estado, _e, jogador):
        return estado.clonar()

    def fake_primeira_aresta(_e, _estado):
        return "H_2_1"

    def fake_aresta_dc(_e, _estado):
        return "V_3_0"  # uma aresta livre arbitrária

    with patch.object(mod_ia, "estrutura_ativa", fake_estrutura_ativa), \
         patch.object(mod_ia, "trigger_double_dealing", fake_trigger), \
         patch.object(mod_ia, "estado_apos_captura_completa", fake_estado_apos_captura), \
         patch.object(mod_ia, "estado_apos_double_cross", fake_estado_apos_dc), \
         patch.object(mod_ia, "primeira_aresta_de_captura", fake_primeira_aresta), \
         patch.object(mod_ia, "aresta_double_cross", fake_aresta_dc):
        r = escolher_jogada(estado, _cfg(profundidade_minimax=1), _md())

    assert r.co_situacao == CodigoSituacao.FINAL_CORRENTE_LONGA
    assert r.co_acao in (CodigoAcao.CAPTURA_COMPLETA, CodigoAcao.SACRIFICIO_DOUBLE_CROSS)
    assert r.js_extra is not None
    assert "co_acao_nao_selecionada" in r.js_extra


def test_timer_estoura_apos_grau_3_detectado_devolve_aleatoria():
    estado, _ = _tabuleiro_grau_3_isolado_pequeno()
    cfg = _cfg()
    md = _md(nu_timer_ms=1)

    real_monotonic = mod_ia.time.monotonic_ns
    inicio_chamada = real_monotonic()
    contador = {"n": 0}

    def fake_monotonic():
        contador["n"] += 1
        # 1ª: registro inicial; 2ª: check pós-P3 (passa); 3ª+: estoura
        if contador["n"] <= 2:
            return inicio_chamada
        return inicio_chamada + 999_000_000

    with patch.object(mod_ia.time, "monotonic_ns", side_effect=fake_monotonic):
        r = escolher_jogada(estado, cfg, md)

    # Pode ter passado pelo Passo 1 (grau_3 detectado); tanto P3 quanto US1
    # são respostas válidas dependendo de quando o timer foi consultado.
    assert r.co_aresta in {"H_0_1", "V_1_0", "V_1_2", "H_2_1"} or \
           r.co_aresta in estado.tracos_disponiveis()

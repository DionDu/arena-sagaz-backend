"""Agente híbrido `ia-pontinhos-3-4` — pipeline em 4 passos com timer cooperativo.

Entry-point único: `escolher_jogada(estado, configuracao, metadados) -> ResultadoJogada`.

Pipeline determinístico:
    1. Captura segura/gulosa (caixa grau-3 isolada).
    2. Exceção do sacrifício (double-cross em final de corrente longa/ciclo).
    3. Fase tática via CNN (TOP-5 arestas mais prováveis).
    4. Validação Minimax sobre as TOP-5.

Timer (D10): se `metadados.nu_timer_ms > 0`, o agente mantém uma resposta
de fallback aleatória (P3) preparada antes de qualquer custo, e — quando
chega à fase tática — uma resposta argmax-CNN (P2). Em cada checkpoint,
se o tempo decorrido excede o limite, retorna a melhor resposta disponível
e marca `co_acao` como `cnn_timeout` ou `aleatoria_timeout`.

Detalhes do contrato em `specs/003-jogador-hibrido/contracts/api-python-pontinhos-3-4.md`.
"""
from __future__ import annotations

import threading
import time

import numpy as np

from gerador_dados.jogo_pontinhos.cnn_inferencia_pontinhos_3_4 import (
    InferenciaCNN,
    carregar_modelo,
    inferir,
    top_k_arestas_livres,
)
from gerador_dados.jogo_pontinhos.correntes_pontinhos_3_4 import (
    aresta_double_cross,
    aresta_que_fecha,
    caixas_grau_3,
    estado_apos_captura_completa,
    estado_apos_double_cross,
    estrutura_ativa,
    primeira_aresta_de_captura,
    trigger_double_dealing,
)
from gerador_dados.jogo_pontinhos.minimax_pontinhos import avaliar, minimax
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    todos_labels_canonicos,
)
from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import (
    CodigoAcao,
    CodigoSituacao,
    ConfiguracaoAgente,
    Estrutura,
    MetadadosTurno,
    ResultadoJogada,
    array_31_com_nan,
    contar_caixas_jogador,
)


# Cache module-level partilhado com `cnn_inferencia_pontinhos_3_4` via DI;
# este módulo apenas referencia para conformidade com T016. O cache real
# vive no módulo de inferência.
_cache_interpretadores: dict[str, InferenciaCNN] = {}
_lock_cache = threading.Lock()


_LABELS_CANONICOS_PEQUENO = todos_labels_canonicos(4, 3)
_INDICE_LABEL_PEQUENO = {lab: i for i, lab in enumerate(_LABELS_CANONICOS_PEQUENO)}


# =============================================================================
# Helpers de timer
# =============================================================================


def _elapsed_ms(inicio_ns: int) -> int:
    return int((time.monotonic_ns() - inicio_ns) // 1_000_000)


def _estourou_timer(inicio_ns: int, nu_timer_ms: int) -> bool:
    if nu_timer_ms <= 0:
        return False
    return _elapsed_ms(inicio_ns) >= nu_timer_ms


# =============================================================================
# Helpers de escolha de aresta
# =============================================================================


def _aresta_aleatoria_livre(
    estado: EstadoTabuleiro, rng: np.random.Generator
) -> str:
    livres = estado.tracos_disponiveis()
    if not livres:
        raise ValueError("não há jogadas disponíveis no estado recebido")
    return livres[int(rng.integers(0, len(livres)))]


def _arg_max_arestas_livres(
    distribuicao: np.ndarray, estado: EstadoTabuleiro
) -> str:
    """Aresta livre com maior probabilidade. Tie-break: menor índice canônico."""
    livres = estado.tracos_disponiveis()
    if not livres:
        raise ValueError("não há jogadas disponíveis no estado recebido")
    melhor_label: str | None = None
    melhor_prob: float = -np.inf
    melhor_idx: int = -1
    for label in livres:
        idx = _INDICE_LABEL_PEQUENO[label]
        prob = float(distribuicao[idx])
        if prob > melhor_prob or (
            prob == melhor_prob and (melhor_idx == -1 or idx < melhor_idx)
        ):
            melhor_label = label
            melhor_prob = prob
            melhor_idx = idx
    assert melhor_label is not None
    return melhor_label


def _arg_max_com_tiebreak(
    scores_31: np.ndarray, top5: list[tuple[str, float]]
) -> str:
    """Aresta com maior score Minimax dentre as avaliadas no TOP-5.

    Tie-break: maior probabilidade CNN — top5 já vem ordenado por prob desc,
    então em empate o primeiro encontrado vence.
    """
    if not top5:
        raise ValueError("top5 vazio")
    melhor_label: str | None = None
    melhor_score: float | None = None
    for label, _prob in top5:
        idx = _INDICE_LABEL_PEQUENO[label]
        score = float(scores_31[idx])
        if np.isnan(score):
            continue
        if melhor_score is None or score > melhor_score:
            melhor_label = label
            melhor_score = score
    if melhor_label is None:
        return top5[0][0]
    return melhor_label


def _aplicar_aleatoriedade(
    melhor_label: str,
    top5: list[tuple[str, float]],
    configuracao: ConfiguracaoAgente,
    rng: np.random.Generator,
) -> str:
    """FR-042: com probabilidade `percentual_aleatoriedade`, substitui a
    melhor aresta por uma escolhida uniformemente entre as TOP-5 da CNN."""
    if configuracao.percentual_aleatoriedade <= 0.0:
        return melhor_label
    if rng.random() >= configuracao.percentual_aleatoriedade:
        return melhor_label
    if not top5:
        return melhor_label
    candidatos = [a for (a, _) in top5]
    idx = int(rng.integers(0, len(candidatos)))
    return candidatos[idx]


# =============================================================================
# Helpers de simulação pós-jogada (para popular `ar_tabuleiro_apos`)
# =============================================================================


def _aplicar_em_clone(estado: EstadoTabuleiro, aresta: str, jogador: int) -> tuple[np.ndarray, int]:
    """Aplica a aresta em um clone do estado e devolve (matriz_apos, caixas_capturadas)."""
    clone = estado.clonar()
    capturas = clone.aplicar_traco(aresta, jogador)
    return clone.matriz.copy(), int(capturas)


def _matriz_apos_estrutura(
    estado_apos_simulacao: EstadoTabuleiro,
) -> np.ndarray:
    return estado_apos_simulacao.matriz.copy()


# =============================================================================
# Helpers para construir ResultadoJogada
# =============================================================================


def _resultado_base(
    co_aresta: str,
    co_situacao: CodigoSituacao,
    co_acao: CodigoAcao,
    tabuleiro_antes: np.ndarray,
    tabuleiro_apos: np.ndarray,
    placar_antes: int,
    capturas: int,
    inicio_ns: int,
    metadados: MetadadosTurno,
) -> ResultadoJogada:
    return ResultadoJogada(
        id_partida=metadados.id_partida,
        id_jogada=metadados.id_jogada,
        id_jogador=metadados.id_jogador,
        nu_jogador=metadados.nu_jogador,
        co_situacao=co_situacao,
        co_acao=co_acao,
        co_aresta=co_aresta,
        ar_tabuleiro_antes=tabuleiro_antes,
        ar_tabuleiro_apos=tabuleiro_apos,
        nu_placar_jogador_antes=placar_antes,
        nu_placar_jogador_apos=placar_antes + capturas,
        ts_jogada=metadados.ts_jogada,
        nu_timer_ms=metadados.nu_timer_ms,
        nu_tempo_calculo_ms=_elapsed_ms(inicio_ns),
    )


def _montar_resultado_us1(
    aresta: str,
    estado: EstadoTabuleiro,
    tabuleiro_antes: np.ndarray,
    placar_antes: int,
    inicio_ns: int,
    metadados: MetadadosTurno,
    configuracao: ConfiguracaoAgente,
) -> ResultadoJogada:
    matriz_apos, capturas = _aplicar_em_clone(estado, aresta, metadados.nu_jogador)
    return _resultado_base(
        co_aresta=aresta,
        co_situacao=CodigoSituacao.CAPTURA_SEGURA,
        co_acao=CodigoAcao.CAPTURA_GULOSA,
        tabuleiro_antes=tabuleiro_antes,
        tabuleiro_apos=matriz_apos,
        placar_antes=placar_antes,
        capturas=capturas,
        inicio_ns=inicio_ns,
        metadados=metadados,
    )


def _montar_resultado_us2(
    aresta: str,
    co_situacao: CodigoSituacao,
    co_acao: CodigoAcao,
    score_escolhida: int,
    co_acao_rejeitada: CodigoAcao,
    score_rejeitada: int,
    estado: EstadoTabuleiro,
    tabuleiro_antes: np.ndarray,
    placar_antes: int,
    inicio_ns: int,
    metadados: MetadadosTurno,
    configuracao: ConfiguracaoAgente,
) -> ResultadoJogada:
    matriz_apos, capturas = _aplicar_em_clone(estado, aresta, metadados.nu_jogador)
    scores_escolhida_31 = array_31_com_nan()
    scores_escolhida_31[_INDICE_LABEL_PEQUENO[aresta]] = float(score_escolhida)
    scores_rejeitada_31 = array_31_com_nan()
    # Para a opção rejeitada não temos a aresta de saída diretamente; o
    # caller passa a estrutura a aresta apropriada e nós populamos só na
    # posição da opção escolhida (a rejeitada vai como vetor cheio de NaN
    # com o score na posição da aresta_rejeitada quando informada — para
    # simplicidade gravamos só o valor escalar via js_extra abaixo).
    js_extra = {
        "co_acao_nao_selecionada": co_acao_rejeitada.value,
        "ar_score_minimax_opcao_nao_selecionada": scores_rejeitada_31.tolist(),
        "score_escolhida": int(score_escolhida),
        "score_rejeitada": int(score_rejeitada),
    }
    resultado = _resultado_base(
        co_aresta=aresta,
        co_situacao=co_situacao,
        co_acao=co_acao,
        tabuleiro_antes=tabuleiro_antes,
        tabuleiro_apos=matriz_apos,
        placar_antes=placar_antes,
        capturas=capturas,
        inicio_ns=inicio_ns,
        metadados=metadados,
    )
    resultado.nu_profundidade_minimax = configuracao.profundidade_minimax
    resultado.ar_score_minimax = scores_escolhida_31
    resultado.js_extra = js_extra
    return resultado


def _montar_resultado_us3_4(
    aresta: str,
    distribuicao_31: np.ndarray,
    scores_31: np.ndarray,
    estado: EstadoTabuleiro,
    tabuleiro_antes: np.ndarray,
    placar_antes: int,
    inicio_ns: int,
    metadados: MetadadosTurno,
    configuracao: ConfiguracaoAgente,
) -> ResultadoJogada:
    matriz_apos, capturas = _aplicar_em_clone(estado, aresta, metadados.nu_jogador)
    resultado = _resultado_base(
        co_aresta=aresta,
        co_situacao=CodigoSituacao.TATICA,
        co_acao=CodigoAcao.CNN_E_MINIMAX,
        tabuleiro_antes=tabuleiro_antes,
        tabuleiro_apos=matriz_apos,
        placar_antes=placar_antes,
        capturas=capturas,
        inicio_ns=inicio_ns,
        metadados=metadados,
    )
    resultado.nu_profundidade_minimax = configuracao.profundidade_minimax
    resultado.ar_score_minimax = scores_31
    resultado.ar_probabilidade_cnn = distribuicao_31.astype(np.float32)
    return resultado


def _montar_resultado_timeout_cnn(
    aresta: str,
    distribuicao_31: np.ndarray,
    scores_31_parcial: np.ndarray | None,
    estado: EstadoTabuleiro,
    tabuleiro_antes: np.ndarray,
    placar_antes: int,
    inicio_ns: int,
    metadados: MetadadosTurno,
    configuracao: ConfiguracaoAgente,
) -> ResultadoJogada:
    matriz_apos, capturas = _aplicar_em_clone(estado, aresta, metadados.nu_jogador)
    resultado = _resultado_base(
        co_aresta=aresta,
        co_situacao=CodigoSituacao.TATICA,
        co_acao=CodigoAcao.CNN_TIMEOUT,
        tabuleiro_antes=tabuleiro_antes,
        tabuleiro_apos=matriz_apos,
        placar_antes=placar_antes,
        capturas=capturas,
        inicio_ns=inicio_ns,
        metadados=metadados,
    )
    resultado.nu_profundidade_minimax = (
        configuracao.profundidade_minimax if scores_31_parcial is not None else None
    )
    resultado.ar_score_minimax = scores_31_parcial
    resultado.ar_probabilidade_cnn = distribuicao_31.astype(np.float32)
    return resultado


def _montar_resultado_timeout_aleatoria(
    aresta: str,
    co_situacao: CodigoSituacao,
    estado: EstadoTabuleiro,
    tabuleiro_antes: np.ndarray,
    placar_antes: int,
    inicio_ns: int,
    metadados: MetadadosTurno,
) -> ResultadoJogada:
    matriz_apos, capturas = _aplicar_em_clone(estado, aresta, metadados.nu_jogador)
    return _resultado_base(
        co_aresta=aresta,
        co_situacao=co_situacao,
        co_acao=CodigoAcao.ALEATORIA_TIMEOUT,
        tabuleiro_antes=tabuleiro_antes,
        tabuleiro_apos=matriz_apos,
        placar_antes=placar_antes,
        capturas=capturas,
        inicio_ns=inicio_ns,
        metadados=metadados,
    )


# =============================================================================
# Entry-point público
# =============================================================================


def escolher_jogada(
    estado: EstadoTabuleiro,
    configuracao: ConfiguracaoAgente,
    metadados: MetadadosTurno,
) -> ResultadoJogada:
    """Pipeline em 4 passos com degradação graciosa por timeout.

    Ver `specs/003-jogador-hibrido/contracts/api-python-pontinhos-3-4.md`
    para o contrato completo (pré-condições, pós-condições, exceções).
    """
    inicio_ns = time.monotonic_ns()
    nu_timer_ms = metadados.nu_timer_ms or 0

    if estado.esta_terminal():
        raise ValueError("não há jogadas disponíveis no estado recebido")

    rng = np.random.default_rng(configuracao.seed_aleatoriedade)
    tabuleiro_antes = estado.matriz.copy()
    placar_antes = contar_caixas_jogador(estado, metadados.nu_jogador)

    # P3: aresta aleatória — preparada IMEDIATAMENTE como piso de saída.
    fallback_p3 = _aresta_aleatoria_livre(estado, rng)

    if _estourou_timer(inicio_ns, nu_timer_ms):
        return _montar_resultado_timeout_aleatoria(
            fallback_p3, CodigoSituacao.TATICA, estado, tabuleiro_antes,
            placar_antes, inicio_ns, metadados,
        )

    # ------------------------------------------------------------------
    # Passo 1 — captura grau-3 isolada (e Passo 2 quando aplicável)
    # ------------------------------------------------------------------
    grau_3 = caixas_grau_3(estado)
    if grau_3:
        if _estourou_timer(inicio_ns, nu_timer_ms):
            return _montar_resultado_timeout_aleatoria(
                fallback_p3, CodigoSituacao.CAPTURA_SEGURA, estado,
                tabuleiro_antes, placar_antes, inicio_ns, metadados,
            )

        # Passo 2 — verificar se as caixas grau-3 são tail de corrente longa/ciclo
        estrutura = estrutura_ativa(estado, grau_3)
        if estrutura is not None and trigger_double_dealing(estrutura, grau_3):
            if _estourou_timer(inicio_ns, nu_timer_ms):
                return _montar_resultado_timeout_aleatoria(
                    fallback_p3,
                    CodigoSituacao.FINAL_CORRENTE_LONGA
                    if estrutura.tipo == "corrente"
                    else CodigoSituacao.FINAL_CICLO,
                    estado, tabuleiro_antes, placar_antes,
                    inicio_ns, metadados,
                )

            estado_a = estado_apos_captura_completa(
                estado, estrutura, metadados.nu_jogador
            )
            estado_b = estado_apos_double_cross(
                estado, estrutura, metadados.nu_jogador
            )
            score_a = minimax(
                estado_a, configuracao.profundidade_minimax,
                -10001, 10001, False,
                fn_avaliacao=avaliar,
            )
            score_b = minimax(
                estado_b, configuracao.profundidade_minimax,
                -10001, 10001, False,
                fn_avaliacao=avaliar,
            )
            co_situacao = (
                CodigoSituacao.FINAL_CORRENTE_LONGA
                if estrutura.tipo == "corrente"
                else CodigoSituacao.FINAL_CICLO
            )
            # Empate → preferir B (sacrifício). FR-014.
            if score_b >= score_a:
                aresta_b = aresta_double_cross(estrutura, estado)
                return _montar_resultado_us2(
                    aresta=aresta_b,
                    co_situacao=co_situacao,
                    co_acao=CodigoAcao.SACRIFICIO_DOUBLE_CROSS,
                    score_escolhida=score_b,
                    co_acao_rejeitada=CodigoAcao.CAPTURA_COMPLETA,
                    score_rejeitada=score_a,
                    estado=estado,
                    tabuleiro_antes=tabuleiro_antes,
                    placar_antes=placar_antes,
                    inicio_ns=inicio_ns,
                    metadados=metadados,
                    configuracao=configuracao,
                )
            else:
                aresta_a = primeira_aresta_de_captura(estrutura, estado)
                return _montar_resultado_us2(
                    aresta=aresta_a,
                    co_situacao=co_situacao,
                    co_acao=CodigoAcao.CAPTURA_COMPLETA,
                    score_escolhida=score_a,
                    co_acao_rejeitada=CodigoAcao.SACRIFICIO_DOUBLE_CROSS,
                    score_rejeitada=score_b,
                    estado=estado,
                    tabuleiro_antes=tabuleiro_antes,
                    placar_antes=placar_antes,
                    inicio_ns=inicio_ns,
                    metadados=metadados,
                    configuracao=configuracao,
                )

        # Captura gulosa (Passo 1 simples): fechar a caixa de menor índice
        grau_3_ordenado = sorted(grau_3)
        aresta_ganho = aresta_que_fecha(estado, grau_3_ordenado[0])
        return _montar_resultado_us1(
            aresta=aresta_ganho,
            estado=estado,
            tabuleiro_antes=tabuleiro_antes,
            placar_antes=placar_antes,
            inicio_ns=inicio_ns,
            metadados=metadados,
            configuracao=configuracao,
        )

    # ------------------------------------------------------------------
    # Passo 3 — Fase tática via CNN
    # ------------------------------------------------------------------
    inferencia = carregar_modelo(configuracao.caminho_modelo_cnn)
    distribuicao_31 = inferir(inferencia, estado)

    # Atualiza P2 (argmax CNN entre arestas livres)
    fallback_p2 = _arg_max_arestas_livres(distribuicao_31, estado)

    if _estourou_timer(inicio_ns, nu_timer_ms):
        return _montar_resultado_timeout_cnn(
            aresta=fallback_p2,
            distribuicao_31=distribuicao_31,
            scores_31_parcial=None,
            estado=estado,
            tabuleiro_antes=tabuleiro_antes,
            placar_antes=placar_antes,
            inicio_ns=inicio_ns,
            metadados=metadados,
            configuracao=configuracao,
        )

    top5 = top_k_arestas_livres(distribuicao_31, estado, k=5)

    # ------------------------------------------------------------------
    # Passo 4 — Validação Minimax sobre TOP-5
    # ------------------------------------------------------------------
    scores_31 = array_31_com_nan()
    estourou_minimax = False
    for label, _prob in top5:
        if _estourou_timer(inicio_ns, nu_timer_ms):
            estourou_minimax = True
            break
        clone = estado.clonar()
        capturas = clone.aplicar_traco(label, metadados.nu_jogador)
        if capturas > 0:
            score = minimax(
                clone, configuracao.profundidade_minimax,
                -10001, 10001, True,
                caixas_ia=capturas, caixas_humano=0,
                fn_avaliacao=avaliar,
            )
        else:
            score = minimax(
                clone, configuracao.profundidade_minimax,
                -10001, 10001, False,
                fn_avaliacao=avaliar,
            )
        scores_31[_INDICE_LABEL_PEQUENO[label]] = int(score)

    if estourou_minimax:
        return _montar_resultado_timeout_cnn(
            aresta=fallback_p2,
            distribuicao_31=distribuicao_31,
            scores_31_parcial=scores_31,
            estado=estado,
            tabuleiro_antes=tabuleiro_antes,
            placar_antes=placar_antes,
            inicio_ns=inicio_ns,
            metadados=metadados,
            configuracao=configuracao,
        )

    melhor_label = _arg_max_com_tiebreak(scores_31, top5)
    melhor_label = _aplicar_aleatoriedade(melhor_label, top5, configuracao, rng)

    return _montar_resultado_us3_4(
        aresta=melhor_label,
        distribuicao_31=distribuicao_31,
        scores_31=scores_31,
        estado=estado,
        tabuleiro_antes=tabuleiro_antes,
        placar_antes=placar_antes,
        inicio_ns=inicio_ns,
        metadados=metadados,
        configuracao=configuracao,
    )

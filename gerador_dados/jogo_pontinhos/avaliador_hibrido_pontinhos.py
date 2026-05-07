"""
avaliador_hibrido_pontinhos.py
Avalia o agente híbrido ia-pontinhos-3-4 contra o Minimax em diferentes profundidades.

Usa ProcessPoolExecutor (processos, não threads) para contornar o GIL durante o
Minimax adversário. Cada worker carrega o modelo TFLite uma única vez via cache
do módulo cnn_inferencia_pontinhos_3_4.

Coleta, por partida, a telemetria de co_situacao/co_acao de cada decisão do
híbrido e agrega em distribuições para relatório gerencial de User Stories.
"""
from __future__ import annotations

import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4

import concurrent.futures
import numpy as np

from gerador_dados.jogo_pontinhos.ia_pontinhos_3_4 import escolher_jogada
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada, _scores_de_todas_jogadas
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import (
    ConfiguracaoAgente,
    MetadadosTurno,
)


# ---------------------------------------------------------------------------
# Globals de processo (inicializados uma vez por worker)
# ---------------------------------------------------------------------------

_PROC_CONFIG: ConfiguracaoAgente | None = None
_PROC_MM = None


def _mm_agent(prof: int):
    def agente(estado: EstadoTabuleiro) -> str:
        return melhor_jogada(estado, prof)
    agente.__name__ = f"Minimax(p={prof})"
    return agente


def _mm_timer_agent(prof_max: int, timer_ms: float):
    def agente(estado: EstadoTabuleiro) -> str:
        deadline = time.perf_counter() + timer_ms / 1000.0
        melhor_traco = None
        for prof in range(1, prof_max + 1):
            if time.perf_counter() >= deadline:
                break
            try:
                scores = _scores_de_todas_jogadas(estado, prof)
                melhor_valor = max(scores.values())
                melhores = [t for t, v in scores.items() if v == melhor_valor]
                melhor_traco = random.choice(melhores)
            except Exception:
                break
            if time.perf_counter() >= deadline:
                break
        if melhor_traco is None:
            melhor_traco = random.choice(estado.tracos_disponiveis())
        return melhor_traco
    agente.__name__ = f"Minimax(p<={prof_max}, {timer_ms:.0f}ms)"
    return agente


def _proc_worker_init(configuracao: ConfiguracaoAgente, prof: int, timer_mm_ms: float) -> None:
    """Executado UMA VEZ por worker ao entrar no pool. Armazena estado de processo."""
    global _PROC_CONFIG, _PROC_MM
    _PROC_CONFIG = configuracao
    _PROC_MM = _mm_timer_agent(prof, timer_mm_ms) if timer_mm_ms > 0 else _mm_agent(prof)


# ---------------------------------------------------------------------------
# Lógica de partida
# ---------------------------------------------------------------------------

def _jogar_partida(
    configuracao: ConfiguracaoAgente,
    agente_mm,
    tamanho: str,
    seed: int,
    hibrido_nu: int,
) -> dict:
    """
    Joga uma partida completa entre o agente híbrido e o Minimax.

    hibrido_nu: valor matricial do híbrido (+1 = joga 1º, -1 = joga 2º).
    Retorna dict com resultado, tempos e telemetria de cada decisão do híbrido.
    """
    if seed is not None:
        random.seed(seed)

    estado = EstadoTabuleiro.de_tamanho(tamanho)
    mm_nu = -hibrido_nu
    hibrido_turno = 1 if hibrido_nu == 1 else 2   # turno_id (1 ou 2) do híbrido
    turno_id = 1
    _VALOR_MATRIZ = {1: 1, 2: -1}

    id_partida = uuid4()
    id_jogador_hibrido = uuid4()

    tempos_hibrido_ms: list[int] = []
    tempos_mm_ms: list[float] = []
    jogadas_hibrido: list[dict] = []

    while not estado.esta_terminal():
        if turno_id == hibrido_turno:
            meta = MetadadosTurno(
                id_partida=id_partida,
                id_jogada=uuid4(),
                id_jogador=id_jogador_hibrido,
                nu_jogador=hibrido_nu,
                ts_jogada=datetime.now(timezone.utc).isoformat(),
                nu_timer_ms=None,
            )
            resultado = escolher_jogada(estado, configuracao, meta)
            tempos_hibrido_ms.append(resultado.nu_tempo_calculo_ms)
            traco = resultado.co_aresta
            # Verifica se esta jogada vai fechar caixa (para telemetria)
            clone_check = estado.clonar()
            caixas_fechadas = clone_check.aplicar_traco(traco, _VALOR_MATRIZ[turno_id])
            jogadas_hibrido.append({
                "co_situacao":         resultado.co_situacao.value,
                "co_acao":             resultado.co_acao.value,
                "nu_tempo_calculo_ms": resultado.nu_tempo_calculo_ms,
                "fechou_caixa":        caixas_fechadas > 0,
                "caixas_fechadas":     caixas_fechadas,
            })
        else:
            t0 = time.perf_counter()
            traco = agente_mm(estado)
            tempos_mm_ms.append((time.perf_counter() - t0) * 1000.0)

        caixas = estado.aplicar_traco(traco, _VALOR_MATRIZ[turno_id])
        if caixas == 0:
            turno_id = 3 - turno_id

    interior = estado.matriz[1::2, 1::2]
    p_h = int((interior == hibrido_nu).sum())
    p_m = int((interior == mm_nu).sum())

    return {
        "vencedor":               1 if p_h > p_m else (2 if p_m > p_h else 0),
        "pontos_hibrido":         p_h,
        "pontos_mm":              p_m,
        "tempo_medio_hibrido_ms": float(np.mean(tempos_hibrido_ms)) if tempos_hibrido_ms else 0.0,
        "tempo_medio_mm_ms":      float(np.mean(tempos_mm_ms)) if tempos_mm_ms else 0.0,
        "jogadas_hibrido":        jogadas_hibrido,
    }


def _proc_worker_match(args: tuple) -> dict:
    """Executa uma partida no worker. Roda em processo separado."""
    idx, hibrido_primeiro, tamanho = args
    seed = idx if hibrido_primeiro else 1000 + idx
    hibrido_nu = 1 if hibrido_primeiro else -1
    return _jogar_partida(_PROC_CONFIG, _PROC_MM, tamanho, seed, hibrido_nu)


# ---------------------------------------------------------------------------
# Agregação de telemetria
# ---------------------------------------------------------------------------

def _agregar_telemetria(jogadas: list[dict]) -> dict:
    """Agrega distribuições de co_situacao e co_acao com tempos médios.

    Também segmenta por jogadas que fecharam caixa (fechamento) para
    análise gerencial de qual user story é mais utilizada no fechamento.
    """
    total = len(jogadas)
    cnt_sit:  dict[str, int]         = defaultdict(int)
    cnt_acao: dict[str, int]         = defaultdict(int)
    t_sit:    dict[str, list[float]] = defaultdict(list)
    t_acao:   dict[str, list[float]] = defaultdict(list)

    # Contadores apenas para jogadas que fecharam caixa
    cnt_acao_fecha: dict[str, int]         = defaultdict(int)
    t_acao_fecha:   dict[str, list[float]] = defaultdict(list)
    total_caixas_fechadas = 0

    for j in jogadas:
        sit, acao, t = j["co_situacao"], j["co_acao"], float(j["nu_tempo_calculo_ms"])
        cnt_sit[sit]  += 1
        cnt_acao[acao] += 1
        t_sit[sit].append(t)
        t_acao[acao].append(t)

        if j.get("fechou_caixa", False):
            cnt_acao_fecha[acao] += 1
            t_acao_fecha[acao].append(t)
            total_caixas_fechadas += j.get("caixas_fechadas", 1)

    def _build(cnt: dict, t_dict: dict) -> dict:
        return {
            k: {
                "count":         cnt[k],
                "pct":           cnt[k] / total * 100 if total > 0 else 0.0,
                "tempo_medio_ms": float(np.mean(t_dict[k])) if t_dict[k] else 0.0,
            }
            for k in cnt
        }

    total_fecha = sum(cnt_acao_fecha.values())
    def _build_fecha(cnt: dict, t_dict: dict) -> dict:
        return {
            k: {
                "count":         cnt[k],
                "pct":           cnt[k] / total_fecha * 100 if total_fecha > 0 else 0.0,
                "tempo_medio_ms": float(np.mean(t_dict[k])) if t_dict[k] else 0.0,
            }
            for k in cnt
        }

    return {
        "total_jogadas":        total,
        "dist_situacao":        _build(cnt_sit,  t_sit),
        "dist_acao":            _build(cnt_acao, t_acao),
        "total_fechamentos":    total_fecha,
        "total_caixas_fechadas": total_caixas_fechadas,
        "dist_acao_fechamento": _build_fecha(cnt_acao_fecha, t_acao_fecha),
    }


# ---------------------------------------------------------------------------
# Avaliação paralela
# ---------------------------------------------------------------------------

def avaliar_paralelo_hibrido(
    configuracao: ConfiguracaoAgente,
    prof: int,
    nome_mm: str,
    tamanho: str,
    n_partidas: int,
    timer_mm_ms: float = 0,
    max_workers: int = 4,
    progress_callback=None,
) -> dict:
    """
    Joga n_partidas em paralelo: metade com híbrido como jogador 1, metade como jogador 2.
    Usa ProcessPoolExecutor para paralelismo real (cada worker tem seu próprio GIL e
    seu próprio interpretador TFLite, carregado uma vez no initializer).

    progress_callback(completed, total, result): chamado após cada partida concluída.
    """
    metade = n_partidas // 2
    tasks = (
        [(i, True,  tamanho) for i in range(metade)] +
        [(i, False, tamanho) for i in range(metade)]
    )

    resultados: list[dict] = []
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_proc_worker_init,
        initargs=(configuracao, prof, timer_mm_ms),
    ) as executor:
        futures = [executor.submit(_proc_worker_match, t) for t in tasks]
        for idx, f in enumerate(concurrent.futures.as_completed(futures), 1):
            result = f.result()
            resultados.append(result)
            if progress_callback is not None:
                progress_callback(idx, len(tasks), result)
            else:
                pct = idx / len(tasks) * 100
                print(f"\r  Progresso: [{idx}/{len(tasks)}] {pct:.1f}%...", end="", flush=True)
    if progress_callback is None:
        print()

    vitorias = sum(1 for r in resultados if r["vencedor"] == 1)
    derrotas  = sum(1 for r in resultados if r["vencedor"] == 2)
    empates   = sum(1 for r in resultados if r["vencedor"] == 0)

    tempos_h = [r["tempo_medio_hibrido_ms"] for r in resultados]
    tempos_m = [r["tempo_medio_mm_ms"]      for r in resultados]

    todas_jogadas = [j for r in resultados for j in r["jogadas_hibrido"]]
    telemetria = _agregar_telemetria(todas_jogadas)

    stats: dict = {
        "adversario":       nome_mm,
        "partidas":         n_partidas,
        "vitorias_hibrido": vitorias,
        "derrotas_hibrido": derrotas,
        "empates":          empates,
        "pct_vitorias":     vitorias / n_partidas * 100,
        "pct_derrotas":     derrotas / n_partidas * 100,
        "pct_empates":      empates  / n_partidas * 100,
        "tempo_hibrido_ms": float(np.mean(tempos_h)),
        "tempo_mm_ms":      float(np.mean(tempos_m)),
        "fator_velocidade": (float(np.mean(tempos_m)) / float(np.mean(tempos_h)))
                            if float(np.mean(tempos_h)) > 0 else 0.0,
        **telemetria,
    }
    if timer_mm_ms > 0:
        stats["timer_mm_ms"] = timer_mm_ms
    return stats


# ---------------------------------------------------------------------------
# Relatório gerencial
# ---------------------------------------------------------------------------

def _fmt_linha(label: str, count: int, pct: float, tempo_ms: float | None) -> str:
    t_str = f"{tempo_ms:>8.2f} ms" if tempo_ms is not None else f"{'—':>11}"
    return f"  {label:<40} {count:>6}  {pct:>5.1f}%  {t_str}"


def imprimir_relatorio_hibrido(stats_list: list[dict]) -> None:
    """
    Imprime relatório gerencial com:
      - Resultado (vitórias / empates / derrotas) e comparativo de velocidade.
      - Distribuição de User Stories por decisão do híbrido, com tempos médios.
    """
    print()
    print("=" * 72)
    titulo = "AVALIAÇÃO POR PARTIDAS REAIS — ia-pontinhos-3-4 vs Minimax"
    if stats_list and stats_list[0].get("timer_mm_ms"):
        titulo += f"  (timer MM: {stats_list[0]['timer_mm_ms']:.0f}ms/jogada)"
    print(titulo)
    print("=" * 72)

    for s in stats_list:
        print(f"\n  Adversário: {s['adversario']}  ({s['partidas']} partidas)")
        print(f"  {'Vitórias Híbrido':26} {s['vitorias_hibrido']:4d}  ({s['pct_vitorias']:5.1f}%)")
        print(f"  {'Empates':26} {s['empates']:4d}  ({s['pct_empates']:5.1f}%)")
        print(f"  {'Derrotas Híbrido':26} {s['derrotas_hibrido']:4d}  ({s['pct_derrotas']:5.1f}%)")
        print(f"  Tempo médio Híbrido:      {s['tempo_hibrido_ms']:.2f} ms/jogada")
        print(f"  Tempo médio {s['adversario']}: {s['tempo_mm_ms']:.1f} ms/jogada")
        fator = s['fator_velocidade']
        print(f"  Híbrido é {fator:.0f}× mais rápido")

        total = s.get("total_jogadas", 0)
        if total == 0:
            continue

        dist_acao = s.get("dist_acao", {})

        print()
        print(f"  ── Decisões do Híbrido ({total} jogadas) {'─' * 31}")
        print(f"  {'User Story / Situação':<40} {'Jogadas':>6}  {'%':>6}  {'Tempo médio':>11}")
        print(f"  {'─' * 68}")

        # US1 — Captura Segura
        us1 = dist_acao.get("captura_gulosa", {})
        print(_fmt_linha(
            "US1 — Captura Segura (grau-3)",
            us1.get("count", 0), us1.get("pct", 0.0), us1.get("tempo_medio_ms", 0.0),
        ))

        # US2 — Exceção do Sacrifício
        cc = dist_acao.get("captura_completa", {})
        dc = dist_acao.get("sacrificio_double_cross", {})
        cnt_us2 = cc.get("count", 0) + dc.get("count", 0)
        pct_us2 = cc.get("pct", 0.0) + dc.get("pct", 0.0)
        t_us2_pool = (
            [cc.get("tempo_medio_ms", 0.0)] * cc.get("count", 0) +
            [dc.get("tempo_medio_ms", 0.0)] * dc.get("count", 0)
        )
        t_us2 = float(np.mean(t_us2_pool)) if t_us2_pool else 0.0
        print(_fmt_linha("US2 — Exceção do Sacrifício", cnt_us2, pct_us2, t_us2))
        if cc.get("count", 0):
            print(_fmt_linha(
                "    └─ captura_completa",
                cc["count"], cc["pct"], cc["tempo_medio_ms"],
            ))
        if dc.get("count", 0):
            print(_fmt_linha(
                "    └─ sacrificio_double_cross",
                dc["count"], dc["pct"], dc["tempo_medio_ms"],
            ))

        # US3+4 — CNN + Minimax
        cm = dist_acao.get("cnn_e_minimax", {})
        print(_fmt_linha(
            "US3+4 — CNN + Minimax Validado",
            cm.get("count", 0), cm.get("pct", 0.0), cm.get("tempo_medio_ms", 0.0),
        ))

        # Timeouts (fallback — só aparecem com timer ativo)
        cto = dist_acao.get("cnn_timeout", {})
        ato = dist_acao.get("aleatoria_timeout", {})
        cnt_to = cto.get("count", 0) + ato.get("count", 0)
        pct_to = cto.get("pct", 0.0) + ato.get("pct", 0.0)
        print(_fmt_linha("Timeouts (fallback)", cnt_to, pct_to, None))

        print(f"  {'─' * 68}")

        # Seção: Fechamento de caixas por User Story
        dist_fecha = s.get("dist_acao_fechamento", {})
        total_fecha = s.get("total_fechamentos", 0)
        total_caixas = s.get("total_caixas_fechadas", 0)
        if total_fecha > 0:
            print()
            print(f"  ── Fechamento de Caixas ({total_caixas} caixas em {total_fecha} jogadas) {'─' * 18}")
            print(f"  {'User Story (fechamento)':<40} {'Jogadas':>6}  {'%':>6}  {'Tempo médio':>11}")
            print(f"  {'─' * 68}")

            us1f = dist_fecha.get("captura_gulosa", {})
            print(_fmt_linha(
                "US1 — Captura Segura",
                us1f.get("count", 0), us1f.get("pct", 0.0), us1f.get("tempo_medio_ms", 0.0),
            ))

            ccf = dist_fecha.get("captura_completa", {})
            dcf = dist_fecha.get("sacrificio_double_cross", {})
            cnt_us2f = ccf.get("count", 0) + dcf.get("count", 0)
            pct_us2f = ccf.get("pct", 0.0) + dcf.get("pct", 0.0)
            t_us2f_pool = (
                [ccf.get("tempo_medio_ms", 0.0)] * ccf.get("count", 0) +
                [dcf.get("tempo_medio_ms", 0.0)] * dcf.get("count", 0)
            )
            t_us2f = float(np.mean(t_us2f_pool)) if t_us2f_pool else 0.0
            print(_fmt_linha("US2 — Exceção do Sacrifício", cnt_us2f, pct_us2f, t_us2f))
            if ccf.get("count", 0):
                print(_fmt_linha(
                    "    └─ captura_completa",
                    ccf["count"], ccf["pct"], ccf["tempo_medio_ms"],
                ))
            if dcf.get("count", 0):
                print(_fmt_linha(
                    "    └─ sacrificio_double_cross",
                    dcf["count"], dcf["pct"], dcf["tempo_medio_ms"],
                ))

            cmf = dist_fecha.get("cnn_e_minimax", {})
            print(_fmt_linha(
                "US3+4 — CNN + Minimax Validado",
                cmf.get("count", 0), cmf.get("pct", 0.0), cmf.get("tempo_medio_ms", 0.0),
            ))

            print(f"  {'─' * 68}")

            # Tempo médio do Minimax adversário no fechamento
            print(f"  Tempo médio Minimax adversário: {s['tempo_mm_ms']:.1f} ms/jogada (referência)")

    print()
    print("=" * 72)

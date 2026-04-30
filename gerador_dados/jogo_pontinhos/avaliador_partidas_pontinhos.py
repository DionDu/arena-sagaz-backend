"""
avaliador_partidas.py
Avalia a CNN jogando partidas reais contra o Minimax em diferentes profundidades.

Uso:
    python -m gerador_dados.avaliador_partidas \
        --modelo modelos/arena_sagaz_pequeno.tflite \
        --tamanho pequeno \
        --partidas 200 \
        --profundidades 1 3 5 6

    # Com timer (comparação justa por orçamento de tempo):
    python -m gerador_dados.avaliador_partidas \
        --modelo modelos/pontinhos_pequeno.tflite \
        --tamanho pequeno \
        --partidas 200 \
        --profundidades 1 3 5 6 \
        --timer 5
"""
import argparse
import time
import random
import threading
import numpy as np
import concurrent.futures

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, todos_labels_canonicos
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada, _scores_de_todas_jogadas
from gerador_dados.jogo_pontinhos.contrato_codificacao_pontinhos import (
    CONTEXTO_PARTIDA,
    normalizar_para_cnn,
)


# ---------------------------------------------------------------------------
# Agentes
# ---------------------------------------------------------------------------

def _minimax_agent_fn(profundidade: int):
    """Retorna uma função-agente que usa o Minimax na profundidade dada."""
    def agente(estado: EstadoTabuleiro) -> str:
        return melhor_jogada(estado, profundidade)
    agente.__name__ = f"Minimax(p={profundidade})"
    return agente


def _minimax_timer_agent_fn(profundidade_max: int, timer_ms: float):
    """Retorna um agente Minimax com iterative deepening e orçamento de tempo.
    
    Começa na profundidade 1 e aumenta até profundidade_max. Se o tempo
    estourar antes de completar uma profundidade, retorna a melhor jogada
    encontrada na profundidade anterior.
    """
    def agente(estado: EstadoTabuleiro) -> str:
        import random
        deadline = time.perf_counter() + timer_ms / 1000.0
        melhor_traco = None
        prof_alcancada = 0
        
        for prof in range(1, profundidade_max + 1):
            if time.perf_counter() >= deadline:
                break
            try:
                scores = _scores_de_todas_jogadas(estado, prof)
                melhor_valor = max(scores.values())
                melhores = [t for t, v in scores.items() if v == melhor_valor]
                melhor_traco = random.choice(melhores)
                prof_alcancada = prof
            except Exception:
                break
            if time.perf_counter() >= deadline:
                break
        
        # Fallback: se nem profundidade 1 completou, joga aleatório
        if melhor_traco is None:
            melhor_traco = random.choice(estado.tracos_disponiveis())
        
        # Armazena a profundidade alcançada como atributo para métricas
        agente._ultima_prof = prof_alcancada
        return melhor_traco
    
    agente.__name__ = f"Minimax(p<={profundidade_max}, {timer_ms:.0f}ms)"
    agente._ultima_prof = 0
    return agente


def _cnn_agent_fn(caminho_modelo: str, labels: list[str]):
    """Retorna uma função-agente que usa o modelo TFLite.

    O `tflite.Interpreter` NÃO é thread-safe: chamar `invoke()` em paralelo
    com o mesmo Interpreter gera `RuntimeError: There is at least 1 reference
    to internal data in the interpreter...`. Para suportar execução em
    `ThreadPoolExecutor`, usamos `threading.local()` — cada thread cria e
    mantém o seu próprio Interpreter (e seus tensores I/O) na primeira
    chamada.
    """
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        import tensorflow.lite as tflite  # type: ignore

    idx_label = {l: i for i, l in enumerate(labels)}
    _local = threading.local()

    def _get_interp():
        interp = getattr(_local, "interp", None)
        if interp is None:
            interp = tflite.Interpreter(model_path=caminho_modelo)
            interp.allocate_tensors()
            _local.interp = interp
            _local.inp = interp.get_input_details()[0]["index"]
            _local.out = interp.get_output_details()[0]["index"]
        return _local.interp, _local.inp, _local.out

    def agente(estado: EstadoTabuleiro) -> str:
        # Normalização conforme contrato_codificacao_pontinhos.json, contexto 3 (partidas).
        # NUNCA duplicar as regras aqui — consulte o JSON e o helper.
        mat = normalizar_para_cnn(estado.matriz, CONTEXTO_PARTIDA)
        X = mat.reshape(1, mat.shape[0], mat.shape[1], 1)
        interp, inp, out = _get_interp()
        interp.set_tensor(inp, X)
        interp.invoke()
        probs = interp.get_tensor(out)[0]          # (31,)
        disponiveis = estado.tracos_disponiveis()
        melhor = max(disponiveis, key=lambda t: probs[idx_label[t]])
        return melhor

    agente.__name__ = "CNN"
    return agente


# ---------------------------------------------------------------------------
# Lógica de partida
# ---------------------------------------------------------------------------

def _localizar_caixas_prontas(matriz: np.ndarray) -> list[tuple[int, int]]:
    """Retorna posições (linha, coluna) — em coords de caixa — com 3 arestas preenchidas."""
    linhas  = (matriz.shape[0] - 1) // 2
    colunas = (matriz.shape[1] - 1) // 2
    out: list[tuple[int, int]] = []
    for r in range(linhas):
        for c in range(colunas):
            if matriz[2*r+1, 2*c+1] != 0:
                continue  # já fechada
            preenchidas = (
                int(matriz[2*r,   2*c+1] != 0) +
                int(matriz[2*r+2, 2*c+1] != 0) +
                int(matriz[2*r+1, 2*c  ] != 0) +
                int(matriz[2*r+1, 2*c+2] != 0)
            )
            if preenchidas == 3:
                out.append((r, c))
    return out


def _contar_caixas_prontas(matriz: np.ndarray) -> int:
    """Conta caixas com exatamente 3 arestas preenchidas (prontas para fechar)."""
    return len(_localizar_caixas_prontas(matriz))


def jogar_partida(
    agente1,
    agente2,
    tamanho: str = "pequeno",
    seed: int | None = None,
    capturar_misses_de: int | None = None,
) -> dict:
    """
    Joga uma partida completa entre dois agentes.
    Retorna dict com pontos, tempos e vencedor.

    Se `capturar_misses_de` for 1 ou 2, cada vez que o agente correspondente
    deixar de fechar uma caixa pronta, um snapshot do estado é registrado em
    `result["eventos_misses"]` para visualização posterior.
    """
    if seed is not None:
        random.seed(seed)

    estado = EstadoTabuleiro.de_tamanho(tamanho)
    # turno_id: 1 = agente1, 2 = agente2 (lógico, para controle de turnos/tempos)
    # valor_matriz: 1 = agente1, -1 = agente2 (valor gravado na matriz do tabuleiro,
    #   compatível com minimax.py e com os dados de treino da CNN)
    turno_id = 1
    tempos = {1: [], 2: []}
    profs_alcancadas = {1: [], 2: []}  # profundidades efetivas (para timer)
    oportunidades_perdidas = {1: 0, 2: 0}  # turno com caixa pronta mas não fechou
    oportunidades_total    = {1: 0, 2: 0}  # turnos em que havia caixa pronta
    _VALOR_MATRIZ = {1: 1, 2: -1}

    eventos_misses: list[dict] = []
    numero_jogada = 0

    while not estado.esta_terminal():
        agente = agente1 if turno_id == 1 else agente2
        numero_jogada += 1

        caixas_prontas_pos = _localizar_caixas_prontas(estado.matriz)
        caixas_prontas = len(caixas_prontas_pos)
        if caixas_prontas > 0:
            oportunidades_total[turno_id] += 1

        # Só copia a matriz se houver chance de virar evento (otimização).
        matriz_antes = None
        if (
            capturar_misses_de is not None
            and capturar_misses_de == turno_id
            and caixas_prontas > 0
        ):
            matriz_antes = estado.matriz.copy()

        t0 = time.perf_counter()
        traco = agente(estado)
        tempos[turno_id].append(time.perf_counter() - t0)
        # Registra profundidade alcançada se o agente suporta (timer)
        if hasattr(agente, '_ultima_prof'):
            profs_alcancadas[turno_id].append(agente._ultima_prof)

        caixas = estado.aplicar_traco(traco, _VALOR_MATRIZ[turno_id])

        if caixas_prontas > 0 and caixas == 0:
            oportunidades_perdidas[turno_id] += 1
            if matriz_antes is not None:
                interior = estado.matriz[1::2, 1::2]
                eventos_misses.append({
                    "numero_jogada":      numero_jogada,
                    "turno_id":           turno_id,
                    "matriz_antes":       matriz_antes,
                    "traco_jogado":       traco,
                    "caixas_prontas_pos": caixas_prontas_pos,
                    "placar_a1":          int((interior == 1).sum()),
                    "placar_a2":          int((interior == -1).sum()),
                })

        if caixas == 0:
            turno_id = 3 - turno_id   # alterna apenas se não fechou caixa

    # Conta caixas por jogador via interior da matriz (posições ímpar×ímpar)
    interior = estado.matriz[1::2, 1::2]
    p1 = int((interior == 1).sum())     # agente1 marca com 1
    p2 = int((interior == -1).sum())    # agente2 marca com -1

    if p1 > p2:
        vencedor = 1
    elif p2 > p1:
        vencedor = 2
    else:
        vencedor = 0   # empate

    result = {
        "pontos_a1": p1,
        "pontos_a2": p2,
        "vencedor": vencedor,          # 1=agente1, 2=agente2, 0=empate
        "tempo_medio_a1_ms": np.mean(tempos[1]) * 1000 if tempos[1] else 0,
        "tempo_medio_a2_ms": np.mean(tempos[2]) * 1000 if tempos[2] else 0,
        "opp_perdidas_a1": oportunidades_perdidas[1],
        "opp_total_a1":    oportunidades_total[1],
        "opp_perdidas_a2": oportunidades_perdidas[2],
        "opp_total_a2":    oportunidades_total[2],
        "eventos_misses":  eventos_misses,
    }
    # Adiciona profundidade média alcançada se disponível
    for tid in [1, 2]:
        if profs_alcancadas[tid]:
            result[f"prof_media_a{tid}"] = np.mean(profs_alcancadas[tid])
    return result


# ---------------------------------------------------------------------------
# Avaliação em série (Paralela e Sequencial)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Workers para ProcessPoolExecutor
# ---------------------------------------------------------------------------
# Por que processos e não threads: o Minimax é Python puro e mantém o GIL
# durante toda a busca. Num ThreadPoolExecutor, 4 threads rodando minimax
# serializam no GIL, usando efetivamente 1 core. Com processos, cada worker
# tem seu próprio GIL e roda em paralelo de verdade. O custo é carregar o
# TFLite uma vez por processo (pago no initializer), não por partida.

_PROC_CNN = None   # agente CNN por processo (inicializado em _proc_worker_init)
_PROC_MM  = None   # agente Minimax por processo


def _proc_worker_init(caminho_modelo, labels, prof, timer_ms):
    """Executado UMA VEZ por processo-worker ao entrar na pool.

    Carrega o TFLite (pesado) e cria o agente Minimax apenas aqui, para que
    o custo seja amortizado entre todas as partidas daquele worker.
    """
    global _PROC_CNN, _PROC_MM
    _PROC_CNN = _cnn_agent_fn(caminho_modelo, labels)
    if timer_ms and timer_ms > 0:
        _PROC_MM = _minimax_timer_agent_fn(prof, timer_ms)
    else:
        _PROC_MM = _minimax_agent_fn(prof)


def _proc_worker_match(args):
    """Executa uma partida CNN vs Minimax. Roda em processo-worker separado."""
    idx, cnn_primeiro, tamanho = args

    if cnn_primeiro:
        r = jogar_partida(_PROC_CNN, _PROC_MM, tamanho, seed=idx, capturar_misses_de=1)
        r["cnn_primeiro"] = True
        # Decora cada evento com info que o main process precisa para visualizar.
        # CNN era turno 1 → _VALOR_MATRIZ[1] = 1 (azul nas caixas dela).
        for e in r.get("eventos_misses", []):
            e["partida_idx"]      = idx
            e["cnn_primeiro"]     = True
            e["cnn_valor_matriz"] = 1
            e["placar_cnn"]       = e["placar_a1"]
            e["placar_mm"]        = e["placar_a2"]
        return r

    r = jogar_partida(_PROC_MM, _PROC_CNN, tamanho, seed=1000 + idx, capturar_misses_de=2)
    r_inv = {
        "pontos_a1": r["pontos_a2"],
        "pontos_a2": r["pontos_a1"],
        "vencedor": 0 if r["vencedor"] == 0 else 3 - r["vencedor"],
        "tempo_medio_a1_ms": r["tempo_medio_a2_ms"],
        "tempo_medio_a2_ms": r["tempo_medio_a1_ms"],
        "cnn_primeiro": False,
    }
    # Preserva prof_media invertendo perspectiva
    if "prof_media_a1" in r:
        r_inv["prof_media_a2"] = r["prof_media_a1"]
    if "prof_media_a2" in r:
        r_inv["prof_media_a1"] = r["prof_media_a2"]
    # Inverte oportunidades perdidas (CNN era a2, passa a ser a1)
    r_inv["opp_perdidas_a1"] = r.get("opp_perdidas_a2", 0)
    r_inv["opp_total_a1"]    = r.get("opp_total_a2",    0)
    r_inv["opp_perdidas_a2"] = r.get("opp_perdidas_a1", 0)
    r_inv["opp_total_a2"]    = r.get("opp_total_a1",    0)
    # CNN era turno 2 → _VALOR_MATRIZ[2] = -1 (caixas dela aparecem como -1 na matriz).
    eventos = r.get("eventos_misses", [])
    for e in eventos:
        e["partida_idx"]      = idx
        e["cnn_primeiro"]     = False
        e["cnn_valor_matriz"] = -1
        e["placar_cnn"]       = e["placar_a2"]
        e["placar_mm"]        = e["placar_a1"]
    r_inv["eventos_misses"] = eventos
    return r_inv


def avaliar_paralelo(
    caminho_modelo: str,
    labels: list[str],
    prof: int,
    nome_mm: str,
    tamanho: str,
    n_partidas: int,
    timer_ms: float = 0,
    max_workers: int = 4,
    progress_callback=None,
    salvar_caixas_perdidas_em=None,
) -> dict:
    """
    Joga n_partidas em paralelo: metade com CNN como jogador 1, metade como jogador 2.
    Usa ProcessPoolExecutor para contornar o GIL durante o Minimax (Python puro).
    Se timer_ms > 0, o Minimax usa iterative deepening com orçamento de tempo.
    """
    metade = n_partidas // 2
    tasks = []
    for i in range(metade):
        tasks.append((i, True, tamanho))
    for i in range(metade):
        tasks.append((i, False, tamanho))

    resultados = []
    # ProcessPoolExecutor: cada processo tem seu próprio GIL e seu próprio
    # TFLite Interpreter. max_workers=4 é um bom default para Ryzen 8-core
    # (sobra folga para o kernel/SO). Ajustável via parâmetro.
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_proc_worker_init,
        initargs=(caminho_modelo, labels, prof, timer_ms),
    ) as executor:
        futures = [executor.submit(_proc_worker_match, t) for t in tasks]
        for idx, f in enumerate(concurrent.futures.as_completed(futures), 1):
            result = f.result()
            resultados.append(result)
            if progress_callback is not None:
                progress_callback(idx, len(tasks), result)
            else:
                perc = idx / len(tasks) * 100
                print(f"\r  Progresso: [{idx}/{len(tasks)}] {perc:.1f}% concluído...", end="", flush=True)
    if progress_callback is None:
        print()  # quebra a linha ao terminar

    vitorias_cnn = sum(1 for r in resultados if r["vencedor"] == 1)
    derrotas_cnn = sum(1 for r in resultados if r["vencedor"] == 2)
    empates      = sum(1 for r in resultados if r["vencedor"] == 0)

    tempos_cnn = [r["tempo_medio_a1_ms"] for r in resultados]
    tempos_mm  = [r["tempo_medio_a2_ms"] for r in resultados]

    opp_perdidas_cnn = sum(r.get("opp_perdidas_a1", 0) for r in resultados)
    opp_total_cnn    = sum(r.get("opp_total_a1",    0) for r in resultados)

    # Salva PNG+MD para cada momento em que a CNN cedeu uma caixa pronta.
    # A quantidade de arquivos por chamada bate com `opp_perdidas_cnn`.
    n_eventos_salvos = 0
    if salvar_caixas_perdidas_em is not None:
        from pathlib import Path
        from gerador_dados.jogo_pontinhos.visualizador_pontinhos import (
            salvar_evento_caixa_perdida,
        )
        out_dir = Path(salvar_caixas_perdidas_em)
        out_dir.mkdir(parents=True, exist_ok=True)
        contexto = {"adversario": nome_mm, "exec_id": out_dir.parent.name}
        for r in resultados:
            for e in r.get("eventos_misses", []):
                pos = "cnn1" if e.get("cnn_primeiro") else "cnn2"
                base = (
                    f"{pos}_partida{int(e['partida_idx']):03d}"
                    f"_jogada{int(e['numero_jogada']):03d}"
                )
                salvar_evento_caixa_perdida(
                    e,
                    out_dir / f"{base}.png",
                    out_dir / f"{base}.md",
                    contexto,
                )
                n_eventos_salvos += 1
        print(f"  Eventos de caixa perdida salvos: {n_eventos_salvos} -> {out_dir}")

    stats = {
        "adversario":     nome_mm,
        "partidas":       n_partidas,
        "vitorias_cnn":   vitorias_cnn,
        "derrotas_cnn":   derrotas_cnn,
        "empates":        empates,
        "pct_vitorias":   vitorias_cnn / n_partidas * 100,
        "pct_derrotas":   derrotas_cnn / n_partidas * 100,
        "pct_empates":    empates      / n_partidas * 100,
        "tempo_cnn_ms":   np.mean(tempos_cnn),
        "tempo_mm_ms":    np.mean(tempos_mm),
        "fator_velocidade": np.mean(tempos_mm) / np.mean(tempos_cnn) if np.mean(tempos_cnn) > 0 else 0,
        "opp_perdidas_cnn": opp_perdidas_cnn,
        "opp_total_cnn":    opp_total_cnn,
        "eventos_salvos":   n_eventos_salvos,
    }
    # Se timer ativo, calcula profundidade média alcançada pelo Minimax
    if timer_ms > 0:
        profs = []
        for r in resultados:
            # prof_media está em a2 quando CNN é primeiro, a1 quando CNN é segundo
            if r.get("cnn_primeiro"):
                if "prof_media_a2" in r:
                    profs.append(r["prof_media_a2"])
            else:
                if "prof_media_a1" in r:  # invertido na perspectiva
                    profs.append(r["prof_media_a1"])
        if profs:
            stats["prof_media_mm"] = np.mean(profs)
        stats["timer_ms"] = timer_ms
    return stats


def avaliar(
    agente_cnn,
    agente_mm,
    nome_mm: str,
    tamanho: str,
    n_partidas: int,
) -> dict:
    """
    Versão sequencial original (mantida para compatibilidade).
    """
    metade = n_partidas // 2
    resultados = []

    for i in range(metade):
        r = jogar_partida(agente_cnn, agente_mm, tamanho, seed=i)
        r["cnn_primeiro"] = True
        resultados.append(r)

    for i in range(metade):
        r = jogar_partida(agente_mm, agente_cnn, tamanho, seed=1000 + i)
        r_inv = {
            "pontos_a1": r["pontos_a2"],   
            "pontos_a2": r["pontos_a1"],   
            "vencedor": 2 - r["vencedor"] if r["vencedor"] != 0 else 0,
            "tempo_medio_a1_ms": r["tempo_medio_a2_ms"],  
            "tempo_medio_a2_ms": r["tempo_medio_a1_ms"],  
            "cnn_primeiro": False,
        }
        if r["vencedor"] == 2:
            r_inv["vencedor"] = 1
        elif r["vencedor"] == 1:
            r_inv["vencedor"] = 2
        resultados.append(r_inv)

    vitorias_cnn = sum(1 for r in resultados if r["vencedor"] == 1)
    derrotas_cnn = sum(1 for r in resultados if r["vencedor"] == 2)
    empates      = sum(1 for r in resultados if r["vencedor"] == 0)

    tempos_cnn = [r["tempo_medio_a1_ms"] for r in resultados]
    tempos_mm  = [r["tempo_medio_a2_ms"] for r in resultados]

    return {
        "adversario":     nome_mm,
        "partidas":       n_partidas,
        "vitorias_cnn":   vitorias_cnn,
        "derrotas_cnn":   derrotas_cnn,
        "empates":        empates,
        "pct_vitorias":   vitorias_cnn / n_partidas * 100,
        "pct_derrotas":   derrotas_cnn / n_partidas * 100,
        "pct_empates":    empates      / n_partidas * 100,
        "tempo_cnn_ms":   np.mean(tempos_cnn),
        "tempo_mm_ms":    np.mean(tempos_mm),
        "fator_velocidade": np.mean(tempos_mm) / np.mean(tempos_cnn) if np.mean(tempos_cnn) > 0 else 0,
    }


def imprimir_relatorio(stats_list: list[dict]) -> None:
    print()
    print("=" * 72)
    titulo = "AVALIAÇÃO POR PARTIDAS REAIS — CNN vs Minimax"
    if stats_list and stats_list[0].get("timer_ms"):
        titulo += f" (timer: {stats_list[0]['timer_ms']:.0f}ms/jogada)"
    print(titulo)
    print("=" * 72)

    for s in stats_list:
        print(f"\n  Adversário: {s['adversario']}  ({s['partidas']} partidas)")
        print(f"  {'Vitórias CNN':20} {s['vitorias_cnn']:4d}  ({s['pct_vitorias']:5.1f}%)")
        print(f"  {'Empates':20} {s['empates']:4d}  ({s['pct_empates']:5.1f}%)")
        print(f"  {'Derrotas CNN':20} {s['derrotas_cnn']:4d}  ({s['pct_derrotas']:5.1f}%)")
        print(f"  Tempo médio CNN:  {s['tempo_cnn_ms']:.2f} ms/jogada")
        print(f"  Tempo médio {s['adversario']}: {s['tempo_mm_ms']:.1f} ms/jogada")
        print(f"  CNN é {s['fator_velocidade']:.0f}× mais rápida")
        if s.get("opp_total_cnn", 0) > 0:
            opp = s["opp_perdidas_cnn"]
            tot = s["opp_total_cnn"]
            print(f"  Caixas deixadas p/ Minimax: {opp:4d} / {tot:4d} oportunidades ({opp/tot*100:.1f}%)")
        if "prof_media_mm" in s:
            print(f"  Profundidade média alcançada pelo Minimax: {s['prof_media_mm']:.1f}")

    print()
    print("=" * 72)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Avalia CNN vs Minimax em partidas reais.")
    parser.add_argument("--modelo",       required=True, help="Caminho para .tflite")
    parser.add_argument("--tamanho",      default="pequeno", choices=["pequeno", "medio", "grande"])
    parser.add_argument("--partidas",     type=int, default=200, help="Total de partidas por profundidade")
    parser.add_argument("--profundidades",type=int, nargs="+", default=[1, 3, 5, 6])
    parser.add_argument("--timer",        type=float, default=0,
                        help="Tempo máximo por jogada do Minimax em ms. "
                             "Se > 0, usa iterative deepening e retorna a melhor "
                             "jogada encontrada dentro do orçamento de tempo. "
                             "Exemplo: --timer 5 (5ms = mesmo orçamento da CNN).")
    parser.add_argument("--workers",      type=int, default=4,
                        help="Número de processos-worker paralelos. "
                             "Default 4 é bom para CPUs 8-core. Em máquinas "
                             "mais fortes (>=12 cores) pode aumentar para 6-8.")
    args = parser.parse_args()

    labels = todos_labels_canonicos(4, 3) if args.tamanho == "pequeno" else todos_labels_canonicos(5, 4)

    print(f"Carregando CNN: {args.modelo}")
    if args.timer > 0:
        print(f"Timer ativo: Minimax limitado a {args.timer:.0f}ms por jogada (iterative deepening)")

    stats_list = []
    for prof in args.profundidades:
        if args.timer > 0:
            nome = f"Minimax(p<={prof}, {args.timer:.0f}ms)"
        else:
            nome = f"Minimax(p={prof})"
        print(f"Avaliando contra {nome} ({args.partidas} partidas)...")
        s = avaliar_paralelo(args.modelo, labels, prof, nome, args.tamanho, args.partidas, args.timer, max_workers=args.workers)
        stats_list.append(s)

    imprimir_relatorio(stats_list)


if __name__ == "__main__":
    main()

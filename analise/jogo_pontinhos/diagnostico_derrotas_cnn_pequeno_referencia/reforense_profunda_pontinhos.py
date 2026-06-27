"""Re-forense profunda — localiza o lance do MEIO-JOGO onde a paridade vira.

O piloto mostrou que ~98% das derrotas já estão perdidas ao entrar no endgame
(t≈19). Logo a derrota nasce no meio-jogo (t<18), fora da janela da forense
padrão. Este módulo **reproduz apenas os seeds das derrotas** (lidos do
`derrotas.csv` de uma rodada) e roda a forense de value-swing com profundidade
MAIOR — empurrando a janela exata para t menor (janela = t ≥ 31−prof).

Como são só dezenas de jogos, dá para ir fundo (p=15→19) sem custo proibitivo.
A configuração (modelo, adversário, eps, abertura…) é lida do `checkpoint.json`
da rodada, garantindo replay idêntico.

Uso (a partir da raiz do repo; use .venv_tf por causa do TFLite):

    .venv_tf\\Scripts\\python -m analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.reforense_profunda_pontinhos \\
        --run-id piloto_v2 --prof-forense 17 --workers 14
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

# IMPORTANTE: 1 thread de BLAS por processo. Com N workers, cada um abrindo
# OpenBLAS/OMP com ~n_cores threads há oversubscrição (N*16) que estoura a
# memória ("OpenBLAS Memory allocation failed"). Como cada worker roda 1 jogo
# por vez, BLAS single-thread é suficiente E mais rápido (sem contenção).
# Precisa vir ANTES de importar numpy (e é reexecutado nos workers via spawn).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np

_RAIZ = Path(__file__).resolve().parents[3]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import todos_labels_canonicos  # noqa: E402
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada  # noqa: E402
from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.adversarios_pontinhos import (  # noqa: E402
    agente_minimax_descuidado,
)
from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.arena_pontinhos import (  # noqa: E402
    jogar_partida_instrumentada,
)
from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.forense_value_swing_pontinhos import (  # noqa: E402
    analisar_partida,
)

_DIMS = {"pequeno": (4, 3), "medio": (5, 4), "grande": (7, 5)}

# Globais de worker (mesmo padrão do executar_diagnostico)
_W_REF = None
_W_ADV = None
_W_CFG: dict = {}
_W_PROBS = None   # extrator de probabilidades da CNN (None se referência for stand-in)

# Campos extras de perfil de confiança da CNN, anexados a cada erro.
# `probs_json` = vetor de saída COMPLETO da CNN (31 labels -> probabilidade bruta),
# serializado em JSON, para qualquer análise posterior sem re-inferir.
CAMPOS_PROBS = ["prob_argmax", "prob_2a", "margem_top2", "prob_jogada_minimax",
                "rank_minimax", "entropia", "probs_json"]


def _agente_minimax(prof):
    def ag(estado):
        return melhor_jogada(estado, prof)
    return ag


def _construir_extrator_probs(cfg: dict):
    """Closure que devolve o PERFIL de confiança da CNN numa posição.

    Replica o pipeline de inferência V8 (mesmas funções do avaliador:
    `_para_dominio_dataset` + `extrair_canais`), restringe aos lances
    disponíveis e renormaliza — é a distribuição de DECISÃO real da CNN.
    Devolve None se a referência não for uma CNN (stand-in Minimax).
    """
    modelo = cfg["modelo"]
    if not modelo or str(modelo).startswith("standin_"):
        return None
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        import tensorflow.lite as tflite
    from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import extrair_canais
    from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import _para_dominio_dataset
    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro

    labels = todos_labels_canonicos(*_DIMS[cfg["tamanho"]])
    idx = {l: i for i, l in enumerate(labels)}
    interp = tflite.Interpreter(model_path=modelo)
    interp.allocate_tensors()
    shape = interp.get_input_details()[0]["shape"]
    K = int(shape[3])
    i_in = interp.get_input_details()[0]["index"]
    i_out = interp.get_output_details()[0]["index"]
    tam = cfg["tamanho"]

    def perfil(matriz_antes, traco_cnn, traco_mm) -> dict:
        est = EstadoTabuleiro.de_tamanho(tam)
        est.matriz = matriz_antes.copy()
        disp = est.tracos_disponiveis()
        c = extrair_canais(_para_dominio_dataset(matriz_antes))
        X = c[np.newaxis, :, :, :K].astype(np.float32)
        interp.set_tensor(i_in, X)
        interp.invoke()
        probs = interp.get_tensor(i_out)[0]
        pa = np.array([probs[idx[t]] for t in disp], dtype=np.float64)
        s = pa.sum()
        if s > 0:
            pa = pa / s                              # renormaliza sobre legais
        ordem = list(np.argsort(pa)[::-1])
        disp_ord = [disp[i] for i in ordem]
        p_arg = float(pa[ordem[0]])
        p_2 = float(pa[ordem[1]]) if len(pa) > 1 else 0.0
        rank_mm = (disp_ord.index(traco_mm) + 1) if traco_mm in disp else -1
        p_mm = float(pa[disp.index(traco_mm)]) if traco_mm in disp else 0.0
        nz = pa[pa > 0]
        ent = float(-(nz * np.log(nz)).sum())
        # Vetor de saída COMPLETO (todos os 31 labels canônicos, prob bruta da CNN).
        probs_json = json.dumps({lab: round(float(probs[idx[lab]]), 6) for lab in labels})
        return {"prob_argmax": round(p_arg, 4), "prob_2a": round(p_2, 4),
                "margem_top2": round(p_arg - p_2, 4), "prob_jogada_minimax": round(p_mm, 4),
                "rank_minimax": rank_mm, "entropia": round(ent, 4), "probs_json": probs_json}

    return perfil


def _worker_init(cfg: dict, prof_forense: int):
    global _W_REF, _W_ADV, _W_CFG, _W_PROBS
    modelo = cfg["modelo"]
    if modelo and not str(modelo).startswith("standin_"):
        from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import _cnn_agent_fn
        labels = todos_labels_canonicos(*_DIMS[cfg["tamanho"]])
        _W_REF = _cnn_agent_fn(modelo, labels)
    else:
        _W_REF = _agente_minimax(int(str(modelo).split("_p")[-1]) if modelo else 2)
    _W_ADV = agente_minimax_descuidado(
        cfg["prof_adversario"], eps_descuido=cfg["eps_descuido"], t_max_descuido=cfg["t_max_descuido"])
    _W_PROBS = _construir_extrator_probs(cfg)
    _W_CFG = dict(cfg=cfg, prof_forense=prof_forense)


def _worker_reforense(seed: int):
    cfg = _W_CFG["cfg"]
    r = jogar_partida_instrumentada(
        _W_REF, _W_ADV, ref_eh_jogador1=(seed % 2 == 0),
        tamanho=cfg["tamanho"], seed=seed,
        lances_abertura_aleatorios=cfg["abertura_aleatoria"])
    erros, resumo = analisar_partida(r, _W_CFG["prof_forense"], tamanho=cfg["tamanho"])
    linhas = []
    for e in erros:
        linha = e.para_linha()
        if _W_PROBS is not None:
            linha.update(_W_PROBS(e.matriz_antes, e.traco_cnn, e.traco_minimax))
        linhas.append(linha)
    return seed, linhas, resumo


def _ler_seeds_derrotas(derrotas_path: Path) -> list[int]:
    with open(derrotas_path, newline="", encoding="utf-8") as f:
        return [int(r["seed"]) for r in csv.DictReader(f)]


def _dist(titulo, chave, fonte):
    if not fonte:
        return
    c = Counter(chave(r) for r in fonte)
    print(f"\n  {titulo}:")
    for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
        print(f"    {str(k):28} {v:5d}  ({v/len(fonte)*100:5.1f}%)")


def _append_csv(path: Path, rows: list[dict], campos: list[str]) -> None:
    if not rows:
        return
    novo = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        if novo:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def _ler_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _diagnostico(corpus_path: Path, resumo_path: Path, janela_t: int) -> None:
    """Imprime o diagnóstico a partir do que está EM DISCO (parcial/retomado)."""
    resumos = _ler_csv(resumo_path)
    corpus = _ler_csv(corpus_path)
    julgadas = [r for r in resumos if int(r["n_julgados"]) > 0]
    ja_perdida = [r for r in julgadas if int(r["valor_entrada"]) < 0]
    com_decisivo = [r for r in julgadas if int(r["n_decisivos"]) > 0]
    print("\n" + "=" * 72)
    print(f"ONDE A PARIDADE VIRA (janela t >= {janela_t}) — {len(resumos)} derrotas analisadas")
    print("=" * 72)
    print(f"  Derrotas com lance julgável: {len(julgadas)}/{len(resumos)}")
    if julgadas:
        print(f"  Erro decisivo CAPTURADO nesta janela: {len(com_decisivo)}/{len(julgadas)} "
              f"({len(com_decisivo)/len(julgadas)*100:.1f}%)")
        print(f"  AINDA perdidas na entrada (vira antes de t={janela_t}): {len(ja_perdida)}/{len(julgadas)} "
              f"({len(ja_perdida)/len(julgadas)*100:.1f}%)")
        ts = [int(r["t_entrada"]) for r in julgadas]
        print(f"  t médio de entrada na janela: {sum(ts)/len(ts):.1f}")

    decisivos = [r for r in corpus if r["decisivo"] in (True, "True")]
    if not decisivos:
        return
    print(f"\n  Erros decisivos localizados: {len(decisivos)}")
    _dist("Por fase", lambda r: r["fase_nome"], decisivos)
    _dist("Por qtd_tracos (t)", lambda r: r["qtd_tracos"], decisivos)
    _dist("Por classificação do lance da CNN", lambda r: r["classificacao_traco_cnn"], decisivos)
    _dist("Por qtd_cadeias_longas", lambda r: r["qtd_cadeias_longas"], decisivos)
    _dist("Havia lance seguro?", lambda r: r["havia_lance_safe"], decisivos)

    if "prob_argmax" in decisivos[0] and decisivos[0]["prob_argmax"] != "":
        arg = [float(r["prob_argmax"]) for r in decisivos]
        marg = [float(r["margem_top2"]) for r in decisivos]
        pmm = [float(r["prob_jogada_minimax"]) for r in decisivos]
        rmm = [int(r["rank_minimax"]) for r in decisivos if int(r["rank_minimax"]) > 0]
        confiante = sum(1 for m in marg if m >= 0.5)
        incerta = sum(1 for m in marg if m < 0.2)
        mm_top3 = sum(1 for r in rmm if r <= 3)
        print("\n  CONFIANÇA DA CNN NO LANCE ERRADO:")
        print(f"    prob média do argmax (lance errado): {sum(arg)/len(arg):.3f}")
        print(f"    margem média p/ a 2a opção:          {sum(marg)/len(marg):.3f}")
        print(f"    CONFIANTE (margem>=0.5, pico no erro): {confiante}/{len(decisivos)} ({confiante/len(decisivos)*100:.1f}%)")
        print(f"    INCERTA (margem<0.2, quase-empate):    {incerta}/{len(decisivos)} ({incerta/len(decisivos)*100:.1f}%)")
        print(f"    prob média dada ao lance do Minimax:   {sum(pmm)/len(pmm):.3f}")
        if rmm:
            print(f"    lance do Minimax estava no TOP-3 da CNN: {mm_top3}/{len(rmm)} ({mm_top3/len(rmm)*100:.1f}%)")
            print(f"    rank médio do lance do Minimax:        {sum(rmm)/len(rmm):.1f}")
        print("    => CONFIANTE alto: dado de treino ensinou errado (re-rotular/gerar).")
        print("    => INCERTA / Minimax no top-3: lance certo conhecido mas não priorizado")
        print("       (sugere busca rasa, value-head ou temperatura).")


def main():
    p = argparse.ArgumentParser(description="Re-forense profunda das derrotas (localiza o lance do meio-jogo).")
    p.add_argument("--run-id", required=True, help="Subpasta da rodada em saidas/ (ex.: piloto_v2).")
    p.add_argument("--prof-forense", type=int, default=17, help="Profundidade do juiz (janela = t >= 31-p).")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--max-seeds", type=int, default=0, help="Analisa só as N primeiras derrotas (0 = todas). Use p/ medir custo antes de soltar tudo.")
    p.add_argument("--saida", default=None)
    args = p.parse_args()

    base = Path(args.saida) if args.saida else (Path(__file__).resolve().parent / "saidas")
    run_dir = base / args.run_id
    cp = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
    cfg = cp["config"]
    seeds = sorted(_ler_seeds_derrotas(run_dir / "derrotas.csv"))
    if args.max_seeds:
        seeds = seeds[:args.max_seeds]

    _lin, _col = _DIMS[cfg["tamanho"]]
    total_arestas = (_lin + 1) * _col + _lin * (_col + 1)   # pequeno (4,3) => 31
    janela_t = max(0, total_arestas - args.prof_forense)
    print("=" * 72)
    print(f"RE-FORENSE PROFUNDA — {len(seeds)} derrotas da rodada '{args.run_id}'")
    print("=" * 72)
    print(f"  Modelo     : {cfg['modelo']}")
    print(f"  Forense    : Minimax p={args.prof_forense}  (janela: t >= {janela_t}) | Workers: {args.workers}")
    print()

    # Campos de saída + paths (corpus de erros e resumo por derrota).
    tem_cnn = bool(cfg["modelo"]) and not str(cfg["modelo"]).startswith("standin_")
    from dataclasses import fields as _dc_fields
    from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.forense_value_swing_pontinhos import ErroDecisivo
    campos_corpus = [f.name for f in _dc_fields(ErroDecisivo) if f.name != "matriz_antes"]
    if tem_cnn:
        campos_corpus += CAMPOS_PROBS
    campos_resumo = ["seed", "placar_ref", "placar_adv", "t_entrada", "valor_entrada",
                     "n_julgados", "n_erros", "n_decisivos"]
    corpus_path = run_dir / f"corpus_reforense_p{args.prof_forense}.csv"
    resumo_path = run_dir / f"reforense_resumo_p{args.prof_forense}.csv"

    # Retomada: pula seeds já analisados (lê o resumo já gravado).
    feitos = {int(r["seed"]) for r in _ler_csv(resumo_path)}
    pendentes = [s for s in seeds if s not in feitos]
    if feitos:
        print(f"  Retomando: {len(feitos)} já analisados, {len(pendentes)} pendentes.\n")

    n_pend = len(pendentes)
    passo = max(1, n_pend // 400)    # log frequente (~a cada poucas derrotas)
    INTERVALO_LOG = 120              # heartbeat: ao menos 1 linha a cada 120 s
    FLUSH = 10                       # grava em disco a cada 10 derrotas concluídas
    t0 = time.perf_counter()
    ultimo_log = t0
    n_dec = 0
    buf_corpus: list[dict] = []
    buf_resumo: list[dict] = []
    interrompido = False

    def _flush():
        _append_csv(corpus_path, buf_corpus, campos_corpus)
        _append_csv(resumo_path, buf_resumo, campos_resumo)
        buf_corpus.clear()
        buf_resumo.clear()

    if pendentes:
        try:
            with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init,
                                     initargs=(cfg, args.prof_forense)) as ex:
                futs = [ex.submit(_worker_reforense, s) for s in pendentes]
                for i, fut in enumerate(as_completed(futs), 1):
                    _seed, linhas, resumo = fut.result()
                    buf_corpus.extend(linhas)
                    buf_resumo.append(resumo)
                    n_dec += sum(1 for l in linhas if l["decisivo"] in (True, "True"))
                    if i % FLUSH == 0:
                        _flush()
                    agora = time.perf_counter()
                    if i % passo == 0 or (agora - ultimo_log) >= INTERVALO_LOG or i == n_pend:
                        ultimo_log = agora
                        el = agora - t0
                        taxa = i / el if el else 0.0
                        eta = (n_pend - i) / taxa if taxa else 0.0
                        print(f"  [{i}/{n_pend}] {i/n_pend*100:5.1f}% | {n_dec} decisivos | "
                              f"{taxa:.2f} jogos/s | decorrido {el/60:.1f} min | "
                              f"ETA {eta/60:.1f} min", flush=True)
        except KeyboardInterrupt:
            interrompido = True
            print("\n!! Interrompido — salvando o que já foi processado...")
        finally:
            _flush()
    else:
        print("  Nada pendente — recomputando diagnóstico do que há em disco.")

    print(f"\n  Corpus incremental: {corpus_path}")
    if interrompido:
        print("  >> Rode O MESMO COMANDO para RETOMAR de onde parou.")

    # Diagnóstico sobre TUDO que está em disco (parcial / retomado incluídos).
    _diagnostico(corpus_path, resumo_path, janela_t)


if __name__ == "__main__":
    main()

"""CLI retomável que encadeia o funil e imprime a taxonomia-resumo dos erros.

Retomada por checkpoint: o corpus é gravado incrementalmente em disco e um
`checkpoint.json` guarda o último seed concluído + contagens. Ctrl+C (ou queda
de energia) deixa tudo durável; reabrir COM O MESMO COMANDO retoma do ponto
exato. Como cada partida é determinística pelo seed, retomar é reproduzível.

Uso (a partir da raiz do repo, com .venv):

    # Piloto para medir taxa de derrota (recomendado ANTES da rodada cheia):
    .venv\\Scripts\\python -m analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.executar_diagnostico \\
        --modelo "modelos/....tflite" --partidas 2000 \\
        --prof-adversario 3 --prof-forense 13 --eps-descuido 0.2 --abertura-aleatoria 4

    # Rodada cheia com parada automática ao atingir a base de diagnóstico:
    .venv\\Scripts\\python -m ...executar_diagnostico \\
        --modelo "modelos/....tflite" --partidas 200000 \\
        --prof-adversario 3 --prof-forense 13 --alvo-erros-decisivos 5000

    # Smoke test sem TFLite (referência = Minimax raso, perde de propósito):
    .venv\\Scripts\\python -m ...executar_diagnostico --partidas 30 --prof-ref 2 \\
        --prof-adversario 4 --prof-forense 7
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import fields
from pathlib import Path

# Bootstrap: garante a raiz do repo no sys.path para rodar como script direto.
_RAIZ = Path(__file__).resolve().parents[3]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import todos_labels_canonicos  # noqa: E402
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada  # noqa: E402
from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.adversarios_pontinhos import (  # noqa: E402
    agente_minimax_descuidado,
)
from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.arena_pontinhos import (  # noqa: E402
    jogar_partida_instrumentada, DERROTA, EMPATE, VITORIA,
)
from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.forense_value_swing_pontinhos import (  # noqa: E402
    analisar_partida, ErroDecisivo,
)

_DIMS = {"pequeno": (4, 3), "medio": (5, 4), "grande": (7, 5)}
_FLUSH_A_CADA = 100      # (sequencial) grava corpus + checkpoint a cada N partidas
_BATCH_PARALELO = 256    # (paralelo) tamanho do lote por checkpoint contíguo
CAMPOS_CORPUS = [f.name for f in fields(ErroDecisivo) if f.name != "matriz_antes"]
CAMPOS_DERROTAS = ["seed", "placar_ref", "placar_adv", "t_entrada", "valor_entrada",
                   "n_julgados", "n_erros", "n_decisivos"]


# ---------------------------------------------------------------------------
# Agentes
# ---------------------------------------------------------------------------

def _agente_minimax(profundidade: int):
    def agente(estado):
        return melhor_jogada(estado, profundidade)
    agente.__name__ = f"Minimax(p={profundidade})"
    return agente


def _construir_referencia(args):
    """Referência sob diagnóstico: TFLite se --modelo, senão Minimax raso stand-in."""
    if args.modelo:
        from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import _cnn_agent_fn
        linhas, colunas = _DIMS[args.tamanho]
        labels = todos_labels_canonicos(linhas, colunas)
        return _cnn_agent_fn(args.modelo, labels), f"CNN({Path(args.modelo).name})"
    return _agente_minimax(args.prof_ref), f"Minimax-standin(p={args.prof_ref})"


def _nome_referencia(args) -> str:
    if args.modelo:
        return f"CNN({Path(args.modelo).name})"
    return f"Minimax-standin(p={args.prof_ref})"


# ---------------------------------------------------------------------------
# Workers de processo (paralelismo) — funções no nível do módulo (pickláveis).
# Cada processo carrega o TFLite UMA vez (no initializer) e reusa entre partidas.
# A unidade de trabalho é UM seed; o resultado volta como linhas de corpus já
# prontas. Como cada partida re-semeia random.seed(seed), o corpus paralelo é
# idêntico ao sequencial (a ordem das linhas é normalizada por seed na gravação).
# ---------------------------------------------------------------------------

_W_REF = None
_W_ADV = None
_W_CFG: dict = {}


def _worker_init(modelo, prof_ref, tamanho, prof_adv, eps, t_max, prof_forense,
                 abertura, incluir_empates):
    global _W_REF, _W_ADV, _W_CFG
    if modelo:
        from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import _cnn_agent_fn
        labels = todos_labels_canonicos(*_DIMS[tamanho])
        _W_REF = _cnn_agent_fn(modelo, labels)
    else:
        _W_REF = _agente_minimax(prof_ref)
    _W_ADV = agente_minimax_descuidado(prof_adv, eps_descuido=eps, t_max_descuido=t_max)
    _W_CFG = dict(tamanho=tamanho, prof_forense=prof_forense,
                  abertura=abertura, incluir_empates=incluir_empates)


def _worker_jogo(seed: int):
    """Joga uma partida e, se derrota, roda a forense. Retorna dados serializáveis:
    (seed, resultado, resumo|None, linhas_corpus, n_decisivos)."""
    r = jogar_partida_instrumentada(
        _W_REF, _W_ADV, ref_eh_jogador1=(seed % 2 == 0),
        tamanho=_W_CFG["tamanho"], seed=seed,
        lances_abertura_aleatorios=_W_CFG["abertura"])
    linhas, decisivos, resumo = [], 0, None
    if r.resultado_ref == DERROTA or (_W_CFG["incluir_empates"] and r.resultado_ref == EMPATE):
        erros, resumo = analisar_partida(r, _W_CFG["prof_forense"], tamanho=_W_CFG["tamanho"])
        for e in erros:
            linhas.append(e.para_linha())
            if e.decisivo:
                decisivos += 1
    return seed, r.resultado_ref, resumo, linhas, decisivos


# ---------------------------------------------------------------------------
# Checkpoint / persistência
# ---------------------------------------------------------------------------

def _assinatura_config(args) -> dict:
    """Parâmetros que DEFINEM o corpus (mudá-los invalida a retomada)."""
    return {
        "modelo": args.modelo or f"standin_p{args.prof_ref}",
        "tamanho": args.tamanho,
        "prof_adversario": args.prof_adversario,
        "prof_forense": args.prof_forense,
        "eps_descuido": args.eps_descuido,
        "t_max_descuido": args.t_max_descuido,
        "abertura_aleatoria": args.abertura_aleatoria,
        "incluir_empates": args.incluir_empates,
        "seed_base": args.seed_base,
    }


def _hash_config(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:8]


def _escrever_checkpoint(caminho: Path, dados: dict) -> None:
    tmp = caminho.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, caminho)


def _montar_checkpoint(cfg, cfg_hash, seed_base, ultimo, contagem, n_erros, n_decisivos) -> dict:
    return {
        "versao": 1, "config": cfg, "config_hash": cfg_hash,
        "seed_base": seed_base, "ultimo_seed_concluido": ultimo,
        "contagem": contagem, "n_erros": n_erros, "n_decisivos": n_decisivos,
        "atualizado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def _append_csv(caminho: Path, linhas: list[dict], campos: list[str]) -> None:
    if not linhas:
        return
    novo = not caminho.exists() or caminho.stat().st_size == 0
    with open(caminho, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        if novo:
            w.writeheader()
        for ln in linhas:
            w.writerow(ln)


def _trim_csv(caminho: Path, ultimo_seed: int, campos: list[str]) -> None:
    """Remove linhas com seed > ultimo_seed (restos de uma queda pós-checkpoint)."""
    if not caminho.exists():
        return
    with open(caminho, newline="", encoding="utf-8") as f:
        linhas = [r for r in csv.DictReader(f) if int(r["seed"]) <= ultimo_seed]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)


def _carregar_corpus(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    with open(caminho, newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    for r in linhas:  # casts mínimos para a taxonomia
        for k in ("seed", "numero_jogada", "qtd_tracos", "fase", "regret",
                  "valor_otimo", "valor_jogado", "qtd_cadeias_longas",
                  "tamanho_max_cadeia_longa"):
            r[k] = int(r[k])
        r["decisivo"] = r["decisivo"] in ("True", "true", "1")
        r["havia_lance_safe"] = r["havia_lance_safe"] in ("True", "true", "1")
    return linhas


# ---------------------------------------------------------------------------
# Taxonomia-resumo
# ---------------------------------------------------------------------------

def _imprimir_taxonomia(rows: list[dict]) -> None:
    print("\n" + "=" * 72)
    print("TAXONOMIA-RESUMO DOS ERROS (lances subótimos da referência)")
    print("=" * 72)
    if not rows:
        print("  Nenhum lance subótimo capturado (referência não perdeu por erro "
              "próprio, ou não houve derrotas).")
        return
    n = len(rows)
    dec = [r for r in rows if r["decisivo"]]
    print(f"\n  Lances subótimos (regret>0): {n}")
    print(f"  Erros DECISIVOS (jogou fora posição não-perdida): {len(dec)} "
          f"({len(dec)/n*100:.1f}%)")
    print(f"  Regret médio (caixas): {sum(r['regret'] for r in rows)/n:.2f}")

    def _dist(titulo, chave, fonte):
        if not fonte:
            return
        c = Counter(chave(r) for r in fonte)
        print(f"\n  {titulo}:")
        for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
            print(f"    {str(k):28} {v:5d}  ({v/len(fonte)*100:5.1f}%)")

    print("\n  --- Apenas erros DECISIVOS (onde a derrota foi selada) ---")
    _dist("Por fase", lambda r: r["fase_nome"], dec)
    _dist("Por classificação do lance da CNN", lambda r: r["classificacao_traco_cnn"], dec)
    _dist("Por qtd_cadeias_longas", lambda r: r["qtd_cadeias_longas"], dec)
    _dist("Havia lance seguro?", lambda r: r["havia_lance_safe"], dec)
    print("\n  Top traços da CNN em erros decisivos:")
    for k, v in Counter(r["traco_cnn"] for r in dec).most_common(10):
        print(f"    {k:12} {v:4d}")


# ---------------------------------------------------------------------------
# Loop principal (retomável)
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Arena de autodiagnóstico (retomável) de derrotas da CNN.")
    p.add_argument("--modelo", default=None, help="TFLite da referência. Omitido => Minimax raso stand-in.")
    p.add_argument("--tamanho", default="pequeno", choices=["pequeno", "medio", "grande"])
    p.add_argument("--partidas", type=int, default=200, help="Teto de partidas a jogar (nesta config).")
    p.add_argument("--prof-ref", type=int, default=2, help="Profundidade do Minimax stand-in (sem --modelo).")
    p.add_argument("--prof-adversario", type=int, default=3, help="Profundidade do adversário (jogue RASO: barato).")
    p.add_argument("--prof-forense", type=int, default=13, help="Profundidade do juiz (alta: exato no endgame).")
    p.add_argument("--eps-descuido", type=float, default=0.2)
    p.add_argument("--t-max-descuido", type=int, default=17)
    p.add_argument("--abertura-aleatoria", type=int, default=4, help="k lances seguros aleatórios no começo.")
    p.add_argument("--incluir-empates", action="store_true")
    p.add_argument("--alvo-erros-decisivos", type=int, default=0, help="Para sozinho ao atingir N erros decisivos (0 = sem alvo).")
    p.add_argument("--seed-base", type=int, default=0)
    p.add_argument("--workers", type=int, default=1,
                   help="Processos paralelos (1 = sequencial). Use ~n_cores-1 para a rodada cheia.")
    p.add_argument("--saida", default=None, help="Pasta-base de saída (default: ./saidas).")
    p.add_argument("--run-id", default=None, help="Nome da subpasta da rodada (default: exec_<hash-config>).")
    args = p.parse_args()

    cfg = _assinatura_config(args)
    cfg_hash = _hash_config(cfg)
    base = Path(args.saida) if args.saida else (Path(__file__).resolve().parent / "saidas")
    run_dir = base / (args.run_id or f"exec_{cfg_hash}")
    run_dir.mkdir(parents=True, exist_ok=True)
    cp_path = run_dir / "checkpoint.json"
    corpus_path = run_dir / "corpus_erros.csv"
    derrotas_path = run_dir / "derrotas.csv"

    # ---- Retomada ----
    contagem = {VITORIA: 0, EMPATE: 0, DERROTA: 0}
    n_erros = n_decisivos = 0
    proximo_seed = args.seed_base
    if cp_path.exists():
        cp = json.loads(cp_path.read_text(encoding="utf-8"))
        if cp.get("config_hash") != cfg_hash:
            print(f"!! checkpoint em {run_dir} tem config diferente. Use --run-id novo "
                  f"ou apague a pasta. Abortando."); sys.exit(1)
        contagem = {k: cp["contagem"][k] for k in contagem}
        n_erros, n_decisivos = cp["n_erros"], cp["n_decisivos"]
        proximo_seed = cp["ultimo_seed_concluido"] + 1
        _trim_csv(corpus_path, cp["ultimo_seed_concluido"], CAMPOS_CORPUS)
        _trim_csv(derrotas_path, cp["ultimo_seed_concluido"], CAMPOS_DERROTAS)
        print(f">> Retomando rodada {run_dir.name}: já {sum(contagem.values())} partidas "
              f"({contagem[DERROTA]}D), {n_decisivos} erros decisivos. Seguindo do seed {proximo_seed}.")

    pct = int(args.eps_descuido * 100)
    nome_adv = f"MinimaxDescuidado(p={args.prof_adversario}, eps={pct}%, t<={args.t_max_descuido})"
    print("=" * 72)
    print("ARENA DE AUTODIAGNÓSTICO — derrotas da referência (retomável)")
    print("=" * 72)
    print(f"  Rodada     : {run_dir.name}  (config {cfg_hash})")
    print(f"  Referência : {_nome_referencia(args)}")
    print(f"  Adversário : {nome_adv}")
    print(f"  Forense    : Minimax p={args.prof_forense} | Workers: {args.workers}")
    print(f"  Teto       : {args.partidas} partidas | alvo erros decisivos: {args.alvo_erros_decisivos or '—'}")
    print()

    seed_final = args.seed_base + args.partidas  # exclusivo
    ultimo_concluido = proximo_seed - 1
    jogadas_inicial = sum(contagem.values())
    t0 = time.perf_counter()
    interrompido = False

    def _progresso():
        jogadas = sum(contagem.values())
        feitas = jogadas - jogadas_inicial
        taxa = feitas / (time.perf_counter() - t0) if feitas else 0.0
        d = contagem[DERROTA]
        print(f"\r  [{jogadas}/{args.partidas}] {d}D ({d/jogadas*100:.1f}%) "
              f"| {n_decisivos} decisivos | {taxa:.1f} part/s", end="", flush=True)

    def _checkpoint(ultimo):
        _escrever_checkpoint(cp_path, _montar_checkpoint(
            cfg, cfg_hash, args.seed_base, ultimo, contagem, n_erros, n_decisivos))

    try:
        if args.workers > 1:
            # ---- Paralelo: checkpoint por LOTE contíguo (retomada por lote) ----
            with ProcessPoolExecutor(
                max_workers=args.workers, initializer=_worker_init,
                initargs=(args.modelo, args.prof_ref, args.tamanho, args.prof_adversario,
                          args.eps_descuido, args.t_max_descuido, args.prof_forense,
                          args.abertura_aleatoria, args.incluir_empates),
            ) as ex:
                for ini in range(proximo_seed, seed_final, _BATCH_PARALELO):
                    chunk = range(ini, min(ini + _BATCH_PARALELO, seed_final))
                    futs = [ex.submit(_worker_jogo, s) for s in chunk]
                    linhas_lote: list[dict] = []
                    derrotas_lote: list[dict] = []
                    for fut in as_completed(futs):
                        _seed, res, resumo, linhas, dec = fut.result()
                        contagem[res] += 1
                        linhas_lote.extend(linhas)
                        n_erros += len(linhas)
                        n_decisivos += dec
                        if resumo is not None:
                            derrotas_lote.append(resumo)
                    # Lote inteiro concluído → grava contíguo e avança checkpoint.
                    linhas_lote.sort(key=lambda r: (int(r["seed"]), int(r["numero_jogada"])))
                    derrotas_lote.sort(key=lambda r: int(r["seed"]))
                    _append_csv(corpus_path, linhas_lote, CAMPOS_CORPUS)
                    _append_csv(derrotas_path, derrotas_lote, CAMPOS_DERROTAS)
                    ultimo_concluido = chunk.stop - 1
                    _checkpoint(ultimo_concluido)
                    _progresso()
                    if args.alvo_erros_decisivos and n_decisivos >= args.alvo_erros_decisivos:
                        print(f"\n>> Alvo de {args.alvo_erros_decisivos} erros decisivos atingido.")
                        break
        else:
            # ---- Sequencial: checkpoint a cada _FLUSH_A_CADA partidas ----
            agente_ref, _ = _construir_referencia(args)
            agente_adv = agente_minimax_descuidado(
                args.prof_adversario, eps_descuido=args.eps_descuido, t_max_descuido=args.t_max_descuido)
            buffer: list[dict] = []
            buffer_derrotas: list[dict] = []
            for seed in range(proximo_seed, seed_final):
                r = jogar_partida_instrumentada(
                    agente_ref, agente_adv, ref_eh_jogador1=(seed % 2 == 0),
                    tamanho=args.tamanho, seed=seed,
                    lances_abertura_aleatorios=args.abertura_aleatoria)
                contagem[r.resultado_ref] += 1
                if r.resultado_ref == DERROTA or (args.incluir_empates and r.resultado_ref == EMPATE):
                    erros, resumo = analisar_partida(r, args.prof_forense, tamanho=args.tamanho)
                    buffer_derrotas.append(resumo)
                    for e in erros:
                        buffer.append(e.para_linha())
                        n_erros += 1
                        if e.decisivo:
                            n_decisivos += 1
                ultimo_concluido = seed
                if sum(contagem.values()) % _FLUSH_A_CADA == 0:
                    _append_csv(corpus_path, buffer, CAMPOS_CORPUS); buffer = []
                    _append_csv(derrotas_path, buffer_derrotas, CAMPOS_DERROTAS); buffer_derrotas = []
                    _checkpoint(ultimo_concluido)
                    _progresso()
                if args.alvo_erros_decisivos and n_decisivos >= args.alvo_erros_decisivos:
                    print(f"\n>> Alvo de {args.alvo_erros_decisivos} erros decisivos atingido.")
                    break
            _append_csv(corpus_path, buffer, CAMPOS_CORPUS)
            _append_csv(derrotas_path, buffer_derrotas, CAMPOS_DERROTAS)
            _checkpoint(ultimo_concluido)
    except KeyboardInterrupt:
        interrompido = True
        print("\n!! Interrompido (Ctrl+C). Progresso salvo até o último checkpoint.")

    jogadas = sum(contagem.values())
    print(f"\n  Partidas: {jogadas} | V/E/D: {contagem[VITORIA]}/{contagem[EMPATE]}/{contagem[DERROTA]} "
          f"(derrota {contagem[DERROTA]/jogadas*100:.1f}%)" if jogadas else "\n  Nenhuma partida.")
    print(f"  Erros: {n_erros} ({n_decisivos} decisivos) | corpus: {corpus_path}")
    if interrompido:
        print("  >> Rode O MESMO COMANDO para retomar exatamente daqui.")

    _imprimir_diagnostico_entrada(derrotas_path, args.prof_forense)
    _imprimir_taxonomia(_carregar_corpus(corpus_path))
    print(f"\n  Tempo desta sessão: {time.perf_counter() - t0:.1f}s")


def _imprimir_diagnostico_entrada(derrotas_path: Path, prof_forense: int) -> None:
    """Onde a derrota nasceu: a CNN já estava perdida ao ENTRAR na janela de forense?"""
    if not derrotas_path.exists():
        return
    with open(derrotas_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    n = len(rows)
    julgadas = [r for r in rows if int(r["n_julgados"]) > 0]
    ja_perdida = [r for r in julgadas if int(r["valor_entrada"]) < 0]
    com_erro = [r for r in julgadas if int(r["n_decisivos"]) > 0]
    sem_janela = n - len(julgadas)
    print("\n" + "=" * 72)
    print("DIAGNÓSTICO DE ORIGEM DA DERROTA (janela de forense = endgame exato)")
    print("=" * 72)
    print(f"  Derrotas analisadas: {n}")
    if julgadas:
        print(f"  Já PERDIDAS na entrada da janela (valor<0 ao iniciar o endgame): "
              f"{len(ja_perdida)}/{len(julgadas)} ({len(ja_perdida)/len(julgadas)*100:.1f}%)")
        print(f"    => decididas ANTES do endgame (meio-jogo) — fora do alcance da forense atual (p={prof_forense}).")
        print(f"  Com erro decisivo DENTRO da janela (endgame): {len(com_erro)}/{len(julgadas)} "
              f"({len(com_erro)/len(julgadas)*100:.1f}%)")
        ts = [int(r["t_entrada"]) for r in julgadas]
        print(f"  t médio de entrada na janela: {sum(ts)/len(ts):.1f}")
    if sem_janela:
        print(f"  Sem nenhum lance julgável (jogo curto / nenhum lance da ref no endgame): {sem_janela}")


if __name__ == "__main__":
    main()

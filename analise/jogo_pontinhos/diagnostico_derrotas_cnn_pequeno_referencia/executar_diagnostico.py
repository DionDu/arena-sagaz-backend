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
_FLUSH_A_CADA = 100   # grava corpus + checkpoint a cada N partidas
CAMPOS_CORPUS = [f.name for f in fields(ErroDecisivo) if f.name != "matriz_antes"]


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


def _append_corpus(caminho: Path, linhas: list[dict]) -> None:
    if not linhas:
        return
    novo = not caminho.exists() or caminho.stat().st_size == 0
    with open(caminho, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CORPUS)
        if novo:
            w.writeheader()
        for ln in linhas:
            w.writerow(ln)


def _trim_corpus(caminho: Path, ultimo_seed: int) -> None:
    """Remove linhas com seed > ultimo_seed (restos de uma queda pós-checkpoint)."""
    if not caminho.exists():
        return
    with open(caminho, newline="", encoding="utf-8") as f:
        linhas = [r for r in csv.DictReader(f) if int(r["seed"]) <= ultimo_seed]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CORPUS)
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
        _trim_corpus(corpus_path, cp["ultimo_seed_concluido"])
        print(f">> Retomando rodada {run_dir.name}: já {sum(contagem.values())} partidas "
              f"({contagem[DERROTA]}D), {n_decisivos} erros decisivos. Seguindo do seed {proximo_seed}.")

    agente_ref, nome_ref = _construir_referencia(args)
    agente_adv = agente_minimax_descuidado(
        args.prof_adversario, eps_descuido=args.eps_descuido, t_max_descuido=args.t_max_descuido)

    print("=" * 72)
    print("ARENA DE AUTODIAGNÓSTICO — derrotas da referência (retomável)")
    print("=" * 72)
    print(f"  Rodada     : {run_dir.name}  (config {cfg_hash})")
    print(f"  Referência : {nome_ref}")
    print(f"  Adversário : {agente_adv.__name__}")
    print(f"  Forense    : Minimax p={args.prof_forense}")
    print(f"  Teto       : {args.partidas} partidas | alvo erros decisivos: {args.alvo_erros_decisivos or '—'}")
    print()

    seed_final = args.seed_base + args.partidas  # exclusivo
    buffer: list[dict] = []
    ultimo_concluido = proximo_seed - 1
    t0 = time.perf_counter()
    interrompido = False

    def _flush():
        nonlocal buffer
        _append_corpus(corpus_path, buffer)
        buffer = []
        _escrever_checkpoint(cp_path, {
            "versao": 1, "config": cfg, "config_hash": cfg_hash,
            "seed_base": args.seed_base, "ultimo_seed_concluido": ultimo_concluido,
            "contagem": contagem, "n_erros": n_erros, "n_decisivos": n_decisivos,
            "atualizado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    try:
        for seed in range(proximo_seed, seed_final):
            r = jogar_partida_instrumentada(
                agente_ref, agente_adv,
                ref_eh_jogador1=(seed % 2 == 0),
                tamanho=args.tamanho, seed=seed,
                lances_abertura_aleatorios=args.abertura_aleatoria)
            contagem[r.resultado_ref] += 1

            if r.resultado_ref == DERROTA or (args.incluir_empates and r.resultado_ref == EMPATE):
                erros = analisar_partida(r, args.prof_forense, tamanho=args.tamanho)
                for e in erros:
                    buffer.append(e.para_linha())
                    n_erros += 1
                    if e.decisivo:
                        n_decisivos += 1

            ultimo_concluido = seed
            jogadas = sum(contagem.values())
            if jogadas % _FLUSH_A_CADA == 0:
                _flush()
                taxa = jogadas / (time.perf_counter() - t0)
                print(f"\r  [{jogadas}/{args.partidas}] {contagem[DERROTA]}D "
                      f"({contagem[DERROTA]/jogadas*100:.1f}%) | {n_decisivos} decisivos "
                      f"| {taxa:.1f} part/s", end="", flush=True)

            if args.alvo_erros_decisivos and n_decisivos >= args.alvo_erros_decisivos:
                print(f"\n>> Alvo de {args.alvo_erros_decisivos} erros decisivos atingido.")
                break
    except KeyboardInterrupt:
        interrompido = True
        print("\n!! Interrompido (Ctrl+C). Salvando progresso...")
    finally:
        _flush()

    jogadas = sum(contagem.values())
    print(f"\n  Partidas: {jogadas} | V/E/D: {contagem[VITORIA]}/{contagem[EMPATE]}/{contagem[DERROTA]} "
          f"(derrota {contagem[DERROTA]/jogadas*100:.1f}%)" if jogadas else "\n  Nenhuma partida.")
    print(f"  Erros: {n_erros} ({n_decisivos} decisivos) | corpus: {corpus_path}")
    if interrompido:
        print("  >> Rode O MESMO COMANDO para retomar exatamente daqui.")

    _imprimir_taxonomia(_carregar_corpus(corpus_path))
    print(f"\n  Tempo desta sessão: {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()

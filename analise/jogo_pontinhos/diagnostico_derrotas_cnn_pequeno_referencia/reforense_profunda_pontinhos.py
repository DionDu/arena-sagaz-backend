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
import sys
from collections import Counter
from pathlib import Path

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


def _agente_minimax(prof):
    def ag(estado):
        return melhor_jogada(estado, prof)
    return ag


def _worker_init(cfg: dict, prof_forense: int):
    global _W_REF, _W_ADV, _W_CFG
    modelo = cfg["modelo"]
    if modelo and not str(modelo).startswith("standin_"):
        from gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos import _cnn_agent_fn
        labels = todos_labels_canonicos(*_DIMS[cfg["tamanho"]])
        _W_REF = _cnn_agent_fn(modelo, labels)
    else:
        _W_REF = _agente_minimax(int(str(modelo).split("_p")[-1]) if modelo else 2)
    _W_ADV = agente_minimax_descuidado(
        cfg["prof_adversario"], eps_descuido=cfg["eps_descuido"], t_max_descuido=cfg["t_max_descuido"])
    _W_CFG = dict(cfg=cfg, prof_forense=prof_forense)


def _worker_reforense(seed: int):
    cfg = _W_CFG["cfg"]
    r = jogar_partida_instrumentada(
        _W_REF, _W_ADV, ref_eh_jogador1=(seed % 2 == 0),
        tamanho=cfg["tamanho"], seed=seed,
        lances_abertura_aleatorios=cfg["abertura_aleatoria"])
    erros, resumo = analisar_partida(r, _W_CFG["prof_forense"], tamanho=cfg["tamanho"])
    linhas = [e.para_linha() for e in erros]
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


def main():
    p = argparse.ArgumentParser(description="Re-forense profunda das derrotas (localiza o lance do meio-jogo).")
    p.add_argument("--run-id", required=True, help="Subpasta da rodada em saidas/ (ex.: piloto_v2).")
    p.add_argument("--prof-forense", type=int, default=17, help="Profundidade do juiz (janela = t >= 31-p).")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--saida", default=None)
    args = p.parse_args()

    base = Path(args.saida) if args.saida else (Path(__file__).resolve().parent / "saidas")
    run_dir = base / args.run_id
    cp = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
    cfg = cp["config"]
    seeds = _ler_seeds_derrotas(run_dir / "derrotas.csv")

    _lin, _col = _DIMS[cfg["tamanho"]]
    total_arestas = (_lin + 1) * _col + _lin * (_col + 1)   # pequeno (4,3) => 31
    janela_t = max(0, total_arestas - args.prof_forense)
    print("=" * 72)
    print(f"RE-FORENSE PROFUNDA — {len(seeds)} derrotas da rodada '{args.run_id}'")
    print("=" * 72)
    print(f"  Modelo     : {cfg['modelo']}")
    print(f"  Forense    : Minimax p={args.prof_forense}  (janela: t >= {janela_t}) | Workers: {args.workers}")
    print()

    todas_linhas: list[dict] = []
    resumos: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init,
                             initargs=(cfg, args.prof_forense)) as ex:
        futs = [ex.submit(_worker_reforense, s) for s in seeds]
        for i, fut in enumerate(as_completed(futs), 1):
            _seed, linhas, resumo = fut.result()
            todas_linhas.extend(linhas)
            resumos.append(resumo)
            print(f"\r  [{i}/{len(seeds)}] derrotas analisadas...", end="", flush=True)
    print()

    # Persistência
    if todas_linhas:
        from dataclasses import fields
        from analise.jogo_pontinhos.diagnostico_derrotas_cnn_pequeno_referencia.forense_value_swing_pontinhos import ErroDecisivo
        campos = [f.name for f in fields(ErroDecisivo) if f.name != "matriz_antes"]
        out = run_dir / f"corpus_reforense_p{args.prof_forense}.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader(); w.writerows(todas_linhas)
        print(f"  Corpus re-forense salvo: {out}")

    # Diagnóstico: empurrando a janela para t>={janela_t}, quantas derrotas agora
    # têm um erro decisivo capturado? E quantas AINDA estavam perdidas na entrada?
    julgadas = [r for r in resumos if int(r["n_julgados"]) > 0]
    ja_perdida = [r for r in julgadas if int(r["valor_entrada"]) < 0]
    com_decisivo = [r for r in julgadas if int(r["n_decisivos"]) > 0]
    print("\n" + "=" * 72)
    print(f"ONDE A PARIDADE VIRA (janela t >= {janela_t})")
    print("=" * 72)
    print(f"  Derrotas com lance julgável: {len(julgadas)}/{len(seeds)}")
    if julgadas:
        print(f"  Erro decisivo CAPTURADO nesta janela: {len(com_decisivo)}/{len(julgadas)} "
              f"({len(com_decisivo)/len(julgadas)*100:.1f}%)")
        print(f"  AINDA perdidas na entrada (vira antes de t={janela_t}): {len(ja_perdida)}/{len(julgadas)} "
              f"({len(ja_perdida)/len(julgadas)*100:.1f}%)")
        ts = [int(r["t_entrada"]) for r in julgadas]
        print(f"  t médio de entrada na janela: {sum(ts)/len(ts):.1f}")

    decisivos = [r for r in todas_linhas if r["decisivo"] in (True, "True")]
    if decisivos:
        print(f"\n  Erros decisivos localizados: {len(decisivos)}")
        _dist("Por fase", lambda r: r["fase_nome"], decisivos)
        _dist("Por qtd_tracos (t)", lambda r: r["qtd_tracos"], decisivos)
        _dist("Por classificação do lance da CNN", lambda r: r["classificacao_traco_cnn"], decisivos)
        _dist("Por qtd_cadeias_longas", lambda r: r["qtd_cadeias_longas"], decisivos)
        _dist("Havia lance seguro?", lambda r: r["havia_lance_safe"], decisivos)


if __name__ == "__main__":
    main()

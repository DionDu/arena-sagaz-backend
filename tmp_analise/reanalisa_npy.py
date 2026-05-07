"""Reanalisa um estado salvo (NPY+JSON) com Minimax em várias profundidades.

Uso:
    py tmp_analise/reanalisa_npy.py <caminho_npy>
    py tmp_analise/reanalisa_npy.py <caminho_png>   # auto-resolve para .npy

Saída: ranking de jogadas por score em p=5, p=7, p=9 + comparação com a
jogada que a CNN fez (no JSON) e com a que o oráculo do run sugeriu.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))

import numpy as np
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas


def main(arg: str):
    p = Path(arg)
    if p.suffix.lower() == ".png":
        p = p.with_suffix(".npy")
    if not p.exists():
        print(f"NPY nao encontrado: {p}")
        sys.exit(1)
    json_path = p.with_suffix(".json")
    if json_path.exists():
        meta = json.loads(json_path.read_text(encoding="utf-8"))
    else:
        meta = {}

    matriz = np.load(p)
    print(f"Arquivo: {p.name}")
    print(f"Matriz shape: {matriz.shape}")
    print(matriz)
    print()
    if meta:
        print("Metadados:")
        for k in ("partida_idx","cnn_primeiro","adversario","numero_jogada",
                 "n_tracos_antes","fase","jogada_cnn","jogada_otima","delta",
                 "classe_delta","prof_oraculo","n_grau3_disponivel","cnn_valor"):
            if k in meta:
                print(f"  {k}: {meta[k]}")
        print()

    estado = EstadoTabuleiro.de_tamanho("pequeno")
    estado.matriz = matriz.copy()
    disponiveis = estado.tracos_disponiveis()
    print(f"Jogadas disponiveis ({len(disponiveis)}): {disponiveis}")
    print()

    jcnn = meta.get("jogada_cnn")
    jotim_run = meta.get("jogada_otima")

    for prof in (5, 7, 9):
        print(f"=== Minimax(p={prof}) ===")
        sc = _scores_de_todas_jogadas(estado, prof)
        m = max(sc.values())
        ots = sorted([t for t, s in sc.items() if s == m])
        print(f"  Score MAX = {m:+d}  otimas: {ots}")
        rank = sorted(sc.items(), key=lambda kv: kv[1], reverse=True)
        for t, s in rank:
            tag = []
            if t == jcnn: tag.append("CNN")
            if t == jotim_run: tag.append("OTIMA_run")
            if t in ots: tag.append(f"OTIMA_p{prof}")
            print(f"    {t}: {s:+d}  {' '.join(tag)}")
        print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1])

"""
patch_minimax_depth_pontinhos.py
================================
Adiciona o campo `minimax_depth` a lotes NPZ gerados antes dessa coluna
existir no pipeline de geração (V3 do notebook).

Uso
---
python patch_minimax_depth_pontinhos.py <pasta> <profundidade>

Exemplos
--------
# Lotes da raiz (depth=7):
python patch_minimax_depth_pontinhos.py dados/ 7

# Lotes da subpasta depth=6:
python patch_minimax_depth_pontinhos.py dados/profundidade_minimax_6/ 6

# Lotes novos do Databricks (depth=8), quando chegarem:
python patch_minimax_depth_pontinhos.py dados/profundidade_minimax_8/ 8

Comportamento
-------------
- Arquivos que já têm `minimax_depth` são ignorados (idempotente).
- Reescreve o NPZ no mesmo caminho (sobrescreve). Mantenha backup se necessário.
- Imprime progresso e contagem final de arquivos atualizados / ignorados.
"""

import sys
import glob
import os
import numpy as np


def patch_folder(folder: str, depth: int) -> None:
    pattern = os.path.join(folder, "dataset_pequeno_*.npz")
    arquivos = sorted(glob.glob(pattern))

    if not arquivos:
        print(f"Nenhum arquivo encontrado em: {pattern}")
        return

    print(f"Pasta   : {folder}")
    print(f"Depth   : {depth}")
    print(f"Arquivos: {len(arquivos)}")
    print()

    atualizados = 0
    ignorados = 0

    for path in arquivos:
        nome = os.path.basename(path)
        d = np.load(path, allow_pickle=True)

        if "minimax_depth" in d:
            depth_existente = int(d["minimax_depth"][0])
            print(f"  [SKIP] {nome}  (já tem minimax_depth={depth_existente})")
            ignorados += 1
            continue

        arrays = {k: d[k] for k in d.files}
        arrays["minimax_depth"] = np.array([depth], dtype=np.int32)
        np.savez_compressed(path, **arrays)
        print(f"  [OK]   {nome}  -> minimax_depth={depth}")
        atualizados += 1

    print()
    print(f"Concluído: {atualizados} atualizados, {ignorados} ignorados.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python patch_minimax_depth_pontinhos.py <pasta> <profundidade>")
        sys.exit(1)

    pasta = sys.argv[1]
    try:
        prof = int(sys.argv[2])
    except ValueError:
        print(f"Profundidade inválida: {sys.argv[2]}")
        sys.exit(1)

    patch_folder(pasta, prof)

"""Normaliza arestas nos datasets .npz: converte traços 1/-1 → 9.

Uso:
    python -m scripts.normalizar_datasets dados/
    python -m scripts.normalizar_datasets /caminho/do/databricks/

Idempotente: se os traços já forem 9, não faz nada.
Caixas fechadas (posições ímpar,ímpar) ficam INTACTAS com 1/-1.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np


def normalizar_matriz(mat: np.ndarray) -> np.ndarray:
    """Converte arestas (traços) de 1/-1 para 9, preservando caixas."""
    h, w = mat.shape
    for r in range(h):
        for c in range(w):
            # Posições de aresta: (par,ímpar) = horizontal, (ímpar,par) = vertical
            if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
                if mat[r, c] != 0:  # aresta preenchida (era 1 ou -1)
                    mat[r, c] = 9
    return mat


def processar_arquivo(caminho: str, backup: bool = True) -> dict:
    """Processa um arquivo .npz, normalizando as matrizes de estados."""
    dados = np.load(caminho, allow_pickle=True)
    estados = dados["estados"].copy()
    # Extrair todos os campos antes de fechar o handle (Windows PermissionError)
    campos_orig = {key: dados[key].copy() if hasattr(dados[key], 'copy') else dados[key] for key in dados.files}
    dados.close()

    # Contar arestas que precisam de conversão
    total_convertidas = 0
    for i in range(len(estados)):
        mat = estados[i]
        for r in range(mat.shape[0]):
            for c in range(mat.shape[1]):
                if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
                    if mat[r, c] != 0 and mat[r, c] != 9:
                        total_convertidas += 1
                        mat[r, c] = 9

    if total_convertidas == 0:
        return {"arquivo": caminho, "amostras": len(estados), "convertidas": 0, "status": "ja_normalizado"}

    # Backup do original
    if backup:
        backup_path = caminho + ".bak"
        if not os.path.exists(backup_path):
            os.rename(caminho, backup_path)
        else:
            os.remove(caminho)

    # Salvar com os mesmos campos
    campos = {}
    for key in campos_orig:
        if key == "estados":
            campos[key] = estados
        else:
            campos[key] = campos_orig[key]

    np.savez_compressed(caminho, **campos)

    return {
        "arquivo": caminho,
        "amostras": len(estados),
        "convertidas": total_convertidas,
        "status": "normalizado",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normaliza arestas nos datasets .npz")
    parser.add_argument("diretorio", help="Pasta contendo os arquivos .npz")
    parser.add_argument("--sem-backup", action="store_true", help="Não criar backup .bak")
    args = parser.parse_args()

    arquivos = sorted(glob.glob(os.path.join(args.diretorio, "*.npz")))
    if not arquivos:
        print(f"Nenhum arquivo .npz encontrado em {args.diretorio}")
        sys.exit(1)

    print(f"Encontrados {len(arquivos)} arquivo(s) .npz em {args.diretorio}")
    print()

    for arq in arquivos:
        resultado = processar_arquivo(arq, backup=not args.sem_backup)
        status = resultado["status"]
        conv = resultado["convertidas"]
        n = resultado["amostras"]
        nome = os.path.basename(arq)
        if status == "ja_normalizado":
            print(f"  {nome}: {n} amostras — ja normalizado (nada a fazer)")
        else:
            print(f"  {nome}: {n} amostras — {conv} arestas convertidas para 9")

    print()
    print("Concluido.")


if __name__ == "__main__":
    main()

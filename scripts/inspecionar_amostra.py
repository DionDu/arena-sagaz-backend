"""Inspeção detalhada de uma amostra de cada NPZ."""
import numpy as np

d = np.load(r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz")
labels = d["labels_canonicos"]
print("Labels canonicos:", list(labels))
print()

# Amostra com mais tracos (mais avancada no jogo)
qtd = d["qtd_tracos"]
idx_med = np.where(qtd == 10)[0][0]  # pegar um estado com 10 tracos

print(f"=== Amostra idx={idx_med}, qtd_tracos={qtd[idx_med]} ===")
print(f"melhor_jogada: {d['melhor_jogada'][idx_med]}")
print(f"depth_jogada: {d['depth_jogada'][idx_med]}")
print(f"depth_melhor_jogada: {d['depth_melhor_jogada'][idx_med]}")
print(f"depth_geracao: {d['depth_geracao'][idx_med]}")
print()

# Scores da jogada original (gerada com depth adaptativa)
sj = d["score_jogada"][idx_med]
print("score_jogada (tracos disponiveis):")
for i, (lb, sc) in enumerate(zip(labels, sj)):
    if sc != -1e9:
        print(f"  [{i:2d}] {lb}: {sc:+.0f}")

print()

# Scores da melhor jogada (recalculada com depth 7)
smj = d["score_melhor_jogada"][idx_med]
print("score_melhor_jogada (tracos disponiveis):")
for i, (lb, sc) in enumerate(zip(labels, smj)):
    if sc != -1e9:
        print(f"  [{i:2d}] {lb}: {sc:+.0f}")

print()

# Comparar
print("Sao iguais?", np.array_equal(sj, smj))
print("Diferenca max:", np.max(np.abs(sj - smj)))

print()
print("Estado da matriz:")
mat = d["estados"][idx_med]
print(mat)

# Verificar um estado simples (1 traco)
idx_1 = np.where(qtd == 1)[0][0]
print(f"\n=== Amostra idx={idx_1}, qtd_tracos={qtd[idx_1]} ===")
print(f"melhor_jogada: {d['melhor_jogada'][idx_1]}")
mat1 = d["estados"][idx_1]
print("Estado da matriz:")
print(mat1)

sj1 = d["score_jogada"][idx_1]
smj1 = d["score_melhor_jogada"][idx_1]
print("\nscore_jogada (tracos disponiveis):")
for i, (lb, sc) in enumerate(zip(labels, sj1)):
    if sc != -1e9:
        print(f"  [{i:2d}] {lb}: {sc:+.0f}")
print("\nscore_melhor_jogada (tracos disponiveis):")
for i, (lb, sc) in enumerate(zip(labels, smj1)):
    if sc != -1e9:
        print(f"  [{i:2d}] {lb}: {sc:+.0f}")

d.close()

import numpy as np

arquivo = r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz"
npz = np.load(arquivo, allow_pickle=True)
score_melhor_jogada = npz['score_melhor_jogada']
labels_canonicos = npz['labels_canonicos'].tolist()

idx = 10
vetor = score_melhor_jogada[idx]

print("Scores do Databricks:")
for i, label in enumerate(labels_canonicos):
    if vetor[i] > -1e8:
        print(f"  {label}: {vetor[i]}")


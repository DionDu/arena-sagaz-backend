import numpy as np

arquivo = r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz"
npz = np.load(arquivo, allow_pickle=True)
estados = npz['estados']
score_melhor_jogada = npz['score_melhor_jogada']
depth_melhor_jogada = npz['depth_melhor_jogada']
labels_canonicos = npz['labels_canonicos'].tolist()

idx = 10
estado_np = estados[idx]

print("Profundidade usada na Fase 2 para idx 10:", depth_melhor_jogada[idx])

import numpy as np
import os
import sys

sys.path.insert(0, 'D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend')
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada_com_scores
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro

arquivo = r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz"
npz = np.load(arquivo, allow_pickle=True)
estados = npz['estados']
score_melhor_jogada = npz['score_melhor_jogada']
labels_canonicos = npz['labels_canonicos'].tolist()

idx = 10
estado_np = estados[idx]

print("MATRIZ NEUTRA (DO ARQUIVO):")
print(estado_np)

estado = EstadoTabuleiro(4, 3)
estado.matriz = estado_np.copy()
rotulo_calc, dict_scores_calc = melhor_jogada_com_scores(estado, profundidade=7)

vetor_scores_npz = score_melhor_jogada[idx]
dict_scores_npz = {}
for i, label in enumerate(labels_canonicos):
    if vetor_scores_npz[i] > -1e8:
        dict_scores_npz[label] = vetor_scores_npz[i]

print("\\nSCORES NO ARQUIVO NPZ:")
for k, v in dict_scores_npz.items():
    print(f"  {k}: {v}")

print("\\nSCORES RECALCULADOS AGORA:")
for k, v in dict_scores_calc.items():
    print(f"  {k}: {v}")

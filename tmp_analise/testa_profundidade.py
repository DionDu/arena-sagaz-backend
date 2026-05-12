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

mat_live = np.zeros_like(estado_np, dtype=np.int8)
altura, largura = mat_live.shape

for r in range(altura):
    for c in range(largura):
        if r % 2 == 0 and c % 2 == 0:
            mat_live[r, c] = 8 # ponto
        elif r % 2 == 1 and c % 2 == 1:
            mat_live[r, c] = 0 # caixa 
        else:
            if estado_np[r, c] == 9:
                mat_live[r, c] = 1 # aresta

estado = EstadoTabuleiro(4, 3)
estado.matriz = mat_live.copy()

# Vamos rodar minimax com profundidades maiores para ver se bate!
print("Avaliando profundidades 7, 8 e 9 para ver se alguma reflete o score do arquivo:")

for depth in [7, 8, 9]:
    rotulo_calc, dict_scores_calc = melhor_jogada_com_scores(estado, profundidade=depth)
    max_score = max(dict_scores_calc.values())
    print(f"Profundidade {depth} -> Max Score: {max_score}")

print("\\nAgora, avaliando o MINIMAX EXATAMENTE COMO IMPLEMENTADO NO WORKER V7:")
# O worker V7 tem este método: calcular_scores_v7 que a gente acabou de auditar.
from gerador_dados.jogo_pontinhos.gerador_amostras_v7_pontinhos import calcular_scores_v7
# O argumento é uma tupla (estado_neutro_bytes, profundidade)
rotulo, scores_flat, depth_usada = calcular_scores_v7((estado_np.tobytes(), 7))
dict_scores_v7 = {}
for i, label in enumerate(labels_canonicos):
    if scores_flat[i] > -1e8:
        dict_scores_v7[label] = scores_flat[i]
print(f"Max Score via Worker V7 (depth=7): {max(dict_scores_v7.values())}")

print("\\nScores NPZ:")
vetor_scores_npz = score_melhor_jogada[idx]
dict_scores_npz = {}
for i, label in enumerate(labels_canonicos):
    if vetor_scores_npz[i] > -1e8:
        dict_scores_npz[label] = vetor_scores_npz[i]

for k, v in dict_scores_npz.items():
    if v == 1.0:
        print(f"  {k}: {v}")

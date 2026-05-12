import numpy as np
import sys

sys.path.insert(0, 'D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend')
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada_com_scores
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro

arquivo = r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz"
npz = np.load(arquivo, allow_pickle=True)
estado_np = npz['estados'][10]

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

print("Estado inicial do tabuleiro:")
print(estado.matriz)

print("\\nSimulando a jogada H_2_1...")
fechadas = estado.aplicar_traco("H_2_1", 1)
print(f"Caixas fechadas por esta jogada: {fechadas}")
print(estado.matriz)

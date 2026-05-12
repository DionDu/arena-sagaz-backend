import numpy as np
import sys
import os

sys.path.insert(0, 'D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend')
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada_com_scores
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro

arquivo = r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz"
npz = np.load(arquivo, allow_pickle=True)
estados = npz['estados']

idx = 10
estado_np = estados[idx]

print("MATRIZ NEUTRA (DO ARQUIVO):")
print(estado_np)

# Conversão CORRETA para estado live (usado durante as partidas do Minimax)
# Na matriz live (de jogo):
# - Pontos = 8
# - Traços ocupados = 1 ou -1 (usaremos sempre 1 porque de quem é o traço não importa pro Minimax de um turno)
# - Caixas = 0! (o Minimax detecta o dono dinamicamente com base nas bordas e re-avalia quem fez)

mat_live = np.zeros_like(estado_np, dtype=np.int8)
altura, largura = mat_live.shape

for r in range(altura):
    for c in range(largura):
        if r % 2 == 0 and c % 2 == 0:
            mat_live[r, c] = 8 # ponto
        elif r % 2 == 1 and c % 2 == 1:
            mat_live[r, c] = 0 # caixa (SEMPRE 0 na inicialização pro Minimax recontar via arestas)
        else:
            if estado_np[r, c] == 9:
                mat_live[r, c] = 1 # aresta ocupada

print("\\nMATRIZ LIVE RECONSTRUÍDA:")
print(mat_live)

estado = EstadoTabuleiro(4, 3)
estado.matriz = mat_live.copy()

print("\\nCaixas Fechadas INICIAIS computadas pelo motor:", estado.caixas_fechadas_por(1) + estado.caixas_fechadas_por(-1))

rotulo_calc, dict_scores_calc = melhor_jogada_com_scores(estado, profundidade=7)

print("\\nSCORES RECALCULADOS AGORA (COM MATRIZ LIVE CORRETA):")
for k, v in dict_scores_calc.items():
    print(f"  {k}: {v}")


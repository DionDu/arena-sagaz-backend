import numpy as np
import sys

sys.path.insert(0, 'D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend')
from gerador_dados.jogo_pontinhos.minimax_pontinhos import minimax
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro

arquivo = r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz"
npz = np.load(arquivo, allow_pickle=True)
estado_np = npz['estados'][10]

estado = EstadoTabuleiro(4, 3)
estado.matriz = estado_np.copy()

print("Resolvendo o tabuleiro completamente (Profundidades 10 a 20) para o índice 10...")
for depth in range(7, 21):
    tracos = estado.tracos_disponiveis()
    if len(tracos) == 0:
        break
        
    # Vamos avaliar especificamente a jogada H_2_1 que o Databricks diz que dá 1.0 (Vitória) e o local diz 0 (Empate)
    estado_teste = estado.clonar()
    fechadas = estado_teste.aplicar_traco("H_2_1", 1)
    
    if fechadas > 0:
        v = minimax(estado_teste, depth - 1, -10001, 10001, True, fechadas, 0)
    else:
        v = minimax(estado_teste, depth - 1, -10001, 10001, False, 0, 0)
        
    print(f"Profundidade {depth} -> Resultado avaliado para H_2_1: {v}")
    

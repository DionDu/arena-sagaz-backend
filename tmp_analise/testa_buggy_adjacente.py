import numpy as np
import sys

sys.path.insert(0, 'D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend')
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, _VAZIO

arquivo = r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz"
npz = np.load(arquivo, allow_pickle=True)
estado_np = npz['estados'][10]

class EstadoTabuleiroBuggy(EstadoTabuleiro):
    def _caixas_adjacentes(self, r: int, c: int) -> list[tuple[int, int]]:
        # BUG ANTIGO INVERTIDO
        adj = []
        if r % 2 == 1:  # traço vertical -> verificando como se fosse horizontal
            if r - 1 >= 0:
                adj.append((r - 1, c))
            if r + 1 < self.matriz.shape[0]:
                adj.append((r + 1, c))
        else:  # traço horizontal -> verificando como se fosse vertical
            if c - 1 >= 0:
                adj.append((r, c - 1))
            if c + 1 < self.matriz.shape[1]:
                adj.append((r, c + 1))
        return [(br, bc) for (br, bc) in adj if br % 2 == 1 and bc % 2 == 1]

estado = EstadoTabuleiroBuggy(4, 3)
estado.matriz = estado_np.copy()

# Recriando as funções de minimax para usar a classe EstadoTabuleiroBuggy
def avaliar(estado, caixas_ia, caixas_humano):
    return caixas_ia - caixas_humano

def minimax_buggy(estado, profundidade, alpha, beta, maximizando, caixas_ia=0, caixas_humano=0):
    if profundidade == 0 or estado.esta_terminal():
        return avaliar(estado, caixas_ia, caixas_humano)

    tracos_originais = estado.tracos_disponiveis()
    tracos_bons = []
    tracos_normais = []
    jogador_atual = 1 if maximizando else -1
    
    for t in tracos_originais:
        fechadas = estado.aplicar_traco(t, jogador_atual)
        estado.desfazer_traco(t)
        if fechadas > 0:
            tracos_bons.append(t)
        else:
            tracos_normais.append(t)
            
    tracos = tracos_bons + tracos_normais

    if maximizando:
        melhor = -10000
        for traco in tracos:
            fechadas = estado.aplicar_traco(traco, 1)
            if fechadas > 0:
                valor = minimax_buggy(estado, profundidade - 1, alpha, beta, True, caixas_ia + fechadas, caixas_humano)
            else:
                valor = minimax_buggy(estado, profundidade - 1, alpha, beta, False, caixas_ia, caixas_humano)
            estado.desfazer_traco(traco)
            melhor = max(melhor, valor)
            alpha = max(alpha, melhor)
            if beta <= alpha:
                break
        return melhor
    else:
        melhor = 10000
        for traco in tracos:
            fechadas = estado.aplicar_traco(traco, -1)
            if fechadas > 0:
                valor = minimax_buggy(estado, profundidade - 1, alpha, beta, False, caixas_ia, caixas_humano + fechadas)
            else:
                valor = minimax_buggy(estado, profundidade - 1, alpha, beta, True, caixas_ia, caixas_humano)
            estado.desfazer_traco(traco)
            melhor = min(melhor, valor)
            beta = min(beta, melhor)
            if beta <= alpha:
                break
        return melhor

def scores_buggy(estado, profundidade):
    tracos = estado.tracos_disponiveis()
    scores = {}
    for traco in tracos:
        fechadas = estado.aplicar_traco(traco, 1)
        if fechadas > 0:
            valor = minimax_buggy(estado, profundidade - 1, -10001, 10001, True, fechadas, 0)
        else:
            valor = minimax_buggy(estado, profundidade - 1, -10001, 10001, False, 0, 0)
        estado.desfazer_traco(traco)
        scores[traco] = valor
    return scores

print("Recalculando com Minimax usando a verificação de caixas INVERTIDA (Bug antigo)...")
scores = scores_buggy(estado, 7)
max_score = max(scores.values())
print(f"Max Score com BUG antigo: {max_score}")
print(f"Score da H_2_1 com bug: {scores.get('H_2_1', 'N/A')}")

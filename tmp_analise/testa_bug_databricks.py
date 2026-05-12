import numpy as np
import sys

sys.path.insert(0, 'D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend')
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro

arquivo = r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz"
npz = np.load(arquivo, allow_pickle=True)
estado_np = npz['estados'][10]

estado = EstadoTabuleiro(4, 3)
estado.matriz = estado_np.copy()

# Função minimax modificada para NÃO reduzir a profundidade quando o jogador fecha uma caixa e joga de novo
def avaliar(estado: EstadoTabuleiro, caixas_ia: int, caixas_humano: int) -> int:
    return caixas_ia - caixas_humano

def minimax_modified(estado, profundidade, alpha, beta, maximizando, caixas_ia=0, caixas_humano=0):
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
                # MANTÉM PROFUNDIDADE
                valor = minimax_modified(estado, profundidade, alpha, beta, True, caixas_ia + fechadas, caixas_humano)
            else:
                # DIMINUI PROFUNDIDADE
                valor = minimax_modified(estado, profundidade - 1, alpha, beta, False, caixas_ia, caixas_humano)
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
                # MANTÉM PROFUNDIDADE
                valor = minimax_modified(estado, profundidade, alpha, beta, False, caixas_ia, caixas_humano + fechadas)
            else:
                # DIMINUI PROFUNDIDADE
                valor = minimax_modified(estado, profundidade - 1, alpha, beta, True, caixas_ia, caixas_humano)
            estado.desfazer_traco(traco)
            melhor = min(melhor, valor)
            beta = min(beta, melhor)
            if beta <= alpha:
                break
        return melhor

def scores_modified(estado, profundidade):
    tracos = estado.tracos_disponiveis()
    scores = {}
    for traco in tracos:
        fechadas = estado.aplicar_traco(traco, 1)
        if fechadas > 0:
            valor = minimax_modified(estado, profundidade, -10001, 10001, True, fechadas, 0)
        else:
            valor = minimax_modified(estado, profundidade - 1, -10001, 10001, False, 0, 0)
        estado.desfazer_traco(traco)
        scores[traco] = valor
    return scores

print("Recalculando com Minimax que não reduz profundidade ao pontuar...")
scores = scores_modified(estado, 7)
max_score = max(scores.values())
print(f"Max Score com lógica alternativa: {max_score}")
for k, v in scores.items():
    if v == max_score:
        print(f"  {k}: {v}")


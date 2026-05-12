import numpy as np
import os
import sys
import random
import time

sys.path.insert(0, 'D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend')
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada_com_scores
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro

arquivos = [
    r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0002.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0003.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0004.npz"
]

NUM_SAMPLES = 100
random.seed(42)

print(f"--- INICIANDO AUDITORIA AMPLA ({NUM_SAMPLES} AMOSTRAS) ---")

total_testes = 0
divergencias_totais = 0
erros = []

start_time = time.time()

for f in arquivos:
    if not os.path.exists(f):
        print(f"Arquivo não encontrado: {f}")
        continue
        
    npz = np.load(f, allow_pickle=True)
    estados = npz['estados']
    score_melhor_jogada = npz['score_melhor_jogada']
    labels_canonicos = npz['labels_canonicos'].tolist()
    
    n_amostras = estados.shape[0]
    
    valid_indices = []
    for i in range(n_amostras):
        if np.sum(estados[i] == 9) >= 15:
            valid_indices.append(i)
            
    amostras_arquivo = min(NUM_SAMPLES // len(arquivos), len(valid_indices))
    indices = random.sample(valid_indices, amostras_arquivo)
    
    for idx in indices:
        estado_np = estados[idx]
        
        # Converte para live de forma segura, zerando as caixas antigas
        mat_live = np.zeros_like(estado_np, dtype=np.int8)
        for r in range(9):
            for c in range(7):
                if r % 2 == 0 and c % 2 == 0:
                    mat_live[r, c] = 8
                elif r % 2 == 1 and c % 2 == 1:
                    mat_live[r, c] = 0
                else:
                    if estado_np[r, c] == 9:
                        mat_live[r, c] = 1
        
        estado = EstadoTabuleiro(4, 3)
        estado.matriz = mat_live.copy()
        
        if estado.esta_terminal():
            continue
            
        rotulo_calc, dict_scores_calc = melhor_jogada_com_scores(estado, profundidade=7)
        
        vetor_scores_npz = score_melhor_jogada[idx]
        dict_scores_npz = {}
        for i, label in enumerate(labels_canonicos):
            if vetor_scores_npz[i] > -1e8:
                dict_scores_npz[label] = vetor_scores_npz[i]
                
        divergencias_locais = 0
        for jogada in dict_scores_calc.keys():
            if jogada not in dict_scores_npz:
                divergencias_locais += 1
            elif abs(dict_scores_calc[jogada] - dict_scores_npz[jogada]) > 1e-4:
                divergencias_locais += 1
                
        for jogada in dict_scores_npz.keys():
            if jogada not in dict_scores_calc:
                divergencias_locais += 1
                
        if divergencias_locais > 0:
            erros.append((os.path.basename(f), idx))
            divergencias_totais += divergencias_locais
            
        total_testes += 1
        
        if total_testes % 10 == 0:
            print(f"  Testadas {total_testes} matrizes ({time.time() - start_time:.1f}s decorridos)...")

end_time = time.time()

print(f"\\n--- RESULTADO DA AUDITORIA AMPLA ---")
print(f"Total de matrizes validadas: {total_testes}")
print(f"Total de Q-Values conferidos: {total_testes * 31} simulações de nós folha.")
print(f"Tempo de processamento da prova real: {end_time - start_time:.2f} s")
if divergencias_totais == 0:
    print("STATUS: [CONFORMIDADE ABSOLUTA] Nenhuma divergência matemática encontrada em todas as amostras testadas!")
else:
    print(f"STATUS: [FALHA] Encontradas {divergencias_totais} divergências em {len(erros)} matrizes.")
    print("Amostras com erro (Arquivo, Índice):", erros[:10])

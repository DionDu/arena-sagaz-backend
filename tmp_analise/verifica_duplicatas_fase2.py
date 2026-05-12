import numpy as np
import os
import glob

arquivos = [
    r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0002.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0003.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0004.npz"
]

files = [f for f in arquivos if os.path.exists(f)]

if not files:
    print("Nenhum arquivo encontrado na pasta Downloads.")
    exit(0)

print(f"Analisando matrizes duplicadas em {len(files)} arquivos NPZ em Downloads...")

estado_to_scores = {}
estado_to_melhor_jogada = {}

divergencias_scores = 0
divergencias_jogadas = 0
total_duplicadas_avaliadas = 0

for f in files:
    try:
        npz = np.load(f, allow_pickle=True)
        estados = npz['estados']
        melhor_jogada = npz['melhor_jogada']
        score_melhor_jogada = npz['score_melhor_jogada']
        
        n = estados.shape[0]
        
        for i in range(n):
            estado_bytes = estados[i].tobytes()
            mj = str(melhor_jogada[i])
            smj = score_melhor_jogada[i]
            
            if estado_bytes in estado_to_scores:
                total_duplicadas_avaliadas += 1
                
                # Compara scores com pequena tolerância de ponto flutuante
                if not np.allclose(estado_to_scores[estado_bytes], smj, atol=1e-5):
                    divergencias_scores += 1
                
                # Compara melhor jogada (rótulo)
                if estado_to_melhor_jogada[estado_bytes] != mj:
                    divergencias_jogadas += 1
            else:
                estado_to_scores[estado_bytes] = smj
                estado_to_melhor_jogada[estado_bytes] = mj
                
    except Exception as e:
        print(f"Erro ao ler {f}: {e}")

print(f"\\n=== RESULTADO DA ANÁLISE DE DUPLICATAS ===")
print(f"Total de matrizes únicas: {len(estado_to_scores):,}")
print(f"Total de colisões (matrizes duplicadas) avaliadas: {total_duplicadas_avaliadas:,}")
print(f"-> Divergências em 'score_melhor_jogada': {divergencias_scores:,} (Esperado: 0)")
print(f"-> Divergências em 'melhor_jogada': {divergencias_jogadas:,} (Pode ser > 0 devido a empates no argmax)")

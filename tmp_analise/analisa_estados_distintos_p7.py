import numpy as np
import os
import glob

dir_7 = 'dados/profundidade_minmax_7_corrigido'
files_7 = glob.glob(os.path.join(dir_7, '*.npz'))

print(f'Total de arquivos NPZ em {dir_7}: {len(files_7)}')

if len(files_7) == 0:
    print('Nenhum arquivo NPZ encontrado em profundidade 7!')
    exit(0)

total_samples = 0
unique_estados = set()

for f in files_7:
    try:
        npz = np.load(f, allow_pickle=True)
        estados = npz['estados']
        total_samples += estados.shape[0]
        
        # Converte cada matriz 9x7 para bytes (ou tuple) para poder inserir no set
        for i in range(estados.shape[0]):
            estado_bytes = estados[i].tobytes()
            unique_estados.add(estado_bytes)
            
    except Exception as e:
        print(f'Erro ao carregar {f}: {e}')

distinct_samples = len(unique_estados)

print(f'\\n--- RESULTADOS DA ANÁLISE DE DISTINÇÃO ---')
print(f'Total de estados (bruto): {total_samples}')
print(f'Total de estados DISTINTOS (únicos): {distinct_samples}')
print(f'Taxa de repetição: {100 * (1 - distinct_samples/total_samples):.2f}%')

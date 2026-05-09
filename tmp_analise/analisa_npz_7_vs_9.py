import numpy as np
import os
import glob

path_9 = 'dados/profundidade_minmax_9/dataset_pequeno_0001.npz'
dir_7 = 'dados/profundidade_minmax_7_corrigido'

print('--- ANÁLISE NPZ 9 ---')
try:
    npz_9 = np.load(path_9, allow_pickle=True)
    print(f'Keys: {list(npz_9.keys())}')
    estados_9 = npz_9['estados']
    rotulos_9 = npz_9['rotulos']
    scores_9 = npz_9['scores']
    print(f'Estados - shape: {estados_9.shape}, dtype: {estados_9.dtype}')
    print(f'Rotulos - shape: {rotulos_9.shape}, dtype: {rotulos_9.dtype}')
    print(f'Scores  - shape: {scores_9.shape}, dtype: {scores_9.dtype}')
    print(f'Unique values in estados: {np.unique(estados_9)}')
    print(f'Rotulos min/max: {rotulos_9.min():.4f}, {rotulos_9.max():.4f}')
    print(f'Scores min/max: {scores_9.min():.4f}, {scores_9.max():.4f}')
    print(f"Generation mode: {npz_9['generation_mode']}")
    print(f"Minimax depth: {npz_9['minimax_depth']}")
except Exception as e:
    print(f'Erro ao carregar {path_9}: {e}')

print('\n--- ANÁLISE NPZ 7 CORRIGIDO ---')
files_7 = glob.glob(os.path.join(dir_7, '*.npz'))
print(f'Total de arquivos NPZ em {dir_7}: {len(files_7)}')

if len(files_7) == 0:
    print('Nenhum arquivo NPZ encontrado em profundidade 7!')
    exit(0)

total_samples = 0
shapes_estados = set()
shapes_rotulos = set()
dtypes_estados = set()
dtypes_rotulos = set()
all_unique_estados = set()
all_keys = set()
generation_modes = set()
minimax_depths = set()

for f in files_7:
    try:
        npz = np.load(f, allow_pickle=True)
        keys = tuple(sorted(list(npz.keys())))
        all_keys.add(keys)
        
        est = npz['estados']
        rot = npz['rotulos']
        total_samples += est.shape[0]
        shapes_estados.add(est.shape[1:])
        shapes_rotulos.add(rot.shape[1:])
        dtypes_estados.add(str(est.dtype))
        dtypes_rotulos.add(str(rot.dtype))
        all_unique_estados.update(np.unique(est))
        
        if 'generation_mode' in npz:
            generation_modes.add(str(npz['generation_mode']))
        if 'minimax_depth' in npz:
            minimax_depths.add(str(npz['minimax_depth']))
    except Exception as e:
        print(f'Erro ao carregar {f}: {e}')

print(f'\nTotal de amostras (p7): {total_samples}')
print(f'Chaves presentes (p7): {all_keys}')
print(f'Shapes estados (exceto batch) (p7): {shapes_estados}')
print(f'Shapes rotulos (exceto batch) (p7): {shapes_rotulos}')
print(f'Dtypes estados (p7): {dtypes_estados}')
print(f'Dtypes rotulos (p7): {dtypes_rotulos}')
print(f'Generation modes (p7): {generation_modes}')
print(f'Minimax depths (p7): {minimax_depths}')
print(f'Valores únicos agregados em estados (p7): {sorted(list(all_unique_estados))}')

allowed_values = {0, 1, 8, 9}
violacoes = set(all_unique_estados) - allowed_values
if not violacoes:
    print('\nCONFORMIDADE COM CONTRATO: OK (estados contêm apenas 0, 1, 8, 9)')
else:
    print(f'\nCONFORMIDADE COM CONTRATO: FALHA (valores inválidos encontrados: {violacoes})')

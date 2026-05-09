import numpy as np
import os
import glob

dir_7 = 'dados/profundidade_minmax_7_corrigido'
files_7 = glob.glob(os.path.join(dir_7, '*.npz'))

print(f'Analisando {len(files_7)} arquivos NPZ em {dir_7}...')

total_samples = 0
unique_estados_global = set()

# Estrutura para armazenar contagens totais e distintas por faixa
faixas = {
    '5-11 tracos (abertura)': {'total': 0, 'distintos': set()},
    '12-17 tracos (1a metade)': {'total': 0, 'distintos': set()},
    '18-23 tracos (2a metade)': {'total': 0, 'distintos': set()},
    '24-28 tracos (fase quente)': {'total': 0, 'distintos': set()},
    '29-30 tracos (final)': {'total': 0, 'distintos': set()},
    'Fora das faixas (0-4 ou 31)': {'total': 0, 'distintos': set()}
}

for f in files_7:
    try:
        npz = np.load(f, allow_pickle=True)
        estados = npz['estados']
        total_samples += estados.shape[0]
        
        for i in range(estados.shape[0]):
            estado = estados[i]
            estado_bytes = estado.tobytes()
            unique_estados_global.add(estado_bytes)
            
            qtd_tracos = np.count_nonzero(estado == 9)
            
            chave_faixa = ''
            if 5 <= qtd_tracos <= 11:
                chave_faixa = '5-11 tracos (abertura)'
            elif 12 <= qtd_tracos <= 17:
                chave_faixa = '12-17 tracos (1a metade)'
            elif 18 <= qtd_tracos <= 23:
                chave_faixa = '18-23 tracos (2a metade)'
            elif 24 <= qtd_tracos <= 28:
                chave_faixa = '24-28 tracos (fase quente)'
            elif 29 <= qtd_tracos <= 30:
                chave_faixa = '29-30 tracos (final)'
            else:
                chave_faixa = 'Fora das faixas (0-4 ou 31)'
                
            faixas[chave_faixa]['total'] += 1
            faixas[chave_faixa]['distintos'].add(estado_bytes)
            
    except Exception as e:
        print(f'Erro ao carregar {f}: {e}')

print(f'\\n--- RESULTADOS GERAIS ---')
print(f'Total absoluto (bruto): {total_samples}')
print(f'Total distintos: {len(unique_estados_global)}')

print(f'\\n--- DISTRIBUIÇÃO POR FAIXA DE TRAÇOS ---')
for nome_faixa, dados in faixas.items():
    total_faixa = dados['total']
    distintos_faixa = len(dados['distintos'])
    print(f"{nome_faixa}: Total={total_faixa}, Distintos={distintos_faixa}")

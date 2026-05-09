import numpy as np
import os
import glob
import json

dir_7 = 'dados/profundidade_minmax_7_corrigido'
files_7 = glob.glob(os.path.join(dir_7, '*.npz'))

print(f'Analisando {len(files_7)} arquivos NPZ em {dir_7}...')

total_samples = 0
# Dicionário para contar a ocorrência de cada quantidade de traços (9)
distribuicao_tracos = {}

# As faixas solicitadas
faixas = {
    '5-11 tracos (abertura)': 0,
    '12-17 tracos (1a metade)': 0,
    '18-23 tracos (2a metade)': 0,
    '24-28 tracos (fase quente)': 0,
    '29-30 tracos (final)': 0,
    'Fora das faixas (0-4 ou 31)': 0
}

for f in files_7:
    try:
        npz = np.load(f, allow_pickle=True)
        estados = npz['estados']
        total_samples += estados.shape[0]
        
        # Para cada estado, contar quantos traços (valor 9) existem
        for i in range(estados.shape[0]):
            estado = estados[i]
            # Conta elementos iguais a 9 (traços)
            qtd_tracos = np.count_nonzero(estado == 9)
            
            # Incrementa o dicionário geral
            distribuicao_tracos[qtd_tracos] = distribuicao_tracos.get(qtd_tracos, 0) + 1
            
            # Enquadra na faixa correta
            if 5 <= qtd_tracos <= 11:
                faixas['5-11 tracos (abertura)'] += 1
            elif 12 <= qtd_tracos <= 17:
                faixas['12-17 tracos (1a metade)'] += 1
            elif 18 <= qtd_tracos <= 23:
                faixas['18-23 tracos (2a metade)'] += 1
            elif 24 <= qtd_tracos <= 28:
                faixas['24-28 tracos (fase quente)'] += 1
            elif 29 <= qtd_tracos <= 30:
                faixas['29-30 tracos (final)'] += 1
            else:
                faixas['Fora das faixas (0-4 ou 31)'] += 1
            
    except Exception as e:
        print(f'Erro ao carregar {f}: {e}')

print(f'\\n--- DISTRIBUIÇÃO POR FAIXA DE TRAÇOS ---')
print(f'Total de estados analisados: {total_samples}\\n')

for nome_faixa, contagem in faixas.items():
    percentual = (contagem / total_samples) * 100 if total_samples > 0 else 0
    print(f'> {nome_faixa:<28}: {percentual:6.2f}% das amostras ({contagem:6d})')

